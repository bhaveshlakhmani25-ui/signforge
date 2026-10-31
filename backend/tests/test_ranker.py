import pytest
from app.services.ranker import (
    DEFAULT_WEIGHTS,
    FORMULA_VERSION,
    RankedTask,
    calculate_sign_priority,
    compute_coverage_gap,
    compute_signer_gap,
    rank_collection_tasks,
)


def test_coverage_gap_bounds():
    # 0 collected, target 10 -> 1.0
    assert compute_coverage_gap(0, 10) == 1.0
    # 5 collected, target 10 -> 0.5
    assert compute_coverage_gap(5, 10) == 0.5
    # 10 collected, target 10 -> 0.0
    assert compute_coverage_gap(10, 10) == 0.0
    # 15 collected, target 10 -> 0.0 (does not go negative)
    assert compute_coverage_gap(15, 10) == 0.0


def test_signer_gap_bounds():
    # When distinct signers is None (unavailable) -> None
    assert compute_signer_gap(None, 3) is None
    # 0 signers, target 3 -> 1.0
    assert compute_signer_gap(0, 3) == 1.0
    # 1 signer, target 3 -> 2/3 ≈ 0.6667
    assert compute_signer_gap(1, 3) == pytest.approx(0.6667, abs=1e-3)
    # 3 signers, target 3 -> 0.0
    assert compute_signer_gap(3, 3) == 0.0
    # 5 signers, target 3 -> 0.0
    assert compute_signer_gap(5, 3) == 0.0


def test_calculate_priority_all_components():
    # w = {unc: 0.5, cov: 0.3, sig: 0.2}
    # unc=0.8, cov=0.6, sig=0.5 -> 0.5*0.8 + 0.3*0.6 + 0.2*0.5 = 0.40 + 0.18 + 0.10 = 0.68
    priority, reason = calculate_sign_priority(coverage_gap=0.6, signer_gap=0.5, uncertainty=0.8)
    assert priority == pytest.approx(0.68, abs=1e-4)
    assert "coverage gap 0.60" in reason
    assert "signer diversity gap 0.50" in reason
    assert "validation error 0.80" in reason


def test_calculate_priority_missing_signer_gap():
    # When signer diversity is unavailable, weights for cov (0.3) and unc (0.5) normalize by sum=0.8
    # unc=0.8, cov=0.4 -> (0.5*0.8 + 0.3*0.4)/0.8 = (0.40 + 0.12)/0.8 = 0.52/0.8 = 0.65
    priority, reason = calculate_sign_priority(coverage_gap=0.4, signer_gap=None, uncertainty=0.8)
    assert priority == pytest.approx(0.65, abs=1e-4)
    assert "signer diversity unavailable" in reason
    assert "validation error 0.80" in reason


def test_calculate_priority_missing_uncertainty():
    # When uncertainty is unavailable (no model trained yet), weights for cov (0.3) and sig (0.2) normalize by sum=0.5
    # cov=0.6, sig=0.4 -> (0.3*0.6 + 0.2*0.4)/0.5 = (0.18 + 0.08)/0.5 = 0.26/0.5 = 0.52
    priority, reason = calculate_sign_priority(coverage_gap=0.6, signer_gap=0.4, uncertainty=None)
    assert priority == pytest.approx(0.52, abs=1e-4)
    assert "validation error not measured" in reason


def test_calculate_priority_only_coverage_gap():
    # Both signer_gap and uncertainty unavailable -> priority equals coverage_gap
    priority, reason = calculate_sign_priority(coverage_gap=0.75, signer_gap=None, uncertainty=None)
    assert priority == 0.75
    assert "signer diversity unavailable" in reason
    assert "validation error not measured" in reason


def test_deterministic_tie_breaking():
    signs = ["WATER", "FOOD", "HELP", "DOCTOR"]
    # All have identical coverage and no other signals
    counts = {s: 2 for s in signs}
    ranked = rank_collection_tasks(
        sign_classes=signs,
        sample_counts=counts,
        signer_counts=None,
        uncertainty_scores=None,
    )
    # Since priority is identical, tie break must be alphabetical: DOCTOR, FOOD, HELP, WATER
    assert [r.sign for r in ranked] == ["DOCTOR", "FOOD", "HELP", "WATER"]


def test_rank_collection_tasks_order():
    signs = ["A", "B", "C"]
    counts = {"A": 2, "B": 8, "C": 5}
    # Unc: A has high error (0.9), B has low error (0.1), C has medium error (0.5)
    unc = {"A": 0.9, "B": 0.1, "C": 0.5}

    ranked = rank_collection_tasks(
        sign_classes=signs,
        sample_counts=counts,
        uncertainty_scores=unc,
        target_samples_per_sign=10,
    )
    assert ranked[0].sign == "A"
    assert ranked[1].sign == "C"
    assert ranked[2].sign == "B"
    assert ranked[0].priority > ranked[1].priority > ranked[2].priority


def test_custom_weights():
    signs = ["A", "B"]
    # A has high coverage gap (0.9), zero error (0.0)
    # B has zero coverage gap (0.0), high error (0.9)
    counts = {"A": 1, "B": 10}
    unc = {"A": 0.0, "B": 0.9}

    # If uncertainty weight is 1.0 and coverage is 0.0 -> B wins
    ranked_unc = rank_collection_tasks(
        sign_classes=signs,
        sample_counts=counts,
        uncertainty_scores=unc,
        weights={"uncertainty": 1.0, "coverage_gap": 0.0, "signer_gap": 0.0},
    )
    assert ranked_unc[0].sign == "B"

    # If coverage weight is 1.0 and uncertainty is 0.0 -> A wins
    ranked_cov = rank_collection_tasks(
        sign_classes=signs,
        sample_counts=counts,
        uncertainty_scores=unc,
        weights={"uncertainty": 0.0, "coverage_gap": 1.0, "signer_gap": 0.0},
    )
    assert ranked_cov[0].sign == "A"

