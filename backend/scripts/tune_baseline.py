"""Pick baseline training settings on the VALIDATION split of an existing run (its exact train/val clips).

The test split is never read here: choose a config by mean val accuracy over seeds, then train the real run through
POST /api/models/train-baseline so the frozen test set is used once.

  .venv/bin/python scripts/tune_baseline.py --run 6
"""
import argparse, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sqlmodel import Session, select

from app.core import config as C
from app.db import engine
from app.db.models import ModelRun, Sample, SignClass
from app.services.baseline_model import predict_logits, train_baseline
from app.services.calibration import nll
from app.services.triage import features

GRID = {
    "current": {},
    "augment": {"augment": True},
    "dropout 0.3": {"dropout": 0.3},
    "augment + dropout 0.3": {"augment": True, "dropout": 0.3},
    "augment + 600 epochs": {"augment": True, "epochs": 600},
    "augment + dropout 0.3 + 600 epochs": {"augment": True, "dropout": 0.3, "epochs": 600},
}

ap = argparse.ArgumentParser()
ap.add_argument("--run", type=int, required=True)
ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
a = ap.parse_args()
with Session(engine) as s:
    run = s.get(ModelRun, a.run)
    classes = [c.id for c in s.exec(select(SignClass).where(SignClass.project_id == run.project_id).order_by(SignClass.id)).all()]
    label = {c: i for i, c in enumerate(classes)}
    def xy(ids):
        rows = [s.get(Sample, i) for i in ids]
        return np.stack([features(r) for r in rows]), np.array([label[r.sign_class_id] for r in rows])
    X, y = xy(run.train_sample_ids)
    Xv, yv = xy(run.metrics["val_sample_ids"])
print(f"run #{a.run}: {len(y)} train, {len(yv)} val clips, {len(set(y))} signs; seeds {a.seeds}; test split not read")
for name, over in GRID.items():
    cfg, t0, acc, loss = {**C.BASELINE, **over}, time.perf_counter(), [], []
    for seed in a.seeds:
        lv = predict_logits(train_baseline(X, y, len(classes), cfg, seed), Xv)
        acc.append(float((lv.argmax(1) == yv).mean())); loss.append(nll(lv, yv))
    print(f"{name:38s} val acc {np.mean(acc):.3f} ± {np.std(acc):.3f}  val NLL {np.mean(loss):.3f}  ({time.perf_counter() - t0:.0f}s)")
