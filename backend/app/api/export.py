import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select

from app.api.projects import get_or_404
from app.core import config as C
from app.db import get_session
from app.db.models import ConsentRecord, Project, Sample, SignClass, Signer
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("", summary="Download zipped corpus export")
@router.get("/corpus", summary="Download zipped corpus export (alias)")
def export_corpus(
    project_id: int = Query(default=1, description="ID of project to export"),
    approved_only: bool = Query(default=True, description="Export approved samples only"),
    include_demo: bool = Query(default=False, description="Include synthetic demo fixture samples"),
    session: Session = Depends(get_session),
):
    project = get_or_404(session, Project, project_id)

    # Fetch sign classes and signers for metadata resolution
    classes = {c.id: c for c in session.exec(select(SignClass).where(SignClass.project_id == project_id)).all()}
    signers = {s.id: s for s in session.exec(select(Signer).where(Signer.project_id == project_id)).all()}

    # Query eligible samples
    stmt = select(Sample).where(Sample.project_id == project_id)
    if approved_only:
        stmt = stmt.where(Sample.review_status == "approved")
    if not include_demo:
        stmt = stmt.where(Sample.source != "demo_fixture")

    samples = session.exec(stmt.order_by(Sample.id.asc())).all()

    if not samples:
        raise HTTPException(
            status_code=400,
            detail=f"No eligible samples found for project #{project_id} (approved_only={approved_only}, include_demo={include_demo}).",
        )

    # Build export archive in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest_samples = []
        classes_in_export = set()

        for s in samples:
            sc_gloss = classes[s.sign_class_id].gloss if s.sign_class_id in classes else f"UNKNOWN_{s.sign_class_id}"
            signer_code = signers[s.signer_id].code if s.signer_id in signers else f"SIGNER_{s.signer_id}"
            classes_in_export.add(sc_gloss)

            lm_arcname = f"landmarks/{s.id}.npz"
            manifest_samples.append({
                "sample_id": s.id,
                "sign_class": sc_gloss,
                "signer_code": signer_code,
                "landmark_file": lm_arcname,
                "fps": s.fps,
                "width": s.width,
                "height": s.height,
                "frame_count": s.frame_count,
                "quality_score": s.quality_score,
                "qc_passed": s.qc_passed,
                "review_status": s.review_status,
                "source": s.source,
                "feature_sha256": s.feature_sha256,
                "provenance_note": s.provenance_note,
            })

            # Read landmark file from disk and add to archive
            feature_path = Path(s.feature_path)
            if feature_path.exists():
                z.write(feature_path, arcname=lm_arcname)
            else:
                # If feature_path moved or relative
                alt_path = Path(C.DATA_DIR) / str(project_id) / f"{s.id}.npz"
                if alt_path.exists():
                    z.write(alt_path, arcname=lm_arcname)

        # 1. Manifest
        manifest_data = {
            "dataset_name": f"{project.name} Corpus Export",
            "target_language": project.target_language,
            "domain": project.domain,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "schema_version": FEATURE_SCHEMA_VERSION,
            "approved_only": approved_only,
            "include_demo": include_demo,
            "n_samples": len(manifest_samples),
            "n_classes": len(classes_in_export),
            "classes": sorted(list(classes_in_export)),
            "samples": manifest_samples,
        }
        z.writestr("manifest.json", json.dumps(manifest_data, indent=2))

        # 2. Provenance document
        repo_root = Path(__file__).resolve().parents[3]
        provenance_path = repo_root / "dataset" / "INCLUDE" / "Dates_and_Time" / "provenance.md"
        if provenance_path.exists():
            z.write(provenance_path, arcname="provenance.md")
        else:
            provenance_content = f"""# Corpus Provenance: {project.name}
Export Timestamp: {datetime.now(timezone.utc).isoformat()}
Language: {project.target_language}
Domain: {project.domain}
Samples: {len(manifest_samples)}
License: CC-BY-4.0 / SIGNFORGE Privacy-by-Pose (landmarks only, raw video excluded).
"""
            z.writestr("provenance.md", provenance_content)

    buf.seek(0)
    zip_bytes = buf.getvalue()
    safe_name = project.name.lower().replace(" ", "_")
    filename = f"signforge_{safe_name}_export.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )
