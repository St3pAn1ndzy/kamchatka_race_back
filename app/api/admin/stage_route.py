from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import AdminDep, SessionDep
from app.db.models.stage_route_point import StageRoutePoint
from app.schemas.admin_stage_route import (
    StageRoutePointResponse,
    StageRouteReplaceRequest,
    StageRouteResponse,
)
from app.services.admin_stage_route import AdminStageRouteService

router = APIRouter(prefix="/directory/stages", tags=["admin-stage-route"])
StageId = Annotated[int, Path(gt=0)]


def _response(stage_id: int, points: list[StageRoutePoint]) -> StageRouteResponse:
    return StageRouteResponse(
        stage_id=stage_id,
        points=[StageRoutePointResponse.model_validate(point) for point in points],
    )


@router.get("/{stage_id}/route", response_model=StageRouteResponse)
async def get_stage_route(
    stage_id: StageId,
    session: SessionDep,
    _admin: AdminDep,
) -> StageRouteResponse:
    points = await AdminStageRouteService(session).get_route(stage_id)
    return _response(stage_id, points)


@router.put("/{stage_id}/route", response_model=StageRouteResponse)
async def replace_stage_route(
    stage_id: StageId,
    body: StageRouteReplaceRequest,
    session: SessionDep,
    admin: AdminDep,
) -> StageRouteResponse:
    points = await AdminStageRouteService(session).replace_route(stage_id, body, admin_id=admin.id)
    return _response(stage_id, points)


@router.delete("/{stage_id}/route", status_code=status.HTTP_204_NO_CONTENT)
async def clear_stage_route(
    stage_id: StageId,
    session: SessionDep,
    admin: AdminDep,
) -> None:
    await AdminStageRouteService(session).clear_route(stage_id, admin_id=admin.id)
