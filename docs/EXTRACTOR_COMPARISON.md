# Browser and Python Extractor Comparison

**Status: NOT DONE**

No valid browser-versus-Python extractor comparison has been verified for SIGNFORGE.

The existing draft `docs/EXTRACTOR_DRIFT_NOTE.md` explicitly labels its measurements as unverified against real browser-extracted clips. The available `backend/scripts/compare_extractors.py` uses synthetic demo frames and adds generated noise; it does not run the browser and Python extractors on identical source frames. Those artifacts do not establish numerical or behavioral compatibility.

Python landmark extraction of INCLUDE clips is not evidence that the browser extractor is compatible.

## Required evidence before claiming compatibility

1. Run the actual browser and Python extractors on identical source frames, using recorded extractor/library versions and model hashes.
2. Compare frame counts, timestamp/sampling behavior, landmark ordering, coordinate conventions, missing-landmark handling, and per-landmark numeric differences.
3. Retain the source clip/frame identifiers, reproducible commands or test harness, and raw comparison results.
4. State tested limitations; do not infer general model compatibility from matching tensor shapes alone.

Until that work is completed, do not claim browser/Python compatibility, measured drift, or compatible inference inputs.
