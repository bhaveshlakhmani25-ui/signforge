"""Extract selected signs from INCLUDE Days_and_Time_3of3.zip and extract landmarks.

Author: Aakarshi Dwivedi (Data & QA)
Target Schema: mp-holistic-75-xyz-v1 (33 pose + 21 left hand + 21 right hand)
"""

import os
import zipfile
import json
import cv2
import numpy as np
import mediapipe as mp
from pathlib import Path

ZIP_PATH = r"C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_3of3.zip"
OUTPUT_BASE = Path(r"dataset/INCLUDE/Dates_and_Time")
VIDEOS_DIR = OUTPUT_BASE / "videos"
LANDMARKS_DIR = OUTPUT_BASE / "landmarks"

# Clean gloss names
SIGNS = [
    ("81. Second", "SECOND"),
    ("82. Morning", "MORNING"),
    ("83. Afternoon", "AFTERNOON"),
    ("84. Evening", "EVENING"),
    ("85. Night", "NIGHT"),
    ("86. Time", "TIME"),
]


def extract_landmarks_from_video(video_path: Path, holistic) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int, float]:
    cap = cv2.VideoCapture(str(video_path))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    frames_points = []
    frames_present = []
    timestamps = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = holistic.process(rgb)

        points = np.zeros((75, 3), dtype=np.float32)
        present = np.zeros(3, dtype=bool)

        # Pose (0..32)
        if res.pose_landmarks:
            present[0] = True
            for i, lm in enumerate(res.pose_landmarks.landmark):
                if i < 33:
                    points[i] = [lm.x, lm.y, lm.z]

        # Left hand (33..53)
        if res.left_hand_landmarks:
            present[1] = True
            for i, lm in enumerate(res.left_hand_landmarks.landmark):
                if i < 21:
                    points[33 + i] = [lm.x, lm.y, lm.z]

        # Right hand (54..74)
        if res.right_hand_landmarks:
            present[2] = True
            for i, lm in enumerate(res.right_hand_landmarks.landmark):
                if i < 21:
                    points[54 + i] = [lm.x, lm.y, lm.z]

        frames_points.append(points)
        frames_present.append(present)
        timestamps.append(frame_idx / fps)
        frame_idx += 1

    cap.release()

    points_arr = np.array(frames_points, dtype=np.float32) if frames_points else np.zeros((0, 75, 3), dtype=np.float32)
    present_arr = np.array(frames_present, dtype=bool) if frames_present else np.zeros((0, 3), dtype=bool)
    t_arr = np.array(timestamps, dtype=np.float64) if timestamps else np.zeros((0,), dtype=np.float64)

    return points_arr, present_arr, t_arr, width, height, fps


def main():
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    LANDMARKS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading from {ZIP_PATH}...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        all_files = z.namelist()

        # Find 3 videos for each of the 6 signs
        selected_files = []
        for folder_name, gloss in SIGNS:
            vids = [f for f in all_files if f.startswith(f"Days_and_Time/{folder_name}/") and (f.endswith(".mp4") or f.endswith(".MOV") or f.endswith(".MP4"))]
            selected = vids[:3]  # take first 3 clips
            for s in selected:
                selected_files.append((s, gloss))

        print(f"Extracting {len(selected_files)} selected videos...")
        manifest_signs = []
        mp_holistic = mp.solutions.holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        for idx, (zip_entry, gloss) in enumerate(selected_files, start=1):
            sign_id = f"DT_{idx:03d}"
            orig_filename = os.path.basename(zip_entry)
            target_video_name = f"{sign_id}_{orig_filename}"
            target_video_path = VIDEOS_DIR / target_video_name

            # Extract video if not present
            if not target_video_path.exists():
                with z.open(zip_entry) as src, open(target_video_path, "wb") as dst:
                    dst.write(src.read())

            # Extract landmarks
            target_lm_name = f"{sign_id}.npz"
            target_lm_path = LANDMARKS_DIR / target_lm_name

            print(f"[{idx}/{len(selected_files)}] Processing {gloss} ({target_video_name})...")
            points, present, t, width, height, fps = extract_landmarks_from_video(target_video_path, mp_holistic)

            # Save landmarks in canonical format
            np.savez_compressed(target_lm_path, points=points, present=present, t=t)

            has_pose = bool(present[:, 0].any()) if len(present) else False
            has_hand = bool((present[:, 1] | present[:, 2]).any()) if len(present) else False

            manifest_signs.append({
                "sign_id": sign_id,
                "label": gloss,
                "gloss": gloss,
                "signer_id": f"INCLUDE-S{(idx % 4) + 1:02d}",
                "video_file": f"videos/{target_video_name}",
                "landmark_file": f"landmarks/{target_lm_name}",
                "fps": float(fps),
                "width": width,
                "height": height,
                "num_frames": len(t),
                "qc_passed": has_pose and has_hand and len(t) >= 10,
                "status": "processed",
            })

        mp_holistic.close()

    manifest = {
        "dataset": "INCLUDE",
        "category": "Dates and Time",
        "schema_version": "mp-holistic-75-xyz-v1",
        "n_signs": len(manifest_signs),
        "classes": sorted(list(set(s["gloss"] for s in manifest_signs))),
        "signs": manifest_signs,
    }

    manifest_path = OUTPUT_BASE / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSuccessfully generated {manifest['n_signs']} landmark files!")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
