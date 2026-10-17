"""Репозиторий участников."""

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import selectinload

from app.db.models.fun_subscription import FanSubscription
from app.db.models.participant import Participant
from app.enums import ParticipantStatus
from app.repositories.base import BaseRepository


class ParticipantRepository(BaseRepository[Participant]):
    model = Participant

    async def list_for_map(
        self,
        *,
        discipline_ids: list[int] | None,
        participant_ids: list[int] | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[Participant], int]:
        filters = []
        if discipline_ids is not None:
            filters.append(Participant.discipline_id.in_(discipline_ids))
        if participant_ids is not None:
            filters.append(Participant.id.in_(participant_ids))
        if not filters:
            return [], 0

        total = int(
            (
                await self.session.execute(select(func.count(Participant.id)).where(*filters))
            ).scalar_one()
        )
        stmt = (
            select(Participant)
            .options(selectinload(Participant.discipline_ref))
            .where(*filters)
            .order_by(Participant.number, Participant.id)
            .limit(limit)
            .offset(offset)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    @staticmethod
    def _supporters_subquery():
        """Подзапрос: participant_id → число болельщиков."""
        return (
            select(
                FanSubscription.participant_id.label("pid"),
                func.count(FanSubscription.id).label("cnt"),
            )
            .group_by(FanSubscription.participant_id)
            .subquery()
        )

    async def list_filtered(
        self,
        *,
        search: str | None = None,
        discipline_id: int | None = None,
        status: ParticipantStatus | None = None,
        sort: str = "bib",
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[Participant, int]]:
        """Список участников с числом болельщиков. Один SQL-запрос, без N+1."""
        subq = self._supporters_subquery()
        stmt = (
            select(Participant, func.coalesce(subq.c.cnt, 0).label("cnt"))
            .options(selectinload(Participant.discipline_ref))
            .outerjoin(subq, Participant.id == subq.c.pid)
        )

        if search:
            stmt = stmt.where(Participant.name.ilike(f"%{search}%"))
        if discipline_id is not None:
            stmt = stmt.where(Participant.discipline_id == discipline_id)
        if status is not None:
            stmt = stmt.where(Participant.status == status.value)

        if sort == "name":
            stmt = stmt.order_by(asc(Participant.name))
        elif sort == "supporters":
            stmt = stmt.order_by(desc("cnt"), asc(Participant.number))
        else:  # bib
            stmt = stmt.order_by(asc(Participant.number))

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [(row[0], int(row[1] or 0)) for row in result.all()]

    async def count_filtered(
        self,
        *,
        search: str | None = None,
        discipline_id: int | None = None,
        status: ParticipantStatus | None = None,
    ) -> int:
        """Общее число участников с фильтрами (для пагинации)."""
        stmt = select(func.count(Participant.id))
        if search:
            stmt = stmt.where(Participant.name.ilike(f"%{search}%"))
        if discipline_id is not None:
            stmt = stmt.where(Participant.discipline_id == discipline_id)
        if status is not None:
            stmt = stmt.where(Participant.status == status.value)
        return int((await self.session.execute(stmt)).scalar_one())

    async def get_with_supporters_count(
        self,
        participant_id: int,
    ) -> tuple[Participant, int] | None:
        """Карточка участника + число болельщиков одним запросом."""
        subq = self._supporters_subquery()
        stmt = (
            select(Participant, func.coalesce(subq.c.cnt, 0).label("cnt"))
            .options(selectinload(Participant.discipline_ref))
            .outerjoin(subq, Participant.id == subq.c.pid)
            .where(Participant.id == participant_id)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return row[0], int(row[1] or 0)
