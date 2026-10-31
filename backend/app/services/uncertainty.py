"""Per-sign validation-error proxy estimation via multi-fold cross-validation.

In accordance with CLAUDE.md and docs/SIMULATION_PROTOCOL.md:
- This metric is explicitly a VALIDATION-ERROR PROXY (1 - recall), NOT calibrated
  predictive entropy or Bayesian uncertainty.
- The frozen test split is strictly excluded from fold creation, training,
  and uncertainty estimation.
- Classes with no validation observations return error_proxy=None with support=0.
  They are never assigned zero or an arbitrary maximum value.
"""
from typing import Any, Callable, Optional, Sequence

import numpy as np
from pydantic import BaseModel, Field

from app.core import config as C
from app.services.baseline_model import predict_proba, train_baseline
from app.services.evaluation import classification_metrics


class SignUncertainty(BaseModel):
    """Validation-error proxy metrics for a single sign class."""
    sign: str
    error_proxy: Optional[float] = None  # 1.0 - recall, or None if no validation observations
    usable_folds: int = 0               # number of folds where this sign had validation support > 0
    support: int = 0                    # total validation instances across usable folds
    total_folds: int = 0                # total number of cross-validation folds evaluated


class UncertaintyReport(BaseModel):
    """Aggregated validation-error proxy report across all target sign classes."""
    method: str = "k_fold_cross_validation_error"
    metric: str = "1_minus_recall"
    labeled_as_predictive_entropy: bool = False
    num_folds: int
    seed: int
    total_samples: int
    per_sign: dict[str, SignUncertainty] = Field(default_factory=dict)


