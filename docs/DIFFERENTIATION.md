# SIGNFORGE — Differentiation & Competitor Landscape

## 1. Product positioning

**SIGNFORGE is a model-guided corpus-building workbench for low-resource sign languages.**

It is **not primarily a sign-language translator**. It helps research teams and communities create more useful training data by identifying data gaps, recommending what to record next, validating samples, adapting a target model, and measuring the effect of new data.

**Core idea:**  
> The model does not just learn from the data. It helps identify what data should be collected next.

## 2. Proposed differentiation

SIGNFORGE aims to connect five capabilities in one repeatable workflow:

1. **Find data gaps:** combine model uncertainty with corpus-health signals such as class coverage, signer diversity, pose completeness, and recording quality.
2. **Recommend the next sample:** create a prioritized, explainable recording queue instead of relying only on random or broad collection.
3. **Validate and document:** include human/native/Deaf review, consent, provenance, and permitted-use metadata.
4. **Adapt a model:** reuse a compatible pretrained motion representation and fine-tune a small target-language model or adapter.
5. **Measure impact:** compare the updated model against a baseline on held-out data, preferably including unseen signers, then use the results to guide the next collection cycle.

This is a **proposed product/workflow differentiation**, not a claim that SIGNFORGE invented pose estimation, transfer learning, active learning, or sign-language datasets.

## 3. Publicly documented neighboring solutions

| Product / research | Publicly documented focus | SIGNFORGE’s proposed distinction |
|---|---|---|
| **ELAN** | Multimedia annotation and time-aligned linguistic annotation for video/audio, including sign-language corpora. | Add model-guided priorities for collecting the next recording; ELAN-compatible export could be a future integration. |
| **ASL Citizen** | Community-sourced American Sign Language dataset with prompted recordings and signer-independent research splits. | Build a reusable workflow that connects collection priorities to target-model adaptation and evaluation for a low-resource language/domain. |
| **GoSign Factory** | Guided sign-data contribution and quality review workflows. | Prioritize tasks using model uncertainty plus corpus-health and signer-coverage gaps. Do not assume GoSign lacks similar internal capabilities. |
| **CLERC / Épée** | Sign-language data infrastructure, structured data, and signer-robust benchmark resources. | Emphasize a closed loop from model uncertainty → targeted collection → adaptation → held-out evaluation. This is an area to compare carefully as the products evolve. |
| **Apple’s sign-language annotation research** | Model-assisted generation of ranked annotation candidates, glosses, and time intervals. | Focus on choosing which new recordings to collect, while also tracking corpus health and model impact—not annotation assistance alone. |
| **Kara Technologies** | Motion-captured sign-language data, signed-content generation, avatars, and Deaf-expert review. | Focus upstream on building and improving low-resource training corpora rather than primarily generating signed content. |
| **Google DeepMind SL2T** | Large-scale multilingual sign-to-text research using pose landmarks and community input. | Address the complementary long-tail problem: targeted data collection and model adaptation where data is limited. |
| **Active class selection research** | Prior work has studied choosing which sign classes and signers to acquire for sign-language recognition datasets. | Therefore, do not claim active data selection itself is novel. Differentiate through the proposed end-to-end product workflow and validate it experimentally. |

**Important:** These comparisons describe public documentation, not undisclosed internal capabilities. “SIGNFORGE adds” means the intended focus of our product, not proof that a competitor cannot do the same thing.

## 4. Best novelty statement

> **SIGNFORGE combines model-guided collection priorities, corpus-health analysis, low-resource model adaptation, human validation, and repeatable evaluation in one proposed corpus-building workflow.**

Avoid claims such as:
- “Nobody else does active learning for sign language.”
- “No sign-language datasets exist.”
- “SIGNFORGE guarantees better accuracy.”
- “Our technology is the first of its kind.”

## 5. How to prove the difference

Once the MVP is functional, compare two collection strategies under the same conditions:

- **Random collection:** add a fixed number of eligible samples chosen randomly.
- **SIGNFORGE-directed collection:** add the same number of samples selected using uncertainty, class coverage, and signer-diversity gaps.

