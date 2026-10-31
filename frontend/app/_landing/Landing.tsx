"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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

const NAV = [["#method", "Method"], ["#readings", "Readings"], ["#evidence", "Evidence"], ["#observers", "Team"]] as const;

const LOOP = [
  ["Consent", "A pseudonymous signer code and a purpose-specific consent record, before the camera turns on."],
  ["Landmarks", "MediaPipe runs in the browser. Body and hand landmarks are kept; the video never leaves the device."],
  ["Automated check", "Missing hands, out-of-frame points, mirrored or too-short clips. Every failure says why."],
  ["Model check", "A model trained on INCLUDE scores how closely the clip matches the dataset. It never calls a sign correct."],
  ["Human review", "People approve, reject or ask for a recapture. Linguistic validation stays with native and Deaf signers."],
  ["Train and measure", "A small model retrains on approved clips and is measured on a test set frozen before collection."],
  ["Record next", "Coverage gaps and missing signers rank the next sign; model uncertainty joins once a model is trained on the project."],
] as const;

const OBSERVERS = [
  ["Tashvi Adhlakha", "Team Leader", "Next-sample ranker and queue, external datasets; export (in progress)."],
  ["Bhavesh Lakhmani", "", "Capture and workbench, deletion and consent withdrawal, the model check."],
  ["Reuben Raju", "", "Simulation harness and benchmark (in progress), transfer-learning tests."],
  ["Aakarshi Dwivedi", "", "Dataset licensing, the INCLUDE import, recording day, acceptance testing."],
] as const;

