"use client";

import { useCallback, useEffect, useState } from "react";
import { api, currentProject, loadModelBundle, readSnapshot, SNAPSHOT, type Calibration, type ModelRun, type SignClass, when } from "@/lib/api";
import { MIN_NEW_SIGN_CLIPS, type Features, type TrainedHead } from "@/lib/headTraining";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";

const pct = (v?: number | null) => (v == null ? "Not evaluated" : `${(v * 100).toFixed(1)}%`);

async function fetchModels() {
  const project = await currentProject();
  if (!project) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
  const [runs, classes] = await Promise.all([
    api<ModelRun[]>(`/api/models/runs?project_id=${project.id}`),
    api<SignClass[]>(`/api/sign-classes?project_id=${project.id}`),
  ]);
  return { project, runs, classes };
}

function CalibrationBlock({ c }: { c: Calibration }) {
  const ece = (v: number) => v.toFixed(3);
  return (
    <div className="space-y-2 text-sm">
      <p className="max-w-[58ch]">
        <span className={`mr-2 rounded-md px-2 py-0.5 text-xs ${c.reliability_passed ? "bg-teal/15 text-teal" : "bg-amber-100 text-amber-950"}`}>
          Reliability check {c.reliability_passed ? "passed" : "failed"}</span>
        Calibrated with temperature scaling (T = {c.temperature.toFixed(2)}, fitted on {c.n_val} validation clips), judged on the {c.test_after.n} frozen test clips:
        calibration error {ece(c.test_before.ece)} → {ece(c.test_after.ece)} (pass at ≤ {c.max_ece}), log-loss {c.test_nll_before.toFixed(2)} → {c.test_nll_after.toFixed(2)}.
        {!c.reliability_passed && " Confidence percentages from this model still overstate how often it is right."}
      </p>
      <details>
        <summary className="cursor-pointer text-indigo">How often the calibrated model was right, by confidence (test clips)</summary>
        <table className="mt-2 text-xs">
          <thead><tr>{["Confidence", "Clips", "Mean confidence", "Actually right"].map((h) => <th key={h} scope="col" className="p-1 pr-3 text-left font-medium">{h}</th>)}</tr></thead>
          <tbody>{c.test_after.bins.map((b) => (
            <tr key={b.lo} className="border-t border-lavender/60 tabular-nums">
              <td className="p-1 pr-3">{Math.round(b.lo * 100)}–{Math.round(b.hi * 100)}%</td><td className="p-1 pr-3">{b.n}</td>
              <td className="p-1 pr-3">{b.mean_confidence == null ? "–" : pct(b.mean_confidence)}</td>
              <td className="p-1 pr-3">{b.accuracy == null ? "–" : `${pct(b.accuracy)} (${Math.round(b.accuracy * b.n)}/${b.n})`}</td>
            </tr>))}</tbody>
        </table>
      </details>
    </div>
  );
}

