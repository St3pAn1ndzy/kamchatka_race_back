"""Репозиторий раздела «Гостям»."""

from sqlalchemy import select

from app.db.models.guest_item import GuestItem
from app.repositories.base import BaseRepository


class GuestItemRepository(BaseRepository[GuestItem]):
    model = GuestItem

    async def list_by_section(self, section: str) -> list[GuestItem]:
        stmt = (
            select(GuestItem)
            .where(
                GuestItem.section == section,
                GuestItem.is_public.is_(True),
            )
            .order_by(GuestItem.order_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())
