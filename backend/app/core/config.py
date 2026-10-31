import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SIGNFORGE_DATA_DIR", BACKEND_DIR.parent / "data" / "processed"))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'signforge.db'}")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

# D5: one sampling rate for every experiment (pretraining effective rate ~8-10 fps, see plan U3).
TARGET_FPS = 10

# QC thresholds: MVP heuristics, not calibrated on real ISL data yet.
QC_MIN_DURATION_S = 0.8
QC_MAX_DURATION_S = 8.0
QC_MAX_MISSING_SHOULDER_RATE = 0.2
QC_MAX_NO_HAND_RATE = 0.5
QC_MAX_HAND_SIDE_MISMATCH_RATE = 0.2
QC_MAX_HAND_DROPOUT_RATE = 0.3

# Model input: TARGET_FPS sampling stretched to MODEL_FRAMES (3 windows of 10). Same for training and prediction.
MODEL_FRAMES = 30
assert MODEL_FRAMES % 10 == 0, "OpenHands DPC reads clips in windows of 10 frames"
SEED = 0
# Chosen on the INCLUDE val split (3 seeds): 80 epochs underfit (train acc 0.65). Never tuned on a test split.
BASELINE = {"hidden": 128, "epochs": 300, "lr": 3e-3, "weight_decay": 1e-4}
TEST_FRACTION = 0.2  # random clip split only; signer-independent splits hold out whole signers
MIN_SIGNERS_FOR_SIGNER_SPLIT = 3
# External datasets (no signer IDs): whole recording-session groups held out per sign, see splits.assign_grouped_splits.
EXTERNAL_TEST_GROUPS_PER_SIGN = 1
EXTERNAL_VAL_GROUPS_PER_SIGN = 1
CHECKPOINT_DIR = Path(os.environ.get("SIGNFORGE_CHECKPOINT_DIR", BACKEND_DIR / "checkpoints"))
BENCHMARK_PATH = Path(os.environ.get("SIGNFORGE_BENCHMARK_PATH", BACKEND_DIR.parent / "data" / "benchmark_results.json"))
