from datetime import datetime

from pydantic import Field

from app.enums import StageStatus
from app.schemas.base import BaseSchema


class SeasonCreateRequest(BaseSchema):
    year: int = Field(ge=2000, le=2100)
    title: str = Field(min_length=1, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = False


class SeasonUpdateRequest(BaseSchema):
    year: int | None = Field(default=None, ge=2000, le=2100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class SeasonResponse(BaseSchema):
    id: int
    year: int
    title: str
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool


class DisciplineCreateRequest(BaseSchema):
    season_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = 0
    is_active: bool = True


class DisciplineUpdateRequest(BaseSchema):
    season_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    is_active: bool | None = None


class DisciplineResponse(BaseSchema):
    id: int
    season_id: int
    code: str
    name: str
    sort_order: int
    is_active: bool


class StageCreateRequest(BaseSchema):
    season_id: int = Field(gt=0)
    number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    distance_km: float = Field(default=0.0, ge=0)
    start_time: datetime | None = None
    finish_time: datetime | None = None
    order_index: int = 0
    tracker_interval_seconds: int = Field(default=1200, ge=15, le=86400)
    status: StageStatus = StageStatus.PLANNED


class StageUpdateRequest(BaseSchema):
    season_id: int | None = Field(default=None, gt=0)
    number: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    distance_km: float | None = Field(default=None, ge=0)
    start_time: datetime | None = None
    finish_time: datetime | None = None
    order_index: int | None = None
    tracker_interval_seconds: int | None = Field(default=None, ge=15, le=86400)
    status: StageStatus | None = None


class StageAdminResponse(BaseSchema):
    id: int
    season_id: int | None
    number: int
    name: str
    distance_km: float
    start_time: datetime | None
    finish_time: datetime | None
    order_index: int
    tracker_interval_seconds: int
    status: StageStatus
