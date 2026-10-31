"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import LandmarkReplay from "@/components/LandmarkReplay";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";
import { api, type Consent, type ModelRun, type Project, type Sample, type SignClass } from "@/lib/api";

type Data = { project: Project; classes: SignClass[]; samples: Sample[]; runs: ModelRun[]; showcase: Sample | null };
const pct = (v?: number | null) => (v == null ? "not evaluated" : `${(v * 100).toFixed(1)}%`);

// What exists in the app today. Describes features, not data, so it's static; update it as milestones land.
const LOOP = [
  ["Consent", "built", "/capture"], ["Capture", "built", "/capture"], ["Automated check", "built", "/corpus"],
  ["Human review", "built", "/corpus"], ["Baseline model", "built", "/models"], ["Transfer learning", "blocked", "/models"],
  ["Next-sample queue", "built", "/active-learning"], ["Before/after benchmark", "planned", null], ["Corpus export", "planned", null],
] as const;
const LOOP_STYLE = { built: ["bg-teal/15 text-teal", "built"], blocked: ["bg-amber-100 text-amber-950", "blocked"],
                     planned: ["bg-lavender/50 text-indigo", "planned"] } as const;
const ICON_PATH = { built: "M3.5 8.5l3 3 6-7", blocked: "M8 3.5v5.5M8 12v.5", planned: "M8 3.5a4.5 4.5 0 1 0 0 9a4.5 4.5 0 1 0 0-9" } as const;

function StateIcon({ state }: { state: keyof typeof ICON_PATH }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden className="inline size-3.5 -translate-y-px" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICON_PATH[state]} />
    </svg>
  );
}

async function fetchOverview(): Promise<Data> {
  const [project] = await api<Project[]>("/api/projects");
  if (!project) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
  const [classes, samples, runs] = await Promise.all([
    api<SignClass[]>(`/api/sign-classes?project_id=${project.id}`),
    api<Sample[]>(`/api/samples?project_id=${project.id}&include_demo=true`),
    api<ModelRun[]>(`/api/models/runs?project_id=${project.id}`),
  ]);
  // A real person's landmarks appear here only if a reviewer approved the sample AND the signer opted into public display.
  const approved = samples.filter((x) => x.source !== "demo_fixture" && x.review_status === "approved" && x.qc_passed);
  const consents = (await Promise.all([...new Set(approved.map((x) => x.signer_id))]
    .map((id) => api<Consent[]>(`/api/consents?signer_id=${id}`)))).flat();
  const publicIds = new Set(consents.filter((c) => c.status === "active" && c.allowed_uses.includes("public_release")).map((c) => c.id));
  return { project, classes, samples, runs, showcase: approved.find((x) => publicIds.has(x.consent_id)) ?? null };
}

