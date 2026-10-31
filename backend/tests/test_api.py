import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import load_features


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ids(client):
    project = client.post("/api/projects", json={"name": "T", "target_language": "ISL"}).json()
    sign = client.post("/api/sign-classes", json={"project_id": project["id"], "gloss": "HELLO"}).json()
    signer = client.post("/api/signers", json={"project_id": project["id"], "code": "S-01"}).json()
    consent = client.post("/api/consents", json={
        "signer_id": signer["id"], "consent_version": "v1", "purpose": "test", "allowed_uses": ["corpus_building"],
        "retention": "landmarks_only", "confirmed": True}).json()
    return {"project_id": project["id"], "sign_class_id": sign["id"], "signer_id": signer["id"],
            "consent_id": consent["id"]}


def capture_body(client, ids, source="captured", **over):
    demo = client.get("/api/demo-frames").json()
    return {**ids, "source": source, "extractor": demo["extractor"], "fps": demo["fps"], "width": demo["width"],
            "height": demo["height"], "frames": demo["frames"], **over}


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_signer_code_rejects_real_name_like_input(client, ids):
    r = client.post("/api/signers", json={"project_id": ids["project_id"], "code": "Priya Sharma"})
    assert r.status_code == 422


def test_consent_requires_confirmation(client, ids):
    r = client.post("/api/consents", json={
        "signer_id": ids["signer_id"], "consent_version": "v1", "purpose": "x", "allowed_uses": ["corpus_building"],
        "retention": "landmarks_only", "confirmed": False})
    assert r.status_code == 422


def test_capture_without_consent_is_403(client, ids):
    r = client.post("/api/samples/capture", json=capture_body(client, ids, consent_id=99999))
    assert r.status_code == 403


def test_capture_with_consent_not_covering_corpus_is_403(client, ids):
    c = client.post("/api/consents", json={
        "signer_id": ids["signer_id"], "consent_version": "v1", "purpose": "x", "allowed_uses": ["model_training"],
        "retention": "landmarks_only", "confirmed": True}).json()
    assert client.post("/api/samples/capture", json=capture_body(client, ids, consent_id=c["id"])).status_code == 403


def test_capture_rejects_mirrored_and_malformed(client, ids):
    assert client.post("/api/samples/capture", json=capture_body(client, ids, mirrored=True)).status_code == 422
    body = capture_body(client, ids)
    body["frames"][0]["pose"] = body["frames"][0]["pose"][:10]
    assert client.post("/api/samples/capture", json=body).status_code == 422


def test_capture_list_review_lifecycle(client, ids):
    r = client.post("/api/samples/capture", json=capture_body(client, ids))
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["review_status"] == "pending_review" and s["qc_passed"] and s["frame_count"] == 60
    assert s["raw_video_retained"] is False and s["mirrored"] is False
    assert os.path.exists(s["feature_path"]) and load_features(s["feature_path"])["points"].shape == (60, 75, 3)

    listed = client.get("/api/samples", params={"project_id": ids["project_id"]}).json()
    assert s["id"] in [x["id"] for x in listed]

    recapture = client.post(f"/api/samples/{s['id']}/review", json={
        "reviewer_code": "R-01", "reviewer_role": "team_non_signer", "decision": "needs_recapture", "note": "cut off"}).json()
    assert recapture["review_status"] == "needs_recapture"
    approved = client.post(f"/api/samples/{s['id']}/review", json={
        "reviewer_code": "R-02", "reviewer_role": "native_signer", "decision": "approved"}).json()
    assert approved["review_status"] == "approved"
    bad = client.post(f"/api/samples/{s['id']}/review", json={
        "reviewer_code": "R-02", "reviewer_role": "native_signer", "decision": "flagged"})
    assert bad.status_code == 422
    roles = [e["reviewer_role"] for e in client.get(f"/api/samples/{s['id']}/reviews").json()]
    assert roles == ["team_non_signer", "native_signer"]


def test_demo_fixtures_excluded_by_default(client, ids):
    demo = client.post("/api/samples/capture", json=capture_body(client, ids, source="demo_fixture")).json()
    assert demo["provenance_note"].startswith("DEMO DATA")
    default_ids = [x["id"] for x in client.get("/api/samples", params={"project_id": ids["project_id"]}).json()]
    all_ids = [x["id"] for x in client.get("/api/samples", params={"project_id": ids["project_id"],
                                                                     "include_demo": True}).json()]
    assert demo["id"] not in default_ids and demo["id"] in all_ids


