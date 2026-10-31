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
# Auto-accept is OFF (team decision, 31 Oct 2026): the INCLUDE model failed its reliability check (test ECE 0.20 > 0.10).
# Even when switched on, model_verified also requires the reference run's reliability check to have passed.
MODEL_VERIFY_ENABLED = False
# Near-duplicate: mean |model input| distance to the nearest same-sign clip. Measured on INCLUDE Greetings: genuinely
# different takes come as close as 0.067, and the SAME video re-extracted differs by ~0.126, so distance cannot catch a
# re-uploaded video. 0.05 only flags near-identical landmark data (exact copies are already caught by the hash check).
DUP_EPSILON = 0.05

# Step 3 calibration
CALIBRATION_BINS = 5     # few clips: more bins would leave most bins nearly empty
RELIABILITY_MAX_ECE = 0.10  # calibrated test-set ECE at or below this counts as a passed reliability check

# Live interpreter (Capture > Interpret). MVP heuristics, not calibrated on live signing.
INTERPRET_MIN_CONF = 0.55     # below this the interpreter says "not sure" instead of naming a sign
INTERPRET_MIN_HAND_SHARE = 0.3  # share of window frames with a hand in view before anything is read
INTERPRET_MIN_MOTION = 0.02   # mean wrist travel (normalised image units) below this counts as "hands still"
