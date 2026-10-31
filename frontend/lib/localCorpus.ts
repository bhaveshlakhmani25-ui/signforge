// Recording on the GitHub Pages build, which has no backend. Signers, consents, clips and reviews are kept in THIS
// browser (IndexedDB) and never sent anywhere. The automated check is a port of backend/app/services/quality_checks.py
// and the model check a port of triage.predict(), both checked by deploy/pages/check_local_interpret.ts.

import { at, learnedSigns, roundEven, referenceModel, resample, scoreFrames, type Bundle, type InFrame } from "./localInterpret.ts"; // explicit extension: deploy/pages/check_local_interpret.ts runs this file in Node

export type LocalBundle = Bundle & {
  qc: Record<string, number>; pose_l_wrist: number; pose_r_wrist: number;
  verify_min_conf: number; verify_margin: number; model_verify_enabled: boolean;
};
type Flag = { code: string; severity: "error" | "warning"; message: string };
type Row = Record<string, unknown> & { id: number };

const pct = (v: number) => `${roundEven(v * 100)}%`; // Python's :.0% rounds halves to even
const r3 = (v: number) => Math.round(v * 1000) / 1000;
const py = (v: number) => (Number.isInteger(v) ? v.toFixed(1) : String(v)); // Python prints 8.0, not 8

/** Port of run_qc(): technical capture quality only, never a language check. */
export function runQc(b: LocalBundle, frames: InFrame[], width: number, height: number) {
  const Q = b.qc, flags: Flag[] = [];
  const flag = (code: string, severity: Flag["severity"], message: string) => flags.push({ code, severity, message });
  const T = frames.length;
  if (T === 0) {
    flag("empty", "error", "No frames were extracted. Check the camera, lighting and that the signer is in view.");
    return { passed: false, flags, metrics: { frame_count: 0 }, completeness: 0 };
  }
  const mean = (f: (x: InFrame) => boolean) => frames.filter(f).length / T;
  const duration = frames[T - 1].t - frames[0].t;
  const poseMissing = 1 - mean((f) => !!f.pose);
  const noHand = 1 - mean((f) => !!(f.left_hand || f.right_hand));
  const completeness = mean((f) => !!f.pose && !!(f.left_hand || f.right_hand));

  let mismatched = 0, checked = 0; // each hand's wrist should sit nearer its own pose wrist (catches left/right swaps)
  for (const [key, handWrist, own, other] of [["left_hand", b.lh_wrist, b.pose_l_wrist, b.pose_r_wrist], ["right_hand", b.rh_wrist, b.pose_r_wrist, b.pose_l_wrist]] as const) {
    for (const f of frames) {
      if (!f.pose || !f[key]) continue;
      const w = at(f, handWrist)!, o = at(f, own)!, x = at(f, other)!;
      if (Math.hypot(w[0] - x[0], w[1] - x[1]) < Math.hypot(w[0] - o[0], w[1] - o[1])) mismatched++;
      checked++;
    }
  }
  const sideMismatch = checked ? mismatched / checked : 0;
  let outside = 0, used = 0; // only the points the model uses: a seated webcam never shows hips or legs
  for (const f of frames) for (const pt of b.minimal_27.map((p) => at(f, p))) {
    if (!pt) continue;
    used++;
    if (pt[0] < 0 || pt[0] > 1 || pt[1] < 0 || pt[1] > 1) outside++;
  }
  const outOfFrame = used ? outside / used : 0;

  const handMetrics: Record<string, number> = {};
  if (duration < Q.QC_MIN_DURATION_S) flag("too_short", "error", `Clip is ${duration.toFixed(1)}s; at least ${py(Q.QC_MIN_DURATION_S)}s is needed for one sign.`);
  if (duration > Q.QC_MAX_DURATION_S) flag("too_long", "error", `Clip is ${duration.toFixed(1)}s; record one sign per clip (max ${py(Q.QC_MAX_DURATION_S)}s).`);
  if (poseMissing > Q.QC_MAX_MISSING_SHOULDER_RATE) flag("body_missing", "error", `Upper body not detected in ${pct(poseMissing)} of frames; shoulders must stay in view.`);
  if (noHand > Q.QC_MAX_NO_HAND_RATE) flag("hands_missing", "error", `No hand detected in ${pct(noHand)} of frames; sign with your hands in front of your body and in good light.`);
  for (const [key, side] of [["left_hand", "left"], ["right_hand", "right"]] as const) {
    const missing = 1 - mean((f) => !!f[key]);
    handMetrics[`${side}_hand_missing_rate`] = r3(missing);
    // a hand never seen is likely a one-handed sign; a hand seen only sometimes is a tracking dropout
    if (Q.QC_MAX_HAND_DROPOUT_RATE < missing && missing < 1) {
      flag(`${side}_hand_dropout`, "warning", `Signer's ${side}-hand landmarks missing in ${pct(missing)} of frames; improve lighting or keep the hand in view.`);
    }
  }
  if (sideMismatch > Q.QC_MAX_HAND_SIDE_MISMATCH_RATE) flag("hand_side_mismatch", "error", `In ${pct(sideMismatch)} of frames a hand is labelled with the wrong side; the video may be mirrored.`);
  if (outOfFrame > 0.05) flag("out_of_frame", "warning", `${pct(outOfFrame)} of the face, arm and hand landmarks are outside the frame; step back or centre yourself.`);
  if (height && Math.abs(width / height - 16 / 9) > 0.05) {
    flag("aspect_ratio", "warning", `Video is ${width}x${height}, not 16:9 like the pretraining data, so landmark positions may be slightly distorted. Use a 16:9 camera setting if you can.`);
  }
  const metrics = { frame_count: T, duration_s: r3(duration), pose_missing_rate: r3(poseMissing), no_hand_rate: r3(noHand),
                    hand_side_mismatch_rate: r3(sideMismatch), out_of_frame_rate: r3(outOfFrame), ...handMetrics };
  return { passed: !flags.some((f) => f.severity === "error"), flags, metrics, completeness: r3(completeness) };
}

