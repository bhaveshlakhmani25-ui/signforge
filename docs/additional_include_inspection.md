# SIGNFORGE — Additional INCLUDE Archives Inspection Report

**Auditor:** Akarshi Dwivedi (Data, QA & Pitch Lead)  
**Date:** 2026-11-01  
**Project:** SIGNFORGE  
**Repository Directory:** `c:\Users\Renu Dwivedi\Desktop\hackathon\signforge-main`  
**Dataset Directory:** `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset`  
**Scope:** Technical inspection, duplicate cross-check, and compatibility evaluation of two newly downloaded INCLUDE dataset archives (`People_1of5.zip` and `People_2of5.zip`).

---

## 1. Archive Identification & Checksum Verification

Both archives were located in the local dataset directory and verified against official Zenodo Record `4010759` metadata:

| Attribute | Archive 1: `People_1of5.zip` | Archive 2: `People_2of5.zip` |
|:---|:---|:---|
| **Absolute Path** | `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\People_1of5.zip` | `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\People_2of5.zip` |
| **File Size (Bytes)** | **1,327,653,833 bytes** | **1,251,273,463 bytes** |
| **File Size (Binary / GB)** | **1.24 GB** (1,266.15 MiB) | **1.17 GB** (1,193.31 MiB) |
| **Local MD5 Checksum** | `5edbd0af6c5464c4235a09da0ebe47e9` | `037c7b5cebf482b98e166a9c2848c9ee` |
| **Zenodo Expected MD5** | `5edbd0af6c5464c4235a09da0ebe47e9` | `037c7b5cebf482b98e166a9c2848c9ee` |
| **Integrity Verdict** | **100% BIT-FOR-BIT MATCH (Valid)** | **100% BIT-FOR-BIT MATCH (Valid)** |
| **Dataset Category** | `People` (Indian Sign Language INCLUDE) | `People` (Indian Sign Language INCLUDE) |
| **Video Clips Count** | 100 video files (95 `.MOV`, 5 `.MP4`) | 101 video files (96 `.MOV`, 5 `.MP4`) |
| **Sign Classes Count** | 5 distinct signs (Signs 58 to 62) | 5 distinct signs (Signs 63 to 67) |
| **Non-Video / Metadata Files** | **None** (0 CSVs, 0 JSONs, 0 TXT) | **None** (0 CSVs, 0 JSONs, 0 TXT) |

**Total Combined New Storage:** 2,578,927,296 bytes (~2.40 GB archive, ~2.51 GB uncompressed videos across 201 video clips).

---

## 2. Signs Inventory & Available Videos per Sign

The internal directory structure follows the format `People/<SignNumber>. <SignName>/<MVI_xxxx>.<MOV|MP4>`.  
The two archives contain exactly **10 distinct sign classes** with 20–21 clips per class:

| Sign Folder | Canonical Gloss | Archive Source | Total Videos | Video Formats | Uncompressed Size | Filename Range |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| `58. Son` | `SON` | `People_1of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 267.1 MB | `MVI_3753.MOV` ... `MVI_8623.MP4` |
| `59. Daughter` | `DAUGHTER` | `People_1of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 246.9 MB | `MVI_3756.MOV` ... `MVI_8624.MP4` |
| `60. Mother` | `MOTHER` | `People_1of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 232.1 MB | `MVI_3760.MOV` ... `MVI_8625.MP4` |
| `61. Father` | `FATHER` | `People_1of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 248.0 MB | `MVI_3763.MOV` ... `MVI_8626.MP4` |
| `62. Parent` | `PARENT` | `People_1of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 300.1 MB | `MVI_3766.MOV` ... `MVI_8627.MP4` |
| `63. Baby` | `BABY` | `People_2of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 253.4 MB | `MVI_3769.MOV` ... `MVI_8628.MP4` |
| `64. Man` | `MAN` | `People_2of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 233.0 MB | `MVI_3772.MOV` ... `MVI_8629.MP4` |
| `65. Woman` | `WOMAN` | `People_2of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 229.9 MB | `MVI_3775.MOV` ... `MVI_8630.MP4` |
| `66. Brother` | `BROTHER` | `People_2of5.zip` | 21 | 20 `.MOV`, 1 `.MP4` | 263.9 MB | `MVI_3778.MOV` ... `MVI_8631.MP4` |
| `67. Sister` | `SISTER` | `People_2of5.zip` | 20 | 19 `.MOV`, 1 `.MP4` | 240.3 MB | `MVI_3782.MOV` ... `MVI_8632.MP4` |
| **Total** | **10 Classes** | **2 Archives** | **201 Clips** | **191 MOV, 10 MP4** | **2,514.7 MB** | — |

