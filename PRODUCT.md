# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Primary (landing page): hackathon judges** at the next-round demo. In about two minutes they need to understand the problem, the loop, and what is actually built, and see honest evidence before the team hands over to the live dashboard.
- **Product users (dashboard):** dataset builders running a collection project for a low-resource sign language, such as research labs, Deaf organisations and accessibility teams. Today these are the team members recording and reviewing clips. Native/Deaf reviewers are part of the design, but are not yet using it.

## Product Purpose
SIGNFORGE is a data-sufficiency engine for low-resource sign languages. It collects consented, quality-checked sign data and tells the community, sign by sign, whether there is enough data and what to record next.

For each clip and each sign, it answers three questions:
1. Is this clip good?
2. Is this sign enough?
3. What should we record next?

Success for the hackathon is the core loop working end to end: capture → landmarks → quality check → match score → triage → train → uncertainty and sufficiency → next-sign recommendation → retrain → before/after evaluation. Every claim the team makes must match what the product shows.

## Positioning
The novelty is the workflow, not any single algorithm: model evidence drives data collection. SIGNFORGE turns model uncertainty plus coverage and signer-diversity gaps into a ranked, reviewable "record this sign next" plan.

It is not a translator, not just a recorder, and not a validated ISL corpus. Neighbours do parts of this: ELAN annotates, ASL Citizen and GoSign collect, and Google SL2T translates at scale. Positioning is phrased as SIGNFORGE's emphasis, never as "nobody else does this".

## Operating Context
- **Demo setting:** a laptop at the hackathon venue, with a webcam, possibly unreliable Wi-Fi, and the backend running locally.
- **Data:**
  - INCLUDE (ISL, Zenodo 4010759, CC BY 4.0). The Greetings subset (9 signs, 190 clips) is imported as `external_dataset` in its own project.
  - The team's own consented recordings are in the "ISL demo" project.
  - Synthetic DEMO DATA is used only for pipeline demos.
- **Workflow:** consent → record or upload → automated check → model check (triage) → human review → train → queue.

## Capabilities and Constraints
**Built:**
- Consented capture with pseudonymous signer codes.
- In-browser MediaPipe landmarks; raw video is never uploaded.
- Automated QC.
- Human review, kept separate from QC and from model triage.
- Delete and consent withdrawal.
- GRU baseline.
- INCLUDE import into its own project.
- Session-grouped frozen splits.
- Temperature calibration.
- `/predict` match scores and triage, with auto-accept OFF until a model passes its reliability check.
- Ranker queue.
- Benchmark endpoint.
- Project switcher.

**Not built:**
- Transfer learning: blocked, no verified checkpoint.
- The simulation/benchmark data (Reuben).
- Sufficiency status.
- The Capture match-score card.
- Authentication and migrations.

**Terminology:** sign, sample, automated check, model check, human review, linguistic validation, DEMO DATA, "matches the dataset at X%".

## Brand Commitments
- **Name and team:** the name is SIGNFORGE. The team is Team Claude's Clan: Tashvi Adhlakha (Team Leader), Bhavesh Lakhmani, Reuben Raju and Aakarshi Dwivedi. Keep these spellings.
- **Tagline from the deck:** "From a few native signs to a model-ready corpus."
- **Deck identity:** navy, indigo and lavender, recorded in DESIGN.md.
- **Voice:** plain, precise and humane. Never say "perfect accuracy", "100% private", "understands sign language", "validated corpus" or "signer-independent", unless the evidence supports it.
- **Change:** the hero line "AI cannot learn what we never collect." is to be replaced (user request, 31 Oct 2026).

## Evidence on Hand
Use live numbers from the backend API, each with its source and caveat, and "Not evaluated yet" when missing.

As of 31 Oct 2026:
- **INCLUDE run #4:**
  - 53% top-1 and macro-F1 0.50 on 32 held-out-session test clips.
  - Calibration failed (test ECE 0.42 → 0.20, against a 0.10 limit).
- **Team HELLO recordings:** match INCLUDE HELLO at only 3–6%. This is signer and recording shift. Present it as a finding, not a failure to hide.
- **Extractor comparison:** browser vs Python give the same top-1 on 16 of 18 clips (`docs/EXTRACTOR_COMPARISON.md`).

There are no testimonials, users, partners, pricing or deployments. Never invent them.

## Product Principles
1. Every number shown is computed from a named source, or labelled DEMO DATA or "Not evaluated yet".
2. The automated check, the model check and human or linguistic review are always separate. Deaf/native review stays part of the design: models reduce the review load, they don't replace it.
3. Consent and allowed use are product features, not footer text.
4. Show flat or worse results as plainly as wins.
5. A corpus builder first: the model is a research instrument for deciding what to collect.

## Accessibility & Inclusion
The product serves Deaf communities, so the target is WCAG 2.1 AA:
- keyboard operation;
- visible focus;
- status always in words, never colour alone;
- reduced-motion respected (the skeleton replay shows a still frame).

Sign languages are independent languages, and an English gloss is a label, not a translation.
