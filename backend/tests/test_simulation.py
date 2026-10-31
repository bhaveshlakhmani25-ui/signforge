import numpy as np
import pytest

from app.services.simulation import (
    BENCHMARK_CLASSES,
    SimulationHarness,
    compute_pool_hash,
    generate_benchmark_subset,
)


def test_generate_benchmark_subset():
    train_pool, test_set = generate_benchmark_subset(
        classes=BENCHMARK_CLASSES,
        samples_per_class=10,
        test_per_class=3,
        seed=42,
    )

    # 10 classes * 7 train = 70 train samples
    assert len(train_pool) == 70
    # 10 classes * 3 test = 30 test samples
    assert len(test_set) == 30

    # Ensure mutually exclusive IDs
    train_ids = {s.id for s in train_pool}
    test_ids = {s.id for s in test_set}
    assert len(train_ids & test_ids) == 0

    # Feature shapes
    for s in train_pool + test_set:
        assert s.features.shape == (30, 27, 2)
        assert s.features.dtype == np.float32

    # Verify hashes
    h_train = compute_pool_hash(train_pool)
    h_test = compute_pool_hash(test_set)
    assert len(h_train) == 64
    assert len(h_test) == 64
    assert h_train != h_test


def test_simulation_harness_execution_and_schema():
    # Fast test harness with 2 rounds, 1 seed, 5 epochs
    classes = ["HELLO", "HELP", "YES"]
    train_pool, test_set = generate_benchmark_subset(
        classes=classes,
        samples_per_class=6,
        test_per_class=2,
        seed=123,
    )

    harness = SimulationHarness(
        classes=classes,
        seeds=[42],
        num_rounds=2,
        batch_size=3,
        initial_per_class=2,
        k_folds=2,
        epochs=5,
    )

    results = harness.run_simulation(train_pool, test_set)

    # Check top-level schema keys
    required_keys = [
        "schema_version",
        "generated_at",
        "dataset",
        "splits",
        "protocol",
        "model",
        "summary",
        "curves",
        "runs",
        "warnings",
    ]
    for key in required_keys:
        assert key in results, f"Missing required top-level key: {key}"

    assert results["schema_version"] == "signforge-benchmark-v1"
    assert results["dataset"]["num_classes"] == 3
    assert results["splits"]["strategy"] == "official_include_test_split"
    assert results["splits"]["signer_independent"] is False

    # Check summary
    summary = results["summary"]
    assert "initial_metrics" in summary
    assert "by_strategy" in summary
    for st in ["signforge", "round_robin", "random"]:
        assert st in summary["by_strategy"]
        strat_sum = summary["by_strategy"][st]
        assert "final_accuracy_mean" in strat_sum
        assert "final_macro_f1_mean" in strat_sum
        assert "macro_f1_gain_mean" in strat_sum
        assert strat_sum["samples_added"] == 6

    # Check curves
    curves = results["curves"]["points_per_strategy"]
    for st in ["signforge", "round_robin", "random"]:
        assert len(curves[st]) == 3  # Round 0, Round 1, Round 2
        for r_idx, pt in enumerate(curves[st]):
            assert pt["round"] == r_idx
            assert "macro_f1_mean" in pt
            assert "accuracy_mean" in pt
            assert 0.0 <= pt["accuracy_mean"] <= 1.0


def test_simulation_fairness_equal_starting_and_budget():
    classes = ["FOOD", "WATER"]
    train_pool, test_set = generate_benchmark_subset(
        classes=classes,
        samples_per_class=8,
        test_per_class=2,
        seed=999,
    )

    harness = SimulationHarness(
        classes=classes,
        seeds=[42],
        num_rounds=2,
        batch_size=2,
        initial_per_class=2,
        k_folds=2,
        epochs=3,
    )

    results = harness.run_simulation(train_pool, test_set)
    curves = results["curves"]["points_per_strategy"]

    # All 3 strategies must start at Round 0 with identical samples and metrics
    r0_sf = curves["signforge"][0]
    r0_rr = curves["round_robin"][0]
    r0_rd = curves["random"][0]

    assert r0_sf["total_training_samples"] == r0_rr["total_training_samples"] == r0_rd["total_training_samples"] == 4
    assert r0_sf["accuracy_mean"] == r0_rr["accuracy_mean"] == r0_rd["accuracy_mean"]
    assert r0_sf["macro_f1_mean"] == r0_rr["macro_f1_mean"] == r0_rd["macro_f1_mean"]

    # At Round 2, all 3 strategies must have trained on exactly initial + 2 * 2 = 8 samples
    r2_sf = curves["signforge"][2]
    r2_rr = curves["round_robin"][2]
    r2_rd = curves["random"][2]
    assert r2_sf["total_training_samples"] == r2_rr["total_training_samples"] == r2_rd["total_training_samples"] == 8

