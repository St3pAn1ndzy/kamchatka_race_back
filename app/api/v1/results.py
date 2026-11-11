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
    discipline_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
    season_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
) -> RaceStandings:
    """Сводная таблица лидеров по сумме опубликованных этапов.

    Учитываются этапы с publication=provisional|official.
    Draft-черновики не показываются.

    Опциональные фильтры:
    - `discipline_id` — показать только участников указанной дисциплины
    - `season_id` — показать этапы указанного сезона (по умолчанию активный сезон)
    """
    return await service.get_standings(
        discipline_id=discipline_id,
        season_id=season_id,
    )


@router.get(
    "/stage/{stage_id}",
    response_model=StageProtocol,
    summary="Протокол этапа",
    responses={
        404: {"description": "Этап не найден"},
    },
)
async def stage_protocol(
    stage_id: Annotated[int, Path(gt=0, le=MAX_ID)],
    service: ResultServiceDep,
    discipline_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
) -> StageProtocol:
    """Протокол этапа: участники, время, штрафы, обязательные остановки.

    Если этап существует, но результаты не опубликованы (draft),
    возвращается 200 с publication=draft и пустым rows.

    Опциональный фильтр:
    - `discipline_id` — показать только участников указанной дисциплины
    """
    protocol = await service.get_stage_protocol(stage_id, discipline_id=discipline_id)
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found",
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
    discipline_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
    season_id: Annotated[int | None, Query(gt=0, le=MAX_ID)] = None,
) -> list[LeaderboardEntry]:
    """Таблица лидеров.

    Опциональные фильтры:
    - `discipline_id` — показать только участников указанной дисциплины
    - `season_id` — показать этапы указанного сезона (по умолчанию активный сезон)
    """
    return await service.get_leaderboard(
        limit=limit,
        discipline_id=discipline_id,
        season_id=season_id,
    )


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
