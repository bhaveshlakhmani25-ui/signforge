"use client";

import type { HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import CameraModes from "@/components/CameraModes";
import LandmarkReplay from "@/components/LandmarkReplay";
import { card, ErrorBanner } from "@/components/ui";
import { api, type Frame } from "@/lib/api";
import { expressionOf, GestureFilter, type Expression, type Gesture } from "@/lib/gestures";
import { extractFromVideo, loadHolistic, toFrame, trackVideo } from "@/lib/holistic";
import { drawSkeleton, EMPTY, smooth } from "@/lib/skeleton";
import { transcribe, type Line } from "@/lib/transcript";

type Reading = {
  state: "sign" | "unsure" | "still" | "no_hands" | "waiting" | "no_model";
  sign?: string; confidence?: number; top3?: { sign: string; p: number }[];
  message?: string; vocabulary: string[]; run_id?: number; calibration_passed?: boolean; retrained?: boolean;
};
type Said = { sign: string; confidence: number; at: number; kind: "sign" | "gesture" };
type Check = { sample_id: number; true_sign: string; reading: Reading };
type Language = { project_id: number; name: string; target_language: string; run_id: number; n_signs: number; accuracy: number | null };

const WINDOW_S = 2.5; // about one INCLUDE clip: the model reads the last 2.5 s of signing
const EVERY_MS = 600; // how often the window is read
const UPLOAD_EVERY_S = 0.25; // an upload is not live, so read it more densely: a short sign still gets two windows in a row
const MAX_UPLOAD_S = 30; // landmarks are extracted at playback speed, so long videos take as long as they play

export default function InterpretPage() {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const running = useRef(false);
  const buffer = useRef<Frame[]>([]);
  const inFlight = useRef(false);
  const pending = useRef<string | null>(null); // a sign must be read twice in a row before it joins the transcript
  const smoothed = useRef(EMPTY);
  const handSeen = useRef({ left: 0, right: 0, at: 0 });
  const [on, setOn] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [reading, setReading] = useState<Reading | null>(null);
  const [said, setSaid] = useState<Said[]>([]);
  const [hands, setHands] = useState({ left: false, right: false });
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const [expression, setExpression] = useState<Expression | null>(null);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [lang, setLang] = useState<number | null>(null);
  const langRef = useRef<number | null>(null);
  const gestures = useRef(new GestureFilter());
  const cues = useRef({ at: 0, gesture: "" as string | null });
  const [check, setCheck] = useState<Check | null>(null);
  const [checking, setChecking] = useState(false);
  const [tally, setTally] = useState({ right: 0, total: 0 });

  // No camera needed: a held-out INCLUDE clip the model never trained on goes through the same interpreter.
  async function runCheck() {
    setError(""); setChecking(true);
    try {
      const c = await api<Check>(`/api/interpret/test-clip${langRef.current ? `?project_id=${langRef.current}` : ""}`, { method: "POST" });
      setCheck(c);
      setTally((t) => ({ right: t.right + (c.reading.state === "sign" && c.reading.sign === c.true_sign ? 1 : 0), total: t.total + 1 }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setChecking(false);
  }

  function onResult(r: HolisticLandmarkerResult) {
    const now = performance.now() / 1000;
    buffer.current.push(toFrame(r, now));
    while (buffer.current.length && now - buffer.current[0].t > WINDOW_S) buffer.current.shift();
    const h = handSeen.current, ms = now * 1000;
    h.left = r.leftHandLandmarks[0] ? ms : h.left;
    h.right = r.rightHandLandmarks[0] ? ms : h.right;
    if (ms - h.at > 200) { h.at = ms; setHands({ left: ms - h.left < 400, right: ms - h.right < 400 }); }
    // Gestures and facial cues are read every frame but shown a few times a second.
    const g = gestures.current.push(r);
    if (ms - cues.current.at > 250) {
      cues.current.at = ms;
      setGesture(g);
      setExpression(expressionOf(r));
      if (g && g.id !== cues.current.gesture) {
        setSaid((prev) => {
          const last = prev.at(-1);
          if (last?.kind === "gesture" && last.sign === g.label && Date.now() - last.at < 4000) return prev; // a hand flickering out and back is one gesture
          return [...prev, { sign: g.label, confidence: 1, at: Date.now(), kind: "gesture" as const }].slice(-12);
        });
      }
      cues.current.gesture = g?.id ?? null;
    }
    const v = video.current, c = canvas.current;
    if (!v || !c) return;
    if (c.width !== v.videoWidth) { c.width = v.videoWidth; c.height = v.videoHeight; }
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, c.width, c.height);
    smoothed.current = smooth(smoothed.current, { pose: r.poseLandmarks[0] ?? null, left: r.leftHandLandmarks[0] ?? null, right: r.rightHandLandmarks[0] ?? null });
    drawSkeleton(ctx, c.width, c.height, smoothed.current);
  }

  async function read() {
    if (!running.current || inFlight.current || buffer.current.length < 5) return;
    inFlight.current = true;
    const t0 = buffer.current[0].t;
    try {
      const r = await api<Reading>("/api/interpret", { body: { frames: buffer.current.map((f) => ({ ...f, t: f.t - t0 })), project_id: langRef.current } });
      if (!running.current) return;
      setReading(r);
      const s = r.state === "sign" ? r.sign! : null;
      if (s && s === pending.current) {
        setSaid((prev) => {
          const last = prev.filter((x) => x.kind === "sign").at(-1);
          if (last?.sign === s && Date.now() - last.at < 4000) return prev; // the same sign held for a while is one sign
          return [...prev, { sign: s, confidence: r.confidence!, at: Date.now(), kind: "sign" as const }].slice(-12);
        });
      }
      pending.current = s;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { inFlight.current = false; }
  }

  async function start() {
    setError(""); setStarting(true);
    try {
      await loadHolistic();
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720, frameRate: { ideal: 30 }, facingMode: "user" }, audio: false });
      const v = video.current!;
      v.srcObject = stream.current;
      await v.play();
      running.current = true;
      buffer.current = [];
      setOn(true); setCheck(null);
      trackVideo(v, () => !running.current, onResult).catch((e) => setError(String(e)));
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setError(name === "NotAllowedError" ? "Camera permission was denied." : name === "NotFoundError" ? "No camera was found." : String((e as Error)?.message ?? e));
    }
    setStarting(false);
  }

  function stop() {
    running.current = false;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    canvas.current?.getContext("2d")?.clearRect(0, 0, canvas.current.width, canvas.current.height);
    setOn(false); setReading(null); setGesture(null); setExpression(null); pending.current = null;
  }

  useEffect(() => {
    api<Language[]>("/api/interpret/languages").then((ls) => {
      setLanguages(ls);
      const pick = [...ls].sort((x, y) => (y.accuracy ?? 0) - (x.accuracy ?? 0))[0]?.project_id ?? null; // start on the most accurate model
      setLang(pick); langRef.current = pick;
    }, () => {});
  }, []);

  useEffect(() => {
    const id = window.setInterval(read, EVERY_MS);
    return () => { window.clearInterval(id); running.current = false; stream.current?.getTracks().forEach((t) => t.stop()); };
  }, []); // read() only touches refs and stable setters, so the interval is set up once

  const vocab = reading?.vocabulary ?? check?.reading.vocabulary ?? [];
  return (
    <div className="space-y-6">
      <header className="space-y-4">
        <CameraModes active="interpret" />
        <div>
          <h1 className="text-[clamp(2rem,3.6vw,2.8rem)] font-semibold leading-none">Interpret live</h1>
          <p className="mt-2 max-w-[62ch] text-base text-indigo">
            The camera reads your signing continuously and names the sign it recognises. Nothing is recorded or saved:
            landmarks are scored and thrown away. It only knows the signs the model was trained on.
          </p>
        </div>
      </header>
      {languages.length > 0 && (
        <label className="flex flex-wrap items-center gap-3 text-base">
          <span className="font-semibold">Read signing as</span>
          <select value={lang ?? ""} onChange={(e) => { const v = Number(e.target.value); setLang(v); langRef.current = v; setReading(null); }}
                  className="rounded-full border border-lavender bg-white px-4 py-2">
            {languages.map((l) => <option key={l.project_id} value={l.project_id}>{l.target_language}: {l.name} ({l.n_signs} signs{l.accuracy != null && `, ${(l.accuracy * 100).toFixed(0)}% on held-out clips`})</option>)}
          </select>
        </label>
      )}
      {error && <ErrorBanner message={error} onRetry={() => { setError(""); if (!on) start(); }} />}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-label="Camera" className="space-y-3">
          <div className="relative aspect-video w-full overflow-hidden bg-navy">
            <video ref={video} playsInline muted className="absolute inset-0 h-full w-full -scale-x-100 object-contain" />
            <canvas ref={canvas} aria-hidden className="absolute inset-0 h-full w-full -scale-x-100 object-contain" />
            {on && (
              <div className="absolute left-3 top-3 flex gap-2 text-sm font-medium">
                {(["left", "right"] as const).map((side) => (
                  <span key={side} className={`flex items-center gap-1.5 px-2.5 py-1 ${hands[side] ? "bg-teal text-white" : "bg-amber-100 text-amber-950"}`}>
                    <span aria-hidden className={`size-2 rounded-full ${hands[side] ? "bg-white" : "bg-amber-700"}`} />
                    {side === "left" ? "Left" : "Right"} hand: {hands[side] ? "tracked" : "not seen"}
                  </span>
                ))}
              </div>
            )}
            {!on && check && <LandmarkReplay key={check.sample_id} sampleId={check.sample_id} className="absolute inset-0 h-full w-full" />}
            {!on && !check && <p className="absolute inset-0 grid place-items-center text-lavender">{starting ? "Starting the camera…" : "Camera is off"}</p>}
          </div>

          {/* The reading, under the camera. */}
          <div role="status" aria-live="polite" className="min-h-[9rem] bg-navy p-5 text-[#efeee9]">
            {!on && check ? <CheckResult check={check} tally={tally} accuracy={languages.find((l) => l.project_id === lang)?.accuracy ?? null} />
              : !on ? <p className="text-lg text-[#efeee9]/70">Start the camera to begin interpreting, or check it on a held-out clip without a camera.</p>
              : !reading || reading.state === "waiting" ? <p className="text-lg text-[#efeee9]/70">Reading…</p>
              : reading.state === "sign" ? (
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <p className="text-sm uppercase tracking-[0.1em] text-[#efeee9]/60">Looks like</p>
                    <p className="f-display text-[clamp(2.6rem,5vw,4rem)] font-semibold leading-none">{reading.sign}</p>
                  </div>
                  <Confidence p={reading.confidence!} passed={reading.calibration_passed} />
                </div>
              ) : (
                <div>
                  <p className="text-xl">{reading.message}</p>
                  {reading.state === "unsure" && (
                    <p className="mt-3 text-base text-[#efeee9]/75">
                      Is this a sign the model hasn&apos;t learned?{" "}
                      <Link href="/capture" className="font-semibold text-safelight underline underline-offset-4">Teach it: record this sign</Link>
                    </p>
                  )}
                </div>
              )}
            {on && reading?.top3 && reading.state !== "no_hands" && reading.state !== "still" && (
              <p className="mt-4 text-sm text-[#efeee9]/70">Closest: {reading.top3.map((t) => `${t.sign} ${(t.p * 100).toFixed(0)}%`).join(" · ")}</p>
            )}
          </div>

          {on && (
            <dl className="grid gap-3 sm:grid-cols-2">
              <div className={`border p-4 ${gesture?.tone === "offensive" ? "border-red-700 bg-red-50" : "border-lavender bg-white"}`}>
                <dt className="text-sm text-indigo">Hand gesture</dt>
                <dd className="mt-1">
                  {gesture ? <><span className={`text-xl font-semibold ${gesture.tone === "offensive" ? "text-red-900" : ""}`}>{gesture.label}</span>
                    <span className="mt-1 block text-sm text-indigo">{gesture.meaning}</span></>
                    : <span className="text-base text-indigo">None held</span>}
                </dd>
              </div>
              <div className="border border-lavender bg-white p-4">
                <dt className="text-sm text-indigo">Facial expression <span className="text-xs">(a cue, not your mood)</span></dt>
                <dd className="mt-1">
                  {expression ? <><span className="text-xl font-semibold">{expression.label}</span>
                    {expression.note && <span className="mt-1 block text-sm text-indigo">{expression.note}</span>}</>
                    : <span className="text-base text-indigo">Face not in view</span>}
                </dd>
              </div>
            </dl>
          )}

          <div className="flex flex-wrap gap-3">
            {on
              ? <button onClick={stop} className="rounded-full border border-navy px-6 py-3 font-semibold hover:bg-white">Stop camera</button>
              : <button onClick={start} disabled={starting} className="rounded-full bg-navy px-6 py-3 font-semibold text-white hover:bg-safelight hover:text-navy disabled:opacity-60">Start interpreting</button>}
            {!on && <button onClick={runCheck} disabled={checking} className="rounded-full border border-navy px-6 py-3 font-semibold hover:bg-white disabled:opacity-60">{checking ? "Reading a clip…" : check ? "Try another clip" : "Check it without a camera"}</button>}
            {said.length > 0 && <button onClick={() => setSaid([])} className="rounded-full px-5 py-3 font-semibold text-indigo hover:bg-white">Clear transcript</button>}
          </div>
        </section>

        <aside className="space-y-6">
          <section aria-labelledby="said-h" className={card}>
            <h2 id="said-h" className="display text-2xl font-semibold">Transcript</h2>
            <p className="mt-1 text-sm text-indigo">A sign is added once it is read twice in a row; held hand gestures appear in [brackets].</p>
            {said.length === 0
              ? <p className="mt-4 text-base text-indigo">Nothing yet.</p>
              : <p className="f-display mt-4 text-[1.8rem] leading-snug">{said.map((x, i) => (
                  <span key={i}>{i > 0 && " · "}{x.kind === "gesture" ? <em className="text-indigo">[{x.sign.toLowerCase()}]</em> : x.sign.toLowerCase().replaceAll("-", " ")}</span>
                ))}</p>}
          </section>

          <section aria-labelledby="vocab-h" className={card}>
            <h2 id="vocab-h" className="display text-2xl font-semibold">Signs it knows{vocab.length ? ` (${vocab.length})` : ""}</h2>
            {vocab.length
              ? <ul className="mt-3 flex flex-wrap gap-2">{vocab.map((v) => <li key={v} className="rounded-full border border-lavender px-3 py-1 text-sm">{v}</li>)}</ul>
              : <p className="mt-2 text-base text-indigo">Shown once the camera starts.</p>}
            <p className="mt-4 text-sm leading-relaxed text-indigo">
              Signs outside this list (including everyday slang and swear words) cannot be recognised yet: no public
              Indian Sign Language dataset contains them. Record them with consent in Collect samples and they can be learned.
            </p>
            {reading?.run_id && <p className="mt-2 text-sm text-indigo">Model: run #{reading.run_id}
              {reading.retrained && <> with its output layer retrained in this browser (<Link href="/models" className="underline">change or revert</Link>)</>}
              {reading.calibration_passed === false && ", confidence not yet calibrated reliably"}.</p>}
          </section>
        </aside>
      </div>
      <UploadTranscript projectId={lang} />
    </div>
  );
}

/** Reads an uploaded video the way the live camera does: 2.5 s windows every 0.6 s, a sign kept once read twice in a row.
 *  Timing uses the video's own clock, so the transcript says where in the video each sign was read. */
function UploadTranscript({ projectId }: { projectId: number | null }) {
  const video = useRef<HTMLVideoElement>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [lines, setLines] = useState<Line[] | null>(null);

  async function run(file: File) {
    const v = video.current!, url = URL.createObjectURL(file); // the video stays in this browser
    setBusy(true); setError(""); setLines(null);
    try {
      setStatus("Loading the landmark model…");
      await loadHolistic();
      v.src = url;
      await v.play();
      setStatus(`Extracting landmarks (up to the first ${MAX_UPLOAD_S} s). Keep this tab visible: it plays at normal speed.`);
      const frames = await extractFromVideo(v, (t) => t >= MAX_UPLOAD_S);
      v.pause();
      if (!frames.length) throw new Error("No video frames were processed. Keep this tab visible and try again.");
      const end = frames.at(-1)!.t;
      const out = await transcribe(frames, (win) => api<Reading>("/api/interpret", { body: { frames: win, project_id: projectId } }),
                                   WINDOW_S, UPLOAD_EVERY_S, (e) => setStatus(`Reading the video: ${e.toFixed(1)} of ${end.toFixed(1)} s…`));
      setLines(out);
      setStatus(`Read ${frames.length} frames from ${end.toFixed(1)} s of video.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(/background|interrupted/i.test(msg) ? "The browser paused the video because this tab went to the background. Keep the tab visible and upload again." : msg);
      setStatus("");
    } finally {
      v.pause(); v.removeAttribute("src"); URL.revokeObjectURL(url); setBusy(false);
    }
  }

  const signs = lines?.filter((l) => l.sign) ?? [];
  return (
    <section aria-labelledby="upload-h" className={card}>
      <h2 id="upload-h" className="display text-2xl font-semibold">Interpret an uploaded video</h2>
      <p className="mt-1 max-w-[70ch] text-sm text-indigo">
        Upload a video of signing and get a transcript with the time each sign was read. The video is processed in this browser and never
        uploaded; only landmarks are scored. The model learned from short clips of single signs, so continuous signing reads less reliably.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-[16rem_1fr]">
        <div className="relative aspect-video overflow-hidden bg-[#0c0c0b]">
          <video ref={video} playsInline muted className="absolute inset-0 h-full w-full object-contain" />
          {!busy && <p className="absolute inset-0 grid place-items-center text-sm text-[#efeee9]/60">No video</p>}
        </div>
        <div className="space-y-3">
          <label className={`inline-block rounded-full bg-navy px-6 py-3 font-semibold text-white focus-within:ring-2 focus-within:ring-indigo ${busy ? "opacity-60" : "cursor-pointer hover:bg-safelight hover:text-navy"}`}>
            {busy ? "Reading…" : "Upload a video"}
            <input type="file" accept="video/*" className="sr-only" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) run(f); }} />
          </label>
          <p aria-live="polite" className="text-sm text-indigo">{status}</p>
          {error && <ErrorBanner message={error} />}
          {lines && (
            <div>
              <p className="f-display text-[1.6rem] leading-snug">
                {signs.length ? signs.map((l) => l.sign!.toLowerCase().replaceAll("-", " ")).join(" · ") : "No sign was read with enough confidence."}
              </p>
              {lines.length > 0 && (
                <ol className="mt-3 space-y-1 text-sm">
                  {lines.map((l, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="f-mono w-14 shrink-0 text-indigo">{l.t.toFixed(1)} s</span>
                      {l.sign ? <span><strong>{l.sign}</strong> {Math.round(l.p! * 100)}%</span>
                        : <span className="text-indigo">not sure{l.note && ` (closest ${l.note}${l.p != null ? ` ${Math.round(l.p * 100)}%` : ""})`}</span>}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function Confidence({ p, passed }: { p: number; passed?: boolean }) {
  return (
    <div className="w-48">
      <p className="flex justify-between text-sm text-[#efeee9]/70"><span>Confidence</span><span className="f-mono">{(p * 100).toFixed(0)}%</span></p>
      <div className="mt-1.5 h-1.5 bg-[#efeee9]/15"><div className="h-full bg-safelight" style={{ width: `${p * 100}%` }} /></div>
      {passed === false && <p className="mt-1 text-xs text-[#efeee9]/55">approximate</p>}
    </div>
  );
}

function CheckResult({ check, tally, accuracy }: { check: Check; tally: { right: number; total: number }; accuracy: number | null }) {
  const r = check.reading, read = r.state === "sign" ? r.sign! : null, right = read === check.true_sign;
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.1em] text-[#efeee9]/60">Held-out test clip #{check.sample_id}: the signer signed</p>
          <p className="f-display text-[clamp(2rem,4vw,3rem)] font-semibold leading-none">{check.true_sign}</p>
        </div>
        {read && <Confidence p={r.confidence!} passed={r.calibration_passed} />}
      </div>
      <p className="mt-3 text-xl">
        {read ? <>Read as <strong>{read}</strong>: <span className={right ? "text-safelight" : "text-red-300"}>{right ? "correct" : "wrong"}</span></> : r.message}
      </p>
      {r.top3 && <p className="mt-2 text-sm text-[#efeee9]/70">Closest: {r.top3.map((t) => `${t.sign} ${(t.p * 100).toFixed(0)}%`).join(" · ")}</p>}
      <p className="mt-2 text-sm text-[#efeee9]/70">
        This session: {tally.right} of {tally.total} read correctly.{accuracy != null && ` Model run #${r.run_id} scored ${(accuracy * 100).toFixed(0)}% on its whole held-out test set.`} The model never trained on these clips.
      </p>
    </div>
  );
}
