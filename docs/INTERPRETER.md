# Interpret live: what it does, what it cannot do, and how to add a language

Written 31 Oct 2026.

## What it does
- The camera runs continuously. Every 0.6 s the last ~2.5 s of body and hand landmarks go to `POST /api/interpret`.
  That window is scored by a trained model and discarded; nothing is stored.
- **Signs.** It names a sign only from the chosen model's vocabulary (ISL: the 9 INCLUDE Greetings today).
  Below `INTERPRET_MIN_CONF` it says "not sure", and it says so too when the hands are still or out of view.
- **Hand gestures.** Rule-based, in the browser, from hand landmarks (`frontend/lib/gestures.ts`, tests: `npm run test:gestures`).
  - Covered: middle finger (flagged as offensive), thumbs up/down, OK, victory, pointing, I love you, open palm, fist.
  - These are everyday gestures, not ISL/ASL vocabulary, and they are shown on their own line.
- **Facial cues.** From MediaPipe face blendshapes: smiling, brows raised, brows lowered/frowning, mouth open.
  - In sign languages these are grammar (non-manual markers), so they are reported as cues, never as the signer's mood.
  - The face is not stored in any sample.
- **Transcript.** A sign joins the transcript after two consecutive matching reads; held gestures appear in [brackets].

## What it cannot do yet, and why
| Asked for | Status | Why |
|---|---|---|
| Hindi/ISL slang and swear words | Not possible from public data | No public ISL dataset contains them (INCLUDE, CISLR, ISL-CSLTR, Mendeley phrase sets: standard vocabulary only). The way in is to record them with consent in Collect samples, have them reviewed, and train. |
| "Any sign" | No | A recognition model can only name signs it has examples of. Out-of-vocabulary signing is often read as "not sure", but a confident wrong answer is possible (a synthetic non-sign was read as ALRIGHT at 86%). |
| Mood, or how confident the signer is | No | Landmarks cannot measure either honestly. The UI shows the model's confidence and facial cues, both labelled as such. |
| Sentences | No | The models are isolated-sign classifiers; the transcript is a sequence of signs, not a translation. |
| Our own signing | Weak | Team clips score 3–6% against INCLUDE HELLO (framing and signer shift; see docs/EXTRACTOR_COMPARISON.md). Training on INCLUDE plus reviewed team clips is the fix. |

## Add American Sign Language (Google's Kaggle "asl-signs": 250 signs, ~94k clips, landmarks already extracted)
1. Create or sign in to a Kaggle account, accept the competition rules at kaggle.com/competitions/asl-signs, and put
   your API token in `~/.kaggle/kaggle.json`. These are steps for a person: the token is your credential.
2. Download the data:
   `kaggle competitions download -c asl-signs -p data/raw/asl-signs`, then unzip it into the same folder.
3. Convert a subset to SIGNFORGE features, using an environment with pandas and pyarrow:
   `python backend/scripts/import_asl_signs.py data/raw/asl-signs data/raw/asl-signs/features --signs 30 --per-sign 60`
4. Import into a new project (target language "American Sign Language") with
   `app.services.external_dataset.import_external_dataset_from_manifest(..., auto_approve=False)`.
5. Train on it from Models & evaluation ("Train on external dataset").
6. Choose it in Interpret live under "Read signing as".

Unlike INCLUDE, asl-signs carries participant IDs, so its held-out split separates participants per sign.
