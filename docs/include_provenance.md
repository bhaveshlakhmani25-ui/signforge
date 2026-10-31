# INCLUDE Dataset Provenance & Licence Verification

**Author:** Aakarshi Dwivedi (Data, QA & Evaluation)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Category:** Days and Time (Indian Sign Language)  

---

## 1. Official Dataset Identifiers

* **Dataset Name:** INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition
* **Curator / Institution:** AI4Bharat / Indian Institute of Technology Madras (IIT Madras)
* **Official Project Website:** https://sign-language.ai4bharat.org/
* **Zenodo Repository Record:** https://zenodo.org/records/4010759
* **Digital Object Identifier (DOI):** [10.1145/3394171.3413528](https://doi.org/10.1145/3394171.3413528)
* **Primary Reference Publication:**
  > Sridhar, A. V., Ganesan, R. G., Kumar, P., & Khapra, M. (2020). *INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition*. Proceedings of the 28th ACM International Conference on Multimedia (ACM MM '20), 1310–1318.

---

## 2. Licence Verification & Terms

* **Verified Licence:** Creative Commons Attribution 4.0 International (**CC-BY-4.0**)
* **Licence Status:** **VERIFIED** (Recorded directly in Zenodo metadata schema).
* **Attribution Requirement:**
  - Any distribution, adaptation, or derivative model must cite the ACM MM 2020 paper above.
  - Changes must be clearly indicated (e.g., extraction of 75-keypoint MediaPipe Holistic landmarks, zero-filling missing joints, omitting face mesh).
* **Redistribution Conditions:**
  - Freedom to copy, transform, and build upon the material in any medium.
  - No additional legal restrictions or technological measures that legally restrict others from doing anything the licence permits.
* **Commercial Use:**
  - CC-BY-4.0 does not contain a "Non-Commercial" (`-NC`) rider.
  - *Ethical Caveat for SIGNFORGE:* While CC-BY-4.0 legally allows commercial adaptation, SIGNFORGE's data governance policy treats ISL signing data as community cultural heritage. No model trained on these signs will be commercialized without explicit community benefit agreements with native ISL signers.

---

## 3. Ingestion Details for Local Hackathon Scope

* **Download Date:** 2026-10-31
* **Source Archives Downloaded:**
  1. `Days_and_Time_1of3.zip` (1,244,115,203 bytes / 1,186.48 MB) — Signs 66 to 73 (112 videos)
  2. `Days_and_Time_2of3.zip` (1,016,797,379 bytes / 969.69 MB) — Signs 74 to 80 (99 videos)
  3. `Days_and_Time_3of3.zip` (852,955,661 bytes / 813.44 MB) — Signs 81 to 86 (87 videos)
* **Total Downloaded Data:** 3,113,868,243 bytes (~2.90 GB) containing 298 video clips across 21 signs.
* **Selected Category:** Days and Time
* **Selected Subset (15 Signs, within 10–20 limit):**
  - From Part 1: `TODAY`, `SUNDAY` (6 clips)
  - From Part 2: `TOMORROW`, `YESTERDAY`, `WEEK`, `MONTH`, `YEAR`, `HOUR`, `MINUTE` (21 clips)
  - From Part 3: `SECOND`, `MORNING`, `AFTERNOON`, `EVENING`, `NIGHT`, `TIME` (18 clips)
* **Signer Attribution:**
  - Signer identities in INCLUDE videos are anonymous volunteer students/instructors designated as pseudonymous codes (`INCLUDE-S01` .. `INCLUDE-S04`). No private personal names or contact data are provided or inferred.

---

## 4. Privacy-by-Pose Governance Restrictions

In compliance with SIGNFORGE's **Privacy-by-Pose** architecture:
1. **Raw Video Isolation:** Raw `.MOV` video files extracted from the zip archives are stored strictly in `dataset/INCLUDE/Dates_and_Time/videos/` on the local machine and are added to `.gitignore`. They are never pushed to GitHub.
2. **Landmark Representations Only:** Only the irreversible 75-keypoint motion coordinate sequences (`.npz`) are stored in the repo and exported.
3. **Face Mesh Dropped:** The 468-point face mesh is excluded to prevent facial biometric reconstruction.
