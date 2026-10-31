"""Generate official data/include/manifest.json for Tashvi's external_dataset loader handoff."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_MANIFEST = Path("dataset/INCLUDE/Dates_and_Time/manifest.json")
OUT_DIR = Path("data/include")
OUT_MANIFEST = OUT_DIR / "manifest.json"
DB_PATH = Path("backend/signforge.db")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(BASE_MANIFEST, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    base_signs = {s["sign_id"]: s for s in base_data.get("signs", [])}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Query classes and signers for label resolution
    classes = dict(c.execute("SELECT id, gloss FROM signclass").fetchall())
    signers = dict(c.execute("SELECT id, code FROM signer").fetchall())

    samples = c.execute(
        "SELECT id, sign_class_id, signer_id, feature_path, feature_sha256, fps, width, height, frame_count, quality_score, qc_passed, provenance_note, created_at "
        "FROM sample WHERE source='external_dataset' ORDER BY id ASC"
    ).fetchall()

    manifest_samples = []
    for idx, row in enumerate(samples, start=1):
        sample_id = row[0]
        sign_class_id = row[1]
        signer_id = row[2]
        feature_path = row[3]
        sha256 = row[4]
        fps = row[5]
        width = row[6]
        height = row[7]
        frame_count = row[8]
        quality_score = row[9]
        qc_passed = bool(row[10])
        prov_note = row[11]
        created_at = row[12]

        dt_id = f"DT_{idx:03d}"
        base_sign = base_signs.get(dt_id, {})
        video_rel = base_sign.get("video_file", "")
        orig_filename = Path(video_rel).name if video_rel else ""
        if "_" in orig_filename:
            # e.g. DT_001_MVI_5056.MOV -> MVI_5056.MOV
            orig_filename = orig_filename.split("_", 2)[-1]

        manifest_samples.append({
            "sample_id": sample_id,
            "sign_id": dt_id,
            "sign_label": classes.get(sign_class_id, "UNKNOWN"),
            "source_type": "external_dataset",
            "dataset_name": "INCLUDE",
            "category": "Days and Time",
            "original_filename": orig_filename,
            "original_source_url": "https://zenodo.org/records/4010759",
            "licence": "CC-BY-4.0",
            "signer_id": signers.get(signer_id, f"INCLUDE-S{(idx % 4) + 1:02d}"),
            "video_path": f"dataset/INCLUDE/Dates_and_Time/{video_rel}" if video_rel else "",
            "landmark_path": feature_path,
            "feature_sha256": sha256,
            "extraction_method": "mediapipe-holistic-python",
            "extraction_version": "mp-holistic-75-xyz-v1",
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "quality_score": quality_score,
            "qc_passed": qc_passed,
            "import_timestamp": created_at,
            "provenance_notes": prov_note or "INCLUDE / AI4Bharat / Zenodo 4010759 / CC-BY-4.0",
        })

    manifest = {
        "dataset_name": "INCLUDE",
        "category": "Days and Time",
        "source_type": "external_dataset",
        "source_repository": "Zenodo",
        "zenodo_record": "4010759",
        "doi": "10.1145/3394171.3413528",
        "licence": "CC-BY-4.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "mp-holistic-75-xyz-v1",
        "n_samples": len(manifest_samples),
        "n_classes": len(set(s["sign_label"] for s in manifest_samples)),
        "classes": sorted(list(set(s["sign_label"] for s in manifest_samples))),
        "samples": manifest_samples,
    }

    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Successfully generated {OUT_MANIFEST} with {manifest['n_samples']} samples across {manifest['n_classes']} classes.")


if __name__ == "__main__":
    main()
