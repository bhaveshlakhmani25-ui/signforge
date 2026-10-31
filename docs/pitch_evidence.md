# SIGNFORGE Pitch Evidence & Empirical Verification Log

**Author:** Aakarshi Dwivedi (Data, QA & Pitch Lead)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Integrity Rule:** Grounded strictly in measured system data. No fabricated benchmark claims or unmeasured accuracy numbers.

---

## 1. Executive Summary

This document serves as the factual evidence base for the SIGNFORGE hackathon pitch deck and demonstration. It categorizes every claim according to its verifiable implementation status, distinguishing live software features from experimental measurements and simulated fixtures.

---

## 2. Evidence Categorization

### A. What is Fully Implemented in Software
* **Consent Gate:** Cryptographically enforced pseudonymous signer registration (`Signer.code` regex `^[A-Z0-9][A-Z0-9-]{1,15}$`) and purpose-specific consent (`ConsentRecord`) blocking capture until active consent is recorded.
* **Privacy-by-Pose In-Browser Extractor:** Client-side MediaPipe Tasks Vision (`holistic_landmarker.task`, 13.7 MB float16 WASM) running in Chrome V8; raw video never leaves the user's browser.
* **Automated Technical Quality Control:** Real-time checks on duration ($0.8\,\text{s} - 8.0\,\text{s}$), missing upper body ($>20\%$), hand dropout ($>30\%$), midline hand-side swap ($>20\%$), and duplicate detection (`feature_sha256`).
* **Human Linguistic Review Pipeline:** Review queue on `/corpus` requiring self-declared reviewer roles (`native_signer`, `deaf_community_member`, `interpreter`, `team_non_signer`). Only native signers count as linguistic validation.
* **Active Learning Ranker:** Live FastAPI endpoint `GET /api/queue?project_id=1` executing:
  $$\text{Priority} = \text{Coverage Gap} + \text{Signer Diversity Gap} + \text{Model Uncertainty}$$
* **Model-Ready Dataset Export:** `GET /api/export` and `/export` interface generating a downloadable `.zip` package containing `manifest.json`, `provenance.md`, and canonical `landmarks/*.npz` files. Raw video is strictly excluded by default.
* **Consent Withdrawal & Sample Erasure:** `POST /api/consents/{id}/withdraw` and `DELETE /api/samples/{id}` with autoincrement ID protection preventing ID reuse.

---

### B. What is Demonstrated Live in the App
* **Corpus Coverage View:** Live breakdown of 23 sign classes in `signforge.db`, showing approved sample counts and signer diversity.
* **Skeletal Motion Replay:** 15 FPS normalized keypoint replay rendered via SVG canvas (`/api/samples/{id}/landmarks`).
* **Interactive Active Learning Guidance:** Real-time prioritization cards with direct "Record this sign" deep-links into the capture interface.
* **Live Export Download:** Immediate client download of `signforge_isl_demo_export.zip` (1.55 MB).

---

### C. What is Ingested from the INCLUDE Dataset
* **Source:** Zenodo Record `4010759` (AI4Bharat / IIT Madras, ACM Multimedia 2020), CC-BY-4.0 licence verified.
* **Category:** Days and Time (ISL).
* **Archives Processed:** `Days_and_Time_2of3.zip` (969.69 MB) and `Days_and_Time_3of3.zip` (813.44 MB) — total 1.78 GB subset, avoiding the 56.8 GB full dataset.
* **Sample Scope:** **39 video clips across 13 unique word signs** (`AFTERNOON`, `EVENING`, `HOUR`, `MINUTE`, `MONTH`, `MORNING`, `NIGHT`, `SECOND`, `TIME`, `TOMORROW`, `WEEK`, `YEAR`, `YESTERDAY`), 3 clips per sign across 4 distinct signers (`INCLUDE-S01` to `INCLUDE-S04`).
* **Source Separation:** Registered in `signforge.db` strictly with `source="external_dataset"`.

---

### D. What Has Been Experimentally Measured

| Metric / Parameter | Experimental Setup | Measured Result | Source Document |
|:---|:---|:---:|:---|
| **Python Extraction Speed** | CPU XNNPACK delegate, 3 test clips (147 frames total) | **11.7 FPS average** (10.2 FPS min, 12.6 FPS max) | `docs/extractor_comparison.md` |
| **Browser WASM Latency** | Chrome V8, WebAssembly SIMD, GPU delegate | **~32–40 ms/frame (25–30 FPS live)** | `docs/extractor_comparison.md` |
| **Extractor Topology Delta** | float16 WASM vs. float32 Python graph | **Mean Euclidean $\Delta < 0.008$** | `docs/extractor_comparison.md` |
| **Technical QC Pass Rate** | 39 real INCLUDE clips evaluated against heuristics | **38 / 39 passed (97.4%)** | `docs/include_import_report.md` |
| **Midline Crossing Flag** | Frame-by-frame analysis of `DT_033` (`YEAR`) | **Swap-R triggered in frames 16–32** | `docs/dataset_integration_verification.md` |
| **Export Bundle Size** | 39 real approved samples compressed with manifest | **1,553,756 bytes (1.55 MB)** | Live test via `GET /api/export` |
| **End-to-End Acceptance** | Automated test suite across 6 lifecycle stages | **100% Pass (6 / 6 workflows)** | `scripts/test_end_to_end.py` |

---

### E. What Remains Incomplete & Honest Disclosures
* **Real Benchmark Comparison Curve:**
  - *Disclosure:* The live `/benchmark` page currently displays `benchmark.sample.json` (explicitly tagged `is_demo: true`). The multi-seed comparative benchmark comparing Ranker vs. Balanced vs. Random on real INCLUDE signs is pending completion by the evaluation pair (Ruben). **We do not claim that the ranker statistically beats random collection on real data until Ruben's final benchmark logs are produced.**
* **Transfer Learning Checkpoint:**
  - *Disclosure:* The OpenHands DPC ST-GCN transfer learning path is explicitly marked **Blocked / Not Verified** in the UI because cross-dataset landmark calibration tests have not been executed.
* **Team Recording Validation:**
  - *Disclosure:* Team demo recordings are non-native signing and are flagged as `team_demo` clips, not linguistically validated ISL.

---

### F. Limitations & System Risks
1. **Facial Expression Absence:** The 75-keypoint schema tracks upper body and hands only. Non-manual grammatical markers (head tilt, eyebrow position, mouth morphemes) are not captured.
2. **Contralateral Hand Occlusion:** Two-handed signs with overlapping trajectories (like `YEAR`) can induce momentary tracking dropouts in 2D monocular cameras.
3. **Hardware Heterogeneity:** Browser WASM performance varies across client hardware; low-end mobile devices without WebAssembly SIMD may experience framerate degradation.
