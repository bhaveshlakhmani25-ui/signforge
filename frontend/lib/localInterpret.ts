// In-browser port of backend/app/services/interpret.py for the GitHub Pages build, which has no backend.
// Same preprocessing (preprocessing.py), same GRU (baseline_model.py), same weights and thresholds, exported by
// deploy/pages/export_snapshot.py. Checked against the real backend's readings by deploy/pages/check_local_interpret.ts.

type Pts = number[][] | null;
export type InFrame = { t: number; pose: Pts; left_hand: Pts; right_hand: Pts };
export type Model = {
  run_id: number; hidden: number; labels: number[]; train_classes: number[]; label_glosses: Record<string, string>;
  temperature: number; calibration_passed: boolean;
  w_ih: number[]; w_hh: number[]; b_ih: number[]; b_hh: number[]; w_head: number[]; b_head: number[];
};
export type Bundle = {
  target_fps: number; model_frames: number; min_conf: number; min_hand_share: number; min_motion: number;
  minimal_27: number[]; shoulder_nodes_27: number[]; lh_wrist: number; rh_wrist: number; models: Record<string, Model>;
};

export const POSE = 0, LH = 33, RH = 54;
export const at = (f: InFrame, p: number): number[] | null => {
  const [part, off] = p < LH ? [f.pose, POSE] : p < RH ? [f.left_hand, LH] : [f.right_hand, RH];
  return part ? part[p - off] : null;
};

// numpy round(): halves go to the even neighbour.
export const roundEven = (v: number) => { const f = Math.floor(v), d = v - f; return d > 0.5 || (d === 0.5 && f % 2 !== 0) ? f + 1 : f; };

/** numpy.linspace(0, n-1, length).round(): the fixed-length rule shared by training and prediction. */
function fixedLength(n: number, length: number): number[] {
  const step = (n - 1) / (length - 1);
  return Array.from({ length }, (_, i) => (i === length - 1 ? n - 1 : roundEven(i * step)));
}

/** Indices of the frames nearest a uniform fps grid (numpy arange + argmin, first index wins ties). */
export function resample(t: number[], fps: number): number[] {
  const step = 1 / fps, n = Math.max(0, Math.ceil((t[t.length - 1] + 1e-9 - t[0]) / step));
  return Array.from({ length: n }, (_, g) => {
    const target = t[0] + g * step;
    let best = 0;
    for (let i = 1; i < t.length; i++) if (Math.abs(t[i] - target) < Math.abs(t[best] - target)) best = i;
    return best;
  });
}

const sigmoid = (v: number) => 1 / (1 + Math.exp(-v));

function gruLogits(m: Model, x: Float64Array, T: number, F: number): number[] {
  const H = m.hidden;
  let h = new Float64Array(H);
  for (let s = 0; s < T; s++) {
    const xs = x.subarray(s * F, (s + 1) * F);
    const gi = new Float64Array(3 * H), gh = new Float64Array(3 * H);
    for (let r = 0; r < 3 * H; r++) {
      let a = m.b_ih[r], b = m.b_hh[r];
      for (let k = 0; k < F; k++) a += m.w_ih[r * F + k] * xs[k];
      for (let k = 0; k < H; k++) b += m.w_hh[r * H + k] * h[k];
      gi[r] = a; gh[r] = b;
    }
    const next = new Float64Array(H);
    for (let j = 0; j < H; j++) { // PyTorch gate order: reset, update, new
      const rg = sigmoid(gi[j] + gh[j]), zg = sigmoid(gi[H + j] + gh[H + j]);
      const ng = Math.tanh(gi[2 * H + j] + rg * gh[2 * H + j]);
      next[j] = (1 - zg) * ng + zg * h[j];
    }
    h = next;
  }
  const C = m.b_head.length;
  return Array.from({ length: C }, (_, c) => { let v = m.b_head[c]; for (let k = 0; k < H; k++) v += m.w_head[c * H + k] * h[k]; return v; });
}

const r4 = (v: number) => Math.round(v * 1e4) / 1e4;

