# SIGNFORGE — Project Brain, Research Dossier, Product Specification, and Claude Code Instructions

> **Document role:** This is the primary working context for building the SIGNFORGE hackathon prototype. Read it before planning, editing, or generating code. It combines the submitted idea deck, implementation constraints, research evidence, product/design direction, data governance, and a copy-ready kickoff prompt.
>
> **Research checked:** 22 October 2026. Re-check linked sources, repository state, model checkpoint availability, APIs, and dataset terms before relying on them. Public evidence may change.

---

## 0. Start here: what SIGNFORGE actually is

**SIGNFORGE — AI-Powered Low-Resource Sign-Language Corpus Builder**

**Tagline:** *From a few native signs to a model-ready corpus.*

**Official problem statement:** “Low-resource sign-language corpus builder using motion-capture transfer learning.”

**Core idea:** SIGNFORGE is not primarily a sign-language translator. It is a data-generation and model-adaptation workbench for under-resourced sign languages. It turns consented sign recordings into structured motion data, checks data quality and coverage, adapts a compatible pretrained representation where feasible, then uses uncertainty and corpus-health signals to recommend what should be collected next.

**The defining question:** **“What data should we collect next?”**

**The key differentiator:** The system does not merely store/annotate data or run a sign classifier. Its proposed workflow feeds model uncertainty and dataset coverage/diversity gaps back into the collection plan, with a human/native/Deaf review gate and a before/after benchmark.

### The product loop

`Consented capture → pose/motion landmarks → segmentation + technical QC → pretrained motion representation → small target-language adapter/head → uncertainty + data-gap analysis → next-sample recommendation → human/native/Deaf validation → model update → frozen-test benchmark → model-ready corpus export`

### Official team and status

- **Team:** Team Claude’s Clan
- **Tashvi Adhlakha** — Team Leader
- **Bhavesh Lakhmani**
- **Reuben Raju**
- **Aakarshi Dwivedi**
- **Status:** Round-1 idea/PPT submission selected. The task now is to build the next-round prototype.
- Preserve these official name spellings as given above.

---

## 1. Product principles — do not drift from these

1. **A corpus builder first, not a translator.** A small recognition model is a research instrument used to evaluate the data loop, not the whole product.
2. **No foundation model trained from scratch.** The intended model path is `pretrained representation → small target dataset → adapter/fine-tuning → uncertainty → targeted collection → retraining/evaluation`.
3. **Honest transfer learning.** Never label randomly initialized weights as “pretrained.” If no compatible checkpoint can be verified, state that clearly and keep the baseline operational.
4. **Data quality has multiple dimensions.** Show coverage, signer diversity, sequence completeness, quality flags, annotation/review status, consent and provenance. Do not invent one magic quality score without showing its parts.
5. **Technical QC is not linguistic validation.** Landmark completeness can be automated; sign correctness, regional meaning and appropriateness need human review, ideally by qualified/native/Deaf reviewers.
6. **Consent and allowed use are product features, not footer text.** Collect the minimum necessary personal data; use pseudonymous signer IDs; be explicit about retention and allowed use.
7. **No fabricated metrics.** Charts and metric cards display real computed results or are visibly labelled `DEMO DATA`. Never mix fixture data into evaluation by default.
8. **MVP before platform.** The hackathon proves a small end-to-end loop—not multilingual, production-grade global infrastructure.
9. **LLMs are optional support tools only.** They may help draft metadata, documentation or explanations. They must not be the sign-recognition model or a substitute for human validation.
10. **Build for explanation.** A team member should be able to explain every model, score, data field and displayed metric to a judge.

---

## 2. What the submitted 10-slide deck promises

Treat these as the narrative contract. Build enough to demonstrate the central loop; do not imply all future ideas already exist.

| Slide | Promise / message | What the prototype should visibly support |
|---|---|---|
| 1. Title | Signer → phone/webcam → motion data → AI data-gap engine → model-ready corpus | Dashboard that visually makes the data-generation workflow obvious |
| 2. Problem | “A data bottleneck—not zero data”: fragmentation, inconsistent annotation, limited coverage, signer bias and data gaps | Corpus health that exposes sample/sign coverage, signer distribution and quality flags |
| 3. Solution | Capture → landmarks → segment/QC → encoder/transfer → uncertainty → next sample → human review → update/benchmark | Working capture/QC/review/next-sample path, with model/evaluation paths integrated as feasible |
| 4. Tech stack | Webcam, MediaPipe/equivalent, Python/PyTorch, GRU/TCN baseline, pretrained encoder + adapter, active learning, FastAPI, Postgres/Supabase, React/Next.js | Locally runnable, documented software path; no hardware dependency |
| 5. Innovation | Few-shot motion transfer, corpus health, privacy-by-pose, model-impact loop; honest landscape comparison | Explainable recommendation logic, provenance and before/after evaluation |
| 6. Impact | Better data → better models → more accessible applications | Measure upstream data and model changes; do not claim unmeasured downstream impact |
| 7. Audience/market | Labs, accessibility startups, Deaf organizations, public institutions and AI companies | Product workflows for dataset creators/reviewers rather than end-user translation |
| 8. Revenue | Community/academic, research, pro, enterprise and data services | Future direction only; do not implement billing in MVP |
| 9. Roadmap | 24-hour MVP → community platform → advanced AI → global infrastructure | Make the current MVP scope clearly smaller than the future roadmap |
| 10. Closing | “AI cannot learn what we never collect. MODEL UNCERTAINTY → NEXT SAMPLE → BETTER DATA.” | Reproduce the core loop in the demo |

### MVP scope committed in the deck

- One target language/domain.
- 10–30 sign classes.
- Ideally 2–4 consenting signers.
- Webcam/phone capture and landmark extraction.
- Baseline vs transfer-learning comparison.
- Uncertainty/active-learning queue and corpus-health dashboard.
- Before/after benchmark.

**Default implementation assumption:** ISL is the most contextually relevant starting target because the deck references Indian Sign Language resources (INCLUDE and iSign). Keep the target language configurable; do not hardwire data schemas or models so they only support ISL. Confirm with the team before downloading large datasets or locking an evaluation design.

---

## 3. Research dossier — evidence and implications for the build

