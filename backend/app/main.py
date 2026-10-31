from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import active_learning, benchmark, export, models, projects, samples, triage
from app.core import config as C
from app.db import init_db
from app.services import demo_fixture
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SIGNFORGE API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=C.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(projects.router)
app.include_router(samples.router)
app.include_router(models.router)
app.include_router(active_learning.router)
app.include_router(export.router)
app.include_router(benchmark.router)
app.include_router(triage.router)


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
