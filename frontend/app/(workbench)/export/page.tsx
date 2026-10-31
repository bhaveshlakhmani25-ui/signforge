"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL, api, type Project, type Sample, type SignClass } from "@/lib/api";
import { card, ErrorBanner } from "@/components/ui";

export default function ExportPage() {
  const [project, setProject] = useState<Project | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [classes, setClasses] = useState<SignClass[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [approvedOnly, setApprovedOnly] = useState(true);
  const [includeDemo, setIncludeDemo] = useState(false);

  const fetchData = useCallback(async () => {
    const [p] = await api<Project[]>("/api/projects");
    if (!p) throw new Error("No project found. Run seed script in backend.");
    const [s, c] = await Promise.all([
      api<Sample[]>(`/api/samples?project_id=${p.id}&include_demo=true`),
      api<SignClass[]>(`/api/sign-classes?project_id=${p.id}`),
    ]);
    return { project: p, samples: s, classes: c };
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchData();
      setProject(data.project);
      setSamples(data.samples);
      setClasses(data.classes);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project details");
    } finally {
      setLoading(false);
    }
  }, [fetchData]);

  useEffect(() => {
    let active = true;
    fetchData().then((data) => {
      if (!active) return;
      setProject(data.project);
      setSamples(data.samples);
      setClasses(data.classes);
      setError("");
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Failed to load project details");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [fetchData]);

  const retry = useCallback(() => {
    setLoading(true);
    void loadData();
  }, [loadData]);

  const eligibleSamples = samples.filter((s) => {
    if (approvedOnly && s.review_status !== "approved") return false;
    if (!includeDemo && s.source === "demo_fixture") return false;
    return true;
  });

  const uniqueClasses = new Set(eligibleSamples.map((s) => s.sign_class_id)).size;
  const realCount = eligibleSamples.filter((s) => s.source !== "demo_fixture").length;
  const demoCount = eligibleSamples.filter((s) => s.source === "demo_fixture").length;

  const exportUrl = project
    ? `${API_URL}/api/export?project_id=${project.id}&approved_only=${approvedOnly}&include_demo=${includeDemo}`
    : "#";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Export Corpus &amp; Features</h1>
        <p className="mt-1 max-w-[62ch] text-sm text-indigo">
          Download a reproducible, model-ready dataset bundle. In accordance with SIGNFORGE&apos;s{" "}
          <strong>Privacy-by-Pose</strong> governance, only normalized landmark sequences and verifiable metadata are
          exported. Raw face and video files are excluded by default.
        </p>
      </header>

      {error && <ErrorBanner message={error} onRetry={retry} />}
      {loading && <p className="text-sm">Loading corpus metadata…</p>}

      {!loading && project && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Export configuration */}
          <section className={`${card} space-y-4`} aria-labelledby="export-config">
            <h2 id="export-config" className="font-semibold text-base">
              Export Configuration
            </h2>

            <div className="space-y-3 text-sm">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={approvedOnly}
                  onChange={(e) => setApprovedOnly(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-indigo text-indigo focus:ring-teal"
                />
                <div>
                  <span className="font-medium text-slate-900">Approved samples only (Recommended)</span>
                  <p className="text-xs text-slate-600">
                    Excludes samples pending review, rejected, or flagged for recapture.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeDemo}
                  onChange={(e) => setIncludeDemo(e.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-indigo text-indigo focus:ring-teal"
                />
                <div>
                  <span className="font-medium text-slate-900">Include synthetic DEMO DATA</span>
                  <p className="text-xs text-slate-600">
                    Includes synthetic fallback samples. Kept unchecked for real-world research exports.
                  </p>
                </div>
              </label>
            </div>

            <div className="pt-2 border-t border-lavender/50">
              <a
                href={exportUrl}
                download
                className={`inline-flex items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-colors ${
                  eligibleSamples.length > 0
                    ? "bg-teal hover:bg-teal/90 shadow-sm"
                    : "bg-slate-300 pointer-events-none cursor-not-allowed"
                }`}
              >
                Download Export Package (.zip)
              </a>
              <p className="mt-2 text-xs text-slate-500">
                Package size: ~{(eligibleSamples.length * 0.04).toFixed(1)} MB compressed archive
              </p>
            </div>
          </section>

          {/* Archive Manifest Preview */}
          <section className={`${card} space-y-4`} aria-labelledby="archive-preview">
            <h2 id="archive-preview" className="font-semibold text-base">
              Archive Contents Preview
            </h2>

            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg bg-lavender/20 p-2.5">
                <dt className="text-xs text-indigo">Eligible Samples</dt>
                <dd className="text-lg font-bold text-slate-900">{eligibleSamples.length}</dd>
                <span className="text-xs text-slate-500">
                  {realCount} real {demoCount > 0 && `+ ${demoCount} demo`}
                </span>
              </div>

              <div className="rounded-lg bg-lavender/20 p-2.5">
                <dt className="text-xs text-indigo">Represented Classes</dt>
                <dd className="text-lg font-bold text-slate-900">{uniqueClasses}</dd>
                <span className="text-xs text-slate-500">of {classes.length} active classes</span>
              </div>
            </dl>

            <div className="space-y-2 text-xs">
              <p className="font-medium text-slate-900">Included in the ZIP bundle:</p>
              <ul className="list-disc pl-5 space-y-1 text-slate-600">
                <li>
                  <code className="text-indigo">manifest.json</code>: Complete metadata, signer codes, sample IDs, FPS, QC flags.
                </li>
                <li>
                  <code className="text-indigo">provenance.md</code>: CC-BY-4.0 attribution, Zenodo DOI 10.1145/3394171.3413528.
                </li>
                <li>
                  <code className="text-indigo">landmarks/*.npz</code>: Canonical <code>mp-holistic-75-xyz-v1</code> tensors for each sample.
                </li>
              </ul>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