The facts below are source-derived. Engineering decisions after each fact are explicitly labeled as proposals.

### 3.1 Dataset fragmentation and standards

**Source:** Ni et al., *Sign-Language Datasets at Scale: A Comprehensive Survey on Resources, Benchmarks, and Annotation Standards*, ACL 2026. [R1]

- The survey indexes **120 resources across 35 sign languages**.
- It discusses fragmented resources, annotation granularity/inconsistency, modality imbalance, signer bias and limited linguistic coverage.
- It proposes a 24-field sign-language datasheet to support documentation and reproducible evaluation.

**Implication for SIGNFORGE:** Track more than sign-class count. Include language/domain/region metadata, signer-distribution summaries, modality/feature schema, annotations and review state, provenance/license, consent/allowed-use, split definitions, model version and benchmark metrics. Keep the dataset manifest exportable and reproducible.

### 3.2 Indian Sign Language context

**Source:** Wadhera, Mahmud and Dhaneshwar, *Towards Inclusive Sign Language Recognition: Dataset Gaps, Ethical Challenges, and Deployment Barriers in the Indian Context*, CVPR Workshops 2026. [R2]

- The paper identifies limited datasets, dialectal diversity, lack of ethically collected/dialect-aware multimodal data, fairness risks from non-representative data and deployment/infrastructure constraints.
- It calls attention to standardized benchmarks, interpreters, annotation frameworks and equitable evaluation.

**Implication:** Do not say India has no datasets. Make ISL target selection configurable, store optional region/dialect/domain notes only where volunteered/appropriate, and treat signer-independent evaluation and consent as first-class design concerns.

### 3.3 Transfer learning for extremely low-resource sign recognition

**Source:** Holmes et al., *From Scarcity to Understanding: Transfer Learning for the Extremely Low Resource Irish Sign Language*, ICCV Workshops 2023. [R3]

- The work investigates transfer learning for extremely low-resource sign-language recognition using pose/keypoint inputs.
- It provides research support for exploring reusable pose/motion representations rather than training everything from scratch.

**Implication:** Compare a simple target-data-only baseline against a genuine transferred representation plus a small head/adapter. The paper does **not** guarantee that an arbitrary checkpoint will fit our keypoint format or improve performance on ISL; compatibility and outcomes must be measured.

### 3.4 Pose-based pipelines and privacy

**Source:** Google DeepMind, *Putting sign language AI into users’ hands*, published August 2026. [R4]

- Google describes SL2T as trained on more than 100,000 hours across more than 50 sign languages and using MediaPipe Holistic pose landmarks as model inputs.
- Their described workflow sends geometric landmark coordinates rather than raw camera video to the server, allowing raw video to be discarded in that workflow.
- The article stresses that sign language uses simultaneous hand, arm, torso, head and facial movement; non-manual signals and spatial constructions matter.

**Implication:** Pose/landmark representation is a credible privacy-aware direction, but landmark data is still potentially sensitive and is not automatically anonymous. Preserve the features the selected task/checkpoint needs; do not drop face/head/body information blindly. Raw-video deletion should be implemented and verified, not merely promised.

### 3.5 MediaPipe Holistic feature layout

**Source:** Google AI Edge, *Holistic Landmarker guide*. [R5]

- The documented task combines face, pose and hands, with 553 landmarks: 478 face, 33 pose and 21 per hand.
- Outputs can include normalized landmarks and world landmarks; other optional outputs are also available.

**Implication:** Do not assume that a 553-landmark tensor is the correct input for every pretrained model. A compatible checkpoint may expect only hands + BlazePose, a different ordering, fixed frame length, different coordinate system or a custom normalization pipeline. Version the feature schema and implement the extractor-to-model contract explicitly.

### 3.6 Indian dataset/resource candidates

**INCLUDE — AI4Bharat.** [R6]

- Official repository contains code for isolated Indian Sign Language recognition.
- The documented pipeline extracts keypoints using MediaPipe Hands and BlazePose; the repository describes baseline training and a `--use_pretrained` path for inference/resuming training.
- The public repository's code workflow is useful as an implementation reference. Dataset download and usage requirements must be checked independently; code availability does not establish permission for every dataset use.

**iSign — ACL 2024.** [R7]

- A benchmark for Indian Sign Language processing with 118k+ video-sentence/phrase pairs, according to the paper.
- Tasks include SignVideo2Text, SignPose2Text, Text2Pose, word prediction and sign semantics.
- It is a valuable ISL research resource, but its continuous video/phrase tasks are not automatically equivalent to a small isolated-sign classification MVP.

**Build decision proposal:** Use small, consented, controlled sign-class clips to demonstrate the SIGNFORGE collection loop. Use INCLUDE/iSign for research reference or additional experiments only after verifying the exact data, labels, split, download process, license/terms and technical fit. Don't make demo reliability depend on downloading a very large corpus.

### 3.7 Other datasets that are useful for research/design, not automatic substitutes for ISL

**ASL Citizen — Microsoft Research.** [R8]

- Microsoft describes about 84,000 ASL videos spanning about 2,700 distinct signs, everyday signers/recording settings, contributor consent and IRB approval.
- ASL is distinct from ISL. It can inform collection workflow and signer-diversity practices but should not be relabelled as ISL.
- Read the current dataset license/terms and contact Microsoft for commercial-use questions; do not infer unrestricted use from public availability.

**How2Sign.** [R9]

- A multimodal, multiview continuous ASL corpus with more than 80 hours of video and associated modalities including transcripts, depth and skeleton/pose resources.
- The official page describes availability for research purposes only. Do not assume commercial use/redistribution rights.
- Likely too large/continuous for the first 24-hour MVP; use as longer-term research context unless a very specific subset is justified and permitted.

**CLERC Épée v0.3.** [R10]

- CLERC documents an ASL keypoint dataset with 1,200 clips from six native Deaf signers, 128 keypoints/frame, gloss annotations/temporal boundaries and a frozen unseen-signer benchmark.
- The listed license is **CC BY-NC-SA 4.0**, a non-commercial/share-alike license. Treat it as research/non-commercial only unless permission/terms change; do not use it for commercial training or redistribute derivatives without checking obligations.
- This is a useful example of why signer-independent evaluation and frozen benchmarks matter. It is ASL, not ISL.

