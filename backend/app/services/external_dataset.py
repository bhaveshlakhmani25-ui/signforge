"""
SIGNFORGE External Dataset Loader Service

Imports external datasets (such as INCLUDE) according to the H+0:45 agreed manifest format:
- Manifest specifies provenance, license, schema, and sample list
- Source is explicitly recorded as "external_dataset" (never mixed with real or demo)
- Pseudonymous signer IDs created (e.g. INC-01)
- Landmarks validated against mp-holistic-75-xyz-v1 contract
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sqlmodel import Session, select

from app.db.models import ConsentRecord, Project, Sample, SignClass, Signer
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from app.services.quality_checks import run_qc
from app.services.storage import save_features


def import_external_dataset_from_manifest(
    manifest_path: str,
    project_id: int,
    session: Session,
    auto_approve: bool = True,
) -> Dict[str, Any]:
    """
    Imports an external dataset from an Akarshi-formatted manifest.json.
    """
    p = Path(manifest_path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    base_dir = p.parent
    with open(p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    dataset_name = manifest.get("dataset_name", "Unknown_External")
    dataset_version = manifest.get("dataset_version", "1.0")
    license_str = manifest.get("license", "Unknown")
    citation = manifest.get("citation", "")
    provenance_note = manifest.get("provenance_note", f"Imported from {dataset_name}")
    schema_version = manifest.get("feature_schema_version", FEATURE_SCHEMA_VERSION)
    extractor = manifest.get("extractor", "mediapipe-holistic-python")
    extractor_model_sha = manifest.get("extractor_model_sha", "")

    samples_data: List[Dict[str, Any]] = manifest.get("samples", [])
    imported_count = 0
    skipped_count = 0

    # Ensure project exists
    project = session.get(Project, project_id)
    if not project:
        project = Project(id=project_id, name=f"ISL ({dataset_name})", target_language="Indian Sign Language", domain="external_benchmark")
        session.add(project)
        session.commit()
        session.refresh(project)

    for item in samples_data:
        gloss = item["gloss"].strip().upper()
        ext_sample_id = str(item.get("external_sample_id", ""))
        ext_signer_id = str(item.get("external_signer_id", "ext_unknown"))
        ext_split = str(item.get("external_split", "train"))
        feature_rel_path = item["feature_file"]

        feature_abs_path = base_dir / feature_rel_path
        if not feature_abs_path.exists():
            skipped_count += 1
            continue

        # Load numpy feature file
        with np.load(feature_abs_path) as npz:
            points = npz["points"].astype(np.float32)
            present = npz["present"].astype(bool) if "present" in npz else np.ones((len(points), 3), bool)
            t = npz["t"].astype(np.float32) if "t" in npz else np.arange(len(points), dtype=np.float32) / float(item.get("fps", 30.0))

        fps = float(item.get("fps", 30.0))
        width = int(item.get("width", 1280))
        height = int(item.get("height", 720))

        # 1. SignClass
        sc = session.exec(
            select(SignClass).where(SignClass.project_id == project_id, SignClass.gloss == gloss)
        ).first()
        if not sc:
            sc = SignClass(project_id=project_id, gloss=gloss, prompt_text=f"Sign: {gloss}")
            session.add(sc)
            session.commit()
            session.refresh(sc)

        # 2. Signer (Pseudonymous with dataset prefix)
        clean_code = f"EXT-{dataset_name[:3].upper()}-{ext_signer_id}"[:16]
        signer = session.exec(
            select(Signer).where(Signer.project_id == project_id, Signer.code == clean_code)
        ).first()
        if not signer:
            signer = Signer(project_id=project_id, code=clean_code)
            session.add(signer)
            session.commit()
            session.refresh(signer)

        # 3. ConsentRecord (Provenance of public license)
        consent = session.exec(
            select(ConsentRecord).where(ConsentRecord.signer_id == signer.id)
        ).first()
        if not consent:
            consent = ConsentRecord(
                signer_id=signer.id,
                consent_version=f"{dataset_name}-{dataset_version}",
                purpose=f"Public dataset import: {dataset_name} ({license_str})",
                allowed_uses=["corpus_building", "model_training", "research_publication"],
                retention="landmarks_only",
                status="active",
            )
            session.add(consent)
            session.commit()
            session.refresh(consent)

        # 4. Landmark QC and Duplicate Check
        qc = run_qc(points, present, t, width, height)
        sha = hashlib.sha256(points.tobytes() + t.tobytes()).hexdigest()
        existing = session.exec(
            select(Sample.id).where(Sample.project_id == project_id, Sample.feature_sha256 == sha)
        ).first()
        if existing:
            skipped_count += 1
            continue

        sample = Sample(
            project_id=project_id,
            sign_class_id=sc.id,
            signer_id=signer.id,
            consent_id=consent.id,
            source="external_dataset",
            feature_schema_version=schema_version,
            extractor=extractor,
            extractor_model_sha=extractor_model_sha,
            fps=fps,
            width=width,
            height=height,
            frame_count=len(t),
            quality_score=qc["completeness"],
            qc_passed=qc["passed"],
            quality_flags=qc["flags"],
            qc_metrics=qc["metrics"],
            feature_sha256=sha,
            review_status="approved" if auto_approve and qc["passed"] else "pending_review",
            split=ext_split,
            provenance_note=provenance_note,
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            dataset_license=license_str,
            citation=citation,
            external_sample_id=ext_sample_id,
            external_signer_id=ext_signer_id,
            external_split=ext_split,
        )
        session.add(sample)
        session.flush()

        sample.feature_path = save_features(project_id, sample.id, points, present, t)
        session.commit()
        imported_count += 1

    return {
        "dataset_name": dataset_name,
        "imported": imported_count,
        "skipped": skipped_count,
        "total_in_manifest": len(samples_data),
    }
