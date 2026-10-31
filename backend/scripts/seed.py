"""Seed the ISL demo project. Usage: python scripts/seed.py [--demo]

--demo also adds clearly labelled DEMO DATA samples (synthetic signers DEMO-01..03) as a webcam fallback
and so the demo model pool can be trained. Re-running only fills in what is missing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402  in-process, so seeding goes through API validation

from app.main import app  # noqa: E402

# Placeholder glosses: need confirmation by the team and a native ISL signer before real collection.
GLOSSES = ["HELLO", "THANK-YOU", "HELP", "EMERGENCY", "DOCTOR", "WATER", "FOOD", "PAIN", "YES", "NO"]
NOTE = "placeholder gloss; confirm with native ISL signer"
DEMO_SIGNERS, DEMO_PER_CLASS = 3, 3


def main(demo: bool):
    with TestClient(app) as c:
        projects = c.get("/api/projects").json()
        project = next((p for p in projects if p["name"] == "ISL demo"), None)
        if project is None:
            project = c.post("/api/projects", json={"name": "ISL demo", "target_language": "Indian Sign Language",
                                                    "domain": "everyday + emergency"}).json()
        pid = project["id"]
        existing = {s["gloss"] for s in c.get("/api/sign-classes", params={"project_id": pid}).json()}
        for g in GLOSSES:
            if g not in existing:
                c.post("/api/sign-classes", json={"project_id": pid, "gloss": g, "prompt_text": f"Sign: {g}",
                                                  "dialect_note": NOTE}).raise_for_status()
        classes = c.get("/api/sign-classes", params={"project_id": pid}).json()
        print(f"project {pid}: {len(classes)} sign classes")
        if not demo:
            return
        added = 0
        for k in range(DEMO_SIGNERS):
            signer = c.post("/api/signers", json={"project_id": pid, "code": f"DEMO-0{k + 1}"}).json()
            have = c.get("/api/samples", params={"project_id": pid, "signer_id": signer["id"], "include_demo": True}).json()
            consents = c.get("/api/consents", params={"signer_id": signer["id"]}).json()
            consent = consents[0] if consents else c.post("/api/consents", json={
                "signer_id": signer["id"], "consent_version": "demo-v1", "purpose": "DEMO DATA fixture (synthetic)",
                "allowed_uses": ["corpus_building"], "retention": "landmarks_only", "confirmed": True}).json()
            for i, sc in enumerate(classes):
                n_have = sum(x["sign_class_id"] == sc["id"] for x in have)
                for rep in range(n_have, DEMO_PER_CLASS):
                    d = c.get("/api/demo-frames", params={"class_index": i, "seed": 1 + rep + 100 * k}).json()
                    c.post("/api/samples/capture", json={
                        "project_id": pid, "sign_class_id": sc["id"], "signer_id": signer["id"], "consent_id": consent["id"],
                        "source": "demo_fixture", "extractor": d["extractor"], "fps": d["fps"], "width": d["width"],
                        "height": d["height"], "frames": d["frames"]}).raise_for_status()
                    added += 1
        print(f"added {added} DEMO DATA samples ({DEMO_SIGNERS} synthetic signers x {DEMO_PER_CLASS} per sign)")

if __name__ == "__main__":
    main("--demo" in sys.argv)