### 3.8 Active learning: what the algorithm means here

**Source concept:** In pool-based active learning, the current model ranks candidate samples, gets the most useful selected examples labelled/validated, retrains, and repeats. Uncertainty sampling commonly uses least confidence, class-probability margin or predictive entropy. [R11]

**MVP implementation proposal (not a published result and not a novel algorithm):** prioritize *collection tasks* using visible components, for example:

- 0.50 × normalized model uncertainty;
- 0.30 × class coverage gap;
- 0.20 × signer-diversity gap.

Weights are starting defaults only. Make them configurable; explain each component in the UI; do not repeat the same class/signer task indefinitely. If there is no trained model/probability output yet, the queue may start from coverage/diversity gaps, but must label uncertainty as “not available yet” rather than faking it.

### 3.8.1 Handoff Contract: Ranker I/O (Tashvi <-> Ruben & Bhavesh)

Shared ranker function used identically by simulation harness (Ruben) and live UI queue (Bhavesh).
**Rule:** Frozen test set NEVER feeds the ranker. Only approved, consenting samples from the training/unassigned pool are counted.

**Ranker Inputs (per sign class):**
```python
{
    "sign_class_id": int,
    "gloss": str,
    "approved_sample_count": int,      # Count of approved, consenting samples
    "distinct_signer_count": int,      # Count of distinct signers with approved samples
    "target_samples": int,             # Target samples per class (default 10, or max across classes)
    "target_signers": int,             # Target distinct signers per class (default 3)
    "uncertainty": float | None,       # 0.0 - 1.0; None if model not evaluated yet
    "weights": {                       # Optional, default: 0.35 cov, 0.25 sig, 0.40 unc
        "coverage": float,
        "signer": float,
        "uncertainty": float
    }
}
```

**Ranker Output Item (per sign class):**
```json
{
  "sign_class_id": 1,
  "gloss": "HELLO",
  "priority": 0.82,
  "coverage_gap": 0.90,
  "signer_gap": 0.67,
  "uncertainty": null,
  "uncertainty_display": "Not evaluated yet",
  "suggested_signer": "new_signer",
  "reason": "High coverage gap (1/10 samples) and only 1 signer represented; model uncertainty not evaluated yet.",
  "formula_version": "ranker-v1"
}
```
**Formula:**
- $\text{coverage\_gap} = \max(0.0, 1.0 - \frac{N_{\text{approved}}}{N_{\text{target}}})$
- $\text{signer\_gap} = \max(0.0, 1.0 - \frac{S_{\text{distinct}}}{S_{\text{target}}})$
- If `uncertainty` is available ($u \in [0, 1]$):
  $$\text{priority} = w_{\text{cov}} \cdot \text{gap}_{\text{cov}} + w_{\text{sig}} \cdot \text{gap}_{\text{sig}} + w_{\text{unc}} \cdot u$$
- If `uncertainty` is `None`:
  $$\text{priority} = \frac{w_{\text{cov}} \cdot \text{gap}_{\text{cov}} + w_{\text{sig}} \cdot \text{gap}_{\text{sig}}}{w_{\text{cov}} + w_{\text{sig}}}$$
- Normalization ensures `priority` is always in $[0.0, 1.0]$. Ties broken deterministically by alphabetical gloss.

### 3.8.2 Handoff Contract: External Dataset Manifest (Akarshi <-> Tashvi)
For Akarshi's INCLUDE import script writing to `data/external/<dataset_name>/`:
`manifest.json`:
```json
{
  "dataset_name": "INCLUDE",
  "dataset_version": "1.0",
  "license": "CC-BY-4.0",
  "citation": "Sridhar et al., INCLUDE, ACM MM 2020",
  "provenance_note": "Subset of 10-20 signs for low-resource ISL benchmark",
  "feature_schema_version": "mp-holistic-75-xyz-v1",
  "extractor": "mediapipe-holistic-python",
  "extractor_model_sha": "e2dab611...",
  "samples": [
    {
      "gloss": "HELLO",
      "external_sample_id": "include_hello_001",
      "external_signer_id": "signer_01",
      "feature_file": "features/include_hello_001.npz",
      "frame_count": 65,
      "fps": 30.0,
      "width": 1920,
      "height": 1080,
      "external_split": "train"
    }
  ]
}
```

### 3.8.3 Handoff Contract: Benchmark Output Schema (Ruben <-> Bhavesh)
Written by Ruben's benchmark script to `data/benchmark_results.json`:
```json
{
  "benchmark_version": "v1",
  "timestamp": "2026-10-31T14:00:00Z",
  "dataset": "INCLUDE-subset",
  "n_classes": 10,
  "seeds": [42, 101, 2024],
  "frozen_test_samples": 30,
  "strategies": {
    "ranker": { "steps": [0, 5, 10, 15, 20], "macro_f1_mean": [0.35, 0.52, 0.68, 0.76, 0.81], "macro_f1_std": [0.03, 0.04, 0.02, 0.02, 0.01] },
    "balanced_round_robin": { "steps": [0, 5, 10, 15, 20], "macro_f1_mean": [0.35, 0.44, 0.55, 0.63, 0.70], "macro_f1_std": [0.03, 0.03, 0.03, 0.02, 0.02] },
    "random": { "steps": [0, 5, 10, 15, 20], "macro_f1_mean": [0.35, 0.40, 0.48, 0.54, 0.61], "macro_f1_std": [0.03, 0.05, 0.04, 0.03, 0.03] }
  },
  "summary": "Active learning ranker beat both random (+20% F1) and balanced round-robin (+11% F1) across 3 seeds."
}
```

### 3.9 Competitor and adjacent-system landscape

Use public documentation only. The comparison below is not proof that any organization lacks private or undisclosed capabilities. Phrase SIGNFORGE’s difference as our proposed workflow emphasis, not as “nobody else does this.”

