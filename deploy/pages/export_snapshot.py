"""Freeze the PUBLIC-SAFE data (deploy/space/, built by deploy/hf-space/build_space.py) into static JSON for the GitHub Pages site.

GitHub Pages has no backend, so the Pages build reads these files instead of calling the API (NEXT_PUBLIC_SNAPSHOT=1).
Same safety rule as the hosted API: external datasets and DEMO DATA only, never a clip, signer, consent or review from the team.

  backend/.venv/bin/python deploy/pages/export_snapshot.py     # writes frontend/public/snapshot/, commit the result
"""
import json, os, re, shutil, sqlite3, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPACE, OUT = ROOT / "deploy" / "space", ROOT / "frontend" / "public" / "snapshot"
if not (SPACE / "signforge.db").exists():
    sys.exit("Run deploy/hf-space/build_space.py first: it builds the public-safe copy this reads.")

# Point the backend at the sanitized bundle, with its container paths rewritten to this checkout.
tmp = Path(tempfile.mkdtemp())
db = tmp / "signforge.db"
shutil.copy(SPACE / "signforge.db", db)
con = sqlite3.connect(db)
for table, col, old, new in (("sample", "feature_path", "/app/data/processed", SPACE / "data" / "processed"),
                             ("modelrun", "weights_path", "/app/checkpoints", SPACE / "checkpoints")):
    con.execute(f"UPDATE {table} SET {col} = ? || substr({col}, ?) WHERE {col} LIKE ?", (str(new), len(old) + 1, old + "%"))
con.commit(); con.close()
os.environ.update(DATABASE_URL=f"sqlite:///{db}", SIGNFORGE_DATA_DIR=str(SPACE / "data" / "processed"),
                  SIGNFORGE_CHECKPOINT_DIR=str(SPACE / "checkpoints"), SIGNFORGE_BENCHMARK_PATH=str(SPACE / "benchmark_results.json"))
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

key = lambda path: re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")  # must match snapshotKey() in frontend/lib/api.ts
shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
written = {}


def put(path, data):
    (OUT / f"{key(path)}.json").write_text(json.dumps(data, separators=(",", ":")))
    written[path] = data


