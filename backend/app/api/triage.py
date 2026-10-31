from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.projects import get_or_404
from app.db import get_session
from app.db.models import Project, Sample
from app.schemas import Frame
from app.services import interpret as interpreter
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


class InterpretIn(BaseModel):
    frames: list[Frame] = Field(max_length=300)  # about 10 s at 30 fps; the client sends ~2.5 s
    project_id: Optional[int] = None  # whose model reads the signing (e.g. the ISL or the ASL project); latest if absent


@router.post("/interpret")
def interpret(body: InterpretIn, session: Session = Depends(get_session)):
    """Live interpretation of a short landmark window. Not stored, not linked to any signer."""
    return interpreter.interpret(session, [f.model_dump() for f in body.frames], body.project_id)


@router.get("/interpret/languages")
def languages(session: Session = Depends(get_session)):
    """Projects that have a calibrated model the interpreter can use, one per sign language/dataset."""
    out = []
    for p in session.exec(select(Project).order_by(Project.id)).all():
        run = triage.reference_run(session, p.id)
        if run:
            out.append({"project_id": p.id, "name": p.name, "target_language": p.target_language, "run_id": run.id,
                        "n_signs": len(run.metrics["train_classes"]), "accuracy": run.metrics.get("accuracy")})
    return out
