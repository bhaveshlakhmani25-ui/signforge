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
        hello = next((s for s in samples if s["qc_passed"]), None)  # the landing plate takes the first HELLO that passed QC
        need_landmarks.update(s["id"] for s in samples if s["qc_passed"] and s["sign_class_id"] == (hello or {}).get("sign_class_id"))
    # Camera-free check: pre-read a pool of held-out clips per language; the page picks one at random.
    for L in langs:
        pool = {}
        for _ in range(60):
            r = c.post(f"/api/interpret/test-clip?project_id={L['project_id']}")
            if r.status_code == 200:
                pool[r.json()["sample_id"]] = r.json()
        put(f"/api/interpret/test-clip?project_id={L['project_id']}", list(pool.values()))
        need_landmarks.update(pool)
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
