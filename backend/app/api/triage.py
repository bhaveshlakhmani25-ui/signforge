from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.projects import get_or_404
from app.db import get_session
from app.db.models import Project, Sample
from app.services import triage

router = APIRouter(prefix="/api")


class PredictIn(BaseModel):
    sample_id: int  # landmarks are already stored at capture, so they are not sent twice


@router.post("/predict")
def predict(body: PredictIn, session: Session = Depends(get_session)):
    """Match score and triage tier for one stored clip (re-runs and stores it)."""
    sample = get_or_404(session, Sample, body.sample_id)
    if sample.source != "captured":
        raise HTTPException(422, "Only clips recorded in SIGNFORGE are triaged: external clips may be the model's training data.")
    r = triage.apply(session, sample)
    session.commit()
    return r


@router.post("/triage/rerun")
def rerun(project_id: int, session: Session = Depends(get_session)):
    """Re-triage every recorded clip still waiting for a human (e.g. after a new reference model)."""
    get_or_404(session, Project, project_id)
    rows = session.exec(select(Sample).where(Sample.project_id == project_id, Sample.source == "captured",
                                             Sample.review_status == "pending_review")).all()
    counts: dict[str, int] = {}
    for s in rows:
        st = triage.apply(session, s)["status"]
        counts[st] = counts.get(st, 0) + 1
    session.commit()
    return {"retriaged": len(rows), "by_status": counts}