/** model_input() + GRU + calibrated softmax over the learned signs (rounded to 4 places, as the API returns them). */
export function scoreFrames(b: Bundle, m: Model, frames: InFrame[], learned: number[], vocab: string[]) {
  // model_input(): resample, fixed length, minimal-27 x/y, clip-level centre and scale (missing parts are zeros).
  const idx0 = resample(frames.map((f) => f.t), b.target_fps);
  const idx = fixedLength(idx0.length, b.model_frames).map((i) => idx0[i]);
  const L = b.model_frames, N = b.minimal_27.length, F = N * 2;
  const x = new Float64Array(L * F);
  idx.forEach((fi, s) => b.minimal_27.forEach((p, n) => {
    const pt = at(frames[fi], p);
    x[s * F + n * 2] = pt ? Math.fround(pt[0]) : 0; x[s * F + n * 2 + 1] = pt ? Math.fround(pt[1]) : 0;
  }));
  const [s1, s2] = b.shoulder_nodes_27;
  let cx = 0, cy = 0, dist = 0;
  for (let s = 0; s < L; s++) {
    const ax = x[s * F + s1 * 2], ay = x[s * F + s1 * 2 + 1], bx = x[s * F + s2 * 2], by = x[s * F + s2 * 2 + 1];
    cx += (ax + bx) / 2; cy += (ay + by) / 2; dist += Math.hypot(ax - bx, ay - by);
  }
  cx /= L; cy /= L; dist /= L;
  if (dist > 0) for (let k = 0; k < x.length; k += 2) { x[k] = (x[k] - cx) / dist; x[k + 1] = (x[k + 1] - cy) / dist; }

  const logits = gruLogits(m, x, L, F);
  const z = learned.map((i) => logits[i] / m.temperature), top = Math.max(...z);
  const e = z.map((v) => Math.exp(v - top)), sum = e.reduce((a, v) => a + v, 0);
  const probs = e.map((v) => v / sum);
  const order = probs.map((_, j) => j).sort((a, c) => probs[c] - probs[a]);
  return { probs: probs.map(r4), top3: order.slice(0, 3).map((j) => ({ sign: vocab[j], p: r4(probs[j]) })) };
}

/** The model's learned signs: output units whose class had training clips. */
export function learnedSigns(m: Model) {
  const known = new Set(m.train_classes);
  const learned = m.labels.map((c, i) => [c, i]).filter(([c]) => known.has(c)).map(([, i]) => i);
  return { learned, vocab: learned.map((i) => m.label_glosses[String(m.labels[i])]) };
}

/** The backend's reference_run(): with no project, the latest calibrated run of any project. */
export const referenceModel = (b: Bundle, projectId: number | null): Model | undefined =>
  projectId != null ? b.models[String(projectId)] : Object.values(b.models).sort((p, q) => q.run_id - p.run_id)[0];

export function interpretLocally(b: Bundle, frames: InFrame[], projectId: number | null) {
  const m = referenceModel(b, projectId);
  if (!m) return { state: "no_model", message: "No trained model yet, so nothing can be interpreted.", vocabulary: [] };
  const { learned, vocab } = learnedSigns(m);
  const base: Record<string, unknown> = { vocabulary: vocab, run_id: m.run_id, calibration_passed: m.calibration_passed };

  const T = frames.length;
  if (T < 5) return { ...base, state: "waiting", message: "Waiting for the camera." };
  const hands = frames.filter((f) => f.left_hand || f.right_hand).length;
  if (hands / T < b.min_hand_share) return { ...base, state: "no_hands", message: "No hands in view. Sign with your hands in front of your body." };
  const travel: number[] = [];
  for (const [key, w] of [["left_hand", b.lh_wrist], ["right_hand", b.rh_wrist]] as const) {
    const rows = frames.filter((f) => f[key]);
    if (rows.length > 2) {
      let d = 0;
      for (let i = 1; i < rows.length; i++) { const p = at(rows[i], w)!, q = at(rows[i - 1], w)!; d += Math.hypot(p[0] - q[0], p[1] - q[1]); }
      travel.push((d / Math.max(rows.length - 1, 1)) * 10);
    }
  }
  if (!travel.length || Math.max(...travel) < b.min_motion) return { ...base, state: "still", message: "Hands are still. Make a sign." };

  const { probs, top3 } = scoreFrames(b, m, frames, learned, vocab);
  base.probs = Object.fromEntries(vocab.map((g, j) => [g, probs[j]]));
  const best = top3[0];
  if (best.p < b.min_conf) {
    return { ...base, state: "unsure", top3,
             message: `Not sure. Closest is ${best.sign} at ${Math.round(best.p * 100)}%, which may also be a sign the model has not learned.` };
  }
  return { ...base, state: "sign", sign: best.sign, confidence: best.p, top3 };
}
