"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { api, currentProject, type Consent, type ReviewEvent, type ReviewStatus, type Sample, type SignClass, type Signer, when } from "@/lib/api";
import { card, DemoBadge, ErrorBanner } from "@/components/ui";

const ROLES = [
  ["native_signer", "Native signer"],
  ["deaf_community_member", "Deaf community member"],
  ["interpreter", "Interpreter"],
  ["team_non_signer", "Team member (non-signer)"],
] as const;
const roleLabel = (r: string) => ROLES.find(([k]) => k === r)?.[1] ?? r;
const STATUS: Record<ReviewStatus, [string, string]> = {
  pending_review: ["Pending review", "bg-amber-100 text-amber-950"],
  approved: ["Approved", "bg-teal/15 text-teal"],
  rejected: ["Rejected", "bg-red-100 text-red-900"],
  needs_recapture: ["Needs recapture", "bg-amber-200 text-amber-950"],
};
const Badge = ({ s }: { s: ReviewStatus }) => <span className={`rounded-md px-2 py-0.5 text-xs ${STATUS[s][1]}`}>{STATUS[s][0]}</span>;

async function fetchCorpus() {
  const project = await currentProject();
  if (!project) throw new Error("No project exists yet. A teammate needs to run `python scripts/seed.py` in the backend folder.");
  const [samples, classes, signers] = await Promise.all([
    api<Sample[]>(`/api/samples?project_id=${project.id}&include_demo=true`),
    api<SignClass[]>(`/api/sign-classes?project_id=${project.id}`),
    api<Signer[]>(`/api/signers?project_id=${project.id}`),
  ]);
  const consents = (await Promise.all(signers.map((x) => api<Consent[]>(`/api/consents?signer_id=${x.id}`)))).flat();
  return { project, samples, classes, signers, consents };
}

const PAGE = 50; // rows rendered at once; the corpus grows with every capture

type Filters = { cls: string; source: string; review: string; qc: string };

