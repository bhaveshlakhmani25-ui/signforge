import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core import config as C
from app.main import app
from app.services.demo_fixture import demo_frames
from app.services.evaluation import classification_metrics
from app.services.preprocessing import frames_to_arrays, model_input
from app.services.splits import RANDOM_CLIP, SIGNER_INDEPENDENT, assign_splits


def test_metrics_on_hand_computed_example():
    # true: A A B B C ; pred: A B B B A
    m = classification_metrics([1, 1, 2, 2, 3], [1, 2, 2, 2, 1], [1, 2, 3])
    assert m["accuracy"] == 0.6
    assert m["confusion_matrix"] == [[1, 1, 0], [0, 2, 0], [1, 0, 0]]
    # A: P=1/2 R=1/2 F1=.5 ; B: P=2/3 R=1 F1=.8 ; C: 0
    assert m["per_class"][1]["f1"] == 0.5 and m["per_class"][2]["f1"] == 0.8 and m["per_class"][3]["f1"] == 0.0
    assert m["macro_f1"] == pytest.approx((0.5 + 0.8 + 0) / 3, abs=1e-4)


def test_macro_f1_ignores_classes_without_test_support():
    m = classification_metrics([1, 1], [1, 1], [1, 2])
    assert m["macro_f1"] == 1.0 and m["per_class"][2]["support"] == 0


def test_model_input_shape_and_contract():
    points, _, t = frames_to_arrays(demo_frames(0, seconds=2.0))
    x = model_input(points, t, C.TARGET_FPS, C.MODEL_FRAMES)
    assert x.shape == (C.MODEL_FRAMES, 27, 2) and x.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(x[:, 3] - x[:, 4], axis=-1).mean(), 1, atol=1e-4)


def _rows(n_signers, per_class=5, classes=(1, 2)):
    rows, i = [], 0
    for sg in range(n_signers):
        for c in classes:
            for _ in range(per_class):
                i += 1
                rows.append({"id": i, "signer_id": 100 + sg, "sign_class_id": c, "split": "unassigned"})
    return rows


def test_random_clip_split_is_stratified_and_labelled_honestly():
    changes, strategy = assign_splits(_rows(2))
    assert strategy == RANDOM_CLIP and "NOT signer-independent" in strategy
    test_ids = {i for i, s in changes.items() if s == "test"}
    rows = {r["id"]: r for r in _rows(2)}
    assert {rows[i]["sign_class_id"] for i in test_ids} == {1, 2}  # every class tested
    assert len(test_ids) == 4  # 20% of 10 per class


def test_signer_independent_split_holds_out_whole_signer():
    rows = _rows(3)
    changes, strategy = assign_splits(rows)
    assert strategy == SIGNER_INDEPENDENT
    test_signers = {r["signer_id"] for r in rows if changes[r["id"]] == "test"}
    train_signers = {r["signer_id"] for r in rows if changes[r["id"]] == "train"}
    assert len(test_signers) == 1 and not test_signers & train_signers


