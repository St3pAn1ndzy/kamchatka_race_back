"""Read-only сервис для экрана «Результаты»."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.checkpoint import Checkpoint
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.stage import Stage


@dataclass
class StageProtocol:
    stage_id: int
    stage_name: str
    stage_number: int
    results_publication: str
    marks: list  # list[MarkRow]


@dataclass
class MarkRow:
    participant_number: int
    participant_name: str
    checkpoint_code: str
    mark_time: str
    penalty_minutes: int
    mandatory_stop_minutes: int
    is_official: bool


class AdminResultsService:
    """Протоколы этапов."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stages(self) -> list[StageProtocol]:
        stmt = select(Stage).order_by(Stage.number)
        stages = (await self.session.execute(stmt)).scalars().all()

        result = []
        for s in stages:
            marks_stmt = (
                select(OfficialMark, Participant, Checkpoint)
                .join(Participant, OfficialMark.participant_id == Participant.id)
                .join(Checkpoint, OfficialMark.checkpoint_id == Checkpoint.id)
                .where(Checkpoint.stage_id == s.id, OfficialMark.is_cancelled.is_(False))
                .order_by(Participant.number, Checkpoint.order_index)
                .options(
                    selectinload(OfficialMark.participant),
                    selectinload(OfficialMark.checkpoint),
                )
            )
            mark_rows = (await self.session.execute(marks_stmt)).all()

            marks = [
                MarkRow(
                    participant_number=om.participant.number,
                    participant_name=om.participant.name,
                    checkpoint_code=cp.code,
                    mark_time=om.mark_time.isoformat() if om.mark_time else "",
                    penalty_minutes=om.penalty_minutes,
                    mandatory_stop_minutes=om.mandatory_stop_minutes,
                    is_official=not om.is_cancelled,
                )
                for om, p, cp in mark_rows
            ]

            result.append(
                StageProtocol(
                    stage_id=s.id,
                    stage_name=s.name,
                    stage_number=s.number,
                    results_publication=s.results_publication,
                    marks=marks,
                )
            )
        return result
