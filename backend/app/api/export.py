from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlmodel import Session

from app.db import get_session
from app.services.export import create_corpus_export_zip

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/corpus")
def download_corpus_zip(
    project_id: int = 1,
    include_demo: bool = False,
    include_external: bool = False,
    session: Session = Depends(get_session),
):
    """
    Exports all approved, consenting landmark features and an auditable manifest as a zip file.
    Raw video is strictly excluded.
    """
    try:
        buf, filename = create_corpus_export_zip(
            session,
            project_id=project_id,
            include_demo=include_demo,
            include_external=include_external,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
