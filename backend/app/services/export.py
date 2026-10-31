"""
SIGNFORGE Corpus Export Engine

Packages approved samples with an auditable manifest containing:
- Feature schema version and landmark layout
- Pseudonymous signer codes (no real names)
- Consent purposes and allowed uses
- Provenance and license attribution for all sources
- Strictly NO raw video
"""

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlmodel import Session, select

from app.db.models import ConsentRecord, Project, Sample, SignClass, Signer
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION


def create_corpus_export_zip(
    db: Session,
    project_id: int,
    include_demo: bool = False,
) -> Tuple[io.BytesIO, str]:
    """Generates a zip bundle containing manifest.json and approved landmark feature files."""
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

    # Query approved samples with active consent
    query = (
        select(Sample)
        .where(
            Sample.project_id == project_id,
            Sample.review_status == "approved",
        )
    )
    if not include_demo:
        query = query.where(Sample.source != "demo_fixture")

    samples = db.exec(query).all()

    # Filter out withdrawn consents
    eligible_samples = []
    for s in samples:
        c = consents.get(s.consent_id)
        if c and c.status == "active":
            eligible_samples.append((s, c))

    unique_signers = {signers[s.signer_id].code for s, _ in eligible_samples if s.signer_id in signers}

    # Build provenance summary
    sources_summary = {}
    for s, _ in eligible_samples:
        src = s.source
        sources_summary[src] = sources_summary.get(src, 0) + 1

    sample_manifests = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for s, c in eligible_samples:
            sc = sign_classes.get(s.sign_class_id)
            signer = signers.get(s.signer_id)
            gloss = sc.gloss if sc else f"CLASS-{s.sign_class_id}"
            signer_code = signer.code if signer else f"S-{s.signer_id}"

            feature_filename = f"features/sample_{s.id}_{gloss}.npz"

            # Read existing feature file and write to zip
            if s.feature_path and os.path.exists(s.feature_path):
                with open(s.feature_path, "rb") as f_in:
                    zf.writestr(feature_filename, f_in.read())

            sample_manifests.append({
                "sample_id": s.id,
                "gloss": gloss,
                "signer_code": signer_code,
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
                "feature_file": feature_filename,
            })

        manifest = {
            "format": "SIGNFORGE_CORPUS_MANIFEST_V1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": project.id,
                "name": project.name,
                "target_language": project.target_language,
                "domain": project.domain,
            },
            "governance": {
                "landmark_schema": FEATURE_SCHEMA_VERSION,
                "points_per_frame": 75,
                "raw_video_included": False,
                "total_approved_samples": len(eligible_samples),
                "distinct_signers_count": len(unique_signers),
                "sources_breakdown": sources_summary,
            },
            "sign_classes": [
                {"id": sc.id, "gloss": sc.gloss, "prompt_text": sc.prompt_text}
                for sc in sign_classes.values()
            ],
            "samples": sample_manifests,
        }

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buffer.seek(0)
    export_filename = f"signforge_corpus_{project.name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return zip_buffer, export_filename
