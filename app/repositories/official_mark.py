"""Репозиторий судейских отметок."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.checkpoint import Checkpoint
from app.db.models.official_mark import OfficialMark
from app.repositories.base import BaseRepository


class OfficialMarkRepository(BaseRepository[OfficialMark]):
    model = OfficialMark

    async def get_active(self, participant_id: int, checkpoint_id: int) -> OfficialMark | None:
        stmt = (
            select(OfficialMark)
            .where(
                OfficialMark.participant_id == participant_id,
                OfficialMark.checkpoint_id == checkpoint_id,
                OfficialMark.is_cancelled.is_(False),
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_update(self, mark_id: int) -> OfficialMark | None:
        stmt = select(OfficialMark).where(OfficialMark.id == mark_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_stage(
        self,
        stage_id: int,
        *,
        include_cancelled: bool = False,
    ) -> list[OfficialMark]:
        """Все отметки на этапе с подгрузкой КП и участника.

        По умолчанию без отменённых (is_cancelled=False).
        """
        stmt = (
            select(OfficialMark)
            .join(Checkpoint, OfficialMark.checkpoint_id == Checkpoint.id)
            .where(Checkpoint.stage_id == stage_id)
            .options(
                selectinload(OfficialMark.checkpoint),
                selectinload(OfficialMark.participant),
            )
            .order_by(OfficialMark.participant_id, OfficialMark.mark_time)
        )
        if not include_cancelled:
            stmt = stmt.where(OfficialMark.is_cancelled.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_participant(
        self,
        participant_id: int,
        stage_id: int | None = None,
        *,
        include_cancelled: bool = False,
    ) -> list[OfficialMark]:
        """Отметки участника. Если stage_id=None — по всем этапам."""
        stmt = (
            select(OfficialMark)
            .join(Checkpoint, OfficialMark.checkpoint_id == Checkpoint.id)
            .where(OfficialMark.participant_id == participant_id)
            .options(selectinload(OfficialMark.checkpoint))
        )
        if stage_id is not None:
            stmt = stmt.where(Checkpoint.stage_id == stage_id)
        if not include_cancelled:
            stmt = stmt.where(OfficialMark.is_cancelled.is_(False))
        stmt = stmt.order_by(OfficialMark.mark_time)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_for_race(
        self,
        *,
        include_cancelled: bool = False,
    ) -> list[OfficialMark]:
        """Все отметки по всем этапам (для расчёта сводной)."""
        stmt = (
            select(OfficialMark)
            .join(Checkpoint, OfficialMark.checkpoint_id == Checkpoint.id)
            .options(
                selectinload(OfficialMark.checkpoint),
                selectinload(OfficialMark.participant),
            )
            .order_by(OfficialMark.participant_id, OfficialMark.mark_time)
        )
        if not include_cancelled:
            stmt = stmt.where(OfficialMark.is_cancelled.is_(False))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
