from pydantic import Field

from app.schemas.base import BaseSchema


class DeviceAssignRequest(BaseSchema):
    device_id: int = Field(gt=0)
    participant_id: int | None = Field(gt=0)
    stage_id: int | None = Field(gt=0)


class DeviceAssignResponse(BaseSchema):
    id: int
    iridium_number: str
    imei: str
    name: str
    participant_id: int | None
    stage_id: int | None
    is_active: bool
