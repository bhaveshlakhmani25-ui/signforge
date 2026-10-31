import numpy as np
import pytest

from app.services.uncertainty import (
    SignUncertainty,
    UncertaintyReport,
    compute_per_sign_validation_error,
    estimate_uncertainty_from_samples,
    make_stratified_folds,
)

FAST_CFG = {"hidden": 16, "epochs": 2, "lr": 1e-3, "weight_decay": 0}


def _dummy_feature(seed: int = 0) -> np.ndarray:
    """Creates a deterministic dummy feature array of shape (30, 27, 2)."""
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, size=(30, 27, 2)).astype(np.float32)


def test_deterministic_fold_assignment():
    """Deterministic fold assignment: same seed yields identical folds, different seed yields different."""
    y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    folds_a1 = make_stratified_folds(y, num_folds=3, seed=42)
    folds_a2 = make_stratified_folds(y, num_folds=3, seed=42)
    folds_b = make_stratified_folds(y, num_folds=3, seed=99)

    for (tr1, val1), (tr2, val2) in zip(folds_a1, folds_a2):
        np.testing.assert_array_equal(tr1, tr2)
        np.testing.assert_array_equal(val1, val2)

    # Different seeds should produce at least one different validation assignment
    any_different = any(not np.array_equal(v1, v2) for (_, v1), (_, v2) in zip(folds_a1, folds_b))
    assert any_different, "Folds should differ across different seeds"


def test_sign_with_valid_observations_in_multiple_folds():
    """A sign with sufficient samples has validation observations in all K folds."""
    classes = ["A", "B"]
    # 6 samples of A, 6 samples of B -> for K=3, exactly 2 samples per fold for each class
    X = np.stack([_dummy_feature(i) for i in range(12)], axis=0)
    y = np.array([0] * 6 + [1] * 6, dtype=int)

    report = compute_per_sign_validation_error(
        X=X,
        y=y,
        classes=classes,
        num_folds=3,
        seed=123,
        model_cfg=FAST_CFG,
    )

    assert isinstance(report, UncertaintyReport)
    assert report.num_folds == 3
    assert report.total_samples == 12
    assert not report.labeled_as_predictive_entropy

    res_a = report.per_sign["A"]
    res_b = report.per_sign["B"]

    assert res_a.usable_folds == 3
    assert res_a.support == 6
    assert res_a.error_proxy is not None
    assert 0.0 <= res_a.error_proxy <= 1.0

    assert res_b.usable_folds == 3
    assert res_b.support == 6
    assert res_b.error_proxy is not None
    assert 0.0 <= res_b.error_proxy <= 1.0


def test_sign_missing_from_one_fold():
    """A sign with fewer samples than folds is absent from at least one fold.
    Its error_proxy is averaged ONLY across usable folds, NOT counted as zero error.
    """
    classes = ["A", "B", "C"]
    # A has 6 samples, B has 6 samples, C has only 2 samples.
    # With num_folds=3, C can only appear in 2 folds; 1 fold will have 0 instances of C.
    X_list = [_dummy_feature(i) for i in range(14)]
    X = np.stack(X_list, axis=0)
    y = np.array([0] * 6 + [1] * 6 + [2] * 2, dtype=int)

    report = compute_per_sign_validation_error(
        X=X,
        y=y,
        classes=classes,
        num_folds=3,
        seed=42,
        model_cfg=FAST_CFG,
    )

    res_c = report.per_sign["C"]
    # C must have usable_folds == 2 (missing from exactly 1 fold)
    assert res_c.usable_folds == 2
    assert res_c.support == 2
    assert res_c.total_folds == 3
    assert res_c.error_proxy is not None
    assert 0.0 <= res_c.error_proxy <= 1.0


def test_sign_with_no_usable_observations_across_folds():
    """A target sign with 0 labeled samples in the pool has 0 usable observations.
    Protocol rule: must return error_proxy = None and support = 0.
    Must NEVER substitute 0.0 or 1.0!
    """
    classes = ["A", "B", "UNSEEN"]
    # Only A and B have samples; UNSEEN has 0 samples
    X = np.stack([_dummy_feature(i) for i in range(8)], axis=0)
    y = np.array([0] * 4 + [1] * 4, dtype=int)

    report = compute_per_sign_validation_error(
        X=X,
        y=y,
        classes=classes,
        num_folds=3,
        seed=42,
        model_cfg=FAST_CFG,
    )

    res_unseen = report.per_sign["UNSEEN"]
    assert res_unseen.error_proxy is None, "Missing observations must be None, not 0.0 or 1.0"
    assert res_unseen.usable_folds == 0
    assert res_unseen.support == 0
    assert res_unseen.total_folds == 3


def test_distinction_between_null_and_measured_zero():
    """Explicitly verifies the difference between None (unobserved) and 0.0 (measured 100% recall)."""
    unobserved = SignUncertainty(sign="X", error_proxy=None, usable_folds=0, support=0, total_folds=3)
    perfect = SignUncertainty(sign="Y", error_proxy=0.0, usable_folds=3, support=6, total_folds=3)

    assert unobserved.error_proxy is None
    assert unobserved.usable_folds == 0

    assert perfect.error_proxy is not None
    assert perfect.error_proxy == 0.0
    assert perfect.usable_folds == 3

    # Must never evaluate unobserved as equal to 0.0
    assert unobserved.error_proxy != perfect.error_proxy


def test_test_split_isolation_with_forbidden_ids():
    """compute_per_sign_validation_error raises ValueError if any forbidden test ID is passed."""
    classes = ["A", "B"]
    X = np.stack([_dummy_feature(i) for i in range(4)], axis=0)
    y = np.array([0, 0, 1, 1], dtype=int)
    sample_ids = [101, 102, 103, 999]  # 999 is in the test set!
    forbidden_test_ids = {999, 1000}

    with pytest.raises(ValueError, match="Test-split isolation violated"):
        compute_per_sign_validation_error(
            X=X,
            y=y,
            classes=classes,
            num_folds=2,
            seed=42,
            model_cfg=FAST_CFG,
            sample_ids=sample_ids,
            forbidden_test_ids=forbidden_test_ids,
        )


def test_test_split_isolation_in_sample_wrapper():
    """estimate_uncertainty_from_samples raises ValueError if a sample has split='test'."""
    samples = [
        {"id": 1, "sign": "A", "split": "train"},
        {"id": 2, "sign": "A", "split": "train"},
        {"id": 3, "sign": "B", "split": "test"},  # Violates test isolation!
    ]

    with pytest.raises(ValueError, match="Test-split isolation violated"):
        estimate_uncertainty_from_samples(
            samples=samples,
            load_feature_fn=lambda s: _dummy_feature(s["id"]),
            classes=["A", "B"],
            num_folds=2,
            seed=42,
            model_cfg=FAST_CFG,
        )


def test_test_split_isolation_clean_samples_pass():
    """When only training samples are passed and no forbidden IDs overlap, computation succeeds."""
    samples = [
        {"id": 1, "sign": "A", "split": "train"},
        {"id": 2, "sign": "A", "split": "train"},
        {"id": 3, "sign": "B", "split": "train"},
        {"id": 4, "sign": "B", "split": "train"},
    ]
    forbidden_test_ids = {100, 101, 102}

    report = estimate_uncertainty_from_samples(
        samples=samples,
        load_feature_fn=lambda s: _dummy_feature(s["id"]),
        classes=["A", "B"],
        num_folds=2,
        seed=42,
        model_cfg=FAST_CFG,
        forbidden_test_ids=forbidden_test_ids,
    )
    assert report.total_samples == 4
    assert report.per_sign["A"].usable_folds > 0