| System | Publicly documented focus | Lesson / honest SIGNFORGE positioning |
|---|---|---|
| **ELAN** [R12] | Multimedia annotation tool for video/audio and sign language, time-linked annotations, tiers and export | Annotation is important; SIGNFORGE proposes an upstream model-guided next-sample loop. ELAN-compatible export is future work, not MVP-critical. |
| **ASL Citizen** [R8] | Community-sourced isolated ASL dataset, everyday signers, contributor consent and research baselines | Learn from contributor design and signer diversity. SIGNFORGE focuses on active model-guided collection tasks and corpus health. |
| **GoSign Factory** [R13] | Publicly described community-driven collection platform: guided prompts, short clips and quality review | Strong adjacent system for scalable collection. Our proposed emphasis is linking model uncertainty + coverage/diversity to which prompt is requested next. |
| **CLERC / Épée** [R10] | Structured keypoint dataset, annotations and frozen unseen-signer benchmark | Shows value of multi-signer data and fixed evaluation. SIGNFORGE connects data gaps to new collection and repeated evaluation. |
| **Kara Technologies** [R14] | Publicly describes a sign library built from native Deaf signers captured with motion capture, reviewed/animated, plus AI translation/digital humans and its KNS notation | Similar upstream investment in authentic motion data; SIGNFORGE’s proposal is a low-resource corpus-builder workflow and active sample-selection loop, not avatar-first translation. |
| **Signvrse** [R15] | Publicly describes AI sign-language products using computer vision, generative AI/LLMs, motion capture, avatars and Deaf-centred data | Adjacent downstream accessibility/translation platform. SIGNFORGE is positioned primarily as data-generation, adaptation and benchmarking infrastructure. |
| **Google DeepMind SL2T** [R4] | Large-scale multilingual sign-to-text translation with pose-landmark input and community governance | Validates pose-based processing and importance of community input; demonstrates the scale gap between production translation systems and our proposed small low-resource collection loop. |
| **OpenHands / INCLUDE research** [R6, R16] | OpenHands documents pose-based pretrained models across languages; INCLUDE provides ISL recognition code/model workflows | Candidate technical references only. Check checkpoint availability, maintenance status, expected keypoints, preprocessing, license and fit before adoption. |

### 3.10 Research references and direct links

- **[R1] ACL 2026 dataset survey:** https://aclanthology.org/2026.acl-long.1928/
- **[R2] CVPR Workshops 2026, Indian-context review:** https://openaccess.thecvf.com/content/CVPR2026W/MSLR/html/Wadhera_Towards_Inclusive_Sign_Language_Recognition_Dataset_Gaps_Ethical_Challenges_and_CVPRW_2026_paper.html
- **[R3] Holmes et al., ICCV Workshops 2023, low-resource transfer learning:** https://openaccess.thecvf.com/content/ICCV2023W/ACVR/html/Holmes_From_Scarcity_to_Understanding_Transfer_Learning_for_the_Extremely_Low_ICCVW_2023_paper.html
- **[R4] Google DeepMind SL2T (August 2026):** https://deepmind.google/blog/putting-sign-language-ai-into-users-hands/
- **[R5] Google AI Edge MediaPipe Holistic Landmarker:** https://developers.google.com/edge/mediapipe/solutions/vision/holistic_landmarker
- **[R6] AI4Bharat INCLUDE repository:** https://github.com/AI4Bharat/INCLUDE
- **[R7] iSign, ACL Anthology:** https://aclanthology.org/2024.findings-acl.643/ and project page https://exploration-lab.github.io/iSign/
- **[R8] ASL Citizen, Microsoft Research:** https://www.microsoft.com/en-us/research/project/asl-citizen/
- **[R9] How2Sign official dataset page:** https://how2sign.github.io/
- **[R10] CLERC Épée dataset and license:** https://clerc.io/data
- **[R11] Active learning overview / pool-based selection:** https://technav.ieee.org/topic/active-learning/ (Use for basic terminology; prioritize primary research if implementing a more sophisticated strategy.)
- **[R12] ELAN official manual:** https://www.mpi.nl/tools/elan/docs/manual/Pref_Introduction.html
- **[R13] GoSign Factory announcement:** https://www.gosign.ai/post/introducing-the-gosign-tasks-platform
- **[R14] Kara Technologies technology page:** https://www.kara.tech/technology
- **[R15] Signvrse official about/product positioning:** https://signvrse.com/about and https://www.signvrse.com/
- **[R16] AI4Bharat OpenHands repository:** https://github.com/AI4Bharat/openhands — repository currently warns it is no longer actively maintained; the code lists Apache-2.0, but dataset/model terms must be assessed separately.
- **[R17] UN International Day of Sign Languages:** https://www.un.org/en/observances/sign-languages-day — UN/WFD context: over 70 million Deaf people worldwide and over 300 sign languages used collectively.
- **[R18] SignDINO / self-supervised sign features, CVPR 2026:** https://openaccess.thecvf.com/content/CVPR2026/html/Gan_Learning_Effective_Sign_Features_without_Text_for_Gloss-free_Sign_Language_CVPR_2026_paper.html — relevant future research, not an MVP checkpoint dependency.

---

## 4. Product design direction — how SIGNFORGE should look and feel

### 4.1 Product personality

Make SIGNFORGE feel like a **premium research/data-operations workbench** for sign-language AI: serious, precise, humane, and modern. It is a tool for researchers and dataset stewards, not a consumer translator, not a cyberpunk demo, and not a generic “AI dashboard template.”

Visual direction:

- Clean layout with a strong information hierarchy and a calm research-lab aesthetic.
- Use the visual cues from the submitted deck (navy/indigo/lavender) but make the app more readable and functional.
- Prefer white/off-white surfaces, deep navy text, indigo actions, subtle lavender backgrounds and a small teal accent for active collection/progress.
- Use amber for pending review/warnings and red only for errors/rejections.
- Subtle borders and restrained shadows; rounded cards approximately 10–14px; consistent spacing based on an 8px grid.
- Use a readable UI font such as Inter or Geist if already available; do not add unnecessary font dependencies.
- Use consistent Lucide-style icons if the project already has an icon library.
- Charts must correspond to real data; all empty states should be designed, not hidden.
- Avoid giant gradients, excessive glassmorphism, meaningless glowing borders, random stock photographs, fake AI animations, decorative 3D avatars and generic filler copy.
- Make keyboard interaction, contrast and screen-reader labels part of the design.

### 4.2 App shell and navigation

Use a left sidebar on desktop and a responsive navigation pattern on small screens.

Recommended navigation:

