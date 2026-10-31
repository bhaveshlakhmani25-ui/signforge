"""Extract mp-holistic-75-xyz-v1 landmarks from INCLUDE category folders and write a manifest.json that
app.services.external_dataset.import_external_dataset_from_manifest can import.

Needs `pip install mediapipe opencv-python-headless numpy` (not in requirements.txt: one-off tool).
Same model file as the browser extractor, so extractor_model_sha matches captured samples.

  python extract_include.py <dir with sign folders, e.g. "48. Hello"> <out dir> [--jobs 3]
"""
import argparse, hashlib, json, re
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parents[2] / "frontend/public/models/holistic_landmarker.task"
_lm = None


def _landmarker():
    global _lm
    if _lm is None:
        from mediapipe.tasks.python import BaseOptions, vision
        _lm = vision.HolisticLandmarker.create_from_options(vision.HolisticLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=vision.RunningMode.VIDEO))
    return _lm


def extract(job):
    import mediapipe as mp
    src, dst = job
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    lm = _landmarker()
    pts, pres, ts, i = [], [], [], 0
    base_ms = int(hash(str(src)) % 1000) * 0  # each clip gets a fresh landmarker below
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        r = lm.detect_for_video(mp.Image(mp.ImageFormat.SRGB, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)), int(i * 1000 / fps) + base_ms)
        p = np.zeros((75, 3), np.float32); pr = np.zeros(3, bool)
        for j, (res, lo, n) in enumerate(((r.pose_landmarks, 0, 33), (r.left_hand_landmarks, 33, 21), (r.right_hand_landmarks, 54, 21))):
            if res:
                p[lo:lo + n] = [[q.x, q.y, q.z] for q in res]; pr[j] = True
        pts.append(p); pres.append(pr); ts.append(i / fps); i += 1
    cap.release()
    global _lm
    _lm = None  # timestamps restart per clip, so use a fresh landmarker
    np.savez_compressed(dst, points=np.stack(pts), present=np.stack(pres), t=np.array(ts, np.float64))
    return {"fps": fps, "width": w, "height": h, "frames": i}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--jobs", type=int, default=3); ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    out = Path(a.out); (out / "features").mkdir(parents=True, exist_ok=True)
    jobs, meta = [], []
    for d in sorted(Path(a.src).iterdir()):
        if not d.is_dir():
            continue
        gloss = re.sub(r"[^A-Z0-9]+", "-", re.sub(r"^\d+\.\s*", "", d.name).upper()).strip("-")  # "you (plural)" -> YOU-PLURAL
        for f in sorted(d.glob("*.MOV"))[: a.limit]:
            rel = f"features/{d.name.split('.')[0]}_{f.stem}.npz"
            jobs.append((f, out / rel)); meta.append((gloss, f.stem, rel))
    with Pool(a.jobs) as pool:
        infos = pool.map(extract, jobs, chunksize=1)
    sha = hashlib.sha256(MODEL.read_bytes()).hexdigest()
    samples = [{"gloss": g, "external_sample_id": s, "external_signer_id": "unknown", "external_split": "unassigned",
                "feature_file": rel, **{k: info[k] for k in ("fps", "width", "height")}} for (g, s, rel), info in zip(meta, infos)]
    (out / "manifest.json").write_text(json.dumps({
        "dataset_name": "INCLUDE", "dataset_version": "zenodo-4010759", "license": "CC BY 4.0",
        "citation": "Sridhar et al., INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition, ACM MM 2020. doi:10.5281/zenodo.4010759",
        "provenance_note": f"INCLUDE {Path(a.src).name.replace('_', ' ')} category; no signer IDs and no official split in these zips; landmarks extracted locally, raw video not stored",
        "feature_schema_version": "mp-holistic-75-xyz-v1", "extractor": "mediapipe-python HolisticLandmarker (float16)",
        "extractor_model_sha": sha, "samples": samples}, indent=1))
    print(len(samples), "clips ->", out / "manifest.json")
