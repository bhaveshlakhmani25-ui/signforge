// Reads a whole video's landmarks the way Interpret live reads the camera: WINDOW_S windows every EVERY_S, a sign kept
// once it is read twice in a row, and the same sign within 4 s counted once. Times are the video's own seconds.

type Pts = number[][] | null;
export type TFrame = { t: number; pose: Pts; left_hand: Pts; right_hand: Pts };
export type TReading = { state: string; sign?: string; confidence?: number; top3?: { sign: string; p: number }[] };
export type Line = { t: number; sign: string | null; p: number | null; note?: string };

export async function transcribe(frames: TFrame[], read: (window: TFrame[]) => Promise<TReading>,
                                 windowS = 2.5, everyS = 0.6, onProgress?: (t: number, end: number) => void): Promise<Line[]> {
  const end = frames.at(-1)?.t ?? 0, out: Line[] = [];
  let pending: string | null = null;
  const ends: number[] = [];
  for (let e = Math.min(windowS, end); e < end - 1e-9; e += everyS) ends.push(e);
  ends.push(end); // the last window ends with the video, so a final sign is not cut off
  for (const e of ends) {
    onProgress?.(e, end);
    const win = frames.filter((f) => f.t > e - windowS && f.t <= e);
    if (win.length < 5) continue;
    const r = await read(win.map((f) => ({ ...f, t: f.t - win[0].t })));
    const s = r.state === "sign" ? r.sign! : null, last = out.at(-1);
    if (s && s === pending && !(last?.sign === s && e - last.t < 4)) out.push({ t: e, sign: s, p: r.confidence! });
    // a run of unsure windows is shown once, so the reader sees where the model hesitated
    if (r.state === "unsure" && last?.sign !== null) out.push({ t: e, sign: null, p: r.top3?.[0]?.p ?? null, note: r.top3?.[0]?.sign });
    pending = s;
  }
  return out;
}
