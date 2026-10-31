from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Num = Annotated[float, Field(allow_inf_nan=False)]
PosePoint = Annotated[list[Num], Field(min_length=4, max_length=4)]  # x, y, z, visibility
HandPoint = Annotated[list[Num], Field(min_length=3, max_length=3)]  # x, y, z

ALLOWED_USES = {"corpus_building", "model_training", "research_publication", "public_release"}
REVIEWER_ROLES = Literal["native_signer", "deaf_community_member", "interpreter", "team_non_signer"]
# Pseudonymous codes only; the pattern is there to discourage typing a real name.
SignerCode = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,15}$")]


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_language: str = Field(min_length=1, max_length=50)
    domain: str = ""


class SignClassIn(BaseModel):
    project_id: int
    gloss: str = Field(min_length=1, max_length=50)
    prompt_text: str = ""
    dialect_note: str = ""


class SignerIn(BaseModel):
    project_id: int
    code: SignerCode
    handedness: Optional[Literal["left", "right", "both"]] = None


class ConsentIn(BaseModel):
    signer_id: int
    consent_version: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    allowed_uses: list[str] = Field(min_length=1)
    retention: Literal["landmarks_only"]  # raw-video retention is not supported in this MVP
    confirmed: Literal[True]

    @field_validator("allowed_uses")
    @classmethod
    def known_uses(cls, v):
        unknown = set(v) - ALLOWED_USES
        if unknown:
            raise ValueError(f"unknown allowed_uses: {sorted(unknown)}")
        return sorted(set(v))


class Frame(BaseModel):
    t: Num = Field(ge=0)
    pose: Optional[Annotated[list[PosePoint], Field(min_length=33, max_length=33)]] = None
    left_hand: Optional[Annotated[list[HandPoint], Field(min_length=21, max_length=21)]] = None
    right_hand: Optional[Annotated[list[HandPoint], Field(min_length=21, max_length=21)]] = None


class CaptureIn(BaseModel):
    project_id: int
    sign_class_id: int
    signer_id: int
    consent_id: int
    source: Literal["captured", "demo_fixture"]
    extractor: str = Field(min_length=1, max_length=100)
    extractor_model_sha: str = ""
    fps: Num = Field(gt=0, le=120)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mirrored: Literal[False] = False  # D4: stored coordinates must be un-mirrored
    frames: list[Frame] = Field(max_length=1200)

    @model_validator(mode="after")
    def increasing_time(self):
        ts = [f.t for f in self.frames]
        if any(b < a for a, b in zip(ts, ts[1:])):
            raise ValueError("frame timestamps must be non-decreasing")
        return self


class ReviewIn(BaseModel):
    reviewer_code: SignerCode
    reviewer_role: REVIEWER_ROLES
    decision: Literal["approved", "rejected", "needs_recapture"]
    note: str = Field(default="", max_length=1000)
