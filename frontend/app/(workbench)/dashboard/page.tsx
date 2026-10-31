"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { card, ErrorBanner } from "@/components/ui";
import { api, currentProject, type ActiveLearningQueueItem, type ActiveLearningQueueResponse, type ModelRun, type Project, type Sample, type SignClass } from "@/lib/api";

type Data = { project: Project; classes: SignClass[]; samples: Sample[]; runs: ModelRun[]; queue: ActiveLearningQueueResponse; reference: ModelRun | null };

async function fetchDashboard(): Promise<Data> {
  const project = await currentProject();
  if (!project) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
  const [classes, samples, runs, queue, projects] = await Promise.all([
    api<SignClass[]>(`/api/sign-classes?project_id=${project.id}`),
    api<Sample[]>(`/api/samples?project_id=${project.id}`), // real only: DEMO DATA never counts here
    api<ModelRun[]>(`/api/models/runs?project_id=${project.id}`),
    api<ActiveLearningQueueResponse>(`/api/active-learning/queue?project_id=${project.id}`),
    api<Project[]>("/api/projects"),
  ]);
  // The model check scores clips with the latest calibrated run of ANY project (in practice the INCLUDE one).
  const all = (await Promise.all(projects.map((p) => p.id === project.id ? runs : api<ModelRun[]>(`/api/models/runs?project_id=${p.id}`)))).flat();
  const reference = all.filter((r) => r.status === "succeeded" && r.metrics.calibration).sort((a, b) => b.id - a.id)[0] ?? null;
  return { project, classes, samples, runs, queue, reference };
}

function coverageState(q: ActiveLearningQueueItem): [string, string] {
  if (q.approved_sample_count === 0) return ["No approved clips", "bg-amber-100 text-amber-950"];
  if (q.coverage_gap > 0) return ["Needs more clips", "bg-amber-100 text-amber-950"];
  if (q.signer_gap > 0) return ["Needs more signers", "bg-amber-100 text-amber-950"];
  return ["At target", "bg-teal/15 text-teal"];
}

