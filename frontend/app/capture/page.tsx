"use client";

import type { HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type Consent, type Frame, type Project, type Sample, type SignClass, type Signer, when } from "@/lib/api";
import { EXTRACTOR, extractFromVideo, loadHolistic } from "@/lib/holistic";
import { drawSkeleton, EMPTY, smooth } from "@/lib/skeleton";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";

const MAX_RECORD_SECONDS = 5;
const MAX_UPLOAD_SECONDS = 8; // backend QC rejects clips longer than this (QC_MAX_DURATION_S)
const OPTIONAL_USES = [
  ["model_training", "Use my landmarks to train and test sign-recognition models. Without this, my samples are never used for training."],
  ["research_publication", "Include results based on my samples, only in aggregate, in research publications."],
  ["public_release", "Show a replay of my landmarks (a moving stick figure, never video) in public SIGNFORGE demos."],
] as const;
const LOW_HAND_Y = 0.9; // normalised: a wrist below this is at the bottom edge and hand tracking is lost
const LOW_HAND_FRAMES = 5;
const CODE_RE = /^[A-Z0-9][A-Z0-9-]{1,15}$/;
const section = `${card} space-y-3`;
let demoSeed = Math.floor(Date.now() / 1000); // module scope: varies per page load so DEMO clips aren't exact duplicates

type Captured = { signClassId: number; frames: Frame[]; source: "captured" | "demo_fixture"; extractor: string; sha: string; width: number; height: number };

function cameraError(e: unknown) {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError") return "Camera permission was denied. You can upload a clip or use DEMO DATA instead.";
  if (name === "NotFoundError") return "No camera was found. You can upload a clip or use DEMO DATA instead.";
  return e instanceof Error ? e.message : String(e);
}

