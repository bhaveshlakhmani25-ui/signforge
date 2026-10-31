from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.services.ranker import DEFAULT_WEIGHTS, FORMULA_VERSION, compute_active_learning_queue

router = APIRouter(prefix="/api/active-learning", tags=["active-learning"])


@router.get("/queue")
def get_queue(
    project_id: int = 1,
    target_samples: int = 10,
    target_signers: int = 3,
    fake: bool = False,
    include_demo: bool = False,
    session: Session = Depends(get_session),
):
    """
    Returns prioritized list of signs to collect next based on:
      priority(sign) = w_cov * coverage_gap + w_sig * signer_gap + w_unc * uncertainty
    Supports ?fake=true so frontend/simulation pairs can develop concurrently.
    """
    queue = compute_active_learning_queue(
        db=session,
        project_id=project_id,
        target_samples=target_samples,
        target_signers=target_signers,
        fake=fake,
        include_demo=include_demo,
    )
    return {
        "project_id": project_id,
        "formula_version": FORMULA_VERSION,
        "weights": DEFAULT_WEIGHTS,
        "queue": queue,
    }