export default function Landing() {
  const [r, setR] = useState<Readings | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => { loadReadings().then(setR, () => setOffline(true)); }, []);

  const run = r?.run, cal = run?.metrics.calibration;
  const pending = offline ? "Backend offline" : "Reading…";

  return (
    <div className="f-body bg-[#0c0c0b] text-[#efeee9] selection:bg-[#f2a33a] selection:text-[#0c0c0b]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:bg-[#efeee9] focus:px-3 focus:py-2 focus:text-[#0c0c0b]">Skip to content</a>

      <header className="sticky top-0 z-40 border-b border-[#efeee9]/15 bg-[#0c0c0b]/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-5 py-3.5 md:px-10">
          <Link href="/" className="f-display text-lg font-bold uppercase tracking-[0.22em]">Signforge</Link>
          <nav aria-label="Plates" className="ml-auto hidden gap-8 text-sm text-[#efeee9]/70 md:flex">
            {NAV.map(([h, l]) => (
              <a key={h} href={h} className="hover:text-[#efeee9]">{l}</a>
            ))}
          </nav>
          <Link href="/dashboard" className="ml-auto border border-[#efeee9]/70 px-4 py-2 text-sm font-semibold transition-colors hover:border-[#f2a33a] hover:bg-[#f2a33a] hover:text-[#0c0c0b] md:ml-0">
            <span className="sm:hidden">Dashboard</span><span className="hidden sm:inline">Open the dashboard</span>
          </Link>
        </div>
      </header>

      <main id="main">
        {/* Plate I: the sign as a chronophotograph. */}
        <section aria-labelledby="plate-1" className="relative overflow-hidden">
          <div aria-hidden className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(239,238,233,0.05)_1px,transparent_1px)] bg-[length:64px_100%]" />
          <div className="relative mx-auto max-w-[1400px] px-5 pt-10 md:px-10 md:pt-12">
            <h1 id="plate-1" className="f-display max-w-[13ch] text-[clamp(3.1rem,7.4vw,6.6rem)] font-semibold leading-[0.92] tracking-[-0.02em] [text-wrap:balance]">
              Know which sign to record <em className="font-medium">next.</em>
            </h1>
          </div>
          <figure className="relative mt-6">
            <div className="h-[clamp(220px,27vw,360px)] border-y border-[#efeee9]/12">
              <Chronograph sampleId={offline ? -1 : r?.plateId ?? null}
                           label="Chronophotograph: eleven faint exposures of the sign HELLO spread across the plate, with a bright figure replaying the clip as a shutter line crosses." />
            </div>
            <figcaption className="mx-auto grid max-w-[1400px] gap-6 px-5 py-6 md:grid-cols-[1fr_auto] md:items-end md:px-10">
              <p className="max-w-[62ch] text-[0.95rem] leading-relaxed text-[#efeee9]/75">
                <span className="f-display mr-2 text-lg italic text-[#efeee9]">Pl. I.</span>
                HELLO in Indian Sign Language{r?.plateFrames ? `, ${r.plateFrames} frames` : ""}, from the INCLUDE dataset (CC BY 4.0).
                Drawn from stored body and hand landmarks: SIGNFORGE keeps the motion, never the video. It checks every clip like this one,
                learns from it, and tells a community which sign to collect next.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/dashboard" className="bg-[#efeee9] px-5 py-3 font-semibold text-[#0c0c0b] transition-colors hover:bg-[#f2a33a]">Open the dashboard</Link>
                <a href="#method" className="border border-[#efeee9]/40 px-5 py-3 font-semibold transition-colors hover:border-[#efeee9]">How it works</a>
              </div>
            </figcaption>
          </figure>
        </section>

        {/* Plate II: live readings, printed on silver-gelatin stock. */}
        <section id="readings" aria-labelledby="plate-2" className="scroll-mt-16 bg-[#d6d5cf] text-[#0c0c0b]">
          <div className="mx-auto max-w-[1400px] px-5 py-20 md:px-10">
            <div className="flex flex-wrap items-baseline justify-between gap-4 border-b-2 border-[#0c0c0b] pb-4">
              <h2 id="plate-2" className="f-display text-[clamp(2rem,4vw,3.4rem)] font-semibold leading-none">
                <span className="mr-3 italic font-medium">Pl. II.</span>The readings
              </h2>
              <p className="f-mono text-xs uppercase tracking-[0.12em] text-[#0c0c0b]/70">{offline ? "Backend offline" : r ? "Read live from the app" : "Reading…"}</p>
            </div>
            <ol>
              <Reading n="a" q="Is this clip good?" built="Consent, in-browser landmarks, and an automated check that explains every failure."
                       value={r ? `${r.recorded} recorded` : pending}
                       note={r ? `+ ${r.imported} imported from INCLUDE · ${r.passed} of ${r.recorded + r.imported} passed the check` : undefined}
                       state="Running" />
              <Reading n="b" q="Does it match the dataset?" built="A model trained on INCLUDE scores each new clip. Temperature-calibrated, but not yet reliable."
                       value={run?.metrics.accuracy != null ? pct(run.metrics.accuracy) : r ? "Not evaluated" : pending}
                       note={run ? `top-1 on ${run.metrics.n_test} held-out clips (run #${run.id})` : undefined}
                       state={offline ? "Backend offline" : cal ? (cal.reliability_passed ? "Calibrated" : "Calibration failed · auto-accept off") : "Not evaluated"}
                       warn={!!cal && !cal.reliability_passed} />
              <Reading n="c" q="Is this sign enough?" built="A per-sign verdict from coverage, signer count and the learning curve."
                       value="No verdict" note="needs the simulation results first" state="Not built yet" warn href="#evidence" />
              <Reading n="d" q="What should we record next?" built="A ranked queue from coverage gaps, missing signers and, later, model uncertainty."
                       value={r?.next?.gloss ?? (r ? "Nothing queued" : pending)}
                       note={r?.next ? (r.next.ties ? `${r.next.project}: tied with ${r.next.ties} other signs` : `${r.next.project}: top of the queue`) : undefined}
                       state="Running" href="#record-next" last />
            </ol>
          </div>
        </section>

        {/* Plate III: why. Sources sit in the margin, as in a monograph. */}
        <section id="story" aria-labelledby="plate-3" className="scroll-mt-16">
          <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-24 md:px-10 lg:grid-cols-[5fr_6fr_3fr]">
            <h2 id="plate-3" className="f-display text-[clamp(2.2rem,4vw,3.6rem)] font-semibold leading-[1.02] [text-wrap:balance]">
              <span className="block text-[0.5em] italic font-medium text-[#efeee9]/55">Pl. III.</span>
              Sign-language AI is held back by data, not by algorithms.
            </h2>
            <div className="max-w-[60ch] space-y-5 text-lg leading-relaxed text-[#efeee9]/85">
              <p>More than 300 sign languages are used by over 70 million Deaf people.<Ref n={1} /> Most have almost no data a model can learn from,
                and what exists is scattered: one survey indexed 120 datasets across 35 sign languages, recorded and annotated in ways that do not line up.<Ref n={2} /></p>
              <p>Indian Sign Language is not starting from zero. But recent work points to the same gaps: regional variation, few signers,
                and data collected without a clear record of consent.<Ref n={3} /></p>
              <p className="text-[#efeee9]">So we did not build another translator. We built the instrument that comes before one: it measures the data a community
                already has, and tells it what to record next.</p>
            </div>
            <aside aria-label="Sources" className="space-y-4 border-l border-[#efeee9]/20 pl-5 text-sm leading-relaxed text-[#efeee9]/60">
              <p id="ref-1"><span className="f-display italic text-[#efeee9]">1.</span> United Nations, International Day of Sign Languages.</p>
              <p id="ref-2"><span className="f-display italic text-[#efeee9]">2.</span> Ni et al., Sign-Language Datasets at Scale, ACL 2026.</p>
              <p id="ref-3"><span className="f-display italic text-[#efeee9]">3.</span> Wadhera, Mahmud &amp; Dhaneshwar, Towards Inclusive Sign Language Recognition, CVPR Workshops 2026.</p>
            </aside>
          </div>
        </section>

        {/* Plate IV: the method, drawn as the closed loop it is. */}
        <section id="method" aria-labelledby="plate-4" className="scroll-mt-16 border-t border-[#efeee9]/15">
          <div className="mx-auto grid max-w-[1400px] items-center gap-14 px-5 py-24 md:px-10 lg:grid-cols-[5fr_6fr]">
            <LoopFigure />
            <div>
              <h2 id="plate-4" className="f-display text-[clamp(2.2rem,4vw,3.6rem)] font-semibold leading-[1.02]">
                <span className="mr-3 italic font-medium text-[#efeee9]/55">Pl. IV.</span>The method
              </h2>
              <p className="mt-3 max-w-[52ch] text-[#efeee9]/70">One loop. Each turn adds clips, re-measures the model, and points at the next gap.</p>
              <ol className="mt-8 border-t border-[#efeee9]/15">
                {LOOP.map(([t, d], i) => (
                  <li key={t} className="grid grid-cols-[2.25rem_1fr] gap-x-3 border-b border-[#efeee9]/15 py-4 md:grid-cols-[2.25rem_10.5rem_1fr]">
                    <span className="f-display pt-0.5 italic text-[#f2a33a]">{i + 1}</span>
                    <h3 className="font-semibold">{t}</h3>
                    <p className="col-start-2 mt-1 max-w-[50ch] text-[0.95rem] leading-relaxed text-[#efeee9]/75 md:col-start-3 md:mt-0">{d}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        {/* Plate V: findings, failures included. */}
        <section id="evidence" aria-labelledby="plate-5" className="scroll-mt-16 bg-[#d6d5cf] text-[#0c0c0b]">
          <div className="mx-auto max-w-[1400px] px-5 py-24 md:px-10">
            <h2 id="plate-5" className="f-display max-w-[18ch] text-[clamp(2.2rem,4vw,3.6rem)] font-semibold leading-[1.02] [text-wrap:balance]">
              <span className="mr-3 italic font-medium">Pl. V.</span>What we measured, including what did not work.
            </h2>
            <dl className="mt-12 border-t-2 border-[#0c0c0b]">
              <Finding fig="1" title="The model on unseen sessions"
                       value={run?.metrics.accuracy != null ? pct(run.metrics.accuracy) : offline ? "Offline" : "—"}
                       body={run ? `Top-1 accuracy on ${run.metrics.n_test} INCLUDE clips from recording sessions the model never saw (macro-F1 ${run.metrics.macro_f1?.toFixed(2)}). INCLUDE has no signer IDs, so this is not a signer-independent result.`
                         : offline ? "The backend is offline, so this reading is missing." : "Appears once a calibrated model has been trained."}
                       source={run ? `Live · run #${run.id}` : "Live"} />
              <Finding fig="2" title="Calibration"
                       value={cal ? `${cal.test_before.ece.toFixed(2)} → ${cal.test_after.ece.toFixed(2)}` : offline ? "Offline" : "—"}
                       body={cal ? `Temperature scaling cut the calibration error on test clips${cal.reliability_passed ? ` below the ${cal.max_ece.toFixed(2)} limit.` : `, but not below the ${cal.max_ece.toFixed(2)} limit. The model's confidence still overstates how often it is right, so automatic acceptance stays off and every clip goes to a person.`}`
                         : offline ? "The backend is offline, so this reading is missing." : "Appears once a calibrated model has been trained."}
                       source={cal ? `Live · run #${run!.id}` : "Live"} warn={!!cal && !cal.reliability_passed} />
              <Finding fig="3" title={`Our own ${r?.teamMatch?.gloss || "team"} recordings`}
                       value={r?.teamMatch ? pct(r.teamMatch.median) : offline ? "Offline" : "—"}
                       body={r?.teamMatch ? `Median match against the dataset across ${r.teamMatch.n} of our clips. INCLUDE signers keep both hands in view; most of our clips show one. Surfacing exactly this kind of gap is what the instrument is for.`
                         : offline ? "The backend is offline, so this reading is missing." : "Appears once team clips have been scored."}
                       source="Live · cause analysed 31 Oct 2026" warn={!!r?.teamMatch && r.teamMatch.median < 0.5} />
              <Finding fig="4" title="Is a sign enough?" value="Not built"
                       body="The per-sign sufficiency verdict needs learning curves from the simulation, which is still in progress. Until then the app shows coverage only."
                       source="Planned" warn />
              <Finding fig="5" title="Browser and Python extraction agree" value="16 / 18"
                       body="The same INCLUDE clips extracted in the browser and in Python gave the same top prediction 16 times out of 18."
                       source="docs/EXTRACTOR_COMPARISON.md · 31 Oct 2026" />
              <Finding fig="6" title="Transfer learning" value="Blocked"
                       body="No pretrained checkpoint has been verified as compatible with our landmark format, so we claim no transfer result."
                       source="docs/MODEL_CARD.md" warn />
            </dl>
            <p className="mt-10 max-w-[64ch] leading-relaxed">
              <span className="font-semibold">What SIGNFORGE is not:</span> a translator, a validated ISL corpus, or proof that a sign is correct.
              A match score says how closely a clip resembles the dataset. Whether it is good signing is decided by people, ideally native and Deaf signers.
            </p>
          </div>
        </section>

        <section id="observers" aria-labelledby="plate-6" className="scroll-mt-16">
          <div className="mx-auto max-w-[1400px] px-5 py-24 md:px-10">
            <h2 id="plate-6" className="f-display text-[clamp(2.2rem,4vw,3.6rem)] font-semibold leading-none">
              <span className="mr-3 italic font-medium text-[#efeee9]/55">Observers.</span>Team Claude&apos;s Clan
            </h2>
            <ul className="mt-12 grid gap-x-12 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
              {OBSERVERS.map(([name, role, did]) => (
                <li key={name} className="border-t border-[#efeee9]/40 pt-4">
                  <p className="f-display text-2xl font-semibold">{name}</p>
                  {role && <p className="f-mono mt-1 text-xs uppercase tracking-[0.12em] text-[#f2a33a]">{role}</p>}
                  <p className="mt-2 leading-relaxed text-[#efeee9]/75">{did}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="record-next" aria-labelledby="close" className="scroll-mt-16 border-t border-[#efeee9]/15">
          <div className="mx-auto max-w-[1400px] px-5 py-24 md:px-10">
            <h2 id="close" className="f-display max-w-[17ch] text-[clamp(2.6rem,5.6vw,5rem)] font-semibold leading-[0.98] [text-wrap:balance]">
              {r?.next ? <>Right now, the queue says: record <em className="font-medium text-[#f2a33a]">{r.next.gloss}</em>.</> : <>See the queue for yourself.</>}
            </h2>
            {r?.next && (
              <p className="mt-5 max-w-[60ch] text-lg leading-relaxed text-[#efeee9]/75">
                {cap(r.next.reason)}
                {r.next.ties > 0 && ` It is tied with ${r.next.ties} other signs in ${r.next.project}: none has an approved clip yet, so any of them is an equally good next take.`}
              </p>
            )}
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard" className="bg-[#efeee9] px-5 py-3 font-semibold text-[#0c0c0b] transition-colors hover:bg-[#f2a33a]">Open the dashboard</Link>
              <Link href="/capture" className="border border-[#efeee9]/40 px-5 py-3 font-semibold transition-colors hover:border-[#efeee9]">Record a sign</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#efeee9]/15">
        <p className="mx-auto max-w-[1400px] px-5 py-8 text-sm text-[#efeee9]/55 md:px-10">
          INCLUDE: Sridhar et al., ACM Multimedia 2020, CC BY 4.0, Zenodo 4010759. Plate I is drawn from its landmarks; no video is shown or stored.
        </p>
      </footer>
    </div>
  );
}

function Reading({ n, q, built, value, note, state, warn, href, last }: {
  n: string; q: string; built: string; value: string; note?: string; state: string; warn?: boolean; href?: string; last?: boolean;
}) {
  const title = <><span className="f-display mr-2 italic font-medium text-[#0c0c0b]/55">{n}.</span>{q}</>;
  return (
    <li className={`grid gap-3 py-7 md:grid-cols-[1.25fr_1.4fr_1.15fr_0.95fr] md:items-baseline md:gap-8 ${last ? "" : "border-b border-[#0c0c0b]/25"}`}>
      <h3 className="f-display text-[1.65rem] font-semibold leading-tight">
        {href ? <a href={href} className="underline decoration-[#0c0c0b]/30 decoration-1 underline-offset-[6px] hover:decoration-[#0c0c0b]">{title}</a> : title}
      </h3>
      <p className="max-w-[42ch] leading-relaxed text-[#0c0c0b]/80">{built}</p>
      <p>
        <span className="f-display block text-[clamp(2rem,3.4vw,3rem)] font-semibold leading-none tabular-nums">{value}</span>
        {note && <span className="f-mono mt-2 block text-xs leading-relaxed text-[#0c0c0b]/70">{note}</span>}
      </p>
      <p className={`f-mono text-xs uppercase tracking-[0.1em] ${warn ? "text-[#8a4100]" : "text-[#0c0c0b]/75"}`}>
        <span aria-hidden className={`mr-2 inline-block size-2 rounded-full align-middle ${warn ? "bg-[#c66a00]" : "bg-[#0c0c0b]"}`} />{state}
      </p>
    </li>
  );
}

function Finding({ fig, title, value, body, source, warn }: { fig: string; title: string; value: string; body: string; source: string; warn?: boolean }) {
  return (
    <div className="grid gap-3 border-b border-[#0c0c0b]/25 py-8 md:grid-cols-[3rem_13rem_12rem_1fr] md:gap-8">
      <dt className="contents">
        <span className="f-display text-lg italic text-[#0c0c0b]/55">Fig. {fig}</span>
        <span className="font-semibold">{title}</span>
      </dt>
      <dd className={`f-display whitespace-nowrap text-[1.9rem] font-semibold leading-none tabular-nums ${warn ? "text-[#8a4100]" : ""}`}>{value}</dd>
      <dd>
        <p className="max-w-[62ch] leading-relaxed">{body}</p>
        <p className="f-mono mt-2 text-xs text-[#0c0c0b]/65">{source}</p>
      </dd>
    </div>
  );
}

function Ref({ n }: { n: number }) {
  return <sup><a href={`#ref-${n}`} className="f-display ml-0.5 italic text-[#f2a33a]" aria-label={`Source ${n}`}>{n}</a></sup>;
}

/** The loop as a closed circle: seven stages on one orbit, a safelight dot travelling round it. */
function LoopFigure() {
  const R = 150, C = 200;
  const pts = LOOP.map((_, i) => {
    const a = -Math.PI / 2 + (i / LOOP.length) * Math.PI * 2;
    return [C + R * Math.cos(a), C + R * Math.sin(a), a] as const;
  });
  return (
    <figure className="mx-auto w-full max-w-[520px]">
      <svg viewBox="-90 -10 580 420" className="w-full" role="img" aria-label="The SIGNFORGE loop: consent, landmarks, automated check, model check, human review, train and measure, record next, and back to consent.">
        <circle cx={C} cy={C} r={R} fill="none" stroke="rgba(239,238,233,0.35)" strokeWidth="1" />
        <circle cx={C} cy={C} r={R - 22} fill="none" stroke="rgba(239,238,233,0.12)" strokeWidth="1" strokeDasharray="2 6" />
        {pts.map(([x, y, a], i) => {
          const lx = C + (R + 30) * Math.cos(a), ly = C + (R + 30) * Math.sin(a);
          const anchor = Math.abs(Math.cos(a)) < 0.2 ? "middle" : Math.cos(a) > 0 ? "start" : "end";
          return (
            <g key={i}>
              <circle cx={x} cy={y} r="11" fill="#0c0c0b" stroke="rgba(239,238,233,0.8)" />
              <text x={x} y={y + 4} textAnchor="middle" fontSize="11" fill="#efeee9" className="f-display" fontStyle="italic">{i + 1}</text>
              <text x={lx} y={ly + 4} textAnchor={anchor} fontSize="12" fill="rgba(239,238,233,0.75)" className="f-body">{LOOP[i][0]}</text>
            </g>
          );
        })}
        <g className="origin-center motion-safe:animate-[spin_14s_linear_infinite]" style={{ transformOrigin: `${C}px ${C}px` }}>
          <circle cx={C} cy={C - R} r="5" fill="#f2a33a" />
        </g>
        <text x={C} y={C - 6} textAnchor="middle" fontSize="30" fill="#efeee9" className="f-display" fontStyle="italic">one loop</text>
        <text x={C} y={C + 18} textAnchor="middle" fontSize="11" fill="rgba(239,238,233,0.6)" className="f-mono">more data · better model · next gap</text>
      </svg>
    </figure>
  );
}
