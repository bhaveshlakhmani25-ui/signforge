"""Redesign brief section 8: triage tiers, audit rate, near-duplicates, auto-accepted clips never train or test."""
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.models import eligible_samples
from app.core import thresholds as TH
from app.db import engine
from app.db.models import ModelRun
from app.main import app
from app.services import triage


@pytest.fixture(scope="module")
def env():
    with TestClient(app) as client:
        p = client.post("/api/projects", json={"name": "TRIAGE", "target_language": "ISL"}).json()["id"]
        sign = {g: client.post("/api/sign-classes", json={"project_id": p, "gloss": g}).json()["id"] for g in ("A", "B", "UNSEEN")}

        def signer(code, uses):
            sid = client.post("/api/signers", json={"project_id": p, "code": code}).json()["id"]
            cid = client.post("/api/consents", json={"signer_id": sid, "consent_version": "v1", "purpose": "t", "allowed_uses": uses,
                                                     "retention": "landmarks_only", "confirmed": True}).json()["id"]
            return sid, cid
        ext, team = signer("EXT-T", ["corpus_building", "model_training"]), signer("TEAM-1", ["corpus_building", "model_training"])
        seed = 100
        for ci, g in enumerate(("A", "B")):
            for grp in range(4):
                for k in range(3):
                    seed += 1
                    d = client.get("/api/demo-frames", params={"class_index": ci, "seed": seed}).json()
                    client.post("/api/samples/capture", json={
                        "project_id": p, "sign_class_id": sign[g], "signer_id": ext[0], "consent_id": ext[1], "source": "external_dataset",
                        "extractor": d["extractor"], "fps": d["fps"], "width": d["width"], "height": d["height"], "frames": d["frames"],
                        "external_sample_id": f"MVI_{100 * grp + k:04d}"}).raise_for_status()
        run = client.post("/api/models/train-baseline", json={"project_id": p, "pool": "external"}).json()
        assert run["status"] == "succeeded"

        def capture(gloss, class_index, seed, frames=None):
            d = client.get("/api/demo-frames", params={"class_index": class_index, "seed": seed}).json()
            r = client.post("/api/samples/capture", json={
                "project_id": p, "sign_class_id": sign[gloss], "signer_id": team[0], "consent_id": team[1], "source": "captured",
                "extractor": d["extractor"], "fps": d["fps"], "width": d["width"], "height": d["height"], "frames": frames or d["frames"]})
            r.raise_for_status()
            return r.json()
        yield {"client": client, "p": p, "capture": capture, "run_id": run["id"]}


def test_quality_fail_is_auto_rejected(env):
    d = env["client"].get("/api/demo-frames", params={"class_index": 0, "seed": 900}).json()
    s = env["capture"]("A", 0, 900, frames=d["frames"][:5])  # 5 frames: too short
    assert s["triage_status"] == "auto_rejected" and s["review_status"] == "pending_review"


def test_disagreement_needs_review(env):
    s = env["capture"]("A", 1, 901)  # claims A, signs B
    assert s["predicted_sign"] == "B" and s["triage_status"] == "needs_review"
    assert "looks more like B" in s["triage"]["reason"]


def test_sign_the_model_never_learned_needs_review(env):
    s = env["capture"]("UNSEEN", 0, 902)
    assert s["triage_status"] == "needs_review" and s["match_confidence"] is None and "has not learned" in s["triage"]["reason"]


def test_agreement_with_auto_accept_off_still_needs_review(env):
    s = env["capture"]("A", 0, 903)
    t = s["triage"]
    assert t["predicted_sign"] == "A" and len(t["top3"]) == 2 and t["calibration_note"]
    assert s["triage_status"] == "needs_review" and t["auto_accept_enabled"] is False
    assert t["per_sign_test_recall"]["support"] > 0


def passing_run(monkeypatch):
    real = triage.reference_run

    def patched(session):
        run = real(session)
        cal = {**run.metrics["calibration"], "reliability_passed": True}
        return ModelRun(**{**run.model_dump(), "metrics": {**run.metrics, "calibration": cal}})  # detached copy, never saved
    monkeypatch.setattr(triage, "reference_run", patched)
    monkeypatch.setattr(TH, "MODEL_VERIFY_ENABLED", True)
    monkeypatch.setattr(TH, "VERIFY_MIN_CONF", 0.0)  # synthetic data: test the rule, not this model's confidence


def test_agreement_high_confidence_is_model_verified_and_never_trains(env, monkeypatch):
    passing_run(monkeypatch)
    monkeypatch.setattr(TH, "DUP_EPSILON", 0.0)  # synthetic clips of one sign are near-identical; duplicates have their own test
    s = env["capture"]("B", 1, 904)
    assert s["triage_status"] == "model_verified" and s["review_status"] == "pending_review", s["triage"]["reason"]
    with Session(engine) as session:  # auto-accepted clips never enter training, so never the frozen test set either
        assert s["id"] not in {x.id for x in eligible_samples(session, env["p"], "real")}


