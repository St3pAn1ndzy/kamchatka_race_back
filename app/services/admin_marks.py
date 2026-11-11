from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.official_mark import OfficialMark
from app.metrics import MARKS_CREATED
from app.repositories.checkpoint import CheckpointRepository
from app.repositories.discipline import DisciplineRepository
from app.repositories.official_mark import OfficialMarkRepository
from app.repositories.participant import ParticipantRepository
from app.repositories.stage import StageRepository
from app.schemas.admin_marks import OfficialMarkCorrectRequest, OfficialMarkCreateRequest
from app.services.cache import cache

_MARK_CONFLICTS = {
    "uq_official_marks_active_participant_checkpoint": "Действующая отметка уже существует",
    "official_marks_participant_id_fkey": "Участник больше не существует",
    "official_marks_checkpoint_id_fkey": "КП больше не существует",
    "official_marks_entered_by_admin_id_fkey": "Администратор больше не существует",
}


def _mark_conflict_detail(exc: IntegrityError) -> str | None:
    driver_error = exc.orig
    cause = driver_error.__cause__
    constraint_name = getattr(cause, "constraint_name", None) or getattr(
        driver_error, "constraint_name", None
    )
    return _MARK_CONFLICTS.get(constraint_name)


class AdminMarkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.marks = OfficialMarkRepository(session)
        self.checkpoints = CheckpointRepository(session)
        self.participants = ParticipantRepository(session)
        self.stages = StageRepository(session)
        self.disciplines = DisciplineRepository(session)

    async def _invalidate_results_cache(self, stage_id: int) -> None:
        """Сброс кэша результатов для указанного этапа и общих standings."""
        await cache.delete(f"public:results:stage:{stage_id}")
        await cache.delete("public:results:standings")
        await cache.invalidate_pattern("public:results:leaderboard:*")

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
        try:
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

            MARKS_CREATED.labels(stage_id=str(checkpoint.stage_id)).inc()
        except IntegrityError as exc:
            await self.session.rollback()
            detail = _mark_conflict_detail(exc)
            if detail is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc
            raise
        await self.session.refresh(mark)

        # Инвалидация кэша протокола для этапа, к которому относится КП
        await self._invalidate_results_cache(checkpoint.stage_id)

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
        try:
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
        except IntegrityError as exc:
            await self.session.rollback()
            detail = _mark_conflict_detail(exc)
            if detail is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, detail) from exc
            raise
        await self.session.refresh(new_mark)

        # Инвалидация кэша протокола для этапа, к которому относится КП
        await self._invalidate_results_cache(checkpoint.stage_id)

        return new_mark
