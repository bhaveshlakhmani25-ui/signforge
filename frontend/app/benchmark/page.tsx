"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";

// Served by GET /api/benchmark, which reads the benchmark script's data/benchmark_results.json and converts either known layout to this one.
type Curve = { mean: number[]; std: number[] };
type Score = { n_train: number; accuracy: number; macro_f1: number };
type Benchmark = {
  schema_version: number; generated_at: string; is_demo?: boolean;
  dataset: { name: string; n_signs: number | null; split: string; source: string };
  protocol: string; metric: string; seeds: number[]; samples_added: number[]; frozen_test_samples?: number | null;
  curves: Record<string, Curve>;
  before_after?: { before: Score; after: Score; added_samples: number };
  transfer?: { status: string; detail: string };
  notes?: string[];
};

const USE_FIXTURE = process.env.NEXT_PUBLIC_USE_FIXTURES === "1";
const STYLE: Record<string, { color: string; dash?: string; label: string }> = {
  ranker: { color: "#3b3f9e", label: "Ranker (SIGNFORGE)" },
  balanced: { color: "#115e59", dash: "6 3", label: "Balanced (round-robin)" },
  random: { color: "#64748b", dash: "2 3", label: "Random" },
};
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const metricName = (m: string) => ({ macro_f1: "Macro-F1", accuracy: "Accuracy" })[m] ?? m;

async function fetchBenchmark(): Promise<Benchmark | null> {
  try {
    return await api<Benchmark>("/api/benchmark");
  } catch (e) {
    if ((e as { status?: number }).status !== 404) throw e; // a malformed file (422) is shown as an error, never as results
    if (!USE_FIXTURE) return null;
    return (await fetch("/benchmark/benchmark.sample.json", { cache: "no-store" })).json(); // DEMO DATA, carries is_demo
  }
}

function verdict(b: Benchmark) {
  const r = b.curves.ranker, bal = b.curves.balanced;
  if (!r || !bal) return null;
  const i = b.samples_added.length - 1;
  const diff = r.mean[i] - bal.mean[i], noise = Math.max(r.std[i], bal.std[i]);
  const n = b.samples_added[i], seeds = b.seeds.length;
  const head = `After ${n} added samples (mean of ${seeds} seeds), the ranker reached ${pct(r.mean[i])} and balanced collection ${pct(bal.mean[i])}.`;
  if (Math.abs(diff) <= noise) return `${head} The difference is within one standard deviation, so we cannot say the ranker is better.`;
  return `${head} The ranker was ${diff > 0 ? "better" : "worse"} by ${pct(Math.abs(diff))}.`;
}