export default function CapturePage() {
  const [project, setProject] = useState<Project | null>(null);
  const [classes, setClasses] = useState<SignClass[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const [code, setCode] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [corpusOk, setCorpusOk] = useState(false);
  const [uses, setUses] = useState<string[]>([]);
  const [signer, setSigner] = useState<Signer | null>(null);
  const [consent, setConsent] = useState<(Consent & { created_at: string }) | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [cameraOn, setCameraOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [overlay, setOverlay] = useState(true);
  const [result, setResult] = useState<Sample | null>(null);
  const [unsaved, setUnsaved] = useState<Captured | null>(null); // extracted landmarks kept if saving fails
  const [consenting, setConsenting] = useState(false);
  const [recommended, setRecommended] = useState(false); // opened from the Active learning page with ?sign=
  const [handsLow, setHandsLow] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const stopRef = useRef<null | "stop" | "cancel">(null);
  const overlayRef = useRef(true);
  const smoothed = useRef(EMPTY);
  const lowFrames = useRef(0);

  useEffect(() => {
    (async () => {
      const [p] = await api<Project[]>("/api/projects");
      if (!p) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
      const cs = await api<SignClass[]>(`/api/sign-classes?project_id=${p.id}`);
      setProject(p);
      setClasses(cs);
      const want = Number(new URLSearchParams(location.search).get("sign"));
      const pre = cs.find((c) => c.id === want);
      setClassId((pre ?? cs[0])?.id ?? null);
      setRecommended(!!pre);
    })().catch((e) => setError(`Could not load the project. ${e.message}`));
    return () => stream.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const fail = (e: unknown) => { setError(cameraError(e)); setBusy(false); setRecording(false); setStatus(""); };
  const sign = classes.find((c) => c.id === classId);

  async function recordConsent() {
    if (consenting) return; // a double-click must not create two consent records
    setError(""); setConsenting(true);
    try {
      const s = await api<Signer>("/api/signers", { body: { project_id: project!.id, code } });
      const c = await api<Consent & { created_at: string }>("/api/consents", { body: {
        signer_id: s.id, consent_version: "signforge-mvp-v1", purpose: `Build a ${project!.target_language} sign corpus (SIGNFORGE prototype)`,
        allowed_uses: ["corpus_building", ...uses], retention: "landmarks_only", confirmed: true,
      } });
      setSigner(s);
      setConsent(c);
    } catch (e) { fail(e); }
    setConsenting(false);
  }

  function draw(r: HolisticLandmarkerResult) {
    const v = video.current, c = canvas.current;
    if (!v || !c) return;
    if (c.width !== v.videoWidth || c.height !== v.videoHeight) { c.width = v.videoWidth; c.height = v.videoHeight; } // resizing reallocates the canvas
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, c.width, c.height);
    // Clips #94/#95 failed because the signing hand sat at or below the bottom edge of the frame.
    const wrists = [r.poseLandmarks[0]?.[15], r.poseLandmarks[0]?.[16]];
    lowFrames.current = wrists.some((w) => w && w.y > LOW_HAND_Y) ? lowFrames.current + 1 : 0;
    setHandsLow(lowFrames.current >= LOW_HAND_FRAMES);
    if (!overlayRef.current) return;
    smoothed.current = smooth(smoothed.current, { pose: r.poseLandmarks[0] ?? null, left: r.leftHandLandmarks[0] ?? null, right: r.rightHandLandmarks[0] ?? null });
    drawSkeleton(ctx, c.width, c.height, smoothed.current);
  }

  function toggleOverlay(on: boolean) {
    overlayRef.current = on;
    setOverlay(on);
    if (!on) canvas.current?.getContext("2d")?.clearRect(0, 0, canvas.current.width, canvas.current.height);
  }

  async function startCamera() {
    setError("");
    try {
      setStatus("Loading landmark model…");
      await loadHolistic();
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
      const v = video.current!;
      v.srcObject = stream.current;
      await v.play();
      setCameraOn(true);
      setStatus("Camera on. Video is processed in this browser and never uploaded.");
    } catch (e) { fail(e); }
  }

  function stopCamera() {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setCameraOn(false);
    setStatus("Camera off.");
  }

  async function extract(v: HTMLVideoElement, maxSeconds: number) {
    stopRef.current = null;
    smoothed.current = EMPTY;
    lowFrames.current = 0;
    v.scrollIntoView({ block: "nearest" }); // an off-screen <video> may never paint, and then no frames reach the extractor
    setRecording(true);
    const frames = await extractFromVideo(v, (t) => t >= maxSeconds || stopRef.current !== null, draw);
    setRecording(false);
    setHandsLow(false);
    return stopRef.current === "cancel" ? null : frames;
  }

  async function record() {
    const v = video.current!;
    setBusy(true); setResult(null); setUnsaved(null); setError("");
    try {
      for (let n = 3; n > 0; n--) { setStatus(`Starting in ${n}…`); await new Promise((r) => setTimeout(r, 1000)); }
      setStatus(`Recording: sign “${sign?.gloss}” now. Recording stops by itself after ${MAX_RECORD_SECONDS} s.`);
      const frames = await extract(v, MAX_RECORD_SECONDS);
      if (!frames) { setBusy(false); setStatus("Cancelled. Nothing was saved."); return; }
      const { sha256 } = await loadHolistic();
      await submit({ signClassId: classId!, frames, source: "captured", extractor: EXTRACTOR, sha: sha256, width: v.videoWidth, height: v.videoHeight });
    } catch (e) { fail(e); }
  }

  async function upload(file: File) {
    const v = video.current!;
    setBusy(true); setResult(null); setUnsaved(null); setError("");
    const url = URL.createObjectURL(file); // stays in this browser: only landmarks are sent
    try {
      if (cameraOn) stopCamera();
      setStatus("Loading landmark model…");
      const { sha256 } = await loadHolistic();
      v.src = url;
      await v.play();
      setStatus(`Extracting landmarks from the clip (only the first ${MAX_UPLOAD_SECONDS}s are used)…`);
      const frames = await extract(v, MAX_UPLOAD_SECONDS);
      const { videoWidth: width, videoHeight: height } = v;
      v.pause();
      v.removeAttribute("src");
      if (!frames) { setBusy(false); setStatus("Cancelled. Nothing was saved."); return; }
      await submit({ signClassId: classId!, frames, source: "captured", extractor: EXTRACTOR, sha: sha256, width, height });
    } catch (e) { fail(e); } finally { URL.revokeObjectURL(url); }
  }

  async function useDemo() {
    setBusy(true); setResult(null); setUnsaved(null); setError("");
    try {
      const d = await api<{ extractor: string; width: number; height: number; frames: Frame[] }>(
        `/api/demo-frames?class_index=${classes.findIndex((c) => c.id === classId)}&seed=${demoSeed++}`);
      await submit({ signClassId: classId!, frames: d.frames, source: "demo_fixture", extractor: d.extractor, sha: "", width: d.width, height: d.height });
    } catch (e) { fail(e); }
  }

  async function submit(c: Captured) {
    if (!c.frames.length) { // nothing to check or store; saving it would only add an empty row to the corpus
      setError("No video frames were processed, so nothing was saved. Keep this tab visible while recording or uploading, and try again.");
      setStatus("Failed."); setBusy(false);
      return;
    }
    setStatus(`Running the automated check on ${c.frames.length} frames…`);
    const duration = c.frames.at(-1)?.t || 0;
    try {
      const s = await api<Sample>("/api/samples/capture", { body: {
        project_id: project!.id, sign_class_id: c.signClassId, signer_id: signer!.id, consent_id: consent!.id,
        source: c.source, extractor: c.extractor, extractor_model_sha: c.sha,
        fps: duration > 0 ? c.frames.length / duration : 30, width: c.width, height: c.height,
        mirrored: false, frames: c.frames,
      } });
      setResult(s);
      setUnsaved(null);
      setStatus("Saved. Waiting for human review.");
    } catch (e) {
      setUnsaved(c);
      setError(`Not saved: ${e instanceof Error ? e.message : e} The ${c.frames.length} extracted frames are kept on this page, so you can retry without recording again.`);
      setStatus("Failed.");
    }
    setBusy(false);
  }

  const canConsent = project && classId && CODE_RE.test(code) && understood && corpusOk;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Capture a consented sample</h1>
        <p className="mt-1 text-sm">The camera turns on only when you press Start camera. Landmarks are extracted in this browser and the raw video is never uploaded.</p>
      </header>
      {error && <ErrorBanner message={error}
        {...(unsaved ? { retryLabel: "Retry saving", onRetry: () => { setError(""); setBusy(true); submit(unsaved); } }
          : !project ? { onRetry: () => location.reload() } : {})} />}

      <section className={section} aria-labelledby="s1">
        <h2 id="s1" className="font-semibold">1. Sign and signer</h2>
        <label className="block text-sm">Sign to record
          <select className="mt-1 block w-full max-w-sm rounded-lg border border-lavender p-2" value={classId ?? ""} disabled={busy}
                  onChange={(e) => setClassId(Number(e.target.value))}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.gloss}</option>)}
          </select>
        </label>
        {project && !classes.length && <p className="text-sm text-amber-900">This project has no sign classes yet, so nothing can be recorded. Add classes with <code>scripts/seed.py</code> or the API.</p>}
        {sign?.dialect_note && <p className="text-xs text-indigo">Note: {sign.dialect_note}</p>}
        <label className="block text-sm">Pseudonymous signer code (not a name), e.g. S-01
          <input className="mt-1 block w-full max-w-sm rounded-lg border border-lavender p-2 uppercase" value={code} disabled={!!consent}
                 onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="S-01" aria-describedby="code-help" />
        </label>
        <p id="code-help" className="text-xs">2–16 characters: A–Z, 0–9 and “-”. Never enter a real name.</p>
      </section>

      <section className={section} aria-labelledby="s2">
        <h2 id="s2" className="font-semibold">2. Consent (required before recording)</h2>
        {consent ? (
          <p className="text-sm">Consent recorded for <strong>{signer?.code}</strong> at {when(consent.created_at)} ·
            allowed uses: {consent.allowed_uses.join(", ").replaceAll("_", " ")} · retention: landmarks only, raw video not retained.
            {!consent.allowed_uses.includes("model_training") && <span className="mt-1 block text-amber-900">This signer didn&apos;t allow model training, so their samples will never be used to train or test a model.</span>}</p>
        ) : (
          <>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
              <span>I understand that body and hand landmark positions are extracted from the video in this browser. The raw video is not uploaded or stored. Landmarks can still be sensitive, identifying personal data.</span></label>
            <label className="flex gap-2 text-sm"><input type="checkbox" checked={corpusOk} onChange={(e) => setCorpusOk(e.target.checked)} />
              <span>I agree that my landmarks can be stored in this {project?.target_language ?? ""} corpus. (Required)</span></label>
            {OPTIONAL_USES.map(([k, label]) => (
              <label key={k} className="flex gap-2 text-sm"><input type="checkbox" checked={uses.includes(k)}
                onChange={(e) => setUses(e.target.checked ? [...uses, k] : uses.filter((u) => u !== k))} /> <span>Optional: {label}</span></label>
            ))}
            <button className="rounded-lg bg-indigo px-4 py-2 text-white disabled:opacity-60" disabled={!canConsent || consenting} onClick={recordConsent}>{consenting ? "Recording consent…" : "Record consent"}</button>
          </>
        )}
      </section>

      <section className={section} aria-labelledby="s3">
        <h2 id="s3" className="font-semibold">3. Record or upload{sign && <> · prompt: <span className="text-indigo">“{sign.gloss}”</span></>}
          {recommended && <span className="ml-2 rounded-md bg-teal/15 px-2 py-0.5 text-xs font-normal text-teal">Recommended by the next-sample queue</span>}</h2>
        <div className="relative aspect-video w-full max-w-2xl overflow-hidden rounded-lg bg-navy">
          {/* Mirrored for display only; extraction reads the un-mirrored frames. */}
          <video ref={video} playsInline muted className={`absolute inset-0 h-full w-full object-contain ${cameraOn ? "-scale-x-100" : ""}`} />
          <canvas ref={canvas} aria-hidden className={`absolute inset-0 h-full w-full object-contain ${cameraOn ? "-scale-x-100" : ""}`} />
          {cameraOn && <div aria-hidden className="pointer-events-none absolute inset-x-[3%] top-[4%] bottom-[14%] rounded-lg border-2 border-dashed border-lavender/70" />}
          {handsLow && cameraOn && <p role="status" className="absolute inset-x-0 bottom-0 bg-amber-100 p-2 text-center text-sm font-medium text-amber-950">A hand is at the bottom of the frame. Raise your hands so they stay inside the dashed box.</p>}
          {!cameraOn && !busy && <p className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-lavender">Camera is off</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {cameraOn
            ? <button className="rounded-lg border border-indigo px-3 py-2 disabled:opacity-60" disabled={busy} onClick={stopCamera}>Stop camera</button>
            : <button className="rounded-lg border border-indigo px-3 py-2 disabled:opacity-60" disabled={!consent || busy} onClick={startCamera}>Start camera</button>}
          {recording ? (
            <>
              <button className="rounded-lg bg-teal px-3 py-2 text-white" onClick={() => (stopRef.current = "stop")}>Stop and save</button>
              <button className="rounded-lg border border-red-700 px-3 py-2 text-red-800" onClick={() => (stopRef.current = "cancel")}>Cancel</button>
            </>
          ) : (
            <button className="rounded-lg bg-indigo px-3 py-2 text-white disabled:opacity-60" disabled={!consent || busy || !cameraOn} onClick={record}>Record sign</button>
          )}
          <label className={`rounded-lg border border-indigo px-3 py-2 focus-within:ring-2 focus-within:ring-indigo ${!consent || busy ? "opacity-60" : "cursor-pointer"}`}>Upload a clip
            <input type="file" accept="video/*" className="sr-only" disabled={!consent || busy} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
          </label>
          <button className="rounded-lg border border-amber-600 px-3 py-2 text-amber-900 disabled:opacity-60" disabled={!consent || busy} onClick={useDemo}>Use DEMO DATA (no webcam)</button>
          <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={overlay} onChange={(e) => toggleOverlay(e.target.checked)} /> Show landmark overlay</label>
        </div>
        <p className="text-xs">Sit back so your head and both hands stay inside the dashed box, and sign above your waist. Hands that drop out of the frame are the most common reason a clip fails the automated check.</p>
        {!consent && <p className="text-xs">Record consent first. Recording, uploading and DEMO DATA stay off until then.</p>}
        <p aria-live="polite" className="text-sm font-medium">{status}</p>
      </section>

      {result && (
        <section className={section} aria-labelledby="s4">
          <h2 id="s4" className="font-semibold">4. Result: sample #{result.id}
            {result.source === "demo_fixture" && <DemoBadge className="ml-2" />}</h2>
          <p className="text-sm">
            {result.qc_passed ? "Passed the automated check." : "Failed the automated check."} Landmark completeness {(result.quality_score * 100).toFixed(0)}%
            {" "}· {result.frame_count} frames · {result.qc_metrics.duration_s}s
          </p>
          {result.quality_flags.length > 0 && (
            <ul className="list-disc pl-5 text-sm">{result.quality_flags.map((f) => <li key={f.code}><strong>{f.severity === "error" ? "Problem" : "Warning"}:</strong> {f.message}</li>)}</ul>
          )}
          {result.quality_flags.some((f) => f.code === "hands_missing" || f.code === "out_of_frame") && (
            <p className="text-sm text-amber-900">To retake: sit further back and keep both hands inside the dashed box the whole time, in good light.</p>
          )}
          <p className="text-sm">Saved and <span className="rounded-md bg-amber-100 px-2 py-0.5 text-amber-950">waiting for human review</span>. The automated check can&apos;t tell whether the sign itself is correct; a reviewer decides that.</p>
          <Link href="/corpus" className="text-sm text-indigo underline">Review it in Corpus & review →</Link>
        </section>
      )}
    </div>
  );
}
