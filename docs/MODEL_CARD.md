# Model card: checkpoint spike (Milestone 1)

**Status: a from-scratch baseline exists; transfer learning is NOT verified.** Nothing in this file is a performance result; runs and their metrics live in the app (Models & Evaluation).

## Baseline (Milestone 3)
- GRU (hidden 128) over the shared `model_input()` features: 10 fps, stretched to 30 frames, 27 points × x/y, OpenHands shoulder normalisation. Random initialisation; no pretrained weights.
- Full-batch Adam, 300 epochs, lr 3e-3, weight decay 1e-4, seed 0. Changed on 31 Oct 2026 from hidden 64 / 80 epochs / lr 1e-3, which underfit INCLUDE Greetings (train accuracy 0.65). The new values were chosen on the INCLUDE validation split over 3 seeds; no test split was used for tuning. Run #3 (old settings, 28% test accuracy) and run #4 (new settings, 53%) are both kept.
- External pool (INCLUDE): the frozen split holds out one whole recording session per sign as test and one as validation. Temperature scaling is fitted on validation and judged on test (ECE, NLL). Run #4: T = 2.80, test ECE 0.42 → 0.20, so the reliability check (ECE ≤ 0.10) **failed**.
- Splits: the first run freezes the test set. ≥3 signers → hold out one whole signer (the one covering the most signs); otherwise a stratified random clip split, labelled *not signer-independent*. New samples only join train.
- Eligibility: real pool = approved + QC-passed captures; demo pool = QC-passed DEMO DATA not rejected/sent back by a reviewer. The two pools are never mixed.
- Known limit: on DEMO DATA the baseline scores 100% because the synthetic signs differ only by a sine-wave frequency. That proves the pipeline runs, nothing more.

## Chosen candidate: AI4Bharat OpenHands, self-supervised DPC (ST-GCN)
| Question (CLAUDE.md §8.2) | Answer | How we know |
|---|---|---|
| Downloadable today? | Yes: `github.com/AI4Bharat/OpenHands/releases/download/checkpoints_v1/raw_dpc.zip`, 36,146,200 B, sha256 `9cee4938…53d4`, contains `epoch=499-step=308499.ckpt` (PyTorch Lightning 1.4.1). Re-checked 2026-10-22: HTTP 200. | downloaded and inspected with a stub unpickler (no code from the file executed) |
| License | Code: Apache-2.0 (repo LICENSE). Weights: published in the same repo's releases; no separate weight license. Pretraining data: Indian SL videos scraped from YouTube per the OpenHands paper, so data provenance is weak. Repo says it is **no longer maintained** (last push 2023-03). | GitHub API, README |
| What does it learn? | Self-supervised dense predictive coding on Indian SL pose sequences: an ST-GCN encoder (10 blocks, 64→256 channels, 3.62 M params incl. GRU) plus GRU aggregator. No class labels, so any class set can get a new head. | tensor shapes in the checkpoint match `examples/ssl/pretrain_dpc_stgcn.yaml` |
| Expected keypoints | 27 points selected from the 75-point MediaPipe Holistic layout (33 pose + 21 left hand + 21 right hand; face dropped): indices `[0,2,5,11,12,13,14,33,37,38,41,42,45,46,49,50,53,54,58,59,62,63,66,67,70,71,74]` | `pose_transforms.py` preset `mediapipe_holistic_minimal_27` |
| Face / non-manual features? | **No.** Only nose, eyes, shoulders, elbows and hands. Facial grammar is not represented; this is a known limitation for ISL. | the 27 indices above |
| Coordinates & normalisation | x, y only (2 channels), MediaPipe normalised image coordinates, un-mirrored, y down. Missing parts zero-filled, then clip-level centre = mean shoulder midpoint, scale = 1 / mean shoulder distance. | OpenHands source; checkpoint BatchNorm running means put shoulders at x ≈ ±0.49 |
| Tensor shape | `(N, C=2, T, V=27)` per window of 10 frames; DPC pretraining: 7 windows, every 3rd frame | config + `STModel.forward` |
| Live extractor compatible? | **Partly.** OpenHands used legacy `mp.solutions.holistic` (removed in mediapipe ≥ 0.10.31, no Python 3.14 wheels). We use `@mediapipe/tasks-vision@1.1.0` HolisticLandmarker: same topology and coordinate convention, different model version. Distribution drift must be measured. | PyPI wheel tags; MediaPipe docs |
| Task compatible? | Isolated signs, short clips: yes. | |

### Open assumptions (each needs a test before we claim compatibility)
- Browser `leftHandLandmarks` = signer's left hand. **Partly confirmed (2026-10-30)** on 5 real webcam clips (#92–96, sign HELLO, 2 signers): the stored pose is un-mirrored (signer's left shoulder at x≈0.7, image right) and the right-hand slot's wrist sat nearest pose wrist 16 in 100% of frames. The left hand was never detected in these clips (one-handed sign, or a detection gap; we can't tell yet), so the left slot is still unconfirmed. QC keeps checking every sample.
- Source frame rate of the pretraining videos is undocumented; we sample at 10 fps (`TARGET_FPS`).
- Feature drift between Tasks and legacy Holistic: to be measured against the checkpoint's BatchNorm statistics.

### Tests required before the transfer path is enabled (Milestone 4)
Strict state-dict load (only the DPC prediction head unused); graph matrix equals the documented edge list; forward shape `(B·W,2,10,27)→(B·W,256)`; BatchNorm input layout check; normalisation unit tests (already passing in `tests/test_preprocessing_qc.py`).

## Alternative considered: AI4Bharat INCLUDE
Code MIT, INCLUDE dataset CC-BY-4.0 (Zenodo 4010759). Its weights (wandb links, downloadable 2026-10-22) are **supervised classifiers over INCLUDE's own classes**, built on a different keypoint layout (separate MediaPipe Hands + Pose, x/y). Usable as a reference baseline, but not a general pretrained encoder for our classes without re-extracting features in its layout.

## Citations
OpenHands: Selvaraj et al., *OpenHands: Making Sign Language Recognition Accessible with Pose-based Pretrained Models across Languages*, ACL 2022; https://github.com/AI4Bharat/OpenHands. INCLUDE: Sridhar et al., ACM MM 2020; https://github.com/AI4Bharat/INCLUDE.