1. **Overview** — current dataset health, latest model run, current collection priority.
2. **Capture** — sign prompt, consent, signer pseudonym, webcam/upload, processing and QC.
3. **Corpus** — samples, classes, signer coverage, provenance and review queue.
4. **Active Learning** — prioritized “what to record next” tasks and reasons.
5. **Models & Evaluation** — baseline/transfer runs, metrics, confusion matrix and split metadata.
6. **Export** — model-ready features and manifest for eligible reviewed samples.
7. **Project Settings** — language/domain, classes, capture settings and consent/retention policy.

Header: project selector/name, target language/domain, real processing state and a compact user/reviewer identity only if authentication actually exists. If auth is not built, do not simulate identities or display fake online status.

### 4.3 Overview dashboard

The first screen must communicate immediately:

> **The model helps decide what data to collect next.**

Suggested layout:

- Top KPI cards: configured sign classes; approved samples; unique consenting signer count; samples pending review. Derive values from the database/API.
- **Next best sample** hero card, e.g. “Collect ‘Emergency’ from a signer not yet represented.” Show why: model uncertainty, class coverage gap, signer-diversity gap. Only show numeric uncertainty when a model run generated it.
- Corpus coverage chart/heatmap: samples per sign class, with approved/pending counts distinguished.
- Quality/review panel: failed extraction, missing landmark frames, pending human review, missing provenance/consent blockers.
- Recent model runs: baseline/transfer, metric summary, dataset version, timestamp and held-out split.
- Empty state for a brand-new project: a short setup checklist; do not populate fake metrics by default.

### 4.4 Capture flow

The capture flow should feel safe and predictable; do not activate a camera without an explicit user action.

1. Select target project and sign-class prompt.
2. Enter/select a **pseudonymous signer code**; do not request real name by default.
3. Show a concise consent/allowed-use summary and required affirmative checkbox before capture.
4. Choose capture source: webcam or upload a locally recorded clip.
5. Record/preview the short clip with clear Start, Stop and Cancel controls.
6. Show actual states: Uploading/Extracting landmarks/Running QC/Saved/Needs review/Failed.
7. Show landmark preview or skeleton overlay if reliable, with the ability to turn it off.
8. Show automated QC results and actionable reasons (e.g. “right-hand landmarks missing in 38% of sampled frames”). Do not show made-up percentages.
9. Save feature sequence and metadata. Raw video is temporary and deleted after extraction by default unless explicit consent/policy says it may be retained.
10. Mark the sample `pending_review`; automated QC must not mark it linguistically approved.

### 4.5 Corpus explorer and review

- Table or accessible list with sample ID, canonical label, signer code, data source, duration/frame count, QC status, review status, split, provenance/license and created time.
- Filters: sign class, source, review state, split, quality flags and consent/provenance eligibility.
- Sample details should show the feature schema version, extractor version, normalization settings and any QC issues.
- Review actions: approve, reject, request recapture, add reviewer note. Record reviewer/status timestamp.
- Use the exact states `pending_review`, `approved`, `rejected`, `needs_recapture` (or map clearly to existing schema). Do not claim “Deaf-validated” unless an appropriate review actually happened.
- Keep technical quality and linguistic review as separate fields.

### 4.6 Active-learning page — the signature feature

This page needs to be the clearest product expression of the novelty.

Show a ranked task list. Each task should include:

- Sign/phrase label to collect.
- Suggested signer group such as “new signer” where appropriate.
- Priority score, but only with disclosed formula and components.
- Model uncertainty (if calculated), coverage gap and signer-diversity gap separately.
- Plain-language rationale: “This class has low model confidence and only one signer represented.”
- CTA such as **Record this sign** that opens Capture with the project/class/task preselected.
- Task state: pending/completed/dismissed; completion requires a corresponding sample and human review if review is part of the task definition.
- History/constraints to avoid repeatedly recommending the same task without explaining why.

Do not add a chatbot here as a substitute for ranking logic. LLM explanations are optional; the core rationale should be deterministically produced from real signals.

### 4.7 Models & evaluation

- Separate sections/tabs for **Baseline** and **Transfer/Adapter**.
- Show status: not configured, blocked (with reason), ready, running, succeeded or failed.
- Every model run must retain model type, checkpoint reference/hash where applicable, feature schema, dataset version, split IDs/strategy, seed/config, training duration and metrics.
- Display top-1 accuracy, macro-F1, confusion matrix, per-class support and unseen-signer results only where supported by the data/split.
- Before/after view must use the same frozen test set; visibly disclose added sample count and split strategy.
- If no compatible checkpoint exists, display “Transfer path not available: checkpoint compatibility not verified.” Do not silently substitute a random model.
- Never render illustrative fake metrics in the same visual style as real metrics without a `DEMO DATA` badge and explicit isolation from experiments.

### 4.8 Corpus export

Provide a simple, auditable export containing:

- Reviewed/eligible landmark sequence data (`.npz`, JSON, or a documented interoperable format).
- Label/class dictionary and language/domain metadata.
- Frame count, timestamps/sampling strategy, keypoint schema/version and normalization metadata.
- Pseudonymous signer IDs and approved optional region/dialect metadata.
- Consent/allowed-use/retention status and provenance/license manifest, but never private consent-document contents beyond the minimum required manifest fields.
- Dataset split/version and benchmark summary.
- Raw video only if explicitly permitted by consent and dataset terms; default export excludes it.

### 4.9 Microcopy and tone

Use plain, precise language. Examples:

- “The model is uncertain about this sign.”
- “Only one signer is currently represented.”
- “Record this sign from a new signer.”
- “Automated quality check passed. Linguistic review is still pending.”
- “Transfer learning is unavailable because no compatible checkpoint has been verified.”

Avoid claims like “Perfect accuracy,” “100% private,” “understands sign language,” “fully validated” or “guaranteed model improvement.”

---

## 5. Proposed MVP architecture

Use the existing repository's architecture if it already works. The below is a recommended default, not a mandate to rewrite a working project.

### Frontend

- Next.js App Router, React, TypeScript and Tailwind CSS.
- Accessible components and charting only where it adds value.
- Typed API client and shared TS types for backend responses.
- Camera flow that works only through explicit user actions and handles permission denial gracefully.

### Backend

