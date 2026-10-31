// Public, non-secret base URL of the local FastAPI backend.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Project = { id: number; name: string; target_language: string; domain: string };
export type SignClass = { id: number; project_id: number; gloss: string; prompt_text: string; dialect_note: string };
export type Signer = { id: number; project_id: number; code: string };
export type Consent = { id: number; signer_id: number; allowed_uses: string[]; retention: string; status: string };
export type ReviewStatus = "pending_review" | "approved" | "rejected" | "needs_recapture";
export type QcFlag = { code: string; severity: "error" | "warning"; message: string };
export type Sample = {
  id: number; sign_class_id: number; signer_id: number; consent_id: number;
  source: "captured" | "public_dataset" | "demo_fixture" | "external_dataset"; extractor: string; extractor_model_sha: string;
  frame_count: number; fps: number; width: number; height: number; quality_score: number; qc_passed: boolean;
  quality_flags: QcFlag[]; qc_metrics: Record<string, number>; review_status: ReviewStatus; split: string;
  feature_schema_version: string; feature_sha256: string; raw_video_retained: boolean; provenance_note: string; created_at: string;
  dataset_name?: string; dataset_version?: string; dataset_license?: string; citation?: string;
  external_sample_id?: string; external_signer_id?: string; external_split?: string;
};
export type ReviewEvent = { id: number; reviewer_code: string; reviewer_role: string; decision: string; note: string; created_at: string };
export type Frame = { t: number; pose: number[][] | null; left_hand: number[][] | null; right_hand: number[][] | null };

export type ActiveLearningQueueItem = {
  sign_class_id: number;
  gloss: string;
  priority: number;
  coverage_gap: number;
  signer_gap: number;
  uncertainty: number | null;
  uncertainty_display: string;
  suggested_signer: "new_signer" | "any_consenting_signer";
  approved_sample_count: number;
  distinct_signer_count: number;
  target_samples: number;
  target_signers: number;
  reason: string;
  formula_version: string;
};

export type ActiveLearningQueueResponse = {
  project_id: number;
  formula_version: string;
  weights: { coverage: number; signer: number; uncertainty: number };
  queue: ActiveLearningQueueItem[];
};

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const method = init?.method ?? (init?.body ? "POST" : "GET");
  let res: Response;
  try {
    res = await fetch(API_URL + path, {
      method,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
      body: init?.body ? JSON.stringify(init.body) : undefined,
      signal: AbortSignal.timeout(method === "GET" ? 15_000 : 120_000), // training is a slow POST
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") throw new Error("The SIGNFORGE backend took too long to respond.");
    throw new Error(`Can't reach the SIGNFORGE backend at ${API_URL}. Check that it is running.`);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d: { loc: string[]; msg: string }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ")
      : res.status >= 500 ? `The backend hit an error (HTTP ${res.status}). Try again; if it repeats, check the backend log.`
      : `Request failed (HTTP ${res.status}).`;
    throw new Error(msg);
  }
  return data as T;
}

// Backend timestamps are UTC; SQLite drops the offset, Postgres keeps it.
export const when = (iso: string) => new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z").toLocaleString();

export type ClassMetrics = { precision: number; recall: number; f1: number; support: number };
export type ModelRun = {
  id: number; model_kind: "baseline" | "transfer"; pool: "real" | "demo"; status: "running" | "succeeded" | "failed";
  failure_detail: string; checkpoint_reference: string; feature_schema_version: string; preprocessing: Record<string, string | number>;
  data_version: string; split_strategy: string; train_sample_ids: number[]; test_sample_ids: number[]; seed: number;
  config: Record<string, string | number>; duration_s: number; created_at: string;
  metrics: { accuracy?: number | null; macro_f1?: number | null; macro_f1_over?: string; per_class?: Record<string, ClassMetrics>;
             confusion_matrix?: number[][]; labels?: number[]; n_test?: number; n_train?: number; train_classes?: number[] };
};
