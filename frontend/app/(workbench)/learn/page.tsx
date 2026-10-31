"use client";

import type { HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import { useEffect, useRef, useState } from "react";
import { card, ErrorBanner } from "@/components/ui";
import LandmarkReplay from "@/components/LandmarkReplay";
import { SNAPSHOT, api, type Consent, type Frame, type Sample, type Signer } from "@/lib/api";
import { EXTRACTOR, extractFromVideo, loadHolistic, trackVideo } from "@/lib/holistic";
import { drawSkeleton, EMPTY, smooth } from "@/lib/skeleton";

type Language = { project_id: number; name: string; target_language: string; run_id: number; n_signs: number; accuracy: number | null };
type LearnSign = { sign_class_id: number; gloss: string; prompt: string; examples: number[] };
type Reading = { state: string; sign?: string; confidence?: number; message?: string; probs?: Record<string, number>; top3?: { sign: string; p: number }[] };
type Attempt = { frames: Frame[]; width: number; height: number; extractor: string; sha: string; reading: Reading; target: LearnSign };

const TRY_SECONDS = 3;

export default function LearnPage() {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const previewing = useRef(false);
  const smoothed = useRef(EMPTY);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [lang, setLang] = useState<number | null>(null);
  const [signs, setSigns] = useState<LearnSign[]>([]);
  const [pick, setPick] = useState<LearnSign | null>(null);
  const [example, setExample] = useState(0);
  const [cameraOn, setCameraOn] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState("");
  // Opt-in saving: one consent per signer per page visit, like Capture.
  const [code, setCode] = useState("");
  const [training, setTraining] = useState(true);
  const [agreed, setAgreed] = useState(false);
  const [signer, setSigner] = useState<Signer | null>(null);
  const [consent, setConsent] = useState<Consent | null>(null);
  const [saved, setSaved] = useState<Sample | null>(null);

  useEffect(() => {
    api<Language[]>("/api/interpret/languages").then((ls) => {
      setLanguages(ls);
      setLang([...ls].sort((x, y) => (y.accuracy ?? 0) - (x.accuracy ?? 0))[0]?.project_id ?? null);
    }, (e) => setError(String(e.message ?? e)));
    return () => { previewing.current = false; stream.current?.getTracks().forEach((t) => t.stop()); };
  }, []);

  useEffect(() => {
    if (lang == null) return;
    api<{ signs: LearnSign[] }>(`/api/learn/signs?project_id=${lang}`).then((r) => {
      setSigns(r.signs); setPick(r.signs[0] ?? null); setExample(0); setAttempt(null); setSigner(null); setConsent(null);
    }, (e) => setError(String(e.message ?? e)));
  }, [lang]);

  function draw(r: HolisticLandmarkerResult) {
    const v = video.current, c = canvas.current;
    if (!v || !c) return;
    if (c.width !== v.videoWidth) { c.width = v.videoWidth; c.height = v.videoHeight; }
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, c.width, c.height);
    smoothed.current = smooth(smoothed.current, { pose: r.poseLandmarks[0] ?? null, left: r.leftHandLandmarks[0] ?? null, right: r.rightHandLandmarks[0] ?? null });
    drawSkeleton(ctx, c.width, c.height, smoothed.current);
  }

  function preview() {
    previewing.current = true;
    trackVideo(video.current!, () => !previewing.current, draw).catch((e) => setError(String(e)));
  }

  async function startCamera() {
    setError(""); setStatus("Starting the camera…");
    try {
      await loadHolistic();
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, frameRate: { ideal: 30 }, facingMode: "user" }, audio: false });
      video.current!.srcObject = stream.current;
      await video.current!.play();
      setCameraOn(true); setStatus("");
      preview();
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setError(name === "NotAllowedError" ? "Camera permission was denied." : name === "NotFoundError" ? "No camera was found." : String((e as Error)?.message ?? e));
      setStatus("");
    }
  }

  async function tryIt() {
    if (!pick || lang == null) return;
    const v = video.current!, target = pick;
    setBusy(true); setAttempt(null); setSaved(null); setError("");
    try {
      for (let n = 3; n > 0; n--) { setStatus(`Get ready… ${n}`); await new Promise((r) => setTimeout(r, 1000)); }
      setStatus(`Sign “${target.gloss}” now`);
      previewing.current = false; // one tracker at a time: the attempt takes over from the preview
      const frames = await extractFromVideo(v, (t) => t >= TRY_SECONDS, draw);
      preview();
      if (frames.length < 5) throw new Error("No video frames were processed. Keep this tab visible and try again.");
      setStatus("Checking your attempt…");
      const t0 = frames[0].t;
      const reading = await api<Reading>("/api/interpret", { body: { frames: frames.map((f) => ({ ...f, t: f.t - t0 })), project_id: lang } });
      const { sha256, delegate } = await loadHolistic();
      setAttempt({ frames, width: v.videoWidth, height: v.videoHeight, extractor: `${EXTRACTOR} ${delegate}`, sha: sha256, reading, target });
      setStatus("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setStatus(""); }
    setBusy(false);
  }

  async function save() {
    if (!attempt || lang == null) return;
    setBusy(true); setError("");
    try {
      let s = signer, c = consent;
      if (!s || !c) {
        const lname = languages.find((l) => l.project_id === lang)?.target_language ?? "sign language";
        s = await api<Signer>("/api/signers", { body: { project_id: lang, code } });
        c = await api<Consent>("/api/consents", { body: {
          signer_id: s.id, consent_version: "signforge-mvp-v1", purpose: `Build a ${lname} sign corpus (SIGNFORGE prototype, Learn page)`,
          allowed_uses: ["corpus_building", ...(training ? ["model_training"] : [])], retention: "landmarks_only", confirmed: true,
        } });
        setSigner(s); setConsent(c);
      }
      const f = attempt.frames, duration = f.at(-1)!.t - f[0].t;
      setSaved(await api<Sample>("/api/samples/capture", { body: {
        project_id: lang, sign_class_id: attempt.target.sign_class_id, signer_id: s.id, consent_id: c.id, source: "captured",
        extractor: attempt.extractor, extractor_model_sha: attempt.sha, fps: duration > 0 ? f.length / duration : 30,
        width: attempt.width, height: attempt.height, mirrored: false, frames: f,
      } }));
    } catch (e) { setError(`Not saved: ${e instanceof Error ? e.message : e}`); }
    setBusy(false);
  }

  const r = attempt?.reading;
  const targetP = r?.probs?.[attempt!.target.gloss];
  const right = r?.state === "sign" && r.sign === attempt?.target.gloss;
  const exampleId = pick?.examples[example % Math.max(pick.examples.length, 1)];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-[clamp(2rem,3.6vw,2.8rem)] font-semibold leading-none">Learn signs</h1>
        <p className="mt-2 max-w-[64ch] text-base text-indigo">
          Watch how a sign is made, copy it on camera, and see whether the model recognises it. The examples are real dataset clips,
          shown as landmarks only. The check is a model&apos;s match, not a teacher&apos;s judgement: a model trained on few signers can
          mark good signing as wrong.
        </p>
      </header>

      {languages.length > 0 && (
        <label className="flex flex-wrap items-center gap-3 text-base">
          <span className="font-semibold">Language</span>
          <select value={lang ?? ""} onChange={(e) => setLang(Number(e.target.value))} className="rounded-full border border-lavender bg-white px-4 py-2">
            {languages.map((l) => <option key={l.project_id} value={l.project_id}>{l.target_language}: {l.name} ({l.n_signs} signs)</option>)}
          </select>
        </label>
      )}
      {error && <ErrorBanner message={error} onRetry={() => setError("")} />}

      {signs.length > 0 && (
        <nav aria-label="Signs" className="flex flex-wrap gap-2">
          {signs.map((s) => (
            <button key={s.sign_class_id} onClick={() => { setPick(s); setExample(0); setAttempt(null); setSaved(null); }}
                    aria-pressed={pick?.sign_class_id === s.sign_class_id}
                    className={`rounded-full border px-4 py-1.5 text-sm ${pick?.sign_class_id === s.sign_class_id ? "border-navy bg-navy font-semibold text-white" : "border-lavender bg-white hover:border-navy"}`}>
              {s.gloss}
            </button>
          ))}
        </nav>
      )}

      {pick && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section aria-labelledby="watch-h" className="space-y-3">
            <h2 id="watch-h" className="display text-2xl font-semibold">1. Watch: {pick.gloss}</h2>
            <div className="relative aspect-video w-full overflow-hidden bg-navy">
              {exampleId != null
                ? <LandmarkReplay key={exampleId} sampleId={exampleId} className="absolute inset-0 h-full w-full" />
                : <p className="absolute inset-0 grid place-items-center text-lavender">No example clip for this sign.</p>}
            </div>
            <p className="text-sm text-indigo">
              Dataset clip #{exampleId}{pick.examples.length > 1 && <> · example {(example % pick.examples.length) + 1} of {pick.examples.length}{" "}
                <button onClick={() => setExample((e) => e + 1)} className="ml-1 font-semibold underline underline-offset-4">Show another signer</button></>}.
              Shown as the camera saw the signer, so their right hand is on your left.
            </p>
            {pick.prompt && <p className="text-base">{pick.prompt}</p>}
          </section>

          <section aria-labelledby="try-h" className="space-y-3">
            <h2 id="try-h" className="display text-2xl font-semibold">2. Try it yourself</h2>
            <div className="relative aspect-video w-full overflow-hidden bg-navy">
              <video ref={video} playsInline muted className="absolute inset-0 h-full w-full -scale-x-100 object-contain" />
              <canvas ref={canvas} aria-hidden className="absolute inset-0 h-full w-full -scale-x-100 object-contain" />
              {!cameraOn && <p className="absolute inset-0 grid place-items-center text-lavender">Camera is off</p>}
              {status && <p role="status" className="absolute inset-x-0 bottom-0 bg-navy/80 px-4 py-2 text-lg text-white">{status}</p>}
            </div>
            <div className="flex flex-wrap gap-3">
              {cameraOn
                ? <button onClick={tryIt} disabled={busy} className="rounded-full bg-navy px-6 py-3 font-semibold text-white hover:bg-safelight hover:text-navy disabled:opacity-60">
                    {attempt ? "Try again" : `Sign ${pick.gloss} (${TRY_SECONDS} s)`}</button>
                : <button onClick={startCamera} disabled={SNAPSHOT} title={SNAPSHOT ? "Needs the live backend" : undefined} className="rounded-full bg-navy px-6 py-3 font-semibold text-white hover:bg-safelight hover:text-navy disabled:opacity-60">Start camera</button>}
            </div>
            <p className="text-sm text-indigo">Nothing is saved unless you choose to below. Only landmarks are ever sent, never video.</p>

            {r && attempt && (
              <div role="status" aria-live="polite" className={`border p-5 ${right ? "border-teal bg-teal/10" : "border-lavender bg-white"}`}>
                <p className="text-xl font-semibold">
                  {right ? `Recognised as ${attempt.target.gloss}.` : r.state === "sign" ? `The model read ${r.sign}, not ${attempt.target.gloss}.` : r.message}
                </p>
                {targetP != null && (
                  <div className="mt-3 max-w-sm">
                    <p className="flex justify-between text-sm text-indigo"><span>Match with {attempt.target.gloss}</span><span className="f-mono">{(targetP * 100).toFixed(0)}%</span></p>
                    <div className="mt-1 h-1.5 bg-lavender/60"><div className="h-full bg-navy" style={{ width: `${targetP * 100}%` }} /></div>
                  </div>
                )}
                {!right && <p className="mt-3 text-sm text-indigo">Watch the example again: check which hand moves, where it starts and where it ends.</p>}
              </div>
            )}
          </section>
        </div>
      )}

      {attempt && (
        <section aria-labelledby="give-h" className={card}>
          <h2 id="give-h" className="display text-2xl font-semibold">3. Optional: add this attempt to the corpus</h2>
          <p className="mt-1 max-w-[70ch] text-sm text-indigo">
            Your attempts teach the model how your team signs, which public datasets cannot. A saved attempt goes through the automated
            check and then waits for human review before it can ever be used for training. Landmarks only; you can withdraw later in Corpus &amp; review.
          </p>
          {saved
            ? <p className="mt-3 text-base">Saved as sample #{saved.id} ({attempt.target.gloss}).{" "}
                {saved.qc_passed ? "Automated check passed. Waiting for human review." : "It did not pass the automated check, so it will not be used for training."}</p>
            : (
              <div className="mt-4 space-y-3">
                {!consent && (
                  <>
                    <label className="block text-sm">Pseudonymous signer code (not a name), e.g. S-01
                      <input className="mt-1 block w-full max-w-xs rounded-lg border border-lavender p-2 uppercase" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
                    </label>
                    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={training} onChange={(e) => setTraining(e.target.checked)} className="mt-1" />
                      Allow my clips to be used to train and test models (otherwise corpus building only).</label>
                    <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1" />
                      I agree that the landmarks of my attempts on this page may be stored for building this sign corpus. Raw video is never stored.</label>
                  </>
                )}
                <button onClick={save} disabled={busy || (!consent && (!agreed || !/^[A-Z0-9][A-Z0-9-]{1,15}$/.test(code)))}
                        className="rounded-full border border-navy px-6 py-3 font-semibold hover:bg-white disabled:opacity-60">
                  {consent ? `Save this attempt as ${signer?.code}` : "Record consent and save"}
                </button>
              </div>
            )}
        </section>
      )}
    </div>
  );
}
