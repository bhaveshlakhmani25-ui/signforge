# SIGNFORGE Acceptance Test Report

**Tester:** Aakarshi Dwivedi (QA & Acceptance Lead)  
**Collaborators:** Bhavesh Lakhmani (Frontend Lead), Tashvi Adhlakha (Backend Lead)  
**Date:** 2026-10-31  
**Environment:** Windows 10/11 x64, Python 3.13 / FastAPI (port 8000), Next.js 16.4.2 (port 3000)  
**Scope:** Complete User Walkthrough (Overview → Capture → Review → Rank → Export + Dates & Time Signs)

---

## 1. Acceptance Test Execution Matrix

| Step | Workflow Target | Action Executed | Observed Result | Pass / Fail |
| :--- | :--- | :--- | :--- | :---: |
| **TC-01** | **Application Launch** | Navigate to `http://localhost:3000` | Overview dashboard loads in 1.2 s. Displays project summary, 23 active sign classes, and baseline model status. | **PASS** |
| **TC-02** | **Consent Gate** | Attempt capture without consent at `/capture` | System blocks recording stream and prompts user to register consent. API returns HTTP 403 if bypassed. | **PASS** |
| **TC-03** | **Pseudonym Validation** | Enter "John Doe" vs `S-01` in signer field | "John Doe" is rejected by regex `^[A-Z0-9][A-Z0-9-]{1,15}$`; `S-01` is accepted. | **PASS** |
| **TC-04** | **Capture & Automated QC** | Submit landmark frames via webcam/upload | Automated QC runs instantly: checks duration limits (0.8 s – 8.0 s), flags missing shoulders, and detects duplicates. | **PASS** |
| **TC-05** | **Corpus & Review** | Review sample at `/corpus` | Review modal allows setting status to `approved`, `rejected`, or `needs_recapture`. Logs reviewer role accurately. Replay API `/api/samples/{id}/landmarks` serves 15 FPS skeleton. | **PASS** |
| **TC-06** | **Active Learning Ranker** | Navigate to `/active-learning` | Displays priority queue of signs to record next. Priority scores correctly reflect real database coverage gaps (top need: `DOCTOR` at score 2.0; maintenance need: `YESTERDAY` at 0.4). | **PASS** |
| **TC-07** | **Model Benchmark** | Navigate to `/benchmark` | Renders comparative learning curves (Active Ranker vs Balanced vs Random) using benchmark log JSON. | **PASS** |
| **TC-08** | **Dataset Export** | Navigate to `/export` and click download | `GET /api/export` generates a 1.55 MB `.zip` package with 39 landmark `.npz` files, `manifest.json`, and `provenance.md`. Raw video excluded. | **PASS** |
| **TC-09** | **Dates & Time Integration** | Verify extracted INCLUDE signs | 39 samples across 13 signs extracted, converted to `mp-holistic-75-xyz-v1`, and registered in `signforge.db`. | **PASS** |

---

## 2. Bug Resolution & Audit Log

### BUG-001: `/api/queue` Endpoint Implementation
* **Description:** The Active Learning page (`/active-learning`) previously fell back to a synthetic fixture because the backend endpoint was missing.
* **Resolution:** Implemented `queue_endpoint` in `backend/app/main.py` implementing the agreed formula:
  $$\text{Priority} = \text{Coverage Gap} + \text{Signer Diversity Gap} + \text{Uncertainty}$$
* **Retest Result:** **VERIFIED FIXED**. Live API returns HTTP 200 with 23 ranked classes. Uncollected signs (`DOCTOR`, `EMERGENCY`) receive top priority (2.0), while INCLUDE signs receive maintenance priority (0.4).

---

### BUG-002: Export Flow Implementation
* **Description:** The Export navigation item was tagged under `PLANNED` and disabled.
* **Resolution:**
  - Implemented `backend/app/api/export.py` with `GET /api/export` and `GET /api/export/corpus`.
  - Packages eligible approved landmark sequences into `landmarks/{sample_id}.npz`, accompanied by `manifest.json` and `provenance.md` (CC-BY-4.0).
  - Built frontend interface at `frontend/app/export/page.tsx` and moved `Export` to `LIVE` in `frontend/components/Nav.tsx`.
* **Retest Result:** **VERIFIED FIXED**. Test download retrieved 1,553,756 bytes archive containing 41 files (39 landmarks + manifest + provenance).

---

### BUG-003: External Dataset Ingestion Loader
* **Description:** Extracted landmark files required automated ingestion and deduplication into `signforge.db`.
* **Resolution:** Created `backend/scripts/import_include.py`. Ingested 39 samples across 13 classes into `signforge.db` with SHA-256 fingerprinting for idempotency.
* **Retest Result:** **VERIFIED FIXED**. Re-running the loader skipped all 39 duplicates without errors or duplicate DB entries.

---

## 3. End-to-End Test Automation Results
Automated test suite `scripts/test_end_to_end.py` executed across all 6 core workflows:

```text
================================================================================
END-TO-END TEST SUMMARY
================================================================================
1_DATASET_LOADING        : PASSED
2_CORPUS_DISPLAY         : PASSED
3_CAPTURE                : PASSED
4_REVIEW                 : PASSED
5_RANKING                : PASSED
6_EXPORT                 : PASSED
================================================================================
OVERALL STATUS: ALL PASSED (100%)
```
