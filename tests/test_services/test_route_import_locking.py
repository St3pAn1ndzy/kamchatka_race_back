"""Проверка согласованных блокировок импорта и расчёта GPS на PostgreSQL"""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.season import Season
from app.db.models.stage import Stage
from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.services.tracking_metrics import TrackingMetricsService


async def test_metrics_wait_for_route_replacement(engine):
    """Расчёт GPS ждёт импорта и использует новую геометрию после его commit"""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as setup:
        season = Season(year=2199, title="Проверка блокировок")
        setup.add(season)
        await setup.flush()
        stage = Stage(season_id=season.id, name="Тест", number=1)
        setup.add(stage)
        await setup.flush()
        setup.add_all(
            [
                StageRoutePoint(stage_id=stage.id, position=i, lat=53, lon=158 + i * 0.01)
                for i in range(2)
            ]
        )
        await setup.commit()
    task = None
    try:
        async with sessions() as importer, sessions() as gps:
            await importer.scalar(select(Stage).where(Stage.id == stage.id).with_for_update())
            point = TrackPoint(
                device_id=999999,
                participant_id=None,
                stage_id=stage.id,
                lat=54,
                lon=159.005,
                recorded_at=datetime.now(UTC),
            )
            task = asyncio.create_task(TrackingMetricsService(gps).fill_metrics(point))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), timeout=0.2)
            await importer.execute(
                delete(StageRoutePoint).where(StageRoutePoint.stage_id == stage.id)
            )
            importer.add_all(
                [
                    StageRoutePoint(stage_id=stage.id, position=i, lat=54, lon=159 + i * 0.01)
                    for i in range(2)
                ]
            )
            await importer.commit()
            await asyncio.wait_for(task, timeout=3)
            assert point.km_from_start is not None
            assert point.km_from_start > 0
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with sessions() as cleanup:
            await cleanup.execute(delete(Stage).where(Stage.id == stage.id))
            await cleanup.execute(delete(Season).where(Season.id == season.id))
            await cleanup.commit()
