"""SIGNFORGE Active Learning & Corpus Task Ranker.

Ranks collection tasks across the vocabulary by synthesizing:
  - coverage_gap: distance from target sample count [0, 1]
  - signer_gap: distance from target distinct signers [0, 1] (or None if unverified)
  - uncertainty: validation-error proxy [0, 1] (or None if unmeasured)

Contract:
  - Inputs: per-sign metrics with support for None when signals are missing
  - Outputs: list of {"sign": str, "priority": float, "reason": str, ...}
  - Deterministic tie-breaking by canonical sign name
  - Configurable weights with proportional redistribution when signals are None
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


DEFAULT_WEIGHTS = {
    "uncertainty": 0.50,
    "coverage_gap": 0.30,
    "signer_gap": 0.20,
}

FORMULA_VERSION = "ranker-v1.0"


class RankedTask(BaseModel):
    sign: str
    priority: float = Field(ge=0.0, le=1.0)
    reason: str
    coverage_gap: float = Field(ge=0.0, le=1.0)
    signer_gap: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    current_samples: int = 0
    distinct_signers: Optional[int] = None
    target_samples: int = 10
    target_signers: int = 3
    formula_version: str = FORMULA_VERSION


def compute_coverage_gap(current_count: int, target_count: int = 10) -> float:
    """Gap from target sample count, scaled to [0, 1].

    0.0 means current_count >= target_count (target fulfilled).
    1.0 means 0 samples collected.
    """
    if target_count <= 0:
        return 0.0
    gap = max(0.0, (target_count - current_count) / float(target_count))
    return min(1.0, round(gap, 4))


def compute_signer_gap(distinct_signers: Optional[int], target_signers: int = 3) -> Optional[float]:
    """Gap from target distinct signers, scaled to [0, 1].

    Returns None if distinct_signers is None (unverified / unavailable signer IDs).
    0.0 means distinct_signers >= target_signers.
    1.0 means 0 signers.
    """
    if distinct_signers is None:
        return None
    if target_signers <= 0:
        return 0.0
    gap = max(0.0, (target_signers - distinct_signers) / float(target_signers))
    return min(1.0, round(gap, 4))


def calculate_sign_priority(
    coverage_gap: float,
    signer_gap: Optional[float],
    uncertainty: Optional[float],
    weights: Optional[dict[str, float]] = None,
) -> tuple[float, str]:
    """Calculate combined priority in [0, 1] and a human-readable explanation.

    When components are None (e.g. signer IDs unavailable or model unmeasured),
    weights are re-normalized across available components so that priority
    remains calibrated on [0, 1].
    """
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    
    # Identify available components
    components: dict[str, float] = {"coverage_gap": coverage_gap}
    explanations: list[str] = [f"coverage gap {coverage_gap:.2f}"]

    if signer_gap is not None:
        components["signer_gap"] = signer_gap
        explanations.append(f"signer diversity gap {signer_gap:.2f}")
    else:
        explanations.append("signer diversity unavailable")

    if uncertainty is not None:
        components["uncertainty"] = uncertainty
        explanations.append(f"validation error {uncertainty:.2f}")
    else:
        explanations.append("validation error not measured")

    # Sum weights of available components
    avail_weight_sum = sum(w.get(k, 0.0) for k in components)
    if avail_weight_sum <= 0:
        return 0.0, "No active scoring components"

    # Normalized linear combination
    raw_score = sum(w.get(k, 0.0) * components[k] for k in components) / avail_weight_sum
    priority = max(0.0, min(1.0, round(raw_score, 4)))

    reason = "; ".join(explanations)
    return priority, reason


def rank_collection_tasks(
    sign_classes: list[str],
    sample_counts: dict[str, int],
    signer_counts: Optional[dict[str, int]] = None,
    uncertainty_scores: Optional[dict[str, Optional[float]]] = None,
    target_samples_per_sign: int = 10,
    target_signers_per_sign: int = 3,
    weights: Optional[dict[str, float]] = None,
) -> list[RankedTask]:
    """Rank sign collection tasks from highest priority to lowest.

    Ties broken alphabetically by canonical sign name to ensure deterministic ordering.

    Args:
        sign_classes: List of canonical sign gloss strings.
        sample_counts: Map of sign -> number of eligible samples currently collected.
        signer_counts: Map of sign -> number of distinct signers (or None if unavailable).
        uncertainty_scores: Map of sign -> validation-error proxy (or None).
        target_samples_per_sign: Target sample count threshold.
        target_signers_per_sign: Target distinct signer count threshold.
        weights: Optional dictionary overriding default component weights.

    Returns:
        List of RankedTask objects sorted in descending order of priority.
    """
    ranked_tasks: list[RankedTask] = []

    for sign in sign_classes:
        n_samples = sample_counts.get(sign, 0)
        c_gap = compute_coverage_gap(n_samples, target_samples_per_sign)

        n_signers = signer_counts.get(sign) if signer_counts is not None else None
        s_gap = compute_signer_gap(n_signers, target_signers_per_sign)

        unc: Optional[float] = None
        if uncertainty_scores is not None and sign in uncertainty_scores:
            unc = uncertainty_scores[sign]

        priority, reason = calculate_sign_priority(
            coverage_gap=c_gap,
            signer_gap=s_gap,
            uncertainty=unc,
            weights=weights,
        )

        ranked_tasks.append(
            RankedTask(
                sign=sign,
                priority=priority,
                reason=reason,
                coverage_gap=c_gap,
                signer_gap=s_gap,
                uncertainty=unc,
                current_samples=n_samples,
                distinct_signers=n_signers,
                target_samples=target_samples_per_sign,
                target_signers=target_signers_per_sign,
            )
        )

    # Sort descending by priority; break ties ascending by canonical sign name
    ranked_tasks.sort(key=lambda t: (-t.priority, t.sign))
    return ranked_tasks

