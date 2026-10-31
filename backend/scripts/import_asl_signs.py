"""Convert Google's Kaggle "Isolated Sign Language Recognition" (asl-signs) landmarks into a SIGNFORGE manifest
that app.services.external_dataset.import_external_dataset_from_manifest imports, like the INCLUDE import.

Get the data first (needs a Kaggle account, accepting the competition rules on kaggle.com, and ~/.kaggle/kaggle.json):
  kaggle competitions download -c asl-signs -p data/raw/asl-signs && unzip -q data/raw/asl-signs/asl-signs.zip -d data/raw/asl-signs

Then, with pandas + pyarrow installed (not in requirements.txt: one-off tool):
  python import_asl_signs.py data/raw/asl-signs data/raw/asl-signs/features --signs 30 --per-sign 60

Expected layout (from the competition): train.csv with path, participant_id, sequence_id, sign; one parquet per sequence
with columns frame, row_id, type (face | left_hand | pose | right_hand), landmark_index, x, y, z (normalised, NaN = missing).
The face is dropped: SIGNFORGE stores body and hands only (mp-holistic-75-xyz-v1).
"""
import argparse, json
from pathlib import Path

import numpy as np
import pandas as pd

ASSUMED_FPS = 30.0  # the parquet files carry frame numbers, not timestamps; recorded in the manifest as an assumption
SLOTS = (("pose", 0, 33), ("left_hand", 33, 21), ("right_hand", 54, 21))


def convert(parquet: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = pd.read_parquet(parquet, columns=["frame", "type", "landmark_index", "x", "y", "z"])
    frames = np.sort(df["frame"].unique())
    pos = {f: i for i, f in enumerate(frames)}
    points = np.zeros((len(frames), 75, 3), np.float32)
    present = np.zeros((len(frames), 3), bool)
    for j, (kind, lo, n) in enumerate(SLOTS):
        part = df[df["type"] == kind]
        for f, g in part.groupby("frame"):
            xyz = g.sort_values("landmark_index")[["x", "y", "z"]].to_numpy(np.float32)
            if len(xyz) == n and not np.isnan(xyz[:, :2]).all():
                points[pos[f], lo:lo + n] = np.nan_to_num(xyz)
                present[pos[f], j] = True
    t = (frames - frames[0]).astype(np.float64) / ASSUMED_FPS
    return points, present, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--signs", type=int, default=30, help="how many signs (most frequent first)")
    ap.add_argument("--only", nargs="*", help="exact sign names to import instead of the most frequent")
    ap.add_argument("--per-sign", type=int, default=60, help="max clips per sign, spread over as many participants as possible")
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    (out / "features").mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(src / "train.csv")
    signs = a.only or meta["sign"].value_counts().index[: a.signs].tolist()
    samples = []
    for sign in signs:
        rows = meta[meta["sign"] == sign]
        # Round-robin over participants so each sign covers as many different signers as possible.
        rows = rows.assign(k=rows.groupby("participant_id").cumcount()).sort_values(["k", "participant_id"]).head(a.per_sign)
        for r in rows.itertuples():
            points, present, t = convert(src / r.path)
            if len(t) < 5:
                continue
            rel = f"features/{sign}_{r.sequence_id}.npz"
            np.savez_compressed(out / rel, points=points, present=present, t=t)
            samples.append({"gloss": sign.upper().replace(" ", "-"), "external_sample_id": f"P{r.participant_id}-S{r.sequence_id}",
                            "external_signer_id": str(r.participant_id), "external_split": "unassigned",
                            "feature_file": rel, "fps": ASSUMED_FPS, "width": 1080, "height": 1920})
    (out / "manifest.json").write_text(json.dumps({
        "dataset_name": "ASL-SIGNS", "dataset_version": "kaggle-asl-signs-2023", "license": "see Kaggle competition rules (asl-signs)",
        "citation": "Google, Isolated Sign Language Recognition (Kaggle, 2023), kaggle.com/competitions/asl-signs",
        "provenance_note": f"American Sign Language, not ISL. Landmarks as released (MediaPipe Holistic); face dropped; "
                           f"timestamps assume {ASSUMED_FPS:.0f} fps; frame size unknown (nominal 1080x1920)",
        "feature_schema_version": "mp-holistic-75-xyz-v1", "extractor": "MediaPipe Holistic (as released by Google/Kaggle)",
        "extractor_model_sha": "", "samples": samples}, indent=1))
    print(f"{len(samples)} clips of {len(signs)} signs -> {out / 'manifest.json'}")


if __name__ == "__main__":
    main()