export default function ModelsPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchModels>> | null>(null);
  const [error, setError] = useState("");
  const [trainError, setTrainError] = useState("");
  const [training, setTraining] = useState<"" | ModelRun["pool"]>("");

  const reload = useCallback(() => fetchModels().then((d) => { setData(d); setError(""); }, (e) => setError(e.message)), []);
  useEffect(() => { reload(); }, [reload]);

  async function train(pool: ModelRun["pool"]) {
    setTraining(pool); setTrainError("");
    try {
      await api<ModelRun>("/api/models/train-baseline", { body: { project_id: data!.project.id, pool } });
      await reload();
    } catch (e) { setTrainError(e instanceof Error ? e.message : String(e)); }
    setTraining("");
  }

  const gloss = (id: number) => data?.classes.find((c) => c.id === id)?.gloss ?? `#${id}`;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Models &amp; evaluation</h1>
        <p className="mt-1 max-w-[58ch] text-sm">
          Models here are research instruments to test whether the collected data is useful, not a translator.
          Every number below is an actual run output, shown with its split and sample counts.
        </p>
      </header>
      {error && <ErrorBanner message={`Could not load the models. ${error}`} onRetry={() => { setError(""); reload(); }} />}
      {SNAPSHOT && data && <BrowserRetrain projectId={data.project.id} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="baseline" className={card}>
          <h2 id="baseline" className="font-semibold">Baseline (from scratch)</h2>
          <p className="mt-1 text-sm">Small GRU over 27 body/hand points, randomly initialised: <strong>not pretrained</strong>. Trains on real samples that passed the automated check, were approved in human review, and come from signers who allowed model training. The first run fixes the test set; later runs reuse it, so results stay comparable.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="rounded-lg bg-indigo px-3 py-2 text-sm text-white disabled:opacity-60" disabled={!data || !!training || SNAPSHOT} title={SNAPSHOT ? "Full training needs the backend; retrain the output layer below instead" : undefined} onClick={() => train("real")}>
              {training === "real" ? "Training…" : "Train on approved real samples"}
            </button>
            <button className="rounded-lg border border-amber-600 px-3 py-2 text-sm text-amber-900 disabled:opacity-60" disabled={!data || !!training || SNAPSHOT} title={SNAPSHOT ? "Full training needs the backend; retrain the output layer below instead" : undefined} onClick={() => train("demo")}>
              {training === "demo" ? "Training…" : "Train on DEMO DATA"}
            </button>
            <button className="rounded-lg border border-indigo px-3 py-2 text-sm text-indigo disabled:opacity-60" disabled={!data || !!training || SNAPSHOT} title={SNAPSHOT ? "Full training needs the backend; retrain the output layer below instead" : undefined} onClick={() => train("external")}>
              {training === "external" ? "Training…" : "Train on external dataset"}
            </button>
            <button className="rounded-lg border border-indigo px-3 py-2 text-sm text-indigo disabled:opacity-60" disabled={!data || !!training || SNAPSHOT} title={SNAPSHOT ? "Full training needs the backend; retrain the output layer below instead" : undefined} onClick={() => train("combined")}>
              {training === "combined" ? "Training…" : "Train on dataset + our approved clips"}
            </button>
          </div>
          {trainError && <p role="alert" className="mt-2 text-sm text-red-900">Training didn&apos;t start. {trainError}</p>}
        </section>
        <section aria-labelledby="transfer" className={card}>
          <h2 id="transfer" className="font-semibold">Transfer / adapter</h2>
          <p className="mt-1 text-sm"><span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs text-amber-950">Blocked</span>{" "}
            Transfer learning is unavailable because no compatible checkpoint has been verified. The OpenHands DPC encoder is the candidate;
            its loading and input-format tests are not written yet (see docs/MODEL_CARD.md).</p>
        </section>
      </div>

      <section aria-labelledby="runs" className="space-y-3">
        <h2 id="runs" className="font-semibold">Runs</h2>
        {data && !data.runs.length && <p className={`${card} text-sm`}>No runs yet. Nothing has been evaluated.</p>}
        {data?.runs.map((r) => (
          <article key={r.id} className={`${card} space-y-3 ${r.pool === "demo" ? "border-amber-300" : ""}`} aria-label={`Run ${r.id}`}>
            <header className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold">Run #{r.id} · {r.model_kind}</h3>
              {r.pool === "demo" && <DemoBadge />}
              <span className={`rounded-md px-2 py-0.5 text-xs ${r.status === "succeeded" ? "bg-teal/15 text-teal" : r.status === "failed" ? "bg-red-100 text-red-900" : "bg-amber-100 text-amber-950"}`}>{r.status}</span>
              <span className="text-xs text-indigo">{when(r.created_at)} · {r.duration_s}s</span>
            </header>
            {r.pool === "external" && <p className="max-w-[58ch] text-xs">External dataset (labels come from the dataset, not from our reviewers). The test set holds out whole recording sessions per sign; signer identity is unknown, so these results are <strong>not</strong> signer-independent.</p>}
            {r.pool === "combined" && <p className="max-w-[58ch] text-xs">External dataset plus this team&apos;s human-approved, consented clips (from Capture and Learn). Tested on the dataset&apos;s same frozen test set, so it shows whether adding our clips kept dataset accuracy; it does <strong>not</strong> measure accuracy on our own signing.</p>}
            {r.pool === "demo" && <p className="text-xs text-amber-900">Synthetic DEMO DATA: these numbers only show the pipeline works. They say nothing about real {data.project.target_language} performance.</p>}
            {r.status === "failed" && <p className="text-sm text-red-900">{r.failure_detail}</p>}
            {r.status === "succeeded" && (
              <>
                <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div><dt className="text-xs text-indigo">Top-1 accuracy</dt><dd className="text-xl font-semibold">{pct(r.metrics.accuracy)}</dd></div>
                  <div><dt className="text-xs text-indigo">Macro-F1</dt><dd className="text-xl font-semibold">{pct(r.metrics.macro_f1)}</dd></div>
                  <div><dt className="text-xs text-indigo">Train / test samples</dt><dd className="text-xl font-semibold">{r.metrics.n_train} / {r.metrics.n_test}</dd></div>
                  <div><dt className="text-xs text-indigo">Data version</dt><dd className="font-mono text-sm">{r.data_version}</dd></div>
                </dl>
                <p className="max-w-[58ch] text-xs"><strong>Split:</strong> {r.split_strategy}. Macro-F1 is averaged over {r.metrics.macro_f1_over}.
                  {" "}<strong>Checkpoint:</strong> {r.checkpoint_reference}. <strong>Seed:</strong> {r.seed}. <strong>Config:</strong> {Object.entries(r.config).map(([k, v]) => `${k}=${v}`).join(", ")}.</p>
                {r.metrics.calibration && <CalibrationBlock c={r.metrics.calibration} />}
                {r.metrics.confusion_matrix && r.metrics.labels && (
                  <details>
                    <summary className="cursor-pointer text-sm text-indigo">Confusion matrix and per-class results</summary>
                    <div className="relative mt-2 overflow-x-auto">
                      <table className="text-xs">
                        <caption className="pb-1 text-left">Rows: true sign · columns: predicted sign</caption>
                        <thead><tr><th scope="col" className="p-1"><span className="sr-only">True sign</span></th>
                          {r.metrics.labels.map((l) => <th key={l} scope="col" className="p-1 font-medium">{gloss(l)}</th>)}
                          <th scope="col" className="p-1 font-medium">Recall</th><th scope="col" className="p-1 font-medium">F1</th></tr></thead>
                        <tbody>
                          {r.metrics.confusion_matrix.map((row, i) => {
                            const l = r.metrics.labels![i];
                            const pc = r.metrics.per_class?.[l];
                            return (
                              <tr key={l}>
                                <th scope="row" className="p-1 text-left font-medium">{gloss(l)}</th>
                                {row.map((v, j) => <td key={j} className={`p-1 text-center ${v ? (i === j ? "bg-teal/20" : "bg-red-100") : ""}`}>{v}</td>)}
                                <td className="p-1 text-center tabular-nums">{pc?.support ? `${row[i]}/${pc.support}` : "–"}</td>
                                <td className="p-1 text-center">{pc?.support ? pc.f1.toFixed(2) : "–"}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}
              </>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}

const pc = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

async function retrainState(projectId: number) {
  const [{ trainingClips, activeHead }, bundle] = await Promise.all([import("@/lib/localCorpus"), loadModelBundle()]);
  const [{ counts, clips, added }, { head, dropped }] = await Promise.all([trainingClips(projectId), activeHead(projectId, bundle.models[String(projectId)]?.run_id)]);
  const newSigns = added.map((a) => ({ gloss: a.gloss, clips: clips.filter((c) => c.sign_class_id === a.id).length }));
  return { counts, newSigns, head, dropped, hasModel: String(projectId) in bundle.models };
}

/** Public demo: retrain the interpreter's output layer in this browser on the dataset plus this visitor's approved clips. */
function BrowserRetrain({ projectId }: { projectId: number }) {
  const [state, setState] = useState<Awaited<ReturnType<typeof retrainState>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TrainedHead | null>(null);

  const load = useCallback(() => retrainState(projectId).then(setState, (e) => setError(e instanceof Error ? e.message : String(e))), [projectId]);
  useEffect(() => { load(); }, [load]);

  async function retrain() {
    setBusy(true); setError("");
    try {
      const [{ trainingClips }, { trainHead }, bundle, feats] = await Promise.all([
        import("@/lib/localCorpus"), import("@/lib/headTraining"), loadModelBundle(), readSnapshot<Features>(`/interpret/features/${projectId}`)]);
      await new Promise((r) => setTimeout(r)); // let "Training…" paint before the CPU-bound loop
      const { clips, added } = await trainingClips(projectId);
      const head = trainHead(bundle, bundle.models[String(projectId)], projectId, feats, clips, added);
      setResult(head);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  }
  async function use(head: TrainedHead | null) {
    const { saveHead, clearHead } = await import("@/lib/localCorpus");
    try { if (head) saveHead(head); else clearHead(projectId); } catch (e) { setError(`Not saved in this browser: ${e instanceof Error ? e.message : e}`); }
    setResult(null); await load();
  }

  if (!state) return error ? <ErrorBanner message={error} /> : null;
  const c = state.counts, shown = result ?? state.head;
  return (
    <section aria-labelledby="retrain" className={card}>
      <h2 id="retrain" className="font-semibold">Retrain the output layer in this browser</h2>
      <p className="mt-1 max-w-[75ch] text-sm">
        Interpret uses this project&apos;s reference model. Here only its final layer is retrained, on that run&apos;s frozen features of the dataset
        clips plus your approved clips from this browser. The GRU itself does not change and was trained from scratch, so this is <strong>not transfer learning</strong>.
        Each of your clips counts 5 times, because each sign has only about 14 dataset clips. Nothing leaves this browser.
      </p>
      {!state.hasModel
        ? <p className="mt-3 text-sm text-amber-900">This project has no trained model, so there is no output layer to retrain. Switch to a dataset project in the sidebar.</p>
        : (
          <>
            <p className="mt-3 text-sm">
              Your clips in this project: {c.recorded} recorded · {c.passed} passed the automated check · {c.approved} approved · <strong>{c.eligible} usable for training</strong>.
              {c.eligible === 0 && " A clip is usable once it passes the automated check, you approve it in Corpus & review, and its consent allows model training (an optional box when you record consent)."}
            </p>
            {state.newSigns.length > 0 && (
              <p className="mt-2 text-sm">Signs you added: {state.newSigns.map((n) => `${n.gloss} (${n.clips} usable clip${n.clips === 1 ? "" : "s"})`).join(", ")}.
                {" "}A new sign is learned once it has at least {MIN_NEW_SIGN_CLIPS} usable clips.</p>
            )}
            {state.dropped && <p className="mt-2 text-sm text-amber-900">Your earlier retrained layer was removed: a clip it learned from was deleted, rejected or lost its training consent, or the site now ships a newer model. Retrain to build a new one.</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="rounded-lg bg-indigo px-3 py-2 text-sm text-white disabled:opacity-60" disabled={busy} onClick={retrain}>
                {busy ? "Training…" : c.eligible ? `Retrain with ${c.eligible} of your clips` : "Retrain on the dataset only"}</button>
              {result && <button className="rounded-lg border border-teal px-3 py-2 text-sm text-teal" onClick={() => use(result)}>Use it in Interpret</button>}
              {!result && state.head && <button className="rounded-lg border border-indigo px-3 py-2 text-sm text-indigo" onClick={() => use(null)}>Revert to run #{state.head.base_run_id}</button>}
            </div>
            {error && <ErrorBanner message={error} />}
            {shown && (
              <div className="mt-4 overflow-x-auto">
                <p className="text-sm font-medium">{result ? "New retrained layer (not in use yet)" : "In use in Interpret on this device"} · trained {when(shown.created_at)} on {shown.n_dataset_clips} dataset clips
                  {" "}+ {shown.user_sample_ids.length} of your clips (weight {shown.user_weight})</p>
                <table className="mt-2 text-sm">
                  <thead><tr className="text-left text-indigo"><th className="pr-6 font-normal">Same {shown.after.n_test} frozen test clips</th><th className="pr-6 font-normal">Accuracy</th><th className="pr-6 font-normal">Macro-F1</th><th className="font-normal">Calibration (ECE)</th></tr></thead>
                  <tbody>
                    {([["Shipped layer (run #" + shown.base_run_id + ")", shown.before], ["Retrained here", shown.after]] as const).map(([label, m]) => (
                      <tr key={label}><td className="pr-6">{label}</td><td className="pr-6">{pc(m.accuracy)}</td><td className="pr-6">{m.macro_f1 == null ? "—" : m.macro_f1.toFixed(3)}</td>
                        <td>{m.ece.toFixed(3)} {m.reliability_passed ? "(passed)" : "(failed: confidence is approximate)"}</td></tr>
                    ))}
                  </tbody>
                </table>
                {shown.new_signs?.length > 0 && <p className="mt-2 text-sm">New signs it can now recognise: <strong>{shown.new_signs.map((n) => n.gloss).join(", ")}</strong>.
                  {" "}They have no held-out test clips, so how well they are recognised is not measured; extra signs can also lower accuracy on the old ones.</p>}
                {shown.skipped_signs?.length > 0 && <p className="mt-1 text-sm text-amber-900">Not learned yet (fewer than {MIN_NEW_SIGN_CLIPS} usable clips): {shown.skipped_signs.map((n) => `${n.gloss} (${n.clips})`).join(", ")}.</p>}
                <p className="mt-2 text-xs text-indigo">The test clips are dataset clips the model never trained on. Your own clips have no held-out test clips, so how much they help your signing is <strong>not measured</strong>.</p>
              </div>
            )}
          </>
        )}
    </section>
  );
}
