from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.db.models import Discipline, Season, Stage
from app.schemas.public_directory import (
    DisciplinePublicResponse,
    SeasonPublicResponse,
    StagePublicResponse,
)
from app.services.public_directory import PublicDirectoryService

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get("/stages", response_model=list[StagePublicResponse])
async def list_stages(
    session: SessionDep,
    season_id: int | None = Query(default=None, gt=0),
) -> list[Stage]:
    service = PublicDirectoryService(session)
    stages = await service.list_stages(season_id=season_id)
    return stages


@router.get("/disciplines", response_model=list[DisciplinePublicResponse])
async def list_disciplines(
    session: SessionDep,
    season_id: int | None = Query(default=None, gt=0),
) -> list[Discipline]:
    service = PublicDirectoryService(session)
    disciplines = await service.list_disciplines(season_id=season_id)

    return disciplines


@router.get("/seasons/active", response_model=SeasonPublicResponse)
async def get_active_season(session: SessionDep) -> Season:
    service = PublicDirectoryService(session)
    season = await service.get_active_season()
    if season is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Активный сезон не найден")
    return season
