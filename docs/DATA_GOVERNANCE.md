# Data governance (prototype)

**Consent first.** No capture control is enabled until a consent record exists for the signer. The API refuses a sample (HTTP 403) unless its consent is active, belongs to that signer and includes `corpus_building`. Each record stores: version, purpose, allowed uses (`corpus_building` required; `model_training`, `research_publication` optional), retention (`landmarks_only`), `raw_video_retained=false`, timestamp.

**Pseudonyms only.** Signers and reviewers are codes like `S-01`; the API rejects anything that is not 2–16 characters of A–Z, 0–9 and `-`, which blocks typical names. Handedness is optional and only if volunteered.

**Privacy-by-pose, with limits.** Video is processed in the browser; only landmark coordinates are sent and stored. Landmarks are *not* anonymous: movement style and body proportions can identify a person. Treat stored `.npz` files as personal data. They live in `data/processed/` (git-ignored) and are never committed.

**Two separate gates.**
1. Automated technical QC: did we capture clean landmarks? (empty, too short/long, body missing, hands missing, intermittent hand dropout, left/right hand swap, out of frame, aspect ratio, exact duplicate).
2. Human review: approve / reject / request recapture (`approved`, `rejected`, `needs_recapture`; new samples start as `pending_review`), recorded with the reviewer's self-declared role. Only a native signer or Deaf community member's approval counts as linguistic validation; a non-signer team member's approval does not, and the UI says so.

**Demo data.** `source=demo_fixture` samples are synthetic, labelled DEMO DATA everywhere and excluded from default listings and any evaluation.

**Deletion and withdrawal.**
- *Delete a sample* (Corpus → Details & review → Delete this sample, or `DELETE /api/samples/{id}`): erases the landmark `.npz`, its review events and its row.
- *Withdraw consent* (Corpus → Signers & consent, or `POST /api/consents/{id}/withdraw` with `{"delete_samples": true|false}`): sets the consent to `withdrawn`, which immediately blocks new captures (403), model training and public replay for that consent. With `delete_samples` it also erases every sample recorded under it. Repeating the call is safe.
- Limits: models already trained on deleted samples are not retrained (their run records keep the sample ids but not the data); deleting a frozen-test-set sample means older results can no longer be reproduced; files already exported are outside the app's control. Deleted data leaves no tombstone.

**Not yet implemented.** Export manifest, dataset versioning, authentication (anyone who can reach the API can delete or withdraw), database migrations.

**Sign glosses.** The 10 seeded ISL glosses are placeholders and must be confirmed with a native ISL signer; sign languages are distinct languages and ISL signs must not be borrowed from ASL.
