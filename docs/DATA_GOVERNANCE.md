# Data governance (prototype)

**Consent first.** No capture control is enabled until a consent record exists for the signer. The API refuses a sample (HTTP 403) unless its consent is active, belongs to that signer and includes `corpus_building`. Each record stores: version, purpose, allowed uses (`corpus_building` required; `model_training`, `research_publication` optional), retention (`landmarks_only`), `raw_video_retained=false`, timestamp.

**Pseudonyms only.** Signers and reviewers are codes like `S-01`; the API rejects anything that is not 2–16 characters of A–Z, 0–9 and `-`, which blocks typical names. Handedness is optional and only if volunteered.

**Privacy-by-pose, with limits.** Video is processed in the browser; only landmark coordinates are sent and stored. Landmarks are *not* anonymous: movement style and body proportions can identify a person. Treat stored `.npz` files as personal data. They live in `data/processed/` (git-ignored) and are never committed.

**Two separate gates.**
1. Automated technical QC: did we capture clean landmarks? (empty, too short/long, body missing, hands missing, intermittent hand dropout, left/right hand swap, out of frame, aspect ratio, exact duplicate).
2. Human review: approve / reject / request recapture (`approved`, `rejected`, `needs_recapture`; new samples start as `pending_review`), recorded with the reviewer's self-declared role. Only a native signer or Deaf community member's approval counts as linguistic validation; a non-signer team member's approval does not, and the UI says so.

**Demo data.** `source=demo_fixture` samples are synthetic, labelled DEMO DATA everywhere and excluded from default listings and any evaluation.

**Not yet implemented.** Consent withdrawal and deletion of a signer's samples, export manifest, dataset versioning. Do not collect from real signers beyond a demo until withdrawal exists.

**Sign glosses.** The 10 seeded ISL glosses are placeholders and must be confirmed with a native ISL signer; sign languages are distinct languages and ISL signs must not be borrowed from ASL.
