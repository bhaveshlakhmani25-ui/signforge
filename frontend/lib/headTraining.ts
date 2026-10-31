// Retrains the interpreter's OUTPUT LAYER in this browser, on the reference run's frozen GRU features plus the visitor's
// approved clips. The GRU is not changed (and it was trained from scratch, so this is not transfer learning). Calibration
// and before/after metrics use the run's own val and frozen test clips, the same rules as backend/app/api/models.py.

import { gruHidden, learnedSigns, modelInput, type Bundle, type InFrame, type Model } from "./localInterpret.ts";

export type Split = { ids: number[]; y: number[]; h: number[][] };
export type Features = { train: Split; val: Split; test: Split };
export type Extra = { id: number; sign_class_id: number; frames: InFrame[] };
export type Metrics = { accuracy: number | null; macro_f1: number | null; ece: number; n_test: number; temperature: number; reliability_passed: boolean };
export type NewSign = { id: number; gloss: string; clips: number };
export type TrainedHead = {
  project_id: number; base_run_id: number; created_at: string; user_sample_ids: number[]; user_weight: number;
  n_dataset_clips: number; w_head: number[]; b_head: number[]; before: Metrics; after: Metrics;
  labels: number[]; train_classes: number[]; label_glosses: Record<string, string>; new_signs: NewSign[]; skipped_signs: NewSign[];
};

export const USER_WEIGHT = 5; // a visitor has a few clips against ~14 dataset clips per sign; each of theirs counts 5 times
export const MIN_NEW_SIGN_CLIPS = 3; // a new sign needs at least this many usable clips before it gets an output
const EPOCHS = 300, LR = 0.01, L2 = 1e-4;

function softmax(z: number[], t = 1) {
  const s = z.map((v) => v / t), m = Math.max(...s), e = s.map((v) => Math.exp(v - m)), sum = e.reduce((a, v) => a + v, 0);
  return e.map((v) => v / sum);
}
const nll = (logits: number[][], y: number[], t: number) => -logits.reduce((a, z, i) => a + Math.log(Math.max(softmax(z, t)[y[i]], 1e-12)), 0) / y.length;
/** Same grid as calibration.fit_temperature: 400 log-spaced values from 0.05 to 20. */
function fitTemperature(logits: number[][], y: number[]) {
  let best = 1, bestNll = Infinity;
  for (let i = 0; i < 400; i++) {
    const t = Math.exp(Math.log(0.05) + (i / 399) * (Math.log(20) - Math.log(0.05)));
    const v = nll(logits, y, t);
    if (v < bestNll) { bestNll = v; best = t; }
  }
  return best;
}
/** calibration.reliability(): expected calibration error over equal-width confidence bins. */
function ece(probs: number[][], y: number[], bins: number) {
  let e = 0;
  for (let b = 0; b < bins; b++) {
    const lo = b / bins, hi = (b + 1) / bins;
    const m = probs.map((p, i) => [Math.max(...p), p.indexOf(Math.max(...p)) === y[i] ? 1 : 0]).filter(([c]) => (lo > 0 ? c > lo : c >= lo) && c <= hi);
    if (m.length) e += (m.length / y.length) * Math.abs(m.reduce((a, [, ok]) => a + ok, 0) / m.length - m.reduce((a, [c]) => a + c, 0) / m.length);
  }
  return e;
}
/** evaluation.classification_metrics(): top-1 accuracy and macro-F1 over classes with test support. */
function scores(pred: number[], y: number[], C: number) {
  if (!y.length) return { accuracy: null, macro_f1: null };
  const f1s: number[] = [];
  for (let c = 0; c < C; c++) {
    const tp = y.filter((v, i) => v === c && pred[i] === c).length, sup = y.filter((v) => v === c).length, got = pred.filter((v) => v === c).length;
    if (!sup) continue;
    const p = got ? tp / got : 0, r = tp / sup;
    f1s.push(p + r ? (2 * p * r) / (p + r) : 0);
  }
  return { accuracy: y.filter((v, i) => v === pred[i]).length / y.length, macro_f1: f1s.reduce((a, v) => a + v, 0) / f1s.length };
}

/** Train an output layer for `m`'s learned signs plus any new signs added in this browser that have enough clips;
 *  evaluate it and the shipped one on the same frozen test clips. */
