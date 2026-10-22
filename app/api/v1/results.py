"""Результаты гонки: протоколы, сводная, таблица лидеров, отметки.

Официальные результаты — только из OfficialMark (требование брифа).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import ResultServiceDep
from app.schemas.results import (
    ControlTimeEntry,
    LeaderboardEntry,
    RaceStandings,
    StageProtocol,
)

router = APIRouter(prefix="/results", tags=["results"])

# Константа для максимального ID (INTEGER в Postgres)
MAX_ID = 2147483647


@router.get(
    "/standings",
    response_model=RaceStandings,
    summary="Сводная таблица лидеров (официальная)",
)
async def standings(
    service: ResultServiceDep,
) -> RaceStandings:
    """Сводная таблица лидеров по сумме опубликованных этапов.

    Учитываются этапы с publication=provisional|official.
    Draft-черновики не показываются.
    """
    return await service.get_standings()


@router.get(
    "/stage/{stage_id}",
    response_model=StageProtocol,
    summary="Протокол этапа",
)
async def stage_protocol(
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    service: ResultServiceDep,
) -> StageProtocol:
    """Протокол этапа: участники, время, штрафы, обязательные остановки."""
    protocol = await service.get_stage_protocol(stage_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found or results are in draft",
        )
    return protocol


@router.get(
    "/leaderboard",
    response_model=list[LeaderboardEntry],
    summary="Таблица лидеров",
)
async def leaderboard(
    service: ResultServiceDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[LeaderboardEntry]:
    """Таблица лидеров."""
    return await service.get_leaderboard(limit=limit)


@router.get(
    "/entry/{participant_id}/control-times",
    response_model=list[ControlTimeEntry],
    summary="Отметки участника на контрольных пунктах",
)
async def control_times(
    participant_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    service: ResultServiceDep,
    stage_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
) -> list[ControlTimeEntry]:
    """Все отметки участника на КП (по этапу или по всем)."""
    return await service.get_control_times(participant_id, stage_id=stage_id)
