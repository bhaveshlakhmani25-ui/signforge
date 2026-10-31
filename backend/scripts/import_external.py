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
from sqlmodel import Session

from app.db import engine, init_db
from app.services.demo_fixture import demo_frames
from app.services.external_dataset import import_external_dataset_from_manifest
from app.services.preprocessing import frames_to_arrays


def generate_mock_include_subset(output_dir: str = "data/external/include"):
    """
    Generates a mock 10-sign INCLUDE subset adhering to the agreed manifest contract.
    Allows testing the entire pipeline while the 56GB zips are downloading.
    """
    out = Path(output_dir)
    feat_dir = out / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)

    glosses = ["HELLO", "THANK-YOU", "HELP", "EMERGENCY", "DOCTOR", "WATER", "FOOD", "PAIN", "YES", "NO"]
    samples_manifest = []

    for idx, gloss in enumerate(glosses):
        for rep in range(3):
            signer_id = f"signer_{rep + 1}"
            sample_id = f"include_{gloss.lower()}_{rep + 1:03d}"
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
        "dataset_name": "INCLUDE",
        "dataset_version": "1.0",
        "license": "CC-BY-4.0",
        "citation": "Sridhar et al., INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition, ACM MM 2020",
        "provenance_note": "INCLUDE subset (10 signs, 3 signers) - AI4Bharat / IIT Madras",
        "feature_schema_version": "mp-holistic-75-xyz-v1",
        "extractor": "mediapipe-holistic-python",
        "extractor_model_sha": "e2dab611c3f8",
        "samples": samples_manifest,
    }

    manifest_file = out / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated test INCLUDE subset with {len(samples_manifest)} samples in {out}")
    print(f"Manifest written to: {manifest_file}")
    return str(manifest_file)


def main():
    parser = argparse.ArgumentParser(description="Import external datasets into SIGNFORGE")
    parser.add_argument("--manifest", type=str, default="data/external/include/manifest.json", help="Path to manifest.json")
    parser.add_argument("--project-id", type=int, default=1, help="Target SIGNFORGE project ID")
    parser.add_argument("--generate-mock-subset", action="store_true", help="Generate mock INCLUDE dataset for pipeline testing")
    parser.add_argument("--no-auto-approve", action="store_true", help="Leave samples in pending_review instead of approved")

    args = parser.parse_args()
    init_db()

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
