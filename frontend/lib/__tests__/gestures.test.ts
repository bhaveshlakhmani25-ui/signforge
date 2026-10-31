// Run: node --experimental-strip-types lib/__tests__/gestures.test.ts
import assert from "node:assert/strict";
import { gestureOf } from "../gestures.ts";

// A synthetic right hand, palm facing the camera, wrist at the bottom (image y grows downwards).
// Each finger is either straight up from its knuckle or curled back toward the palm.
type P = { x: number; y: number; z: number };
function hand(ext: { thumb?: "up" | "down" | "side" | false; index?: boolean; middle?: boolean; ring?: boolean; pinky?: boolean; okTouch?: boolean }): P[] {
  const pts: P[] = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
  pts[0] = { x: 0.5, y: 0.8, z: 0 };
  const bases = { index: 0.44, middle: 0.5, ring: 0.56, pinky: 0.62 } as const;
  const ids = { index: [5, 6, 7, 8], middle: [9, 10, 11, 12], ring: [13, 14, 15, 16], pinky: [17, 18, 19, 20] } as const;
  for (const f of ["index", "middle", "ring", "pinky"] as const) {
    const x = bases[f], [mcp, pip, dip, tip] = ids[f];
    pts[mcp] = { x, y: 0.62, z: 0 };
    if (ext[f]) { pts[pip] = { x, y: 0.54, z: 0 }; pts[dip] = { x, y: 0.48, z: 0 }; pts[tip] = { x, y: 0.42, z: 0 }; }
    else { pts[pip] = { x, y: 0.56, z: 0 }; pts[dip] = { x, y: 0.62, z: 0 }; pts[tip] = { x, y: 0.66, z: 0 }; }
  }
  const t = ext.thumb;
  pts[1] = { x: 0.42, y: 0.74, z: 0 }; pts[2] = { x: 0.38, y: 0.68, z: 0 };
  if (t === "up") { pts[3] = { x: 0.36, y: 0.6, z: 0 }; pts[4] = { x: 0.35, y: 0.52, z: 0 }; }
  else if (t === "down") { pts[2] = { x: 0.38, y: 0.62, z: 0 }; pts[3] = { x: 0.36, y: 0.72, z: 0 }; pts[4] = { x: 0.35, y: 0.8, z: 0 }; }
  else if (t === "side") { pts[3] = { x: 0.32, y: 0.66, z: 0 }; pts[4] = { x: 0.26, y: 0.64, z: 0 }; }
  else { pts[3] = { x: 0.43, y: 0.64, z: 0 }; pts[4] = { x: 0.47, y: 0.63, z: 0 }; }
  if (ext.okTouch) { pts[4] = { x: 0.44, y: 0.5, z: 0 }; pts[8] = { x: 0.445, y: 0.5, z: 0 }; pts[6] = { x: 0.44, y: 0.55, z: 0 }; }
  return pts;
}
const id = (h: P[]) => gestureOf(h)?.id ?? null;

assert.equal(id(hand({ middle: true })), "middle");
assert.equal(id(hand({ thumb: "up" })), "thumbsUp");
assert.equal(id(hand({ thumb: "down" })), "thumbsDown");
assert.equal(id(hand({ index: true, middle: true })), "victory");
assert.equal(id(hand({ index: true })), "pointing");
assert.equal(id(hand({ thumb: "side", index: true, middle: true, ring: true, pinky: true })), "palm");
assert.equal(id(hand({})), "fist");
assert.equal(id(hand({ thumb: "side", index: true, pinky: true })), "ily");
assert.equal(id(hand({ okTouch: true, middle: true, ring: true, pinky: true })), "ok");
console.log("gestures: all 9 cases pass");
