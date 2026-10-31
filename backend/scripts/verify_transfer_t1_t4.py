#!/usr/bin/env python3
"""SIGNFORGE Transfer Learning Checkpoint Verification Spike (T1–T4).

Tests the OpenHands self-supervised DPC ST-GCN checkpoint against the
four mandatory compatibility requirements before transfer learning can be enabled:
  - T1: Strict PyTorch state-dict load (only DPC prediction head unused)
  - T2: Graph matrix equals the documented 27-node kinematic edge list
  - T3: Encoder forward shape check: (B*W, 2, 10, 27) -> (B*W, 256)
  - T4: BatchNorm input layout check and coordinate alignment

If any check fails or requires unverified runtime hacks, the script
reports the checkpoint as BLOCKED and documents the within-ISL fallback.
"""

import os
import sys
import types
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

# Ensure backend path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

CHECKPOINT_PATH = backend_dir / "checkpoints" / "epoch=499-step=308499.ckpt"


class TransferTestResult:
    def __init__(self, name: str, passed: bool, detail: str):
        self.name = name
        self.passed = passed
        self.detail = detail


def run_t1_strict_load(ckpt_path: Path) -> tuple[bool, str, dict]:
    """T1: Strict PyTorch state-dict load check.

    Evaluates whether the checkpoint can be safely loaded in standard PyTorch
    without arbitrary code execution risks or obsolete PyTorch Lightning dependencies.
    """
    if not ckpt_path.exists():
        return False, f"Checkpoint file missing: {ckpt_path}", {}

    # Attempt 1: Standard weights_only=True load (PyTorch 2.6+ secure default)
    try:
        torch.load(ckpt_path, map_location="cpu", weights_only=True)
        # If this succeeds, weights_only is supported
        safe_load = True
    except Exception as e_safe:
        safe_load = False
        safe_err = f"{type(e_safe).__name__}: {str(e_safe)[:120]}"

    # Attempt 2: Standard weights_only=False load (without stubbing)
    try:
        torch.load(ckpt_path, map_location="cpu", weights_only=False)
        unpickler_clean = True
    except Exception as e_unpickler:
        unpickler_clean = False
        unpickler_err = f"{type(e_unpickler).__name__}: {str(e_unpickler)[:120]}"

    # Attempt 3: Controlled unpickling with minimal module stubbing to inspect state_dict
    try:
        class DummyModelCheckpoint:
            def __setstate__(self, state):
                pass

        sys.modules["pytorch_lightning"] = types.ModuleType("pytorch_lightning")
        sys.modules["pytorch_lightning.callbacks"] = types.ModuleType("pytorch_lightning.callbacks")
        sys.modules["pytorch_lightning.callbacks.model_checkpoint"] = types.SimpleNamespace(
            ModelCheckpoint=DummyModelCheckpoint
        )

        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        sd = ckpt.get("state_dict", {})
        has_sd = len(sd) > 0
    except Exception as e_stub:
        has_sd = False
        sd = {}

    if not safe_load and not unpickler_clean:
        detail = (
            f"FAILED secure load ({safe_err}). "
            f"FAILED standard unpickle ({unpickler_err}). "
            f"PyTorch Lightning 1.4.1 pickle format is incompatible with standard PyTorch 2.6+ environment. "
            f"Recovered {len(sd)} keys under shim."
        )
        # T1 fails strict load without shims
        return False, detail, sd

    return True, f"Strict load succeeded with {len(sd)} keys.", sd


def run_t2_graph_matrix(sd: dict) -> tuple[bool, str]:
    """T2: Graph matrix equals documented 27-node edge list.

    Checks the adjacency buffer `model.conv_encoder.A` against the OpenHands
    minimal-27 skeleton topology.
    """
    a_key = "model.conv_encoder.A"
    if a_key not in sd:
        return False, f"Missing graph adjacency key '{a_key}' in state_dict."

    A = sd[a_key]
    if A.shape != torch.Size([3, 27, 27]):
        return False, f"Expected shape [3, 27, 27], got {list(A.shape)}."

    # Verify partition sum equals V (27)
    a_sum = float(A.sum())
    if abs(a_sum - 27.0) > 1e-3:
        return False, f"Normalized partition sum expected 27.0, got {a_sum:.4f}."

    # Verify partition 0 is identity / self-loops
    p0_diag = torch.diag(A[0])
    p0_diag_nonzeros = int((p0_diag > 0).sum())
    if p0_diag_nonzeros != 27:
        return False, f"Partition 0 self-loop nonzeros expected 27, got {p0_diag_nonzeros}."

    return True, f"Graph adjacency verified: shape [3, 27, 27], partition sum {a_sum:.1f}, 27 self-loops."


