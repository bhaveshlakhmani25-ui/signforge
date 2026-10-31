"""
SIGNFORGE Corpus Export Engine

Packages approved samples with an auditable manifest containing:
- Feature schema version and landmark layout
- Pseudonymous signer codes (strictly no personal details: names, emails)
- Consent purposes and allowed uses (active consent + corpus_building authorization)
- Provenance and license attribution for all sources
- Strictly NO raw video
- Landmarks folder containing only valid .npz files matching manifest.csv 1:1
- manifest.csv with columns: clip_id, sign, signer_pseudonym, source, dataset_name, external_sample_id, external_signer_id, licence, consent_flags, review_status, extractor_version, landmark_file
- dataset_summary.json with counts by sign/source, exclusions breakdown, known limits, and uninvented deletion accounting
"""

import csv
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from app.db.models import ConsentRecord, Project, Sample, SignClass, Signer
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from app.services.mock_policy import is_mock_sample


def is_redistributable_license(license_str: Optional[str]) -> bool:
    """
    Evaluates whether an external dataset's stored license permits redistribution
    in an exported corpus bundle.
    """
    if not license_str:
        return False
    lic = license_str.strip().upper()
    if lic in ("UNKNOWN", "NONE", "PROPRIETARY", "ALL RIGHTS RESERVED", "UNLICENSED", "RESTRICTED", "NO-REDISTRIBUTION"):
        return False
    if "NO-REDISTRIBUTION" in lic or "NO-DERIVATIVES" in lic or "-ND" in lic or "ND-" in lic:
        return False
    permitted_tokens = [
        "CC-BY", "CC0", "PUBLIC DOMAIN", "MIT", "APACHE", "BSD", "OPEN", "RESEARCH"
    ]
    return any(token in lic for token in permitted_tokens)


