# SIGNFORGE — Additional INCLUDE Import Proposal & Benchmark Protection Plan

**Author:** Akarshi Dwivedi (Data, QA & Pitch Lead)  
**Date:** 2026-11-01  
**Project:** SIGNFORGE  
**Repository Directory:** `c:\Users\Renu Dwivedi\Desktop\hackathon\signforge-main`  
**Input Archives:** `People_1of5.zip` (1.24 GB) and `People_2of5.zip` (1.17 GB)  
**Status:** **PROPOSAL ONLY — PENDING USER APPROVAL (NO DATA IMPORTED)**

---

## 1. Executive Summary & Context

* **Existing Dataset State:**
  - Category: `Dates_and_Time`
  - Active Classes: **15 unique sign classes**
  - Active Samples: **45 samples** (3 samples per class)
  - Database Source: `source="external_dataset"` in `backend/signforge.db`
  - Canonical Manifest: [`data/include/manifest.json`](file:///c:/Users/Renu%20Dwivedi/Desktop/hackathon/signforge-main/data/include/manifest.json)
  - Evaluation Constraint: **10 to 20 signs target** for the hackathon baseline.
* **New Data Available:**
  - Category: `People` (Signs 58 through 67)
  - Total Signs: **10 distinct classes** (`SON`, `DAUGHTER`, `MOTHER`, `FATHER`, `PARENT`, `BABY`, `MAN`, `WOMAN`, `BROTHER`, `SISTER`)
  - Total Videos: **201 video clips** (~2.51 GB uncompressed)
  - Overlap with Existing Signs: **0 signs** (100% disjoint domain).

---

## 2. Evaluation of Strategic Options

Our project constraint mandates keeping the active experiment within **10–20 signs**. We evaluated three strategic paths:

### Option A: Add More Samples to Existing Signs
* **Description:** Add additional clips to the 15 existing `Dates_and_Time` signs to deepen sample coverage (e.g. from 3 clips to 5+ clips per sign).
* **Feasibility:** **INFEASIBLE.**
* **Reason:** The two new archives belong entirely to the `People` category. They contain **zero clips for any of the 15 Dates & Time signs**. Option A cannot be executed with these archives.

---

### Option B: Select 5 New Signs to Reach the 20-Sign Upper Bound
* **Description:** Import a balanced subset of **5 new signs** from the `People` category (3 clips per sign = 15 clips), expanding the total corpus from 15 to exactly **20 signs** (60 clips total).
* **Proposed Candidate Signs (5 Core Family Concepts):**
  1. `FATHER` (Sign 61) — 3 clips
  2. `MOTHER` (Sign 60) — 3 clips
  3. `BROTHER` (Sign 66) — 3 clips
  4. `SISTER` (Sign 67) — 3 clips
  5. `BABY` (Sign 63) — 3 clips
* **Advantages:**
  - Hits the exact upper ceiling of our 20-sign target.
  - Demonstrates cross-category scalability (Temporal + Kinship/People vocabulary).
* **Disadvantages & Risks:**
  - **Breaks Domain Coherence:** Merges two distinct lexical domains (15 calendar concepts + 5 family concepts) into a single corpus.
  - **Invalidates Trained Models:** A 15-class classifier cannot predict 20 classes. Baseline GRU weights (`run_*.pt`) would need full retraining with a 20-dimensional output layer.
  - **Expands the Frozen Test Set:** Requires adding 5 test clips, changing test set cardinality from 15 to 20.
  - **Risk to Pitch Stability:** Introduces new variables just before hackathon judging.

---

### Option C: Keep As Inspected & Staged, But Do NOT Import (RECOMMENDED)
* **Description:** Maintain the existing 15-sign Dates & Time dataset as the **frozen primary benchmark** for the hackathon demonstration. Keep `People_1of5.zip` and `People_2of5.zip` fully inspected, checksummed, and documented as a **verified Turn-Key Expansion Pool**.
* **Advantages:**
  - **Zero Benchmark Disruption:** Ruben's active learning evaluation harness runs cleanly against the existing 15-sign frozen test set.
  - **Domain Purity:** The corpus remains a semantically focused, linguistically coherent module (`Dates and Time` ISL vocabulary).
  - **Audit Integrity:** Preserves the verified 45-sample, 44-passed QC baseline with zero risk of regressions or collisions.
  - **Honest Narrative for Pitch Deck:** "We demonstrated our active-learning pipeline on a focused 15-sign temporal corpus, and independently verified and staged 10 additional kinship signs for immediate post-pitch expansion."
* **Recommendation:** **OPTION C IS STRONGLY RECOMMENDED.**

---

## 3. Detailed Technical Blueprint for Option B (Turn-Key Expansion)

If the user explicitly approves expanding the corpus to 20 signs, the following exact specification will be executed:

### A. Sample Selection Matrix (15 Additional Clips)

| New Sign Class | Canonical Gloss | Archive Source | Source Video Filename | Assigned Staged Filename | Sample ID Range |
|:---|:---|:---:|:---|:---|:---:|
| `60. Mother` | `MOTHER` | `People_1of5.zip` | `People/60. Mother/MVI_3760.MOV`<br>`People/60. Mother/MVI_3761.MOV`<br>`People/60. Mother/MVI_3762.MOV` | `PEOPLE_001_MVI_3760.MOV`<br>`PEOPLE_002_MVI_3761.MOV`<br>`PEOPLE_003_MVI_3762.MOV` | `#139`–`#141` |
| `61. Father` | `FATHER` | `People_1of5.zip` | `People/61. Father/MVI_3763.MOV`<br>`People/61. Father/MVI_3764.MOV`<br>`People/61. Father/MVI_3765.MOV` | `PEOPLE_004_MVI_3763.MOV`<br>`PEOPLE_005_MVI_3764.MOV`<br>`PEOPLE_006_MVI_3765.MOV` | `#142`–`#144` |
| `63. Baby` | `BABY` | `People_2of5.zip` | `People/63. Baby/MVI_3769.MOV`<br>`People/63. Baby/MVI_3770.MOV`<br>`People/63. Baby/MVI_3771.MOV` | `PEOPLE_007_MVI_3769.MOV`<br>`PEOPLE_008_MVI_3770.MOV`<br>`PEOPLE_009_MVI_3771.MOV` | `#145`–`#147` |
| `66. Brother` | `BROTHER` | `People_2of5.zip` | `People/66. Brother/MVI_3778.MOV`<br>`People/66. Brother/MVI_3779.MOV`<br>`People/66. Brother/MVI_3780.MOV` | `PEOPLE_010_MVI_3778.MOV`<br>`PEOPLE_011_MVI_3779.MOV`<br>`PEOPLE_012_MVI_3780.MOV` | `#148`–`#150` |
| `67. Sister` | `SISTER` | `People_2of5.zip` | `People/67. Sister/MVI_3782.MOV`<br>`People/67. Sister/MVI_3783.MOV`<br>`People/67. Sister/MVI_3784.MOV` | `PEOPLE_013_MVI_3782.MOV`<br>`PEOPLE_014_MVI_3783.MOV`<br>`PEOPLE_015_MVI_3784.MOV` | `#151`–`#153` |

### B. Storage & Compute Requirements
* **Video Storage:** 15 clips = ~188.4 MB in `dataset/INCLUDE/People/videos/`. (Git-ignored under Privacy-by-Pose).
* **Landmark Storage:** 15 `.npz` files = ~530 KB in `dataset/INCLUDE/People/landmarks/` and `data/processed/1/`.
* **Feature Extraction Runtime:** 15 clips × 65 frames × 85 ms/frame (MediaPipe CPU) = **~82 seconds total processing time**.

### C. Collision Protection Strategy
To eliminate any risk of collision with the 8 recycled camera filenames (`MVI_5071.MOV` ... `MVI_5079.MOV`):
* All extracted clips will be prefixed with `PEOPLE_xxx_`.
* Database records will store `raw_filename` with category tags: `People/60. Mother/MVI_3760.MOV`.
* Features will be stored using unique sample database IDs: `data/processed/1/{sample_id}.npz`.

### D. Governance & Metadata Ingestion Rules
* `source`: `external_dataset`
* `consent_id`: `1` (Project default external dataset consent covering CC-BY-4.0 terms)
* `signer_verified`: `false` (Mandatory: labeled as assigned synthetic pseudonyms)
* `signer_assignment_method`: `modulo_4_rotation`
* `provenance_note`: `"INCLUDE / Zenodo 4010759 / CC-BY-4.0 / People / {clip_code}"`

---

## 4. Benchmark & Split Impact Analysis

| Dimension | Current Baseline (Option C) | Proposed Expansion (Option B) | Technical Consequence |
|:---|:---:|:---:|:---|
| **Class Count** | 15 classes | 20 classes (+5 classes) | Requires resizing model architecture |
| **Total Clips** | 45 clips | 60 clips (+15 clips) | Expands dataset by 33.3% |
| **Train Split** | 30 clips (2/class) | 40 clips (2/class) | Increases training diversity |
| **Frozen Test Split** | 15 clips (1/class) | 20 clips (1/class) | **Invalidates current benchmark baseline** |
| **Validation Split** | Optional val clips | Optional val clips | No negative impact |
| **Existing Checkpoints** | `run_*.pt` valid (15 outputs) | **INVALIDATED** | Must retrain GRU classifier from scratch |
| **Manifest State** | `data/include/manifest.json` intact | Requires manifest schema update | Hand-off files must be regenerated |

---

## 5. Strict Safeguards (Benchmark Protection Plan)

Until the user issues explicit approval:

1. **Zero Database Alterations:** No records will be added to `signforge.db`. Existing samples #92 through #137 remain completely untouched.
2. **Zero File Overwrites:** `data/include/manifest.json` remains read-only.
3. **Zero Video Extractions:** The two ZIP files (`People_1of5.zip`, `People_2of5.zip`) remain sealed in `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\`.
4. **Zero Model Invalidation:** The existing 15-class classifier weights and frozen test set remain protected.
5. **Separation Guarantee:** No external data will ever mix with `demo_fixture` or user-captured `real` data.
