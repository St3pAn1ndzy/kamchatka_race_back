from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.official_mark import OfficialMark
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.discipline import DisciplineRepository
from app.repositories.official_mark import OfficialMarkRepository
from app.repositories.participant import ParticipantRepository
from app.repositories.stage import StageRepository
from app.schemas.admin_marks import OfficialMarkCorrectRequest, OfficialMarkCreateRequest


class AdminMarkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.marks = OfficialMarkRepository(session)
        self.checkpoints = CheckpointRepository(session)
        self.participants = ParticipantRepository(session)
        self.stages = StageRepository(session)
        self.disciplines = DisciplineRepository(session)

    async def create(self, body: OfficialMarkCreateRequest, *, admin_id: int) -> OfficialMark:
        participant = await self.participants.get_by_id(body.participant_id)
        if participant is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Участник не найден")

        checkpoint = await self.checkpoints.get_for_update(body.checkpoint_id)
        if checkpoint is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "КП не найден")

        stage = await self.stages.get_by_id(checkpoint.stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Этап не найден")
        if participant.discipline_id is not None and stage.season_id is not None:
            discipline = await self.disciplines.get_by_id(participant.discipline_id)
            if discipline is None or discipline.season_id != stage.season_id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Участник и КП относятся к разным сезонам",
                )

        if await self.marks.get_active(body.participant_id, body.checkpoint_id) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Действующая отметка уже существует")

        mark = OfficialMark(
            participant_id=body.participant_id,
            checkpoint_id=body.checkpoint_id,
            mark_time=body.mark_time,
            penalty_minutes=body.penalty_minutes,
            mandatory_stop_minutes=body.mandatory_stop_minutes,
            comment=body.comment,
            entered_by_admin_id=admin_id,
        )
        self.marks.add(mark)
        await self.session.flush()
        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action="official_mark_created",
                entity_type="official_mark",
                entity_id=str(mark.id),
                payload={
                    "participant_id": mark.participant_id,
                    "checkpoint_id": mark.checkpoint_id,
                    "mark_time": mark.mark_time.isoformat(),
                    "penalty_minutes": mark.penalty_minutes,
                    "mandatory_stop_minutes": mark.mandatory_stop_minutes,
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(mark)
        return mark

    async def correct(
        self,
        mark_id: int,
        body: OfficialMarkCorrectRequest,
        *,
        admin_id: int,
    ) -> OfficialMark:
        original = await self.marks.get_by_id(mark_id)
        if original is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Отметка не найдена")

        # И создание, и исправление берут блокировку КП в одном порядке
        checkpoint = await self.checkpoints.get_for_update(original.checkpoint_id)
        if checkpoint is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "КП не найден")

        old_mark = await self.marks.get_for_update(mark_id)
        if old_mark is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Отметка не найдена")
        if old_mark.is_cancelled:
            raise HTTPException(status.HTTP_409_CONFLICT, "Отметка уже отменена")

        old_payload = {
            "mark_id": old_mark.id,
            "mark_time": old_mark.mark_time.isoformat(),
            "penalty_minutes": old_mark.penalty_minutes,
            "mandatory_stop_minutes": old_mark.mandatory_stop_minutes,
            "comment": old_mark.comment,
        }
        old_mark.is_cancelled = True
        old_mark.cancel_reason = body.cancel_reason
        # Освобождаем место в частичном уникальном индексе до вставки замены
        await self.session.flush()

        new_mark = OfficialMark(
            participant_id=old_mark.participant_id,
            checkpoint_id=old_mark.checkpoint_id,
            mark_time=body.mark_time,
            penalty_minutes=body.penalty_minutes,
            mandatory_stop_minutes=body.mandatory_stop_minutes,
            comment=body.comment,
            entered_by_admin_id=admin_id,
            cancels_mark_id=old_mark.id,
        )
        self.marks.add(new_mark)
        await self.session.flush()
        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action="official_mark_corrected",
                entity_type="official_mark",
                entity_id=str(new_mark.id),
                payload={
                    "old": old_payload,
                    "new": {
                        "mark_id": new_mark.id,
                        "mark_time": new_mark.mark_time.isoformat(),
                        "penalty_minutes": new_mark.penalty_minutes,
                        "mandatory_stop_minutes": new_mark.mandatory_stop_minutes,
                        "comment": new_mark.comment,
                    },
                    "cancel_reason": body.cancel_reason,
                },
            )
        )
        await self.session.commit()
        await self.session.refresh(new_mark)
        return new_mark
