// Checks the browser interpreter against readings from the real backend (golden.json, written by export_snapshot.py).
//   node deploy/pages/check_local_interpret.ts
import { readFileSync } from "node:fs";
import { interpretLocally, type Bundle } from "../../frontend/lib/localInterpret.ts";

const bundle: Bundle = JSON.parse(readFileSync(new URL("../../frontend/public/snapshot/interpret_models.json", import.meta.url), "utf8"));
const golden = JSON.parse(readFileSync(new URL("golden.json", import.meta.url), "utf8"));
let worst = 0, bad = 0;
for (const g of golden) {
  const got = interpretLocally(bundle, g.frames, g.project_id) as Record<string, any>, exp = g.expected;
  const diff = Math.max(...Object.keys(exp.probs ?? {}).map((k) => Math.abs(exp.probs[k] - got.probs?.[k])));
  worst = Math.max(worst, diff);
  if (got.state !== exp.state || got.sign !== exp.sign || !(diff < 2e-3)) { bad++; console.log("MISMATCH", exp.state, exp.sign, "->", got.state, got.sign, diff); }
}
console.log(`${golden.length - bad}/${golden.length} match the backend; largest probability difference ${worst.toExponential(1)}`);
process.exit(bad ? 1 : 0);
