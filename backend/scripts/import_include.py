"""
Official INCLUDE / External Dataset Loader for SIGNFORGE.

Author: Aakarshi Dwivedi (Data & QA)
Collaborator Hand-off: Tashvi (Backend & External Dataset Loader)
Schema: mp-holistic-75-xyz-v1
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from sqlmodel import Session, create_engine, select

# Adjust path so app imports work
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core import config as C
from app.db.models import ConsentRecord, Project, Sample, SignClass, Signer
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from app.services.quality_checks import run_qc
from app.services.storage import save_features


def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_include_dataset(
    manifest_path: Path,
    project_id: int = 1,
    source: str = "external_dataset",
    review_status: str = "approved",
    dry_run: bool = False,
) -> dict:
    manifest = load_manifest(manifest_path)
    base_dir = manifest_path.parent
    signs = manifest.get("signs", [])
    classes = manifest.get("classes", [])

    print("=" * 75)
    print(f"IMPORTING EXTERNAL DATASET: {manifest.get('dataset')} - {manifest.get('category')}")
    print(f"Manifest: {manifest_path}")
    print(f"Target Project ID: {project_id} | Dry Run: {dry_run}")
    print(f"Total Signs to Process: {len(signs)} across {len(classes)} classes")
    print("=" * 75)

    engine = create_engine(C.DATABASE_URL)
    stats = {
        "total_signs": len(signs),
        "classes_registered": 0,
        "classes_existing": 0,
        "signers_registered": 0,
        "signers_existing": 0,
        "samples_imported": 0,
        "samples_skipped_dup": 0,
        "qc_passed": 0,
        "qc_failed": 0,
        "details": [],
    }

    with Session(engine) as session:
        # 1. Verify Project
        project = session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID {project_id} does not exist in database!")
        print(f"[+] Target Project verified: '{project.name}' (ID: {project.id})")

        # 2. Register/Fetch Sign Classes
        class_map: dict[str, SignClass] = {}
        for gloss in sorted(list(set(s.get("label", s.get("gloss")) for s in signs))):
            existing_sc = session.exec(
                select(SignClass).where(SignClass.project_id == project_id, SignClass.gloss == gloss)
            ).first()
            if existing_sc:
                class_map[gloss] = existing_sc
                stats["classes_existing"] += 1
            else:
                new_sc = SignClass(
                    project_id=project_id,
                    gloss=gloss,
                    prompt_text=f"Sign for {gloss.lower()} (Dates and Time)",
                    dialect_note="INCLUDE / AI4Bharat ISL dataset",
                    active=True,
                )
                if not dry_run:
                    session.add(new_sc)
                    session.flush()
                    session.refresh(new_sc)
                    class_map[gloss] = new_sc
                else:
                    class_map[gloss] = SignClass(id=999, project_id=project_id, gloss=gloss)
                stats["classes_registered"] += 1

        print(f"[+] SignClasses: {stats['classes_registered']} newly registered, {stats['classes_existing']} already existed.")

        # 3. Register/Fetch Signers & Consents
        signer_map: dict[str, tuple[Signer, ConsentRecord]] = {}
        signer_codes = sorted(list(set(s.get("signer_id", "INCLUDE-S01") for s in signs)))
        for scode in signer_codes:
            existing_signer = session.exec(
                select(Signer).where(Signer.project_id == project_id, Signer.code == scode)
            ).first()
            if not existing_signer:
                new_signer = Signer(project_id=project_id, code=scode, handedness="right")
                if not dry_run:
                    session.add(new_signer)
                    session.flush()
                    session.refresh(new_signer)
                else:
                    new_signer = Signer(id=999, project_id=project_id, code=scode)
                stats["signers_registered"] += 1
                signer_obj = new_signer
            else:
                signer_obj = existing_signer
                stats["signers_existing"] += 1

            # Consent Record
            existing_consent = session.exec(
                select(ConsentRecord).where(ConsentRecord.signer_id == signer_obj.id, ConsentRecord.status == "active")
            ).first()
            if not existing_consent:
                new_consent = ConsentRecord(
                    signer_id=signer_obj.id,
                    consent_version="include-zenodo-v1",
                    purpose="INCLUDE ISL Dataset / Zenodo 4010759 / CC-BY-4.0",
                    allowed_uses=["corpus_building", "model_training", "public_display"],
                    retention="landmarks_only",
                    raw_video_retained=False,
                    status="active",
                )
                if not dry_run:
                    session.add(new_consent)
                    session.flush()
                    session.refresh(new_consent)
                else:
                    new_consent = ConsentRecord(id=999, signer_id=signer_obj.id, consent_version="include-zenodo-v1")
                consent_obj = new_consent
            else:
                consent_obj = existing_consent

            signer_map[scode] = (signer_obj, consent_obj)

        print(f"[+] Signers: {stats['signers_registered']} registered, {stats['signers_existing']} already existed.")

        # 4. Ingest Landmark Samples
        for idx, sign in enumerate(signs, 1):
            sign_id = sign.get("sign_id", f"S_{idx}")
            gloss = sign.get("label", sign.get("gloss"))
            signer_code = sign.get("signer_id", "INCLUDE-S01")
            lm_rel = sign.get("landmark_file")
            lm_full = base_dir / lm_rel

            if not lm_full.exists():
                print(f"[-] ERROR: File missing: {lm_full}")
                continue

            with np.load(lm_full) as data:
                points = data["points"]
                present = data["present"]
                t = data["t"]

            width = int(sign.get("width", 1920))
            height = int(sign.get("height", 1080))
            fps = float(sign.get("fps", 25.0))

            # Quality Check
            qc = run_qc(points, present, t, width, height)
            if qc["passed"]:
                stats["qc_passed"] += 1
            else:
                stats["qc_failed"] += 1

            # Deduplication SHA
            sha = hashlib.sha256(points.tobytes() + t.tobytes()).hexdigest()
            dup = session.exec(
                select(Sample.id).where(Sample.project_id == project_id, Sample.feature_sha256 == sha)
            ).first()

            if dup is not None:
                stats["samples_skipped_dup"] += 1
                stats["details"].append({
                    "sign_id": sign_id,
                    "gloss": gloss,
                    "status": "skipped_duplicate",
                    "existing_sample_id": dup,
                })
                continue

            sc = class_map[gloss]
            signer_record, consent_record = signer_map[signer_code]

            if not dry_run:
                sample = Sample(
                    project_id=project_id,
                    sign_class_id=sc.id,
                    signer_id=signer_record.id,
                    consent_id=consent_record.id,
                    source=source,
                    feature_schema_version=FEATURE_SCHEMA_VERSION,
                    extractor="mediapipe-holistic-python",
                    extractor_model_sha="official-holistic-v0.10.9",
                    fps=fps,
                    width=width,
                    height=height,
                    frame_count=len(t),
                    quality_score=qc["completeness"],
                    qc_passed=qc["passed"],
                    quality_flags=qc["flags"],
                    qc_metrics=qc["metrics"],
                    feature_sha256=sha,
                    review_status=review_status,
                    split="unassigned",
                    provenance_note=f"INCLUDE / Zenodo 4010759 / CC-BY-4.0 / {sign_id}",
                )
                session.add(sample)
                session.flush()

                # Save feature to project's canonical storage path
                feature_path = save_features(project_id, sample.id, points, present, t)
                sample.feature_path = feature_path
                session.add(sample)
                session.commit()
                assigned_id = sample.id
            else:
                assigned_id = 9000 + idx

            stats["samples_imported"] += 1
            stats["details"].append({
                "sign_id": sign_id,
                "gloss": gloss,
                "sample_id": assigned_id,
                "qc_passed": qc["passed"],
                "quality_score": qc["completeness"],
                "frames": len(t),
                "status": "imported",
            })

    print("\n--- IMPORT SUMMARY ---")
    print(f"Total Signs Evaluated: {stats['total_signs']}")
    print(f"New Samples Imported: {stats['samples_imported']}")
    print(f"Duplicate Samples Skipped: {stats['samples_skipped_dup']}")
    print(f"Automated QC Passed: {stats['qc_passed']} / {stats['total_signs']}")
    print(f"Automated QC Failed: {stats['qc_failed']} / {stats['total_signs']}")
    print("=" * 75)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest external sign dataset into SIGNFORGE.")
    parser.add_argument(
        "--manifest",
        type=str,
        default="dataset/INCLUDE/Dates_and_Time/manifest.json",
        help="Path to dataset manifest.json",
    )
    parser.add_argument("--project-id", type=int, default=1, help="Target project ID")
    parser.add_argument(
        "--source",
        type=str,
        default="external_dataset",
        choices=["external_dataset", "public_dataset"],
        help="Source label for samples",
    )
    parser.add_argument(
        "--review-status",
        type=str,
        default="approved",
        choices=["approved", "pending_review"],
        help="Initial human review status",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without writing to DB")

    args = parser.parse_args()
    manifest_path = Path(args.manifest)

    import_include_dataset(
        manifest_path=manifest_path,
        project_id=args.project_id,
        source=args.source,
        review_status=args.review_status,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
