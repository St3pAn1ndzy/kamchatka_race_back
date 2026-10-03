"""Судейские отметки в административном API"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, SessionDep
from app.db.models.audit_log import AuditLog
from app.db.models.checkpoint import Checkpoint
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.schemas.admin import (
    OfficialMarkCorrectRequest,
    OfficialMarkCreateRequest,
    OfficialMarkResponse,
)

router = APIRouter(prefix="/marks", tags=["admin-marks"])


@router.post("", response_model=OfficialMarkResponse)
async def create_official_mark(
    body: OfficialMarkCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> OfficialMarkResponse:
    """Создаём официальную отметку прохождения КП"""
    participant = await session.get(Participant, body.participant_id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Участник не найден",
        )

    checkpoint = await session.get(Checkpoint, body.checkpoint_id)
    if checkpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="КП не найден",
        )

    mark = OfficialMark(
        participant_id=body.participant_id,
        checkpoint_id=body.checkpoint_id,
        mark_time=body.mark_time,
        penalty_minutes=body.penalty_minutes,
        mandatory_stop_minutes=body.mandatory_stop_minutes,
        comment=body.comment,
        entered_by_admin_id=admin.id,
    )
    session.add(mark)
    await session.flush()

    # Пишем короткий след в аудит, чтобы потом было понятно кто внёс отметку
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="official_mark_created",
            entity_type="official_mark",
            entity_id=str(mark.id),
            payload={
                "participant_id": body.participant_id,
                "checkpoint_id": body.checkpoint_id,
                "mark_time": body.mark_time.isoformat(),
                "penalty_minutes": body.penalty_minutes,
                "mandatory_stop_minutes": body.mandatory_stop_minutes,
            },
        )
    )

    await session.commit()
    await session.refresh(mark)

    return OfficialMarkResponse.model_validate(mark)


@router.post("/{mark_id}/correct", response_model=OfficialMarkResponse)
async def correct_official_mark(
    mark_id: int,
    body: OfficialMarkCorrectRequest,
    session: SessionDep,
    admin: AdminDep,
) -> OfficialMarkResponse:
    """Исправляем судейскую отметку без удаления истории"""
    old_mark = await session.get(OfficialMark, mark_id)
    if old_mark is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отметка не найдена",
        )
    if old_mark.is_cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Отметка уже отменена",
        )

    old_mark.is_cancelled = True
    old_mark.cancel_reason = body.cancel_reason

    new_mark = OfficialMark(
        participant_id=old_mark.participant_id,
        checkpoint_id=old_mark.checkpoint_id,
        mark_time=body.mark_time,
        penalty_minutes=body.penalty_minutes,
        mandatory_stop_minutes=body.mandatory_stop_minutes,
        comment=body.comment,
        entered_by_admin_id=admin.id,
        cancels_mark_id=old_mark.id,
    )
    session.add(new_mark)
    await session.flush()

    # В аудите держим связь старой и новой отметки, чтобы разбор был понятным
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="official_mark_corrected",
            entity_type="official_mark",
            entity_id=str(new_mark.id),
            payload={
                "old_mark_id": old_mark.id,
                "new_mark_id": new_mark.id,
                "cancel_reason": body.cancel_reason,
                "mark_time": body.mark_time.isoformat(),
                "penalty_minutes": body.penalty_minutes,
                "mandatory_stop_minutes": body.mandatory_stop_minutes,
            },
        )
    )

    await session.commit()
    await session.refresh(new_mark)

    return OfficialMarkResponse.model_validate(new_mark)