function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const share = Math.min(1, value / Math.max(max, 1));
  return (
    <div className="min-w-0">
      <p className="flex justify-between gap-2 text-sm"><span className="text-indigo">{label}</span><span className="f-mono tabular-nums">{value}/{max}</span></p>
      <div className="mt-1.5 h-1 bg-lavender/60" role="presentation">
        <div className="h-full bg-navy" style={{ width: `${share * 100}%` }} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => fetchDashboard().then((d) => { setData(d); setError(""); }, (e) => setError(String(e.message ?? e))), []);
  useEffect(() => { reload(); }, [reload]);

  const real = data?.samples ?? [];
  const count = (f: (s: Sample) => boolean) => real.filter(f).length;
  const pending = (s: Sample) => s.review_status === "pending_review";
  const stats = data && [
    ["Signs", data.classes.length],
    ["Clips recorded", real.length],
    ["Approved by a person", count((s) => s.review_status === "approved")],
    ["Waiting for review", count((s) => pending(s) && s.triage_status !== "auto_rejected")],
    ["Signers", new Set(real.map((s) => s.signer_id)).size],
  ] as const;
  const attention = data && [
    ["Failed the automated check", count((s) => !s.qc_passed), "Record these again."],
    ["Model check: needs a person", count((s) => pending(s) && s.triage_status === "needs_review"), "The model disagreed, was unsure, or has not learned the sign."],
    ["Sent back for recapture", count((s) => s.review_status === "needs_recapture"), "A reviewer asked for a new recording."],
    ["Rejected in review", count((s) => s.review_status === "rejected"), "Excluded from training."],
  ] as const;
  const latest = data?.runs.find((r) => r.pool === "real" && r.status === "succeeded");
  const ref = data?.reference, cal = ref?.metrics.calibration;
  const top = data?.queue.queue[0];
  const tied = top ? data!.queue.queue.filter((q) => q.priority === top.priority).length : 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[clamp(2.2rem,4vw,3rem)] font-semibold leading-none">Dashboard</h1>
          <p className="mt-2 text-base text-indigo">{data ? `${data.project.name} · ${data.project.target_language}` : "Loading the project…"}</p>
        </div>
        <Link href="/capture" className="rounded-full bg-navy px-6 py-3 font-semibold text-white transition-colors hover:bg-safelight hover:text-navy">Record a sign</Link>
      </header>
      {error && <ErrorBanner message={`Could not load the dashboard. ${error}`} onRetry={() => { setError(""); reload(); }} />}

      {data && (
        <>
          <section aria-labelledby="next" className="border border-lavender border-t-4 border-t-navy bg-white p-5 md:p-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="next" className="display text-[clamp(1.8rem,3vw,2.4rem)] font-semibold leading-none">What to record next</h2>
              <Link href="/active-learning" className="text-base text-indigo underline underline-offset-4 hover:text-navy">Full queue and formula</Link>
            </div>
            {data.queue.queue.length === 0
              ? <p className="mt-4 text-indigo">Nothing to recommend. Add signs to the project, or every sign has reached its target.</p>
              : (
                <ol className="mt-6 border-t border-lavender">
                  {data.queue.queue.slice(0, 3).map((q, i) => (
                    <li key={q.sign_class_id} className="grid gap-4 border-b border-lavender py-5 md:grid-cols-[2.5rem_1fr_15rem_auto] md:items-center">
                      <span className="f-display text-2xl italic text-amber-800">{i + 1}</span>
                      <div className="min-w-0">
                        <p className="display text-[1.7rem] font-semibold leading-none">{q.gloss}{q.suggested_signer === "new_signer" && <span className="f-body ml-3 text-base font-normal text-indigo">from a new signer</span>}</p>
                        <p className="mt-2 max-w-[60ch] text-base text-indigo">{q.reason.charAt(0).toUpperCase() + q.reason.slice(1)}</p>
                      </div>
                      <div className="grid gap-2">
                        <Meter label="Approved clips" value={q.approved_sample_count} max={q.target_samples} />
                        <Meter label="Signers" value={q.distinct_signer_count} max={q.target_signers} />
                      </div>
                      <Link href={`/capture?sign=${q.sign_class_id}`} className="justify-self-start rounded-full bg-navy px-5 py-2.5 font-semibold text-white transition-colors hover:bg-safelight hover:text-navy">
                        Record this sign<span className="sr-only">: {q.gloss}</span>
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            <p className="mt-4 text-sm text-indigo">
              {tied > 2 && `The top ${tied} signs are tied, so any of them is an equally good next take. `}
              Ranked by coverage gap and signer gap{data.queue.queue.some((q) => q.uncertainty != null) ? ", plus model uncertainty" : "; model uncertainty joins once a model is trained on this project"}.
            </p>
          </section>

          {stats && (
            <section aria-labelledby="stats">
              <h2 id="stats" className="sr-only">Where the corpus stands</h2>
              <dl className="grid grid-cols-2 divide-lavender border border-lavender bg-white sm:grid-cols-5 sm:divide-x">
                {stats.map(([label, value]) => (
                  <div key={label} className="px-5 py-4">
                    <dt className="text-sm text-indigo">{label}</dt>
                    <dd className="f-display mt-1 text-[2.2rem] font-semibold leading-none tabular-nums">{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-sm text-indigo">Recorded and external clips only; DEMO DATA is never counted.</p>
            </section>
          )}

          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            <section aria-labelledby="coverage" className={card}>
              <h2 id="coverage" className="display text-2xl font-semibold">Sign coverage</h2>
              <p className="mt-1 text-sm text-indigo">Approved clips and signers against the target. This is coverage only: the per-sign &ldquo;is it enough&rdquo; verdict is not built yet.</p>
              <ul className="mt-3 divide-y divide-lavender/70">
                {[...data.queue.queue].sort((a, b) => a.gloss.localeCompare(b.gloss)).map((q) => {
                  const [label, cls] = coverageState(q);
                  return (
                    <li key={q.sign_class_id} className="grid grid-cols-[1fr_auto] items-center gap-3 py-2.5 sm:grid-cols-[9rem_1fr_auto]">
                      <span className="font-semibold">{q.gloss}</span>
                      <span className="hidden text-sm tabular-nums text-indigo sm:block">{q.approved_sample_count}/{q.target_samples} clips · {q.distinct_signer_count}/{q.target_signers} signers</span>
                      <span className={`px-2 py-0.5 text-sm ${cls}`}>{label}</span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <div className="space-y-6">
              {attention && (
                <section aria-labelledby="attention" className={card}>
                  <h2 id="attention" className="display text-2xl font-semibold">Needs attention</h2>
                  <ul className="mt-2 space-y-2">
                    {attention.map(([label, n, hint]) => (
                      <li key={label}>
                        <Link href="/corpus" className="flex items-start justify-between gap-3 px-2 py-2 hover:bg-background">
                          <span><span className="font-semibold">{label}</span><span className="block text-sm text-indigo">{hint}</span></span>
                          <span className={`f-display text-2xl font-semibold tabular-nums ${n ? "text-amber-800" : "text-indigo"}`}>{n}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section aria-labelledby="model" className={card}>
                <h2 id="model" className="display text-2xl font-semibold">Models</h2>
                <dl className="mt-2 space-y-3">
                  <div>
                    <dt className="text-sm text-indigo">Model check (scores new clips)</dt>
                    <dd>{ref
                      ? <>Run #{ref.id}: {((ref.metrics.accuracy ?? 0) * 100).toFixed(0)}% on {ref.metrics.n_test} held-out clips.{" "}
                          {cal && !cal.reliability_passed && <span className="text-amber-900">Calibration failed, so automatic acceptance is off.</span>}</>
                      : "Not available yet: no calibrated model has been trained."}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-indigo">This project&apos;s own data</dt>
                    <dd>{latest
                      ? <>Run #{latest.id}: {((latest.metrics.accuracy ?? 0) * 100).toFixed(0)}% on {latest.metrics.n_test} test clips.</>
                      : "Not evaluated yet. Training needs approved clips of at least 2 signs."}</dd>
                  </div>
                  <div><dt className="text-sm text-indigo">Transfer learning</dt><dd>Blocked: no compatible checkpoint verified.</dd></div>
                </dl>
                <Link href="/models" className="mt-3 inline-block text-sm text-indigo underline">Models &amp; evaluation</Link>
              </section>
            </div>
          </div>
        </>
      )}
      {!data && !error && <p className="text-sm">Loading…</p>}
    </div>
  );
}