/** Port of triage.predict(), minus the near-duplicate distance (other clips' landmarks are not in this browser). */
function triage(b: LocalBundle, sampleId: number, gloss: string, qc: ReturnType<typeof runQc>, frames: InFrame[]): Record<string, unknown> & { status: string } {
  const out: Record<string, unknown> = {
    sample_id: sampleId, claimed_sign: gloss, quality: { passed: qc.passed, failed_checks: qc.flags.filter((f) => f.severity === "error").map((f) => f.code) },
    model: null, match_confidence: null, predicted_sign: null, top3: [], per_sign_test_recall: null, calibration_note: null,
    is_near_duplicate: false, nearest_same_sign_distance: null, audited: false, auto_accept_enabled: b.model_verify_enabled,
  };
  if (!qc.passed) return { ...out, status: "auto_rejected", reason: "The automated check failed, so the clip needs to be recorded again." };
  const m = referenceModel(b, null);
  if (!m) return { ...out, status: "needs_review", reason: "No calibrated model exists yet, so a reviewer has to check this clip." };
  const { learned, vocab } = learnedSigns(m);
  out.model = { run_id: m.run_id, temperature: m.temperature, reliability_passed: m.calibration_passed, signs: vocab };
  if (!vocab.includes(gloss)) return { ...out, status: "needs_review", reason: `The model has not learned ${gloss}, so it cannot score this clip. A reviewer has to check it.` };
  const { probs, top3 } = scoreFrames(b, m, frames, learned, vocab);
  const conf = probs[vocab.indexOf(gloss)], top = top3[0].sign;
  Object.assign(out, { match_confidence: conf, predicted_sign: top, top3 });
  const agrees = top === gloss, confident = conf >= b.verify_min_conf + b.verify_margin, autoOn = b.model_verify_enabled && m.calibration_passed;
  if (autoOn && agrees && confident) return { ...out, status: "model_verified", reason: `The model agrees this is ${gloss} at ${pct(conf)}.` };
  const why = !agrees ? `The model thinks this looks more like ${top} (${pct(top3[0].p)}) than ${gloss} (${pct(conf)}).`
    : !confident ? `The model agrees but is only ${pct(conf)} sure.`
    : !autoOn ? "The model agrees, but auto-accept is switched off until a model passes its reliability check."
    : `The model agrees at ${pct(conf)}.`;
  return { ...out, status: "needs_review", reason: `${why} A reviewer has to check it.` };
}

