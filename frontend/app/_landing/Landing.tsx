"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import Chronograph from "@/components/Chronograph";
import { api, type ActiveLearningQueueResponse, type ModelRun, type Project, type Sample, type SignClass } from "@/lib/api";

// Every reading on this page comes from the backend at load time. Missing values say why; nothing is filled in.
type Readings = {
  recorded: number; imported: number; passed: number;
  run: ModelRun | null;
  next: { gloss: string; reason: string; ties: number; project: string } | null;
  teamMatch: { median: number; n: number; gloss: string } | null;
  plateId: number | null; plateFrames: number | null;
};

async function loadReadings(): Promise<Readings> {
  const projects = await api<Project[]>("/api/projects");
  const per = await Promise.all(projects.map(async (p) => ({
    p,
    samples: await api<Sample[]>(`/api/samples?project_id=${p.id}`), // DEMO DATA is excluded by default
    runs: await api<ModelRun[]>(`/api/models/runs?project_id=${p.id}`),
    classes: await api<SignClass[]>(`/api/sign-classes?project_id=${p.id}`),
  })));
  const all = per.flatMap((x) => x.samples);
  const run = per.flatMap((x) => x.runs).filter((r) => r.status === "succeeded" && r.metrics.calibration).sort((a, b) => b.id - a.id)[0] ?? null;
  const team = per.find((x) => x.samples.some((s) => s.source === "captured"));
  const queue = team ? await api<ActiveLearningQueueResponse>(`/api/active-learning/queue?project_id=${team.p.id}`) : null;
  const top = queue?.queue[0];

  const byGloss = new Map<string, number[]>();
  for (const s of team?.samples ?? []) {
    if (s.match_confidence == null) continue;
    const g = team!.classes.find((c) => c.id === s.sign_class_id)?.gloss ?? "";
    byGloss.set(g, [...(byGloss.get(g) ?? []), s.match_confidence]);
  }
  const [gloss, vals] = [...byGloss.entries()].sort((a, b) => b[1].length - a[1].length)[0] ?? ["", []];
  const sorted = [...vals].sort((a, b) => a - b);

  const ext = per.find((x) => x.samples.some((s) => s.source === "external_dataset"));
  const hello = ext?.classes.find((c) => c.gloss === "HELLO");
  const plate = ext?.samples.find((s) => s.sign_class_id === hello?.id && s.qc_passed);
  return {
    recorded: all.filter((s) => s.source === "captured").length,
    imported: all.filter((s) => s.source === "external_dataset").length,
    passed: all.filter((s) => s.qc_passed).length,
    run,
    next: top ? { gloss: top.gloss, reason: top.reason, ties: queue!.queue.filter((q) => q.priority === top.priority).length - 1, project: team!.p.name } : null,
    teamMatch: sorted.length ? { median: sorted[Math.floor(sorted.length / 2)], n: sorted.length, gloss } : null,
    plateId: plate?.id ?? null, plateFrames: plate?.frame_count ?? null,
  };
}

const pct = (v: number) => `${Math.round(v * 100)}%`;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);


const NAV = [["#readings", "Readings"], ["#story", "Why"], ["#method", "How it works"], ["#evidence", "Evidence"]] as const;

const LOOP = [
  ["Consent", "A pseudonymous signer code and a purpose-specific consent record, before the camera turns on."],
  ["Landmarks", "MediaPipe runs in the browser. Body and hand landmarks are kept; the video never leaves the device."],
  ["Automated check", "Missing hands, out-of-frame points, mirrored or too-short clips. Every failure says why."],
  ["Model check", "A model trained on INCLUDE scores how closely the clip matches the dataset. It never calls a sign correct."],
  ["Human review", "People approve, reject or ask for a recapture. Linguistic validation stays with native and Deaf signers."],
  ["Train and measure", "A small model retrains on approved clips and is measured on a test set frozen before collection."],
  ["Record next", "Coverage gaps and missing signers rank the next sign. Model uncertainty joins once a model is trained on the project."],
] as const;

