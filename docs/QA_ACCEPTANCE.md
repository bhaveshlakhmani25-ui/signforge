# User Acceptance Testing & Bug Loop Protocol

**Lead Tester:** Aakarshi Dwivedi  
**Scope:** End-to-End Walkthrough of SIGNFORGE (Capture → Review → Rank → Export)

---

## 1. Acceptance Checklist

### Step 1: Consent Gate (`/capture`)
- [ ] Attempting to capture without a selected signer / consent returns a clear prompt to register consent.
- [ ] Signer pseudonym field rejects names like "John Doe" and accepts alphanumeric codes like `S-01`.
- [ ] Consent options require explicit check for `corpus_building`.

### Step 2: Live & Upload Capture (`/capture`)
- [ ] Video preview is mirrored visually for user comfort, but landmark coordinates are un-mirrored.
- [ ] Recording 3 seconds produces a skeleton overlay.
- [ ] Uploading a sample `.mp4` clip extracts landmarks without sending the video file to the backend.
- [ ] Automated QC triggers immediately:
  - Dropped hands trigger warning flag.
  - Duration $< 0.8\text{ s}$ or $> 8\text{ s}$ is flagged.
  - Exact duplicate landmark submission is rejected.

### Step 3: Human Review (`/corpus`)
- [ ] New captures appear under `Pending Review`.
- [ ] Reviewer must select their role (Native Signer, Deaf Community Member, Non-signer Team Member).
- [ ] Approving or rejecting a sample updates the status immediately without page refresh.
- [ ] Non-signer approval is clearly badged as technical check, not linguistic validation.

### Step 4: Active Learning Queue (`/active-learning`)
- [ ] Shows list of signs ranked by priority.
- [ ] Signs with 0 approved samples appear as `HIGH` priority with a plain-language explanation.
- [ ] Clicking "Record this sign" pre-fills the sign in `/capture`.

### Step 5: Benchmark & Export (`/benchmark`, `/export`)
- [ ] Benchmark curves show comparison between Active Learning, Balanced, and Random collection.
- [ ] Export package downloads a `.zip` containing only `.npz` landmark files and `manifest.json`. Raw video is verified absent.

---

## 2. Bug Filing Template

When filing a bug, use this exact format:

```markdown
### [BUG] <Short Title>
- **Page / Component:** (e.g. `/capture` -> VideoStream)
- **Assigned To:** [Tashvi / Reuben] (Backend/Model) or [Bhavesh] (Frontend/UI)
- **Severity:** Blocker / Major / Cosmetic
- **Steps to Reproduce:**
  1. Navigate to `/capture`
  2. Select Signer `S-01`
  3. Click "Start Recording"
- **Expected Result:** Camera starts stream and records landmarks.
- **Actual Result:** Error toast "Permission denied" or camera does not release.
- **Console / Network Error:** <Paste exact browser console error or HTTP response>
```