with TestClient(app) as c:
    def get(path):
        r = c.get(path)
        if r.status_code == 200:
            put(path, r.json())
            return r.json()

    projects = get("/api/projects")
    langs = get("/api/interpret/languages")
    get("/api/benchmark"); get("/api/demo-frames?class_index=0&seed=1")
    need_landmarks = set()
    for p in projects:
        pid = p["id"]
        for path in (f"/api/sign-classes?project_id={pid}", f"/api/samples?project_id={pid}", f"/api/samples?project_id={pid}&include_demo=true",
                     f"/api/models/runs?project_id={pid}", f"/api/active-learning/queue?project_id={pid}"):
            get(path)
        for s in get(f"/api/signers?project_id={pid}") or []:
            get(f"/api/consents?signer_id={s['id']}")
        learn = get(f"/api/learn/signs?project_id={pid}")
        for sign in (learn or {})["signs"] if learn else []:
            need_landmarks.update(sign["examples"])
        samples = get(f"/api/samples?project_id={pid}") or []
        hello = {c["id"] for c in get(f"/api/sign-classes?project_id={pid}") if c["gloss"] == "HELLO"}
        plate = next((s for s in samples if s["sign_class_id"] in hello and s["qc_passed"]), None)  # same pick as Landing.tsx
        if plate:
            need_landmarks.add(plate["id"])
    # Camera-free check: pre-read a pool of held-out clips per language; the page picks one at random.
    for L in langs:
        pool = {}
        for _ in range(60):
            r = c.post(f"/api/interpret/test-clip?project_id={L['project_id']}")
            if r.status_code == 200:
                pool[r.json()["sample_id"]] = r.json()
        put(f"/api/interpret/test-clip?project_id={L['project_id']}", list(pool.values()))
        need_landmarks.update(pool)
    # Live camera without a backend: the interpreter's GRU weights + settings, run in the browser by frontend/lib/localInterpret.ts.
    import torch
    from app.core import config as C, thresholds as TH
    from app.db.models import ModelRun, Sample
    from app.services import landmark_schema as S
    from app.services.storage import load_features
    from sqlmodel import Session
    from app.db import engine
    models, golden = {}, []
    with Session(engine) as session:
        for L in langs:
            run = session.get(ModelRun, L["run_id"])
            sd = torch.load(run.weights_path)
            r6 = lambda t: [round(float(v), 6) for v in t.flatten()]
            m = run.metrics
            models[str(L["project_id"])] = {
                "run_id": run.id, "hidden": run.config["hidden"], "labels": m["labels"], "train_classes": m["train_classes"],
                "label_glosses": m["label_glosses"], "temperature": m["calibration"]["temperature"],
                "calibration_passed": m["calibration"]["reliability_passed"],
                "w_ih": r6(sd["gru.weight_ih_l0"]), "w_hh": r6(sd["gru.weight_hh_l0"]), "b_ih": r6(sd["gru.bias_ih_l0"]),
                "b_hh": r6(sd["gru.bias_hh_l0"]), "w_head": r6(sd["head.weight"]), "b_head": r6(sd["head.bias"])}
            # Reference readings from the real backend, for checking the browser port (kept out of the public site).
            parts = (("pose", S.POSE), ("left_hand", S.LEFT_HAND), ("right_hand", S.RIGHT_HAND))
            for sid in run.test_sample_ids[:8]:
                f = load_features(session.get(Sample, sid).feature_path)
                frames = [{"t": float(t), **{k: f["points"][i, sl].tolist() if f["present"][i, j] else None for j, (k, sl) in enumerate(parts)}}
                          for i, t in enumerate(f["t"])]
                for fr in frames:  # the API takes pose points as x,y,z,visibility
                    fr["pose"] = [[*pt, 1.0] for pt in fr["pose"]] if fr["pose"] else None
                body = {"frames": frames, "project_id": L["project_id"]}
                golden.append({**body, "expected": c.post("/api/interpret", json=body).json()})
        # Reference QC results for the browser port of run_qc (deploy/pages/check_local_interpret.ts), passing and failing clips.
        from sqlmodel import select
        from app.services.quality_checks import run_qc
        from app.services.preprocessing import frames_to_arrays
        qc_golden = []
        for passed in (True, False):
            for smp in session.exec(select(Sample).where(Sample.qc_passed == passed).order_by(Sample.id).limit(15)).all():
                f = load_features(smp.feature_path)
                frames = [{"t": float(t), **{k: ([[*pt, 1.0] for pt in f["points"][i, sl].tolist()] if k == "pose" else f["points"][i, sl].tolist())
                                             if f["present"][i, j] else None for j, (k, sl) in enumerate(parts)}} for i, t in enumerate(f["t"])]
                qc_golden.append({"frames": frames, "width": smp.width, "height": smp.height,
                                  "expected": run_qc(*frames_to_arrays(frames), smp.width, smp.height)})
        base = next(g for g in qc_golden if g["expected"]["passed"])  # altered copies reach the branches real clips miss
        for fn in (lambda fs: [{**f, "pose": None} if i % 2 else f for i, f in enumerate(fs)],                  # body_missing
                   lambda fs: [{**f, "left_hand": f["right_hand"], "right_hand": f["left_hand"]} for f in fs],   # hand_side_mismatch
                   lambda fs: [{**f, "t": f["t"] * 6} for f in fs]):                                           # too_long
            frames = fn(base["frames"])
            qc_golden.append({**base, "frames": frames, "expected": run_qc(*frames_to_arrays(frames), base["width"], base["height"])})
    put("/interpret/models", {"qc": {k: getattr(C, k) for k in dir(C) if k.startswith("QC_")},
                              "pose_l_wrist": S.POSE_L_WRIST, "pose_r_wrist": S.POSE_R_WRIST,
                              "verify_min_conf": TH.VERIFY_MIN_CONF, "verify_margin": TH.VERIFY_MARGIN,
                              "model_verify_enabled": TH.MODEL_VERIFY_ENABLED,"target_fps": C.TARGET_FPS, "model_frames": C.MODEL_FRAMES, "min_conf": TH.INTERPRET_MIN_CONF,
                              "min_hand_share": TH.INTERPRET_MIN_HAND_SHARE, "min_motion": TH.INTERPRET_MIN_MOTION,
                              "minimal_27": S.MINIMAL_27, "shoulder_nodes_27": list(S.SHOULDER_NODES_27),
                              "lh_wrist": S.LH_WRIST, "rh_wrist": S.RH_WRIST, "models": models})
    (ROOT / "deploy" / "pages" / "golden.json").write_text(json.dumps({"interpret": golden, "qc": qc_golden}))

    for sid in sorted(need_landmarks):
        r = c.get(f"/api/samples/{sid}/landmarks")
        if r.status_code == 200:
            d = r.json()
            d["frames"] = [{k: ([[round(v, 3) for v in pt] for pt in pts] if pts else None) for k, pts in f.items()} for f in d["frames"]]
            put(f"/api/samples/{sid}/landmarks", d)

# Safety net: nothing recorded by the team may appear anywhere in the snapshot.
blob = " ".join(p.read_text() for p in OUT.glob("*.json"))
assert '"source":"captured"' not in blob and "reviewer_code" not in blob, "snapshot contains non-public data"
size = sum(p.stat().st_size for p in OUT.glob("*.json"))
print(f"{len(written)} files, {size/1e6:.1f} MB -> {OUT}")
