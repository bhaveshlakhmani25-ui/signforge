import hashlib
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.projects import delete_sample, get_or_404, save
from app.db import get_session
from app.db.models import ConsentRecord, ReviewEvent, Sample, SignClass, Signer
from app.schemas import CaptureIn, ReviewIn
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from app.services.mock_policy import non_mock_sample_clause
from app.services import landmark_schema as S
from app.services.preprocessing import frames_to_arrays, resample
from app.services.quality_checks import run_qc
from app.services.storage import load_features, save_features

router = APIRouter(prefix="/api/samples")


@router.post("/capture", status_code=201)
def capture(body: CaptureIn, session: Session = Depends(get_session)):
    sign_class = get_or_404(session, SignClass, body.sign_class_id)
    signer = get_or_404(session, Signer, body.signer_id)
    if sign_class.project_id != body.project_id or signer.project_id != body.project_id:
        raise HTTPException(422, "That sign or signer belongs to a different project. Reload the page and try again.")
    consent = session.get(ConsentRecord, body.consent_id)
    if consent is None or consent.signer_id != signer.id or consent.status != "active":
        raise HTTPException(403, "No active consent record for this signer; record consent before capturing.")
    if "corpus_building" not in consent.allowed_uses:
        raise HTTPException(403, "This signer's consent does not allow corpus building.")

    points, present, t = frames_to_arrays([f.model_dump() for f in body.frames])
    qc = run_qc(points, present, t, body.width, body.height)
    sha = hashlib.sha256(points.tobytes() + t.tobytes()).hexdigest()
    dup = session.exec(select(Sample.id).where(Sample.project_id == body.project_id, Sample.feature_sha256 == sha)).first()
    if dup is not None:
        qc["flags"].append({"code": "duplicate", "severity": "error",
                            "message": f"Identical landmarks already stored as sample #{dup}."})
        qc["passed"] = False

    if body.source == "demo_fixture":
        prov_note = "DEMO DATA: synthetic, not real signing"
    elif body.source in ("external_dataset", "public_dataset"):
        prov_note = f"External: {body.dataset_name} ({body.dataset_license}) - {body.citation}".strip()
    else:
        prov_note = "Captured in SIGNFORGE; landmarks only, raw video never uploaded"

    sample = Sample(
        project_id=body.project_id, sign_class_id=sign_class.id, signer_id=signer.id, consent_id=consent.id,
        source=body.source, feature_schema_version=FEATURE_SCHEMA_VERSION, extractor=body.extractor,
        extractor_model_sha=body.extractor_model_sha, fps=body.fps, width=body.width, height=body.height,
        frame_count=len(t), quality_score=qc["completeness"], qc_passed=qc["passed"], quality_flags=qc["flags"],
        qc_metrics=qc["metrics"], feature_sha256=sha,
        provenance_note=prov_note,
        dataset_name=body.dataset_name,
        dataset_version=body.dataset_version,
        dataset_license=body.dataset_license,
        citation=body.citation,
        external_sample_id=body.external_sample_id,
        external_signer_id=body.external_signer_id,
        external_split=body.external_split,
    )
    session.add(sample)
    session.flush()  # assign id; nothing is committed unless the feature file is written
    sample.feature_path = save_features(body.project_id, sample.id, points, present, t)
    session.commit()
    session.refresh(sample)
    return sample


@router.get("")
def list_samples(project_id: int, sign_class_id: Optional[int] = None, signer_id: Optional[int] = None,
                 review_status: Optional[str] = None, split: Optional[str] = None,
                 source: Optional[str] = None, include_demo: bool = False,
                 session: Session = Depends(get_session)):
    q = select(Sample).where(Sample.project_id == project_id)
    for col, val in ((Sample.sign_class_id, sign_class_id), (Sample.signer_id, signer_id),
                     (Sample.review_status, review_status), (Sample.split, split), (Sample.source, source)):
        if val is not None:
            q = q.where(col == val)
    if not include_demo:  # DEMO DATA never enters real listings/evaluation by default
        q = q.where(non_mock_sample_clause())
    return session.exec(q.order_by(Sample.id.desc())).all()


REPLAY_FPS = 15


@router.get("/{sample_id}/landmarks")
def landmarks(sample_id: int, session: Session = Depends(get_session)):
    """Stored landmarks for skeleton replay: x/y only, 15 fps, missing parts as null (not the model's zero-fill)."""
    sample = get_or_404(session, Sample, sample_id)
    f = load_features(sample.feature_path)
    xy = f["points"][..., :2].round(4)
    frames = [{part: (xy[i, sl].tolist() if f["present"][i, j] else None)
               for j, (part, sl) in enumerate((("pose", S.POSE), ("left", S.LEFT_HAND), ("right", S.RIGHT_HAND)))}
              for i in resample(f["t"], REPLAY_FPS)]
    return {"sample_id": sample.id, "source": sample.source, "fps": REPLAY_FPS, "width": sample.width,
            "height": sample.height, "frames": frames}


@router.get("/{sample_id}/reviews")
def list_reviews(sample_id: int, session: Session = Depends(get_session)):
    return session.exec(select(ReviewEvent).where(ReviewEvent.sample_id == sample_id)).all()


@router.post("/{sample_id}/review")
def review(sample_id: int, body: ReviewIn, session: Session = Depends(get_session)):
    """Human review. Recorded with the reviewer's self-declared role; QC never sets this."""
    sample = get_or_404(session, Sample, sample_id)
    session.add(ReviewEvent(sample_id=sample_id, **body.model_dump()))
    sample.review_status = body.decision
    return save(session, sample)


@router.delete("/{sample_id}", status_code=204)
def delete(sample_id: int, session: Session = Depends(get_session)):
    delete_sample(session, get_or_404(session, Sample, sample_id))
    session.commit()
