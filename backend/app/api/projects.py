from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.db.models import ConsentRecord, Project, ReviewEvent, Sample, SignClass, Signer
from app.schemas import ConsentIn, ProjectIn, SignClassIn, SignerIn, WithdrawIn
from app.services.storage import delete_features

router = APIRouter(prefix="/api")


def get_or_404(session: Session, model, id_: int):
    obj = session.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {id_} not found")
    return obj


def save(session: Session, obj):
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def delete_sample(session: Session, sample: Sample) -> None:
    """Erase a sample's landmark file, its review events and its row. The caller commits.
    Models already trained on it are not retrained; their runs keep the ids but not the data."""
    delete_features(sample.feature_path)
    for e in session.exec(select(ReviewEvent).where(ReviewEvent.sample_id == sample.id)).all():
        session.delete(e)
    session.delete(sample)


@router.get("/projects")
def list_projects(session: Session = Depends(get_session)):
    return session.exec(select(Project)).all()


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)):
    return save(session, Project(**body.model_dump()))


@router.get("/sign-classes")
def list_sign_classes(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(SignClass).where(SignClass.project_id == project_id)).all()


@router.post("/sign-classes", status_code=201)
def create_sign_class(body: SignClassIn, session: Session = Depends(get_session)):
    get_or_404(session, Project, body.project_id)
    return save(session, SignClass(**body.model_dump()))


@router.get("/signers")
def list_signers(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Signer).where(Signer.project_id == project_id)).all()


@router.post("/signers", status_code=201)
def create_signer(body: SignerIn, session: Session = Depends(get_session)):
    get_or_404(session, Project, body.project_id)
    existing = session.exec(select(Signer).where(Signer.project_id == body.project_id, Signer.code == body.code)).first()
    return existing or save(session, Signer(**body.model_dump()))


@router.get("/consents")
def list_consents(signer_id: int, session: Session = Depends(get_session)):
    return session.exec(select(ConsentRecord).where(ConsentRecord.signer_id == signer_id)).all()


@router.post("/consents", status_code=201)
def create_consent(body: ConsentIn, session: Session = Depends(get_session)):
    get_or_404(session, Signer, body.signer_id)
    return save(session, ConsentRecord(**body.model_dump(exclude={"confirmed"}), raw_video_retained=False))


@router.post("/consents/{consent_id}/withdraw")
def withdraw_consent(consent_id: int, body: Optional[WithdrawIn] = None, delete_samples: Optional[bool] = None,
                     session: Session = Depends(get_session)):
    """Stops all future use (capture, training, export, public replay). Optionally erases the samples recorded under it.
    The choice must be explicit: JSON body {"delete_samples": ...} or ?delete_samples=... query parameter."""
    erase = body.delete_samples if body is not None else delete_samples
    if erase is None:
        raise HTTPException(422, "Say whether to also delete this consent's samples (delete_samples true or false).")
    consent = get_or_404(session, ConsentRecord, consent_id)
    consent.status = "withdrawn"
    session.add(consent)
    affected = session.exec(select(Sample).where(Sample.consent_id == consent_id)).all()
    for s in affected:
        if erase:
            delete_sample(session, s)
        elif "[CONSENT WITHDRAWN]" not in s.provenance_note:
            # Not a review decision: consent status alone keeps these out of training, export and the ranker.
            s.provenance_note = f"{s.provenance_note} [CONSENT WITHDRAWN]".strip()
            session.add(s)
    session.commit()
    deleted = len(affected) if erase else 0
    return {"status": consent.status, "consent_id": consent_id, "samples_affected": len(affected),
            "samples_deleted": deleted, "deleted_samples": deleted}
