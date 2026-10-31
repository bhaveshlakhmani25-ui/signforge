# Extractor comparison and INCLUDE checks (redesign brief, step 0)

Run on 31 Oct 2026. Every number below was measured. None is an estimate.

## Question

Recordings made in the app are extracted in the browser. The INCLUDE import was extracted in Python. If the two extractors disagree, a model trained on INCLUDE would judge app recordings unfairly. So: do they produce the same landmarks, and does the model give the same answer on both?

## Setup

| | Browser | Python |
|---|---|---|
| Library | `@mediapipe/tasks-vision` 1.1.0 (the exact copy the app bundles) | `mediapipe` 1.2.0 (`HolisticLandmarker`) |
| Model file | `frontend/public/models/holistic_landmarker.task` | Same file (same SHA-256) |
| Mode | `VIDEO`, a fresh landmarker for each clip | `VIDEO`, a fresh landmarker for each clip |
| Frames | Every frame, by seeking to its middle | Every frame, decoded in order with OpenCV |

- **Clips:** 18 from the INCLUDE Greetings frozen test split, 2 per sign for all 9 signs, 1920×1080 at 25 fps.
- **Model:** run #4, a GRU trained on the INCLUDE train split, temperature T = 2.80.
- **Scripts:** the comparison scripts are throwaway. The remuxed videos were deleted afterwards and nothing was saved to the database.

## Results

| Measure | Result |
|---|---|
| Frame counts | Identical for all 18 clips |
| Body part detected in both extractors | Pose 100%, left hand 99.7%, right hand 97.7% of frames |
| Pose x/y difference | 0.0032 of the image width or height on average (about 6 px at 1920 wide) |
| Hand labelled as the other side | 0% of frames. The left-hand slot holds the same physical hand in both. |
| Difference at model input (30×27×2, normalised) | 0.126 mean absolute |
| For scale: the same sign, two different INCLUDE clips | 0.349 mean absolute |
| Same top-1 prediction | **16 of 18** (89%) |
| Mean difference in calibrated confidence | 0.042 |
| Right answer (matches the dataset label) | Python 9/18, browser 10/18 |

## What this means

- The two extractors agree closely on landmarks: sub-percent coordinate differences and no hand swaps.
- At the model input the difference is about a third of the natural variation between two clips of the same sign. That isn't negligible.
- In 2 of 18 clips the extractor alone changed the predicted sign. Both were clips the model was unsure about.
- **For `/predict` (step 4):** a confidence near the `VERIFY_MIN_CONF` threshold (0.70) can change with the extractor. Confidences within about ±0.05 of the threshold should go to human review, not be auto-accepted.

## Not covered

- **Live capture is sampled differently.** The app's Capture page extracts frames while the video plays (about 16 fps on the team's webcam), not every frame. That adds a sampling difference on top of what was measured here. The model resamples everything to 10 fps, which should shrink it, but this was not measured.
- **A different camera and signer** (team recordings versus INCLUDE) is a separate and probably larger shift. Team recordings are 1280×720, the same 16:9 shape as INCLUDE. This comparison cannot measure that shift. Team-clip match scores in step 6 will show it.
- **Small sample:** 18 clips. The 16/18 agreement has a wide uncertainty range.

## INCLUDE checks

| Check | Result |
|---|---|
| Licence | CC BY 4.0 (Zenodo record 4010759). Attribution: Sridhar et al., ACM MM 2020. Recorded in every imported sample. |
| Signer IDs | None in the files. Clips are named `MVI_xxxx` by the camera. |
| Recording sessions | File numbers come in runs of 3–4 consecutive numbers per sign, which looks like one recording session each. The split holds out whole sessions per sign, so near-identical repeats never sit in both train and test. Signer identity is still unknown, so results are not signer-independent. |
| Official train/test CSVs | Not in the Greetings zips. The README says a `Train_Test_Split` folder ships in one of the other category zips. |
