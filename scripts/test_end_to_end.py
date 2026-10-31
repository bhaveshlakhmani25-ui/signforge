"""
Comprehensive End-to-End Acceptance Test Script for SIGNFORGE.
Validates the complete 6-stage lifecycle:
1. Dataset Loading (INCLUDE Dates & Time + Projects + Classes)
2. Corpus Display (Real vs Demo samples separation, Replay API)
3. Consented Capture (Signer -> Consent -> Pose/Hand Capture -> Technical QC)
4. Human Review (ReviewEvent with Deaf/Native role tag)
5. Active Learning Ranking (/api/queue)
6. Model-Ready Export (/api/export downloadable ZIP)
"""

import json
import urllib.request
import urllib.error
import zipfile
import io
import sys

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def run_tests():
    print("=" * 80)
    print("SIGNFORGE END-TO-END ACCEPTANCE TESTING")
    print("=" * 80)
    results = {}

    # 1. Dataset Loading
    print("\n[Step 1] Testing Dataset Loading & Metadata API...")
    try:
        p_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/projects").read())
        project = p_res[0]
        pid = project["id"]
        
        sc_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/sign-classes?project_id={pid}").read())
        s_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/samples?project_id={pid}&include_demo=true").read())
        
        real_samples = [s for s in s_res if s["source"] != "demo_fixture"]
        demo_samples = [s for s in s_res if s["source"] == "demo_fixture"]
        
        print(f"  [+] Project: '{project['name']}' (ID: {pid})")
        print(f"  [+] Sign Classes: {len(sc_res)} total classes")
        print(f"  [+] Total Samples in DB: {len(s_res)} (Real: {len(real_samples)}, Demo: {len(demo_samples)})")
        results["1_dataset_loading"] = {
            "status": "PASSED",
            "project_id": pid,
            "classes_count": len(sc_res),
            "real_samples_count": len(real_samples),
            "demo_samples_count": len(demo_samples)
        }
    except Exception as e:
        print(f"  [-] Failed Step 1: {e}")
        results["1_dataset_loading"] = {"status": "FAILED", "error": str(e)}

    # 2. Corpus Display & Replay API
    print("\n[Step 2] Testing Corpus Display & Landmark Replay...")
    try:
        # Check frontend page status
        fe_res = urllib.request.urlopen(f"{FRONTEND_URL}/corpus", timeout=10)
        print(f"  [+] Frontend /corpus HTTP Status: {fe_res.status}")
        
        # Test landmark replay for sample 92 (first INCLUDE sample)
        replay_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/samples/92/landmarks").read())
        print(f"  [+] Replay API: sample_id={replay_res['sample_id']}, source={replay_res['source']}, frames={len(replay_res['frames'])}, fps={replay_res['fps']}")
        results["2_corpus_display"] = {
            "status": "PASSED",
            "frontend_status": fe_res.status,
            "sample_replay_id": replay_res["sample_id"],
            "replay_frames": len(replay_res["frames"])
        }
    except Exception as e:
        print(f"  [-] Failed Step 2: {e}")
        results["2_corpus_display"] = {"status": "FAILED", "error": str(e)}

    # 3. Consented Capture Flow
    print("\n[Step 3] Testing Consented Capture Flow...")
    try:
        # Step 3a: Create Signer
        signer_payload = json.dumps({"project_id": pid, "code": "TEST-S01", "handedness": "right"}).encode("utf-8")
        req_signer = urllib.request.Request(f"{BASE_URL}/api/signers", data=signer_payload, headers={"Content-Type": "application/json"})
        signer = json.loads(urllib.request.urlopen(req_signer).read())
        print(f"  [+] Created test signer: ID={signer['id']}, Code={signer['code']}")
        
        # Step 3b: Create Consent Record
        consent_payload = json.dumps({
            "signer_id": signer["id"],
            "consent_version": "v1.0-test",
            "purpose": "End-to-End Acceptance Verification",
            "allowed_uses": ["corpus_building", "model_training"],
            "retention": "landmarks_only",
            "confirmed": True
        }).encode("utf-8")
        req_consent = urllib.request.Request(f"{BASE_URL}/api/consents", data=consent_payload, headers={"Content-Type": "application/json"})
        consent = json.loads(urllib.request.urlopen(req_consent).read())
        print(f"  [+] Recorded consent: ID={consent['id']}, Status={consent['status']}")
        
        # Step 3c: Capture Sample (using demo-frames endpoint for realistic motion sequence)
        frames_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/demo-frames?class_index=0&seed=999").read())
        capture_payload = json.dumps({
            "project_id": pid,
            "sign_class_id": sc_res[0]["id"],
            "signer_id": signer["id"],
            "consent_id": consent["id"],
            "source": "captured",
            "extractor": frames_res["extractor"],
            "extractor_model_sha": "mediapipe-test-sha",
            "fps": frames_res["fps"],
            "width": frames_res["width"],
            "height": frames_res["height"],
            "frames": frames_res["frames"]
        }).encode("utf-8")
        req_capture = urllib.request.Request(f"{BASE_URL}/api/samples/capture", data=capture_payload, headers={"Content-Type": "application/json"})
        sample = json.loads(urllib.request.urlopen(req_capture).read())
        print(f"  [+] Captured sample: ID={sample['id']}, SignClass={sample['sign_class_id']}, QC_Passed={sample['qc_passed']}")
        results["3_capture"] = {
            "status": "PASSED",
            "signer_id": signer["id"],
            "consent_id": consent["id"],
            "sample_id": sample["id"],
            "qc_passed": sample["qc_passed"]
        }
    except Exception as e:
        print(f"  [-] Failed Step 3: {e}")
        results["3_capture"] = {"status": "FAILED", "error": str(e)}

    # 4. Human Review Flow
    print("\n[Step 4] Testing Human Review Workflow...")
    try:
        sample_to_review = results.get("3_capture", {}).get("sample_id", 92)
        review_payload = json.dumps({
            "reviewer_code": "REV-AKARSHI",
            "reviewer_role": "native_signer",
            "decision": "approved",
            "note": "Verified natural ISL gesture execution during QA acceptance pass."
        }).encode("utf-8")
        req_review = urllib.request.Request(f"{BASE_URL}/api/samples/{sample_to_review}/review", data=review_payload, headers={"Content-Type": "application/json"})
        reviewed_sample = json.loads(urllib.request.urlopen(req_review).read())
        print(f"  [+] Review submitted: sample_id={reviewed_sample['id']}, review_status={reviewed_sample['review_status']}")
        
        # Verify review event logged
        events = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/samples/{sample_to_review}/reviews").read())
        print(f"  [+] Review events logged: {len(events)} event(s) -> Role: {events[-1]['reviewer_role']}")
        results["4_review"] = {
            "status": "PASSED",
            "sample_id": sample_to_review,
            "decision": reviewed_sample["review_status"],
            "reviewer_role": events[-1]["reviewer_role"]
        }
    except Exception as e:
        print(f"  [-] Failed Step 4: {e}")
        results["4_review"] = {"status": "FAILED", "error": str(e)}

    # 5. Active Learning Ranking
    print("\n[Step 5] Testing Active Learning Ranker...")
    try:
        q_res = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/queue?project_id={pid}").read())
        items = q_res["items"]
        top_item = items[0]
        bottom_item = items[-1]
        print(f"  [+] Queue Formula: {q_res['formula']}")
        print(f"  [+] Total Ranked Classes: {len(items)}")
        print(f"  [+] #1 Ranked Need: {top_item['gloss']} (Priority: {top_item['priority']}, Reason: {top_item['reason']})")
        print(f"  [+] Lowest Need (Well Covered): {bottom_item['gloss']} (Priority: {bottom_item['priority']}, Reason: {bottom_item['reason']})")
        results["5_ranking"] = {
            "status": "PASSED",
            "total_ranked": len(items),
            "top_sign": top_item["gloss"],
            "top_priority": top_item["priority"],
            "bottom_sign": bottom_item["gloss"],
            "bottom_priority": bottom_item["priority"]
        }
    except Exception as e:
        print(f"  [-] Failed Step 5: {e}")
        results["5_ranking"] = {"status": "FAILED", "error": str(e)}

    # 6. Export Functionality
    print("\n[Step 6] Testing Model-Ready Export...")
    try:
        export_url = f"{BASE_URL}/api/export?project_id={pid}&approved_only=true&include_demo=false"
        with urllib.request.urlopen(export_url) as res:
            zip_bytes = res.read()
            status = res.status
            disposition = res.headers.get("Content-Disposition")
            
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
            names = z.namelist()
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            provenance = z.read("provenance.md").decode("utf-8")
            landmarks = [n for n in names if n.startswith("landmarks/")]
            
        print(f"  [+] Export HTTP Status: {status}")
        print(f"  [+] Disposition: {disposition}")
        print(f"  [+] Total Archive Size: {len(zip_bytes)} bytes ({len(zip_bytes)/(1024*1024):.2f} MB)")
        print(f"  [+] Manifest Samples: {manifest['n_samples']} samples across {manifest['n_classes']} classes")
        print(f"  [+] Packaged Landmarks: {len(landmarks)} .npz files")
        print(f"  [+] Provenance Header: {provenance.splitlines()[0]}")
        results["6_export"] = {
            "status": "PASSED",
            "archive_size_bytes": len(zip_bytes),
            "n_samples": manifest["n_samples"],
            "n_classes": manifest["n_classes"],
            "n_landmarks": len(landmarks),
            "has_provenance": "INCLUDE" in provenance or "ISL demo" in provenance
        }
    except Exception as e:
        print(f"  [-] Failed Step 6: {e}")
        results["6_export"] = {"status": "FAILED", "error": str(e)}

    print("\n" + "=" * 80)
    print("END-TO-END TEST SUMMARY")
    print("=" * 80)
    all_passed = True
    for step, res in sorted(results.items()):
        status = res.get("status")
        print(f"{step.upper():<25}: {status}")
        if status != "PASSED": all_passed = False
    print("=" * 80)
    print(f"OVERALL STATUS: {'ALL PASSED (100%)' if all_passed else 'SOME STEPS FAILED'}")

    return results

if __name__ == "__main__":
    run_tests()
