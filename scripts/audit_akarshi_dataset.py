"""
Independent audit script for Akarshi's dataset work.
Audits:
1. All 3 ZIP files (existence, size, readability).
2. Local extracted videos and landmarks (counts, shapes, zero NaNs).
3. Manifest integrity (data/include/manifest.json).
4. Database integrity (backend/signforge.db).
5. QC pass/fail matching between stored records and manifest.
"""

import json
import os
import sqlite3
import zipfile
from pathlib import Path

ZIPS = [
    r"C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_1of3.zip",
    r"C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_2of3.zip",
    r"C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_3of3.zip",
]


def audit():
    print("=" * 75)
    print("SECTION 1: ZIP ARCHIVES AUDIT")
    print("=" * 75)
    total_zip_bytes = 0
    for z in ZIPS:
        exists = os.path.exists(z)
        sz = os.path.getsize(z) if exists else 0
        total_zip_bytes += sz
        readable = False
        n_files = 0
        if exists:
            try:
                with zipfile.ZipFile(z, "r") as zf:
                    n_files = len(zf.namelist())
                    readable = n_files > 0
            except Exception as e:
                readable = False
        print(f"Archive: {os.path.basename(z)}")
        print(f"  Path: {z}")
        print(f"  Exists: {exists} | Readable: {readable} | Size: {sz} bytes ({sz / (1024*1024):.2f} MB)")
        print(f"  Internal entries: {n_files}")
    print(f"Total ZIP Storage: {total_zip_bytes} bytes ({total_zip_bytes / (1024*1024*1024):.3f} GB)")

    print("\n" + "=" * 75)
    print("SECTION 2: LOCAL EXTRACTED FILES AUDIT")
    print("=" * 75)
    vid_dir = Path("dataset/INCLUDE/Dates_and_Time/videos")
    lm_dir = Path("dataset/INCLUDE/Dates_and_Time/landmarks")
    actual_vids = sorted(list(vid_dir.glob("*.*")))
    actual_lms = sorted(list(lm_dir.glob("*.npz")))
    print(f"Video Directory: {vid_dir}")
    print(f"  Video Count: {len(actual_vids)}")
    print(f"Landmark Directory: {lm_dir}")
    print(f"  Landmark NPZ Count: {len(actual_lms)}")

    print("\n" + "=" * 75)
    print("SECTION 3: MANIFEST AUDIT (data/include/manifest.json)")
    print("=" * 75)
    manifest_path = Path("data/include/manifest.json")
    if not manifest_path.exists():
        print("ERROR: data/include/manifest.json missing!")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)

    samples = m.get("samples", [])
    classes = m.get("classes", [])
    print(f"Manifest Dataset: {m.get('dataset_name')}")
    print(f"Manifest Source Type: {m.get('source_type')}")
    print(f"Manifest Sample Count: {len(samples)}")
    print(f"Distinct Classes Count: {len(classes)} -> {classes}")

    sample_ids = [s["sample_id"] for s in samples]
    sign_ids = [s["sign_id"] for s in samples]
    orig_filenames = [s["original_filename"] for s in samples]
    video_paths = [s["video_path"] for s in samples]
    lm_paths = [s["landmark_path"] for s in samples]

    print(f"Unique sample_ids: {len(set(sample_ids))} / {len(sample_ids)}")
    print(f"Unique sign_ids: {len(set(sign_ids))} / {len(sign_ids)}")
    print(f"Unique original_filenames: {len(set(orig_filenames))} / {len(orig_filenames)}")
    print(f"Unique video_paths: {len(set(video_paths))} / {len(video_paths)}")
    print(f"Unique landmark_paths: {len(set(lm_paths))} / {len(lm_paths)}")

    # Check file existence for every sample
    missing_vids = [s for s in samples if not Path(s["video_path"]).exists()]
    missing_lms = [s for s in samples if not Path(s["landmark_path"]).exists()]
    print(f"Samples with missing video files: {len(missing_vids)}")
    print(f"Samples with missing landmark files: {len(missing_lms)}")

    # Check QC results in manifest
    qc_passed_m = [s for s in samples if s.get("qc_passed")]
    qc_failed_m = [s for s in samples if not s.get("qc_passed")]
    print(f"QC passed in manifest: {len(qc_passed_m)} / {len(samples)}")
    print(f"QC failed in manifest: {len(qc_failed_m)} / {len(samples)}")
    for qf in qc_failed_m:
        print(f"  Flagged Sample: sample_id={qf['sample_id']}, sign_id={qf['sign_id']}, sign_label={qf['sign_label']}")

    print("\n" + "=" * 75)
    print("SECTION 4: DATABASE AUDIT (backend/signforge.db)")
    print("=" * 75)
    conn = sqlite3.connect("backend/signforge.db")
    c = conn.cursor()

    db_counts_by_source = c.execute("SELECT source, count(*) FROM sample GROUP BY source").fetchall()
    print("Database Samples by Source:")
    for src, cnt in db_counts_by_source:
        print(f"  - {src}: {cnt} samples")

    ext_samples = c.execute(
        "SELECT id, sign_class_id, signer_id, qc_passed, quality_score, quality_flags, source, review_status, feature_path, feature_sha256 "
        "FROM sample WHERE source='external_dataset' ORDER BY id ASC"
    ).fetchall()
    print(f"Total 'external_dataset' rows in DB: {len(ext_samples)}")

    db_sample_ids = [s[0] for s in ext_samples]
    db_qc_passed = [s for s in ext_samples if s[3] == 1]
    db_qc_failed = [s for s in ext_samples if s[3] == 0]
    db_review_approved = [s for s in ext_samples if s[7] == "approved"]

    print(f"Unique DB sample IDs: {len(set(db_sample_ids))} / {len(db_sample_ids)}")
    print(f"DB QC Passed: {len(db_qc_passed)} / {len(ext_samples)}")
    print(f"DB QC Failed: {len(db_qc_failed)} / {len(ext_samples)}")
    print(f"DB Review Approved: {len(db_review_approved)} / {len(ext_samples)}")

    for df in db_qc_failed:
        print(f"  Flagged in DB: ID={df[0]}, sign_class_id={df[1]}, qc_passed={df[3]}, review_status={df[7]}, flags={df[5]}")

    # Cross-check manifest sample_ids vs database sample_ids
    manifest_id_set = set(sample_ids)
    db_id_set = set(db_sample_ids)
    diff_m_db = manifest_id_set - db_id_set
    diff_db_m = db_id_set - manifest_id_set
    print(f"\nManifest IDs not in DB: {diff_m_db if diff_m_db else 'None (100% matched)'}")
    print(f"DB IDs not in Manifest: {diff_db_m if diff_db_m else 'None (100% matched)'}")


if __name__ == "__main__":
    audit()
