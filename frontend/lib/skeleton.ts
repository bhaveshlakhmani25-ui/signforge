// Edges copied from @mediapipe/tasks-vision 1.1.0 (HolisticLandmarker.POSE_CONNECTIONS limited to face, arms and hands,
// i.e. landmarks 0-22; HAND_CONNECTIONS), so pages that only replay stored landmarks don't load the MediaPipe bundle.
// Hips/legs are left out: a seated webcam never sees them, MediaPipe extrapolates them, and the model doesn't use them.
const UPPER_BODY = [[0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],[11,12],[11,13],[13,15],[15,17],[15,19],[15,21],[17,19],[12,14],[14,16],[16,18],[16,20],[16,22],[18,20]];
const HAND = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[0,17],[17,18],[18,19],[19,20]];

export type Pt = { x: number; y: number };
export type SkeletonParts = { pose: Pt[] | null; left: Pt[] | null; right: Pt[] | null };
export const EMPTY: SkeletonParts = { pose: null, left: null, right: null };
const PARTS = [["pose", UPPER_BODY, "#c9c6f2"], ["left", HAND, "#5eead4"], ["right", HAND, "#fcd34d"]] as const;
const SMOOTHING = 0.5; // weight of the newest frame in the display moving average

/** Display-only smoothing so the skeleton doesn't jitter. Never applied to stored landmarks (model contract). */
export function smooth(prev: SkeletonParts, next: SkeletonParts): SkeletonParts {
  const one = (a: Pt[] | null, b: Pt[] | null) => {
    if (!b?.length) return null; // part lost: drop it rather than freeze a stale skeleton
    if (!a || a.length !== b.length) return b;
    return b.map((p, i) => ({ x: a[i].x + SMOOTHING * (p.x - a[i].x), y: a[i].y + SMOOTHING * (p.y - a[i].y) }));
  };
  return { pose: one(prev.pose, next.pose), left: one(prev.left, next.left), right: one(prev.right, next.right) };
}

/** Draws normalised (0-1) landmarks onto a canvas sized w×h. Teal = signer's left hand, amber = right. */
export function drawSkeleton(ctx: CanvasRenderingContext2D, w: number, h: number, parts: SkeletonParts, scale = 1) {
  ctx.lineCap = "round";
  for (const [key, edges, color] of PARTS) {
    const pts = parts[key];
    if (!pts) continue;
    ctx.strokeStyle = ctx.fillStyle = color;
    ctx.lineWidth = 3 * scale;
    ctx.beginPath();
    for (const [a, b] of edges) {
      ctx.moveTo(pts[a].x * w, pts[a].y * h);
      ctx.lineTo(pts[b].x * w, pts[b].y * h);
    }
    ctx.stroke();
    for (const p of key === "pose" ? pts.slice(0, 23) : pts) {
      ctx.beginPath();
      ctx.arc(p.x * w, p.y * h, 3 * scale, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
