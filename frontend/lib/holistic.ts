import { FilesetResolver, HolisticLandmarker, type HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import type { Frame } from "./api";

export const EXTRACTOR = "@mediapipe/tasks-vision@1.1.0 HolisticLandmarker (float16)";
const MODEL_URL = "/models/holistic_landmarker.task"; // fetched by `npm run setup:models`

let loaded: Promise<{ landmarker: HolisticLandmarker; sha256: string; delegate: "GPU" | "CPU" }> | null = null;
// The landmarker is shared by every recording, and MediaPipe rejects a timestamp <= the last one it saw.
// Uploaded clips restart at 0 s, so the counter must outlive a single recording.
let lastMs = -1;
const STALL_MS = 3000; // no new video frame for this long ends the recording with what was captured

export function loadHolistic() {
  loaded ??= (async () => {
    const buf = new Uint8Array(await (await fetch(MODEL_URL)).arrayBuffer());
    const digest = await crypto.subtle.digest("SHA-256", buf);
    const sha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
    const vision = await FilesetResolver.forVisionTasks("/models");
    // GPU runs the model several times faster than CPU, so more frames reach the tracker and fast hand movement
    // is not lost between frames. Confidence thresholds stay at MediaPipe's defaults, the same as the INCLUDE import.
    for (const delegate of ["GPU", "CPU"] as const) {
      try {
        const landmarker = await HolisticLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetBuffer: buf, delegate },
          runningMode: "VIDEO",
          outputFaceBlendshapes: true, // facial cues for the interpreter; stored samples never include the face
        });
        return { landmarker, sha256, delegate };
      } catch (e) {
        if (delegate === "CPU") throw e; // no WebGL: fall back to CPU, and only fail if that fails too
      }
    }
    throw new Error("unreachable");
  })();
  loaded.catch(() => (loaded = null)); // allow retry after a failed load
  return loaded;
}

export function toFrame(r: HolisticLandmarkerResult, t: number): Frame {
  // Coordinates stay as MediaPipe returns them: normalised, un-mirrored (plan D4). Mirroring is CSS-only.
  const pose = r.poseLandmarks[0];
  const hand = (h?: { x: number; y: number; z: number }[]) => (h?.length ? h.map((p) => [p.x, p.y, p.z]) : null);
  return {
    t,
    pose: pose?.length ? pose.map((p) => [p.x, p.y, p.z, p.visibility ?? 0]) : null,
    left_hand: hand(r.leftHandLandmarks[0]),
    right_hand: hand(r.rightHandLandmarks[0]),
  };
}

/** Runs extraction on every decoded frame of a playing <video> until `shouldStop` or the video ends. */
export async function extractFromVideo(video: HTMLVideoElement, shouldStop: (t: number) => boolean,
                                       onResult?: (r: HolisticLandmarkerResult) => void): Promise<Frame[]> {
  const { landmarker } = await loadHolistic();
  const frames: Frame[] = [];
  let t0: number | null = null;
  let lastT = 0, lastFrameAt = performance.now(), finished = false;
  return new Promise((resolve) => {
    const done = () => {
      if (finished) return;
      finished = true;
      clearInterval(watchdog);
      resolve(frames);
    };
    // Frames can stop arriving (camera unplugged, permission revoked, stalled file). Without this, Stop/Cancel
    // are only seen inside a frame callback and the recording would wait forever. Hidden tabs pause on purpose.
    const watchdog = setInterval(() => {
      if (shouldStop(lastT) || (!document.hidden && performance.now() - lastFrameAt > STALL_MS)) done();
    }, 250);
    video.addEventListener("ended", done, { once: true });
    const step = (_now: number, meta: VideoFrameCallbackMetadata) => {
      if (video.ended || finished) return;
      t0 ??= meta.mediaTime;
      const t = meta.mediaTime - t0;
      lastT = t;
      lastFrameAt = performance.now();
      if (shouldStop(t)) return done();
      const ms = Math.max(lastMs + 1, Math.round(meta.mediaTime * 1000)); // detectForVideo needs increasing timestamps
      lastMs = ms;
      const r = landmarker.detectForVideo(video, ms);
      frames.push(toFrame(r, t));
      onResult?.(r);
      video.requestVideoFrameCallback(step);
    };
    video.requestVideoFrameCallback(step);
  });
}

/** Tracks a live <video> for the preview (no frames kept) until `shouldStop()` returns true. */
export async function trackVideo(video: HTMLVideoElement, shouldStop: () => boolean, onResult: (r: HolisticLandmarkerResult) => void) {
  const { landmarker } = await loadHolistic();
  // Same clock as extractFromVideo (the video's own media time), so recording continues the preview's timeline smoothly.
  const step = (_now: number, meta: VideoFrameCallbackMetadata) => {
    if (shouldStop() || !video.srcObject) return;
    const ms = Math.max(lastMs + 1, Math.round(meta.mediaTime * 1000));
    lastMs = ms;
    onResult(landmarker.detectForVideo(video, ms));
    video.requestVideoFrameCallback(step);
  };
  video.requestVideoFrameCallback(step);
}
