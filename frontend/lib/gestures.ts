/** Rule-based hand gestures and facial-expression cues, read from MediaPipe landmarks every frame.
 *  These are everyday gestures, not ISL/ASL vocabulary: they are shown separately from the sign model's reading. */
import type { HolisticLandmarkerResult, NormalizedLandmark } from "@mediapipe/tasks-vision";

export type Gesture = { id: string; label: string; meaning: string; tone: "neutral" | "positive" | "negative" | "offensive" };

const G: Record<string, Gesture> = {
  middle: { id: "middle", label: "Middle finger", meaning: "Offensive gesture: an insult in India, the US and most other places.", tone: "offensive" },
  thumbsUp: { id: "thumbsUp", label: "Thumbs up", meaning: "Approval: good, yes, OK.", tone: "positive" },
  thumbsDown: { id: "thumbsDown", label: "Thumbs down", meaning: "Disapproval: bad, no.", tone: "negative" },
  ok: { id: "ok", label: "OK sign", meaning: "OK or fine in most places (offensive in some countries).", tone: "positive" },
  victory: { id: "victory", label: "Victory / peace", meaning: "Peace or victory. Two fingers also mean the number 2.", tone: "positive" },
  pointing: { id: "pointing", label: "Pointing", meaning: "Pointing at someone or something; in ISL and ASL pointing also works as a pronoun (you, he, she, it).", tone: "neutral" },
  ily: { id: "ily", label: "I love you", meaning: "ASL handshape for I love you, widely understood in Deaf communities.", tone: "positive" },
  palm: { id: "palm", label: "Open palm", meaning: "Open hand: stop, wait or hello, depending on movement.", tone: "neutral" },
  fist: { id: "fist", label: "Closed fist", meaning: "Closed fist: can mean anger, strength or the start of many signs.", tone: "neutral" },
};

const d = (a: NormalizedLandmark, b: NormalizedLandmark) => Math.hypot(a.x - b.x, a.y - b.y);

/** Which fingers are extended: a fingertip clearly further from the wrist than its middle joint. */
function fingers(h: NormalizedLandmark[]) {
  const w = h[0], palm = d(h[0], h[9]) || 1e-6;
  const ext = (tip: number, pip: number) => d(h[tip], w) > d(h[pip], w) * 1.15;
  return {
    thumb: d(h[4], h[5]) > 0.55 * palm && d(h[4], h[17]) > d(h[3], h[17]),
    index: ext(8, 6), middle: ext(12, 10), ring: ext(16, 14), pinky: ext(20, 18), palm,
  };
}

export function gestureOf(h: NormalizedLandmark[]): Gesture | null {
  const f = fingers(h);
  const { thumb, index, middle, ring, pinky } = f;
  if (middle && !index && !ring && !pinky) return G.middle;
  if (d(h[4], h[8]) < 0.3 * f.palm && middle && ring && pinky) return G.ok;
  if (thumb && !index && !middle && !ring && !pinky) {
    const up = h[4].y < h[2].y - 0.35 * f.palm, down = h[4].y > h[2].y + 0.35 * f.palm; // image y grows downwards
    return up ? G.thumbsUp : down ? G.thumbsDown : null;
  }
  if (thumb && index && pinky && !middle && !ring) return G.ily;
  if (index && middle && !ring && !pinky) return G.victory;
  if (index && !middle && !ring && !pinky) return G.pointing;
  if (index && middle && ring && pinky) return G.palm;
  if (!index && !middle && !ring && !pinky) return G.fist;
  return null;
}

/** Holds a gesture only once it has been seen in most of the recent frames, so passing handshapes mid-sign don't flicker. */
export class GestureFilter {
  private recent: (string | null)[] = [];
  private size = 10; // frames considered
  private need = 7; // frames that must agree
  push(r: HolisticLandmarkerResult): Gesture | null {
    const hands = [r.rightHandLandmarks[0], r.leftHandLandmarks[0]].filter(Boolean) as NormalizedLandmark[][];
    const g = hands.map(gestureOf).find((x) => x && x.tone === "offensive") ?? hands.map(gestureOf).find(Boolean) ?? null;
    this.recent.push(g?.id ?? null);
    if (this.recent.length > this.size) this.recent.shift();
    const counts = new Map<string, number>();
    for (const id of this.recent) if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
    const [best, n] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? [null, 0];
    return best && n >= this.need ? G[best] : null;
  }
}

export type Expression = { label: string; note?: string };

/** Facial cues from MediaPipe blendshapes. In sign languages these are grammar (e.g. raised brows on a yes/no question),
 *  so they are reported as cues, never as a verdict on someone's mood. */
export function expressionOf(r: HolisticLandmarkerResult): Expression | null {
  const cats = r.faceBlendshapes?.[0]?.categories;
  if (!cats?.length) return null;
  const s = (name: string) => cats.find((c) => c.categoryName === name)?.score ?? 0;
  const avg = (...n: string[]) => n.reduce((a, k) => a + s(k), 0) / n.length;
  const smile = avg("mouthSmileLeft", "mouthSmileRight"), frown = avg("mouthFrownLeft", "mouthFrownRight");
  const browsDown = avg("browDownLeft", "browDownRight"), browsUp = Math.max(s("browInnerUp"), avg("browOuterUpLeft", "browOuterUpRight"));
  if (smile > 0.5) return { label: "Smiling" };
  if (browsUp > 0.5) return { label: "Brows raised", note: "In ISL and ASL this often marks a yes/no question, or surprise." };
  if (browsDown > 0.45 || frown > 0.35) return { label: "Brows lowered / frowning", note: "Often marks a wh- question (what, where, who), or displeasure." };
  if (s("jawOpen") > 0.5) return { label: "Mouth open" };
  return { label: "Neutral" };
}
