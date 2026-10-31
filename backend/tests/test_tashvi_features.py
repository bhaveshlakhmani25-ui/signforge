import io
import json
import os
from pathlib import Path
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ranker import (
    RankerConfig,
    DEFAULT_RANKER_CONFIG,
    score_sign_class,
    get_fake_queue,
    compute_active_learning_queue,
)
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
    # Agreed format requires {sign, priority, reason}
    assert "sign" in top and "gloss" in top and "priority" in top and "reason" in top
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


def test_ranker_config_and_deterministic_tie_breaking():
    # 1. Config customization for simulation (Ruben's harness)
    custom_config = RankerConfig(
        formula_version="simulation-v2",
        w_coverage=0.50,
        w_signer=0.30,
        w_uncertainty=0.20,
        default_target_samples=20,
        default_target_signers=5,
    )
    assert custom_config.weights["coverage"] == 0.50

    # 2. Pure score computation with custom config
    scored = score_sign_class(
        sign_class_id=1,
        gloss="ZEBRA",
        approved_count=10,
        distinct_signers=2,
        config=custom_config,
    )
    assert scored["target_samples"] == 20
    assert scored["coverage_gap"] == 0.5
    assert scored["sign"] == "ZEBRA"
    assert scored["formula_version"] == "simulation-v2"
    assert "priority" in scored and "reason" in scored

    # 3. Deterministic alphabetical tie-breaking
    # Two sign classes with identical statistics and uncertainty
    res_zebra = score_sign_class(
        sign_class_id=1, gloss="ZEBRA", approved_count=0, distinct_signers=0, config=custom_config
    )
    res_apple = score_sign_class(
        sign_class_id=2, gloss="APPLE", approved_count=0, distinct_signers=0, config=custom_config
    )
    assert res_zebra["priority"] == res_apple["priority"]

    # Sorting must deterministically place APPLE before ZEBRA
    queue = [res_zebra, res_apple]
    queue.sort(key=lambda x: (-x["priority"], x["sign"]))
    assert queue[0]["sign"] == "APPLE"
    assert queue[1]["sign"] == "ZEBRA"


