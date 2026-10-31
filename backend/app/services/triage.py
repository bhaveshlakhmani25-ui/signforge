"""Model triage (redesign F1/F2): match score of a clip against the reference model, and the tier it lands in.

The reference model is the latest succeeded run that has a calibration (in practice the INCLUDE external-pool run).
It may belong to another project, so signs are matched by gloss. A match score never says a sign is correct.
"""
import random
from functools import lru_cache

import numpy as np
import torch
from sqlmodel import Session, select

from app.core import config as C
from app.core import thresholds as TH
from app.db.models import ModelRun, Sample, SignClass
from app.services.baseline_model import GRUClassifier, predict_logits
from app.services.calibration import softmax
from app.services.preprocessing import model_input
from app.services.storage import load_features

HUMAN = {"approved": "human_verified", "rejected": "rejected", "needs_recapture": "needs_recapture"}


def status_of(sample: Sample) -> str:
    """The brief's single status: a human decision always wins over the model's triage."""
    return HUMAN.get(sample.review_status) or sample.triage_status or "needs_review"


def reference_run(session: Session) -> ModelRun | None:
    runs = session.exec(select(ModelRun).where(ModelRun.status == "succeeded").order_by(ModelRun.id.desc())).all()
    return next((r for r in runs if r.metrics.get("calibration") and r.weights_path), None)


@lru_cache(maxsize=4)
def _model(run_id: int, weights_path: str, n_classes: int, hidden: int) -> GRUClassifier:
    m = GRUClassifier(n_classes, hidden)
    m.load_state_dict(torch.load(weights_path))
    return m.eval()


def features(sample: Sample) -> np.ndarray:
    f = load_features(sample.feature_path)
    return model_input(f["points"], f["t"], C.TARGET_FPS, C.MODEL_FRAMES)


def nearest_same_sign(session: Session, sample: Sample, x: np.ndarray) -> float | None:
    others = session.exec(select(Sample).where(Sample.sign_class_id == sample.sign_class_id, Sample.id != sample.id,
                                               Sample.qc_passed == True)).all()  # noqa: E712
    return min((float(np.abs(x - features(o)).mean()) for o in others), default=None)


def audited(sample_id: int) -> bool:
    return random.Random(sample_id).random() < TH.AUDIT_RATE  # deterministic per clip, ~AUDIT_RATE overall


def predict(session: Session, sample: Sample) -> dict:
    gloss = session.get(SignClass, sample.sign_class_id).gloss
    failed = [f["code"] for f in sample.quality_flags if f["severity"] == "error"]
    out = {"sample_id": sample.id, "claimed_sign": gloss, "quality": {"passed": sample.qc_passed, "failed_checks": failed},
           "model": None, "match_confidence": None, "predicted_sign": None, "top3": [], "per_sign_test_recall": None,
           "calibration_note": None, "is_near_duplicate": False, "nearest_same_sign_distance": None, "audited": False,
           "auto_accept_enabled": TH.MODEL_VERIFY_ENABLED}
    if not sample.qc_passed:
        return {**out, "status": "auto_rejected", "reason": "The automated check failed, so the clip needs to be recorded again."}

    x = features(sample)
    dist = nearest_same_sign(session, sample, x)
    out["nearest_same_sign_distance"] = None if dist is None else round(dist, 4)
    out["is_near_duplicate"] = dist is not None and dist < TH.DUP_EPSILON

    run = reference_run(session)
    if run is None:
        return {**out, "status": "needs_review", "reason": "No calibrated model exists yet, so a reviewer has to check this clip."}
    m, cal = run.metrics, run.metrics["calibration"]
    glosses = {int(k): v for k, v in m["label_glosses"].items()}
    head = m["labels"]  # the output layer has a unit per project sign, including signs with no training clips
    learned = [i for i, c in enumerate(head) if c in set(m["train_classes"])]
    labels = [head[i] for i in learned]
    out["model"] = {"run_id": run.id, "project_id": run.project_id, "pool": run.pool, "temperature": cal["temperature"],
                    "reliability_passed": cal["reliability_passed"], "signs": [glosses[c] for c in labels]}
    if gloss not in out["model"]["signs"]:
        return {**out, "status": "needs_review",
                "reason": f"The model has not learned {gloss}, so it cannot score this clip. A reviewer has to check it."}

    logits = predict_logits(_model(run.id, run.weights_path, len(head), run.config["hidden"]), x[None])
    probs = softmax(logits[:, learned], cal["temperature"])[0]  # only signs the model was trained on can be predicted
    order = np.argsort(probs)[::-1]
    i_claim = [glosses[c] for c in labels].index(gloss)
    conf, top = float(probs[i_claim]), glosses[labels[order[0]]]
    out |= {"match_confidence": round(conf, 4), "predicted_sign": top,
            "top3": [{"sign": glosses[labels[j]], "p": round(float(probs[j]), 4)} for j in order[:3]]}
    pc = m["per_class"].get(str(labels[i_claim])) or m["per_class"].get(labels[i_claim])
    if pc and pc["support"]:
        k = head.index(labels[i_claim])
        out["per_sign_test_recall"] = {"hits": int(m["confusion_matrix"][k][k]), "support": pc["support"],
                                       "recall": pc["recall"]}
    top_conf = float(probs[order[0]])
    b = next((b for b in cal["test_after"]["bins"] if b["lo"] < top_conf <= b["hi"] or (b["lo"] == 0 and top_conf <= b["hi"])), None)
    if b and b["n"]:
        note = (f"On {b['n']} held-out test clips where the model was {round(b['lo'] * 100)}–{round(b['hi'] * 100)}% sure, "
                f"it was right {round(b['accuracy'] * b['n'])} of {b['n']} times.")
    else:
        note = "No held-out test clips had this confidence, so there is no evidence yet for how often it is right here."
    if not cal["reliability_passed"]:
        note += " This model failed its reliability check, so treat the percentage as approximate."
    out["calibration_note"] = note

    agrees = top == gloss
    confident = conf >= TH.VERIFY_MIN_CONF + TH.VERIFY_MARGIN
    if TH.MODEL_VERIFY_ENABLED and cal["reliability_passed"] and agrees and confident and not out["is_near_duplicate"]:
        out["audited"] = audited(sample.id)
        return {**out, "status": "model_verified", "reason": f"The model agrees this is {gloss} at {conf:.0%}."
                + (" It was also picked at random for a human audit." if out["audited"] else "")}
    auto_on = TH.MODEL_VERIFY_ENABLED and cal["reliability_passed"]
    why = (f"The model thinks this looks more like {top} ({float(probs[order[0]]):.0%}) than {gloss} ({conf:.0%})." if not agrees
           else f"The model agrees but is only {conf:.0%} sure." if not confident
           else "The model agrees, but auto-accept is switched off until a model passes its reliability check." if not auto_on
           else f"The model agrees at {conf:.0%}.")
    if out["is_near_duplicate"]:
        why += " The clip is almost identical to another clip of this sign, so it adds little and is not accepted automatically."
    return {**out, "status": "needs_review", "reason": why + " A reviewer has to check it."}


def apply(session: Session, sample: Sample) -> dict:
    """Run predict() and store the outcome on the sample (caller commits)."""
    r = predict(session, sample)
    sample.triage_status, sample.triage = r["status"], r
    sample.match_confidence, sample.predicted_sign = r["match_confidence"], r["predicted_sign"] or ""
    sample.is_near_duplicate, sample.audited = r["is_near_duplicate"], r["audited"]
    session.add(sample)
    return r