export default function CorpusPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchCorpus>> | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [f, setF] = useState<Filters>({ cls: "", source: "", review: "", qc: "" });
  const [limit, setLimit] = useState(PAGE);

  const reload = useCallback(() => fetchCorpus().then((d) => { setData(d); setError(""); }, (e) => setError(e.message)), []);
  useEffect(() => { reload(); }, [reload]);

  const gloss = (id: number) => data?.classes.find((c) => c.id === id)?.gloss ?? `#${id}`;
  const code = (id: number) => data?.signers.find((s) => s.id === id)?.code ?? `#${id}`;
  const real = data?.samples.filter((s) => s.source !== "demo_fixture") ?? [];
  const shown = (data?.samples ?? []).filter((s) =>
    (!f.cls || s.sign_class_id === Number(f.cls)) && (!f.source || s.source === f.source) &&
    (!f.review || s.review_status === f.review) && (!f.qc || String(s.qc_passed) === f.qc));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Corpus &amp; review{data && <span className="font-normal text-indigo">: {data.project.name}</span>}</h1>
        <p className="mt-2 max-w-[58ch] rounded-xl border border-indigo/20 bg-lavender/30 p-3 text-sm">
          <strong>The automated check is not a language check.</strong> It only confirms the landmarks were captured cleanly.
          Whether a sample is a correct, natural sign is decided in human review, and it only counts as linguistic validation when the reviewer is a native or Deaf signer. Each decision shows the reviewer&apos;s self-declared role.
        </p>
      </header>
      {error && <ErrorBanner message={`Could not load the corpus. ${error}`} onRetry={() => { setError(""); reload(); }} />}
      {!data && !error && <p className="text-sm">Loading the corpus…</p>}

      {data && (
        <section aria-labelledby="coverage" className={card}>
          <h2 id="coverage" className="font-semibold">Coverage by sign (captured and external-dataset samples; DEMO DATA excluded)</h2>
          <div className="relative mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-indigo"><tr>
                {["Sign", "Samples", "Approved", "Pending", "Needs recapture", "Rejected", "Failed check", "Signers"].map((h) => <th key={h} scope="col" className="py-1 pr-4 font-medium">{h}</th>)}
              </tr></thead>
              <tbody>
                {data.classes.map((c) => {
                  const xs = real.filter((s) => s.sign_class_id === c.id);
                  const n = (st: ReviewStatus) => xs.filter((s) => s.review_status === st).length;
                  const signers = new Set(xs.map((s) => s.signer_id)).size;
                  return (
                    <tr key={c.id} className="border-t border-lavender/60">
                      <th scope="row" className="py-1 pr-4 font-medium">{c.gloss}</th>
                      <td className="pr-4">{xs.length || <span className="text-amber-800">none yet</span>}</td>
                      <td className="pr-4">{n("approved")}</td><td className="pr-4">{n("pending_review")}</td>
                      <td className="pr-4">{n("needs_recapture")}</td><td className="pr-4">{n("rejected")}</td>
                      <td className="pr-4">{xs.filter((s) => !s.qc_passed).length}</td>
                      <td className="pr-4">{signers}{signers === 1 && <span className="ml-1 text-xs text-amber-800">only one signer</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data && <SignersConsent data={data} onDone={reload} />}

      {data && (
        <section aria-labelledby="samples" className="space-y-3">
          <h2 id="samples" className="font-semibold">Samples ({shown.length} of {data.samples.length})</h2>
          <div className="flex flex-wrap gap-3 text-sm">
            {([
              ["cls", "Sign", data.classes.map((c) => [String(c.id), c.gloss])],
              ["source", "Source", [["captured", "Captured"], ["external_dataset", "External dataset"], ["demo_fixture", "DEMO DATA"]]],
              ["review", "Review", Object.entries(STATUS).map(([k, [l]]) => [k, l])],
              ["qc", "Automated check", [["true", "Passed"], ["false", "Failed"]]],
            ] as [keyof Filters, string, string[][]][]).map(([key, label, opts]) => (
              <label key={key}>{label}
                <select className="ml-2 rounded-lg border border-lavender bg-white p-1" value={f[key]} onChange={(e) => { setF({ ...f, [key]: e.target.value }); setLimit(PAGE); }}>
                  <option value="">All</option>
                  {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            ))}
          </div>

          {!shown.length && <p className="rounded-xl border border-dashed border-indigo/30 bg-white p-4 text-sm">
            {data.samples.length ? "No samples match these filters. Set a filter back to All to see more." : "No samples yet. Record one on the Capture page."}</p>}
          {shown.length > 0 && (
            <div className="relative overflow-x-auto rounded-xl border border-lavender bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-navy text-white">
                  <tr>{["#", "Sign", "Signer", "Source", "Frames", "Automated check", "Human review", "Split", "Created", ""].map((h) =>
                    <th key={h} scope="col" className="px-3 py-2 font-medium">{h || <span className="sr-only">Actions</span>}</th>)}</tr>
                </thead>
                <tbody>
                  {shown.slice(0, limit).map((s) => (
                    <Fragment key={s.id}>
                      <tr className="border-t border-lavender align-top">
                        <td className="px-3 py-2">{s.id}</td>
                        <td className="px-3 py-2 font-medium">{gloss(s.sign_class_id)}</td>
                        <td className="px-3 py-2">{code(s.signer_id)}</td>
                        <td className="px-3 py-2">{s.source === "demo_fixture" ? <DemoBadge /> : s.source === "external_dataset" ? `${s.dataset_name || "external"} (external)` : s.source}</td>
                        <td className="px-3 py-2">{s.frame_count} · {s.qc_metrics.duration_s ?? "?"}s</td>
                        <td className="px-3 py-2">
                          {s.qc_passed ? <span className="text-teal">Passed</span> : <span className="text-red-800">Failed</span>}
                          <span className="text-xs"> · {(s.quality_score * 100).toFixed(0)}% complete</span>
                          {s.quality_flags.length > 0 && <ul className="mt-1 text-xs">{s.quality_flags.map((q) => <li key={q.code}>{q.severity === "error" ? "Problem" : "Warning"}: {q.code.replaceAll("_", " ")}</li>)}</ul>}
                        </td>
                        <td className="px-3 py-2"><Badge s={s.review_status} /></td>
                        <td className="px-3 py-2">{s.split}</td>
                        <td className="px-3 py-2 text-xs">{when(s.created_at)}</td>
                        <td className="px-3 py-2">
                          <button className="text-indigo underline" aria-expanded={open === s.id} onClick={() => setOpen(open === s.id ? null : s.id)}>
                            {open === s.id ? "Close" : "Details & review"}
                          </button>
                        </td>
                      </tr>
                      {open === s.id && (
                        <tr className="bg-background"><td colSpan={10} className="px-3 py-3">
                          <SampleDetail sample={s} onDone={reload} />
                        </td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {shown.length > limit && (
            <button className="rounded-lg border border-indigo px-3 py-2 text-sm text-indigo" onClick={() => setLimit(limit + PAGE)}>
              {shown.length - limit <= PAGE ? `Show the remaining ${shown.length - limit}` : `Show ${PAGE} more (${shown.length - limit} not shown)`}
            </button>
          )}
        </section>
      )}
    </div>
  );
}

function SampleDetail({ sample: s, onDone }: { sample: Sample; onDone: () => void }) {
  const [events, setEvents] = useState<ReviewEvent[]>([]);
  const [code, setCode] = useState("");
  const [role, setRole] = useState<string>("team_non_signer");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const loadEvents = useCallback(() => api<ReviewEvent[]>(`/api/samples/${s.id}/reviews`)
    .then(setEvents, (e) => setError(e.message)), [s.id]);
  useEffect(() => { loadEvents(); }, [loadEvents]);

  async function decide(decision: "approved" | "rejected" | "needs_recapture") {
    if (saving) return; // one decision per click, even on a double-click
    setError(""); setSaving(true);
    try {
      await api(`/api/samples/${s.id}/review`, { body: { reviewer_code: code, reviewer_role: role, decision, note } });
      setNote("");
      await loadEvents();
      onDone();
    } catch (e) { setError(`Review not saved; your note is kept. ${e instanceof Error ? e.message : e}`); }
    setSaving(false);
  }

  async function remove() {
    if (saving) return;
    setError(""); setSaving(true);
    try {
      await api(`/api/samples/${s.id}`, { method: "DELETE" });
      onDone();
    } catch (e) { setError(`Not deleted. ${e instanceof Error ? e.message : e}`); setSaving(false); setConfirmDelete(false); }
  }

  const valid = /^[A-Z0-9][A-Z0-9-]{1,15}$/.test(code);
  return (
    <div className="grid gap-4 text-sm lg:grid-cols-2">
      <div className="space-y-2">
        <h3 className="font-semibold">Provenance &amp; features</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-indigo">Feature schema</dt><dd>{s.feature_schema_version} (un-normalised; normalisation is applied at model time)</dd>
          <dt className="text-indigo">Extractor</dt><dd>{s.extractor}</dd>
          <dt className="text-indigo">Model sha256</dt><dd className="break-all">{s.extractor_model_sha || "n/a"}</dd>
          <dt className="text-indigo">Capture</dt><dd>{s.width}×{s.height}, {s.fps.toFixed(1)} fps, un-mirrored</dd>
          <dt className="text-indigo">Consent</dt><dd>record #{s.consent_id} · {s.raw_video_retained ? "raw video retained" : "raw video not stored"}</dd>
          <dt className="text-indigo">Provenance</dt><dd>{s.provenance_note}</dd>
        </dl>
        <h3 className="pt-2 font-semibold">Automated check</h3>
        {s.quality_flags.length ? <ul className="list-disc pl-5 text-xs">{s.quality_flags.map((q) => <li key={q.code}><strong>{q.severity === "error" ? "Problem" : "Warning"}:</strong> {q.message}</li>)}</ul>
          : <p className="text-xs">The automated check found no issues. Human review is still needed.</p>}
        <p className="text-xs text-indigo">{Object.entries(s.qc_metrics).map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="font-semibold">Human review</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label>Reviewer code
            <input className="mt-1 block w-28 rounded-lg border border-lavender p-1 uppercase" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="R-01" />
          </label>
          <label>Role (self-declared)
            <select className="mt-1 block rounded-lg border border-lavender p-1" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </label>
        </div>
        <label className="block">Note
          <input className="mt-1 block w-full rounded-lg border border-lavender p-1" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
        </label>
        {role === "team_non_signer" && <p className="text-xs text-amber-900">A non-signer can check the recording, not the sign. This review does not count as linguistic validation.</p>}
        <div className="flex flex-wrap gap-2">
          <button disabled={!valid || saving} className="rounded-lg bg-teal px-3 py-1 text-white disabled:opacity-60" onClick={() => decide("approved")}>Approve</button>
          <button disabled={!valid || saving} className="rounded-lg border border-amber-600 px-3 py-1 text-amber-950 disabled:opacity-60" onClick={() => decide("needs_recapture")}>Request recapture</button>
          <button disabled={!valid || saving} className="rounded-lg bg-red-700 px-3 py-1 text-white disabled:opacity-60" onClick={() => decide("rejected")}>Reject</button>
        </div>
        {!valid && <p className="text-xs">Enter a reviewer code (e.g. R-01) to enable review actions.</p>}
        {error && <p role="alert" className="text-red-900">{error}</p>}
        <div className="border-t border-lavender pt-3">
          {confirmDelete ? (
            <div className="space-y-2">
              <p className="text-xs text-red-900">Deleting erases this sample&apos;s landmarks and review history for good.
                {(s.review_status === "approved" || s.split === "test") && " It is approved or in the frozen test set, so model results that used it can no longer be reproduced."}
                {" "}Models already trained on it are not retrained.</p>
              <div className="flex gap-2">
                <button disabled={saving} className="rounded-lg bg-red-700 px-3 py-1 text-white disabled:opacity-60" onClick={remove}>{saving ? "Deleting…" : "Delete permanently"}</button>
                <button disabled={saving} className="rounded-lg border border-indigo px-3 py-1 text-indigo" onClick={() => setConfirmDelete(false)}>Keep it</button>
              </div>
            </div>
          ) : <button className="rounded-lg border border-red-700 px-3 py-1 text-red-800" onClick={() => setConfirmDelete(true)}>Delete this sample</button>}
        </div>
        {events.length > 0 && (
          <ul className="text-xs">{events.map((e) => (
            <li key={e.id} className="break-words">{when(e.created_at)}: <strong>{e.decision.replaceAll("_", " ")}</strong> by {e.reviewer_code} ({roleLabel(e.reviewer_role)}){e.note && `: “${e.note}”`}</li>
          ))}</ul>
        )}
      </div>
    </div>
  );
}

function SignersConsent({ data, onDone }: { data: Awaited<ReturnType<typeof fetchCorpus>>; onDone: () => void }) {
  const [asking, setAsking] = useState<number | null>(null);
  const [erase, setErase] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function withdraw(id: number) {
    if (busy) return;
    setError(""); setBusy(true);
    try {
      await api(`/api/consents/${id}/withdraw`, { body: { delete_samples: erase } });
      setAsking(null);
      onDone();
    } catch (e) { setError(`Consent not withdrawn. ${e instanceof Error ? e.message : e}`); }
    setBusy(false);
  }

  return (
    <section aria-labelledby="consents" className={card}>
      <h2 id="consents" className="font-semibold">Signers &amp; consent</h2>
      <p className="mt-1 max-w-[58ch] text-xs">Withdrawing consent stops all further use of a signer&apos;s samples: new recordings, model training and public replay.
        You can also erase the stored landmarks. Models already trained are not retrained, and files already exported are outside this app&apos;s control.</p>
      {!data.consents.length && <p className="mt-2 text-sm">No signers have given consent yet.</p>}
      <ul className="mt-3 space-y-2">
        {data.consents.map((c) => {
          const signer = data.signers.find((x) => x.id === c.signer_id);
          const n = data.samples.filter((x) => x.consent_id === c.id).length;
          const active = c.status === "active";
          return (
            <li key={c.id} className="rounded-lg border border-lavender/70 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <strong>{signer?.code ?? `#${c.signer_id}`}</strong>
                <span className={`rounded-md px-2 py-0.5 text-xs ${active ? "bg-teal/15 text-teal" : "bg-red-100 text-red-900"}`}>{active ? "Consent active" : "Consent withdrawn"}</span>
                <span className="text-xs">allowed: {c.allowed_uses.join(", ").replaceAll("_", " ")} · {n} sample{n === 1 ? "" : "s"} stored</span>
                {active && asking !== c.id && (
                  <button className="ml-auto rounded-lg border border-red-700 px-3 py-1 text-red-800" onClick={() => { setAsking(c.id); setError(""); }}>Withdraw consent</button>
                )}
              </div>
              {asking === c.id && (
                <div className="mt-3 space-y-2">
                  <label className="flex gap-2 text-sm"><input type="checkbox" checked={erase} onChange={(e) => setErase(e.target.checked)} />
                    <span>Also delete this consent&apos;s {n} stored sample{n === 1 ? "" : "s"} (landmarks and reviews). This can&apos;t be undone.</span></label>
                  <div className="flex gap-2">
                    <button disabled={busy} className="rounded-lg bg-red-700 px-3 py-1 text-white disabled:opacity-60" onClick={() => withdraw(c.id)}>{busy ? "Withdrawing…" : "Confirm withdrawal"}</button>
                    <button disabled={busy} className="rounded-lg border border-indigo px-3 py-1 text-indigo" onClick={() => setAsking(null)}>Cancel</button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p role="alert" className="mt-2 text-sm text-red-900">{error}</p>}
    </section>
  );
}
