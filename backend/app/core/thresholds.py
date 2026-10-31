"""Decision thresholds (redesign brief, F2/F4). Starting defaults, NOT calibrated: tune them against the simulation.
One file on purpose, so no threshold hides in the code as a magic number."""

# F4 sufficiency
TARGET_SAMPLES = 15      # usable clips per sign for "enough"
MIN_SIGNERS = 3          # distinct signers per sign for "enough"
PLATEAU_DELTA = 0.02     # validation-accuracy gain per added batch below which a sign has plateaued
MIN_VAL_CLIPS = 3        # fewer validation clips than this per sign -> status "unsure"

# F2 triage
VERIFY_MIN_CONF = 0.70   # calibrated confidence needed to auto-accept as model_verified
AUDIT_RATE = 0.15        # share of model_verified clips still sent to a human reviewer
VERIFY_MARGIN = 0.05     # confidence this close to VERIFY_MIN_CONF goes to review: the extractor alone moves it ~0.04 (docs/EXTRACTOR_COMPARISON.md)
# DUP_EPSILON is added in step 4, set from measured same-sign nearest-neighbour distances, not guessed.

# Step 3 calibration
CALIBRATION_BINS = 5     # few clips: more bins would leave most bins nearly empty
RELIABILITY_MAX_ECE = 0.10  # calibrated test-set ECE at or below this counts as a passed reliability check
