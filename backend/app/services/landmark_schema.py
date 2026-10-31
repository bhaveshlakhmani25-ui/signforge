"""75-point layout used by AI4Bharat OpenHands (MediaPipe Holistic minus face).

Source: github.com/AI4Bharat/OpenHands scripts/mediapipe_extract.py (body, face, lh, rh concat, face dropped)
and openhands/datasets/pose_transforms.py (PoseSelect / CenterAndScaleNormalize presets).
"""

FEATURE_SCHEMA_VERSION = "mp-holistic-75-xyz-v1"

N_POSE, N_HAND = 33, 21
POSE = slice(0, 33)
LEFT_HAND = slice(33, 54)   # signer's left hand (plan U1: verified per sample by QC hand-side check)
RIGHT_HAND = slice(54, 75)
N_POINTS = 75

POSE_L_SHOULDER, POSE_R_SHOULDER = 11, 12
POSE_L_WRIST, POSE_R_WRIST = 15, 16
LH_WRIST, RH_WRIST = 33, 54

# PoseSelect preset "mediapipe_holistic_minimal_27"
MINIMAL_27 = [0, 2, 5, 11, 12, 13, 14, 33, 37, 38, 41, 42, 45, 46, 49, 50, 53, 54, 58, 59, 62, 63, 66, 67, 70, 71, 74]
# "shoulder_mediapipe_holistic_minimal_27": nodes 3,4 of MINIMAL_27 == pose 11,12
SHOULDER_NODES_27 = (3, 4)