// ---- storage: one IndexedDB database, ids far above the snapshot's so they never collide ----
const FIRST_ID = 1_000_001;
const STORES = ["signers", "consents", "samples", "reviews"] as const;
type Store = (typeof STORES)[number];
let dbp: Promise<IDBDatabase> | null = null;
const fail = (e: unknown): never => {
  throw new Error(`This browser would not save the clip here (${e instanceof Error ? e.message : String(e)}). Private windows and full storage can block it.`);
};
function db() {
  dbp ??= new Promise<IDBDatabase>((res, rej) => {
    const r = indexedDB.open("signforge-local", 1);
    r.onupgradeneeded = () => STORES.forEach((s) => r.result.createObjectStore(s, { keyPath: "id" }));
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  }).catch((e) => { dbp = null; return fail(e); });
  return dbp;
}
async function tx<T>(store: Store, mode: IDBTransactionMode, op: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const d = await db();
  return new Promise<T>((res, rej) => {
    const r = op(d.transaction(store, mode).objectStore(store));
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  }).catch(fail);
}
const all = (s: Store) => tx<Row[]>(s, "readonly", (o) => o.getAll() as IDBRequest<Row[]>);
const get = (s: Store, id: number) => tx<Row | undefined>(s, "readonly", (o) => o.get(id) as IDBRequest<Row | undefined>);
const put = (s: Store, row: Row) => tx(s, "readwrite", (o) => o.put(row)).then(() => row);
const del = (s: Store, id: number) => tx(s, "readwrite", (o) => o.delete(id));
const nextId = async (s: Store) => Math.max(FIRST_ID - 1, ...(await all(s)).map((r) => r.id)) + 1;
const now = () => new Date().toISOString();
const httpError = (status: number, message: string) => Object.assign(new Error(message), { status });
const isLocal = (id: number) => id >= FIRST_ID;
const publicRow = ({ frames, ...row }: Row) => (void frames, row); // stored landmarks stay out of list responses

