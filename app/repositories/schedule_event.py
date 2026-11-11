from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.schedule_event import ScheduleEvent
from app.enums import ScheduleKind
from app.repositories.base import BaseRepository


class ScheduleEventRepository(BaseRepository[ScheduleEvent]):
    """Запросы к опубликованным событиям программы."""

    model = ScheduleEvent

    @staticmethod
    def _public_filters(
        *,
        kind: ScheduleKind | None,
        stage_id: int | None,
        starts_from: datetime | None,
        starts_to: datetime | None,
    ) -> tuple[ColumnElement[bool], ...]:
        """Сформировать одинаковые фильтры для списка и подсчёта."""
        filters: list[ColumnElement[bool]] = [ScheduleEvent.is_public.is_(True)]

        if kind is not None:
            filters.append(ScheduleEvent.kind == kind.value)

        if stage_id is not None:
            filters.append(ScheduleEvent.stage_id == stage_id)

        if starts_from is not None:
            filters.append(ScheduleEvent.starts_at >= starts_from)

        if starts_to is not None:
            filters.append(ScheduleEvent.starts_at <= starts_to)

        return tuple(filters)

    async def list_public(
        self,
        *,
        kind: ScheduleKind | None,
        stage_id: int | None,
        starts_from: datetime | None,
        starts_to: datetime | None,
        limit: int,
        offset: int,
    ) -> list[ScheduleEvent]:
        """Получить страницу опубликованных событий в хронологическом порядке."""
        filters = self._public_filters(
            kind=kind,
            stage_id=stage_id,
            starts_from=starts_from,
            starts_to=starts_to,
        )

        stmt = (
            select(ScheduleEvent)
            .where(*filters)
            .order_by(
                ScheduleEvent.starts_at.asc(),
                ScheduleEvent.id.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_public(
        self,
        *,
        kind: ScheduleKind | None,
        stage_id: int | None,
        starts_from: datetime | None,
        starts_to: datetime | None,
    ) -> int:
        """Посчитать опубликованные события с учётом фильтров."""
        filters = self._public_filters(
            kind=kind,
            stage_id=stage_id,
            starts_from=starts_from,
            starts_to=starts_to,
        )

        stmt = select(func.count(ScheduleEvent.id)).where(*filters)
        result = await self.session.execute(stmt)

        return int(result.scalar_one())

    async def get_public_by_id(
        self,
        event_id: int,
    ) -> ScheduleEvent | None:
        """Найти опубликованное событие по идентификатору."""
        stmt = select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.is_public.is_(True),
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
