#!/usr/bin/env python3
"""SIGNFORGE Benchmark Execution Script.

Runs the multi-seed active collection simulation comparing:
  - SIGNFORGE (model-guided ranker)
  - Balanced round-robin (class-balanced)
  - Random selection (uniform random)

Outputs:
  - Summary comparison table printed to terminal
  - Complete JSON artifact written to data/benchmark_results.json
"""

import argparse
import json
import sys
from pathlib import Path

# Add backend directory to path if run from root
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.simulation import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_ROUNDS,
    DEFAULT_SEEDS,
    SimulationHarness,
    generate_benchmark_subset,
)


def format_table(results: dict) -> str:
    """Formats a clean terminal summary table."""
    summary = results["summary"]
    initial = summary["initial_metrics"]
    by_strat = summary["by_strategy"]
    curves = results["curves"]["points_per_strategy"]

    lines = []
    lines.append("=" * 80)
    lines.append("  SIGNFORGE ACTIVE COLLECTION SIMULATION BENCHMARK RESULTS")
    lines.append("=" * 80)
    lines.append(f"Dataset:            {results['dataset']['name']} ({results['dataset']['language']})")
    lines.append(f"Vocabulary:         {results['dataset']['num_classes']} signs: {', '.join(results['dataset']['sign_classes'])}")
    lines.append(f"Evaluation Split:   {results['splits']['strategy']} (Frozen Test: {results['splits']['test_sample_count']} samples)")
    lines.append(f"Signer Independent: {results['splits']['signer_independent']} (Honesty rule: INCLUDE signer IDs unverified)")
    lines.append(f"Uncertainty Proxy:  {results['protocol']['uncertainty_proxy']['method']} (1 - recall, {results['protocol']['uncertainty_proxy']['num_folds']} folds)")
    lines.append(f"Seeds Evaluated:    {results['protocol']['seeds']}")
    lines.append(f"Acquisition Budget: {results['protocol']['num_rounds']} rounds × {results['protocol']['batch_size_per_round']} samples/round = {summary['final_budget'] - summary['initial_budget']} added samples")
    lines.append("-" * 80)
    lines.append("")
    lines.append("BEFORE / AFTER PERFORMANCE SUMMARY (Mean ± Std across seeds):")
    lines.append("-" * 80)
    header = f"{'Strategy':<16} | {'Init Macro-F1':<14} | {'Final Macro-F1':<16} | {'F1 Gain':<10} | {'Final Accuracy':<16}"
    lines.append(header)
    lines.append("-" * 80)

    init_f1_str = f"{initial['macro_f1_mean'] * 100:.1f}% ± {initial['macro_f1_std'] * 100:.1f}%"

    for strat_key, strat_name in [
        ("signforge", "SIGNFORGE (Ranker)"),
        ("round_robin", "Round-Robin"),
        ("random", "Random Selection"),
    ]:
        s_data = by_strat[strat_key]
        final_f1_str = f"{s_data['final_macro_f1_mean'] * 100:.1f}% ± {s_data['final_macro_f1_std'] * 100:.1f}%"
        gain_val = s_data['macro_f1_gain_mean'] * 100
        gain_str = f"+{gain_val:.1f}%" if gain_val >= 0 else f"{gain_val:.1f}%"
        final_acc_str = f"{s_data['final_accuracy_mean'] * 100:.1f}% ± {s_data['final_accuracy_std'] * 100:.1f}%"

        lines.append(f"{strat_name:<16} | {init_f1_str:<14} | {final_f1_str:<16} | {gain_str:<10} | {final_acc_str:<16}")

    lines.append("-" * 80)
    lines.append("")
    lines.append("ACQUISITION PROGRESSION CURVES (Macro-F1 by Round):")
    lines.append("-" * 80)
    curve_header = f"{'Round':<6} | {'Samples':<8} | {'SIGNFORGE':<18} | {'Round-Robin':<18} | {'Random':<18}"
    lines.append(curve_header)
    lines.append("-" * 80)

    num_rounds = results["protocol"]["num_rounds"]
    for r in range(num_rounds + 1):
        sf_pt = curves["signforge"][r]
        rr_pt = curves["round_robin"][r]
        rd_pt = curves["random"][r]

        sf_str = f"{sf_pt['macro_f1_mean'] * 100:.1f}% (±{sf_pt['macro_f1_std'] * 100:.1f}%)"
        rr_str = f"{rr_pt['macro_f1_mean'] * 100:.1f}% (±{rr_pt['macro_f1_std'] * 100:.1f}%)"
        rd_str = f"{rd_pt['macro_f1_mean'] * 100:.1f}% (±{rd_pt['macro_f1_std'] * 100:.1f}%)"

        lines.append(f"{r:<6} | {sf_pt['total_training_samples']:<8} | {sf_str:<18} | {rr_str:<18} | {rd_str:<18}")

    lines.append("-" * 80)
    lines.append("")
    lines.append("CORE FINDINGS & INTERPRETATION:")
    sf_gain = by_strat["signforge"]["macro_f1_gain_mean"]
    rr_gain = by_strat["round_robin"]["macro_f1_gain_mean"]
    rd_gain = by_strat["random"]["macro_f1_gain_mean"]
    lines.append(f"  * SIGNFORGE achieved {sf_gain * 100:.1f}% macro-F1 gain from {summary['initial_budget']} to {summary['final_budget']} samples.")
    lines.append(f"  * Round-Robin achieved {rr_gain * 100:.1f}% gain; Random selection achieved {rd_gain * 100:.1f}% gain.")
    diff_vs_rand = (sf_gain - rd_gain) * 100
    diff_vs_rr = (sf_gain - rr_gain) * 100
    lines.append(f"  * Advantage over Random: +{diff_vs_rand:.1f}% macro-F1.")
    lines.append(f"  * Advantage over Round-Robin: +{diff_vs_rr:.1f}% macro-F1.")
    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run SIGNFORGE evaluation simulation benchmark")
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS, help="Random seeds for evaluation")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help=f"Number of acquisition rounds (default: {DEFAULT_ROUNDS})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Batch size per round (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--epochs", type=int, default=50, help="Model training epochs (default: 50)")
    parser.add_argument("--output", type=str, default="data/benchmark_results.json", help="Output JSON path")
    args = parser.parse_args()

    print(f">> Initializing benchmark subset fixture (10 classes, 180 clips)...")
    train_pool, test_set = generate_benchmark_subset()
    print(f">> Training candidate pool: {len(train_pool)} samples | Frozen test set: {len(test_set)} samples")

    harness = SimulationHarness(
        seeds=args.seeds,
        num_rounds=args.rounds,
        batch_size=args.batch_size,
        epochs=args.epochs,
    )

    print(f">> Executing simulation across seeds {args.seeds} for 3 strategies...")
    results = harness.run_simulation(train_pool, test_set)

    # Format table and print
    table_str = format_table(results)
    print("\n" + table_str + "\n")

    # Save artifact
    raw_path = Path(args.output)
    if raw_path.is_absolute():
        output_path = raw_path
    else:
        cwd_cand = (Path.cwd() / raw_path).resolve()
        repo_root = backend_dir.parent.resolve()
        if cwd_cand.is_relative_to(repo_root):
            output_path = cwd_cand
        else:
            output_path = (repo_root / "data" / raw_path.name).resolve()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f">> Successfully exported benchmark artifact to: {output_path}")
    print(f">> Schema compliance: {results['schema_version']} | Size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
