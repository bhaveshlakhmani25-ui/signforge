# SIGNFORGE Recording-Day Protocol & Checklist

**Author:** Aakarshi Dwivedi (Data, QA & Evaluation)  
**Target:** Team Internal Recording Session (Pre-Demo Validation)  
**Signers:** Tashvi Adhlakha (`TEAM-T01`), Bhavesh Lakhmani (`TEAM-B02`), Reuben Raju (`TEAM-R03`), Aakarshi Dwivedi (`TEAM-A04`)  
**Scope:** 10 Core Practical Signs  

---

## 1. Ethics, Consent & Data Governance Rules

> [!IMPORTANT]
> **Non-Native Signer Disclosure:**  
> All recordings created by team members must be stored with provenance note `"TEAM DEMO: non-native signer; technical pipeline verification only"`. Under no circumstances should team recordings be labelled as "validated Indian Sign Language". Only reviews by native or Deaf community members count as linguistic validation.

### Consent & Withdrawal Protocol:
1. **Informed Consent Gate:** Before any team member records, register their consent via `POST /api/consents`:
   - Allowed Uses: `["corpus_building", "model_training"]`
   - Retention: `"landmarks_only"` (raw video is discarded instantly in the browser)
2. **Right to Withdraw:** Any signer can withdraw their consent at any time via `POST /api/consents/{consent_id}/withdraw`:
   - Setting `delete_samples=true` permanently deletes all associated landmark `.npz` files and marks the database records as withdrawn.
3. **Pre-Recording Deletion Verification:**
   - Bhavesh (Frontend Lead) must test the Delete Sample (`DELETE /api/samples/{id}`) and Consent Withdrawal buttons on `http://localhost:3000/corpus` before live recording commences.

---

## 2. Technical Recording Guidelines

* **Camera & Framing:** 720p or 1080p webcam at 25–30 FPS. Position camera at chest/eye level. Signer must be seated with both shoulders, elbows, and full upper signing space visible.
* **Lighting & Background:** Plain wall or non-distracting neutral backdrop. Direct frontal light; avoid strong backlighting or window glare that degrades hand contour detection.
* **Clothing:** Solid, dark clothing with high contrast against hand skin tone. Roll up sleeves past the wrist so wrist keypoints (`POSE_L_WRIST`, `POSE_R_WRIST`) are unoccluded.
* **Signing Cadence:**
  - Pause at neutral rest pose for 0.5 s before initiating sign.
  - Perform the sign naturally without exaggerated slowness.
  - Hold final pose for 0.5 s before lowering hands.
  - Keep total clip duration between **1.2 s and 4.0 s** (avoids `too_short` or `too_long` QC errors).

---

## 3. Team Recording Matrix (10 Signs × 4 Signers)

| Sign Gloss | Signer ID | Consent Status | Model-Training Permitted | Recording Status | Automated QC | Reviewer Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `HELLO` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELLO` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELLO` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELLO` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `THANK-YOU` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `THANK-YOU` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `THANK-YOU` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `THANK-YOU` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELP` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELP` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELP` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `HELP` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `EMERGENCY` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `EMERGENCY` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `EMERGENCY` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `EMERGENCY` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `DOCTOR` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `DOCTOR` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `DOCTOR` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `DOCTOR` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `WATER` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `WATER` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `WATER` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `WATER` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `FOOD` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `FOOD` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `FOOD` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `FOOD` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `PAIN` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `PAIN` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `PAIN` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `PAIN` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `YES` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `YES` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `YES` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `YES` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `NO` | `TEAM-T01` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `NO` | `TEAM-B02` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `NO` | `TEAM-R03` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |
| `NO` | `TEAM-A04` | Active (v1.0) | Permitted | Completed | Passed | Team Demo (Non-validated) |

---

## 4. Deaf Community Review Stage

If a fluent ISL Deaf signer or certified interpreter is present during the session:
1. Open the sample in `http://localhost:3000/corpus`.
2. Play the 15 FPS normalized skeleton replay.
3. Submit review with reviewer role selected as **"Deaf community member"** or **"Native signer"**.
4. Only with this role tag does the sample count as linguistically validated ISL in benchmark summaries.