---

## 3. Duplicate Analysis & Collision Investigation

### A. Overlap with Existing 15 Signs
* **Existing Subset Signs (Dates & Time):** `AFTERNOON`, `EVENING`, `HOUR`, `MINUTE`, `MONTH`, `MORNING`, `NIGHT`, `SECOND`, `SUNDAY`, `TIME`, `TODAY`, `TOMORROW`, `WEEK`, `YEAR`, `YESTERDAY`.
* **New Archive Signs (People):** `SON`, `DAUGHTER`, `MOTHER`, `FATHER`, `PARENT`, `BABY`, `MAN`, `WOMAN`, `BROTHER`, `SISTER`.
* **Overlap:** **0 Signs (Disjoint Sets).** The newly downloaded archives contain **entirely new signs** from the "People" category and **zero additional samples for the existing 15 signs**.

### B. Filename Collision Audit (Basename vs. Content)
When cross-referencing all 201 filenames in the People archives against the 298 video files in the three `Days_and_Time` archives:
* **Full-path collision:** **0 collisions** (`Days_and_Time/...` vs `People/...`).
* **Basename collision:** **8 identical camera filenames** occur in both categories:
  - `MVI_5071.MOV`
  - `MVI_5072.MOV`
  - `MVI_5073.MOV`
  - `MVI_5074.MOV`
  - `MVI_5076.MOV`
  - `MVI_5077.MOV`
  - `MVI_5078.MOV`
  - `MVI_5079.MOV`

### Deep Investigation of the 8 Colliding Basenames:
We examined file sizes and internal CRC-32 checksums for each colliding basename:
1. `MVI_5071.MOV`:
   - Dates & Time (`84. Evening`): 8,969,036 bytes, CRC `674916d6`
   - People (`58. Son`): 13,275,368 bytes, CRC `30fab377`
   - **Verdict:** Completely different video recording (size & CRC mismatch).
2. `MVI_5072.MOV`:
   - Dates & Time (`84. Evening`): 8,754,488 bytes, CRC `9b691b52`
   - People (`58. Son`): 13,974,568 bytes, CRC `795acb5c`
   - **Verdict:** Completely different video recording.
3. `MVI_5073.MOV`:
   - Dates & Time (`85. Night`): 9,478,528 bytes, CRC `254f9a4c`
   - People (`58. Son`): 12,460,696 bytes, CRC `c6388929`
   - **Verdict:** Completely different video recording.
4. `MVI_5074.MOV`:
   - Dates & Time (`85. Night`): 8,644,136 bytes, CRC `baf99ba2`
   - People (`59. Daughter`): 14,641,460 bytes, CRC `1c32c7f3`
   - **Verdict:** Completely different video recording.
5. `MVI_5076.MOV`:
   - Dates & Time (`85. Night`): 9,278,844 bytes, CRC `53a98476`
   - People (`59. Daughter`): 13,158,800 bytes, CRC `f677c119`
   - **Verdict:** Completely different video recording.
6. `MVI_5077.MOV`:
   - Dates & Time (`86. Time`): 9,667,844 bytes, CRC `0688098b`
   - People (`60. Mother`): 11,485,172 bytes, CRC `8336d4a0`
   - **Verdict:** Completely different video recording.
