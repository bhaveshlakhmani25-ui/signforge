from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import export, models, projects, samples
from app.core import config as C
from app.db import get_session, init_db
from app.db.models import Sample, SignClass
from app.services import demo_fixture
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from fastapi import Depends
from sqlmodel import Session, select


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SIGNFORGE API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=C.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(projects.router)
app.include_router(samples.router)
app.include_router(models.router)
app.include_router(export.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")  # this is the API; the app itself runs on http://localhost:3000


@app.get("/api/health")
def health():
    return {"status": "ok", "feature_schema_version": FEATURE_SCHEMA_VERSION, "target_fps": C.TARGET_FPS,
            "transfer_model": "not verified: checkpoint compatibility tests not written yet"}


@app.get("/api/demo-frames")
def demo_frames_endpoint(class_index: int = 0, seed: int = 0):
    """DEMO DATA fallback when no webcam is available; submitted through the normal capture path as demo_fixture."""
    return {"extractor": demo_fixture.EXTRACTOR, "fps": 30, "width": 1280, "height": 720,
            "frames": demo_fixture.demo_frames(class_index % 10, seed)}


@app.get("/api/queue")
def queue_endpoint(project_id: int = 1, session: Session = Depends(get_session)):
    """Active Learning Ranker: ranks sign classes by coverage gap, signer diversity gap, and uncertainty."""
    classes = session.exec(select(SignClass).where(SignClass.project_id == project_id, SignClass.active == True)).all()
    samples = session.exec(select(Sample).where(Sample.project_id == project_id, Sample.source != "demo_fixture")).all()

    TARGET_SAMPLES = 5.0
    TARGET_SIGNERS = 3.0

    items = []
    for sc in classes:
        cls_samples = [s for s in samples if s.sign_class_id == sc.id and s.review_status == "approved"]
        n_samples = len(cls_samples)
        n_signers = len(set(s.signer_id for s in cls_samples))

        coverage_gap = max(0.0, min(1.0, 1.0 - (n_samples / TARGET_SAMPLES)))
        signer_gap = max(0.0, min(1.0, 1.0 - (n_signers / TARGET_SIGNERS)))
        uncertainty = None
        priority = round(coverage_gap + signer_gap, 2)

        if n_samples == 0:
            reason = "No approved samples in dataset. High recording priority."
        elif n_signers < 2:
            reason = f"Only {n_signers} signer(s) captured ({n_samples} samples). Needs signer diversity."
        elif coverage_gap > 0:
            reason = f"Thin corpus ({n_samples}/{int(TARGET_SAMPLES)} samples). Additional samples needed."
        else:
            reason = f"Adequate coverage ({n_samples} samples across {n_signers} signers)."

        items.append({
            "sign_id": sc.id,
            "gloss": sc.gloss,
            "priority": priority,
            "coverage_gap": round(coverage_gap, 2),
            "signer_gap": round(signer_gap, 2),
            "uncertainty": uncertainty,
            "reason": reason,
        })

    items.sort(key=lambda x: (-x["priority"], x["gloss"]))

    return {
        "formula": "coverage_gap + signer_gap + uncertainty (each scaled 0 to 1)",
        "uncertainty_available": False,
        "items": items,
    }

