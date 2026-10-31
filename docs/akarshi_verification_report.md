# SIGNFORGE - Akarshi Dataset Work Verification Audit

**Auditor:** Independent Technical Verification (for Akarshi Dwivedi)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Repository Working Directory:** `c:\Users\Renu Dwivedi\Desktop\hackathon\signforge-main`  
**Scope:** Independent verification of INCLUDE dataset preparation, licence research, extractor benchmarking, manifests, database records, acceptance testing, and pitch readiness.

---

## Task Audit Table

| Assigned task | Current status | Evidence | Missing work | Action |
|:---|:---:|:---|:---|:---|
| **1. INCLUDE Archive Verification** | **COMPLETE** | 3 ZIPs in `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\` (3.11 GB, 298 clips, 0 corrupted) | None | Archives safely preserved locally |
| **2. Subset Extraction (15 Signs / 45 Clips)** | **COMPLETE** | 45 `.MOV` clips in `dataset/INCLUDE/Dates_and_Time/videos/` (15 signs x 3 clips) | None | Preserved under Privacy-by-Pose (git-ignored) |
| **3. Canonical Landmark Generation** | **COMPLETE** | 45 `.npz` files in `dataset/INCLUDE/.../landmarks/` & `data/processed/1/` (shape `(T,75,3)`, float32, 0 NaNs/Infs) | None | Verified canonical `mp-holistic-75-xyz-v1` format |
| **4. Manifest Generation** | **COMPLETE** | `data/include/manifest.json` (45 items, 14 metadata fields, valid JSON) | Signer IDs need explicit unverified label | Update `signer_verified: false` and add pseudonym notes |
| **5. Database Ingestion (`signforge.db`)** | **COMPLETE** | `backend/signforge.db` (45 samples IDs #92-#130, #132-#137, source `external_dataset`) | None | Total samples 136 (91 demo_fixture + 45 external_dataset) |
| **6. Automated Technical QC** | **COMPLETE** | 44/45 passed (97.8%); Sample #124 (`DT_033`, `YEAR`) correctly flagged for hand-side mismatch | Align Sample #124 DB review_status to `needs_recapture` | Prevent inclusion in model training |
| **7. Licence & Legal Provenance** | **COMPLETE** | Verified CC-BY-4.0 from primary Zenodo REST API (`zenodo_meta.json`); `docs/include_provenance.md` created | None | Clarified Zenodo Concept DOI vs ACM MM '20 paper DOI |
| **8. Extractor Comparison (CPU vs WASM)** | **COMPLETE** | `docs/extractor_comparison.md` (measured 11.7 FPS Python vs 25-30 FPS WASM, delta < 0.008) | None | WASM in-browser extractor certified compatible |
| **9. Acceptance & Regression Testing** | **COMPLETE** | `scripts/test_end_to_end.py` (6/6 workflows passed, 100%), `pytest` (41/41 passed in 28.29s) | None | Verified DB state clean after test teardown |
| **10. Recording-Day Preparation** | **PARTIALLY COMPLETE** | `docs/recording_day_checklist.md` with 10 signs x 4 signers matrix and consent protocols | Physical in-person recording session not yet held | Conduct recording session; tag team recordings as `team_demo` |
| **11. Deaf Community / Native Signer Review** | **NOT STARTED** | Review pipeline operational mechanically (`ReviewEvent` DB records verified) | Formal native Deaf ISL signer review not yet conducted | Schedule community feedback post-hackathon; keep non-native disclaimer |
| **12. Multi-Seed Benchmark Evaluation** | **BLOCKED** | UI reads `benchmark.sample.json` (`is_demo: true`); mock state transparently disclosed | Multi-seed evaluation harness not run on INCLUDE data | Ruben to run harness with random stratified clip splits; do not claim active learning beats random |
| **13. OpenHands DPC Transfer Learning** | **BLOCKED** | Endpoint `/api/models/transfer-learn` explicitly returns `blocked_not_verified` | Upstream ST-GCN weights require custom GCN runtime | Keep documented as blocked / future work |
| **14. Pitch Evidence Alignment** | **COMPLETE** | `docs/pitch_evidence.md`, `docs/demo_script.md`, `docs/updated_pitch_content.md` | Rehearsal of 2-minute live demo | Practice live walkthrough sticking strictly to verified facts |

---

## 1. Verified Completed Tasks

The following tasks have been independently executed, inspected against disk and database state, and verified:

1. **Three-Archive Download & Integrity Audit:**
   - Located all three category ZIP archives on disk at `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\`:
     - `Days_and_Time_1of3.zip` (1,154,646,310 bytes)
     - `Days_and_Time_2of3.zip` (1,145,809,796 bytes)
     - `Days_and_Time_3of3.zip` (813,412,137 bytes)
     - Total archive size: **3,113,868,243 bytes (~2.90 GB)** containing 298 video clips.
   - Verified archive integrity and readable zip headers with zero file corruption.
2. **Selective Subset Extraction (15 Signs / 45 Clips):**
   - Extracted 45 video clips across 15 distinct signs (3 clips per sign) into `dataset/INCLUDE/Dates_and_Time/videos/`.
   - Adhered strictly to the 10-20 signs constraint, avoiding full 56.8 GB download and avoiding extracting all 298 videos.
3. **Canonical Feature Generation (`mp-holistic-75-xyz-v1`):**
   - Generated 45 `.npz` feature tensors in `dataset/INCLUDE/Dates_and_Time/landmarks/` and copied to `data/processed/1/{sample_id}.npz`.
   - Validated array shapes `(T, 75, 3)` with 100% `float32` precision, **0 NaNs**, and **0 Infs**.
4. **Database Ingestion as `external_dataset`:**
   - Ingested 45 samples into `signforge.db` strictly under `source="external_dataset"`.
   - Zero mixing with `demo_fixture` data (91 synthetic samples remain isolated).
   - Deduplication verified: re-running import skips all 45 samples via SHA-256 fingerprinting.
5. **Manifest Generation (`data/include/manifest.json`):**
   - Validated JSON structure with all 14 required fields, mapping each sample to its original filename, landmark path, and licence terms.
6. **Automated Technical Quality Control:**
   - 44 of 45 samples passed automated heuristics.
   - Identified and diagnostically traced the single flagged sample (`DT_033`, `YEAR`).
7. **Empirical Extractor Comparison (`docs/extractor_comparison.md`):**
   - Benchmarked identical video clips (`DT_001`, `DT_004`, `DT_007`) comparing Python CPU (11.7 FPS average) against in-browser WebAssembly SIMD (25-30 FPS live, ~32-40 ms/frame).
   - Verified cross-pipeline feature topology compatibility (mean Euclidean delta < 0.008).
8. **End-to-End Acceptance Testing:**
   - Executed `scripts/test_end_to_end.py` with 100% pass across all 6 workflows (loading, corpus view, capture, review, active learning ranking, and zipped export).
   - Executed full backend pytest suite (`pytest backend/tests/`): **41 passed in 28.29s**.
   - Verified that test sample creation and subsequent deletion (`DELETE /api/samples/{id}`) left zero lingering test data in the production database.

---

## 2. Tasks Completed but Not Independently Verified

1. **Multi-Person Live Recording Day:**
   - The checklist, participant coordination matrix, and consent/withdrawal protocols are documented in [`docs/recording_day_checklist.md`](file:///c:/Users/Renu%20Dwivedi/Desktop/hackathon/signforge-main/docs/recording_day_checklist.md).
   - However, the actual physical recording session with all four team members recording all 10 signs has not taken place yet.
2. **Deaf Community / Native Signer Review:**
   - The human review pipeline is verified mechanically (`ReviewEvent` records role tags properly in DB).
   - However, no native Deaf ISL signer has reviewed the 45 INCLUDE clips within this session; reviews currently logged are team test entries.

---

## 3. Tasks Not Done / Blocked

1. **Multi-Seed Benchmark Generation (`public/benchmark/benchmark.json`):**
   - The `/benchmark` page currently reads `benchmark.sample.json` (explicitly flagged `is_demo: true`).
   - Ruben's offline evaluation harness comparing Ranker vs. Balanced vs. Random on the 15 INCLUDE signs has not been executed yet. **We must not claim active learning beats random collection until this harness produces real logs.**
2. **Transfer Learning Checkpoint Compatibility:**
   - The OpenHands DPC ST-GCN transfer learning pipeline is explicitly marked **Blocked / Not Verified** in the API and UI.

---

## 4. Data Integrity Problems & Audit Findings

During the independent audit, three critical discrepancies were uncovered:

### Finding 1: Signer IDs are Assigned / Inferred, NOT Ground-Truth
* **Investigation:** The raw category ZIP archives from Zenodo (`Days_and_Time_1of3.zip`, `2of3.zip`, `3of3.zip`) contain **only video files** (`.MOV` and `.MP4`). There is no signer mapping CSV or metadata file included in these category archives.
* **Root Cause:** In our extraction scripts (`extract_include_dates_and_time.py`, `extract_include_part2.py`, `extract_include_part1.py`), signer IDs were assigned synthetically using modulo 4 rotation:
  ```python
  "signer_id": f"INCLUDE-S{(idx % 4) + 1:02d}"
  ```
* **Impact & Policy:**
  > [!WARNING]
  > `INCLUDE-S01`, `INCLUDE-S02`, `INCLUDE-S03`, and `INCLUDE-S04` are **unverified synthetic pseudonyms**.  
  > They **CANNOT be used to claim true signer-independent evaluation or signer-split cross-validation**.  
  > The manifest and documentation must explicitly label them as assigned pseudonyms.

### Finding 2: Flagged QC Sample #124 Has Inconsistent Review Status in Database
* **Investigation:** Sample #124 (`DT_033`, `YEAR`) failed automated technical QC (`qc_passed=0` in DB due to hand-side mismatch and dropout). However, during bulk ingestion, its database field `review_status` was set to `"approved"`.
* **Impact:** While `backend/app/api/models.py` safely filters by `Sample.qc_passed == True` (so #124 is excluded from model training), having `review_status="approved"` on a flagged sample is contradictory.
* **Remedy:** Sample #124's review status should be updated to `"needs_recapture"` in `signforge.db` to align with QA documentation.

### Finding 3: Publication DOI vs. Dataset DOI Discrepancy
* **Investigation:** `10.1145/3394171.3413528` is the **ACM Multimedia 2020 publication DOI** for the conference paper. The **Zenodo dataset repository record** is `4010759` (concept DOI `10.5281/zenodo.4010758`).
* **Impact:** Previous reports merged the two into a single "DOI" citation.
* **Remedy:** Both DOIs are now clearly separated and documented.

---

## 5. Signer Identity Status

| Signer Identifier | Source Status | Assignment Mechanism | Permitted Usage | Prohibited Usage |
|:---|:---:|:---|:---|:---|
| `INCLUDE-S01` | **UNVERIFIED** | Synthetic modulo rotation (`idx % 4 == 0`) | Category grouping demonstration only | **Do NOT use for signer-independent splits** |
| `INCLUDE-S02` | **UNVERIFIED** | Synthetic modulo rotation (`idx % 4 == 1`) | Category grouping demonstration only | **Do NOT use for signer-independent splits** |
| `INCLUDE-S03` | **UNVERIFIED** | Synthetic modulo rotation (`idx % 4 == 2`) | Category grouping demonstration only | **Do NOT use for signer-independent splits** |
| `INCLUDE-S04` | **UNVERIFIED** | Synthetic modulo rotation (`idx % 4 == 3`) | Category grouping demonstration only | **Do NOT use for signer-independent splits** |

---

## 6. Licence and DOI Status

* **Licence Name:** Creative Commons Attribution 4.0 International (**CC-BY-4.0**)
* **Licence Status:** **CONFIRMED FROM PRIMARY SOURCE**
* **Primary Evidence:** Verified directly from official Zenodo REST API metadata (`zenodo_meta.json` from `https://zenodo.org/api/records/4010759`):
  ```json
  "license": {"id": "cc-by-4.0"}
  ```
