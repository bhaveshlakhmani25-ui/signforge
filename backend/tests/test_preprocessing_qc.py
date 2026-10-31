import numpy as np

from app.services import landmark_schema as S
from app.services.demo_fixture import demo_frames
from app.services.preprocessing import center_and_scale, fixed_length, frames_to_arrays, resample, select_minimal27_xy
from app.services.quality_checks import run_qc


def arrays(**kw):
    return frames_to_arrays(demo_frames(0, **kw))


def codes(qc):
    return {f["code"] for f in qc["flags"]}


def test_minimal27_mapping():
    assert len(S.MINIMAL_27) == 27
    assert [S.MINIMAL_27[i] for i in S.SHOULDER_NODES_27] == [S.POSE_L_SHOULDER, S.POSE_R_SHOULDER]
    assert S.MINIMAL_27[7] == S.LH_WRIST and S.MINIMAL_27[17] == S.RH_WRIST
    points, _, _ = arrays()
    assert select_minimal27_xy(points).shape == (len(points), 27, 2)


def test_zero_fill_for_missing_parts():
    frames = demo_frames(0)
    frames[3]["left_hand"] = None
    points, present, _ = frames_to_arrays(frames)
    assert not present[3, 1] and present[3, 0]
    assert (points[3, S.LEFT_HAND] == 0).all()


def test_t5_center_and_scale_unit_shoulders():
    x = center_and_scale(select_minimal27_xy(arrays()[0]))
    p1, p2 = x[:, 3], x[:, 4]
    np.testing.assert_allclose(((p1 + p2) / 2).mean(0), 0, atol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(p1 - p2, axis=-1).mean(), 1, atol=1e-5)


def test_t5_zero_filled_frames_match_openhands_formula():
    points, _, _ = arrays()
    points[:5, S.POSE] = 0  # body missing in 5 frames, zero-filled as OpenHands does
    x = select_minimal27_xy(points)
    p1, p2 = x[:, 3], x[:, 4]
    expected = (x - ((p1 + p2) / 2).mean(0)) / np.linalg.norm(p1 - p2, axis=-1).mean()
    np.testing.assert_allclose(center_and_scale(x), expected, rtol=1e-5)


def test_t5_all_zero_clip_is_left_unnormalized():
    x = np.zeros((10, 27, 2), np.float32)
    assert (center_and_scale(x) == 0).all()


def test_t8_resample_and_fixed_length():
    _, _, t = arrays(seconds=2.0, fps=30)
    idx = resample(t, 10)
    assert len(idx) == 20 and idx[0] == 0 and (np.diff(idx) == 3).all()  # 30 fps -> every 3rd frame
    assert len(fixed_length(len(idx), 60)) == 60 and len(fixed_length(200, 60)) == 60
    np.testing.assert_array_equal(fixed_length(20, 60), fixed_length(20, 60))  # deterministic: same for train/predict


def test_qc_clean_demo_passes():
    qc = run_qc(*arrays(), width=1280, height=720)
    assert qc["passed"], qc["flags"]
    assert qc["completeness"] == 1.0


def test_t6_hand_side_swap_flagged():
    qc = run_qc(*arrays(swap_hands=True), width=1280, height=720)
    assert "hand_side_mismatch" in codes(qc) and not qc["passed"]


def test_qc_empty():
    qc = run_qc(*frames_to_arrays([]), width=1280, height=720)
    assert codes(qc) == {"empty"} and not qc["passed"]


def test_qc_too_short():
    assert "too_short" in codes(run_qc(*arrays(seconds=0.5), width=1280, height=720))


def test_qc_hands_and_body_missing():
    frames = demo_frames(0)
    for f in frames:
        f["left_hand"] = f["right_hand"] = None
        f["pose"] = None
    qc = run_qc(*frames_to_arrays(frames), width=1280, height=720)
    assert {"hands_missing", "body_missing"} <= codes(qc)


def test_qc_aspect_ratio_warning_does_not_fail():
    qc = run_qc(*arrays(), width=640, height=480)
    assert "aspect_ratio" in codes(qc) and qc["passed"]


def test_hand_dropout_warns_but_one_handed_sign_does_not():
    frames = demo_frames(0)
    for f in frames[: len(frames) // 2]:
        f["right_hand"] = None  # tracked in half the clip: dropout
    qc = run_qc(*frames_to_arrays(frames), width=1280, height=720)
    assert "right_hand_dropout" in codes(qc) and qc["passed"]
    assert qc["metrics"]["right_hand_missing_rate"] == 0.5

    frames = demo_frames(0)
    for f in frames:
        f["right_hand"] = None  # never present: one-handed sign
    assert "right_hand_dropout" not in codes(run_qc(*frames_to_arrays(frames), width=1280, height=720))


def test_out_of_frame_ignores_legs_but_catches_arms():
    frames = demo_frames(0)
    for f in frames:
        for i in range(23, 33):
            f["pose"][i][1] = 1.4  # hips/legs below a seated webcam's frame: normal
    assert "out_of_frame" not in codes(run_qc(*frames_to_arrays(frames), width=1280, height=720))
    for f in frames:
        f["pose"][13][1] = f["pose"][14][1] = 1.2  # elbows (model points) out of frame
    assert "out_of_frame" in codes(run_qc(*frames_to_arrays(frames), width=1280, height=720))