Keep the initial training data, model setup, sample budget, and held-out evaluation set consistent. Compare:
- Macro-F1 and accuracy
- Per-class performance and confusion matrix
- Unseen-signer performance where feasible
- Number of added samples needed to reach a defined performance level
- Which signs and signer groups remain underrepresented

Do not let the sample-selection process leak into the final test set. Report the actual result even if targeted collection does **not** outperform random selection.

## 6. Implementation priority

For the hackathon MVP, prioritize the core loop:

**Capture → landmarks → baseline → verified transfer learning → uncertainty/data-gap scoring → next-sample recommendation → human review → retraining/evaluation.**

Do not build a dashboard that only looks convincing. Make each displayed recommendation traceable to real model or corpus signals, and show actual benchmark outputs.

## 7. Sources

Use the official pages/papers to verify public claims before presenting them.

1. **ELAN documentation** — https://www.mpi.nl/tools/elan/docs/manual/Pref_Introduction.html
2. **ASL Citizen dataset description (Microsoft Research)** — https://www.microsoft.com/en-us/research/project/asl-citizen/dataset-description/
3. **GoSign Factory** — https://www.gosign.ai/post/introducing-the-gosign-tasks-platform
4. **CLERC** — https://clerc.io/
5. **Apple Machine Learning Research: Sign-language annotations** — https://machinelearning.apple.com/research/sign-language-annotations
6. **Kara Technologies** — https://www.kara.tech/technology
7. **Google DeepMind: Putting Sign Language AI into Users’ Hands (SL2T)** — https://deepmind.google/blog/putting-sign-language-ai-into-users-hands/
8. **Active class selection for sign-language recognition dataset acquisition** — https://iris.univr.it/handle/11562/1125085
9. **Transfer learning for extremely low-resource Irish Sign Language (ICCV Workshops 2023)** — https://openaccess.thecvf.com/content/ICCV2023W/ACVR/html/Holmes_From_Scarcity_to_Understanding_Transfer_Learning_for_the_Extremely_Low_ICCVW_2023_paper.html

---

**One-line positioning:**  
**SIGNFORGE turns model uncertainty into a targeted data-collection plan for low-resource sign-language AI.**

---

## 8. Source check (2026-10-22, public pages only)

| Neighbour | What the cited page actually says | Does SIGNFORGE's proposed distinction hold? |
|---|---|---|
| GoSign Factory | Guided prompts, short clips, quality review, consent ("GDPR-aligned"), paid contributors. Nothing on how prompts are chosen. | Yes, per public docs: no model-guided prompt selection is described. Do not claim they lack it internally. |
| ASL Citizen | Fixed ASL-LEX vocabulary shown as a series; each signer in exactly one split (signer-independent). | Yes: collection is not adaptive. **Copy their signer-independent split rule.** |
| Apple annotation research | Pseudo-annotation of *existing* videos (ranked gloss/fingerspelling candidates with time intervals). | Yes: annotation assistance, not deciding what to record. |
| CLERC / Épée | Data infrastructure, versioning, licensing, an "Unknown-Signer Accuracy" metric. No uncertainty-guided collection described. | Yes, but closest on infrastructure + unseen-signer evaluation. Compare carefully. |
| Kara Technologies | The cited technology page (fetched today) describes AI translation, KNS notation and avatars. It does **not** mention motion capture or Deaf-expert review. | Positioning holds; **the "motion-captured / Deaf-expert review" wording in §3 is not supported by this page**. Find another source or drop it. |
| Active class selection (Bicego, Vázquez-Enríquez, Alba-Castro, 2023, LNCS, doi:10.1007/978-3-031-43148-7_26) | Chooses which sign *class* to acquire next; preliminary study of choosing *signers*. | **Our class/signer recommendation is this idea.** Cite it on the Active Learning page; the claim is the integrated, measured workflow, not the selection itself. |

Not re-checked here: ELAN, Google SL2T (summarised in CLAUDE.md §3.9) and the full text of the ACS paper (abstract only).