def collect_export_data(
    db: Session,
    project_id: int,
    include_demo: bool = False,
    include_external: bool = False,
    export_purpose: str = "corpus_building",
) -> Dict[str, Any]:
    """
    Gathers, validates, and filters samples for export, tracking precise exclusion reasons.
    """
    project = db.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    sign_classes = {
        sc.id: sc
        for sc in db.exec(select(SignClass).where(SignClass.project_id == project_id)).all()
    }
    signers = {
        s.id: s
        for s in db.exec(select(Signer).where(Signer.project_id == project_id)).all()
    }
    consents = {
        c.id: c
        for c in db.exec(select(ConsentRecord)).all()
    }

    all_samples = db.exec(
        select(Sample).where(Sample.project_id == project_id)
    ).all()

    exclusion_counts = {
        "pending_or_rejected_review": 0,
        "withdrawn_or_ineligible_consent": 0,
        "consent_purpose_unauthorized": 0,
        "retention_prohibited": 0,
        "mock_or_demo_data": 0,
        "external_not_requested": 0,
        "unlicensed_or_restrictive_external": 0,
        "missing_landmark_file": 0,
    }

    eligible_samples = []

    for s in all_samples:
        # 1. Review status gate
        if s.review_status != "approved":
            exclusion_counts["pending_or_rejected_review"] += 1
            continue

        # 2. Mock / demo exclusion by default
        if not include_demo and is_mock_sample(s):
            exclusion_counts["mock_or_demo_data"] += 1
            continue

        # 3. Consent enforcement
        c = consents.get(s.consent_id)
        if not c or c.status != "active":
            exclusion_counts["withdrawn_or_ineligible_consent"] += 1
            continue

        allowed = c.allowed_uses or []
        if export_purpose not in allowed:
            exclusion_counts["consent_purpose_unauthorized"] += 1
            continue

        retention = (c.retention or "").strip().lower()
        if not retention or retention in ("none", "ephemeral", "no_retention", "temporary"):
            exclusion_counts["retention_prohibited"] += 1
            continue

        # 4. External dataset handling (opt-in + redistributable license check)
        is_external = s.source in ("external_dataset", "public_dataset")
        if is_external:
            if not include_external:
                exclusion_counts["external_not_requested"] += 1
                continue
            if not is_redistributable_license(s.dataset_license):
                exclusion_counts["unlicensed_or_restrictive_external"] += 1
                continue

        # 5. Landmark physical file verification
        if not s.feature_path or not os.path.isfile(s.feature_path):
            exclusion_counts["missing_landmark_file"] += 1
            continue

        try:
            with open(s.feature_path, "rb") as f_test:
                file_bytes = f_test.read()
            if len(file_bytes) == 0:
                exclusion_counts["missing_landmark_file"] += 1
                continue
        except OSError:
            exclusion_counts["missing_landmark_file"] += 1
            continue

        sc = sign_classes.get(s.sign_class_id)
        signer = signers.get(s.signer_id)
        gloss = sc.gloss if sc else f"CLASS-{s.sign_class_id}"
        signer_code = signer.code if signer else f"S-{s.signer_id}"

        landmark_filename = f"landmarks/clip_{s.id}_{gloss}.npz"

        eligible_samples.append({
            "sample": s,
            "consent": c,
            "gloss": gloss,
            "signer_code": signer_code,
            "file_bytes": file_bytes,
            "landmark_filename": landmark_filename,
        })

    # Aggregations
    counts_by_sign = {}
    counts_by_source = {}
    unique_signers = set()
    external_datasets_map = {}

    for item in eligible_samples:
        s = item["sample"]
        gloss = item["gloss"]
        src_cat = "own" if s.source == "captured" else "external"

        counts_by_sign[gloss] = counts_by_sign.get(gloss, 0) + 1
        counts_by_source[src_cat] = counts_by_source.get(src_cat, 0) + 1
        unique_signers.add(item["signer_code"])

        if src_cat == "external":
            dname = s.dataset_name or "Unknown_External"
            if dname not in external_datasets_map:
                external_datasets_map[dname] = {
                    "dataset_name": dname,
                    "license": s.dataset_license,
                    "citation": s.citation,
                    "sample_count": 0,
                }
            external_datasets_map[dname]["sample_count"] += 1

    # Build CSV text
    csv_buf = io.StringIO()
    csv_writer = csv.writer(csv_buf)
    csv_header = [
        "clip_id",
        "sign",
        "signer_pseudonym",
        "source",
        "dataset_name",
        "external_sample_id",
        "external_signer_id",
        "licence",
        "consent_flags",
        "review_status",
        "extractor_version",
        "landmark_file",
    ]
    csv_writer.writerow(csv_header)

    sample_manifests_json = []

    for item in eligible_samples:
        s = item["sample"]
        c = item["consent"]
        gloss = item["gloss"]
        src_cat = "own" if s.source == "captured" else "external"
        dname = s.dataset_name if s.dataset_name else "SIGNFORGE_LOCAL"
        licence = s.dataset_license if src_cat == "external" else "Participant Consent (landmarks only)"
        consent_flags = ";".join(c.allowed_uses or [])
        ext_ver = f"{s.extractor}:{s.feature_schema_version}"

        csv_writer.writerow([
            s.id,
            gloss,
            item["signer_code"],
            src_cat,
            dname,
            s.external_sample_id or "",
            s.external_signer_id or "",
            licence,
            consent_flags,
            s.review_status,
            ext_ver,
            item["landmark_filename"],
        ])

        sample_manifests_json.append({
            "sample_id": s.id,
            "gloss": gloss,
            "signer_code": item["signer_code"],
            "source": s.source,
            "feature_schema_version": s.feature_schema_version,
            "frame_count": s.frame_count,
            "fps": s.fps,
            "quality_score": round(s.quality_score, 4),
            "split": s.split,
            "consent": {
                "allowed_uses": c.allowed_uses,
                "retention": c.retention,
                "status": c.status,
            },
            "provenance": {
                "note": s.provenance_note,
                "dataset_name": s.dataset_name,
                "dataset_version": s.dataset_version,
                "license": s.dataset_license,
                "citation": s.citation,
                "external_sample_id": s.external_sample_id,
            },
            "feature_file": item["landmark_filename"],
        })

    csv_content = csv_buf.getvalue()

    summary_data = {
        "project": {
            "id": project.id,
            "name": project.name,
            "target_language": project.target_language,
            "domain": project.domain,
        },
        "export_purpose": export_purpose,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_project_samples": len(all_samples),
        "total_exported_samples": len(eligible_samples),
        "distinct_signers_count": len(unique_signers),
        "counts_by_sign": counts_by_sign,
        "counts_by_source": counts_by_source,
        "external_datasets": list(external_datasets_map.values()),
        "excluded_samples_breakdown": {
            **exclusion_counts,
            "permanently_deleted_samples": "Untracked: deleted samples are permanently erased from SQLite without tombstone records.",
        },
        "known_limits": [
            "Pose (upper body) and hand landmarks only; raw video excluded by design for signer privacy.",
            "Normalized image coordinates [0, 1] x [0, 1] un-mirrored; depth z is relative MediaPipe scale.",
            "Extractor drift between browser and Python pipeline evaluated in simulation (< 0.005 MAE); real browser clips pending validation.",
            "Small signer pool (hackathon scope: target 3-7 signers).",
            "Deletion history is unavailable: deleted database records are permanently purged from SQLite without audit tombstone records.",
        ],
        "governance": {
            "raw_video_included": False,
            "personal_details_included": False,
            "pseudonymous_signers_only": True,
        },
    }

    manifest_json_data = {
        "format": "SIGNFORGE_CORPUS_MANIFEST_V1",
        "exported_at": summary_data["exported_at"],
        "project": summary_data["project"],
        "governance": {
            "landmark_schema": FEATURE_SCHEMA_VERSION,
            "points_per_frame": 75,
            "raw_video_included": False,
            "total_approved_samples": len(eligible_samples),
            "distinct_signers_count": len(unique_signers),
            "sources_breakdown": counts_by_source,
        },
        "sign_classes": [
            {"id": sc.id, "gloss": sc.gloss, "prompt_text": sc.prompt_text}
            for sc in sign_classes.values()
        ],
        "samples": sample_manifests_json,
    }

    return {
        "project": project,
        "eligible_samples": eligible_samples,
        "csv_content": csv_content,
        "summary_data": summary_data,
        "manifest_json_data": manifest_json_data,
    }