- Python + FastAPI.
- Pydantic schemas and a modular service layer.
- SQLAlchemy/SQLModel or existing typed persistence layer.
- SQLite local-development fallback; PostgreSQL/Supabase when configured.
- CORS configured deliberately. No service-role database secret in the frontend bundle.

### ML / vision

- MediaPipe Holistic Landmarker or a verified compatible extraction path.
- NumPy/PyTorch; simple GRU or Temporal CNN baseline first.
- Candidate pretrained motion/pose checkpoint, verified before integration.
- Small trainable head/adapter initially; do not fine-tune a giant model.
- Fixed, versioned preprocessing shared by training and inference.

### Storage

- Local development feature store for `.npz`/JSON, abstracted for later Supabase Storage migration.
- Database stores metadata/paths, not unbounded binary video blobs by default.
- Ignore recordings, feature dumps, downloaded weights, local DBs and `.env` files in Git.

### Optional integrations

- Gemini API may support metadata/documentation suggestions only. No API key is required for the core product.
- ESP32/IMU is future-only unless the whole software workflow is already reliable.
- Payments, full multi-tenant SaaS and production auth are out of scope.

### Suggested repository structure

Adapt, don't blindly recreate or overwrite:

```text
signforge/
  CLAUDE.md
  README.md
  .env.example
  .gitignore
  frontend/
    app/
      page.tsx
      capture/page.tsx
      corpus/page.tsx
      active-learning/page.tsx
      models/page.tsx
      export/page.tsx
      settings/page.tsx
    components/
    lib/api.ts
    lib/types.ts
  backend/
    app/
      main.py
      api/
      core/config.py
      schemas/
      db/
      services/
        landmark_extraction.py
        preprocessing.py
        quality_checks.py
        baseline_model.py
        transfer_model.py
        uncertainty.py
        corpus_health.py
        active_learning.py
        evaluation.py
        export.py
    tests/
  data/
    README.md
    processed/  # ignored by git
  docs/
    DATA_GOVERNANCE.md
    MODEL_CARD.md
    DEMO_SCRIPT.md
```

Do not create empty scaffolding for every possible module before a single real vertical slice works.

---

## 6. Data contracts and database objects

Minimum entities; map to existing schemas if they already exist.

### Project

- `id`, `name`, `target_language`, `domain`, `created_at`, `updated_at`.

### SignClass

- `id`, `project_id`, `canonical_label`, `prompt_text`, optional `region_or_dialect_note`, `active`.

### Signer

- `id` or pseudonymous `signer_code`, `project_id`, `consent_status`, `consent_timestamp`, `allowed_use`, `retention_choice`, optional volunteered `region`, `dialect`, `handedness` if needed. Real name is not required.

### Sample

- `id`, `project_id`, `sign_class_id`, `signer_id`, `source` (`captured`, `public_dataset`, `demo_fixture`), feature path, `frame_count`, quality score/components, `quality_flags`, `technical_qc_status`, `review_status`, `reviewer_note`, `split`, `collection_round`, `feature_schema_version`, `extractor_version`, `preprocessing_config`, `provenance_license`, raw-video retention state, `created_at`.

### ModelRun

- `id`, `model_kind` (`baseline`, `transfer`), checkpoint reference/hash, feature schema, dataset version, split strategy/IDs, seed/config, metrics JSON, training duration, status, failure detail, `created_at`.

### Recommendation

- `id`, `project_id`, `sign_class_id`, suggested signer constraint/group, uncertainty score or `null`, coverage gap, signer-diversity gap, overall priority, score formula/version, explanation, status (`pending`, `completed`, `dismissed`), linked sample/run IDs, `created_at`.

### Governance/provenance

Record purpose, allowed uses, retention, consent state/timestamp, original source, dataset license/version, attribution and raw-video retention/deletion state. Avoid putting personal data or private signed consent files inside Git or demo exports.

---

## 7. Landmark processing and quality contract

1. **One extraction contract:** training, evaluation and live inference must use the same extractor version and preprocessing rules.
2. **Schema versioning:** record landmark subset/order, coordinate representation, units/scale, frame sampling, sequence length and normalization. A model checkpoint cannot be used unless its expected contract matches or an explicit validated adapter maps between them.
3. **Avoid silent schema mismatches:** MediaPipe's 553 landmarks are not interchangeable with a 128-keypoint Épée schema or INCLUDE's hands + BlazePose keypoints.
4. **Sequence rules:** fixed length or a documented variable-length strategy. The same padding/truncation/masking logic must be used in train and inference.
5. **Quality checks:** no/very short clip; extraction failures; missing hands/body; missing-frame proportion; insufficient sampled frames; implausible coordinate values; consent missing; license/provenance missing; duplicate sample where detectable.
6. **Explain QC:** every failed sample should have a readable reason. Thresholds must be configuration values and labeled as MVP heuristics until calibrated.
7. **Segmentation honesty:** prompted short clips plus trimming/QC are acceptable for the MVP; do not claim linguistically perfect automatic segmentation.
8. **Privacy:** process locally when practical; delete temporary raw video after extraction unless consent and the documented retention policy explicitly allow keeping it. Treat landmarks as sensitive derived data, not guaranteed anonymous.

---

## 8. Model plan

### 8.1 Baseline from scratch

- Input: normalized feature sequence from consented target-language samples.
- Start with a small GRU or Temporal CNN classifier.
- Train only when enough approved samples exist for the configured classes.
- Use reproducible seeds when possible; store dataset version, split and model configuration.

### 8.2 Transfer model

Before coding around any model, create a **checkpoint spike** and record the answers to the following:

- Can the checkpoint actually be downloaded/loaded today?
- What license covers code, checkpoint, and associated dataset separately?
- What keypoints/ordering/coordinate convention/sequence length does it expect?
- Does it include facial/non-manual features or only hands/body?
- What preprocessing did the original paper/repository use?
- Can the live extractor produce compatible features? If not, how will the mapping be tested?
- Is the dataset task compatible (isolated signs vs continuous signing; labels/classes/domain)?

**Candidate references:** INCLUDE and OpenHands. OpenHands explicitly warns that it is no longer actively maintained; the project can still be inspected, but don't assume that its weights are readily available or compatible. INCLUDE describes pretrained workflows using MediaPipe Hands and BlazePose. Any specific checkpoint must be tested.

