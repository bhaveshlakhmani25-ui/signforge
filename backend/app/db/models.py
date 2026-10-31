from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    target_language: str
    domain: str = ""
    created_at: datetime = Field(default_factory=now)


class SignClass(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    gloss: str
    prompt_text: str = ""
    dialect_note: str = ""
    active: bool = True


class Signer(SQLModel, table=True):
    """Pseudonymous only: no real name is ever stored."""
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    code: str = Field(index=True)
    handedness: Optional[str] = None  # only if volunteered
    created_at: datetime = Field(default_factory=now)


class ConsentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    signer_id: int = Field(foreign_key="signer.id", index=True)
    consent_version: str
    purpose: str
    allowed_uses: list[str] = Field(sa_column=Column(JSON))
    retention: str  # e.g. "landmarks_only"
    raw_video_retained: bool = False
    status: str = "active"  # active | withdrawn
    created_at: datetime = Field(default_factory=now)


class Sample(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    sign_class_id: int = Field(foreign_key="signclass.id", index=True)
    signer_id: int = Field(foreign_key="signer.id", index=True)
    consent_id: int = Field(foreign_key="consentrecord.id")
    source: str  # captured | public_dataset | demo_fixture
    feature_path: str = ""
    feature_schema_version: str
    extractor: str
    extractor_model_sha: str = ""
    fps: float
    width: int
    height: int
    mirrored: bool = False
    frame_count: int
    quality_score: float  # landmark completeness: share of frames with body + at least one hand
    qc_passed: bool
    quality_flags: list[dict] = Field(sa_column=Column(JSON))
    qc_metrics: dict = Field(sa_column=Column(JSON))
    feature_sha256: str = Field(index=True)  # exact-duplicate detection
    review_status: str = "pending_review"  # pending_review | approved | rejected | needs_recapture (human only)
    split: str = "unassigned"
    collection_round: int = 0
    raw_video_retained: bool = False
    provenance_note: str = ""
    # Provenance fields for external datasets (e.g. INCLUDE) and multi-source traceability
    dataset_name: str = ""
    dataset_version: str = ""
    dataset_license: str = ""
    citation: str = ""
    external_sample_id: str = ""
    external_signer_id: str = ""
    external_split: str = ""
    created_at: datetime = Field(default_factory=now)


class ReviewEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="sample.id", index=True)
    reviewer_code: str
    reviewer_role: str  # native_signer | deaf_community_member | interpreter | team_non_signer (self-declared)
    decision: str  # approved | rejected | needs_recapture
    note: str = ""
    created_at: datetime = Field(default_factory=now)


class ModelRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    model_kind: str  # baseline | transfer
    pool: str  # real | demo (DEMO DATA runs are never mixed with real evaluation)
    status: str = "running"  # running | succeeded | failed
    failure_detail: str = ""
    checkpoint_reference: str = "none (random initialisation)"
    weights_path: str = ""
    feature_schema_version: str
    preprocessing: dict = Field(sa_column=Column(JSON))
    data_version: str = ""
    split_strategy: str = ""
    train_sample_ids: list[int] = Field(sa_column=Column(JSON))
    test_sample_ids: list[int] = Field(sa_column=Column(JSON))
    seed: int
    config: dict = Field(sa_column=Column(JSON))
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))
    duration_s: float = 0.0
    created_at: datetime = Field(default_factory=now)
