"""
CLI tool to import external datasets (e.g. INCLUDE) into SIGNFORGE.

Usage:
  python scripts/import_external.py --manifest data/external/include/manifest.json [--project-id 1]
  python scripts/import_external.py --generate-mock-subset   # Generates test manifest + landmarks for 10 ISL signs
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from sqlmodel import Session, select, func

from app.db import engine, init_db
from app.db.models import ConsentRecord, ReviewEvent, Sample, Signer
from app.services.demo_fixture import demo_frames
from app.services.external_dataset import import_external_dataset_from_manifest
from app.services.mock_policy import is_mock_sample, mock_sample_clause
from app.services.preprocessing import frames_to_arrays


def generate_mock_include_subset(output_dir: str = "data/external/include"):
    """
    Generates a mock 10-sign INCLUDE subset adhering to the agreed manifest contract.
    Explicitly marked with MOCK_INCLUDE and is_mock=True.
    """
    out = Path(output_dir)
    feat_dir = out / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)

    glosses = ["HELLO", "THANK-YOU", "HELP", "EMERGENCY", "DOCTOR", "WATER", "FOOD", "PAIN", "YES", "NO"]
    samples_manifest = []

    for idx, gloss in enumerate(glosses):
        for rep in range(3):
            signer_id = f"mock_signer_{rep + 1}"
            sample_id = f"mock_include_{gloss.lower()}_{rep + 1:03d}"
            feat_filename = f"features/{sample_id}.npz"
            feat_path = out / feat_filename

            frames = demo_frames(idx, seed=rep * 10 + idx)
            points, present, t = frames_to_arrays(frames)

            np.savez_compressed(feat_path, points=points, present=present, t=t)

            samples_manifest.append({
                "gloss": gloss,
                "external_sample_id": sample_id,
                "external_signer_id": signer_id,
                "feature_file": feat_filename,
                "frame_count": len(t),
                "fps": 30.0,
                "width": 1280,
                "height": 720,
                "external_split": "test" if rep == 2 else "train",
            })

    manifest = {
        "dataset_name": "MOCK_INCLUDE",
        "dataset_version": "1.0",
        "is_mock": True,
        "license": "CC-BY-4.0",
        "citation": "Sridhar et al., INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition, ACM MM 2020",
        "provenance_note": "[MOCK] Synthetic INCLUDE subset (10 signs, 3 signers) for pipeline testing",
        "feature_schema_version": "mp-holistic-75-xyz-v1",
        "extractor": "mediapipe-holistic-python",
        "extractor_model_sha": "e2dab611c3f8",
        "samples": samples_manifest,
    }

    manifest_file = out / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated test mock INCLUDE subset with {len(samples_manifest)} samples in {out}")
    print(f"Manifest written to: {manifest_file}")
    return str(manifest_file)


def purge_mock_data(
    session: Session,
    project_id: int,
    dry_run: bool = False,
    auto_confirm: bool = False,
) -> dict:
    """
    Safely purges positively identified mock/demo data for a project:
    - Previews affected records and feature files.
    - Requires explicit confirmation unless auto_confirm=True.
    - Protects captured recordings and genuine external datasets.
    - Protects shared signer and consent records.
    - Deletes feature files only for confirmed mock records; never deletes directories.
    """
    mock_samples = session.exec(
        select(Sample).where(
            Sample.project_id == project_id,
            mock_sample_clause(),
        )
    ).all()

    if not mock_samples:
        print(f"No mock samples found in project {project_id}.")
        return {"purged_samples": 0, "deleted_files": 0, "dry_run": dry_run}

    # Strict safety assertions on every candidate
    for s in mock_samples:
        if s.source == "captured":
            raise RuntimeError(f"CRITICAL REFUSAL: Sample {s.id} has source='captured' and cannot be purged!")
        if not is_mock_sample(s):
            raise RuntimeError(f"CRITICAL REFUSAL: Sample {s.id} is not identified as mock data!")

    mock_sample_ids = {s.id for s in mock_samples}

    # Check for shared feature files with non-mock samples
    non_mock_feature_paths = set(
        session.exec(
            select(Sample.feature_path).where(
                Sample.id.not_in(mock_sample_ids),
                Sample.feature_path != "",
            )
        ).all()
    )

    files_to_delete = []
    for s in mock_samples:
        if s.feature_path and os.path.isfile(s.feature_path):
            if s.feature_path not in non_mock_feature_paths:
                files_to_delete.append(s.feature_path)

    files_to_delete = sorted(list(set(files_to_delete)))

    # Identify candidate signers and consents to clean up (only if NOT shared with non-mock samples)
    candidate_signer_ids = {s.signer_id for s in mock_samples if s.signer_id}
    candidate_consent_ids = {s.consent_id for s in mock_samples if s.consent_id}

    shared_signer_ids = set(
        session.exec(
            select(Sample.signer_id).where(
                Sample.signer_id.in_(candidate_signer_ids),
                Sample.id.not_in(mock_sample_ids),
            )
        ).all()
    )
    safe_signer_ids = candidate_signer_ids - shared_signer_ids

    shared_consent_ids = set(
        session.exec(
            select(Sample.consent_id).where(
                Sample.consent_id.in_(candidate_consent_ids),
                Sample.id.not_in(mock_sample_ids),
            )
        ).all()
    )
    safe_consent_ids = candidate_consent_ids - shared_consent_ids

    # Display Preview
    print("\n================== MOCK PURGE PREVIEW ==================")
    print(f"Project ID:              {project_id}")
    print(f"Mock Samples to Delete:  {len(mock_samples)}")
    print(f"Feature Files to Delete: {len(files_to_delete)}")
    print(f"Signers to Delete:       {len(safe_signer_ids)} (protected {len(shared_signer_ids)} shared)")
    print(f"Consents to Delete:      {len(safe_consent_ids)} (protected {len(shared_consent_ids)} shared)")
    print("--------------------------------------------------------")
    for s in mock_samples[:10]:
        print(f"  Sample ID {s.id:4d} | SignClass ID: {s.sign_class_id} | Dataset: {s.dataset_name} | Note: {s.provenance_note[:30]}")
    if len(mock_samples) > 10:
        print(f"  ... and {len(mock_samples) - 10} more samples")
    print("========================================================\n")

    if dry_run:
        print("[DRY-RUN] Purge preview complete. No records or files were deleted.")
        return {
            "purged_samples": len(mock_samples),
            "deleted_files": len(files_to_delete),
            "dry_run": True,
        }

    if not auto_confirm:
        try:
            confirm = input("Type 'yes' to permanently delete these mock samples and landmark files: ")
            if confirm.strip().lower() != "yes":
                print("Purge cancelled. No records or files were modified.")
                return {
                    "purged_samples": 0,
                    "deleted_files": 0,
                    "cancelled": True,
                }
        except (EOFError, OSError):
            print("Purge cancelled (non-interactive session without --yes).")
            return {
                "purged_samples": 0,
                "deleted_files": 0,
                "cancelled": True,
            }

    # Execute DB Deletions in Transaction
    for s in mock_samples:
        for rev in session.exec(select(ReviewEvent).where(ReviewEvent.sample_id == s.id)).all():
            session.delete(rev)
        session.delete(s)

    for sid in safe_signer_ids:
        signer = session.get(Signer, sid)
        if signer:
            session.delete(signer)

    for cid in safe_consent_ids:
        consent = session.get(ConsentRecord, cid)
        if consent:
            session.delete(consent)

    session.commit()

    # Safely delete confirmed individual feature files
    deleted_files_count = 0
    for fpath in files_to_delete:
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
                deleted_files_count += 1
        except OSError as e:
            print(f"Warning: could not delete file {fpath}: {e}")

    print(f"Successfully purged {len(mock_samples)} mock samples and {deleted_files_count} feature files.")
    return {
        "purged_samples": len(mock_samples),
        "deleted_files": deleted_files_count,
        "dry_run": False,
        "cancelled": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Import external datasets into SIGNFORGE")
    parser.add_argument("--manifest", type=str, default="data/external/include/manifest.json", help="Path to manifest.json")
    parser.add_argument("--project-id", type=int, default=1, help="Target SIGNFORGE project ID")
    parser.add_argument("--generate-mock-subset", action="store_true", help="Generate mock INCLUDE dataset for pipeline testing")
    parser.add_argument("--no-auto-approve", action="store_true", help="Leave samples in pending_review instead of approved")
    parser.add_argument("--purge-mock", action="store_true", help="Purge mock data from database and feature files")
    parser.add_argument("--dry-run", action="store_true", help="Preview purge actions without modifying database or files")
    parser.add_argument("--yes", "-y", action="store_true", help="Confirm deletion non-interactively")

    args = parser.parse_args()
    init_db()

    if args.purge_mock:
        with Session(engine) as session:
            purge_mock_data(
                session=session,
                project_id=args.project_id,
                dry_run=args.dry_run,
                auto_confirm=args.yes,
            )
        return

    manifest_path = args.manifest
    if args.generate_mock_subset:
        manifest_path = generate_mock_include_subset()

    if not Path(manifest_path).exists():
        print(f"Error: manifest file '{manifest_path}' does not exist.")
        print("Tip: run with '--generate-mock-subset' to create a test dataset.")
        sys.exit(1)

    print(f"Importing external dataset from {manifest_path} into project {args.project_id}...")
    with Session(engine) as session:
        result = import_external_dataset_from_manifest(
            manifest_path=manifest_path,
            project_id=args.project_id,
            session=session,
            auto_approve=not args.no_auto_approve,
        )

    print("\n--- Import Summary ---")
    print(f"Dataset:            {result['dataset_name']}")
    print(f"Imported Samples:   {result['imported']}")
    print(f"Skipped/Duplicates: {result['skipped']}")
    print(f"Total in Manifest:  {result['total_in_manifest']}")
    print("----------------------\n")


if __name__ == "__main__":
    main()