def test_exact_duplicate_is_flagged(client, ids):
    first = client.post("/api/samples/capture", json=capture_body(client, ids, frames=client.get(
        "/api/demo-frames", params={"seed": 7}).json()["frames"])).json()
    second = client.post("/api/samples/capture", json=capture_body(client, ids, frames=client.get(
        "/api/demo-frames", params={"seed": 7}).json()["frames"])).json()
    assert "duplicate" not in {f["code"] for f in first["quality_flags"]}
    assert not second["qc_passed"]
    assert any(f["code"] == "duplicate" and f"#{first['id']}" in f["message"] for f in second["quality_flags"])


def test_landmarks_replay_endpoint(client, ids):
    s = client.post("/api/samples/capture", json=capture_body(client, ids, frames=client.get(
        "/api/demo-frames", params={"seed": 31}).json()["frames"])).json()
    r = client.get(f"/api/samples/{s['id']}/landmarks").json()
    assert r["fps"] == 15 and len(r["frames"]) == 30  # 2 s demo clip at 15 fps
    f = r["frames"][0]
    assert len(f["pose"]) == 33 and len(f["left"]) == 21 and len(f["pose"][0]) == 2
    assert client.get("/api/samples/999999/landmarks").status_code == 404


def test_capture_with_another_signers_consent_is_403(client, ids):
    other = client.post("/api/signers", json={"project_id": ids["project_id"], "code": "OTHER-1"}).json()
    r = client.post("/api/samples/capture", json=capture_body(client, ids, signer_id=other["id"]))
    assert r.status_code == 403


def new_signer(client, ids, code, uses=("corpus_building", "model_training")):
    signer = client.post("/api/signers", json={"project_id": ids["project_id"], "code": code}).json()
    consent = client.post("/api/consents", json={
        "signer_id": signer["id"], "consent_version": "v1", "purpose": "test", "allowed_uses": list(uses),
        "retention": "landmarks_only", "confirmed": True}).json()
    return {**ids, "signer_id": signer["id"], "consent_id": consent["id"]}


def test_delete_sample_removes_file_row_and_reviews(client, ids):
    s = client.post("/api/samples/capture", json=capture_body(client, ids, frames=client.get(
        "/api/demo-frames", params={"seed": 41}).json()["frames"])).json()
    client.post(f"/api/samples/{s['id']}/review", json={"reviewer_code": "R-01", "reviewer_role": "team_non_signer",
                                                        "decision": "approved"})
    assert os.path.exists(s["feature_path"])
    assert client.delete(f"/api/samples/{s['id']}").status_code == 204
    assert not os.path.exists(s["feature_path"])
    assert s["id"] not in [x["id"] for x in client.get("/api/samples", params={"project_id": ids["project_id"]}).json()]
    assert client.get(f"/api/samples/{s['id']}/reviews").json() == []
    assert client.delete(f"/api/samples/{s['id']}").status_code == 404
    again = client.post("/api/samples/capture", json=capture_body(client, ids, frames=client.get(
        "/api/demo-frames", params={"seed": 42}).json()["frames"])).json()
    assert again["id"] > s["id"]  # a deleted id is never handed to a new recording


def test_withdraw_blocks_capture_and_training_and_can_delete_samples(client, ids):
    from app.api.models import eligible_samples
    from app.db import engine
    from sqlmodel import Session

    w = new_signer(client, ids, "W-01")
    s = client.post("/api/samples/capture", json=capture_body(client, w, frames=client.get(
        "/api/demo-frames", params={"seed": 51}).json()["frames"])).json()
    client.post(f"/api/samples/{s['id']}/review", json={"reviewer_code": "R-01", "reviewer_role": "team_non_signer",
                                                        "decision": "approved"})
    with Session(engine) as db:
        assert s["id"] in [x.id for x in eligible_samples(db, ids["project_id"], "real")]

    r = client.post(f"/api/consents/{w['consent_id']}/withdraw", json={"delete_samples": False})
    assert r.status_code == 200 and r.json()["status"] == "withdrawn" and r.json()["deleted_samples"] == 0
    assert os.path.exists(s["feature_path"])  # kept, but no longer usable
    assert client.post("/api/samples/capture", json=capture_body(client, w)).status_code == 403
    with Session(engine) as db:
        assert s["id"] not in [x.id for x in eligible_samples(db, ids["project_id"], "real")]

    again = client.post(f"/api/consents/{w['consent_id']}/withdraw", json={"delete_samples": True})
    assert again.json()["deleted_samples"] == 1  # repeatable, and now erases
    assert not os.path.exists(s["feature_path"])
    assert client.post("/api/consents/999999/withdraw", json={"delete_samples": True}).status_code == 404
    assert client.post(f"/api/consents/{w['consent_id']}/withdraw", json={}).status_code == 422
