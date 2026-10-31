import io
import json
import os
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ranker import score_sign_class, get_fake_queue, compute_active_learning_queue
from app.services.storage import load_features


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup_data(client):
    proj = client.post("/api/projects", json={"name": "TashviTest", "target_language": "ISL"}).json()
    pid = proj["id"]

    sign_a = client.post("/api/sign-classes", json={"project_id": pid, "gloss": "ALPHA"}).json()
    sign_b = client.post("/api/sign-classes", json={"project_id": pid, "gloss": "BETA"}).json()
    signer_1 = client.post("/api/signers", json={"project_id": pid, "code": "SIG-01"}).json()
    signer_2 = client.post("/api/signers", json={"project_id": pid, "code": "SIG-02"}).json()

    consent_1 = client.post("/api/consents", json={
        "signer_id": signer_1["id"],
        "consent_version": "v1",
        "purpose": "ranker test",
        "allowed_uses": ["corpus_building"],
        "retention": "landmarks_only",
        "confirmed": True,
    }).json()

    consent_2 = client.post("/api/consents", json={
        "signer_id": signer_2["id"],
        "consent_version": "v1",
        "purpose": "ranker test",
        "allowed_uses": ["corpus_building"],
        "retention": "landmarks_only",
        "confirmed": True,
    }).json()

    return {
        "project_id": pid,
        "sign_a": sign_a["id"],
        "sign_b": sign_b["id"],
        "signer_1": signer_1["id"],
        "signer_2": signer_2["id"],
        "consent_1": consent_1["id"],
        "consent_2": consent_2["id"],
    }


def capture_sample(client, data, sign_class_id, signer_id, consent_id, source="captured", **over):
    demo = client.get("/api/demo-frames").json()
    body = {
        "project_id": data["project_id"],
        "sign_class_id": sign_class_id,
        "signer_id": signer_id,
        "consent_id": consent_id,
        "source": source,
        "extractor": demo["extractor"],
        "fps": demo["fps"],
        "width": demo["width"],
        "height": demo["height"],
        "frames": demo["frames"],
        **over,
    }
    r = client.post("/api/samples/capture", json=body)
    r.raise_for_status()
    return r.json()


def test_pure_ranker_formula_without_uncertainty():
    # 2 approved samples out of 10 -> coverage_gap = 0.8
    # 1 distinct signer out of 3 -> signer_gap = 1 - 1/3 = 0.667
    res = score_sign_class(
        sign_class_id=1,
        gloss="TEST",
        approved_count=2,
        distinct_signers=1,
        target_samples=10,
        target_signers=3,
        uncertainty=None,
    )
    assert res["coverage_gap"] == 0.8
    assert res["signer_gap"] == pytest.approx(0.667, abs=1e-3)
    assert res["uncertainty"] is None
    assert res["uncertainty_display"] == "Not evaluated yet"
    # priority = (0.35 * 0.8 + 0.25 * 0.667) / 0.60 = (0.28 + 0.1667) / 0.60 = 0.744
    assert res["priority"] == pytest.approx(0.744, abs=1e-3)
    assert res["suggested_signer"] == "new_signer"
    assert "needs 8 more approved samples" in res["reason"]


def test_pure_ranker_formula_with_uncertainty():
    res = score_sign_class(
        sign_class_id=1,
        gloss="TEST",
        approved_count=5,
        distinct_signers=2,
        target_samples=10,
        target_signers=3,
        uncertainty=0.90,
    )
    # cov_gap = 0.5, sig_gap = 0.333, unc = 0.90
    # priority = 0.35 * 0.5 + 0.25 * 0.333 + 0.40 * 0.90 = 0.175 + 0.0833 + 0.36 = 0.618
    assert res["coverage_gap"] == 0.5
    assert res["signer_gap"] == pytest.approx(0.333, abs=1e-3)
    assert res["uncertainty"] == 0.90
    assert res["priority"] == pytest.approx(0.618, abs=1e-3)
    assert "model uncertainty is 0.90" in res["reason"]


def test_fake_queue_endpoint(client):
    r = client.get("/api/active-learning/queue", params={"fake": True})
    assert r.status_code == 200
    data = r.json()
    assert data["formula_version"] == "ranker-v1"
    assert len(data["queue"]) > 0
    top = data["queue"][0]
    assert "gloss" in top and "priority" in top and "reason" in top
    # Priorities should be descending
    priorities = [x["priority"] for x in data["queue"]]
    assert priorities == sorted(priorities, reverse=True)


