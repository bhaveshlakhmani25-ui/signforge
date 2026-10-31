# SIGNFORGE

AI-powered low-resource sign-language corpus builder: *from a few native signs to a model-ready corpus.*
Team Claude's Clan: Tashvi Adhlakha (lead), Bhavesh Lakhmani, Reuben Raju, Aakarshi Dwivedi. Project rules: [CLAUDE.md](CLAUDE.md).

## Status
| Works | Not built yet |
|---|---|
| Consent → capture (webcam / uploaded clip / DEMO DATA, with stop/cancel) → in-browser landmarks → validation → QC (incl. hand dropout, left/right swap, exact duplicates) → stored as `pending_review` → human review: approve / reject / request recapture, with reviewer role → corpus coverage per class → **delete a sample / withdraw consent** (blocks capture and training, optionally erases the landmarks; see [docs/DATA_GOVERNANCE.md](docs/DATA_GOVERNANCE.md)) → **baseline GRU** (frozen test split, signer-independent when ≥3 signers, recorded runs with accuracy / macro-F1 / confusion matrix; DEMO DATA runs kept separate) | Pretrained transfer (OpenHands checkpoint **not verified**, see [docs/MODEL_CARD.md](docs/MODEL_CARD.md)), the real next-sample ranker and `/api/queue`, benchmark data, export, authentication, migrations. **Pages built against agreed formats:** Active learning (shows DEMO DATA rows until `/api/queue` exists) and Benchmark (reads `frontend/public/benchmark/benchmark.json`; "Not evaluated yet" until it exists). Browser test results: [docs/BROWSER_TESTS.md](docs/BROWSER_TESTS.md) |

## Run locally (macOS, Python 3.14, Node 24)
Terminal 1, backend:
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/seed.py --demo   # ISL demo project, 10 placeholder glosses, 90 DEMO DATA samples (3 synthetic signers x 3 per sign)
.venv/bin/uvicorn app.main:app --port 8000
```
Terminal 2, frontend:
```bash
cd frontend && npm install && npm run setup:models   # copies MediaPipe WASM + downloads holistic_landmarker.task (13.7 MB)
npm run dev   # http://localhost:3000
```
Schema changes are not migrated: after pulling a model change, move `backend/signforge.db` and `data/processed/` aside and re-run `seed.py`.
shortcut: no Alembic migrations yet; add them before real (non-demo) collection starts.

## Deploying

Two services: the FastAPI backend and the Next.js frontend.

- **Backend:** `cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  Set `CORS_ORIGINS` to the frontend's public URL (comma-separated for several). `DATABASE_URL` defaults to a SQLite file and
  `SIGNFORGE_DATA_DIR` to `data/processed`; both need a persistent disk, or the corpus is lost on restart. There are no
  database migrations: new columns are added at startup.
- **Frontend:** set `NEXT_PUBLIC_API_URL` to the backend's public URL **before** `npm run build` (it is baked into the build),
  then `npm run build && npm start`. The build downloads the MediaPipe model (13.7 MB) on first run via `prebuild`.
- **Hosted backend (Hugging Face Space):** `python3 deploy/hf-space/build_space.py` assembles `deploy/space/` (git-ignored):
  the backend plus a public-safe copy of the data (external datasets and DEMO DATA only; team-recorded clips, their
  signers, consents and review records are left out). Upload it with `hf upload <user>/signforge-api deploy/space . --repo-type space`,
  then set the repository variable `API_URL` to `https://<user>-signforge-api.hf.space` and re-run the Pages workflow.
  The Space has no login and its disk resets on restart.
- **HTTPS is required.** Browsers only allow the camera on `https://` pages or `localhost`, so Capture and Interpret
  will not start on a plain `http://` host.
- Trained model weights and imported datasets live under `SIGNFORGE_DATA_DIR` and are not in git: a fresh deploy starts with an
  empty corpus and no trained model until data is imported and a model is trained.

Tests: `cd backend && .venv/bin/pytest` · `cd frontend && npm run typecheck && npm run lint && npm run build`

## Landmark contract
- Extractor: `@mediapipe/tasks-vision@1.1.0` HolisticLandmarker in the browser; the model's sha256 is computed at load and stored on every sample (`e2dab611…c3f8` at time of writing). Raw video never leaves the browser.
- Stored per sample: un-mirrored, un-normalised `(T,75,3)` points (33 pose + 21 left hand + 21 right hand, missing parts zero-filled), presence mask, timestamps, fps, width, height. Schema `mp-holistic-75-xyz-v1`.
- Model preprocessing (`model_input()` in `backend/app/services/preprocessing.py`, shared by every model) replicates AI4Bharat OpenHands exactly: 27-point subset, x/y only, clip-level shoulder centre/scale, 10 fps sampling. See the plan's compatibility contract (V1–V8, U1–U5) for what is verified vs assumed.
- Known extractor gap: the OpenHands checkpoint was trained on *legacy* MediaPipe Holistic, which is not installable on Python 3.14. Drift will be measured, not assumed away.

## Honesty rules
DEMO DATA is synthetic, badged in the UI and excluded from listings/evaluation by default. Automated QC is not linguistic validation. Model metrics shown in the app are real run outputs; runs on DEMO DATA are badged and only prove the pipeline works. The real baseline trains only on approved samples whose signer allowed model training.

## Citations
AI4Bharat OpenHands (Apache-2.0, unmaintained): https://github.com/AI4Bharat/OpenHands · MediaPipe Holistic Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/holistic_landmarker

## Competitive positioning
See [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md), including a 2026-10-22 check of each competitor claim against its source. Choosing which sign/signer to collect next has prior work (Bicego et al., 2023, *Active Class Selection for Dataset Acquisition in Sign Language Recognition*); SIGNFORGE's claim is the integrated, measured workflow, not the selection idea.

## How we work (Claude Code)
The repo enables the **ponytail** plugin in `.claude/settings.json`; Claude Code offers to install it when a teammate opens the project. It makes Claude take the smallest change that fully solves a task, keep tests with new logic, and mark any known limit in code as `shortcut: <limit>, <when to upgrade>`.
- `/ponytail lite | full | ultra`: how hard to push back on scope (default `full`).
- `/ponytail-debt`: list every `shortcut:` left in the code: our to-do list before real data collection.
- `/ponytail-review`: review a change for bugs, safety and unneeded code before merging.

### GitHub Pages without a backend (public read-only demo)

If the repo variable `API_URL` is unset, the Pages build runs in snapshot mode: it reads frozen JSON from `frontend/public/snapshot/` instead of calling an API.
It holds external datasets and DEMO DATA only (never team clips, signers, consents or reviews) and is read-only; recording, review, training and the live camera need the backend.
Refresh it after changing the data or models:

```bash
python deploy/hf-space/build_space.py
backend/.venv/bin/python deploy/pages/export_snapshot.py   # then commit frontend/public/snapshot
```

Set `API_URL` to a hosted backend later and the Pages site switches to live mode on its next deploy.
