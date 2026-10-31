import type { Queue, SignClass } from "./api";

// DEMO DATA only. Used while the backend has no /api/queue; every number here is invented to exercise the page, never shown without a badge.
// shortcut: remove this file when the real ranker endpoint is merged.
export function fixtureQueue(classes: SignClass[]): Queue {
  return {
    formula: "coverage_gap + signer_gap + uncertainty (each scaled 0 to 1)",
    uncertainty_available: false,
    items: classes.map((c, i) => {
      const coverage_gap = Math.max(0.1, 1 - i * 0.12), signer_gap = Math.max(0.1, 0.9 - i * 0.1);
      return { sign_id: c.id, gloss: c.gloss, priority: +(coverage_gap + signer_gap).toFixed(2), coverage_gap, signer_gap, uncertainty: null,
               reason: "Fixture row: the real ranker is not connected yet." };
    }).slice(0, 8),
  };
}
