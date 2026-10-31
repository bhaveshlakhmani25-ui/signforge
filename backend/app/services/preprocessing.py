import numpy as np

from app.services import landmark_schema as S


def frames_to_arrays(frames: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Browser frames -> (points (T,75,3) float32, present (T,3) bool [pose, lh, rh], t (T,) float64 seconds).

    Missing parts are zero-filled, as in OpenHands mediapipe_extract.py (plan D3). Shapes are validated upstream.
    """
    T = len(frames)
    points = np.zeros((T, S.N_POINTS, 3), np.float32)
    present = np.zeros((T, 3), bool)
    for i, f in enumerate(frames):
        for j, (key, sl) in enumerate((("pose", S.POSE), ("left_hand", S.LEFT_HAND), ("right_hand", S.RIGHT_HAND))):
            if f.get(key) is not None:
                points[i, sl] = np.asarray(f[key], np.float32)[:, :3]  # drop pose visibility
                present[i, j] = True
    t = np.array([f["t"] for f in frames], np.float64)
    return points, present, t


def resample(t: np.ndarray, fps: float) -> np.ndarray:
    """Indices of the frames nearest to a uniform `fps` grid over the clip (no interpolation of zero-filled parts)."""
    if len(t) == 0:
        return np.zeros(0, int)
    grid = np.arange(t[0], t[-1] + 1e-9, 1.0 / fps)
    return np.abs(t[None, :] - grid[:, None]).argmin(axis=1)


def fixed_length(n_frames: int, length: int) -> np.ndarray:
    """Indices that stretch/squash a clip to exactly `length` frames; the same rule for training and prediction."""
    return np.linspace(0, n_frames - 1, length).round().astype(int)


def select_minimal27_xy(points: np.ndarray) -> np.ndarray:
    """(T,75,3) -> (T,27,2): OpenHands PoseSelect minimal_27, x,y only (checkpoint uses 2 channels)."""
    return points[:, S.MINIMAL_27, :2]


def center_and_scale(x: np.ndarray) -> np.ndarray:
    """OpenHands CenterAndScaleNormalize, clip level, copied exactly (plan D3): stats over ALL frames, zeros included."""
    p1, p2 = x[:, S.SHOULDER_NODES_27[0]], x[:, S.SHOULDER_NODES_27[1]]
    center = ((p1 + p2) / 2).mean(axis=0)
    mean_dist = np.sqrt(((p1 - p2) ** 2).sum(-1)).mean()
    with np.errstate(divide="ignore"):
        scale = np.float32(1.0) / mean_dist
    if np.isinf(scale):
        return x  # OpenHands: "Do not normalize"
    return (x - center) * scale


def model_input(points: np.ndarray, t: np.ndarray, fps: float, length: int) -> np.ndarray:
    """The one feature contract for every model: stored (T,75,3) -> (length,27,2) float32.

    Resample to `fps`, stretch/squash to `length`, then OpenHands minimal-27 x/y with clip-level normalisation.
    """
    idx = resample(t, fps)
    idx = idx[fixed_length(len(idx), length)]
    return center_and_scale(select_minimal27_xy(points[idx])).astype(np.float32)
