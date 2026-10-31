"""DEMO DATA: synthetic landmark sequences in the browser frame format. Not real signing; never use for evaluation."""
import numpy as np

EXTRACTOR = "demo_fixture/synthetic-v2"

# A seated signer facing the camera, un-mirrored (signer's left side at image right). MediaPipe pose indices.
_BODY = {0: (0.50, 0.30), 1: (0.515, 0.28), 2: (0.525, 0.28), 3: (0.535, 0.28), 4: (0.485, 0.28), 5: (0.475, 0.28),
         6: (0.465, 0.28), 7: (0.55, 0.29), 8: (0.45, 0.29), 9: (0.515, 0.34), 10: (0.485, 0.34),
         11: (0.60, 0.48), 12: (0.40, 0.48), 23: (0.57, 0.92), 24: (0.43, 0.92),
         25: (0.57, 1.20), 26: (0.43, 1.20), 27: (0.57, 1.45), 28: (0.43, 1.45),  # legs: below a webcam frame
         29: (0.57, 1.50), 30: (0.43, 1.50), 31: (0.58, 1.52), 32: (0.42, 1.52)}


def _hand_template() -> np.ndarray:
    """21 hand landmarks for an open hand pointing up (wrist at origin, thumb towards +x), unit scale."""
    pts = [(0.0, 0.0)]
    for angle, start in ((-55, 0.25), (-15, 0.45), (0, 0.47), (15, 0.45), (30, 0.40)):  # thumb, index..pinky
        a = np.radians(angle)
        direction = np.array([-np.sin(a), -np.cos(a)])  # y up is negative in image coordinates
        pts += [tuple(direction * (start + 0.18 * k)) for k in range(4)]
    return np.array(pts)


_HAND = _hand_template()


def demo_frames(class_index: int, seed: int = 0, seconds: float = 2.0, fps: float = 30.0,
                swap_hands: bool = False) -> list[dict]:
    rng = np.random.default_rng(seed * 1000 + class_index)
    pose = np.zeros((33, 4))
    pose[:, 3] = 1.0
    for i, xy in _BODY.items():
        pose[i, :2] = xy
    freq, phase = 0.5 + 0.25 * class_index, class_index * 0.7  # each sign class moves differently
    frames = []
    for i in range(int(seconds * fps)):
        t = i / fps
        p = pose.copy()
        p[15, :2] = (0.60 + 0.08 * np.sin(2 * np.pi * freq * t + phase), 0.55 - 0.15 * np.cos(2 * np.pi * freq * t))
        p[16, :2] = (0.36 - 0.05 * np.sin(2 * np.pi * freq * t), 0.72)
        for elbow, shoulder, wrist, out in ((13, 11, 15, 0.05), (14, 12, 16, -0.05)):
            p[elbow, :2] = (p[shoulder, :2] + p[wrist, :2]) / 2 + (out, 0.06)  # elbow bends outward and down
        for finger, wrist in ((17, 15), (19, 15), (21, 15), (18, 16), (20, 16), (22, 16)):
            p[finger, :2] = p[wrist, :2] + (0, -0.03)
        p[:, :2] += rng.normal(0, 0.002, (33, 2))
        hands = [p[15, :3] + np.c_[_HAND * (-0.07, 0.07), np.zeros(21)],  # signer's left: thumb towards body centre
                 p[16, :3] + np.c_[_HAND * (0.07, 0.07), np.zeros(21)]]
        for h in hands:
            h[:, :2] += rng.normal(0, 0.002, (21, 2))
        hands[0][0], hands[1][0] = p[15, :3], p[16, :3]  # hand landmark 0 is the wrist
        if swap_hands:
            hands.reverse()
        frames.append({"t": t, "pose": p.tolist(), "left_hand": hands[0].tolist(), "right_hand": hands[1].tolist()})
    return frames
