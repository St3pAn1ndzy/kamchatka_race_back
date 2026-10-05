"""Схемы для управления гонкой в админке"""

from datetime import datetime

from pydantic import Field

from app.enums import RaceState
from app.schemas.base import BaseSchema


class RaceStatusUpdateRequest(BaseSchema):
    """Данные для смены текущего состояния гонки"""

    status: RaceState
    current_stage_id: int | None = Field(default=None, gt=0)


class RaceStatusResponse(BaseSchema):
    """Текущее состояние гонки для админки"""

    id: int
    status: RaceState
    current_stage_id: int | None = None
    updated_at: datetime
