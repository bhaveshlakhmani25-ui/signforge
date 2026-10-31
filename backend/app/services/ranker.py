"""
SIGNFORGE Active Learning Ranker Service

Shared ranker logic for both live queue (UI) and simulation harness.
Contract:
  priority(sign) = w_cov * coverage_gap + w_sig * signer_gap + w_unc * uncertainty
  (each scaled 0-1.0; frozen test set NEVER feeds it).
"""

from typing import Any, Dict, List, Optional
from sqlmodel import Session, select, func

from app.db.models import ConsentRecord, ModelRun, Sample, SignClass, Signer

FORMULA_VERSION = "ranker-v1"
DEFAULT_WEIGHTS = {
    "coverage": 0.35,
    "signer": 0.25,
    "uncertainty": 0.40,
}


def score_sign_class(
    sign_class_id: int,
    gloss: str,
    approved_count: int,
    distinct_signers: int,
    target_samples: int = 10,
    target_signers: int = 3,
    uncertainty: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Pure ranker function computing priority and explanation for a single sign class."""
    w = weights or DEFAULT_WEIGHTS
    w_cov = w.get("coverage", 0.35)
    w_sig = w.get("signer", 0.25)
    w_unc = w.get("uncertainty", 0.40)

    # 1. Coverage gap (0.0 to 1.0)
    target_s = max(1, target_samples)
    coverage_gap = max(0.0, min(1.0, 1.0 - (approved_count / target_s)))

    # 2. Signer diversity gap (0.0 to 1.0)
    target_sg = max(1, target_signers)
    signer_gap = max(0.0, min(1.0, 1.0 - (distinct_signers / target_sg)))

    # 3. Overall priority
    if uncertainty is not None:
        u = max(0.0, min(1.0, float(uncertainty)))
        raw_p = (w_cov * coverage_gap) + (w_sig * signer_gap) + (w_unc * u)
        total_w = w_cov + w_sig + w_unc
        priority = raw_p / total_w if total_w > 0 else 0.0
        unc_val = round(u, 3)
        unc_display = f"{unc_val:.2f}"
    else:
        # Uncertainty is unavailable; scale purely over coverage and signer diversity
        total_w = w_cov + w_sig
        raw_p = (w_cov * coverage_gap) + (w_sig * signer_gap)
        priority = raw_p / total_w if total_w > 0 else 0.0
        unc_val = None
        unc_display = "Not evaluated yet"

    priority = round(max(0.0, min(1.0, priority)), 3)
    coverage_gap = round(coverage_gap, 3)
    signer_gap = round(signer_gap, 3)

    # 4. Suggested signer group
    suggested_signer = "new_signer" if distinct_signers < target_signers else "any_consenting_signer"

    # 5. Plain-language explanation
    reasons = []
    if coverage_gap > 0:
        reasons.append(f"needs {max(0, target_samples - approved_count)} more approved samples ({approved_count}/{target_samples})")
    else:
        reasons.append(f"sample target met ({approved_count}/{target_samples})")

    if signer_gap > 0:
        reasons.append(f"only {distinct_signers}/{target_signers} signers represented")
    else:
        reasons.append(f"signer target met ({distinct_signers}/{target_signers})")

    if unc_val is not None:
        reasons.append(f"model uncertainty is {unc_display}")
    else:
        reasons.append("model uncertainty not evaluated yet")

    reason_str = "; ".join(reasons) + "."

    return {
        "sign_class_id": sign_class_id,
        "gloss": gloss,
        "priority": priority,
        "coverage_gap": coverage_gap,
        "signer_gap": signer_gap,
        "uncertainty": unc_val,
        "uncertainty_display": unc_display,
        "suggested_signer": suggested_signer,
        "approved_sample_count": approved_count,
        "distinct_signer_count": distinct_signers,
        "target_samples": target_samples,
        "target_signers": target_signers,
        "reason": reason_str,
        "formula_version": FORMULA_VERSION,
    }


def get_fake_queue(project_id: int = 1) -> List[Dict[str, Any]]:
    """Deterministic fake queue for frontend and harness integration in hour 1."""
    demo_classes = [
        ("EMERGENCY", 1, 1, 0.88, 101),
        ("HELP", 2, 1, 0.75, 102),
        ("HOSPITAL", 3, 2, 0.62, 103),
        ("WATER", 4, 2, 0.45, 104),
        ("FOOD", 5, 2, None, 105),
        ("THANK_YOU", 6, 3, None, 106),
        ("HELLO", 8, 3, 0.20, 107),
    ]
    items = []
    for gloss, appr, signers, unc, sc_id in demo_classes:
        items.append(
            score_sign_class(
                sign_class_id=sc_id,
                gloss=gloss,
                approved_count=appr,
                distinct_signers=signers,
                target_samples=10,
                target_signers=3,
                uncertainty=unc,
            )
        )
    items.sort(key=lambda x: (-x["priority"], x["gloss"]))
    return items


def compute_active_learning_queue(
    db: Session,
    project_id: int,
    target_samples: int = 10,
    target_signers: int = 3,
    fake: bool = False,
    include_demo: bool = False,
) -> List[Dict[str, Any]]:
    """
    Computes the prioritized queue of collection tasks.
    Guarantees:
      - Frozen test set samples NEVER feed coverage or signer counts.
      - Withdrawn consent samples NEVER feed counts.
      - DEMO DATA is excluded by default unless include_demo=True.
    """
    if fake:
        return get_fake_queue(project_id)

    # 1. Fetch active sign classes for the project
    classes = db.exec(
        select(SignClass).where(SignClass.project_id == project_id, SignClass.active == True)
    ).all()

    if not classes:
        return []

    # 2. Extract class uncertainties from latest successful model run if available
    latest_run = db.exec(
        select(ModelRun)
        .where(
            ModelRun.project_id == project_id,
            ModelRun.status == "succeeded",
            ModelRun.pool == ("demo" if include_demo else "real"),
        )
        .order_by(ModelRun.created_at.desc())
    ).first()

    uncertainties: Dict[int, float] = {}
    if latest_run and latest_run.metrics:
        # If per-class metrics exist, 1.0 - f1 is an honest empirical proxy for model error/uncertainty
        per_class = latest_run.metrics.get("per_class", {})
        for cid_str, m in per_class.items():
            try:
                cid = int(cid_str)
                f1 = m.get("f1")
                if f1 is not None and m.get("support", 0) > 0:
                    uncertainties[cid] = max(0.0, min(1.0, 1.0 - float(f1)))
            except (ValueError, TypeError):
                continue

    # 3. For each class, query approved training/unassigned samples
    queue = []
    for sc in classes:
        # Exclude frozen test set ('test') and withdrawn consents
        query = (
            select(Sample.signer_id)
            .join(ConsentRecord, ConsentRecord.id == Sample.consent_id)
            .where(
                Sample.project_id == project_id,
                Sample.sign_class_id == sc.id,
                Sample.review_status == "approved",
                Sample.split != "test",  # RULE: Frozen test set never feeds ranker
                ConsentRecord.status == "active",
            )
        )
        if not include_demo:
            query = query.where(Sample.source != "demo_fixture")

        signers_found = db.exec(query).all()
        approved_count = len(signers_found)
        distinct_signers = len(set(signers_found))

        unc = uncertainties.get(sc.id) if sc.id in uncertainties else None

        item = score_sign_class(
            sign_class_id=sc.id,
            gloss=sc.gloss,
            approved_count=approved_count,
            distinct_signers=distinct_signers,
            target_samples=target_samples,
            target_signers=target_signers,
            uncertainty=unc,
        )
        queue.append(item)

    # Sort descending by priority, breaking ties deterministically by gloss
    queue.sort(key=lambda x: (-x["priority"], x["gloss"]))
    return queue
