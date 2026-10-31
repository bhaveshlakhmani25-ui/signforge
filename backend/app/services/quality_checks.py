"""Automated technical QC. This is NOT linguistic validation; only a human reviewer can do that."""
import numpy as np

from app.core import config as C
from app.services import landmark_schema as S


def run_qc(points: np.ndarray, present: np.ndarray, t: np.ndarray, width: int, height: int) -> dict:
    flags: list[dict] = []

    def flag(code: str, severity: str, message: str):
        flags.append({"code": code, "severity": severity, "message": message})

    T = len(t)
    if T == 0:
        flag("empty", "error", "No frames were extracted. Check the camera, lighting and that the signer is in view.")
        return {"passed": False, "flags": flags, "metrics": {"frame_count": 0}, "completeness": 0.0}

    duration = float(t[-1] - t[0])
    pose_missing = float(1 - present[:, 0].mean())
    no_hand = float(1 - present[:, 1:].any(axis=1).mean())
    completeness = float((present[:, 0] & present[:, 1:].any(axis=1)).mean())

    # D6: each hand slot's wrist should sit nearer its own pose wrist than the other one (catches left/right swaps).
    mismatched, checked = 0, 0
    for slot, hand_wrist, own, other in ((1, S.LH_WRIST, S.POSE_L_WRIST, S.POSE_R_WRIST),
                                         (2, S.RH_WRIST, S.POSE_R_WRIST, S.POSE_L_WRIST)):
        rows = present[:, 0] & present[:, slot]
        if rows.any():
            w = points[rows, hand_wrist, :2]
            d_own = np.linalg.norm(w - points[rows, own, :2], axis=1)
            d_other = np.linalg.norm(w - points[rows, other, :2], axis=1)
            mismatched += int((d_other < d_own).sum())
            checked += int(rows.sum())
    hand_side_mismatch = mismatched / checked if checked else 0.0

    # Only the points the model uses: a seated webcam never shows hips/legs, and that must not raise a warning.
    used = np.repeat(present, [S.N_POSE, S.N_HAND, S.N_HAND], axis=1)[:, S.MINIMAL_27]
    xy = points[:, S.MINIMAL_27, :2][used]
    out_of_frame = float(((xy < 0) | (xy > 1)).any(axis=-1).mean()) if len(xy) else 0.0

    metrics_hand: dict[str, float] = {}
    if duration < C.QC_MIN_DURATION_S:
        flag("too_short", "error", f"Clip is {duration:.1f}s; at least {C.QC_MIN_DURATION_S}s is needed for one sign.")
    if duration > C.QC_MAX_DURATION_S:
        flag("too_long", "error", f"Clip is {duration:.1f}s; record one sign per clip (max {C.QC_MAX_DURATION_S}s).")
    if pose_missing > C.QC_MAX_MISSING_SHOULDER_RATE:
        flag("body_missing", "error", f"Upper body not detected in {pose_missing:.0%} of frames; shoulders must stay in view.")
    if no_hand > C.QC_MAX_NO_HAND_RATE:
        flag("hands_missing", "error", f"No hand detected in {no_hand:.0%} of frames; sign with your hands in front of your body and in good light.")
    for slot, side in ((1, "left"), (2, "right")):
        missing = float(1 - present[:, slot].mean())
        metrics_hand[f"{side}_hand_missing_rate"] = round(missing, 3)
        # A hand never seen is likely a one-handed sign; a hand seen only sometimes is a tracking dropout.
        if C.QC_MAX_HAND_DROPOUT_RATE < missing < 1:
            flag(f"{side}_hand_dropout", "warning",
                 f"Signer's {side}-hand landmarks missing in {missing:.0%} of frames; improve lighting or keep the hand in view.")
    if hand_side_mismatch > C.QC_MAX_HAND_SIDE_MISMATCH_RATE:
        flag("hand_side_mismatch", "error",
             f"In {hand_side_mismatch:.0%} of frames a hand is labelled with the wrong side; the video may be mirrored.")
    if out_of_frame > 0.05:
        flag("out_of_frame", "warning", f"{out_of_frame:.0%} of the face, arm and hand landmarks are outside the frame; step back or centre yourself.")
    if height and abs(width / height - 16 / 9) > 0.05:
        flag("aspect_ratio", "warning", f"Video is {width}x{height}, not 16:9 like the pretraining data, so landmark positions may be slightly distorted. "
                                                f"Use a 16:9 camera setting if you can.")

    metrics = {"frame_count": T, "duration_s": round(duration, 3), "pose_missing_rate": round(pose_missing, 3),
               "no_hand_rate": round(no_hand, 3), "hand_side_mismatch_rate": round(hand_side_mismatch, 3),
               "out_of_frame_rate": round(out_of_frame, 3), **metrics_hand}
    passed = not any(f["severity"] == "error" for f in flags)
    return {"passed": passed, "flags": flags, "metrics": metrics, "completeness": round(completeness, 3)}
