from pathlib import Path

import numpy as np

from app.core import config as C


# shortcut: local .npz files only, swap these two functions for Supabase Storage when it is configured.
def save_features(project_id: int, sample_id: int, points: np.ndarray, present: np.ndarray, t: np.ndarray) -> str:
    path = Path(C.DATA_DIR) / str(project_id) / f"{sample_id}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, points=points, present=present, t=t)
    return str(path)


def load_features(path: str) -> dict[str, np.ndarray]:
    with np.load(path) as f:
        return {k: f[k] for k in f.files}
