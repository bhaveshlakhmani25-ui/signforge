# SIGNFORGE — Pitch Deck Outline & 2-Minute Demo Script

**Owner:** Aakarshi Dwivedi (Pitch & QA)  
**Strict Rule:** No fabricated numbers. All metrics cited must come directly from the benchmark output log (`data/benchmark_results.json`).

---

## 1. 10-Slide Pitch Narrative

### Slide 1: Title
- **Headline:** SIGNFORGE — AI-Powered Low-Resource Sign-Language Corpus Builder
- **Tagline:** *From a few native signs to a model-ready corpus.*
- **Team:** Team Claude's Clan (Tashvi Adhlakha, Bhavesh Lakhmani, Reuben Raju, Aakarshi Dwivedi)

### Slide 2: The Core Problem — "A Data Bottleneck, Not Zero Data"
- Sign language resources are fragmented across 35+ languages.
- High barrier to entry: Scraping public videos lacks consent, contains annotation noise, and lacks Deaf community linguistic validation.
- Without active guidance, datasets suffer from severe class imbalance and signer bias.

### Slide 3: The Solution — The SIGNFORGE Loop
- Not just a translation app: a specialized data-generation and adaptation workbench.
- **The product loop:**
  `Consent Gate → In-Browser Landmarks → Automated QC → Pretrained Encoder / Baseline → Model Uncertainty & Coverage Analysis → "What to Collect Next" Task Ranker → Human Review Gate → Frozen Benchmark → Clean Export`.

### Slide 4: Architecture & Privacy-by-Pose
- **Client-Side Landmark Extraction:** Using MediaPipe Holistic WASM in the browser.
- **Privacy First:** Raw video never leaves the user's browser. Only un-mirrored landmark coordinates `(T, 75, 3)` are transmitted.
- **Tech Stack:** FastAPI, SQLModel/SQLite, Next.js 16 (React 19), PyTorch baseline GRU.

### Slide 5: Automated QC vs. Human Linguistic Validation
- **Technical QC (Automated):** Detects missing shoulders, dropped hands, left/right hand swaps, duration anomalies, and exact duplicates.
- **Human Review Gate (Linguistic):** A sample is only considered linguistically valid if verified by a Native Signer or Deaf Community Member.

### Slide 6: The Innovation — Active Learning ("What to Record Next?")
- Traditional data collection asks signers to record arbitrary lists.
- SIGNFORGE dynamically calculates:
  $$\text{Priority} = f(\text{Coverage Gap}, \text{Signer Diversity Gap}, \text{Model Uncertainty})$$
- Directly feeds collectors high-priority tasks (e.g. *"EMERGENCY has 0 approved samples; prioritize this"*).

### Slide 7: Real Benchmark & Experimental Validation
- Baseline model evaluated on a strictly frozen test set (signer-independent split when $\ge 3$ signers).
- Learning curves prove that Active Class Selection achieves target accuracy significantly faster than random sampling.
- *(Cite exact numbers from `data/benchmark_results.json`)*.

### Slide 8: Market & Stakeholders
- Universities and accessibility research labs.
- Assistive tech startups building Sign-to-Text systems.
- Deaf organizations and public healthcare / emergency response systems.

### Slide 9: Roadmap
- **Today (Hackathon MVP):** End-to-end active collection loop, ISL demo glosses, technical QC, baseline evaluation, export manifest.
- **Next 3 Months:** OpenHands transfer learning fine-tuning, multi-signer community portal, consent withdrawal API.
- **Long-term:** Continuous sign language expansion, mobile SDK for field collectors.

### Slide 10: Closing Message
> **“AI cannot learn what we never collect. Model Uncertainty → Next Sample → Better Data.”**

---

## 2. 2-Minute Demo Script (Rehearsal Guide)

- **[0:00 - 0:25] The Consent Gate & Ethics:**
  - *"Welcome to SIGNFORGE. Before any recording can happen, we enforce our Data Governance policy. The webcam remains locked until signer consent is verified under a pseudonym like `S-01`."*
- **[0:25 - 0:50] Capture & Instant QC:**
  - *"I'll sign 'HELLO'. Notice two things: the video is processed right here in the browser using MediaPipe WASM. The raw video is never uploaded. Watch our automated QC instantly check the sequence for hand dropout and body alignment."*
- **[0:50 - 1:15] Human Review & Corpus Health:**
  - *"Moving to the Corpus screen: technical QC is not linguistic validation. Samples stay in `pending_review` until verified by a reviewer, tagged by their role (native signer vs team member)."*
- **[1:15 - 1:40] Active Learning ("What to Record Next?"):**
  - *"Here is our core differentiator: the Active Learning dashboard. Rather than guessing, the system tells us: 'EMERGENCY has zero approved samples—record this next.' Clicking this button immediately loads the capture prompt."*
- **[1:40 - 2:00] Benchmark & Export:**
  - *"Finally, our Benchmark page proves the hypothesis: active sample selection reaches higher accuracy faster than random collection. And with one click, we export the clean, model-ready dataset with its reproducible manifest."*
