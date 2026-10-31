# SIGNFORGE — Recording Day Field Guide & Protocol (Section 7)

**Lead Organizer:** Aakarshi Dwivedi (QA & Field Coordinator)  
**Target:** In-person / Controlled Sign Language Corpus Capture  
**Compatibility:** Schema `mp-holistic-75-xyz-v1` & Automated QC Thresholds  

---

## 1. Schedule & Station Setup

| Time Slot | Activity | Key Responsibilities |
| :--- | :--- | :--- |
| **08:30 – 09:15** | Equipment Check & Lighting Calibration | Position tripod, verify 1080p stream, test background uniformity. |
| **09:15 – 09:45** | Signer Orientation & Ethics Briefing | Explain Consent Gate, pseudonymous IDs (`S-01`), and Privacy-by-Pose. |
| **09:45 – 12:30** | Recording Block 1: Everyday & Emergency Signs | Record 10 base glosses (`HELLO`, `EMERGENCY`, `DOCTOR`, etc.) with 3–5 repetitions per signer. |
| **12:30 – 13:30** | Break & Intermediate Backup | Backup extracted `.npz` files to secondary secure offline drive. |
| **13:30 – 16:00** | Recording Block 2: Dates and Time Signs | Record newly integrated classes (`SECOND`, `MORNING`, `AFTERNOON`, `EVENING`, `NIGHT`, `TIME`). |
| **16:00 – 17:00** | Human Review & Linguistic Validation | Review flagged recordings with Native ISL Signer / Deaf Community Member. |

---

## 2. Participant Coordination & Consent Protocol

1. **Informed Consent Gate:**
   - Every participant must register a Consent Record in the app before any capture button is unlocked.
   - Purpose: `corpus_building` (mandatory), `model_training` (optional, explicit toggle).
   - Retention policy strictly enforced: `landmarks_only` (raw video is never uploaded or retained).
2. **Pseudonym Assignment:**
   - Names are strictly prohibited. Signers are assigned codes adhering to regex `^[A-Z0-9][A-Z0-9-]{1,15}$` (e.g. `S-01`, `S-02`, `S-03`).
   - Optional demographic volunteer data: Handedness (`left`, `right`, `both`).

---

## 3. Physical Environment, Camera Framing & Lighting

* **Camera Positioning:**
  - Eye-level with the seated or standing signer (approx. 1.2 m – 1.4 m from floor).
  - Distance: 1.5 m – 2.0 m from signer to ensure full upper-body coverage (hips to crown of head).
* **Lighting:**
  - Frontal three-point lighting or soft diffused daylight.
  - **Avoid backlighting:** Window behind the signer causes silhouette underexposure, leading to hand tracking failure.
* **Background:**
  - Solid, non-reflective matte backdrop (neutral blue, grey, or off-white) to optimize landmark edge detection.
  - Signer clothing: Plain, solid colour contrasting with skin tone (avoid patterns or stripes).
* **Hand Visibility & Framing:**
  - The signer must hold hands within frame throughout the entire sign stroke.
  - Signers must pause with neutral hands at rest for 0.5 s before and after executing the sign.

---

## 4. Technical Specifications & File Standards

* **Capture Resolution:** 1920 $\times$ 1080 (minimum 1280 $\times$ 720).
* **Target Frame Rate:** 25.0 – 30.0 FPS.
* **Duration Limits (Automated QC Enforced):**
  - Minimum clip duration: **0.8 seconds** (`QC_MIN_DURATION_S = 0.8`).
  - Maximum clip duration: **8.0 seconds** (`QC_MAX_DURATION_S = 8.0`).
* **File Naming & Directory Convention:**
  - Stored feature paths: `data/processed/{project_id}/{sample_id}.npz`
  - External ingestion staging: `dataset/INCLUDE/Dates_and_Time/videos/DT_{id}_{filename}.mp4`

---

## 5. Quality Verification & Human Review Workflow

Each recording undergoes two distinct validation steps:
1. **Automated Technical QC (Instant):**
   - Missing shoulders rate $> 20\%$ $\rightarrow$ **FAIL**
   - Dropped hands rate $> 30\%$ $\rightarrow$ **FAIL**
   - Left/right hand cross-body mismatch $> 20\%$ $\rightarrow$ **FAIL**
   - Exact duplicate landmark sequence $\rightarrow$ **FAIL**
2. **Human Review Gate:**
   - Status transitions from `pending_review` $\rightarrow$ `approved`, `rejected`, or `needs_recapture`.
   - Reviewer role must be logged: `native_signer`, `deaf_community_member`, `interpreter`, or `team_non_signer`.
   - Only native signer or Deaf community approval constitutes linguistic validation.