async function sha256(frames: InFrame[]) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(frames)));
  return [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function deleteSample(id: number) {
  for (const r of (await all("reviews")).filter((r) => r.sample_id === id)) await del("reviews", r.id);
  await del("samples", id);
}

export const NOT_LOCAL = Symbol("not local");
type Snap = <T>(path: string) => Promise<T>;

/** Requests the browser answers itself on the Pages build. NOT_LOCAL means: read the frozen snapshot instead. */
export async function localRequest(path: string, method: string, body: unknown, snap: Snap, bundle: () => Promise<LocalBundle>): Promise<unknown> {
  const url = new URL(path, "http://x"), q = (k: string) => url.searchParams.get(k);
  const b = (body ?? {}) as Record<string, unknown>;
  const route = `${method} ${url.pathname.replace(/\/\d+(?=\/|$)/g, "/:id")}`;
  const id = Number(url.pathname.match(/\/(\d+)(?=\/|$)/)?.[1]);
  const snapOr = async <T,>(p: string, fallback: T) => snap<T>(p).catch(() => fallback);

  switch (route) {
    case "POST /api/signers": {
      const mine = (await all("signers")).find((s) => s.project_id === b.project_id && s.code === b.code);
      return mine ?? put("signers", { id: await nextId("signers"), project_id: b.project_id, code: b.code, created_at: now() });
    }
    case "GET /api/signers":
      return [...await snapOr<Row[]>(path, []), ...(await all("signers")).filter((s) => s.project_id === Number(q("project_id")))];
    case "POST /api/consents": {
      if (!(await get("signers", Number(b.signer_id)))) throw httpError(404, "Signer not found. Reload the page and try again.");
      const { confirmed, ...rest } = b;
      void confirmed;
      return put("consents", { ...rest, id: await nextId("consents"), raw_video_retained: false, status: "active", created_at: now() });
    }
    case "GET /api/consents": {
      const signer = Number(q("signer_id"));
      return isLocal(signer) ? (await all("consents")).filter((c) => c.signer_id === signer) : snap(path);
    }
    case "POST /api/consents/:id/withdraw": {
      const c = isLocal(id) ? await get("consents", id) : undefined;
      if (!c) throw httpError(403, "Only consents recorded in this browser can be changed in the public demo.");
      await put("consents", { ...c, status: "withdrawn" });
      const affected = (await all("samples")).filter((s) => s.consent_id === id);
      for (const s of affected) {
        if (b.delete_samples) await deleteSample(s.id);
        else if (!String(s.provenance_note).includes("[CONSENT WITHDRAWN]")) await put("samples", { ...s, provenance_note: `${s.provenance_note} [CONSENT WITHDRAWN]` });
      }
      return { status: "withdrawn", deleted_samples: b.delete_samples ? affected.length : 0 };
    }
    case "POST /api/samples/capture": {
      const classes = await snap<{ id: number; gloss: string }[]>(`/api/sign-classes?project_id=${b.project_id}`);
      const sign = classes.find((c) => c.id === b.sign_class_id);
      const signer = await get("signers", Number(b.signer_id)), consent = await get("consents", Number(b.consent_id));
      if (!sign || !signer || signer.project_id !== b.project_id) throw httpError(422, "That sign or signer belongs to a different project. Reload the page and try again.");
      if (!consent || consent.signer_id !== signer.id || consent.status !== "active") throw httpError(403, "No active consent record for this signer; record consent before capturing.");
      if (!(consent.allowed_uses as string[]).includes("corpus_building")) throw httpError(403, "This signer's consent does not allow corpus building.");
      const frames = b.frames as InFrame[], width = Number(b.width), height = Number(b.height);
      const B = await bundle(), qc = runQc(B, frames, width, height), sha = await sha256(frames);
      const dup = (await all("samples")).find((s) => s.project_id === b.project_id && s.feature_sha256 === sha);
      if (dup) { qc.flags.push({ code: "duplicate", severity: "error", message: `Identical landmarks already stored as sample #${dup.id}.` }); qc.passed = false; }
      const sid = await nextId("samples"), t = triage(B, sid, sign.gloss, qc, frames);
      const sample: Row = {
        id: sid, project_id: b.project_id, sign_class_id: sign.id, signer_id: signer.id, consent_id: consent.id, source: b.source,
        feature_path: "", feature_schema_version: "mp-holistic-75-xyz-v1", extractor: b.extractor, extractor_model_sha: b.extractor_model_sha,
        fps: b.fps, width, height, mirrored: false, frame_count: frames.length, quality_score: qc.completeness, qc_passed: qc.passed,
        quality_flags: qc.flags, qc_metrics: qc.metrics, feature_sha256: sha, review_status: "pending_review", split: "unassigned",
        collection_round: 0, raw_video_retained: false, provenance_note: "Captured in SIGNFORGE public demo; landmarks only, stored in this browser",
        dataset_name: "", dataset_version: "", dataset_license: "", citation: "", external_sample_id: "", external_signer_id: "", external_split: "",
        triage_status: b.source === "captured" ? t.status : "", triage: b.source === "captured" ? t : {},
        match_confidence: b.source === "captured" ? t.match_confidence : null, predicted_sign: b.source === "captured" ? t.predicted_sign ?? "" : "",
        is_near_duplicate: false, audited: false, created_at: now(), frames,
      };
      return publicRow(await put("samples", sample));
    }
    case "GET /api/samples": {
      const pid = Number(q("project_id")), demo = q("include_demo") === "true";
      const mine = (await all("samples")).filter((s) => s.project_id === pid && (demo || s.source !== "demo_fixture")).sort((x, y) => y.id - x.id);
      return [...mine.map(publicRow), ...await snapOr<Row[]>(path, [])];
    }
  }
  if (!isLocal(id)) return NOT_LOCAL;
  const sample = await get("samples", id);
  if (!sample) throw httpError(404, "Sample not found.");
  switch (route) {
    case "GET /api/samples/:id/landmarks": {
      const frames = sample.frames as InFrame[], xy = (pts: number[][] | null) => pts && pts.map((p) => [Math.round(p[0] * 1e4) / 1e4, Math.round(p[1] * 1e4) / 1e4]);
      return { sample_id: id, source: sample.source, fps: 15, width: sample.width, height: sample.height,
               frames: resample(frames.map((f) => f.t), 15).map((i) => ({ pose: xy(frames[i].pose), left: xy(frames[i].left_hand), right: xy(frames[i].right_hand) })) };
    }
    case "GET /api/samples/:id/reviews":
      return (await all("reviews")).filter((r) => r.sample_id === id);
    case "POST /api/samples/:id/review": {
      const ev = await put("reviews", { id: await nextId("reviews"), sample_id: id, reviewer_code: b.reviewer_code, reviewer_role: b.reviewer_role,
                                        decision: b.decision, note: b.note ?? "", created_at: now() });
      await put("samples", { ...sample, review_status: b.decision });
      return ev;
    }
    case "DELETE /api/samples/:id":
      await deleteSample(id);
      return null;
  }
  return NOT_LOCAL;
}

/** Everything this browser holds, for "Download my clips" (landmarks only; there is never any video). */
export async function exportLocal() {
  return { exported_at: now(), note: "SIGNFORGE public demo: recorded in this browser, landmarks only. Never uploaded anywhere.",
           signers: await all("signers"), consents: await all("consents"), samples: await all("samples"), reviews: await all("reviews") };
}
