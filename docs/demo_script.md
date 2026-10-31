# SIGNFORGE Live Demo Script (2-Minute Timed Rehearsal)

**Presenter:** Aakarshi Dwivedi (Data, QA & Pitch Lead)  
**Timing:** Exactly 2:00 minutes  
**Live Frontend:** `http://localhost:3000` | **Live API:** `http://localhost:8000/docs`  
**Strict Rule:** Only cite real, measured numbers from repository logs and live endpoints.

---

### [0:00 – 0:25] Introduction & The Privacy-by-Pose Consent Gate
* **Action:** Start on the Overview dashboard (`http://localhost:3000`). Click **Capture** in the navigation bar.
* **Spoken Script:**
  > *"Judges, building AI for low-resource sign languages like Indian Sign Language cannot follow the old playbook of scraping random videos without consent. In SIGNFORGE, privacy and ethics come first.*
  > 
  > *Notice that here on the Capture screen, the recording pipeline is completely locked. Before any camera capture can take place, our Consent Gate enforces registering a pseudonymous signer code—like `S-01`—and consenting to corpus building with a landmarks-only retention policy."*

---

### [0:25 – 0:50] Client-Side Extraction & Instant Technical QC
* **Action:** Show the webcam view or trigger a quick capture sequence.
* **Spoken Script:**
  > *"When a signer records, raw video never touches a server. We run MediaPipe Holistic compiled to WebAssembly directly inside the browser at 25 to 30 frames per second.*
  > 
  > *The moment the recording completes, our automated technical QC runs in milliseconds: it validates clip duration between 0.8 and 8 seconds, verifies shoulder stability, and flags hand dropouts. Only the 75 normalized body and hand keypoints are saved. The raw video is discarded on the device."*

---

### [0:50 – 1:15] Corpus Review & Real INCLUDE Dates & Time Dataset
* **Action:** Click **Corpus & review** (`http://localhost:3000/corpus`).
* **Spoken Script:**
  > *"Automated checks are not linguistic validation. Here in the Corpus, samples stay pending until verified by a human reviewer who explicitly declares their role—such as a Native Signer or Deaf community member.*
  > 
  > *Crucially, we've integrated the official Dates and Time category from AI4Bharat's INCLUDE dataset: 39 real video clips across 13 unique ISL signs—including `MORNING`, `EVENING`, `WEEK`, and `YEAR`—all normalized to our `mp-holistic-75-xyz-v1` schema. You can click any sample to see a 15 FPS skeleton replay."*

---

### [1:15 – 1:40] Active Learning ("What Should We Record Next?")
* **Action:** Click **Active learning** (`http://localhost:3000/active-learning`).
* **Spoken Script:**
  > *"This is SIGNFORGE's primary innovation. Instead of burdening Deaf communities with arbitrary recording checklists, our Active Learning Ranker balances coverage gaps, signer diversity, and model uncertainty to answer: 'What data should we collect next?'*
  > 
  > *Notice that signs with zero real samples—like `DOCTOR` and `EMERGENCY`—are scored at highest urgency (2.0), while our 13 freshly imported INCLUDE signs drop down to maintenance priority (0.4). With one click on 'Record this sign', signers are directed straight to the pre-filled capture screen."*

---

### [1:40 – 2:00] Live Model-Ready Export & Wrap-up
* **Action:** Click **Export** (`http://localhost:3000/export`) and click the teal **"Download Export Package (.zip)"** button.
* **Spoken Script:**
  > *"Finally, here on our new Export screen, researchers can package the vetted corpus with one click. The generated 1.55 MB zip bundle contains all approved `.npz` landmark tensors, cryptographic checksums in `manifest.json`, and our formal CC-BY-4.0 provenance document.*
  > 
  > *SIGNFORGE closes the loop: from consented capture and community review to intelligent collection and reproducible dataset release. Thank you—we're ready for your questions!"*
