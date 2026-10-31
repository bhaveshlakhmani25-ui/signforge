from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.db.models import ConsentRecord, Project, SignClass, Signer
from app.schemas import ConsentIn, ProjectIn, SignClassIn, SignerIn

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
