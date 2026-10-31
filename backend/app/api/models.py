import hashlib
import time
from typing import Literal

import numpy as np
import torch
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.projects import get_or_404, save
from app.core import config as C
from app.core import thresholds as TH
from app.db import get_session
from app.db.models import ConsentRecord, ModelRun, Project, Sample, SignClass
from app.services.mock_policy import mock_sample_clause, non_mock_sample_clause
from app.services.baseline_model import predict_logits, train_baseline
from app.services.calibration import fit_temperature, nll, reliability, softmax
from app.services.evaluation import classification_metrics
from app.services.landmark_schema import FEATURE_SCHEMA_VERSION
from app.services.preprocessing import model_input
from app.services.splits import assign_grouped_splits, assign_splits
from app.services.storage import load_features

router = APIRouter(prefix="/api/models")


class TrainIn(BaseModel):
    project_id: int
    pool: Literal["real", "demo", "external"] = "real"


def eligible_samples(session: Session, project_id: int, pool: str) -> list[Sample]:
    """Real pool: human-approved, QC-passed captures whose signer allowed model training (mock data excluded).
    Demo pool: QC-passed DEMO DATA not rejected/sent back by a reviewer.
    External pool: QC-passed external-dataset clips (labels from the dataset, not reviewed by us) not rejected/sent back."""
    q = select(Sample).where(Sample.project_id == project_id, Sample.qc_passed == True)  # noqa: E712
    if pool == "external":  # the dataset's licence is recorded as its consent: withdrawing it stops training too
        q = (select(Sample, ConsentRecord).join(ConsentRecord, Sample.consent_id == ConsentRecord.id)
             .where(Sample.project_id == project_id, Sample.qc_passed == True, Sample.source == "external_dataset",  # noqa: E712
                    Sample.review_status.not_in(["rejected", "needs_recapture"])))
        return [s for s, c in session.exec(q.order_by(Sample.id)).all()
                if c.status == "active" and "model_training" in c.allowed_uses]
    if pool == "demo":  # still respect any human decision against a sample
        q = q.where(mock_sample_clause(), Sample.review_status.not_in(["rejected", "needs_recapture"]))
        return list(session.exec(q.order_by(Sample.id)).all())
    q = (select(Sample, ConsentRecord).join(ConsentRecord, Sample.consent_id == ConsentRecord.id)
         .where(Sample.project_id == project_id, Sample.qc_passed == True,  # noqa: E712
                non_mock_sample_clause(), Sample.review_status == "approved"))
    return [s for s, c in session.exec(q.order_by(Sample.id)).all()
            if c.status == "active" and "model_training" in c.allowed_uses]


def calibrate(val_logits, y_val, test_logits, y_test) -> dict:
    """Fit T on val; judge it on the frozen test split (judging on val would be in-sample and prove nothing)."""
    t = fit_temperature(val_logits, y_val)
    before, after = reliability(softmax(test_logits), y_test, TH.CALIBRATION_BINS), reliability(softmax(test_logits, t), y_test, TH.CALIBRATION_BINS)
    return {
        "method": "temperature scaling, T fitted on the val split", "temperature": round(t, 4), "n_val": int(len(y_val)),
        "val_after": reliability(softmax(val_logits, t), y_val, TH.CALIBRATION_BINS),
        "test_before": before, "test_after": after,
        "test_nll_before": round(nll(test_logits, y_test), 4), "test_nll_after": round(nll(test_logits, y_test, t), 4),
        "max_ece": TH.RELIABILITY_MAX_ECE,
        "reliability_passed": after["ece"] <= TH.RELIABILITY_MAX_ECE and nll(test_logits, y_test, t) <= nll(test_logits, y_test),
    }


