"use client";

import { useCallback, useEffect, useState } from "react";
import { api, currentProject, type ModelRun, type SignClass, when } from "@/lib/api";
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

export default function ModelsPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchModels>> | null>(null);
  const [error, setError] = useState("");
  const [trainError, setTrainError] = useState("");
  const [training, setTraining] = useState<"" | "real" | "demo">("");

  const reload = useCallback(() => fetchModels().then((d) => { setData(d); setError(""); }, (e) => setError(e.message)), []);
  useEffect(() => { reload(); }, [reload]);

  async function train(pool: "real" | "demo") {
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

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="baseline" className={card}>
          <h2 id="baseline" className="font-semibold">Baseline (from scratch)</h2>
          <p className="mt-1 text-sm">Small GRU over 27 body/hand points, randomly initialised: <strong>not pretrained</strong>. Trains on real samples that passed the automated check, were approved in human review, and come from signers who allowed model training. The first run fixes the test set; later runs reuse it, so results stay comparable.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="rounded-lg bg-indigo px-3 py-2 text-sm text-white disabled:opacity-60" disabled={!data || !!training} onClick={() => train("real")}>
              {training === "real" ? "Training…" : "Train on approved real samples"}
            </button>
            <button className="rounded-lg border border-amber-600 px-3 py-2 text-sm text-amber-900 disabled:opacity-60" disabled={!data || !!training} onClick={() => train("demo")}>
              {training === "demo" ? "Training…" : "Train on DEMO DATA"}
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
                {r.metrics.confusion_matrix && r.metrics.labels && (
                  <details>
                    <summary className="cursor-pointer text-sm text-indigo">Confusion matrix and per-class results</summary>
                    <div className="relative mt-2 overflow-x-auto">
                      <table className="text-xs">
                        <caption className="pb-1 text-left">Rows: true sign · columns: predicted sign</caption>
                        <thead><tr><th scope="col" className="p-1"><span className="sr-only">True sign</span></th>
                          {r.metrics.labels.map((l) => <th key={l} scope="col" className="p-1 font-medium">{gloss(l)}</th>)}
                          <th scope="col" className="p-1 font-medium">Support</th><th scope="col" className="p-1 font-medium">F1</th></tr></thead>
                        <tbody>
                          {r.metrics.confusion_matrix.map((row, i) => {
                            const l = r.metrics.labels![i];
                            const pc = r.metrics.per_class?.[l];
                            return (
                              <tr key={l}>
                                <th scope="row" className="p-1 text-left font-medium">{gloss(l)}</th>
                                {row.map((v, j) => <td key={j} className={`p-1 text-center ${v ? (i === j ? "bg-teal/20" : "bg-red-100") : ""}`}>{v}</td>)}
                                <td className="p-1 text-center">{pc?.support ?? 0}</td>
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