* **Dataset Identifiers:**
  - **Zenodo Record URL:** `https://zenodo.org/records/4010759`
  - **Zenodo Record ID:** `4010759` (Concept: `4010758`)
  - **Zenodo Concept DOI:** `10.5281/zenodo.4010758`
  - **Publication DOI:** `10.1145/3394171.3413528` (ACM MM '20 paper)
* **Attribution Requirement:** Mandatory citation of Sridhar et al. (ACM MM '20).
* **Commercial Use:** Allowed by CC-BY-4.0; restricted by SIGNFORGE ethics policy pending Deaf community consultation.

---

## 7. Manifest Validation Result (`data/include/manifest.json`)

* **JSON Validation:** Valid UTF-8 JSON.
* **Total Samples:** Exactly 45 entries.
* **Distinct Classes:** Exactly 15 classes (`AFTERNOON`, `EVENING`, `HOUR`, `MINUTE`, `MONTH`, `MORNING`, `NIGHT`, `SECOND`, `SUNDAY`, `TIME`, `TODAY`, `TOMORROW`, `WEEK`, `YEAR`, `YESTERDAY`).
* **Source Type:** 100% `external_dataset`. Zero `demo_fixture` or `captured` records.
* **File Existence:** All 45 referenced `.MOV` videos and all 45 `.npz` feature files exist on disk.
* **QC Flag Identification:** Sample #124 (`DT_033`, `YEAR`) is explicitly marked with `qc_passed: false`.

---

## 8. Database Validation Result (`backend/signforge.db`)

* **Total Samples in Database:** 136 samples
  - `demo_fixture`: 91 samples (IDs #1 to #91)
  - `external_dataset`: 45 samples (IDs #92 to #130, #132 to #137)
* **Duplicate Records:** 0 duplicate sample records.
* **QC Passed in DB:** 44 samples (`qc_passed == 1`).
* **QC Failed in DB:** 1 sample (`qc_passed == 0`, Sample #124).
* **Model Training Isolation:** Confirmed that `backend/app/api/models.py` queries `select(Sample).where(Sample.qc_passed == True)`, ensuring flagged samples are never fed into classifier training.

---

## 9. Extractor Comparison Status

* **Status:** **EMPIRICALLY MEASURED & COMPLETE**
* **Documentation:** [`docs/extractor_comparison.md`](file:///c:/Users/Renu%20Dwivedi/Desktop/hackathon/signforge-main/docs/extractor_comparison.md)
* **Key Measured Findings:**
  1. *Speed:* Python MediaPipe CPU achieves **11.7 FPS** batch processing. Browser WASM achieves **25-30 FPS** live execution (~32-40 ms/frame).
  2. *Quantization Variance:* Float16 WASM vs Float32 Python introduces mean Euclidean delta < 0.008 (negligible after shoulder normalization).
  3. *Missing Joint Topology:* Both pipelines produce identical 75-point vectors (`0..32` pose, `33..53` left hand, `54..74` right hand) with zero-filled non-detections.
* **Compatibility Recommendation:** **COMPATIBLE**.

---

## 10. Acceptance Test Results

* **Automated Unit & Integration Tests:**  
  `pytest backend/tests/ -v`: **41 passed, 0 failed, 0 skipped** (28.29s).
* **End-to-End Acceptance Workflows:**  
  `scripts/test_end_to_end.py`: **6 / 6 passed (100%)**:
  1. Dataset loading: PASSED
  2. Corpus display & replay: PASSED
  3. Consented capture: PASSED
  4. Human review: PASSED
  5. Active learning ranking: PASSED
  6. Model-ready export: PASSED
* **Production Data Protection:**  
  Test sample #138 was created during the test run and immediately removed via `DELETE /api/samples/138`. Inspection of `signforge.db` confirmed that all 136 production samples remain untouched.

---

## 11. Exact Next Actions

### For Akarshi (Data & QA Lead):
1. **Annotate Signer IDs in Manifest:** Update [`data/include/manifest.json`](file:///c:/Users/Renu%20Dwivedi/Desktop/hackathon/signforge-main/data/include/manifest.json) to set `"signer_verified": false` and add a note in `provenance_notes` explaining that signer codes are assigned pseudonyms.
2. **Update Sample #124 Review Status:** Update `signforge.db` so Sample #124 (`YEAR`) has `review_status="needs_recapture"`.
3. **Conduct 2-Minute Demo Rehearsal:** Practice the live walkthrough using [`docs/demo_script.md`](file:///c:/Users/Renu%20Dwivedi/Desktop/hackathon/signforge-main/docs/demo_script.md) ensuring all citations reference only the verified 15 signs / 45 samples.

### For Tashvi (Backend Lead):
1. **Confirm External Dataset Loader Integration:** Verify that `import_include.py` and `export.py` remain the canonical handoff endpoints.
2. **Model Training Pool Check:** Ensure future training routes support `pool="external"` so real INCLUDE samples can train the baseline GRU without mixing with `demo_fixture`.

### For Ruben (Evaluation Lead):
1. **Execute Real Benchmark Harness:** Run the multi-seed evaluation script against the 45 INCLUDE samples to generate real accuracy curves for `public/benchmark/benchmark.json`.
2. **Avoid Signer Splits on INCLUDE Subset:** Because signer IDs are unverified modulo assignments, Ruben must configure the evaluation harness to use **random stratified clip splits** rather than signer-independent splits for this dataset.

---

## 12. Sign-off and Quality Certification

**Role:** Data, QA & Pitch Lead (Team Claude's Clan)  
**Name:** Akarshi Dwivedi  
**Status:** **APPROVED WITH CAVEATS**  

### Certification Statement:
> "I have verified that all 45 imported samples originate from the official Zenodo INCLUDE dataset under CC-BY-4.0 licensing, have been properly extracted into canonical `(T,75,3)` landmark representations, and are cleanly isolated in `signforge.db` under `source='external_dataset'`. Automated QC correctly identified 1 anomalous sample (#124), and all 41 backend tests and 6/6 end-to-end integration workflows pass.  
>  
> **Caveats for Pitch and Evaluation:**  
> 1. Signer IDs `INCLUDE-S01` through `INCLUDE-S04` are synthetic modulo rotation pseudonyms and must not be used to claim signer-independent evaluation.  
> 2. The active learning benchmark numbers on `/benchmark` remain mock fixtures (`is_demo: true`) until Ruben completes the offline multi-seed harness on the 45 real clips. We will make zero unsubstantiated claims during the pitch."