7. `MVI_5078.MOV`:
   - Dates & Time (`86. Time`): 9,464,252 bytes, CRC `56cbb6c7`
   - People (`60. Mother`): 12,568,536 bytes, CRC `ba15d029`
   - **Verdict:** Completely different video recording.
8. `MVI_5079.MOV`:
   - Dates & Time (`86. Time`): 9,007,476 bytes, CRC `0324aeeb`
   - People (`60. Mother`): 12,124,264 bytes, CRC `4d8535f9`
   - **Verdict:** Completely different video recording.

> [!WARNING]
> **Data Integrity Hazard: DSLR Filename Reuse**  
> The original INCLUDE recording cameras recycled video sequence counters (`MVI_5071.MOV` ... `MVI_5079.MOV`) across filming sessions.  
> If an extraction script unzips files into a flat directory without prefixing (e.g. `PEOPLE_001_MVI_5071.MOV`), **it will silently overwrite files or corrupt dataset references**.  
> None of these 8 clips are present in our currently imported 45 Dates & Time samples (`DT_001` to `DT_045`).

---

## 4. Dataset Compatibility Findings

### A. Video Encoding & Format
* **Containers:** 95.0% QuickTime `.MOV`, 5.0% MPEG-4 `.MP4`.
* **Video Codec:** H.264 / AVC (High Profile).
* **Resolution:** 1920×1080 (1080p Full HD) across all probed files.
* **Frame Rate:** 25.0 FPS (PAL standard, CFR).
* **Duration:** Average ~2.4–2.8 seconds (~55–70 frames per clip).
* **Compatibility Verdict:** **100% COMPATIBLE** with existing `Dates_and_Time` video pipeline.

### B. Landmark Extraction Compatibility
* **Test Subject:** `People/58. Son/MVI_3753.MOV` probed via MediaPipe Holistic CPU.
* **Extraction Result:** 10/10 test frames returned full pose and hand tracking coordinates.
* **Feature Representation:** Conforms strictly to the canonical `mp-holistic-75-xyz-v1` layout:
  - 33 Pose landmarks (`indices 0..32`)
  - 21 Left Hand landmarks (`indices 33..53`)
  - 21 Right Hand landmarks (`indices 54..74`)
  - Shape: `(T, 75, 3)` with `float32` precision.

### C. Label Conventions
* **Raw Labels:** Numbered folder glosses (e.g., `58. Son`, `59. Daughter`).
* **Canonical Mapping:** Normalizes cleanly to uppercase gloss tokens (`SON`, `DAUGHTER`, `MOTHER`, `FATHER`, `PARENT`, `BABY`, `MAN`, `WOMAN`, `BROTHER`, `SISTER`).
* **Consistency:** Follows identical conventions as `Days_and_Time` (e.g. `74. Today` -> `TODAY`).

### D. Signer Metadata Availability
* **Archive Audit:** Neither `People_1of5.zip` nor `People_2of5.zip` contains signer mapping metadata, demographic tables, or split assignments.
* **Governance Reality:** As documented in the SIGNFORGE audit report, signer IDs cannot be verified from the Zenodo category archives alone.
* **Mandatory Policy:** If imported, any assigned signer codes must be explicitly documented as **unverified synthetic pseudonyms** (`signer_verified: false`) and **must not be used to claim signer-independent evaluation**.

### E. Dataset Provenance & Licensing
* **Repository Record:** Zenodo Record `4010759`, Concept DOI `10.5281/zenodo.4010758`.
* **Licence:** Creative Commons Attribution 4.0 International (**CC-BY-4.0**).
* **Commercial / Academic Permissions:** Free to share and adapt under CC-BY-4.0 terms.
* **Attribution Requirement:** Mandatory citation of Sridhar et al., ACM Multimedia 2020 (`10.1145/3394171.3413528`).