export default function Overview() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(() => fetchOverview().then((d) => { setData(d); setError(""); }, (e) => setError(String(e.message ?? e))), []);
  useEffect(() => { reload(); }, [reload]);

  const real = data?.samples.filter((s) => s.source !== "demo_fixture") ?? [];
  const count = (f: (s: Sample) => boolean) => real.filter(f).length;
  const kpis = data && [
    ["Signs in this project", data.classes.length],
    ["Approved samples", count((s) => s.review_status === "approved")],
    ["Signers with real samples", new Set(real.map((s) => s.signer_id)).size],
    ["Waiting for human review", count((s) => s.review_status === "pending_review")],
  ];
  const quality = data && [
    ["Failed the automated check", count((s) => !s.qc_passed)],
    ["Needs recapture", count((s) => s.review_status === "needs_recapture")],
    ["Rejected in review", count((s) => s.review_status === "rejected")],
    ["Signs with no real samples yet", data.classes.filter((c) => !real.some((s) => s.sign_class_id === c.id)).length],
  ];
  const demoCount = (data?.samples.length ?? 0) - real.length;
  const latestReal = data?.runs.find((r) => r.pool === "real" && r.status === "succeeded");
  const demoRuns = data?.runs.filter((r) => r.pool === "demo").length ?? 0;


  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={`Could not load the overview. ${error}`} onRetry={() => { setError(""); reload(); }} />}
      <section aria-labelledby="hero" className="overflow-hidden rounded-2xl bg-gradient-to-br from-navy to-indigo text-white">
        <div className="grid items-center gap-6 p-6 md:grid-cols-[1.2fr_1fr] md:p-8">
          <div>
            <h1 id="hero" className="text-3xl font-bold leading-tight md:text-4xl">AI cannot learn what we never collect.</h1>
            <p className="mt-3 text-lavender">Model uncertainty → next sample → better data.</p>
            <p className="mt-2 max-w-xl text-sm text-white/85">
              SIGNFORGE turns a few consented native signs into a model-ready corpus, and uses the model to decide what to record next.
              {data && <> Current project: {data.project.name}, {data.project.target_language}.</>}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link href="/capture" className="rounded-lg bg-teal px-4 py-2 font-medium text-white hover:bg-teal/90 focus-visible:outline-2 focus-visible:outline-white">Record a sample</Link>
              <Link href="/corpus" className="rounded-lg border border-lavender/60 px-4 py-2 text-white hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-white">Open the corpus</Link>
            </div>
          </div>
          <figure className="rounded-xl bg-navy/60 p-3">
            {data ? <LandmarkReplay sampleId={data.showcase?.id} className="aspect-video w-full" />
              : <div className="grid aspect-video place-items-center text-sm text-lavender">{error ? "Replay unavailable" : "Loading…"}</div>}
            {data && (
              <figcaption className="mt-2 text-xs text-lavender">
                {data.showcase
                  ? <>Approved sample #{data.showcase.id}, replayed from stored landmarks: this is all SIGNFORGE keeps, no video. Shown with the signer&apos;s consent.</>
                  : <><DemoBadge className="mr-1" />
                      Synthetic landmarks. Real recordings appear here only once approved and the signer opts into public display.</>}
              </figcaption>
            )}
          </figure>
        </div>
      </section>

      {!data && !error && <p className="text-sm">Loading…</p>}

      {data && kpis && quality && (
        <>
          <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
            <section aria-labelledby="next" className={`${card} border-2 border-indigo/50`}>
              <h2 id="next" className="font-semibold">Next best sample</h2>
              <p className="mt-2 text-sm">Not available yet. The queue will rank signs by model uncertainty, coverage gap and signer-diversity gap, each shown separately.</p>
              <p className="mt-2 text-xs text-indigo">Model uncertainty: not available (no model trained on real data).</p>
            </section>
            <section aria-labelledby="models" className={card}>
              <h2 id="models" className="font-semibold">Latest model</h2>
              {latestReal ? (
                <p className="mt-2 text-sm">Run #{latestReal.id}: accuracy {pct(latestReal.metrics.accuracy)}, macro-F1 {pct(latestReal.metrics.macro_f1)} on {latestReal.metrics.n_test} test samples.
                  <span className="block text-xs text-indigo">{latestReal.split_strategy}</span></p>
              ) : (
                <p className="mt-2 text-sm">Not evaluated on real data yet. The baseline needs approved samples of at least 2 signs, from signers who allowed model training.</p>
              )}
              {demoRuns > 0 && <p className="mt-1 text-xs text-amber-900">{demoRuns === 1 ? "1 DEMO DATA run exists" : `${demoRuns} DEMO DATA runs exist`}; they only show the pipeline works.</p>}
              <Link href="/models" className="mt-2 inline-block text-sm text-indigo underline">Models &amp; evaluation →</Link>
            </section>
          </div>

          <section aria-labelledby="loop" className={card}>
            <h2 id="loop" className="font-semibold">The loop: what works today</h2>
            <ol className="mt-3 flex flex-wrap gap-2 text-sm">
              {LOOP.map(([label, state, href]) => {
                const [cls, word] = LOOP_STYLE[state];
                const body = <><StateIcon state={state} /> {label}<span className="sr-only"> ({word})</span></>;
                return <li key={label}>{href
                  ? <Link href={href} className={`inline-block rounded-lg px-3 py-1.5 hover:ring-2 hover:ring-indigo/30 ${cls}`}>{body}</Link>
                  : <span className={`inline-block rounded-lg px-3 py-1.5 ${cls}`}>{body}</span>}</li>;
              })}
            </ol>
            <p className="mt-2 flex flex-wrap gap-x-3 text-xs">
              <span><StateIcon state="built" /> built</span>
              <span><StateIcon state="blocked" /> blocked (pretrained checkpoint not verified yet)</span>
              <span><StateIcon state="planned" /> planned</span>
            </p>
          </section>

          <section aria-labelledby="kpis">
            <h2 id="kpis" className="sr-only">Corpus summary</h2>
            <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {kpis.map(([label, value]) => (
                <div key={label} className={card}>
                  <dt className="text-xs text-indigo">{label}</dt>
                  <dd className="mt-1 text-3xl font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs">Counts cover real samples only. {demoCount > 0 && <>{demoCount} DEMO DATA samples are excluded.</>}</p>
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <section aria-labelledby="quality" className={card}>
              <h2 id="quality" className="font-semibold">Quality and review</h2>
              <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
                {quality.map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-2 rounded-lg bg-background px-3 py-2">
                    <dt>{label}</dt><dd className={`font-semibold ${value ? "text-amber-800" : ""}`}>{value}</dd>
                  </div>
                ))}
              </dl>
            </section>
            {real.length === 0 && (
              <section aria-labelledby="start" className={card}>
                <h2 id="start" className="font-semibold">Getting started</h2>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
                  <li>Confirm the {data.classes.length} placeholder signs with a native {data.project.target_language} signer.</li>
                  <li>On Capture, record consent and a first sample. Tick the model-training box if the signer agrees, or the sample can&apos;t be used to train.</li>
                  <li>Review it in Corpus &amp; review. Only approved samples are used to train.</li>
                </ol>
              </section>
            )}
          </div>
        </>
      )}
    </div>
  );
}
