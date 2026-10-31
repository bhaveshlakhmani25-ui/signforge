# INCLUDE Dataset Import Report (`external_dataset`)

**Author:** Aakarshi Dwivedi (Data, QA & Evaluation)  
**Collaborator Handoff:** Tashvi Adhlakha (Backend & Data Ingestion)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Source Type:** `external_dataset`  

---

## 1. Import Summary Statistics (All 3 Archives)

| Metric | Target | Actual Result | Verification Status |
|:---|:---:|:---:|:---:|
| **Source ZIP Files Processed** | 3 | 3 (`Days_and_Time_1of3`, `2of3`, `3of3`) | Verified |
| **Signs Selected** | 10–20 signs | **15 signs** | Verified (within 10–20 target) |
| **Videos Extracted & Processed** | 3 per sign | **45 video clips** | Verified |
| **Landmark Files Generated** | 45 | **45 `.npz` files** | Verified (`mp-holistic-75-xyz-v1`) |
| **Successful Database Imports** | 45 | **45 samples** (`id` #92 to #130, #132 to #137) | Verified in `signforge.db` |
| **Failed Imports** | 0 | **0** | Clean execution |
| **Automated Technical QC Passed** | — | **44 / 45 (97.8%)** | 1 flagged for midline hand crossing |
| **Deduplication Check** | Idempotent | **39 duplicates skipped on re-import** | Verified via SHA-256 hash |
| **Source Type in Database** | `external_dataset` | `external_dataset` | Verified (100% isolated) |

---

## 2. Ingested Sign Classes Inventory (15 Word Signs)

| Sign Label | Source Archive | Sample Count | Signer Representation | Automated QC |
|:---|:---:|:---:|:---:|:---:|
| `SUNDAY` | Part 1 (`1of3`) | 3 | `INCLUDE-S04`, `S01`, `S02` | 3 / 3 Passed |
| `TODAY` | Part 1 (`1of3`) | 3 | `INCLUDE-S01`, `S02`, `S03` | 3 / 3 Passed |
| `TOMORROW` | Part 2 (`2of3`) | 3 | `INCLUDE-S04`, `S01`, `S02` | 3 / 3 Passed |
| `YESTERDAY` | Part 2 (`2of3`) | 3 | `INCLUDE-S03`, `S04`, `S01` | 3 / 3 Passed |
| `WEEK` | Part 2 (`2of3`) | 3 | `INCLUDE-S02`, `S03`, `S04` | 3 / 3 Passed |
| `MONTH` | Part 2 (`2of3`) | 3 | `INCLUDE-S01`, `S02`, `S03` | 3 / 3 Passed |
| `YEAR` | Part 2 (`2of3`) | 3 | `INCLUDE-S04`, `S01`, `S02` | 2 / 3 Passed (1 Flagged) |
| `HOUR` | Part 2 (`2of3`) | 3 | `INCLUDE-S03`, `S04`, `S01` | 3 / 3 Passed |
| `MINUTE` | Part 2 (`2of3`) | 3 | `INCLUDE-S02`, `S03`, `S04` | 3 / 3 Passed |
| `SECOND` | Part 3 (`3of3`) | 3 | `INCLUDE-S02`, `S03`, `S04` | 3 / 3 Passed |
| `MORNING` | Part 3 (`3of3`) | 3 | `INCLUDE-S01`, `S02`, `S03` | 3 / 3 Passed |
| `AFTERNOON` | Part 3 (`3of3`) | 3 | `INCLUDE-S04`, `S01`, `S02` | 3 / 3 Passed |
| `EVENING` | Part 3 (`3of3`) | 3 | `INCLUDE-S03`, `S04`, `S01` | 3 / 3 Passed |
| `NIGHT` | Part 3 (`3of3`) | 3 | `INCLUDE-S02`, `S03`, `S04` | 3 / 3 Passed |
| `TIME` | Part 3 (`3of3`) | 3 | `INCLUDE-S01`, `S02`, `S03` | 3 / 3 Passed |
| **Total** | **All 3 Parts** | **45** | **4 Signers (`S01`..`S04`)** | **44 / 45 Passed** |

---

## 3. Data Governance & Source Separation

```text
signforge.db Samples Breakdown:
├── demo_fixture       : 91 samples (Synthetic sine-wave fixture; excluded from real evaluation)
└── external_dataset   : 45 samples (AI4Bharat INCLUDE Days and Time benchmark samples)
```

1. **Strict Isolation:** `external_dataset` samples are marked with `source="external_dataset"` and are never mixed with `demo_fixture` data.
2. **Privacy-by-Pose:** Raw QuickTime videos (`.MOV`) are preserved locally in `dataset/INCLUDE/Dates_and_Time/videos/` and are excluded from git commits and public exports.
3. **Traceability:** Every sample points to its canonical feature path at `data/processed/1/{sample_id}.npz` and includes its source SHA-256 checksum in `data/include/manifest.json`.

---

## 4. Technical QC Flag Investigation (`DT_033` / `YEAR`)

* **Flagged Codes:** `hand_side_mismatch` (25% frames), `left_hand_dropout` (30%), `right_hand_dropout` (32%).
* **Analysis:** The sign "YEAR" involves the dominant right hand crossing the torso's midline to revolve around the stationary left hand. When the right wrist moves to the left side of the chest, Euclidean heuristics misinterpret the contralateral movement as a flipped webcam.
* **Resolution:** The sample is preserved in the database with `qc_passed=False` and status `needs_recapture`. It provides authentic active-learning training signal to request clearer recording geometry.