def test_near_duplicate_flagged_and_not_auto_accepted(env, monkeypatch):
    passing_run(monkeypatch)
    d = env["client"].get("/api/demo-frames", params={"class_index": 1, "seed": 905}).json()
    env["capture"]("B", 1, 905, frames=d["frames"])
    for f in d["frames"]:  # tiny jitter: not byte-identical, so the hash check does not catch it
        f["pose"][0][0] += 1e-4
    s = env["capture"]("B", 1, 905, frames=d["frames"])
    assert s["is_near_duplicate"] is True and s["triage_status"] == "needs_review"
    assert "almost identical" in s["triage"]["reason"] and "switched off" not in s["triage"]["reason"]


def test_audit_rate():
    rate = np.mean([triage.audited(i) for i in range(1, 4001)])
    assert abs(rate - TH.AUDIT_RATE) < 0.02


def test_predict_endpoint_and_status_precedence(env):
    s = env["capture"]("A", 0, 906)
    r = env["client"].post("/api/predict", json={"sample_id": s["id"]}).json()
    assert r["claimed_sign"] == "A" and r["model"]["run_id"] == env["run_id"]
    env["client"].post(f"/api/samples/{s['id']}/review", json={"reviewer_code": "R1", "reviewer_role": "team_non_signer",
                                                               "decision": "approved"}).raise_for_status()
    with Session(engine) as session:
        from app.db.models import Sample
        assert triage.status_of(session.get(Sample, s["id"])) == "human_verified"  # a human decision always wins


def test_interpret_reads_a_window_without_storing_it(env):
    client = env["client"]
    d = client.get("/api/demo-frames", params={"class_index": 1, "seed": 950}).json()
    before = len(client.get("/api/samples", params={"project_id": env["p"]}).json())
    r = client.post("/api/interpret", json={"frames": d["frames"]}).json()
    assert r["state"] in ("sign", "unsure") and set(r["vocabulary"]) == {"A", "B"} and r["top3"]
    if r["state"] == "sign":
        assert r["sign"] == "B"
    assert len(client.get("/api/samples", params={"project_id": env["p"]}).json()) == before  # nothing stored

    still = [dict(d["frames"][10], t=i / 30) for i in range(60)]
    assert client.post("/api/interpret", json={"frames": still}).json()["state"] == "still"
    no_hands = [dict(f, left_hand=None, right_hand=None) for f in d["frames"]]
    assert client.post("/api/interpret", json={"frames": no_hands}).json()["state"] == "no_hands"
    assert client.post("/api/interpret", json={"frames": d["frames"][:3]}).json()["state"] == "waiting"


def test_interpreter_language_list_and_project_choice(env):
    client = env["client"]
    langs = client.get("/api/interpret/languages").json()
    mine = next(l for l in langs if l["project_id"] == env["p"])
    assert mine["n_signs"] == 2 and mine["run_id"] == env["run_id"]
    d = client.get("/api/demo-frames", params={"class_index": 0, "seed": 960}).json()
    r = client.post("/api/interpret", json={"frames": d["frames"], "project_id": env["p"]}).json()
    assert r["run_id"] == env["run_id"] and set(r["vocabulary"]) == {"A", "B"}


def test_interpret_test_clip_reads_a_held_out_clip(env):
    client = env["client"]
    run = next(r for r in client.get("/api/models/runs", params={"project_id": env["p"]}).json() if r["id"] == env["run_id"])
    r = client.post("/api/interpret/test-clip", params={"project_id": env["p"]}).json()
    assert r["sample_id"] in run["test_sample_ids"] and r["true_sign"] in ("A", "B")
    assert r["reading"]["run_id"] == env["run_id"] and r["reading"]["state"] in ("sign", "unsure")
    assert client.post("/api/interpret/test-clip", params={"project_id": 999999}).status_code == 404


def test_learn_signs_lists_known_signs_with_examples(env):
    client = env["client"]
    r = client.get("/api/learn/signs", params={"project_id": env["p"]}).json()
    assert r["run_id"] == env["run_id"] and [s["gloss"] for s in r["signs"]] == ["A", "B"]  # UNSEEN was never trained
    assert all(1 <= len(s["examples"]) <= 3 for s in r["signs"])
    d = client.get("/api/demo-frames", params={"class_index": 0, "seed": 970}).json()
    probs = client.post("/api/interpret", json={"frames": d["frames"], "project_id": env["p"]}).json()["probs"]
    assert set(probs) == {"A", "B"} and abs(sum(probs.values()) - 1) < 0.01
    assert client.get("/api/learn/signs", params={"project_id": 999999}).status_code == 404
