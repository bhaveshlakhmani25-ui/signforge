# Dataset Provenance & Licence Check: AI4Bharat INCLUDE

**Author:** Aakarshi Dwivedi (Data & QA)  
**Date:** 2026-10-31  
**Target:** Indian Sign Language (ISL) Subset for SIGNFORGE  

---

## 1. Overview & Dataset Citation
* **Dataset Name:** INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition
* **Source:** AI4Bharat / Zenodo
* **Repository:** https://github.com/AI4Bharat/INCLUDE
* **Zenodo Record:** https://zenodo.org/record/4010759 (DOI: 10.5281/zenodo.4010759)
* **Publication:** Advaitha Vetrivel Sridhar, Rohith G, Pratyush Kumar, Mitesh Khapra. *INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition*. In Proceedings of the 28th ACM International Conference on Multimedia (ACM MM '20), 2020.

---

## 2. Licence Analysis & Compliance

| Component | Licence | Terms / Permitted Use | Compliant with SIGNFORGE? |
| :--- | :--- | :--- | :--- |
| **Code** | MIT License | Attribution required, commercial & non-commercial use permitted. | Yes |
| **Dataset (Videos/Landmarks)** | CC-BY-4.0 | You are free to share and adapt the material for any purpose, with appropriate credit and indication of changes. | Yes |

### Attribution Notice:
> "INCLUDE dataset courtesy of AI4Bharat (Sridhar et al., ACM MM 2020), licensed under CC-BY-4.0."

---

## 3. Privacy & Governance Rules (SIGNFORGE Alignment)
1. **No Raw Video Redistribution:** 
   - Even though INCLUDE videos are CC-BY-4.0, SIGNFORGE principles dictate **Privacy-by-Pose**: we extract and store landmark `.npz` files only.
   - Raw video files are downloaded locally for landmark extraction only and excluded from git and dataset exports.
2. **Signer Pseudonymization:**
   - Signer identities in INCLUDE are mapped to synthetic codes (e.g. `INCLUDE-S01`, `INCLUDE-S02`) adhering to SIGNFORGE's alphanumeric pseudonym requirement.
3. **Subset Selection:**
   - To avoid large downloads and keep validation fast, only **1–2 zips** (covering 10–20 selected everyday/emergency signs matching our 10 seeded classes) are ingested.
