# SIGNFORGE Pitch Deck Content (Honest Metrics Edition)

**Author:** Aakarshi Dwivedi (Pitch & QA Lead)  
**Date:** 2026-10-31  
**Integrity Rule:** Grounded strictly in measured system data. No fabricated accuracy or performance metrics.

---

## Slide 1: Title & Positioning
* **Headline:** SIGNFORGE — AI-Powered Low-Resource Sign-Language Corpus Builder
* **Tagline:** *From a few native signs to a model-ready corpus.*
* **Team:** Team Claude's Clan (Tashvi Adhlakha, Bhavesh Lakhmani, Reuben Raju, Aakarshi Dwivedi)
* **What SIGNFORGE is:** A data-generation and model-adaptation workbench that turns consented signing into structured motion data, identifies coverage gaps, and tells collectors: **“What sign should we record next?”**

---

## Slide 2: The Problem — The Low-Resource Data Bottleneck
* Over 35+ sign languages documented globally; Indian Sign Language (ISL) serves over 5 million Deaf individuals with severe data scarcity.
* Scraping public web videos yields noisy labels, lacks signer consent, and omits essential Deaf community linguistic validation.
* Unfocused collection leads to class imbalance and signer bias.

---

## Slide 3: The End-to-End Workflow
```text
Consent Gate (Pseudonymous) 
  → In-Browser Landmarks (WASM, Privacy-by-Pose) 
  → Automated Technical QC 
  → Human Linguistic Review (Role-Declared) 
  → Active Learning Queue ("What to collect next") 
  → Frozen-Split Baseline Evaluation 
  → Model-Ready Corpus Export (.zip bundle)
```

---

## Slide 4: Real Data Integration — AI4Bharat INCLUDE (Dates & Time)
* **Category Ingested:** Dates and Time category (Zenodo record `4010759`, CC-BY-4.0).
* **Archives Processed:**
  - `Days_and_Time_3of3.zip` (852.96 MB)
  - `Days_and_Time_2of3.zip` (1,016.80 MB)
* **Signs Imported:** **13 unique ISL word signs** (`AFTERNOON`, `EVENING`, `HOUR`, `MINUTE`, `MONTH`, `MORNING`, `NIGHT`, `SECOND`, `TIME`, `TOMORROW`, `WEEK`, `YEAR`, `YESTERDAY`).
* **Samples Extracted & Ingested:** **39 video clips** (3 per sign across 4 signers).
* **Storage & Governance:** Standardized `.npz` landmark tensors, cryptographic `manifest.json`, and formal `provenance.md`. Raw videos retained locally under Privacy-by-Pose policy.

---

## Slide 5: Landmark Extraction & Privacy-by-Pose
* **Schema:** `mp-holistic-75-xyz-v1` (33 pose + 21 left hand + 21 right hand, zero-filled missing joints).
* **Client-Side Extraction:** Powered by `@mediapipe/tasks-vision@1.1.0` in WebAssembly float16. Raw video never leaves the client's device.
* **Empirical Python Processing Benchmark (Dates & Time Source Clips):**
  - `DT_001` (Second): 10.2 FPS (4.71 s for 48 frames)
  - `DT_004` (Morning): 12.2 FPS (4.34 s for 53 frames)
  - `DT_007` (Afternoon): 12.6 FPS (3.64 s for 46 frames)
  - **Empirical Average:** 11.7 FPS on standard CPU.

---

## Slide 6: Automated QC vs. Human Linguistic Gate
* **Automated Technical QC (Instant Heuristics):**
  - Minimum/Maximum duration check (0.8 s to 8.0 s).
  - Missing shoulder detection ($> 20\%$).
  - Hand dropout rate ($> 30\%$).
  - Left/right hand cross-body mismatch ($> 20\%$).
  - Duplicate landmark hash matching (`feature_sha256`).
  - *Empirical Pass Rate:* 38 of 39 real samples passed automated QC (97.4%). `DT_033` (`YEAR`) flagged for midline hand crossing.
* **Human Validation Gate:**
  - Status stays `pending_review` until verified by a reviewer.
  - Reviewer role explicitly tracked (`native_signer`, `deaf_community_member`, `interpreter`, `team_non_signer`).
  - Only native signers count toward true linguistic validity.

---

## Slide 7: Active Learning ("What Should We Collect Next?")
* Replaces static wordlists with dynamic rank scoring:
  $$\text{Priority} = \text{Coverage Gap} + \text{Signer Diversity Gap} + \text{Model Uncertainty}$$
* **Live System Integration:**
  - `GET /api/queue` serves 23 ranked classes directly from `signforge.db`.
  - Uncollected signs (`DOCTOR`, `EMERGENCY`, `FOOD`) rank at maximum urgency (score 2.0).
  - 13 INCLUDE signs rank at maintenance priority (score 0.4).
  - Direct collector handoff: prioritized cards in UI with a one-click **"Record this sign"** shortcut.

---

## Slide 8: Real Benchmark Status & Honest Evaluation
* **Baseline GRU Architecture:** Hidden size 64, 80 epochs, Adam lr $10^{-3}$, minimal 27-keypoint subset, clip-level shoulder normalization.
* **Current Run Metrics (Demo Pool Fixture):**
  - Seeded Run ID 1: 90 samples, Top-1 Accuracy: 1.0, Macro F1: 1.0.
  - *Honesty Disclosure:* Evaluated on synthetic demo sine-wave fixture solely to verify pipeline execution; real ISL benchmark curves will be generated once full community collection completes.
* **Transfer Learning Status:** Marked **Blocked / Not Verified** in the system. The OpenHands DPC ST-GCN checkpoint exists, but feature drift between legacy Holistic and Tasks Vision is being measured before adoption.

---

## Slide 9: Completed Milestones & Near-Term Roadmap
* **Completed in this Hackathon Sprint:**
  - [x] Consented in-browser capture with pseudonym validation.
  - [x] In-browser MediaPipe WASM extraction + automated technical QC.
  - [x] Ingestion of 39 real ISL samples across 13 classes from AI4Bharat INCLUDE.
  - [x] Live Active Learning Ranker (`/api/queue`) driving collection priorities.
  - [x] Model-ready downloadable `.zip` export (`/api/export` & `/export` UI).
* **Near-Term Roadmap:**
  - Complete ingestion of `Days_and_Time_1of3.zip` when downloaded.
  - Train baseline classifier on real INCLUDE landmark corpus.
  - Integrate facial grammar markers (eyebrow raise, mouth morphemes) into extended schema.

---

## Slide 10: Closing
> **“AI cannot learn what we never collect. SIGNFORGE directs collection to where models are weakest.”**