If compatible, freeze most of the encoder and train a small classification head/adapter first. Compare transfer vs baseline on identical splits. If not compatible, document the blocker and do not claim the required transfer result has been completed. A feature extractor trained on the same small data is not a pretrained transfer baseline.

### 8.3 Active learning / next-sample task

For the prototype, rank **collection tasks** (for example, “collect `Emergency` from a signer not represented yet”), not only random unlabeled clips. Candidate signals:

- predictive uncertainty from a trained model (normalized entropy, low confidence or small top-two margin);
- sign-class coverage gap;
- signer-diversity gap;
- quality/review blockers if relevant.

The illustrative default formula in Section 3.8 is only a proposal. Normalize each term, keep weights configurable, show the component scores, and record the formula version. Avoid repeatedly recommending the same task with no new rationale. Never calculate or display an uncertainty score when there is no valid trained model for it.

### 8.4 Model impact loop

- Freeze a test split before active collection begins.
- Add newly recommended, reviewed samples only to the appropriate training pool.
- Retrain/re-fine-tune on the updated training data.
- Evaluate with the **same frozen test set** and same metric code.
- Show sample counts, added sample count, split strategy and metrics next to the comparison.
- An improvement is a hypothesis; show flat/worse results honestly.

---

## 9. Evaluation, data splits and metrics

Report metrics only where the dataset supports them:

- Top-1 accuracy.
- Macro-F1 (important under class imbalance).
- Confusion matrix and per-class support.
- Unseen-signer performance when the split truly holds signers out of training.
- Training time and number of new targeted samples.
- Before/after metrics on identical frozen test examples.

Rules:

- A random clip split is **not** signer-independent. Name the split accurately.
- With only 2–4 signers, true signer-independent evaluation may be low-powered or infeasible for the full 10–30 classes. State the limitation clearly instead of overstating the evidence.
- Do not compare scores to a paper unless tasks, languages, labels, dataset and split match.
- Never hardcode a sample score to make the chart look good.
- If metrics are not yet available, show “Not evaluated yet,” not 0% or an invented placeholder.

---

## 10. Corpus health and APIs

### Minimum corpus-health indicators

- configured classes vs classes with approved samples;
- sample count per class and review state;
- unique consenting signer count and signer count by class;
- landmark completeness/missing-frame rate;
- failed QC and quality-flag counts;
- consent and provenance/license eligibility;
- most uncertain/weak classes when a real model is available;
- next recommended collection task and rationale.

### Suggested FastAPI endpoints

Adapt names to the existing codebase; use typed request/response contracts.

- `GET /api/health`
- `GET/POST /api/projects`
- `GET/POST /api/sign-classes`
- `POST /api/samples/capture` (clip or landmark payload)
- `GET /api/samples` (filters: class, signer, source, review state, split)
- `POST /api/samples/{id}/review`
- `GET /api/corpus/health`
- `POST /api/models/train-baseline`
- `POST /api/models/train-transfer` (only if checkpoint verified)
- `GET /api/models/runs`
- `POST /api/active-learning/recommend`
- `POST /api/active-learning/{id}/complete`
- `POST /api/benchmark/compare`
- `GET /api/export/corpus`

Use a local fallback if Supabase isn't configured. Never place privileged database credentials in frontend environment variables exposed to the browser.

---

## 11. Privacy, consent and Deaf-community governance

- Consent must be explicit, informed, purpose-specific and recorded before capture/use.
- Use pseudonymous signer codes by default; don't collect real names unless there's a documented need and consent.
- Record permitted use and retention choice, not only a generic “accepted” boolean.
- Do not retain raw video by default after landmarks are extracted unless policy/consent explicitly allows it.
- Landmark/pose sequences can still be sensitive or re-identifiable; never say “100% anonymous” or “completely private.”
- Dataset files/weights may have separate licenses from code; preserve provenance and attribution for each source.
- Do not redistribute data or train on public data for uses that the license doesn't allow.
- Human/native/Deaf review is a real process; don't synthesize reviewer identity or validation status.
- Sign languages are independent natural languages and vary regionally; ASL is not ISL, and an English gloss is not a universal label.
- Prefer community participation and compensation when possible; do not frame contributor data as free labor.

---

## 12. Implementation workflow for Claude Code

Follow this order. Avoid attempting to implement every page at once.

### Milestone 0 — Repository reconnaissance

- Read current `CLAUDE.md`, README, manifests, git status, file tree, existing code and tests.
- Report what already exists, what runs, what fails and any local changes that must be preserved.
- Do not delete/overwrite files just to match the proposed folder tree.

### Milestone 1 — Model/checkpoint feasibility spike (early, time-boxed)

- Verify at least one realistic checkpoint option and preprocessing contract.
- Document the exact choice, evidence, license, expected input shape and adaptation path in `docs/MODEL_CARD.md` or a short research note.
- If none can be verified quickly, keep baseline path working and mark transfer as blocked/limited. No fake weights or fake metrics.

### Milestone 2 — First vertical slice

`Project + sign class → consent/pseudonymous signer → webcam/upload → landmark extraction → QC result → metadata persistence → pending review`

Run it end to end before building the full dashboard. Include a consented or clearly labelled demo fixture only if needed for fallback.

### Milestone 3 — Baseline

- Small GRU/TCN baseline using compatible target samples.
- Data split + metrics + persistence of model run.
- Unit tests for sequence shape, empty/invalid input and deterministic metric computation.

### Milestone 4 — Transfer/adapter

- Integrate only after checkpoint compatibility is verified.
- Compare with baseline using same feature contract/split.
- Document limitations and actual run results.

### Milestone 5 — Corpus health + active learning

- Compute class coverage and signer diversity from real database state.
- Add model uncertainty only where there is a trained, valid model.
- Recommend a class/signer task, explain component signals and open Capture prefilled from the recommendation.

### Milestone 6 — Review, export and benchmark

- Persist human review separately from automated QC.
- Update/retrain with newly approved samples.
- Before/after comparison on the same frozen test set.
- Export feature data plus manifest; exclude raw video by default.

### Milestone 7 — Visual polish + demo hardening

