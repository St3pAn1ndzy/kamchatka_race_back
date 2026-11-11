"""Согласованный километраж этапов и КП после изменения геометрии"""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.checkpoint import Checkpoint
from app.db.models.season import Season
from app.db.models.stage import Stage


async def lock_route_seasons(session: AsyncSession, stage_ids: list[int]) -> None:
    """Сериализует изменения маршрутов одного сезона до блокировки отдельных этапов"""
    await session.scalars(
        select(Season.id)
        .where(Season.id.in_(select(Stage.season_id).where(Stage.id.in_(stage_ids))))
        .order_by(Season.id)
        .with_for_update()
    )


async def update_route_distances(
    session: AsyncSession, stages: Sequence[Stage], distances: dict[int, float]
) -> dict[int, float]:
    """Обновляет длины и сдвигает километраж следующих КП, сохраняя их идентификаторы"""
    season_ids = {stage.season_id for stage in stages if stage.season_id is not None}
    offsets = {stage.id: 0.0 for stage in stages}
    if season_ids:
        ordered = await session.scalars(
            select(Stage)
            .where(Stage.season_id.in_(season_ids))
            .order_by(Stage.season_id, Stage.order_index, Stage.number, Stage.id)
        )
        current_season, old_total, new_total = None, 0.0, 0.0
        for stage in ordered:
            if stage.season_id != current_season:
                current_season, old_total, new_total = stage.season_id, 0.0, 0.0
            offsets[stage.id] = new_total
            delta = new_total - old_total
            if stage.id not in distances and delta:
                await session.execute(
                    update(Checkpoint)
                    .where(Checkpoint.stage_id == stage.id)
                    .values(km_from_race_start=Checkpoint.km_from_race_start + delta)
                )
            old_total += stage.distance_km
            new_total += distances.get(stage.id, stage.distance_km)
    for stage in stages:
        stage.distance_km = distances[stage.id]
    return offsets
