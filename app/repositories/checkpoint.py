from sqlalchemy import select

from app.db.models.checkpoint import Checkpoint
from app.repositories.base import BaseRepository


class CheckpointRepository(BaseRepository[Checkpoint]):
    model = Checkpoint

    async def get_for_update(self, checkpoint_id: int) -> Checkpoint | None:
        stmt = select(Checkpoint).where(Checkpoint.id == checkpoint_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()