- Loading/error/empty states, responsive layout, keyboard accessibility.
- Webcam permission denial and backend unavailable states.
- A prerecorded consented or synthetic fixture path for demo fallback, clearly labelled and never treated as real benchmark data.
- Full README and demo steps.

After each milestone: run tests, summarize actual changes and remaining blockers, and ask before destructive changes or external uploads. Do not claim a test passes unless it was run.

---

## 13. Definition of done — judge-ready MVP

- [ ] Project starts locally from documented commands.
- [ ] User can select a project/sign class, use a pseudonymous signer code, confirm consent and capture/upload a short sample.
- [ ] Landmark sequence is extracted or validated; schema/version metadata are recorded.
- [ ] QC produces real, explainable flags and saves sample metadata.
- [ ] Reviewer can approve/reject/request recapture; QC and linguistic validation are distinct.
- [ ] Corpus page shows real class coverage, signer distribution, pending/rejected/QC-failed counts and governance status.
- [ ] Baseline model can train and infer on a controlled dataset, with actual metrics.
- [ ] Transfer path either uses a verified compatible pretrained checkpoint or is honestly marked as incomplete/blocked.
- [ ] Active-learning queue explains a next task using real uncertainty/coverage/diversity signals; missing signals are displayed as unavailable, not fabricated.
- [ ] Targeted reviewed samples can be added and re-evaluated using the same frozen test set.
- [ ] Model runs record sample counts, data version, checkpoint, split and metrics.
- [ ] Export contains approved feature sequences, labels and provenance/consent manifest; raw video excluded by default.
- [ ] Demo fallback exists and is labelled clearly.
- [ ] Tests, limitations, dataset/weight citations, model/data cards and demo instructions are documented.

---

## 14. 24-hour execution plan — adapt to team skills and actual schedule

The deck proposes a 24-hour MVP. This plan is a suggested sequence, not a guarantee that every advanced feature fits. Preserve the core loop over optional polish.

| Time | Focus | Exit check |
|---|---|---|
| 0–2h | Repo audit, environment, target vocabulary, task split, data schema, consent fields | Everyone can run the skeleton; decisions documented |
| 2–5h | Webcam/upload + landmark extraction + QC + persistence | One sample produces a stored feature sequence + QC output |
| 5–8h | Corpus page and review state; controlled seed data | A reviewer can approve/reject and dashboard numbers update |
| 8–11h | Baseline GRU/TCN + metrics | Baseline run recorded with proper split/counts |
| 11–13h | Checkpoint integration/adapter if compatible | Transfer run works or blocker documented honestly |
| 13–16h | Uncertainty + coverage/diversity scoring + next-task UI | Recommendation can prefill the capture form and explain why |
| 16–19h | Retraining, frozen-test benchmark, export manifest | Before/after path works or limitations shown clearly |
| 19–21h | Integration fixes and responsive UI | Full demo path stable end-to-end |
| 21–23h | Test, QA, rehearse, backup demo fixture | No critical blocker in the demo path |
| 23–24h | Final pitch/demo | Claims match actual evidence and product behavior |

**Cut order if time runs short:** wearable hardware → optional LLM → transformer experiment → complex auth/billing → advanced export formats. Do **not** cut consent, real capture/QC, honest baseline, recommendation rationale or actual evaluation.

---

## 15. Prompt to start Claude Code

Use this prompt in the Claude Code terminal after placing this file in the repository root. This file should remain the durable specification; the prompt asks Claude to act on it rather than paraphrase it.

```text
Read CLAUDE.md completely. It is the source of truth for the SIGNFORGE product, research constraints, UX direction, ML requirements, data governance and acceptance criteria.

We have been selected from Round 1 and are building the prototype now. First, inspect the existing repository, file tree, git status, README, dependencies, app architecture and tests. Preserve all existing work. Do not immediately scaffold the entire product and do not make destructive changes.

Return a concise reconnaissance report covering:
1. What already exists and what runs;
2. The smallest end-to-end path that should be implemented next;
3. The best current pretrained checkpoint candidate, with verified repository/checkpoint, license, expected landmarks/tensor shape and preprocessing—or an explicit statement that no compatible option has yet been verified;
4. Decisions/blockers that genuinely require the team;
5. A milestone plan that prioritizes a working data-generation loop over dashboard-only polish.

Then implement only the first vertical slice: select a target sign class, record consent and pseudonymous signer ID, capture or upload a short clip, extract/validate landmarks, run meaningful QC, persist metadata/provenance and show the sample in a pending-review state. Integrate this into the existing architecture rather than replacing it.

Before choosing or integrating a pretrained model, verify input-schema compatibility and current licensing. Do not call random weights pretrained. Do not invent sample data, metric values, human reviewers or completed validation. Clearly label every demo fixture. Keep target language configurable; ISL is the default proposal, not a hardcoded assumption.

Design the UI as a polished research/data-operations workbench using the deck's navy/indigo/lavender direction, strong typography, restrained cards, clear corpus tables, a prominent “What data should we collect next?” workflow, accessible controls and useful empty/error/loading states. No generic AI dashboard filler, fake charts, fake live indicators or nonfunctional buttons.

After this first slice, run the relevant tests and type/lint checks. Report the files changed, commands actually run, observed results, and anything still blocked. Do not continue to all later milestones until this slice is verified.
```

---

## 16. Rules for all future Claude Code work

- Check Git status before edits. Keep commits/small diffs so the team can review them.
- Reuse existing working modules and styles rather than restarting from scratch.
- Prefer a working thin slice with tests over large unverified code dumps.
- Read current official docs for dependencies/API changes when needed.
- No unnecessary paid API dependency; no secrets in source control.
- No raw sign recordings or large public datasets committed to Git.
- Every chart must be computed from an explicit data source or visibly identified as a non-production fixture.
- Make UI actions functional. If an action is not implemented, disable it or label it as planned—not a button that does nothing.
- Ask the team before selecting a different target language, changing public-data usage, uploading recordings to cloud services, or changing consent/retention policy.
- At the end of a completed milestone/project, teach the team each key concept in order: landmarks, coordinate normalization, temporal sequence models, transfer learning, uncertainty, active learning, data leakage/splits, macro-F1, data provenance and consent handling.

**North star:** SIGNFORGE turns model uncertainty into a targeted, reviewable data-collection plan for low-resource sign-language AI.
