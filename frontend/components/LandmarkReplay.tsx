"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { drawSkeleton, EMPTY, smooth, type SkeletonParts } from "@/lib/skeleton";

type Replay = { fps: number; width: number; height: number; frames: { pose: number[][] | null; left: number[][] | null; right: number[][] | null }[] };
type Fit = (a: number[][] | null) => { x: number; y: number }[] | null;

/** Zooms to the signer: fits the bounding box of in-frame face/arm/hand points (all frames) into the canvas,
 *  keeping the capture's aspect ratio. Hips/legs are often extrapolated below a webcam frame, so they don't count. */
function fitToSigner(r: Replay, cw: number, ch: number): Fit {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const f of r.frames) for (const pts of [f.pose?.slice(0, 23), f.left, f.right]) for (const [x, y] of pts ?? []) {
    if (x < 0 || x > 1 || y < 0 || y > 1) continue;
    x0 = Math.min(x0, x * r.width); x1 = Math.max(x1, x * r.width);
    y0 = Math.min(y0, y * r.height); y1 = Math.max(y1, y * r.height);
  }
  if (!isFinite(x0)) { x0 = 0; y0 = 0; x1 = r.width; y1 = r.height; }
  const s = 0.85 * Math.min(cw / Math.max(x1 - x0, 1), ch / Math.max(y1 - y0, 1));
  const ox = (cw - (x1 - x0) * s) / 2 - x0 * s, oy = (ch - (y1 - y0) * s) / 2 - y0 * s;
  return (a) => a?.map(([x, y]) => ({ x: (x * r.width * s + ox) / cw, y: (y * r.height * s + oy) / ch })) ?? null;
}

type DemoFrames = { width: number; height: number; fps: number; frames: { pose: number[][] | null; left_hand: number[][] | null; right_hand: number[][] | null }[] };
const fromDemo = (d: DemoFrames): Replay => ({ ...d, frames: d.frames.map((f) => ({ pose: f.pose, left: f.left_hand, right: f.right_hand })) });

/** Loops a stored sample's landmarks as a skeleton (exactly what SIGNFORGE keeps: no video).
 *  Without a sampleId it replays synthetic DEMO DATA frames instead. */
export default function LandmarkReplay({ sampleId, className = "" }: { sampleId?: number; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<Replay | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = sampleId != null ? api<Replay>(`/api/samples/${sampleId}/landmarks`) : api<DemoFrames>("/api/demo-frames?class_index=0&seed=1").then(fromDemo);
    load.then(setData, (e) => setError(e.message));
  }, [sampleId]);

  useEffect(() => {
    const c = canvas.current;
    if (!data || !c || !data.frames.length) return;
    const ctx = c.getContext("2d")!;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const toPts = fitToSigner(data, c.width, c.height);
    let i = 0, prev: SkeletonParts = EMPTY, last = 0, raf = 0, visible = true;
    const seen = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    seen.observe(c);
    const paint = () => {
      const f = data.frames[i];
      prev = smooth(prev, { pose: toPts(f.pose), left: toPts(f.left), right: toPts(f.right) });
      ctx.clearRect(0, 0, c.width, c.height);
      drawSkeleton(ctx, c.width, c.height, prev);
    };
    if (reduced) { i = Math.floor(data.frames.length / 2); paint(); seen.disconnect(); return; }
    const tick = (now: number) => {
      if (visible && now - last >= 1000 / data.fps) { // no drawing while scrolled out of view
        last = now;
        paint();
        i = (i + 1) % data.frames.length;
        if (i === 0) prev = EMPTY; // don't smear the loop's end into its start
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); seen.disconnect(); };
  }, [data]);

  if (error) return <p className="text-xs text-lavender">Replay unavailable: {error}</p>;
  return <canvas ref={canvas} width={640} height={360} className={className} role="img"
                 aria-label="Animated stick figure replaying stored body and hand landmarks of a sample" />;
}