function Chart({ b }: { b: Benchmark }) {
  const W = 640, H = 300, L = 48, R = 16, T = 12, B = 40;
  const xs = b.samples_added, xmax = Math.max(...xs, 1);
  const x = (v: number) => L + (v / xmax) * (W - L - R);
  const y = (v: number) => T + (1 - Math.min(1, Math.max(0, v))) * (H - T - B);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${metricName(b.metric)} against samples added, for ${Object.keys(b.curves).join(", ")}. The table below gives the exact values.`} className="w-full max-w-2xl">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="#c9c6f2" strokeWidth="1" />
          <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#14163a">{Math.round(t * 100)}%</text></g>
      ))}
      {xs.map((v) => <text key={v} x={x(v)} y={H - 22} textAnchor="middle" fontSize="11" fill="#14163a">{v}</text>)}
      <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" fontSize="12" fill="#14163a">Samples added</text>
      {Object.entries(b.curves).map(([k, c]) => {
        const st = STYLE[k] ?? { color: "#14163a", label: k };
        const band = xs.map((v, i) => `${x(v)},${y(c.mean[i] + c.std[i])}`).concat([...xs].reverse().map((v, i) => `${x(v)},${y(c.mean[xs.length - 1 - i] - c.std[xs.length - 1 - i])}`)).join(" ");
        return (
          <g key={k}>
            <polygon points={band} fill={st.color} opacity="0.12" />
            <polyline points={xs.map((v, i) => `${x(v)},${y(c.mean[i])}`).join(" ")} fill="none" stroke={st.color} strokeWidth="2.5" strokeDasharray={st.dash} />
            {xs.map((v, i) => <circle key={v} cx={x(v)} cy={y(c.mean[i])} r="3" fill={st.color} />)}
          </g>
        );
      })}
    </svg>
  );
}

export default function BenchmarkPage() {
  const [b, setB] = useState<Benchmark | null | undefined>(undefined); // undefined = loading, null = no file yet
  const [error, setError] = useState("");
  const reload = useCallback(() => fetchBenchmark().then((d) => { setB(d); setError(""); }, (e) => setError(e.message)), []);
  useEffect(() => { reload(); }, [reload]);

  const sentence = b && verdict(b);
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Benchmark{b?.is_demo && <DemoBadge className="ml-3 align-middle" />}</h1>
        <p className="mt-1 max-w-[58ch] text-sm">Does choosing what to record next beat recording evenly or at random? Each curve is the mean over several random seeds,
          measured on a test set that is frozen before any samples are added.</p>
      </header>
      {error && <ErrorBanner message={error} onRetry={() => { setError(""); reload(); }} />}
      {b === undefined && !error && <p className="text-sm">Loading the benchmark…</p>}
      {b === null && <p className={`${card} text-sm`}>Not evaluated yet. No benchmark file has been produced, so there is nothing to show. Run the benchmark script to create <code>data/benchmark_results.json</code>.</p>}

      {b && (
        <>
          {b.is_demo && <p className="rounded-xl border border-amber-300 bg-amber-100 p-3 text-sm text-amber-950">This is a fixture with invented numbers, shown to check the layout. Do not quote anything on this page.</p>}
          <section aria-labelledby="curves" className={`${card} space-y-3`}>
            <h2 id="curves" className="font-semibold">{metricName(b.metric)} against samples added</h2>
            {sentence && <p className="max-w-[58ch] text-sm font-medium">{sentence}</p>}
            <Chart b={b} />
            <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
              {Object.keys(b.curves).map((k) => {
                const st = STYLE[k] ?? { color: "#14163a", label: k };
                return <li key={k} className="flex items-center gap-2"><svg width="28" height="8" aria-hidden><line x1="0" x2="28" y1="4" y2="4" stroke={st.color} strokeWidth="2.5" strokeDasharray={st.dash} /></svg>{st.label}</li>;
              })}
              <li>Shaded band: ± 1 standard deviation across seeds</li>
            </ul>
            <div className="relative overflow-x-auto">
              <table className="text-sm">
                <caption className="pb-1 text-left text-xs">{metricName(b.metric)} (mean ± std) by samples added</caption>
                <thead><tr><th scope="col" className="p-1 text-left font-medium">Strategy</th>
                  {b.samples_added.map((n) => <th key={n} scope="col" className="p-1 font-medium tabular-nums">{n}</th>)}</tr></thead>
                <tbody>
                  {Object.entries(b.curves).map(([k, c]) => (
                    <tr key={k} className="border-t border-lavender/60"><th scope="row" className="p-1 text-left font-medium">{(STYLE[k] ?? { label: k }).label}</th>
                      {c.mean.map((m, i) => <td key={i} className="p-1 text-center tabular-nums">{pct(m)} ± {(c.std[i] * 100).toFixed(1)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="max-w-[58ch] text-xs"><strong>Data:</strong> {b.dataset.name} ({b.dataset.n_signs ?? "?"} signs, source: {b.dataset.source.replaceAll("_", " ")}). <strong>Split:</strong> {b.dataset.split}{b.frozen_test_samples != null && `, ${b.frozen_test_samples} frozen test samples`}.
              {" "}<strong>Seeds:</strong> {b.seeds.join(", ")}. <strong>Protocol:</strong> {b.protocol} <strong>Generated:</strong> {b.generated_at ? new Date(b.generated_at).toLocaleString() : "not stated"}.</p>
          </section>

          {b.before_after && (
            <section aria-labelledby="ba" className={`${card} space-y-2`}>
              <h2 id="ba" className="font-semibold">Before and after, same frozen test set</h2>
              <div className="relative overflow-x-auto">
                <table className="text-sm">
                  <thead><tr>{["", "Training samples", "Accuracy", "Macro-F1"].map((h) => <th key={h} scope="col" className="p-1 pr-4 text-left font-medium">{h || <span className="sr-only">Stage</span>}</th>)}</tr></thead>
                  <tbody>
                    {([["Before", b.before_after.before], ["After", b.before_after.after]] as const).map(([l, s]) => (
                      <tr key={l} className="border-t border-lavender/60"><th scope="row" className="p-1 pr-4 text-left font-medium">{l}</th>
                        <td className="p-1 pr-4 tabular-nums">{s.n_train}</td><td className="p-1 pr-4 tabular-nums">{pct(s.accuracy)}</td><td className="p-1 pr-4 tabular-nums">{pct(s.macro_f1)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs">{b.before_after.added_samples} samples were added between the two runs. An improvement here is a result to check, not proof the method works.</p>
            </section>
          )}

          <section aria-labelledby="tr" className={`${card} space-y-1`}>
            <h2 id="tr" className="font-semibold">Transfer learning</h2>
            {b.transfer
              ? <p className="text-sm"><span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs text-amber-950">{b.transfer.status}</span> {b.transfer.detail}</p>
              : <p className="text-sm">Not evaluated yet. This benchmark does not include a transfer comparison.</p>}
          </section>
          {b.notes && b.notes.length > 0 && <ul className="list-disc pl-5 text-sm">{b.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
        </>
      )}
    </div>
  );
}
