"use client";

import type { HolisticLandmarkerResult } from "@mediapipe/tasks-vision";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import CameraModes from "@/components/CameraModes";
import { card, ErrorBanner } from "@/components/ui";
import { api, type Frame } from "@/lib/api";
import { loadHolistic, toFrame, trackVideo } from "@/lib/holistic";
import { drawSkeleton, EMPTY, smooth } from "@/lib/skeleton";

type Reading = {
  state: "sign" | "unsure" | "still" | "no_hands" | "waiting" | "no_model";
  sign?: string; confidence?: number; top3?: { sign: string; p: number }[];
  message?: string; vocabulary: string[]; run_id?: number; calibration_passed?: boolean;
};
type Said = { sign: string; confidence: number; at: number };

const WINDOW_S = 2.5; // about one INCLUDE clip: the model reads the last 2.5 s of signing
const EVERY_MS = 600; // how often the window is read

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

  function onResult(r: HolisticLandmarkerResult) {
    const now = performance.now() / 1000;
    buffer.current.push(toFrame(r, now));
    while (buffer.current.length && now - buffer.current[0].t > WINDOW_S) buffer.current.shift();
    const h = handSeen.current, ms = now * 1000;
    h.left = r.leftHandLandmarks[0] ? ms : h.left;
    h.right = r.rightHandLandmarks[0] ? ms : h.right;
    if (ms - h.at > 200) { h.at = ms; setHands({ left: ms - h.left < 400, right: ms - h.right < 400 }); }
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
      const r = await api<Reading>("/api/interpret", { body: { frames: buffer.current.map((f) => ({ ...f, t: f.t - t0 })) } });
      if (!running.current) return;
      setReading(r);
      const s = r.state === "sign" ? r.sign! : null;
      if (s && s === pending.current) {
        setSaid((prev) => {
          const last = prev.at(-1);
          if (last?.sign === s && Date.now() - last.at < 4000) return prev; // the same sign held for a while is one sign
          return [...prev, { sign: s, confidence: r.confidence!, at: Date.now() }].slice(-12);
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
      setOn(true);
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
    setOn(false); setReading(null); pending.current = null;
  }

  useEffect(() => {
    const id = window.setInterval(read, EVERY_MS);
    return () => { window.clearInterval(id); running.current = false; stream.current?.getTracks().forEach((t) => t.stop()); };
  }, []); // read() only touches refs and stable setters, so the interval is set up once

  const vocab = reading?.vocabulary ?? [];
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
            {!on && <p className="absolute inset-0 grid place-items-center text-lavender">{starting ? "Starting the camera…" : "Camera is off"}</p>}
          </div>

          {/* The reading, under the camera. */}
          <div role="status" aria-live="polite" className="min-h-[9rem] bg-navy p-5 text-[#efeee9]">
            {!on ? <p className="text-lg text-[#efeee9]/70">Start the camera to begin interpreting.</p>
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

          <div className="flex flex-wrap gap-3">
            {on
              ? <button onClick={stop} className="rounded-full border border-navy px-6 py-3 font-semibold hover:bg-white">Stop camera</button>
              : <button onClick={start} disabled={starting} className="rounded-full bg-navy px-6 py-3 font-semibold text-white hover:bg-safelight hover:text-navy disabled:opacity-60">Start interpreting</button>}
            {said.length > 0 && <button onClick={() => setSaid([])} className="rounded-full px-5 py-3 font-semibold text-indigo hover:bg-white">Clear transcript</button>}
          </div>
        </section>

        <aside className="space-y-6">
          <section aria-labelledby="said-h" className={card}>
            <h2 id="said-h" className="display text-2xl font-semibold">Transcript</h2>
            <p className="mt-1 text-sm text-indigo">A sign is added once it is read twice in a row.</p>
            {said.length === 0
              ? <p className="mt-4 text-base text-indigo">Nothing yet.</p>
              : <p className="f-display mt-4 text-[1.8rem] leading-snug">{said.map((s) => s.sign.toLowerCase().replaceAll("-", " ")).join(" · ")}</p>}
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
            {reading?.run_id && <p className="mt-2 text-sm text-indigo">Model: run #{reading.run_id}{reading.calibration_passed === false && ", confidence not yet calibrated reliably"}.</p>}
          </section>
        </aside>
      </div>
    </div>
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