def make_stratified_folds(
    y: np.ndarray,
    num_folds: int,
    seed: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Partition sample indices into K stratified folds deterministically.

    For each class present in y, its indices are shuffled using a seeded RNG
    and distributed round-robin across the K folds.

    Returns:
        List of (train_indices, val_indices) arrays.
    """
    if num_folds < 2:
        raise ValueError(f"num_folds must be >= 2, got {num_folds}")

    n_samples = len(y)
    if n_samples == 0:
        return [(np.array([], dtype=int), np.array([], dtype=int)) for _ in range(num_folds)]

    rng = np.random.default_rng(seed)
    val_buckets: list[list[int]] = [[] for _ in range(num_folds)]

    unique_classes = np.unique(y)
    for c in unique_classes:
        c_indices = np.where(y == c)[0]
        shuffled = rng.permutation(c_indices)
        for i, idx in enumerate(shuffled):
            val_buckets[i % num_folds].append(int(idx))

    all_indices = set(range(n_samples))
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for k in range(num_folds):
        val_idx = np.array(sorted(val_buckets[k]), dtype=int)
        train_idx = np.array(sorted(all_indices - set(val_idx)), dtype=int)
        folds.append((train_idx, val_idx))

    return folds


def compute_per_sign_validation_error(
    X: np.ndarray,
    y: np.ndarray,
    classes: Sequence[Any],
    num_folds: int = 3,
    seed: int = 0,
    model_cfg: Optional[dict] = None,
    sample_ids: Optional[Sequence[Any]] = None,
    forbidden_test_ids: Optional[set[Any] | Sequence[Any]] = None,
) -> UncertaintyReport:
    """Estimates the per-sign validation-error proxy (1 - recall) across multiple folds.

    Args:
        X: Feature tensor of shape (N, T, 27, 2).
        y: Array of integer class labels in range 0..len(classes)-1.
        classes: Sequence of canonical sign glosses or class identifiers.
        num_folds: Number of stratified validation folds (default: 3).
        seed: Random seed for deterministic fold assignment and model initialization.
        model_cfg: Optional model training configuration dictionary (defaults to C.BASELINE).
        sample_ids: Optional sample identifiers aligned with X and y.
        forbidden_test_ids: Optional set of frozen test sample IDs. Raises ValueError
            if any sample_id is present in this set (test-split isolation check).

    Returns:
        UncertaintyReport containing per-sign error proxy, usable fold counts, and support.
    """
    # Enforce test-split isolation if forbidden test IDs are provided
    if forbidden_test_ids is not None and sample_ids is not None:
        forbidden_set = set(forbidden_test_ids)
        overlap = set(sample_ids) & forbidden_set
        if overlap:
            raise ValueError(
                f"Test-split isolation violated! {len(overlap)} samples with forbidden test IDs "
                f"found in uncertainty estimation input: {sorted(list(overlap))[:5]}"
            )

    cfg = model_cfg or C.BASELINE
    n_classes = len(classes)
    idx_to_class = {i: str(c) for i, c in enumerate(classes)}

    if len(y) == 0:
        per_sign = {
            str(c): SignUncertainty(
                sign=str(c),
                error_proxy=None,
                usable_folds=0,
                support=0,
                total_folds=num_folds,
            )
            for c in classes
        }
        return UncertaintyReport(
            num_folds=num_folds,
            seed=seed,
            total_samples=0,
            per_sign=per_sign,
        )

    folds = make_stratified_folds(y, num_folds=num_folds, seed=seed)

    # Track validation errors and supports per class across folds
    # class_idx -> list of fold error values
    fold_errors: dict[int, list[float]] = {i: [] for i in range(n_classes)}
    fold_supports: dict[int, list[int]] = {i: [] for i in range(n_classes)}

    for fold_k, (train_idx, val_idx) in enumerate(folds):
        if len(train_idx) == 0 or len(val_idx) == 0:
            continue

        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        # Train baseline model on fold training partition using deterministic seed
        fold_seed = seed + fold_k * 1000
        model = train_baseline(X_train, y_train, n_classes, cfg, seed=fold_seed)

        # Predict on validation partition
        probs = predict_proba(model, X_val)
        y_pred = probs.argmax(axis=-1)

        # Compute metrics using existing evaluation module
        metrics = classification_metrics(y_val.tolist(), y_pred.tolist(), list(range(n_classes)))
        per_class_metrics = metrics["per_class"]

        for i in range(n_classes):
            c_info = per_class_metrics.get(i, {"support": 0, "recall": 0.0})
            support = c_info["support"]
            if support > 0:
                # Sign was evaluated in this fold
                recall = float(c_info["recall"])
                error_k = round(max(0.0, min(1.0, 1.0 - recall)), 4)
                fold_errors[i].append(error_k)
                fold_supports[i].append(int(support))

    # Aggregate across usable folds
    per_sign_results: dict[str, SignUncertainty] = {}
    for i in range(n_classes):
        c_name = idx_to_class[i]
        errors = fold_errors[i]
        supports = fold_supports[i]
        usable_count = len(errors)
        total_support = sum(supports)

        if usable_count > 0:
            mean_error = round(float(np.mean(errors)), 4)
            error_proxy: Optional[float] = mean_error
        else:
            # Protocol rule: if a class has no usable validation observations,
            # return None. Do NOT substitute 0 or 1.
            error_proxy = None

        per_sign_results[c_name] = SignUncertainty(
            sign=c_name,
            error_proxy=error_proxy,
            usable_folds=usable_count,
            support=total_support,
            total_folds=num_folds,
        )

    return UncertaintyReport(
        num_folds=num_folds,
        seed=seed,
        total_samples=len(y),
        per_sign=per_sign_results,
    )


def estimate_uncertainty_from_samples(
    samples: Sequence[dict[str, Any]],
    load_feature_fn: Callable[[dict[str, Any]], np.ndarray],
    classes: Sequence[Any],
    num_folds: int = 3,
    seed: int = 0,
    model_cfg: Optional[dict] = None,
    forbidden_test_ids: Optional[set[Any] | Sequence[Any]] = None,
) -> UncertaintyReport:
    """Convenience wrapper to estimate uncertainty directly from sample records.

    Verifies that no sample with split='test' enters the pool.
    """
    sample_ids: list[Any] = []
    for s in samples:
        # Strict isolation check: fail immediately if a test split sample enters
        if s.get("split") == "test":
            raise ValueError(
                f"Test-split isolation violated! Sample {s.get('id')} has split='test'. "
                "Frozen test samples must never enter validation fold creation or uncertainty estimation."
            )
        sample_ids.append(s.get("id"))

    if not samples:
        return compute_per_sign_validation_error(
            np.zeros((0, C.MODEL_FRAMES, 27, 2), dtype=np.float32),
            np.array([], dtype=int),
            classes=classes,
            num_folds=num_folds,
            seed=seed,
            model_cfg=model_cfg,
            sample_ids=sample_ids,
            forbidden_test_ids=forbidden_test_ids,
        )

    class_to_idx = {c: i for i, c in enumerate(classes)}
    X_list: list[np.ndarray] = []
    y_list: list[int] = []

    for s in samples:
        c_label = s.get("sign_class_id") or s.get("sign") or s.get("gloss")
        if c_label not in class_to_idx:
            raise ValueError(f"Sample {s.get('id')} has unrecognized class {c_label} (not in {classes})")
        feat = load_feature_fn(s)
        X_list.append(feat)
        y_list.append(class_to_idx[c_label])

    X = np.stack(X_list, axis=0)
    y = np.array(y_list, dtype=int)

    return compute_per_sign_validation_error(
        X=X,
        y=y,
        classes=classes,
        num_folds=num_folds,
        seed=seed,
        model_cfg=model_cfg,
        sample_ids=sample_ids,
        forbidden_test_ids=forbidden_test_ids,
    )

