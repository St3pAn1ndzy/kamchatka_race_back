"""Атомарная замена маршрутов и КП нескольких этапов"""

from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.checkpoint import Checkpoint
from app.db.models.official_mark import OfficialMark
from app.db.models.stage import Stage
from app.db.models.stage_route_point import StageRoutePoint
from app.db.models.track_point import TrackPoint
from app.enums import CheckpointKind
from app.services.cache import cache
from app.services.tracking_metrics import _distance_km, route_progress_km


class ImportSelection(BaseModel):
    """Явно выбранный этап, направление линии и типы контрольных пунктов"""

    model_config = ConfigDict(extra="forbid")
    stage_id: int = Field(gt=0, le=2147483647)
    reverse: StrictBool
    direction_confirmed: StrictBool
    kinds: list[CheckpointKind] = Field(max_length=100)


class RaceRouteImportService:
    """Проверяет весь пакет до первой замены и сохраняет одной транзакцией"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self, lines: list[dict], mapping: list[dict], *, admin_id: int, file_hash: str
    ) -> list[int]:
        selections = [ImportSelection.model_validate(item) for item in mapping]
        ids = [s.stage_id for s in selections]
        if not lines or len(lines) != len(selections) or len(set(ids)) != len(ids):
            raise HTTPException(422, "Сопоставьте каждую линию отдельному этапу")
        if not all(s.direction_confirmed for s in selections):
            raise HTTPException(422, "Подтвердите направление каждого этапа")
        stages = list(
            await self.session.scalars(
                select(Stage).where(Stage.id.in_(ids)).order_by(Stage.id).with_for_update()
            )
        )
        if len(stages) != len(ids):
            raise HTTPException(404, "Один из этапов не найден")
        if len({s.season_id for s in stages}) != 1 or stages[0].season_id is None:
            raise HTTPException(422, "Этапы должны принадлежать одному сезону")
        if any(s.status != "planned" for s in stages):
            raise HTTPException(409, "Импорт разрешён только для запланированных этапов")
        if (
            await self.session.scalar(
                select(TrackPoint.id).where(TrackPoint.stage_id.in_(ids)).limit(1)
            )
            is not None
        ):
            raise HTTPException(409, "У этапов уже есть GPS-точки")
        old_cps = list(
            await self.session.scalars(
                select(Checkpoint)
                .where(Checkpoint.stage_id.in_(ids))
                .order_by(Checkpoint.id)
                .with_for_update()
            )
        )
        if (
            old_cps
            and await self.session.scalar(
                select(OfficialMark.id)
                .where(OfficialMark.checkpoint_id.in_([c.id for c in old_cps]))
                .limit(1)
            )
            is not None
        ):
            raise HTTPException(409, "У КП есть судейские отметки, включая отменённые")
        prepared = {}
        for line, selection in zip(lines, selections, strict=True):
            if len(selection.kinds) != len(line["checkpoints"]):
                raise HTTPException(422, "Задайте тип каждого контрольного пункта")
            points = list(reversed(line["points"])) if selection.reverse else line["points"]
            geometry = [SimpleNamespace(**p) for p in points]
            distance = sum(
                _distance_km(a.lat, a.lon, b.lat, b.lon)
                for a, b in zip(geometry, geometry[1:], strict=False)
            )
            cps = []
            for cp, kind in zip(line["checkpoints"], selection.kinds, strict=True):
                if (
                    cp["elevation"] is not None
                    and not -2147483648 <= round(cp["elevation"]) <= 2147483647
                ):
                    raise HTTPException(422, "Высота КП выходит за допустимый диапазон INTEGER")
                km = route_progress_km(geometry, cp["lat"], cp["lon"])
                if km is None:
                    raise HTTPException(422, "КП находится дальше одного километра от линии")
                if kind in {CheckpointKind.START, CheckpointKind.FINISH}:
                    endpoint = geometry[0] if kind == CheckpointKind.START else geometry[-1]
                    if _distance_km(cp["lat"], cp["lon"], endpoint.lat, endpoint.lon) > 0.2:
                        raise HTTPException(422, "КП старта или финиша не совпадает с концом линии")
                    km = 0.0 if kind == CheckpointKind.START else distance
                cps.append((km, cp, kind))
            prepared[selection.stage_id] = (points, sorted(cps, key=lambda c: c[0]), distance)
        season_stages = list(
            await self.session.scalars(
                select(Stage)
                .where(Stage.season_id == stages[0].season_id)
                .order_by(Stage.order_index, Stage.number, Stage.id)
            )
        )
        offsets, accumulated = {}, 0.0
        for stage in season_stages:
            offsets[stage.id] = accumulated
            accumulated += prepared[stage.id][2] if stage.id in prepared else stage.distance_km
        # Сдвиг километража неприменимых к пакету КП не должен происходить незаметно
        first_selected = next(i for i, stage in enumerate(season_stages) if stage.id in ids)
        for stage in season_stages[first_selected:]:
            if stage.id not in ids:
                raise HTTPException(422, "Сопоставьте также все последующие этапы сезона")
        by_id = {s.id: s for s in stages}
        try:
            for stage_id, (points, cps, distance) in prepared.items():
                await self.session.execute(
                    delete(StageRoutePoint).where(StageRoutePoint.stage_id == stage_id)
                )
                await self.session.execute(
                    delete(Checkpoint).where(Checkpoint.stage_id == stage_id)
                )
                rows = [{"stage_id": stage_id, "position": i, **p} for i, p in enumerate(points)]
                for start in range(0, len(rows), 1000):
                    await self.session.execute(insert(StageRoutePoint), rows[start : start + 1000])
                for i, (km, cp, kind) in enumerate(cps):
                    self.session.add(
                        Checkpoint(
                            stage_id=stage_id,
                            code=f"КП-{i + 1}",
                            name=cp["name"],
                            kind=kind.value,
                            lat=cp["lat"],
                            lon=cp["lon"],
                            altitude=round(cp["elevation"])
                            if cp["elevation"] is not None
                            else None,
                            km_from_race_start=offsets[stage_id] + km,
                            order_index=i,
                            has_judge=False,
                            is_public=True,
                        )
                    )
                by_id[stage_id].distance_km = distance
                self.session.add(
                    AuditLog(
                        admin_id=admin_id,
                        action="race_route_imported",
                        entity_type="stage",
                        entity_id=str(stage_id),
                        payload={
                            "file_sha256": file_hash,
                            "points": len(points),
                            "checkpoints": len(cps),
                        },
                    )
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                409, "Данные изменились во время импорта, повторите предпросмотр"
            ) from exc
        for stage_id in ids:
            await cache.delete(f"public:map:route:{stage_id}")
            await cache.delete(f"public:map:checkpoint:{stage_id}")
        await cache.invalidate_pattern("public:stages:*")
        return ids
