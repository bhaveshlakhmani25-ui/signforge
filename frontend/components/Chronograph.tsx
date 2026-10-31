"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { HAND, UPPER_BODY } from "@/lib/skeleton";

type Frame = { pose: number[][] | null; left: number[][] | null; right: number[][] | null };
type Replay = { fps: number; width: number; height: number; frames: Frame[] };

const EXPOSURES = 11;
const PASS_MS = 5200; // one shutter pass across the plate
const INK = "239,238,233"; // emulsion white
const SAFELIGHT = "#f2a33a";

/** A Marey-style chronophotograph of a stored sample: faint exposures of the sign spread across the plate,
 *  and a live figure that plays the clip as the shutter crosses. Landmarks only, as SIGNFORGE stores them. */
export default function Chronograph({ sampleId, label }: { sampleId: number | null; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<Replay | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (sampleId == null) return;
    api<Replay>(`/api/samples/${sampleId}/landmarks`).then((d) => setData(d.frames.length ? d : null), () => setFailed(true));
  }, [sampleId]);

  useEffect(() => {
    const c = canvas.current;
    if (!c || !data) return;
    const ctx = c.getContext("2d")!;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mono = getComputedStyle(c).getPropertyValue("--font-mono").trim() || "monospace";
    const n = data.frames.length;

    // Fit the signer's upper body (face, arms, hands across all frames) to the plate height.
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const f of data.frames) for (const pts of [f.pose?.slice(0, 23), f.left, f.right]) for (const [x, y] of pts ?? []) {
      if (x < -0.1 || x > 1.1 || y < -0.1 || y > 1.1) continue;
      const px = x * data.width, py = y * data.height;
      x0 = Math.min(x0, px); x1 = Math.max(x1, px); y0 = Math.min(y0, py); y1 = Math.max(y1, py);
    }

    let W = 0, H = 0, s = 1, figW = 0, margin = 0, dpr = 1;
    const resize = () => {
      dpr = Math.min(2, devicePixelRatio || 1);
      W = c.clientWidth * dpr; H = c.clientHeight * dpr;
      c.width = W; c.height = H;
      s = (H * 0.84) / Math.max(y1 - y0, 1);
      figW = (x1 - x0) * s;
      margin = Math.max(figW * 0.15, W * 0.02);
    };
    const at = (i: number) => margin + (i / (EXPOSURES - 1)) * (W - 2 * margin - figW); // left edge of exposure i

    const figure = (f: Frame, left: number, alpha: number, weight: number) => {
      const P = (p: number[]) => [left + (p[0] * data.width - x0) * s, H * 0.08 + (p[1] * data.height - y0) * s] as const;
      ctx.strokeStyle = `rgba(${INK},${alpha})`;
      ctx.lineCap = "round";
      for (const [pts, edges, lw] of [[f.pose, UPPER_BODY, 1.6], [f.left, HAND, 1.1], [f.right, HAND, 1.1]] as const) {
        if (!pts) continue;
        ctx.lineWidth = lw * weight * dpr;
        ctx.beginPath();
        for (const [a, b] of edges) {
          if (!pts[a] || !pts[b]) continue;
          const [ax, ay] = P(pts[a]), [bx, by] = P(pts[b]);
          ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
        }
        ctx.stroke();
      }
      if (f.pose) { // the head as Marey drew it: a small open disc
        const [hx, hy] = P(f.pose[0]);
        ctx.lineWidth = 1.4 * weight * dpr;
        ctx.beginPath(); ctx.arc(hx, hy, 9 * weight * dpr, 0, Math.PI * 2); ctx.stroke();
      }
    };

    const paint = (p: number) => {
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < EXPOSURES; i++) {
        const k = Math.round((i / (EXPOSURES - 1)) * (n - 1));
        figure(data.frames[k], at(i), 0.13 + 0.22 * (i / (EXPOSURES - 1)), 1);
      }
      if (p < 0) return;
      const fi = Math.min(n - 1, Math.floor(p * n));
      const left = at(p * (EXPOSURES - 1));
      const sx = left + figW / 2;
      const g = ctx.createLinearGradient(sx - 60 * dpr, 0, sx + 60 * dpr, 0);
      g.addColorStop(0, "rgba(242,163,58,0)"); g.addColorStop(0.5, "rgba(242,163,58,0.10)"); g.addColorStop(1, "rgba(242,163,58,0)");
      ctx.fillStyle = g; ctx.fillRect(sx - 60 * dpr, 0, 120 * dpr, H);
      ctx.fillStyle = SAFELIGHT; ctx.fillRect(sx - 0.75 * dpr, 0, 1.5 * dpr, H);
      figure(data.frames[fi], left, 0.98, 1.7);
      ctx.font = `${11 * dpr}px ${mono}`; ctx.fillStyle = SAFELIGHT;
      ctx.fillText(`t ${(fi / data.fps).toFixed(2)} s`, Math.min(sx + 10 * dpr, W - 70 * dpr), H - 10 * dpr);
    };

    resize();
    const ro = new ResizeObserver(() => { resize(); if (reduced) paint(-1); });
    ro.observe(c);
    if (reduced) { paint(-1); figure(data.frames[n - 1], at(EXPOSURES - 1), 0.95, 1.6); return () => ro.disconnect(); }

    let raf = 0, visible = true, t0 = performance.now();
    const seen = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    seen.observe(c);
    const tick = (now: number) => {
      if (visible) paint(((now - t0) % PASS_MS) / PASS_MS); else t0 = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); seen.disconnect(); ro.disconnect(); };
  }, [data]);

  if (failed || sampleId == null) {
    return <div className="grid h-full place-items-center text-sm text-[#8d8c86]">{failed ? "Plate unavailable: the backend is offline." : "Developing the plate…"}</div>;
  }
  return <canvas ref={canvas} className="block h-full w-full" role="img" aria-label={label} />;
}