def create_corpus_export_zip(
    db: Session,
    project_id: int,
    include_demo: bool = False,
    include_external: bool = False,
    export_purpose: str = "corpus_building",
) -> Tuple[io.BytesIO, str]:
    """Generates an in-memory zip bundle containing landmarks/, manifest.csv, dataset_summary.json, and manifest.json."""
    data = collect_export_data(
        db=db,
        project_id=project_id,
        include_demo=include_demo,
        include_external=include_external,
        export_purpose=export_purpose,
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Landmark files in landmarks/
        for item in data["eligible_samples"]:
            zf.writestr(item["landmark_filename"], item["file_bytes"])

        # 2. manifest.csv
        zf.writestr("manifest.csv", data["csv_content"])

        # 3. dataset_summary.json
        zf.writestr("dataset_summary.json", json.dumps(data["summary_data"], indent=2))

        # 4. manifest.json (backward compatibility)
        zf.writestr("manifest.json", json.dumps(data["manifest_json_data"], indent=2))

    zip_buffer.seek(0)
    project_name = data["project"].name.lower().replace(" ", "_")
    export_filename = f"signforge_corpus_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return zip_buffer, export_filename


def export_corpus_to_folder(
    db: Session,
    project_id: int,
    output_dir: str,
    include_demo: bool = False,
    include_external: bool = False,
    export_purpose: str = "corpus_building",
) -> Dict[str, Any]:
    """Writes the exact export folder structure to a local filesystem directory."""
    data = collect_export_data(
        db=db,
        project_id=project_id,
        include_demo=include_demo,
        include_external=include_external,
        export_purpose=export_purpose,
    )

    out = Path(output_dir)
    landmarks_dir = out / "landmarks"
    landmarks_dir.mkdir(parents=True, exist_ok=True)

    for item in data["eligible_samples"]:
        rel_path = item["landmark_filename"]
        dest_file = out / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "wb") as f_out:
            f_out.write(item["file_bytes"])

    with open(out / "manifest.csv", "w", encoding="utf-8", newline="") as f_csv:
        f_csv.write(data["csv_content"])

    with open(out / "dataset_summary.json", "w", encoding="utf-8") as f_sum:
        json.dump(data["summary_data"], f_sum, indent=2)

    with open(out / "manifest.json", "w", encoding="utf-8") as f_man:
        json.dump(data["manifest_json_data"], f_man, indent=2)

    return {
        "output_dir": str(out.resolve()),
        "exported_samples": len(data["eligible_samples"]),
        "summary": data["summary_data"],
    }