export function trainHead(b: Bundle & { calibration_bins: number; max_ece: number }, m: Model, projectId: number, f: Features, extra: Extra[],
                          added: { id: number; gloss: string }[] = []): TrainedHead {
  const { learned } = learnedSigns(m), H = m.hidden, C0 = learned.length;
  const count = (id: number) => extra.filter((e) => e.sign_class_id === id).length;
  const candidates = added.filter((a) => !m.labels.includes(a.id)).map((a) => ({ ...a, clips: count(a.id) }));
  const newSigns = candidates.filter((a) => a.clips >= MIN_NEW_SIGN_CLIPS), C = C0 + newSigns.length;
  const cls = new Map([...learned.map((i, j) => [m.labels[i], j] as const), ...newSigns.map((a, k) => [a.id, C0 + k] as const)]); // sign_class_id -> output row
  const rows = (s: Split) => s.h.map((h, i) => ({ h, y: cls.get(s.y[i]) })).filter((r): r is { h: number[]; y: number } => r.y !== undefined);
  const mine = extra.filter((e) => cls.has(e.sign_class_id)).map((e) => {
    const { x, L, F } = modelInput(b, e.frames);
    return { h: Array.from(gruHidden(m, x, L, F)), y: cls.get(e.sign_class_id)!, w: USER_WEIGHT };
  });
  const train = [...rows(f.train).map((r) => ({ ...r, w: 1 })), ...mine], val = rows(f.val), test = rows(f.test);

  // warm start from the shipped layer, then full-batch Adam on weighted cross-entropy with L2
  const W = [...learned.flatMap((i) => m.w_head.slice(i * H, (i + 1) * H)), ...new Array(newSigns.length * H).fill(0)];
  const B = [...learned.map((i) => m.b_head[i]), ...new Array(newSigns.length).fill(0)]; // new signs start from zero
  const mW = new Float64Array(W.length), vW = new Float64Array(W.length), mB = new Float64Array(C), vB = new Float64Array(C);
  const total = train.reduce((a, r) => a + r.w, 0);
  for (let ep = 1; ep <= EPOCHS; ep++) {
    const gW = new Float64Array(W.length), gB = new Float64Array(C);
    for (const r of train) {
      const p = softmax(B.map((bias, c) => { let v = bias; for (let k = 0; k < H; k++) v += W[c * H + k] * r.h[k]; return v; }));
      for (let c = 0; c < C; c++) {
        const g = ((p[c] - (c === r.y ? 1 : 0)) * r.w) / total;
        gB[c] += g;
        for (let k = 0; k < H; k++) gW[c * H + k] += g * r.h[k];
      }
    }
    const adam = (P: number[], G: Float64Array, M: Float64Array, V: Float64Array, decay: number) => {
      for (let i = 0; i < P.length; i++) {
        const g = G[i] + decay * P[i];
        M[i] = 0.9 * M[i] + 0.1 * g; V[i] = 0.999 * V[i] + 0.001 * g * g;
        P[i] -= (LR * (M[i] / (1 - 0.9 ** ep))) / (Math.sqrt(V[i] / (1 - 0.999 ** ep)) + 1e-8);
      }
    };
    adam(W, gW, mW, vW, L2); adam(B, gB, mB, vB, 0);
  }

  const evaluate = (Wh: number[], Bh: number[], fitT: boolean): Metrics => {
    const lg = (rs: { h: number[] }[]) => rs.map((r) => Bh.map((bias, c) => { let v = bias; for (let k = 0; k < H; k++) v += Wh[c * H + k] * r.h[k]; return v; }));
    const t = fitT ? fitTemperature(lg(val), val.map((r) => r.y)) : m.temperature;
    const tl = lg(test), ty = test.map((r) => r.y), probs = tl.map((z) => softmax(z, t));
    const e = ece(probs, ty, b.calibration_bins);
    return { ...scores(probs.map((p) => p.indexOf(Math.max(...p))), ty, C), ece: e, n_test: ty.length, temperature: t,
             reliability_passed: e <= b.max_ece && nll(tl, ty, t) <= nll(tl, ty, 1) };
  };
  const shippedW = learned.flatMap((i) => m.w_head.slice(i * H, (i + 1) * H)), shippedB = learned.map((i) => m.b_head[i]);
  const after = evaluate(W, B, true);

  // write the learned rows back into a full-size layer (rows for signs without training clips stay as shipped), then append new signs
  const w_head = [...m.w_head, ...W.slice(C0 * H)], b_head = [...m.b_head, ...B.slice(C0)];
  learned.forEach((i, j) => { for (let k = 0; k < H; k++) w_head[i * H + k] = W[j * H + k]; b_head[i] = B[j]; });
  return { project_id: projectId, base_run_id: m.run_id, created_at: new Date().toISOString(), user_sample_ids: extra.filter((e) => cls.has(e.sign_class_id)).map((e) => e.id),
           user_weight: USER_WEIGHT, n_dataset_clips: rows(f.train).length, w_head, b_head, before: evaluate(shippedW, shippedB, false), after,
           labels: [...m.labels, ...newSigns.map((a) => a.id)], train_classes: [...m.train_classes, ...newSigns.map((a) => a.id)],
           label_glosses: { ...m.label_glosses, ...Object.fromEntries(newSigns.map((a) => [String(a.id), a.gloss])) },
           new_signs: newSigns, skipped_signs: candidates.filter((a) => a.clips < MIN_NEW_SIGN_CLIPS) };
}

/** The interpreter model with a retrained output layer swapped in (its calibration comes from the retrain). */
export const withHead = (m: Model, t: TrainedHead): Model =>
  ({ ...m, w_head: t.w_head, b_head: t.b_head, temperature: t.after.temperature, calibration_passed: t.after.reliability_passed,
     labels: t.labels ?? m.labels, train_classes: t.train_classes ?? m.train_classes, label_glosses: t.label_glosses ?? m.label_glosses });
