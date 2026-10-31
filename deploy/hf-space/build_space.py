"""Assemble a Hugging Face Space folder (deploy/space/) holding the backend plus a PUBLIC-SAFE copy of the data.

Kept: external datasets (INCLUDE, ASL) and labelled DEMO DATA, with the models trained on them.
Left out: every clip recorded by the team (source "captured"), their signers, consents and review records, and any model run that
used them. The hosted API has no login, so nothing a person contributed may be in it.

  python deploy/hf-space/build_space.py          # then see deploy/hf-space/README.md
"""
import shutil, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DB, SRC_CKPT = ROOT / "backend" / "signforge.db", ROOT / "backend" / "checkpoints"
OUT = ROOT / "deploy" / "space"
PUBLIC_SOURCES = ("external_dataset", "demo_fixture")

if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "data" / "processed").mkdir(parents=True)
(OUT / "checkpoints").mkdir()
shutil.copytree(ROOT / "backend" / "app", OUT / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copy(ROOT / "backend" / "requirements.txt", OUT / "requirements.txt")
for f in ("Dockerfile", "README.md"):
    shutil.copy(Path(__file__).parent / f, OUT / f)

db = OUT / "signforge.db"
shutil.copy(SRC_DB, db)
con = sqlite3.connect(db)
q = lambda sql, *a: con.execute(sql, a).fetchall()
marks = ",".join("?" * len(PUBLIC_SOURCES))

con.execute("DELETE FROM reviewevent")  # reviewer codes belong to the team; a sample keeps its review status without them
con.execute(f"DELETE FROM sample WHERE source NOT IN ({marks})", PUBLIC_SOURCES)
con.execute("DELETE FROM consentrecord WHERE id NOT IN (SELECT consent_id FROM sample)")
con.execute("DELETE FROM signer WHERE id NOT IN (SELECT signer_id FROM sample)")
# Runs that trained on real (team) clips are dropped; demo and external runs only saw public data.
con.execute("DELETE FROM modelrun WHERE pool NOT IN ('demo', 'external')")

kept = 0
for sid, pid, path in q("SELECT id, project_id, feature_path FROM sample"):
    rel = Path(path).as_posix().split("data/processed/")[-1]
    src = ROOT / "data" / "processed" / rel
    (OUT / "data" / "processed" / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, OUT / "data" / "processed" / rel)
    con.execute("UPDATE sample SET feature_path=? WHERE id=?", (f"/app/data/processed/{rel}", sid))
    kept += 1
for rid, w in q("SELECT id, weights_path FROM modelrun"):
    shutil.copy(SRC_CKPT / Path(w).name, OUT / "checkpoints" / Path(w).name)
    con.execute("UPDATE modelrun SET weights_path=? WHERE id=?", (f"/app/checkpoints/{Path(w).name}", rid))
con.commit()

print("projects:", q("SELECT id, name FROM project"))
print("samples by source:", q("SELECT source, count(*) FROM sample GROUP BY source"))
print("signers:", q("SELECT count(*) FROM signer")[0][0], "| consents:", q("SELECT count(*) FROM consentrecord")[0][0],
      "| model runs:", q("SELECT id, pool FROM modelrun"))
assert not q("SELECT 1 FROM sample WHERE source NOT IN ('external_dataset','demo_fixture')")
con.execute("VACUUM")
con.close()
print(f"{kept} feature files copied -> {OUT}")
