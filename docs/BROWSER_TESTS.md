# Browser tests: upload and stall watchdog

Run 31 Oct 2026 in the Claude Code built-in browser pane (Chromium), backend :8000 and frontend :3000, on branch `bhavesh/frontend-delete`.

## Method
No file picker or camera is available to the agent, so the Capture page was driven from the console:
1. Record consent for a throwaway signer (`BT-01`, corpus building only).
2. Make a 3 s synthetic clip: draw on a 1280×720 `<canvas>`, record it with `MediaRecorder` to `video/webm`, wrap it in a `File`.
3. Put the file on the Upload input with `DataTransfer` and dispatch `change`. Wait for "Result: sample #…".
4. Repeat step 2–3 a second time (the second upload previously failed when MediaPipe timestamps restarted at 0).
5. Clean up: withdraw `BT-01`'s consent with delete on.

## Results
| Check | Result |
|---|---|
| Upload path (`upload()` → `extractFromVideo` → `/api/samples/capture`), 7 s clip | Saved: 149 frames over 6.9 s; extraction ran on every frame |
| Second upload in a row (shared MediaPipe timestamp counter `lastMs`) | Saved: 81 frames, no timestamp error |
| Stall watchdog: video paused 2 s into a 7 s upload | Recording ended **3.2 s after the pause** with the 56 frames captured so far, and the video had not ended, so the watchdog (not the `ended` event) stopped it |
| Automated check on synthetic clips | Failed (no body, no hands), as expected: the canvas has no person in it |

**Earlier 0-frame runs.** The first attempts got 0 frames: `requestVideoFrameCallback` never fired while the `<video>` was below the fold in a hidden browser pane. After scrolling the video into view, frames arrived. The exact browser rule was not pinned down, so two fixes went in:
- Capture scrolls the video into view when a recording or upload starts.
- A 0-frame result is no longer saved as an empty sample; the user is told to keep the tab visible and try again.

## Still not verified (needs a person at a real browser)
- Upload of a real clip of a person, twice in a row, with landmarks extracted.
- Stall watchdog during a webcam recording (e.g. unplug the camera or revoke permission mid-recording: the recording should end within about 3 s and keep the frames captured so far).
- Stop and Cancel during an upload.
- Stall watchdog with a real webcam (only a paused file was tested).
- The low-hands warning and the dashed framing box on a real webcam.
Akarshi's acceptance pass should cover these; log results here.
