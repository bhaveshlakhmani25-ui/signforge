"""Live interpretation of a short window of landmarks. Nothing is stored: the window is scored and discarded.

It can only name signs the reference model was trained on (today: the INCLUDE subset). Anything else, and
anything it is unsure about, is reported as such rather than forced into the nearest known sign.
"""
import numpy as np
from sqlmodel import Session

from app.core import config as C
from app.core import thresholds as TH
from app.services import landmark_schema as S
from app.services import triage
from app.services.baseline_model import predict_logits
from app.services.calibration import softmax
from app.services.preprocessing import frames_to_arrays, model_input


def interpret(session: Session, frames: list[dict]) -> dict:
    run = triage.reference_run(session)
    if run is None:
        return {"state": "no_model", "message": "No trained model yet, so nothing can be interpreted.", "vocabulary": []}
    m = run.metrics
    glosses = {int(k): v for k, v in m["label_glosses"].items()}
    head = m["labels"]
    learned = [i for i, c in enumerate(head) if c in set(m["train_classes"])]
    vocab = [glosses[head[i]] for i in learned]
    base = {"vocabulary": vocab, "run_id": run.id, "calibration_passed": m["calibration"]["reliability_passed"]}

    points, present, t = frames_to_arrays(frames)
    if len(t) < 5:
        return {**base, "state": "waiting", "message": "Waiting for the camera."}
    hands = present[:, 1:].any(axis=1)
    if hands.mean() < TH.INTERPRET_MIN_HAND_SHARE:
        return {**base, "state": "no_hands", "message": "No hands in view. Sign with your hands in front of your body."}
    # Wrist travel across the window: a signer at rest should not be read as a sign.
    travel = []
    for slot, w in ((1, S.LH_WRIST), (2, S.RH_WRIST)):
        rows = present[:, slot]
        if rows.sum() > 2:
            xy = points[rows, w, :2]
            travel.append(float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum() / max(rows.sum() - 1, 1) * 10))
    if not travel or max(travel) < TH.INTERPRET_MIN_MOTION:
        return {**base, "state": "still", "message": "Hands are still. Make a sign."}

    x = model_input(points, t, C.TARGET_FPS, C.MODEL_FRAMES)
    logits = predict_logits(triage._model(run.id, run.weights_path, len(head), run.config["hidden"]), x[None])
    probs = softmax(logits[:, learned], m["calibration"]["temperature"])[0]
    order = np.argsort(probs)[::-1]
    top3 = [{"sign": vocab[j], "p": round(float(probs[j]), 4)} for j in order[:3]]
    best = top3[0]
    if best["p"] < TH.INTERPRET_MIN_CONF:
        return {**base, "state": "unsure", "top3": top3,
                "message": f"Not sure. Closest is {best['sign']} at {best['p']:.0%}, which may also be a sign the model has not learned."}
    return {**base, "state": "sign", "sign": best["sign"], "confidence": best["p"], "top3": top3}
