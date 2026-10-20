from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from app.schemas.base import BaseSchema

CancelReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class OfficialMarkCreateRequest(BaseSchema):
    participant_id: int = Field(gt=0)
    checkpoint_id: int = Field(gt=0)
    mark_time: AwareDatetime
    penalty_minutes: int = Field(default=0, ge=0)
    mandatory_stop_minutes: int = Field(default=0, ge=0)
    comment: str | None = Field(default=None, max_length=2000)


class OfficialMarkCorrectRequest(BaseSchema):
    mark_time: AwareDatetime
    penalty_minutes: int = Field(default=0, ge=0)
    mandatory_stop_minutes: int = Field(default=0, ge=0)
    comment: str | None = Field(default=None, max_length=2000)
    cancel_reason: CancelReason | None = None


class OfficialMarkResponse(BaseSchema):
    id: int
    participant_id: int
    checkpoint_id: int
    mark_time: datetime
    penalty_minutes: int
    mandatory_stop_minutes: int
    comment: str | None
    entered_by_admin_id: int
    created_at: datetime
    is_cancelled: bool
    cancel_reason: str | None
    cancels_mark_id: int | None