@router.post("/train-baseline", status_code=201)
def train_baseline_endpoint(body: TrainIn, session: Session = Depends(get_session)):
    get_or_404(session, Project, body.project_id)
    samples = eligible_samples(session, body.project_id, body.pool)
    if len({s.sign_class_id for s in samples}) < 2:
        found = "no usable samples" if not samples else (
            f"{len(samples)} usable sample{'s' if len(samples) != 1 else ''}, all of the same sign")
        raise HTTPException(422, f"Not enough data to train yet: {found}, and at least 2 signs are needed. A real sample is usable once it passes the automated check, "
                                 "is approved in human review, and its signer allowed model training.")

    split_fn = assign_grouped_splits if body.pool == "external" else assign_splits
    changes, strategy = split_fn([s.model_dump() for s in samples])
    for s in samples:
        s.split = changes.get(s.id, s.split)
        session.add(s)
    if strategy is None:  # test set was frozen by an earlier run of this pool
        prev = session.exec(select(ModelRun).where(ModelRun.project_id == body.project_id, ModelRun.pool == body.pool,
                                                   ModelRun.split_strategy != "").order_by(ModelRun.id)).first()
        strategy = prev.split_strategy if prev else "frozen test set"
    train = [s for s in samples if s.split == "train"]
    test = [s for s in samples if s.split == "test"]
    val = [s for s in samples if s.split == "val"]  # only the external pool has one: it fits the calibration temperature
    if not test or len({s.sign_class_id for s in train}) < 2:
        session.rollback()
        raise HTTPException(422, f"Not enough data to set aside a test set: {len(train)} for training and {len(test)} for testing. "
                                 "Record at least 2 usable samples of each sign.")
    session.commit()

    class_rows = session.exec(select(SignClass).where(SignClass.project_id == body.project_id).order_by(SignClass.id)).all()
    classes = [c.id for c in class_rows]
    label = {c: i for i, c in enumerate(classes)}
    run = save(session, ModelRun(
        project_id=body.project_id, model_kind="baseline", pool=body.pool, feature_schema_version=FEATURE_SCHEMA_VERSION,
        preprocessing={"target_fps": C.TARGET_FPS, "frames": C.MODEL_FRAMES, "points": "openhands minimal_27, x/y",
                       "normalisation": "clip-level shoulder centre/scale (OpenHands)"},
        data_version=hashlib.sha256("|".join(f"{s.id}:{s.feature_sha256}:{s.split}" for s in train + val + test).encode())
        .hexdigest()[:12],
        split_strategy=strategy, train_sample_ids=[s.id for s in train], test_sample_ids=[s.id for s in test],
        seed=C.SEED, config={"model": "GRU", **C.BASELINE}))
    t0 = time.perf_counter()
    try:
        def xy(rows):
            feats = [load_features(s.feature_path) for s in rows]
            X = np.stack([model_input(f["points"], f["t"], C.TARGET_FPS, C.MODEL_FRAMES) for f in feats])
            return X, np.array([label[s.sign_class_id] for s in rows])
        X_train, y_train = xy(train)
        X_test, y_test = xy(test)
        model = train_baseline(X_train, y_train, len(classes), C.BASELINE, C.SEED)
        test_logits = predict_logits(model, X_test)
        y_pred = test_logits.argmax(1)
        metrics = classification_metrics([classes[i] for i in y_test], [classes[i] for i in y_pred], classes)
        metrics["n_train"] = len(train)
        metrics["train_classes"] = sorted({s.sign_class_id for s in train})
        metrics["label_glosses"] = {c.id: c.gloss for c in class_rows}  # lets other projects match by gloss
        if val:
            X_val, y_val = xy(val)
            metrics["calibration"] = calibrate(predict_logits(model, X_val), y_val, test_logits, y_test)
        else:
            metrics["calibration"] = None
        metrics["val_sample_ids"] = [s.id for s in val]
        C.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        run.weights_path = str(C.CHECKPOINT_DIR / f"run_{run.id}.pt")
        torch.save(model.state_dict(), run.weights_path)
        run.metrics, run.status = metrics, "succeeded"
    except Exception as e:  # record the failure honestly instead of losing the run
        run.status, run.failure_detail = "failed", f"{type(e).__name__}: {e}"
    run.duration_s = round(time.perf_counter() - t0, 3)
    return save(session, run)


@router.get("/runs")
def list_runs(project_id: int, session: Session = Depends(get_session)):
    return session.exec(select(ModelRun).where(ModelRun.project_id == project_id).order_by(ModelRun.id.desc())).all()