def test_external_dataset_contribution_to_coverage():
    from sqlmodel import Session
    from app.db import engine
    from app.db.models import Project, SignClass, Signer, ConsentRecord, Sample

    with Session(engine) as session:
        proj = Project(name="ExternalRankerCoverageTest", target_language="ISL")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        pid = proj.id

        sc_cat = SignClass(project_id=pid, gloss="CAT", prompt_text="Sign: CAT")
        sc_dog = SignClass(project_id=pid, gloss="DOG", prompt_text="Sign: DOG")
        session.add(sc_cat)
        session.add(sc_dog)

        signer_real = Signer(project_id=pid, code="SIG-REAL-01")
        signer_ext_1 = Signer(project_id=pid, code="EXT-INC-01")
        signer_ext_2 = Signer(project_id=pid, code="EXT-INC-02")
        signer_mock = Signer(project_id=pid, code="EXT-MOCK-01")
        session.add(signer_real)
        session.add(signer_ext_1)
        session.add(signer_ext_2)
        session.add(signer_mock)
        session.commit()
        session.refresh(sc_cat)
        session.refresh(sc_dog)
        session.refresh(signer_real)
        session.refresh(signer_ext_1)
        session.refresh(signer_ext_2)
        session.refresh(signer_mock)

        c_real = ConsentRecord(signer_id=signer_real.id, consent_version="v1", purpose="real", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        c_ext_1 = ConsentRecord(signer_id=signer_ext_1.id, consent_version="v1", purpose="ext", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        c_ext_2 = ConsentRecord(signer_id=signer_ext_2.id, consent_version="v1", purpose="ext", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        c_mock = ConsentRecord(signer_id=signer_mock.id, consent_version="v1", purpose="mock", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        session.add(c_real)
        session.add(c_ext_1)
        session.add(c_ext_2)
        session.add(c_mock)
        session.commit()
        session.refresh(c_real)
        session.refresh(c_ext_1)
        session.refresh(c_ext_2)
        session.refresh(c_mock)

        # CAT has 2 genuine approved external samples from 2 distinct external signers
        s_ext_1 = Sample(
            project_id=pid, sign_class_id=sc_cat.id, signer_id=signer_ext_1.id, consent_id=c_ext_1.id,
            source="external_dataset", dataset_name="INCLUDE", feature_path="", feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s_ext_1_sha", review_status="approved", split="train",
        )
        s_ext_2 = Sample(
            project_id=pid, sign_class_id=sc_cat.id, signer_id=signer_ext_2.id, consent_id=c_ext_2.id,
            source="external_dataset", dataset_name="INCLUDE", feature_path="", feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s_ext_2_sha", review_status="approved", split="train",
        )

        # DOG has 1 mock external sample
        s_mock = Sample(
            project_id=pid, sign_class_id=sc_dog.id, signer_id=signer_mock.id, consent_id=c_mock.id,
            source="external_dataset", dataset_name="MOCK_INCLUDE", provenance_note="[MOCK] synthetic",
            feature_path="", feature_schema_version="mp-holistic-75-xyz-v1", extractor="test",
            fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s_mock_sha", review_status="approved", split="train",
        )
        session.add(s_ext_1)
        session.add(s_ext_2)
        session.add(s_mock)
        session.commit()

        # Compute active learning queue
        queue = compute_active_learning_queue(session, project_id=pid, target_samples=10, target_signers=3)
        q_map = {item["sign"]: item for item in queue}

        # 1. CAT: Genuine external samples contribute to count and distinct signers!
        assert q_map["CAT"]["approved_sample_count"] == 2
        assert q_map["CAT"]["distinct_signer_count"] == 2
        assert q_map["CAT"]["coverage_gap"] == 0.8  # 1 - 2/10
        assert q_map["CAT"]["priority"] < 1.0

        # 2. DOG: Mock sample is excluded by non_mock_sample_clause() by default!
        assert q_map["DOG"]["approved_sample_count"] == 0
        assert q_map["DOG"]["distinct_signer_count"] == 0
        assert q_map["DOG"]["coverage_gap"] == 1.0
        assert q_map["DOG"]["priority"] == 1.0

        # 3. Output format check: {sign, priority, reason} present on all items
        for item in queue:
            assert "sign" in item
            assert "priority" in item
            assert "reason" in item

        # Clean up
        session.delete(s_ext_1)
        session.delete(s_ext_2)
        session.delete(s_mock)
        session.delete(c_real)
        session.delete(c_ext_1)
        session.delete(c_ext_2)
        session.delete(c_mock)
        session.delete(signer_real)
        session.delete(signer_ext_1)
        session.delete(signer_ext_2)
        session.delete(signer_mock)
        session.delete(sc_cat)
        session.delete(sc_dog)
        session.delete(proj)
        session.commit()


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

    # Provenance note updated; the human review decision is NOT overwritten (consent status alone excludes the sample)
    updated_sample = client.get(f"/api/samples", params={"project_id": setup_data["project_id"]}).json()
    target = next((x for x in updated_sample if x["id"] == s["id"]), None)
    assert target is not None
    assert target["review_status"] == "approved"
    assert "[CONSENT WITHDRAWN]" in target["provenance_note"]


def test_import_external_dataset_manifest(setup_data):
    from sqlmodel import Session
    from app.db import engine
    from app.services.external_dataset import import_external_dataset_from_manifest
    from scripts.import_external import generate_mock_include_subset

    manifest_path = generate_mock_include_subset("data/external/test_include")
    with Session(engine) as session:
        res = import_external_dataset_from_manifest(manifest_path, setup_data["project_id"], session)
        assert res["dataset_name"] == "MOCK_INCLUDE"
        assert res["imported"] > 0


# =========================================================================
# STEP 3: Centralized Mock Detection, Isolation, and Safe Purge Tests
# =========================================================================

from app.services.mock_policy import (
    is_mock_sample,
    mock_sample_clause,
    non_mock_sample_clause,
    tag_legacy_mock_sample,
    backfill_legacy_mock_tags,
    LEGACY_MOCK_PROVENANCE_NOTE,
)
from app.db.models import Project, Sample, SignClass, Signer, ConsentRecord, ReviewEvent
from scripts.import_external import purge_mock_data


def test_mock_policy_python_sql_consistency_and_null_safety(setup_data):
    from sqlmodel import Session, select
    from app.db import engine

    pid = setup_data["project_id"]
    test_cases = [
        # (source, dataset_name, provenance_note, expected_mock, label)
        ("demo_fixture", "", "", True, "demo_fixture"),
        ("external_dataset", "MOCK_INCLUDE", "", True, "mock_include_dataset"),
        ("external_dataset", "mock_subset", "", True, "lowercase_mock_prefix"),
        ("external_dataset", "", "[MOCK] test note", True, "mock_tag_in_note"),
        ("external_dataset", "INCLUDE", LEGACY_MOCK_PROVENANCE_NOTE, True, "legacy_mock_include"),
        ("external_dataset", "INCLUDE", "Zenodo download by Akarshi", False, "genuine_include"),
        ("captured", "", "", False, "genuine_captured"),
        ("captured", None, None, False, "null_fields_captured"),
        ("external_dataset", None, None, False, "null_fields_external"),
    ]

    with Session(engine) as session:
        for src, ds, note, expected_mock, label in test_cases:
            s = Sample(
                project_id=pid,
                sign_class_id=setup_data["sign_a"],
                signer_id=setup_data["signer_1"],
                consent_id=setup_data["consent_1"],
                source=src,
                dataset_name=ds or "",
                provenance_note=note or "",
                feature_schema_version="mp-holistic-75-xyz-v1",
                extractor="test",
                fps=30.0,
                width=1280,
                height=720,
                frame_count=30,
                quality_score=1.0,
                qc_passed=True,
                quality_flags=[],
                qc_metrics={},
                feature_sha256=f"hash_{label}_{expected_mock}",
            )
            session.add(s)
            session.commit()
            session.refresh(s)

            # 1. Python in-memory evaluation
            py_res = is_mock_sample(s)
            assert py_res == expected_mock, f"Python is_mock_sample failed for {label}: got {py_res}, expected {expected_mock}"

            # 2. SQL clause evaluation
            sql_mock = session.exec(select(Sample).where(Sample.id == s.id, mock_sample_clause())).first()
            assert (sql_mock is not None) == expected_mock, f"SQL mock_sample_clause mismatch for {label}"

            sql_non_mock = session.exec(select(Sample).where(Sample.id == s.id, non_mock_sample_clause())).first()
            assert (sql_non_mock is not None) == (not expected_mock), f"SQL non_mock_sample_clause mismatch for {label}"

            # Clean up test sample
            session.delete(s)
            session.commit()


def test_legacy_mock_identification_and_explicit_backfill(setup_data):
    from sqlmodel import Session
    from app.db import engine

    pid = setup_data["project_id"]
    with Session(engine) as session:
        s = Sample(
            project_id=pid,
            sign_class_id=setup_data["sign_a"],
            signer_id=setup_data["signer_1"],
            consent_id=setup_data["consent_1"],
            source="external_dataset",
            dataset_name="INCLUDE",
            provenance_note=LEGACY_MOCK_PROVENANCE_NOTE,
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="legacy_mock_test_sha",
        )
        session.add(s)
        session.commit()
        session.refresh(s)

        # Before backfill: identified as mock by legacy note
        assert is_mock_sample(s) is True

        # Test single tagging
        tagged = tag_legacy_mock_sample(s)
        assert tagged is True
        assert s.dataset_name == "MOCK_INCLUDE"
        assert s.provenance_note.startswith("[MOCK]")
        assert is_mock_sample(s) is True

        session.delete(s)
        session.commit()


def test_genuine_external_dataset_protection(setup_data):
    from sqlmodel import Session, select
    from app.db import engine
    from app.services.external_dataset import import_external_dataset_from_manifest

    pid = setup_data["project_id"]
    out_dir = Path("data/external/test_genuine_include")
    out_dir.mkdir(parents=True, exist_ok=True)
    feat_dir = out_dir / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)

    dummy_feat = feat_dir / "sample_gen_001.npz"
    import numpy as np
    pts = np.zeros((30, 75, 3), dtype=np.float32)
    pts[:, 11, :2] = [0.4, 0.4]  # left shoulder
    pts[:, 12, :2] = [0.6, 0.4]  # right shoulder
    pts[:, 33:54, :2] = 0.5      # left hand present
    np.savez_compressed(dummy_feat, points=pts, present=np.ones((30, 3), bool), t=np.arange(30, dtype=np.float32)/30.0)

    manifest = {
        "dataset_name": "INCLUDE",
        "dataset_version": "1.0",
        "license": "CC-BY-4.0",
        "citation": "Real INCLUDE citation",
        "provenance_note": "Genuine ISL clips from Zenodo download",
        "feature_schema_version": "mp-holistic-75-xyz-v1",
        "extractor": "mediapipe-holistic-python",
        "samples": [{
            "gloss": "ALPHA",
            "external_sample_id": "real_inc_001",
            "external_signer_id": "signer_zenodo_1",
            "feature_file": "features/sample_gen_001.npz",
            "frame_count": 30,
            "fps": 30.0,
            "width": 1280,
            "height": 720,
            "external_split": "train",
        }],
    }
    mfile = out_dir / "manifest.json"
    with open(mfile, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    with Session(engine) as session:
        res = import_external_dataset_from_manifest(str(mfile), pid, session)
        assert res["dataset_name"] == "INCLUDE"

        imported = session.exec(
            select(Sample).where(Sample.external_sample_id == "real_inc_001")
        ).first()
        assert imported is not None
        # MUST NOT be classified as mock
        assert is_mock_sample(imported) is False

        # Signer code should have EXT-INC prefix, NOT EXT-MOCK
        signer = session.get(Signer, imported.signer_id)
        assert signer.code.startswith("EXT-INC")

        # Clean up
        session.delete(imported)
        session.commit()


def test_mock_excluded_from_all_four_operations(client, setup_data):
    from sqlmodel import Session
    from app.db import engine
    from app.services.ranker import compute_active_learning_queue
    from app.api.models import eligible_samples
    from app.services.export import create_corpus_export_zip

    pid = setup_data["project_id"]

    with Session(engine) as session:
        # Create a new project to test isolation
        proj = Project(name="IsolationTest", target_language="ISL")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        iso_pid = proj.id

        sc = SignClass(project_id=iso_pid, gloss="ISOTEST", prompt_text="Sign: ISOTEST")
        signer_real = Signer(project_id=iso_pid, code="SIG-REAL")
        signer_mock = Signer(project_id=iso_pid, code="EXT-MOCK-01")
        session.add(sc)
        session.add(signer_real)
        session.add(signer_mock)
        session.commit()
        session.refresh(sc)
        session.refresh(signer_real)
        session.refresh(signer_mock)

        con_real = ConsentRecord(signer_id=signer_real.id, consent_version="v1", purpose="real", allowed_uses=["model_training", "corpus_building"], retention="landmarks_only", status="active")
        con_mock = ConsentRecord(signer_id=signer_mock.id, consent_version="v1", purpose="mock", allowed_uses=["model_training", "corpus_building"], retention="landmarks_only", status="active")
        session.add(con_real)
        session.add(con_mock)
        session.commit()
        session.refresh(con_real)
        session.refresh(con_mock)

        # 1. Genuine sample with valid feature file
        f_real = Path("data/processed/iso_real_file.npz")
        f_real.parent.mkdir(parents=True, exist_ok=True)
        f_real.write_bytes(b"PK_iso_real")

        s_real = Sample(
            project_id=iso_pid,
            sign_class_id=sc.id,
            signer_id=signer_real.id,
            consent_id=con_real.id,
            source="captured",
            feature_path=str(f_real.resolve()),
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="iso_real_sha",
            review_status="approved",
            split="train",
        )
        # 2. Mock sample
        s_mock = Sample(
            project_id=iso_pid,
            sign_class_id=sc.id,
            signer_id=signer_mock.id,
            consent_id=con_mock.id,
            source="external_dataset",
            dataset_name="MOCK_INCLUDE",
            provenance_note="[MOCK] synthetic test",
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="iso_mock_sha",
            review_status="approved",
            split="train",
        )
        session.add(s_real)
        session.add(s_mock)
        session.commit()

        # Operation 1: Ranker queue
        q_default = compute_active_learning_queue(session, iso_pid, include_demo=False)
        assert len(q_default) == 1
        # Mock sample is excluded -> approved count should be 1 (only s_real)
        assert q_default[0]["approved_sample_count"] == 1
        assert q_default[0]["distinct_signer_count"] == 1

        # Operation 2: Model training eligible_samples (real pool)
        real_pool = eligible_samples(session, iso_pid, pool="real")
        assert len(real_pool) == 1
        assert real_pool[0].id == s_real.id

        # Operation 3: Corpus export (include_demo=False)
        zip_buf, _ = create_corpus_export_zip(session, iso_pid, include_demo=False)
        with zipfile.ZipFile(zip_buf) as zf:
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert len(manifest_data["samples"]) == 1
        assert manifest_data["samples"][0]["signer_code"] == "SIG-REAL"

        # Operation 4: Sample listing API
        r = client.get(f"/api/samples", params={"project_id": iso_pid, "include_demo": False})
        assert r.status_code == 200
        samples_list = r.json()
        assert len(samples_list) == 1
        assert samples_list[0]["id"] == s_real.id

        # Clean up isolation project
        session.delete(s_real)
        session.delete(s_mock)
        session.delete(con_real)
        session.delete(con_mock)
        session.delete(signer_real)
        session.delete(signer_mock)
        session.delete(sc)
        session.delete(proj)
        session.commit()

        if f_real.exists():
            f_real.unlink()


def test_purge_mock_safe_execution_and_cancellation():
    from sqlmodel import Session
    from app.db import engine

    with Session(engine) as session:
        # Create temp project
        proj = Project(name="PurgeTestProject", target_language="ISL")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        pid = proj.id

        sc = SignClass(project_id=pid, gloss="PURGETEST", prompt_text="Sign: PURGETEST")
        signer_real = Signer(project_id=pid, code="SIG-REAL-PURGE")
        signer_mock = Signer(project_id=pid, code="EXT-MOCK-PURGE")
        session.add(sc)
        session.add(signer_real)
        session.add(signer_mock)
        session.commit()
        session.refresh(sc)
        session.refresh(signer_real)
        session.refresh(signer_mock)

        con_real = ConsentRecord(signer_id=signer_real.id, consent_version="v1", purpose="real", allowed_uses=["model_training"], retention="landmarks_only", status="active")
        con_mock = ConsentRecord(signer_id=signer_mock.id, consent_version="v1", purpose="mock", allowed_uses=["model_training"], retention="landmarks_only", status="active")
        session.add(con_real)
        session.add(con_mock)
        session.commit()
        session.refresh(con_real)
        session.refresh(con_mock)

        # Temporary feature files
        test_dir = Path("data/processed/purge_test")
        test_dir.mkdir(parents=True, exist_ok=True)
        real_file = test_dir / "real_file.npz"
        mock_file = test_dir / "mock_file.npz"
        real_file.write_text("real content")
        mock_file.write_text("mock content")

        s_real = Sample(
            project_id=pid,
            sign_class_id=sc.id,
            signer_id=signer_real.id,
            consent_id=con_real.id,
            source="captured",
            feature_path=str(real_file.resolve()),
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="purge_real_sha",
            review_status="approved",
            split="train",
        )
        s_mock = Sample(
            project_id=pid,
            sign_class_id=sc.id,
            signer_id=signer_mock.id,
            consent_id=con_mock.id,
            source="external_dataset",
            dataset_name="MOCK_INCLUDE",
            provenance_note="[MOCK] test purge",
            feature_path=str(mock_file.resolve()),
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="purge_mock_sha",
            review_status="approved",
            split="train",
        )
        session.add(s_real)
        session.add(s_mock)
        session.commit()
        session.refresh(s_real)
        session.refresh(s_mock)

        # 1. Test Dry Run: 0 deleted
        dry_res = purge_mock_data(session, pid, dry_run=True)
        assert dry_res["dry_run"] is True
        assert dry_res["purged_samples"] == 1
        assert session.get(Sample, s_mock.id) is not None
        assert mock_file.exists()
        assert real_file.exists()

        # 2. Test Cancellation (auto_confirm=False, user abort): 0 deleted
        cancel_res = purge_mock_data(session, pid, dry_run=False, auto_confirm=False)
        # auto_confirm=False with no mock input cancels
        assert cancel_res["cancelled"] is True
        assert session.get(Sample, s_mock.id) is not None
        assert mock_file.exists()

        # 3. Test Confirmed Execution:
        exec_res = purge_mock_data(session, pid, dry_run=False, auto_confirm=True)
        assert exec_res["purged_samples"] == 1
        assert exec_res["deleted_files"] == 1

        # Mock sample is gone from DB and disk
        assert session.get(Sample, s_mock.id) is None
        assert not mock_file.exists()

        # Genuine sample is 100% intact in DB and disk
        assert session.get(Sample, s_real.id) is not None
        assert real_file.exists()

        # Mock signer and consent should be deleted since not shared
        assert session.get(Signer, signer_mock.id) is None
        assert session.get(ConsentRecord, con_mock.id) is None

        # Genuine signer and consent intact
        assert session.get(Signer, signer_real.id) is not None
        assert session.get(ConsentRecord, con_real.id) is not None

        # Clean up
        session.delete(s_real)
        session.delete(con_real)
        session.delete(signer_real)
        session.delete(sc)
        session.delete(proj)
        session.commit()

        if real_file.exists():
            real_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()


def test_purge_shared_signer_and_file_protection():
    from sqlmodel import Session
    from app.db import engine

    with Session(engine) as session:
        proj = Project(name="SharedProtectionTest", target_language="ISL")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        pid = proj.id

        sc = SignClass(project_id=pid, gloss="SHAREDTEST", prompt_text="Sign: SHAREDTEST")
        shared_signer = Signer(project_id=pid, code="SIG-SHARED")
        session.add(sc)
        session.add(shared_signer)
        session.commit()
        session.refresh(sc)
        session.refresh(shared_signer)

        shared_consent = ConsentRecord(signer_id=shared_signer.id, consent_version="v1", purpose="shared", allowed_uses=["model_training"], retention="landmarks_only", status="active")
        session.add(shared_consent)
        session.commit()
        session.refresh(shared_consent)

        test_dir = Path("data/processed/shared_test")
        test_dir.mkdir(parents=True, exist_ok=True)
        shared_file = test_dir / "shared_feature.npz"
        shared_file.write_text("shared content")

        # Genuine sample using shared_signer and shared_file
        s_real = Sample(
            project_id=pid,
            sign_class_id=sc.id,
            signer_id=shared_signer.id,
            consent_id=shared_consent.id,
            source="captured",
            feature_path=str(shared_file.resolve()),
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="shared_real_sha",
            review_status="approved",
            split="train",
        )
        # Mock sample also referencing shared_signer and shared_file
        s_mock = Sample(
            project_id=pid,
            sign_class_id=sc.id,
            signer_id=shared_signer.id,
            consent_id=shared_consent.id,
            source="external_dataset",
            dataset_name="MOCK_INCLUDE",
            provenance_note="[MOCK] shared test",
            feature_path=str(shared_file.resolve()),
            feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test",
            fps=30.0,
            width=1280,
            height=720,
            frame_count=30,
            quality_score=1.0,
            qc_passed=True,
            quality_flags=[],
            qc_metrics={},
            feature_sha256="shared_mock_sha",
            review_status="approved",
            split="train",
        )
        session.add(s_real)
        session.add(s_mock)
        session.commit()

        # Purge mock
        res = purge_mock_data(session, pid, auto_confirm=True)
        assert res["purged_samples"] == 1
        # The shared file MUST NOT be deleted!
        assert res["deleted_files"] == 0
        assert shared_file.exists()

        # Shared signer and consent MUST NOT be deleted!
        assert session.get(Signer, shared_signer.id) is not None
        assert session.get(ConsentRecord, shared_consent.id) is not None

        # Clean up
        session.delete(s_real)
        session.delete(shared_consent)
        session.delete(shared_signer)
        session.delete(sc)
        session.delete(proj)
        session.commit()

        if shared_file.exists():
            shared_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()


# =========================================================================
# STEP 4: Consent-Aware, Provenance-Preserving Dataset Export Tests
# =========================================================================

from app.services.export import export_corpus_to_folder, is_redistributable_license


def test_redistributable_license_policy():
    # Permitted open / research licenses
    assert is_redistributable_license("CC-BY-4.0") is True
    assert is_redistributable_license("CC-BY-SA-4.0") is True
    assert is_redistributable_license("CC0 1.0 Universal") is True
    assert is_redistributable_license("MIT") is True
    assert is_redistributable_license("Apache-2.0") is True
    assert is_redistributable_license("Public Domain") is True

    # Restrictive / unknown licenses
    assert is_redistributable_license(None) is False
    assert is_redistributable_license("") is False
    assert is_redistributable_license("Unknown") is False
    assert is_redistributable_license("Proprietary") is False
    assert is_redistributable_license("No-Redistribution") is False
    assert is_redistributable_license("CC-BY-ND-4.0") is False


def test_export_comprehensive_safety_and_manifest_parity(client):
    from sqlmodel import Session
    from app.db import engine
    from app.services.export import create_corpus_export_zip

    with Session(engine) as session:
        proj = Project(name="ComprehensiveExportProject", target_language="ISL")
        session.add(proj)
        session.commit()
        session.refresh(proj)
        pid = proj.id

        sc_alpha = SignClass(project_id=pid, gloss="ALPHA", prompt_text="Sign: ALPHA")
        sc_beta = SignClass(project_id=pid, gloss="BETA", prompt_text="Sign: BETA")
        session.add(sc_alpha)
        session.add(sc_beta)

        signer_1 = Signer(project_id=pid, code="SIG-EXP-01")
        signer_2 = Signer(project_id=pid, code="SIG-EXP-02")
        signer_ext = Signer(project_id=pid, code="EXT-INC-01")
        session.add(signer_1)
        session.add(signer_2)
        session.add(signer_ext)
        session.commit()
        session.refresh(sc_alpha)
        session.refresh(sc_beta)
        session.refresh(signer_1)
        session.refresh(signer_2)
        session.refresh(signer_ext)

        # Consents
        c_active = ConsentRecord(signer_id=signer_1.id, consent_version="v1", purpose="corpus", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        c_withdrawn = ConsentRecord(signer_id=signer_1.id, consent_version="v1", purpose="corpus", allowed_uses=["corpus_building"], retention="landmarks_only", status="withdrawn")
        c_unauth = ConsentRecord(signer_id=signer_1.id, consent_version="v1", purpose="model", allowed_uses=["model_training"], retention="landmarks_only", status="active")
        c_no_ret = ConsentRecord(signer_id=signer_2.id, consent_version="v1", purpose="corpus", allowed_uses=["corpus_building"], retention="none", status="active")
        c_ext = ConsentRecord(signer_id=signer_ext.id, consent_version="v1", purpose="external", allowed_uses=["corpus_building"], retention="landmarks_only", status="active")
        session.add(c_active)
        session.add(c_withdrawn)
        session.add(c_unauth)
        session.add(c_no_ret)
        session.add(c_ext)
        session.commit()
        session.refresh(c_active)
        session.refresh(c_withdrawn)
        session.refresh(c_unauth)
        session.refresh(c_no_ret)
        session.refresh(c_ext)

        # Temporary files directory
        test_dir = Path("data/processed/export_test")
        test_dir.mkdir(parents=True, exist_ok=True)
        f_valid_1 = test_dir / "valid_1.npz"
        f_valid_ext = test_dir / "valid_ext.npz"
        f_valid_ext_unlic = test_dir / "valid_ext_unlic.npz"
        f_mock = test_dir / "mock_file.npz"
        f_empty = test_dir / "empty_landmark.npz"
        f_valid_1.write_bytes(b"PK_landmark_data_valid_1")
        f_valid_ext.write_bytes(b"PK_landmark_data_ext")
        f_valid_ext_unlic.write_bytes(b"PK_landmark_data_unlic")
        f_mock.write_bytes(b"PK_landmark_data_mock")
        f_empty.write_bytes(b"")  # 0-byte unreadable landmark file

        # 1. Eligible genuine captured
        s1 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s1_sha", review_status="approved", split="train",
        )
        # 2. Excluded: Withdrawn consent
        s2 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_withdrawn.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s2_sha", review_status="approved", split="train",
        )
        # 3. Excluded: Unauthorized purpose
        s3 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_unauth.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s3_sha", review_status="approved", split="train",
        )
        # 4. Excluded: Retention prohibited
        s4 = Sample(
            project_id=pid, sign_class_id=sc_beta.id, signer_id=signer_2.id, consent_id=c_no_ret.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s4_sha", review_status="approved", split="train",
        )
        # 5. Excluded: Pending review
        s5 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s5_sha", review_status="pending_review", split="train",
        )
        # 6. Excluded: Rejected review
        s6 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="captured", feature_path=str(f_valid_1.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s6_sha", review_status="rejected", split="train",
        )
        # 7. Excluded: Mock data
        s7 = Sample(
            project_id=pid, sign_class_id=sc_beta.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="external_dataset", dataset_name="MOCK_INCLUDE", provenance_note="[MOCK] test",
            feature_path=str(f_mock.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s7_sha", review_status="approved", split="train",
        )
        # 8. External dataset: Licensed (CC-BY-4.0)
        s8 = Sample(
            project_id=pid, sign_class_id=sc_beta.id, signer_id=signer_ext.id, consent_id=c_ext.id,
            source="external_dataset", dataset_name="AI4Bharat_ISL", dataset_license="CC-BY-4.0", citation="Paper 2020",
            feature_path=str(f_valid_ext.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s8_sha", review_status="approved", split="train",
        )
        # 9. External dataset: Unlicensed / Unknown
        s9 = Sample(
            project_id=pid, sign_class_id=sc_beta.id, signer_id=signer_ext.id, consent_id=c_ext.id,
            source="external_dataset", dataset_name="UnlicensedISL", dataset_license="Unknown",
            feature_path=str(f_valid_ext_unlic.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s9_sha", review_status="approved", split="train",
        )
        # 10. Excluded: Missing feature file on disk
        s10 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="captured", feature_path=str(test_dir / "non_existent_file.npz"), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s10_sha", review_status="approved", split="train",
        )
        # 11. Excluded: Unreadable / 0-byte feature file on disk
        s11 = Sample(
            project_id=pid, sign_class_id=sc_alpha.id, signer_id=signer_1.id, consent_id=c_active.id,
            source="captured", feature_path=str(f_empty.resolve()), feature_schema_version="mp-holistic-75-xyz-v1",
            extractor="test", fps=30.0, width=1280, height=720, frame_count=30, quality_score=1.0, qc_passed=True,
            quality_flags=[], qc_metrics={}, feature_sha256="s11_sha", review_status="approved", split="train",
        )

        all_test_samples = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11]
        for s in all_test_samples:
            session.add(s)
        session.commit()

        # -------------------------------------------------------------
        # Case A: Default Export (include_external=False, include_demo=False)
        # -------------------------------------------------------------
        zip_buf, filename = create_corpus_export_zip(session, pid, include_demo=False, include_external=False)
        with zipfile.ZipFile(zip_buf) as zf:
            names = zf.namelist()
            assert "manifest.csv" in names
            assert "dataset_summary.json" in names
            assert "manifest.json" in names

            # Parse manifest.csv
            csv_lines = zf.read("manifest.csv").decode("utf-8").strip().splitlines()
            csv_header = csv_lines[0].split(",")
            csv_data = [line.split(",") for line in csv_lines[1:]]

            # Parity: Exactly 1 sample included (s1)
            assert len(csv_data) == 1
            landmark_files = [n for n in names if n.startswith("landmarks/") and n.endswith(".npz")]
            assert len(landmark_files) == 1
            assert len(csv_data) == len(landmark_files)

            # Check CSV columns
            row = csv_data[0]
            assert row[0] == str(s1.id)
            assert row[1] == "ALPHA"
            assert row[2] == "SIG-EXP-01"
            assert row[3] == "own"
            assert row[9] == "approved"

            # Parse dataset_summary.json
            summary = json.loads(zf.read("dataset_summary.json").decode("utf-8"))
            assert summary["total_exported_samples"] == 1
            assert summary["counts_by_source"]["own"] == 1
            assert "external" not in summary["counts_by_source"]
            # Exclusions breakdown: exactly reflects actual database records
            excl = summary["excluded_samples_breakdown"]
            assert excl["withdrawn_or_ineligible_consent"] == 1
            assert excl["consent_purpose_unauthorized"] == 1
            assert excl["retention_prohibited"] == 1
            assert excl["pending_or_rejected_review"] == 2
            assert excl["mock_or_demo_data"] == 1
            assert excl["external_not_requested"] == 2
            assert excl["missing_landmark_file"] == 2  # s10 (missing) + s11 (0-byte)
            assert "Untracked" in excl["permanently_deleted_samples"]

            # Privacy checks
            assert summary["governance"]["raw_video_included"] is False
            assert summary["governance"]["personal_details_included"] is False
            assert not any(n.endswith((".mp4", ".webm", ".avi", ".mov")) for n in names)

        # -------------------------------------------------------------
        # Case B: Opt-In External Export (include_external=True)
        # -------------------------------------------------------------
        zip_buf_ext, _ = create_corpus_export_zip(session, pid, include_demo=False, include_external=True)
        with zipfile.ZipFile(zip_buf_ext) as zf_ext:
            csv_lines_ext = zf_ext.read("manifest.csv").decode("utf-8").strip().splitlines()
            csv_data_ext = [line.split(",") for line in csv_lines_ext[1:]]

            # s1 (own) + s8 (licensed external) = 2 samples!
            # s9 (unlicensed external) remains excluded!
            assert len(csv_data_ext) == 2
            landmark_files_ext = [n for n in zf_ext.namelist() if n.startswith("landmarks/") and n.endswith(".npz")]
            assert len(landmark_files_ext) == 2
            assert len(csv_data_ext) == len(landmark_files_ext)

            summary_ext = json.loads(zf_ext.read("dataset_summary.json").decode("utf-8"))
            assert summary_ext["total_exported_samples"] == 2
            assert summary_ext["counts_by_source"]["own"] == 1
            assert summary_ext["counts_by_source"]["external"] == 1
            assert summary_ext["excluded_samples_breakdown"]["unlicensed_or_restrictive_external"] == 1

            # Provenance and attribution preserved from stored records
            assert len(summary_ext["external_datasets"]) == 1
            ext_meta = summary_ext["external_datasets"][0]
            assert ext_meta["dataset_name"] == "AI4Bharat_ISL"
            assert ext_meta["license"] == "CC-BY-4.0"
            assert ext_meta["citation"] == "Paper 2020"
            assert ext_meta["sample_count"] == 1

            # CSV attribution check for row 2 (external)
            ext_csv_row = [r for r in csv_data_ext if r[3] == "external"][0]
            assert ext_csv_row[4] == "AI4Bharat_ISL"
            assert ext_csv_row[7] == "CC-BY-4.0"

        # -------------------------------------------------------------
        # Case C: Purpose-Specific Consent Restriction
        # -------------------------------------------------------------
        # Requesting export for "research_publication":
        # s1 only authorized "corpus_building", so it must be excluded!
        zip_buf_research, _ = create_corpus_export_zip(
            session, pid, include_demo=False, include_external=False, export_purpose="research_publication"
        )
        with zipfile.ZipFile(zip_buf_research) as zf_res:
            csv_lines_res = zf_res.read("manifest.csv").decode("utf-8").strip().splitlines()
            # Only header line; s1 excluded due to purpose mismatch
            assert len(csv_lines_res) == 1
            summary_res = json.loads(zf_res.read("dataset_summary.json").decode("utf-8"))
            assert summary_res["total_exported_samples"] == 0
            assert summary_res["excluded_samples_breakdown"]["consent_purpose_unauthorized"] >= 2

        # -------------------------------------------------------------
        # Case D: Folder Export Function
        # -------------------------------------------------------------
        folder_export_dir = test_dir / "folder_export_out"
        folder_res = export_corpus_to_folder(session, pid, str(folder_export_dir), include_external=True)
        assert folder_res["exported_samples"] == 2
        assert (folder_export_dir / "manifest.csv").exists()
        assert (folder_export_dir / "dataset_summary.json").exists()
        assert len(list((folder_export_dir / "landmarks").glob("*.npz"))) == 2

        # -------------------------------------------------------------
        # Clean Up Isolation Test Records
        # -------------------------------------------------------------
        for s in all_test_samples:
            session.delete(s)
        session.delete(c_active)
        session.delete(c_withdrawn)
        session.delete(c_unauth)
        session.delete(c_no_ret)
        session.delete(c_ext)
        session.delete(signer_1)
        session.delete(signer_2)
        session.delete(signer_ext)
        session.delete(sc_alpha)
        session.delete(sc_beta)
        session.delete(proj)
        session.commit()

        # Clean up files
        for f in (f_valid_1, f_valid_ext, f_valid_ext_unlic, f_mock, f_empty):
            if f.exists():
                f.unlink()
        import shutil
        if folder_export_dir.exists():
            shutil.rmtree(folder_export_dir)
        if test_dir.exists():
            shutil.rmtree(test_dir)


def test_export_endpoint_backward_compatibility(client, setup_data):
    pid = setup_data["project_id"]
    # 1. Default call (no include_external parameter)
    r1 = client.get(f"/api/export/corpus", params={"project_id": pid})
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "application/zip"
    assert "attachment; filename=signforge_corpus_" in r1.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(r1.content)) as zf:
        names = zf.namelist()
        assert "manifest.csv" in names
        assert "dataset_summary.json" in names
        assert "manifest.json" in names

    # 2. Call with explicit include_external=False
    r2 = client.get(f"/api/export/corpus", params={"project_id": pid, "include_external": False})
    assert r2.status_code == 200

    # 3. Call with include_external=True
    r3 = client.get(f"/api/export/corpus", params={"project_id": pid, "include_external": True})
    assert r3.status_code == 200
