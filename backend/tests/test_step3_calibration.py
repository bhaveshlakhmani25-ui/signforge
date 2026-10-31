import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.calibration import fit_temperature, reliability, softmax
from app.services.splits import SESSION_GROUPED, assign_grouped_splits, session_groups


def test_temperature_recovers_known_overconfidence():
    rng = np.random.default_rng(0)
    true = rng.normal(0, 1.5, (4000, 5))
    y = np.array([rng.choice(5, p=p) for p in softmax(true)])
    assert 2.4 < fit_temperature(true * 3, y) < 3.8  # logits made 3x too confident -> T close to 3
    assert 0.8 < fit_temperature(true, y) < 1.25     # already calibrated -> T close to 1


def test_reliability_bins_and_ece():
    probs = np.array([[0.95, 0.05], [0.9, 0.1], [0.3, 0.7], [0.45, 0.55]])
    r = reliability(probs, np.array([0, 1, 1, 1]), 5)
    assert sum(b["n"] for b in r["bins"]) == 4 and r["n"] == 4
    top = r["bins"][-1]
    assert top["n"] == 2 and top["accuracy"] == 0.5  # 0.95 right, 0.9 wrong
    assert reliability(np.array([[1.0, 0.0]] * 3), np.array([0, 0, 0]), 5)["ece"] == 0


def rows(n_classes=2, groups=(3, 3, 4, 3)):
    out, sid = [], 0
    for c in range(n_classes):
        num = 10
        for g in groups:
            for _ in range(g):
                out.append({"id": sid, "sign_class_id": c, "split": "unassigned", "external_sample_id": f"MVI_{num:04d}"})
                sid, num = sid + 1, num + 1
            num += 20  # gap between recording sessions
    return out


def test_grouped_split_holds_out_whole_sessions_and_stays_frozen():
    rs = rows()
    changes, strategy = assign_grouped_splits(rs)
    assert strategy == SESSION_GROUPED
    for c in (0, 1):
        mine = [r for r in rs if r["sign_class_id"] == c]
        g = session_groups(mine)
        for split in ("test", "val"):
            held = {g[r["id"]] for r in mine if changes[r["id"]] == split}
            assert len(held) == 1  # exactly one whole session per sign
            assert all(changes[r["id"]] == split for r in mine if g[r["id"]] in held)
    for r in rs:
        r["split"] = changes[r["id"]]
    new = {"id": 999, "sign_class_id": 0, "split": "unassigned", "external_sample_id": "MVI_0011"}
    again, strategy = assign_grouped_splits(rs + [new])
    assert strategy is None and again == {999: "train"}  # frozen: never re-drawn, new clips only train


def test_external_pool_trains_and_calibrates_on_val_judged_on_test():
    with TestClient(app) as client:
        p = client.post("/api/projects", json={"name": "EXT", "target_language": "ISL"}).json()["id"]
        signs = [client.post("/api/sign-classes", json={"project_id": p, "gloss": g}).json()["id"] for g in ("A", "B")]
        signer = client.post("/api/signers", json={"project_id": p, "code": "EXT-1"}).json()["id"]
        consent = client.post("/api/consents", json={"signer_id": signer, "consent_version": "v1", "purpose": "t",
                              "allowed_uses": ["corpus_building", "model_training"], "retention": "landmarks_only",
                              "confirmed": True}).json()["id"]
        seed = 0
        for ci, sign in enumerate(signs):
            for g in range(4):
                for k in range(3):
                    seed += 1
                    demo = client.get("/api/demo-frames", params={"class_index": ci, "seed": seed}).json()
                    client.post("/api/samples/capture", json={
                        "project_id": p, "sign_class_id": sign, "signer_id": signer, "consent_id": consent,
                        "source": "external_dataset", "extractor": demo["extractor"], "fps": demo["fps"],
                        "width": demo["width"], "height": demo["height"], "frames": demo["frames"],
                        "external_sample_id": f"MVI_{100 * g + k:04d}"}).raise_for_status()
        assert client.post("/api/models/train-baseline", json={"project_id": p, "pool": "real"}).status_code == 422
        run = client.post("/api/models/train-baseline", json={"project_id": p, "pool": "external"}).json()
        assert run["status"] == "succeeded", run.get("failure_detail")
        cal = run["metrics"]["calibration"]
        assert cal["n_val"] == 6 and cal["test_after"]["n"] == 6 and run["metrics"]["n_train"] == 12
        assert set(run["metrics"]["val_sample_ids"]).isdisjoint(run["test_sample_ids"] + run["train_sample_ids"])
        assert run["metrics"]["label_glosses"] == {str(signs[0]): "A", str(signs[1]): "B"}
        assert isinstance(cal["reliability_passed"], bool) and cal["temperature"] > 0