def test_real_queue_and_frozen_test_isolation(client, setup_data):
    pid = setup_data["project_id"]

    # Initially empty queue (all classes need samples)
    q1 = client.get("/api/active-learning/queue", params={"project_id": pid}).json()["queue"]
    assert len(q1) == 2
    # Both have max priority initially
    assert q1[0]["priority"] == 1.0

    # Add 1 sample for ALPHA, approved
    s1 = capture_sample(client, setup_data, setup_data["sign_a"], setup_data["signer_1"], setup_data["consent_1"])
    client.post(f"/api/samples/{s1['id']}/review", json={
        "reviewer_code": "REV-01", "reviewer_role": "team_non_signer", "decision": "approved"
    }).raise_for_status()

    # Add 1 sample for BETA, but marked with split="test" (FROZEN TEST SET)
    s2 = capture_sample(client, setup_data, setup_data["sign_b"], setup_data["signer_2"], setup_data["consent_2"])
    client.post(f"/api/samples/{s2['id']}/review", json={
        "reviewer_code": "REV-01", "reviewer_role": "team_non_signer", "decision": "approved"
    }).raise_for_status()

    # Manually mark s2 as test split
    from sqlmodel import Session
    from app.db import engine
    from app.db.models import Sample
    with Session(engine) as session:
        samp = session.get(Sample, s2["id"])
        samp.split = "test"
        session.add(samp)
        session.commit()

    # Re-query queue: BETA's test sample MUST NOT be counted!
    q2 = client.get("/api/active-learning/queue", params={"project_id": pid}).json()["queue"]
    q_map = {x["gloss"]: x for x in q2}

    # ALPHA has 1 approved training sample
    assert q_map["ALPHA"]["approved_sample_count"] == 1
    assert q_map["ALPHA"]["distinct_signer_count"] == 1

    # BETA has 1 sample in test split -> counted as 0!
    assert q_map["BETA"]["approved_sample_count"] == 0
    assert q_map["BETA"]["distinct_signer_count"] == 0
    assert q_map["BETA"]["priority"] > q_map["ALPHA"]["priority"]


def test_export_corpus_zip(client, setup_data):
    pid = setup_data["project_id"]
    r = client.get("/api/export/corpus", params={"project_id": pid})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    # Inspect zip contents
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == "SIGNFORGE_CORPUS_MANIFEST_V1"
        assert manifest["governance"]["raw_video_included"] is False
        assert manifest["project"]["name"] == "TashviTest"
        # Only approved samples in export
        assert len(manifest["samples"]) >= 1


def test_delete_sample(client, setup_data):
    s = capture_sample(client, setup_data, setup_data["sign_a"], setup_data["signer_1"], setup_data["consent_1"])
    feat_path = s["feature_path"]
    assert os.path.exists(feat_path)

    # Delete sample
    del_res = client.delete(f"/api/samples/{s['id']}")
    assert del_res.status_code == 204

    # Feature file on disk must be removed
    assert not os.path.exists(feat_path)

    # Querying landmarks must return 404
    assert client.get(f"/api/samples/{s['id']}/landmarks").status_code == 404


def test_withdraw_consent(client, setup_data):
    signer = client.post("/api/signers", json={"project_id": setup_data["project_id"], "code": "SIG-W1"}).json()
    consent = client.post("/api/consents", json={
        "signer_id": signer["id"],
        "consent_version": "v1",
        "purpose": "withdrawal test",
        "allowed_uses": ["corpus_building"],
        "retention": "landmarks_only",
        "confirmed": True,
    }).json()

    s = capture_sample(client, setup_data, setup_data["sign_a"], signer["id"], consent["id"])
    client.post(f"/api/samples/{s['id']}/review", json={
        "reviewer_code": "REV-01", "reviewer_role": "team_non_signer", "decision": "approved"
    }).raise_for_status()

    # Withdraw consent with delete_samples=False
    r = client.post(f"/api/consents/{consent['id']}/withdraw", json={"delete_samples": False})
    assert r.status_code == 200
    assert r.json() == {"status": "withdrawn", "deleted_samples": 0}

    # Check sample is now marked rejected and provenance note updated
    updated_sample = client.get(f"/api/samples", params={"project_id": setup_data["project_id"]}).json()
    target = next((x for x in updated_sample if x["id"] == s["id"]), None)
    assert target is not None
    assert target["review_status"] == "rejected"
    assert "[CONSENT WITHDRAWN]" in target["provenance_note"]
