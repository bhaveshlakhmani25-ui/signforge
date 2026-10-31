"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type Project, type Queue, type SignClass } from "@/lib/api";
import { fixtureQueue } from "@/lib/fixtures";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";

async function fetchQueue() {
  const [project] = await api<Project[]>("/api/projects");
  if (!project) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
  try {
    return { project, queue: await api<Queue>(`/api/queue?project_id=${project.id}`), fixture: false };
  } catch (e) {
    if ((e as { status?: number }).status !== 404) throw e; // only "endpoint not built yet" falls back; real failures stay visible
    const classes = await api<SignClass[]>(`/api/sign-classes?project_id=${project.id}`);
    return { project, queue: fixtureQueue(classes), fixture: true };
  }
}

const num = (v: number) => v.toFixed(2);

function Part({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="min-w-24">
      <dt className="text-xs text-indigo">{label}</dt>
      {value == null
        ? <dd className="text-sm text-amber-900">Not available yet</dd>
        : <dd className="text-sm font-medium tabular-nums">{num(value)}
            <span aria-hidden className="mt-1 block h-1.5 rounded-full bg-lavender/50"><span className="block h-full rounded-full bg-indigo" style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }} /></span></dd>}
    </div>
  );
}

export default function ActiveLearningPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchQueue>> | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(() => fetchQueue().then((d) => { setData(d); setError(""); }, (e) => setError(e.message)), []);
  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">What should we record next?</h1>
        <p className="mt-1 max-w-[58ch] text-sm">Signs are ranked by where the corpus is thinnest: few samples, few signers, and (once a model exists) where the model is unsure.
          Recording the top sign from a new signer is the most useful next step.</p>
      </header>
      {error && <ErrorBanner message={`Could not load the queue. ${error}`} onRetry={() => { setError(""); reload(); }} />}
      {!data && !error && <p className="text-sm">Loading the queue…</p>}

      {data?.fixture && (
        <p className="rounded-xl border border-amber-300 bg-amber-100 p-3 text-sm text-amber-950">
          <DemoBadge className="mr-2" />The backend does not have a next-sample queue yet, so these rows are a fixture to show the layout. The numbers are invented and say nothing about this corpus.
        </p>
      )}

      {data && (
        <section aria-labelledby="queue" className="space-y-3">
          <h2 id="queue" className="font-semibold">Ranked signs</h2>
          <p className="max-w-[58ch] text-xs">Priority = {data.queue.formula}. {!data.queue.uncertainty_available && "Model uncertainty is not available yet because no model has been evaluated for this ranking."}</p>
          {!data.queue.items.length && <p className={`${card} text-sm`}>Nothing to recommend. The project has no signs yet, or every sign has reached its target.</p>}
          <ol className="space-y-3">
            {data.queue.items.map((q, i) => (
              <li key={q.sign_id} className={`${card} space-y-2 ${data.fixture ? "border-amber-300" : ""}`}>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm text-indigo">#{i + 1}</span>
                  <h3 className="text-lg font-semibold">{q.gloss}</h3>
                  {data.fixture && <DemoBadge />}
                  <span className="text-sm">Priority <strong className="tabular-nums">{num(q.priority)}</strong></span>
                  <Link href={`/capture?sign=${q.sign_id}`} className="ml-auto rounded-lg bg-teal px-3 py-2 text-sm text-white hover:opacity-90">
                    Record this sign<span className="sr-only">: {q.gloss}</span>
                  </Link>
                </div>
                <dl className="flex flex-wrap gap-x-6 gap-y-2">
                  <Part label="Coverage gap" value={q.coverage_gap} />
                  <Part label="Signer gap" value={q.signer_gap} />
                  <Part label="Model uncertainty" value={q.uncertainty} />
                </dl>
                <p className="max-w-[58ch] text-sm">{q.reason}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
