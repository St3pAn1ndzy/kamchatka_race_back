"""Справочники гонки в административном API"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import AdminDep, SessionDep
from app.schemas.admin_directory import (
    DisciplineCreateRequest,
    DisciplineResponse,
    DisciplineUpdateRequest,
    SeasonCreateRequest,
    SeasonResponse,
    SeasonUpdateRequest,
    StageAdminResponse,
    StageCreateRequest,
    StageUpdateRequest,
)
from app.services.admin_directory import AdminDirectoryService

router = APIRouter(prefix="/directory", tags=["admin-directory"])


@router.get("/seasons", response_model=list[SeasonResponse])
async def list_seasons(
    session: SessionDep,
    _admin: AdminDep,
) -> list[SeasonResponse]:
    service = AdminDirectoryService(session)
    seasons = await service.list_seasons()
    return [SeasonResponse.model_validate(season) for season in seasons]


@router.post(
    "/seasons",
    response_model=SeasonResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_season(
    body: SeasonCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> SeasonResponse:
    service = AdminDirectoryService(session)
    season = await service.create_season(body, admin_id=admin.id)
    return SeasonResponse.model_validate(season)


@router.patch("/seasons/{season_id}", response_model=SeasonResponse)
async def update_season(
    season_id: Annotated[int, Path(gt=0)],
    body: SeasonUpdateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> SeasonResponse:
    service = AdminDirectoryService(session)
    season = await service.update_season(season_id, body, admin_id=admin.id)
    return SeasonResponse.model_validate(season)


@router.get("/disciplines", response_model=list[DisciplineResponse])
async def list_disciplines(
    session: SessionDep,
    _admin: AdminDep,
    season_id: int | None = Query(default=None, gt=0),
) -> list[DisciplineResponse]:
    service = AdminDirectoryService(session)
    disciplines = await service.list_disciplines(season_id=season_id)
    return [DisciplineResponse.model_validate(discipline) for discipline in disciplines]


@router.post(
    "/disciplines",
    response_model=DisciplineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_discipline(
    body: DisciplineCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> DisciplineResponse:
    service = AdminDirectoryService(session)
    discipline = await service.create_discipline(body, admin_id=admin.id)
    return DisciplineResponse.model_validate(discipline)


@router.patch("/disciplines/{discipline_id}", response_model=DisciplineResponse)
async def update_discipline(
    discipline_id: Annotated[int, Path(gt=0)],
    body: DisciplineUpdateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> DisciplineResponse:
    service = AdminDirectoryService(session)
    discipline = await service.update_discipline(discipline_id, body, admin_id=admin.id)
    return DisciplineResponse.model_validate(discipline)


@router.get("/stages", response_model=list[StageAdminResponse])
async def list_stages(
    session: SessionDep,
    _admin: AdminDep,
    season_id: int | None = Query(default=None, gt=0),
) -> list[StageAdminResponse]:
    service = AdminDirectoryService(session)
    stages = await service.list_stages(season_id=season_id)
    return [StageAdminResponse.model_validate(stage) for stage in stages]


@router.post(
    "/stages",
    response_model=StageAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stage(
    body: StageCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> StageAdminResponse:
    service = AdminDirectoryService(session)
    stage = await service.create_stage(body, admin_id=admin.id)
    return StageAdminResponse.model_validate(stage)


@router.patch("/stages/{stage_id}", response_model=StageAdminResponse)
async def update_stage(
    stage_id: Annotated[int, Path(gt=0)],
    body: StageUpdateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> StageAdminResponse:
    service = AdminDirectoryService(session)
    stage = await service.update_stage(stage_id, body, admin_id=admin.id)
    return StageAdminResponse.model_validate(stage)