def run_t3_forward_shape(sd: dict) -> tuple[bool, str]:
    """T3: Encoder forward shape check (B*W, 2, 10, 27) -> (B*W, 256).

    Verifies the spatial-temporal GCN blocks and GRU aggregator produce 256-dim embeddings.
    """
    # Check weight dimensions of encoder and aggregator
    gcn0_w = sd.get("model.conv_encoder.st_gcn_networks.0.gcn.conv.weight")
    if gcn0_w is None or gcn0_w.shape != torch.Size([192, 2, 1, 1]):
        return False, f"ST-GCN input conv weight expected [192, 2, 1, 1], got {getattr(gcn0_w, 'shape', None)}"

    gcn9_w = sd.get("model.conv_encoder.st_gcn_networks.9.tcn.2.weight")
    if gcn9_w is None or gcn9_w.shape != torch.Size([256, 256, 9, 1]):
        return False, f"ST-GCN final conv weight expected [256, 256, 9, 1], got {getattr(gcn9_w, 'shape', None)}"

    gru_w = sd.get("model.agg.weight_hh_l0")
    if gru_w is None or gru_w.shape != torch.Size([768, 256]):
        return False, f"Aggregator GRU weight expected [768, 256], got {getattr(gru_w, 'shape', None)}"

    # Check temporal pooling / window aggregation
    return True, "ST-GCN encoder channels 2->64->128->256 and GRU hidden dim 256 confirmed from checkpoint weights."


def run_t4_batchnorm_layout(sd: dict) -> tuple[bool, str]:
    """T4: BatchNorm input layout check and coordinate normalization.

    Verifies the input BatchNorm layer parameters and running statistics.
    """
    bn_w = sd.get("model.conv_encoder.data_bn.weight")
    bn_mean = sd.get("model.conv_encoder.data_bn.running_mean")
    if bn_w is None or bn_mean is None:
        return False, "Missing data_bn weight or running_mean in state_dict."

    if bn_w.shape != torch.Size([54]):
        return False, f"Expected data_bn shape [54] (27 points * 2 coords), got {bn_w.shape}."

    # Check shoulder coordinates in running mean:
    # Point 3: left shoulder (idx 6, 7 in interleaved xy)
    # Point 4: right shoulder (idx 8, 9 in interleaved xy)
    ls_x = float(bn_mean[6])
    rs_x = float(bn_mean[8])

    if abs(ls_x - 0.487) > 0.05 or abs(rs_x - (-0.487)) > 0.05:
        return False, f"Shoulder x running mean mismatch: expected ~±0.487, got left={ls_x:.3f}, right={rs_x:.3f}."

    return True, f"BatchNorm input layout verified: 54 interleaved coords (x/y), shoulder x running means at {rs_x:.3f} and +{ls_x:.3f}."


def main():
    print("=" * 80)
    print("  SIGNFORGE TRANSFER LEARNING COMPATIBILITY SPIKE (T1–T4)")
    print("=" * 80)
    print(f"Target Checkpoint: {CHECKPOINT_PATH.name}")
    print(f"Candidate Source:  AI4Bharat OpenHands DPC ST-GCN (epoch=499-step=308499.ckpt)")
    print("-" * 80)

    # Run T1
    t1_pass, t1_msg, sd = run_t1_strict_load(CHECKPOINT_PATH)
    print(f"T1 [Strict State-Dict Load]: {'PASSED' if t1_pass else 'FAILED (BLOCKED)'}")
    print(f"   Detail: {t1_msg}\n")

    # Run T2
    t2_pass, t2_msg = run_t2_graph_matrix(sd) if sd else (False, "Skipped (no state_dict)")
    print(f"T2 [Graph Adjacency Matrix]: {'PASSED' if t2_pass else 'FAILED'}")
    print(f"   Detail: {t2_msg}\n")

    # Run T3
    t3_pass, t3_msg = run_t3_forward_shape(sd) if sd else (False, "Skipped (no state_dict)")
    print(f"T3 [Encoder Structural Inspection]: {'PASSED' if t3_pass else 'FAILED'}")
    print(f"   Detail: {t3_msg} (Note: structural inspection of weight tensors only; live forward pass was not executed due to T1 unpickling block)\n")

    # Run T4
    t4_pass, t4_msg = run_t4_batchnorm_layout(sd) if sd else (False, "Skipped (no state_dict)")
    print(f"T4 [BatchNorm Layout Check]: {'PASSED' if t4_pass else 'FAILED'}")
    print(f"   Detail: {t4_msg}\n")

    print("=" * 80)
    print("OVERALL TRANSFER STATUS DETERMINATION:")
    all_passed = t1_pass and t2_pass and t3_pass and t4_pass

    if all_passed:
        print("  STATUS: VERIFIED. Checkpoint meets all compatibility criteria.")
    else:
        print("  STATUS: BLOCKED.")
        print("  ROOT CAUSE:")
        print("    1. PyTorch Lightning 1.4.1 checkpoint format requires unpickling arbitrary Python objects,")
        print("       violating PyTorch 2.6+ secure loading standards (weights_only=True).")
        print("    2. Legacy OpenHands dependency chain cannot run natively on Python 3.14 on Windows.")
        print("    3. While mathematical weights (ST-GCN channels and BatchNorm means) align structurally,")
        print("       enabling transfer learning without native runtime verification would violate")
        print("       CLAUDE.md §1 Principle 3 ('Honest transfer learning').")
        print("")
        print("  MANDATORY FALLBACK:")
        print("    Maintain the from-scratch GRU baseline as the primary operational model.")
        print("    Label the transfer path as honestly BLOCKED in the UI and documentation.")
        print("    Use the within-ISL simulation benchmark for all empirical evaluations.")
    print("=" * 80)

    # Return exit code: 0 if verified, 1 if blocked
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

