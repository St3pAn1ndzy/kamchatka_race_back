from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_marks import (
    OfficialMarkCorrectRequest,
    OfficialMarkCreateRequest,
    OfficialMarkResponse,
)
from app.services.admin_marks import AdminMarkService

router = APIRouter(prefix="/marks", tags=["admin-marks"])
MarkId = Annotated[int, Path(gt=0)]


@router.post("", response_model=OfficialMarkResponse, status_code=status.HTTP_201_CREATED)
async def create_official_mark(
    body: OfficialMarkCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> OfficialMarkResponse:
    mark = await AdminMarkService(session).create(body, admin_id=admin.id)
    return OfficialMarkResponse.model_validate(mark)


@router.post("/{mark_id}/correct", response_model=OfficialMarkResponse)
async def correct_official_mark(
    mark_id: MarkId,
    body: OfficialMarkCorrectRequest,
    session: SessionDep,
    admin: AdminDep,
) -> OfficialMarkResponse:
    mark = await AdminMarkService(session).correct(mark_id, body, admin_id=admin.id)
    return OfficialMarkResponse.model_validate(mark)