def test_frozen_test_never_grows():
    rows = _rows(2)
    first, _ = assign_splits(rows)
    for r in rows:
        r["split"] = first[r["id"]]
    rows.append({"id": 999, "signer_id": 100, "sign_class_id": 1, "split": "unassigned"})
    second, strategy = assign_splits(rows)
    assert strategy is None and second == {999: "train"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def project(client):
    p = client.post("/api/projects", json={"name": "ModelTest", "target_language": "ISL"}).json()
    classes = [client.post("/api/sign-classes", json={"project_id": p["id"], "gloss": g}).json() for g in ("A", "B", "C")]
    signer = client.post("/api/signers", json={"project_id": p["id"], "code": "DEMO-T1"}).json()
    consent = client.post("/api/consents", json={"signer_id": signer["id"], "consent_version": "v1", "purpose": "test",
                                                 "allowed_uses": ["corpus_building"], "retention": "landmarks_only",
                                                 "confirmed": True}).json()
    for ci, c in enumerate(classes):
        for seed in range(5):
            client.post("/api/samples/capture", json={
                "project_id": p["id"], "sign_class_id": c["id"], "signer_id": signer["id"], "consent_id": consent["id"],
                "source": "demo_fixture", "extractor": "demo", "fps": 30, "width": 1280, "height": 720,
                "frames": demo_frames(ci, seed=seed + 50)}).raise_for_status()
    return p


def test_real_pool_without_approved_samples_is_refused(client, project):
    r = client.post("/api/models/train-baseline", json={"project_id": project["id"], "pool": "real"})
    assert r.status_code == 422 and "approved" in r.json()["detail"]


def test_demo_pool_trains_and_records_run(client, project):
    run = client.post("/api/models/train-baseline", json={"project_id": project["id"], "pool": "demo"}).json()
    assert run["status"] == "succeeded", run["failure_detail"]
    assert run["pool"] == "demo" and run["checkpoint_reference"].startswith("none")
    assert run["split_strategy"] == RANDOM_CLIP
    m = run["metrics"]
    assert m["n_test"] == len(run["test_sample_ids"]) == 3 and m["n_train"] == 12
    assert 0 <= m["accuracy"] <= 1 and len(m["confusion_matrix"]) == 3
    assert not set(run["train_sample_ids"]) & set(run["test_sample_ids"])


def test_second_run_reuses_frozen_test_set(client, project):
    runs = [client.post("/api/models/train-baseline", json={"project_id": project["id"], "pool": "demo"}).json()
            for _ in range(2)]
    assert runs[0]["test_sample_ids"] == runs[1]["test_sample_ids"]
    assert runs[1]["split_strategy"] == RANDOM_CLIP
    assert runs[0]["metrics"]["confusion_matrix"] == runs[1]["metrics"]["confusion_matrix"]  # fixed seed
    listed = client.get("/api/models/runs", params={"project_id": project["id"]}).json()
    assert len(listed) >= 3


def test_signer_split_prefers_signer_covering_most_classes():
    rows = _rows(3) + [{"id": 500, "signer_id": 999, "sign_class_id": 1, "split": "unassigned"}]  # 1-clip signer
    changes, _ = assign_splits(rows)
    assert changes[500] == "train"


def test_demo_pool_respects_reviewer_rejection(client, project):
    runs = client.get("/api/models/runs", params={"project_id": project["id"]}).json()
    victim = runs[0]["train_sample_ids"][0]
    client.post(f"/api/samples/{victim}/review", json={"reviewer_code": "R-09", "reviewer_role": "team_non_signer",
                                                       "decision": "needs_recapture"}).raise_for_status()
    run = client.post("/api/models/train-baseline", json={"project_id": project["id"], "pool": "demo"}).json()
    assert victim not in run["train_sample_ids"] and run["metrics"]["n_train"] == 11


def _freeze(rows):
    changes, _ = assign_splits(rows)
    for r in rows:
        r["split"] = changes.get(r["id"], r["split"])
    return rows


def test_held_out_signer_new_clips_never_join_train():
    rows = _freeze(_rows(3))
    held_out = next(r["signer_id"] for r in rows if r["split"] == "test")
    rows.append({"id": 900, "signer_id": held_out, "sign_class_id": 1, "split": "unassigned"})
    rows.append({"id": 901, "signer_id": 555, "sign_class_id": 1, "split": "unassigned"})  # brand-new signer
    changes, strategy = assign_splits(rows)
    assert strategy is None and 900 not in changes and changes[901] == "train"


def test_redrawn_test_set_never_takes_trained_clips():
    rows = _freeze(_rows(2))
    for r in rows:
        if r["split"] == "test":
            r["split"] = "gone"  # e.g. test clips later rejected and no longer eligible
    rows = [r for r in rows if r["split"] != "gone"]
    rows += [{"id": 700 + i, "signer_id": 100, "sign_class_id": 1 + i % 2, "split": "unassigned"} for i in range(4)]
    changes, _ = assign_splits(rows)
    assert {i for i, s in changes.items() if s == "test"} <= {700, 701, 702, 703}


def test_training_respects_model_training_consent(client):
    p = client.post("/api/projects", json={"name": "ConsentTest", "target_language": "ISL"}).json()
    classes = [client.post("/api/sign-classes", json={"project_id": p["id"], "gloss": g}).json() for g in ("A", "B")]

    def signer(code, uses):
        s = client.post("/api/signers", json={"project_id": p["id"], "code": code}).json()
        c = client.post("/api/consents", json={"signer_id": s["id"], "consent_version": "v1", "purpose": "t",
                                               "allowed_uses": uses, "retention": "landmarks_only", "confirmed": True}).json()
        return s["id"], c["id"]

    def add(sid, cid, ci, seed):
        s = client.post("/api/samples/capture", json={
            "project_id": p["id"], "sign_class_id": classes[ci]["id"], "signer_id": sid, "consent_id": cid,
            "source": "captured", "extractor": "test", "fps": 30, "width": 1280, "height": 720,
            "frames": demo_frames(ci, seed=seed)}).json()
        client.post(f"/api/samples/{s['id']}/review", json={"reviewer_code": "R-1", "reviewer_role": "native_signer",
                                                            "decision": "approved"}).raise_for_status()
        return s["id"]

    ok = signer("OK-1", ["corpus_building", "model_training"])
    no = signer("NO-1", ["corpus_building"])
    for ci in (0, 1):
        for seed in range(3):
            add(*ok, ci, 200 + seed)
    forbidden = add(*no, 0, 300)
    run = client.post("/api/models/train-baseline", json={"project_id": p["id"], "pool": "real"}).json()
    assert run["status"] == "succeeded", run
    assert forbidden not in run["train_sample_ids"] + run["test_sample_ids"]