export default function Landing() {
  const [r, setR] = useState<Readings | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => { loadReadings().then(setR, () => setOffline(true)); }, []);

  const run = r?.run, cal = run?.metrics.calibration;
  const pending = offline ? "Backend offline" : "Reading…";
  const missing = offline ? "The backend is offline, so this reading is missing." : "Appears once a calibrated model has been trained.";

  return (
    <div className="landing f-body min-h-screen bg-[#0c0c0b] text-[#efeee9] selection:bg-[#f2a33a] selection:text-[#0c0c0b]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:bg-[#efeee9] focus:px-3 focus:py-2 focus:text-[#0c0c0b]">Skip to content</a>

      <header className="sticky top-0 z-40 border-b border-[#efeee9]/15 bg-[#0c0c0b]/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-5 py-3.5 md:px-10">
          <Link href="/" className="f-display text-lg font-bold uppercase tracking-[0.22em]">Signforge</Link>
          <nav aria-label="Sections" className="ml-auto hidden gap-8 text-base text-[#efeee9]/75 md:flex">
            {NAV.map(([h, l]) => <a key={h} href={h} className="hover:text-[#efeee9]">{l}</a>)}
          </nav>
          <Link href="/dashboard" className="ml-auto rounded-full border border-[#efeee9]/70 px-5 py-2 text-sm font-semibold transition-colors hover:border-[#f2a33a] hover:bg-[#f2a33a] hover:text-[#0c0c0b] md:ml-0">
            <span className="sm:hidden">Dashboard</span><span className="hidden sm:inline">Open the dashboard</span>
          </Link>
        </div>
      </header>

      <main id="main">
        {/* The opening plate: a real sign as a chronophotograph. */}
        <section aria-labelledby="hero" className="relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(239,238,233,0.05)_1px,transparent_1px)] bg-[length:64px_100%]" />
          <div className="relative mx-auto max-w-[1400px] px-5 pt-10 md:px-10 md:pt-12">
            <h1 id="hero" className="f-display max-w-[13ch] text-[clamp(3.1rem,7.4vw,6.6rem)] font-semibold leading-[0.92] tracking-[-0.02em] [text-wrap:balance]">
              Know which sign to record <em className="font-medium">next.</em>
            </h1>
          </div>
          <div className="relative mt-6 h-[clamp(220px,27vw,360px)] border-y border-[#efeee9]/12">
            <Chronograph sampleId={offline ? -1 : r?.plateId ?? null}
                         label="A signer's HELLO drawn as a long exposure: faint stick figures across the plate, with a bright figure replaying the sign." />
          </div>
          <div className="relative mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-6 px-5 py-8 md:px-10">
            <p className="max-w-[40ch] text-[clamp(1.2rem,1.7vw,1.45rem)] leading-snug">
              SIGNFORGE checks every sign clip, measures what a model learns from it, and points to the next sign to record.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-[#efeee9] px-7 py-3.5 text-lg font-semibold text-[#0c0c0b] transition-colors hover:bg-[#f2a33a]">Open the dashboard</Link>
              <a href="#method" className="rounded-full border border-[#efeee9]/40 px-7 py-3.5 text-lg font-semibold transition-colors hover:border-[#efeee9]">How it works</a>
            </div>
          </div>
        </section>

        {/* Live readings, on silver-gelatin print stock. */}
        <section id="readings" aria-labelledby="readings-h" className="scroll-mt-16 border-t border-[#efeee9]/15">
          <div className="mx-auto max-w-[1200px] px-5 py-20 md:px-10 md:py-24">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <h2 id="readings-h" className="f-display text-[clamp(2.2rem,4.4vw,3.8rem)] font-semibold leading-none">The readings</h2>
              <p className="f-mono text-sm uppercase tracking-[0.1em] text-[#efeee9]/70">{offline ? "Backend offline" : r ? "Live from the app" : "Reading…"}</p>
            </div>
            <ol className="mt-10 border-t border-[#efeee9]/50">
              <Reading q="Is this clip good?" built="Consent, in-browser landmarks and an automated check that explains every failure."
                       value={r ? `${r.recorded} recorded` : pending}
                       note={r ? `plus ${r.imported} imported from INCLUDE` : undefined} state="Running" />
              <Reading q="Does it match the dataset?" built="A model trained on INCLUDE scores each new clip. It is calibrated, but not yet reliable."
                       value={run?.metrics.accuracy != null ? pct(run.metrics.accuracy) : r ? "Not evaluated" : pending}
                       note={run ? `on ${run.metrics.n_test} unseen clips` : undefined}
                       state={offline ? "Backend offline" : cal ? (cal.reliability_passed ? "Calibrated" : "Calibration failed") : "Not evaluated"}
                       warn={!!cal && !cal.reliability_passed} />
              <Reading q="Is this sign enough?" built="A per-sign verdict from coverage, signers and the learning curve."
                       value="No verdict" note="needs the simulation first" state="Not built yet" warn />
              <Reading q="What should we record next?" built="A ranked queue from coverage gaps and missing signers."
                       value={r?.next?.gloss ?? (r ? "Nothing queued" : pending)}
                       note={r?.next?.ties ? `tied with ${r.next.ties} other signs` : undefined} state="Running" />
            </ol>
          </div>
        </section>

        {/* Why. */}
        <section id="story" aria-labelledby="story-h" className="scroll-mt-16">
          <div className="mx-auto grid max-w-[1200px] gap-12 px-5 py-24 md:px-10 lg:grid-cols-[5fr_7fr]">
            <h2 id="story-h" className="f-display text-[clamp(2.4rem,4.4vw,3.8rem)] font-semibold leading-[1.02] [text-wrap:balance]">
              Sign-language AI is held back by data, not by algorithms.
            </h2>
            <div className="max-w-[56ch] space-y-6 text-[1.2rem] leading-relaxed text-[#efeee9]/90">
              <p>More than 300 sign languages are used by over 70 million Deaf people.<Ref n={1} /> Most have almost no data a model can learn from,
                and what exists is scattered across datasets that do not line up.<Ref n={2} /></p>
              <p>Indian Sign Language has research datasets, but the same gaps keep returning: regional variation, few signers,
                and data collected without a clear record of consent.<Ref n={3} /></p>
              <p className="text-[#efeee9]">So we did not build another translator. We built the instrument that comes before one.</p>
            </div>
          </div>
        </section>

        <section id="method" aria-labelledby="method-h" className="scroll-mt-16 border-t border-[#efeee9]/15">
          <div className="mx-auto max-w-[1200px] px-5 py-24 md:px-10">
            <h2 id="method-h" className="f-display text-[clamp(2.4rem,4.4vw,3.8rem)] font-semibold leading-none">How it works</h2>
            <p className="mt-4 max-w-[50ch] text-[1.2rem] text-[#efeee9]/75">One loop. Each turn adds clips, re-measures the model and points at the next gap.</p>
            <Method />
          </div>
        </section>

        {/* Findings, failures included. */}
        <section id="evidence" aria-labelledby="evidence-h" className="scroll-mt-16 border-t border-[#efeee9]/15">
          <div className="mx-auto max-w-[1200px] px-5 py-24 md:px-10">
            <h2 id="evidence-h" className="f-display max-w-[16ch] text-[clamp(2.4rem,4.4vw,3.8rem)] font-semibold leading-[1.02] [text-wrap:balance]">
              What we measured, including what did not work.
            </h2>
            <dl className="mt-12 border-t border-[#efeee9]/50">
              <Finding title="Accuracy on unseen recording sessions" value={run?.metrics.accuracy != null ? pct(run.metrics.accuracy) : offline ? "Offline" : "—"}
                       body={run ? `${run.metrics.n_test} INCLUDE clips the model never saw. INCLUDE has no signer IDs, so this is not a signer-independent result.` : missing}
                       source={run ? `Live · run #${run.id}` : "Live"} />
              <Finding title="Calibration" value={cal ? `${cal.test_before.ece.toFixed(2)} → ${cal.test_after.ece.toFixed(2)}` : offline ? "Offline" : "—"}
                       body={cal ? (cal.reliability_passed ? `Below the ${cal.max_ece.toFixed(2)} limit.` : `Improved, but not below the ${cal.max_ece.toFixed(2)} limit. So automatic acceptance stays off and every clip goes to a person.`) : missing}
                       source={cal ? `Live · run #${run!.id}` : "Live"} warn={!!cal && !cal.reliability_passed} />
              <Finding title={`Our own ${r?.teamMatch?.gloss || "team"} clips`} value={r?.teamMatch ? pct(r.teamMatch.median) : offline ? "Offline" : "—"}
                       body={r?.teamMatch ? `Median match against the dataset across ${r.teamMatch.n} clips. INCLUDE signers keep both hands in view; ours mostly show one. Finding gaps like this is the point.` : offline ? "The backend is offline, so this reading is missing." : "Appears once team clips have been scored."}
                       source="Live" warn={!!r?.teamMatch && r.teamMatch.median < 0.5} />
              <Finding title="Transfer learning" value="Blocked"
                       body="No pretrained checkpoint has been verified as compatible with our landmarks, so we claim no transfer result."
                       source="docs/MODEL_CARD.md" warn />
            </dl>
          </div>
        </section>

        <section id="record-next" aria-labelledby="close" className="scroll-mt-16">
          <div className="mx-auto max-w-[1200px] px-5 py-24 md:px-10">
            <h2 id="close" className="f-display max-w-[17ch] text-[clamp(2.6rem,5.6vw,5rem)] font-semibold leading-[0.98] [text-wrap:balance]">
              {r?.next ? <>Right now, the queue says: record <em className="font-medium text-[#f2a33a]">{r.next.gloss}</em>.</> : <>See the queue for yourself.</>}
            </h2>
            {r?.next && (
              <p className="mt-6 max-w-[52ch] text-[1.2rem] leading-relaxed text-[#efeee9]/80">
                {r.next.ties > 0 ? `It is tied with ${r.next.ties} other signs in ${r.next.project}: none has an approved clip yet, so any of them is an equally good next take.` : cap(r.next.reason)}
              </p>
            )}
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-[#efeee9] px-7 py-3.5 text-lg font-semibold text-[#0c0c0b] transition-colors hover:bg-[#f2a33a]">Open the dashboard</Link>
              <Link href="/capture" className="rounded-full border border-[#efeee9]/40 px-7 py-3.5 text-lg font-semibold transition-colors hover:border-[#efeee9]">Record a sign</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#efeee9]/15">
        <div className="mx-auto grid max-w-[1200px] gap-12 px-5 pb-10 pt-16 md:grid-cols-[1.4fr_1fr_1.4fr] md:px-10">
          <div>
            <p className="f-display text-2xl font-bold uppercase tracking-[0.2em]">Signforge</p>
            <p className="mt-3 max-w-[30ch] text-[1.05rem] leading-relaxed text-[#efeee9]/70">
              A corpus builder for low-resource sign languages: from a few native signs to a model-ready corpus.
            </p>
            <Link href="/dashboard" className="mt-6 inline-block rounded-full bg-[#efeee9] px-6 py-3 font-semibold text-[#0c0c0b] transition-colors hover:bg-[#f2a33a]">Open the dashboard</Link>
          </div>
          <nav aria-label="Footer">
            <p className="f-mono text-xs uppercase tracking-[0.14em] text-[#efeee9]/50">Explore</p>
            <ul className="mt-4 space-y-2.5 text-[1.05rem]">
              {[["#readings", "Readings"], ["#method", "How it works"], ["#evidence", "Evidence"], ["/capture", "Record a sign"], ["/corpus", "Corpus & review"]].map(([h, l]) => (
                <li key={h}><a href={h} className="text-[#efeee9]/80 hover:text-[#f2a33a]">{l}</a></li>
              ))}
            </ul>
          </nav>
          <div>
            <p className="f-mono text-xs uppercase tracking-[0.14em] text-[#efeee9]/50">Sources</p>
            <ol className="mt-4 space-y-2.5 text-[0.95rem] leading-snug text-[#efeee9]/65">
              <li id="ref-1">1. United Nations, International Day of Sign Languages</li>
              <li id="ref-2">2. Ni et al., Sign-Language Datasets at Scale, ACL 2026</li>
              <li id="ref-3">3. Wadhera, Mahmud &amp; Dhaneshwar, CVPR Workshops 2026</li>
              <li>INCLUDE dataset: Sridhar et al., ACM MM 2020, CC BY 4.0</li>
            </ol>
          </div>
        </div>
        <div className="mx-auto flex max-w-[1200px] flex-wrap justify-between gap-3 border-t border-[#efeee9]/10 px-5 py-6 text-sm text-[#efeee9]/50 md:px-10">
          <p>Built by Team Claude&apos;s Clan.</p>
          <p>Landmarks only: no sign video is stored or shown.</p>
        </div>
      </footer>
    </div>
  );
}

function Reading({ q, built, value, note, state, warn }: { q: string; built: string; value: string; note?: string; state: string; warn?: boolean }) {
  return (
    <li className="grid gap-4 border-b border-[#efeee9]/15 py-8 md:grid-cols-[1.3fr_1fr] md:gap-12">
      <div>
        <h3 className="f-display text-[clamp(1.7rem,2.4vw,2.1rem)] font-semibold leading-tight">{q}</h3>
        <p className="mt-2 max-w-[44ch] text-[1.12rem] leading-relaxed text-[#efeee9]/80">{built}</p>
      </div>
      <div className="md:text-right">
        <p className="f-display text-[clamp(2.2rem,3.6vw,3.2rem)] font-semibold leading-none tabular-nums">{value}</p>
        {note && <p className="mt-2 text-[1.05rem] text-[#efeee9]/70">{note}</p>}
        <p className={`f-mono mt-3 text-sm uppercase tracking-[0.08em] ${warn ? "text-[#f2a33a]" : "text-[#efeee9]/75"}`}>
          <span aria-hidden className={`mr-2 inline-block size-2 rounded-full align-middle ${warn ? "bg-[#f2a33a]" : "bg-[#efeee9]"}`} />{state}
        </p>
      </div>
    </li>
  );
}

function Finding({ title, value, body, source, warn }: { title: string; value: string; body: string; source: string; warn?: boolean }) {
  return (
    <div className="grid gap-4 border-b border-[#efeee9]/15 py-9 md:grid-cols-[1fr_1.3fr] md:gap-12">
      <div>
        <dt className="text-[1.15rem] font-semibold">{title}</dt>
        <dd className={`f-display mt-2 text-[clamp(2.2rem,3.6vw,3rem)] font-semibold leading-none tabular-nums ${warn ? "text-[#f2a33a]" : ""}`}>{value}</dd>
      </div>
      <dd>
        <p className="max-w-[52ch] text-[1.12rem] leading-relaxed">{body}</p>
        <p className="f-mono mt-3 text-sm text-[#efeee9]/65">{source}</p>
      </dd>
    </div>
  );
}

function Ref({ n }: { n: number }) {
  return <sup><a href={`#ref-${n}`} className="f-display ml-0.5 italic text-[#f2a33a]" aria-label={`Source ${n}`}>{n}</a></sup>;
}

const STEP_MS = 1900; // first pass: how long each stage holds the spotlight
const AMBIENT_MS = 4200; // afterwards: the dot keeps orbiting, slowly and without moving any text

/** The loop. On first view it plays once (1 → 7): each stage takes the spotlight while the others fade.
 *  After that it settles into an ambient orbit: every stage stays readable and the stage the dot passes
 *  is only marked in amber. It pauses off-screen; reduced motion shows everything still. */
function Method() {
  const ref = useRef<HTMLDivElement>(null);
  const [spot, setSpot] = useState(-1); // spotlight stage during the first pass, -1 otherwise
  const [step, setStep] = useState(0); // stages travelled so far; only grows, so the dot never spins backwards
  const [ambient, setAmbient] = useState(false);
  const visible = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timers: number[] = [];
    let interval = 0, started = false;
    const io = new IntersectionObserver(([e]) => {
      visible.current = e.isIntersecting;
      if (!e.isIntersecting || started || e.intersectionRatio < 0.45) return;
      started = true;
      LOOP.forEach((_, i) => timers.push(window.setTimeout(() => { setSpot(i); setStep(i); }, 300 + i * STEP_MS)));
      timers.push(window.setTimeout(() => {
        setSpot(-1); setAmbient(true);
        interval = window.setInterval(() => { if (visible.current) setStep((n) => n + 1); }, AMBIENT_MS);
      }, 300 + LOOP.length * STEP_MS + 400));
    }, { threshold: [0, 0.45] });
    io.observe(el);
    return () => { io.disconnect(); timers.forEach(clearTimeout); clearInterval(interval); };
  }, []);

  const R = 150, C = 200;
  const angle = (i: number) => -Math.PI / 2 + (i / LOOP.length) * Math.PI * 2;
  const mark = step % LOOP.length, turn = (step / LOOP.length) * 360;
  const dim = (i: number) => spot >= 0 && spot !== i;

  return (
    <div ref={ref} className="mt-12 grid items-center gap-12 lg:grid-cols-[5fr_6fr]">
      <figure className="mx-auto w-full max-w-[500px]">
        <svg viewBox="-130 -10 660 420" className="w-full" role="img" aria-label="The loop: consent, landmarks, automated check, model check, human review, train and measure, record next, and back to consent.">
          <circle cx={C} cy={C} r={R} fill="none" stroke="rgba(239,238,233,0.35)" strokeWidth="1" />
          {LOOP.map(([label], i) => {
            const a = angle(i), x = C + R * Math.cos(a), y = C + R * Math.sin(a);
            const lx = C + (R + 28) * Math.cos(a), ly = C + (R + 28) * Math.sin(a);
            const anchor = Math.abs(Math.cos(a)) < 0.2 ? "middle" : Math.cos(a) > 0 ? "start" : "end";
            const on = spot === i || (ambient && mark === i);
            return (
              <g key={label} className="transition-opacity duration-700" opacity={dim(i) ? 0.35 : 1}>
                <circle cx={x} cy={y} r={spot === i ? 15 : 12} fill={on ? "#f2a33a" : "#0c0c0b"} stroke={on ? "#f2a33a" : "rgba(239,238,233,0.8)"} className="transition-all duration-700" />
                <text x={x} y={y + 5} textAnchor="middle" fontSize="14" fill={on ? "#0c0c0b" : "#efeee9"} className="f-display" fontStyle="italic">{i + 1}</text>
                <text x={lx} y={ly + 5} textAnchor={anchor} fontSize="19" fill="#efeee9" className="f-body">{label}</text>
              </g>
            );
          })}
          <g style={{ transform: `rotate(${turn}deg)`, transformOrigin: `${C}px ${C}px`, transition: `transform ${ambient ? 1600 : 900}ms cubic-bezier(.22,1,.36,1)` }}>
            <circle cx={C} cy={C - R} r="6" fill="#f2a33a" />
          </g>
          <text x={C} y={C - 4} textAnchor="middle" fontSize="32" fill="#efeee9" className="f-display" fontStyle="italic">one loop</text>
          <text x={C} y={C + 22} textAnchor="middle" fontSize="13" fill="rgba(239,238,233,0.7)" className="f-body">more data · better model · next gap</text>
        </svg>
      </figure>
      <ol>
        {LOOP.map(([t, d], i) => {
          const on = spot === i, marked = on || (ambient && mark === i);
          return (
            <li key={t} aria-current={on ? "step" : undefined}
                className={`grid grid-cols-[2.5rem_1fr] gap-x-3 border-b border-[#efeee9]/15 py-3.5 transition-all duration-500 ${dim(i) ? "opacity-30" : "opacity-100"} ${on ? "translate-x-2" : ""}`}>
              <span className={`f-display text-2xl italic leading-none transition-colors duration-700 ${marked ? "text-[#f2a33a]" : "text-[#efeee9]/60"}`}>{i + 1}</span>
              <div>
                <h3 className={`font-semibold transition-all duration-500 ${on ? "text-[1.6rem]" : "text-[1.25rem]"}`}>{t}</h3>
                {/* During the first pass only the spotlit stage shows its text, so the whole loop fits on one screen. */}
                <div className={`grid transition-[grid-template-rows] duration-500 ${dim(i) ? "grid-rows-[0fr]" : "grid-rows-[1fr]"}`}>
                  <p className="overflow-hidden"><span className="mt-1 block max-w-[50ch] text-[1.1rem] leading-relaxed text-[#efeee9]/80">{d}</span></p>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
