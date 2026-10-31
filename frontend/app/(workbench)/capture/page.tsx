"use client";

import type { HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { normaliseGloss } from "@/lib/localCorpus";
import { SNAPSHOT, api, currentProject, type Consent, type Frame, type Project, type Sample, type SignClass, type Signer, when } from "@/lib/api";
import { EXTRACTOR, extractFromVideo, loadHolistic, trackVideo } from "@/lib/holistic";
import { drawSkeleton, EMPTY, smooth } from "@/lib/skeleton";
import CameraModes from "@/components/CameraModes";
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
const READY_MS = 1000; // shoulders and a hand must be in view this long before the countdown starts
const READY_TIMEOUT_MS = 12_000;
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
  const [hands, setHands] = useState({ left: false, right: false }); // live: is each hand tracked right now
  const [takes, setTakes] = useState(1); // takes recorded back to back
  const [waiting, setWaiting] = useState(false); // waiting for the signer to be in frame before a take
  const [session, setSession] = useState<Sample[]>([]); // every take saved since the last Record press
  const readySince = useRef(0);
  const previewing = useRef(false);
  const handSeen = useRef({ left: 0, right: 0, at: 0 });
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const stopRef = useRef<null | "stop" | "cancel">(null);
  const overlayRef = useRef(true);
  const smoothed = useRef(EMPTY);
  const lowFrames = useRef(0);

  useEffect(() => {
    (async () => {
      const p = await currentProject();
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
    // A hand counts as tracked if it was seen in the last few frames; the state updates a few times a second, not every frame.
    const h = handSeen.current, now = performance.now();
    h.left = r.leftHandLandmarks[0] ? now : h.left;
    h.right = r.rightHandLandmarks[0] ? now : h.right;
    if (now - h.at > 200) { h.at = now; setHands({ left: now - h.left < 400, right: now - h.right < 400 }); }
    const shoulders = r.poseLandmarks[0]?.[11] && r.poseLandmarks[0]?.[12];
    const ready = !!shoulders && (now - h.left < 400 || now - h.right < 400);
    readySince.current = ready ? readySince.current || now : 0;
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
      // 30 fps where the camera allows it: the hand tracker follows motion frame to frame, so fewer frames lose fast hands.
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, frameRate: { ideal: 30 }, facingMode: "user" }, audio: false });
      const v = video.current!;
      v.srcObject = stream.current;
      await v.play();
      setCameraOn(true);
      startPreview();
      setStatus("Camera on. Check that both hand markers say tracked, then record. Video is processed in this browser and never uploaded.");
    } catch (e) { fail(e); }
  }

  function startPreview() {
    if (previewing.current || !video.current) return;
    previewing.current = true;
    trackVideo(video.current, () => !previewing.current, draw).catch(fail);
  }

  function stopCamera() {
    previewing.current = false;
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
    previewing.current = false; // one tracker at a time: the recording takes over from the preview
    setRecording(true);
    const frames = await extractFromVideo(v, (t) => t >= maxSeconds || stopRef.current !== null, draw);
    setRecording(false);
    setHandsLow(false);
    if (v.srcObject) startPreview(); // back to live feedback for the next take
    return stopRef.current === "cancel" ? null : frames;
  }

  /** Resolves true once shoulders and a hand have been in view for READY_MS; false on timeout or Cancel. */
  async function inFrame(take: string) {
    const t0 = performance.now();
    stopRef.current = null;
    setWaiting(true);
    try {
      while (!(readySince.current && performance.now() - readySince.current >= READY_MS)) {
        if (stopRef.current === "cancel" || performance.now() - t0 > READY_TIMEOUT_MS) return false;
        setStatus(`${take}Get in frame: both shoulders and at least one hand must be visible.`);
        await new Promise((r) => setTimeout(r, 150));
      }
      return true;
    } finally { setWaiting(false); }
  }

  async function record() {
    const v = video.current!, saved: Sample[] = [];
    setBusy(true); setResult(null); setUnsaved(null); setError(""); setSession([]);
    try {
      for (let k = 1; k <= takes; k++) {
        const take = takes > 1 ? `Take ${k} of ${takes}. ` : "";
        if (!(await inFrame(take))) {
          setStatus(stopRef.current === "cancel" ? `Cancelled.${saved.length ? ` ${saved.length} earlier take(s) were saved.` : " Nothing was saved."}`
            : "Couldn't see your shoulders and a hand for long enough. Sit back so your upper body is in the dashed box, in good light, and try again.");
          break;
        }
        for (let n = k === 1 ? 3 : 2; n > 0; n--) { setStatus(`${take}Starting in ${n}…`); await new Promise((r) => setTimeout(r, 1000)); }
        setStatus(`${take}Recording: sign “${sign?.gloss}” now. Recording stops by itself after ${MAX_RECORD_SECONDS} s.`);
        const frames = await extract(v, MAX_RECORD_SECONDS);
        if (!frames) { setStatus(`Cancelled.${saved.length ? ` ${saved.length} earlier take(s) were saved.` : " Nothing was saved."}`); break; }
        const { sha256, delegate } = await loadHolistic();
        const s = await submit({ signClassId: classId!, frames, source: "captured", extractor: `${EXTRACTOR} ${delegate}`, sha: sha256, width: v.videoWidth, height: v.videoHeight }, k === takes);
        if (!s) break; // the error banner keeps the frames for a retry
        saved.push(s); setSession([...saved]);
      }
    } catch (e) { fail(e); }
    setBusy(false);
  }

  async function upload(file: File) {
    const v = video.current!;
    setBusy(true); setResult(null); setUnsaved(null); setError("");
    const url = URL.createObjectURL(file); // stays in this browser: only landmarks are sent
    try {
      if (cameraOn) stopCamera();
      setStatus("Loading landmark model…");
      const { sha256, delegate } = await loadHolistic();
      v.src = url;
      await v.play();
      setStatus(`Extracting landmarks from the clip (only the first ${MAX_UPLOAD_SECONDS}s are used)…`);
      const frames = await extract(v, MAX_UPLOAD_SECONDS);
      const { videoWidth: width, videoHeight: height } = v;
      v.pause();
      v.removeAttribute("src");
      if (!frames) { setBusy(false); setStatus("Cancelled. Nothing was saved."); return; }
      await submit({ signClassId: classId!, frames, source: "captured", extractor: `${EXTRACTOR} ${delegate}`, sha: sha256, width, height });
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

  async function submit(c: Captured, last = true): Promise<Sample | null> {
    if (!c.frames.length) { // nothing to check or store; saving it would only add an empty row to the corpus
      setError("No video frames were processed, so nothing was saved. Keep this tab visible while recording or uploading, and try again.");
      setStatus("Failed."); setBusy(false);
      return null;
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
      if (last) setBusy(false);
      return s;
    } catch (e) {
      setUnsaved(c);
      setError(`Not saved: ${e instanceof Error ? e.message : e} The ${c.frames.length} extracted frames are kept on this page, so you can retry without recording again.`);
      setStatus("Failed.");
      setBusy(false);
      return null;
    }
  }

  const canConsent = project && classId && CODE_RE.test(code) && understood && corpusOk;

  return (
    <div className="space-y-6">
      <header>
        <CameraModes active="collect" />
        <h1 className="mt-4 text-[clamp(2rem,3.6vw,2.8rem)] font-semibold leading-none">Capture a consented sample</h1>
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
        {project && <AddSign projectId={project.id} disabled={busy} onAdded={(c) => { setClasses((cs) => [...cs, c]); setClassId(c.id); setRecommended(false); }} />}
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
              <span>{SNAPSHOT
                ? <>I agree that my landmarks can be stored <strong>in this browser, on this device</strong>, until I delete them or clear site data. In this public demo nothing is sent to the team or anywhere else. (Required)</>
                : <>I agree that my landmarks can be stored in this {project?.target_language ?? ""} corpus. (Required)</>}</span></label>
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
          {cameraOn && (
            <div role="status" aria-live="polite" className="absolute left-3 top-3 flex gap-2 text-sm font-medium">
              {(["left", "right"] as const).map((side) => (
                <span key={side} className={`flex items-center gap-1.5 px-2.5 py-1 ${hands[side] ? "bg-teal text-white" : "bg-amber-100 text-amber-950"}`}>
                  <span aria-hidden className={`size-2 rounded-full ${hands[side] ? "bg-white" : "bg-amber-700"}`} />
                  Your {side} hand: {hands[side] ? "tracked" : "not seen"}
                </span>
              ))}
            </div>
          )}
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
          ) : waiting ? (
            <button className="rounded-lg border border-red-700 px-3 py-2 text-red-800" onClick={() => (stopRef.current = "cancel")}>Cancel</button>
          ) : (
            <>
              <button className="rounded-lg bg-indigo px-3 py-2 text-white disabled:opacity-60" disabled={!consent || busy || !cameraOn} onClick={record}>
                {takes > 1 ? `Record ${takes} takes` : "Record sign"}</button>
              <label className="flex items-center gap-1 text-sm">Takes
                <select className="rounded-lg border border-lavender p-1.5" value={takes} disabled={busy} onChange={(e) => setTakes(Number(e.target.value))}>
                  {[1, 3, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </>
          )}
          <label className={`rounded-lg border border-indigo px-3 py-2 focus-within:ring-2 focus-within:ring-indigo ${!consent || busy ? "opacity-60" : "cursor-pointer"}`}>Upload a clip
            <input type="file" accept="video/*" className="sr-only" disabled={!consent || busy} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
          </label>
          <button className="rounded-lg border border-amber-600 px-3 py-2 text-amber-900 disabled:opacity-60" disabled={!consent || busy || SNAPSHOT} title={SNAPSHOT ? "DEMO DATA is generated by the backend" : undefined} onClick={useDemo}>Use DEMO DATA (no webcam)</button>
          <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={overlay} onChange={(e) => toggleOverlay(e.target.checked)} /> Show landmark overlay</label>
        </div>
        <p className="text-xs">Sit back so your head and both hands stay inside the dashed box, and sign above your waist. Hands that drop out of the frame are the most common reason a clip fails the automated check.</p>
        {!consent && <p className="text-xs">Record consent first. Recording, uploading and DEMO DATA stay off until then.</p>}
        {SNAPSHOT && <LocalClips />}
        <p aria-live="polite" className="text-sm font-medium">{status}</p>
      </section>

      {result && (
        <section className={section} aria-labelledby="s4">
          <h2 id="s4" className="font-semibold">4. Result: sample #{result.id}
            {result.source === "demo_fixture" && <DemoBadge className="ml-2" />}</h2>
          <p className="text-sm">
            {result.qc_passed ? "Passed the automated check." : "Failed the automated check."} Landmark completeness {(result.quality_score * 100).toFixed(0)}%
            {" "}· {result.frame_count} frames · {result.qc_metrics.duration_s}s · captured at {Math.round(result.fps)} fps
          </p>
          {result.fps < 12 && result.source === "captured" && (
            <p className="text-sm text-amber-900">Only {Math.round(result.fps)} frames per second were tracked. Close other tabs or apps, and sign a little slower, so fast hand movements are not missed.</p>
          )}
          {result.triage_status && (
            <p className="text-sm"><strong>Model check:</strong>{" "}
              {result.triage_status === "auto_rejected" ? "not run, because the automated check failed."
                : <>{result.triage?.reason}{result.triage?.top3?.length ? <span className="block text-indigo">Closest: {result.triage.top3.map((t) => `${t.sign} ${Math.round(t.p * 100)}%`).join(" · ")}</span> : null}</>}
            </p>
          )}
          {result.quality_flags.length > 0 && (
            <ul className="list-disc pl-5 text-sm">{result.quality_flags.map((f) => <li key={f.code}><strong>{f.severity === "error" ? "Problem" : "Warning"}:</strong> {f.message}</li>)}</ul>
          )}
          {result.quality_flags.some((f) => f.code === "hands_missing" || f.code === "out_of_frame") && (
            <p className="text-sm text-amber-900">To retake: sit further back and keep both hands inside the dashed box the whole time, in good light.</p>
          )}
          <p className="text-sm">Saved and <span className="rounded-md bg-amber-100 px-2 py-0.5 text-amber-950">waiting for human review</span>. The automated check can&apos;t tell whether the sign itself is correct; a reviewer decides that.</p>
          {session.length > 1 && (
            <div className="text-sm">
              <p className="font-medium">This session: {session.filter((x) => x.qc_passed).length} of {session.length} takes passed the automated check.</p>
              <ul className="mt-1 space-y-0.5">{session.map((x, i) => (
                <li key={x.id}>Take {i + 1}: sample #{x.id} · {x.qc_passed ? "passed" : `failed (${x.quality_flags.filter((f) => f.severity === "error").map((f) => f.code.replaceAll("_", " ")).join(", ")})`}
                  {x.match_confidence != null && ` · model match ${Math.round(x.match_confidence * 100)}%`}</li>
              ))}</ul>
            </div>
          )}
          <Link href="/corpus" className="text-sm text-indigo underline">Review it in Corpus & review →</Link>
        </section>
      )}
    </div>
  );
}

/** Public demo only: clips recorded here never leave the browser, so offer them as a file. */
function LocalClips() {
  const [error, setError] = useState("");
  async function download() {
    try {
      const { exportLocal } = await import("@/lib/localCorpus.ts");
      const blob = new Blob([JSON.stringify(await exportLocal())], { type: "application/json" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "signforge-my-clips.json" });
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  return (
    <p className="text-xs">
      Public demo: clips are saved in this browser only, not sent to the team. Review or delete them in Corpus &amp; review.{" "}
      <button className="underline underline-offset-2" onClick={download}>Download my clips (landmarks JSON)</button>
      {error && <span className="ml-2 text-red-800">{error}</span>}
    </p>
  );
}

/** A sign the project does not have yet. On the public demo it is saved in this browser; with the backend, in the project. */
function AddSign({ projectId, disabled, onAdded }: { projectId: number; disabled: boolean; onAdded: (c: SignClass) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const gloss = normaliseGloss(name);
  async function add() {
    setSaving(true); setError("");
    try {
      onAdded(await api<SignClass>("/api/sign-classes", { body: { project_id: projectId, gloss, prompt_text: `Sign "${gloss.toLowerCase().replaceAll("-", " ")}"` } }));
      setName(""); setOpen(false);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setSaving(false);
  }
  if (!open) return <button className="text-sm text-indigo underline underline-offset-2 disabled:opacity-60" disabled={disabled} onClick={() => setOpen(true)}>Add a new sign</button>;
  return (
    <div className="max-w-sm space-y-2 border border-lavender p-3">
      <label className="block text-sm">Name of the new sign (an English gloss, e.g. GOOD-LUCK)
        <input className="mt-1 block w-full rounded-lg border border-lavender p-2 uppercase" value={name} maxLength={50}
               onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && gloss) add(); }} />
      </label>
      <p className="text-xs text-indigo">
        A gloss is only a label, not a translation. To teach the model this sign: record at least 3 clips, approve them in Corpus &amp; review
        (with model training allowed in the consent), then retrain on Models &amp; evaluation.
      </p>
      {error && <p className="text-sm text-red-800">{error}</p>}
      <div className="flex gap-2">
        <button className="rounded-lg bg-indigo px-3 py-2 text-sm text-white disabled:opacity-60" disabled={!gloss || saving} onClick={add}>{saving ? "Adding…" : gloss ? `Add ${gloss}` : "Add"}</button>
        <button className="rounded-lg px-3 py-2 text-sm text-indigo" onClick={() => { setOpen(false); setError(""); }}>Cancel</button>
      </div>
    </div>
  );
}
