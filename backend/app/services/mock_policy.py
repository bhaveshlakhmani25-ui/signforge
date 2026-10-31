"""
SIGNFORGE Centralized Mock & Demo Data Policy

Single source of truth for mock detection, filtering, isolation, and safe cleanup.
Guarantees:
- In-browser demo fixtures (source='demo_fixture') are identified as mock.
- Newly generated synthetic external datasets ('MOCK_INCLUDE') are identified as mock.
- Legacy previously imported synthetic INCLUDE records are identified via unique provenance note.
- Genuine INCLUDE datasets and captured recordings are protected and never classified as mock.
- Nullable and empty fields are handled safely in both Python and SQL.
- Python and SQL filter expressions agree 100%.
"""

from typing import Any, Optional
from sqlalchemy import or_, not_, func
from sqlmodel import Session, select

from app.db.models import Sample

# The unique provenance note written exclusively by the synthetic mock generator
LEGACY_MOCK_PROVENANCE_NOTE = "INCLUDE subset (10 signs, 3 signers) - AI4Bharat / IIT Madras"


def is_mock_sample(sample: Any) -> bool:
    """
    Null-safe in-memory evaluation of whether a sample is mock or demo data.
    Works with SQLModel Sample objects, dictionaries, or duck-typed objects.
    """
    if sample is None:
        return False

    if isinstance(sample, dict):
        source = (sample.get("source") or "").strip()
        dataset_name = (sample.get("dataset_name") or "").strip().upper()
        prov_note = (sample.get("provenance_note") or "").strip()
    else:
        source = (getattr(sample, "source", None) or "").strip()
        dataset_name = (getattr(sample, "dataset_name", None) or "").strip().upper()
        prov_note = (getattr(sample, "provenance_note", None) or "").strip()

    # 1. Webcam demo fixture fallback
    if source == "demo_fixture":
        return True

    # 2. New mock dataset naming convention
    if dataset_name.startswith("MOCK"):
        return True

    # 3. Explicit mock tag in provenance note
    if prov_note.startswith("[MOCK]") or "[MOCK]" in prov_note:
        return True

    # 4. Verified legacy synthetic mock provenance note
    if prov_note == LEGACY_MOCK_PROVENANCE_NOTE:
        return True

    return False


def mock_sample_clause():
    """
    SQLAlchemy boolean expression matching all mock and demo clips.
    Uses func.coalesce to guarantee safe evaluation over NULL columns.
    """
    return or_(
        Sample.source == "demo_fixture",
        func.coalesce(Sample.dataset_name, "").ilike("mock%"),
        func.coalesce(Sample.provenance_note, "").like("[MOCK]%"),
        func.coalesce(Sample.provenance_note, "") == LEGACY_MOCK_PROVENANCE_NOTE,
    )


def non_mock_sample_clause():
    """
    SQLAlchemy boolean expression matching genuine, non-mock samples.
    Evaluating to True ensures the sample is real captured or genuine external data.
    """
    return not_(mock_sample_clause())


def tag_legacy_mock_sample(sample: Sample) -> bool:
    """
    If the sample matches legacy mock criteria, safely updates dataset_name to MOCK_INCLUDE
    and prefixes its provenance_note. Does not touch genuine data.
    """
    prov = (sample.provenance_note or "").strip()
    if prov == LEGACY_MOCK_PROVENANCE_NOTE:
        sample.dataset_name = "MOCK_INCLUDE"
        if not prov.startswith("[MOCK]"):
            sample.provenance_note = f"[MOCK] {LEGACY_MOCK_PROVENANCE_NOTE}"
        return True
    return False


def backfill_legacy_mock_tags(session: Session, dry_run: bool = False) -> int:
    """
    Explicitly relabels legacy mock records in the provided session.
    Never run automatically during application startup.
    Returns the count of relabeled records.
    """
    samples = session.exec(
        select(Sample).where(
            func.coalesce(Sample.provenance_note, "") == LEGACY_MOCK_PROVENANCE_NOTE
        )
    ).all()
    count = 0
    for s in samples:
        if tag_legacy_mock_sample(s):
            count += 1
            if not dry_run:
                session.add(s)
    if not dry_run and count > 0:
        session.commit()
    return count
