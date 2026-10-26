"""Проверки управления состоянием гонки и сохранения истории изменений"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.race_status import RaceStatus
from app.enums import RaceState
from app.services.admin_race import AdminRaceService


def _service(current=None):
    """Подменяет только доступ к хранилищу, сохраняя настоящую логику сервиса"""
    session = MagicMock(spec=AsyncSession)
    service = AdminRaceService(session)
    service.stages.exists_by_id = AsyncMock(return_value=True)
    service.race_statuses.get_current = AsyncMock(return_value=current)
    service.race_statuses.flush = AsyncMock()
    return service, session


async def test_missing_stage_does_not_change_race_or_write_audit():
    """Несуществующий этап возвращает 404 до изменения гонки и записи аудита"""
    service, session = _service()
    service.stages.exists_by_id.return_value = False

    with pytest.raises(HTTPException) as error:
        await service.update_status(admin_id=7, status=RaceState.LIVE, current_stage_id=42)

    assert error.value.status_code == 404
    service.race_statuses.get_current.assert_not_awaited()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


async def test_first_status_is_created_with_admin_audit_before_commit():
    """Первый статус сохраняется вместе с автором и новыми значениями в аудите"""
    service, session = _service()
    current = RaceStatus(id=1, status="live", current_stage_id=42)
    service.race_statuses.create_current = MagicMock(return_value=current)

    async def commit():
        audit = session.add.call_args.args[0]
        assert isinstance(audit, AuditLog)
        assert audit.admin_id == 7
        assert audit.action == "race_status_created"
        assert audit.entity_type == "race_status"
        assert audit.entity_id == "1"
        assert audit.payload == {
            "old": None,
            "new": {"status": "live", "current_stage_id": 42},
        }

    session.commit.side_effect = commit

    result = await service.update_status(admin_id=7, status=RaceState.LIVE, current_stage_id=42)

    assert result is current
    service.stages.exists_by_id.assert_awaited_once_with(42)
    service.race_statuses.create_current.assert_called_once_with(
        status=RaceState.LIVE, current_stage_id=42
    )
    service.race_statuses.flush.assert_awaited_once()
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(current)


async def test_status_update_keeps_previous_values_in_audit():
    """Изменение существующей гонки сохраняет старые и новые значения в аудите"""
    current = RaceStatus(id=1, status="upcoming", current_stage_id=None)
    service, session = _service(current)

    async def update(record, *, status, current_stage_id):
        record.status = status.value
        record.current_stage_id = current_stage_id
        return record

    service.race_statuses.update_current = AsyncMock(side_effect=update)

    result = await service.update_status(admin_id=7, status=RaceState.LIVE, current_stage_id=42)

    assert result is current
    audit = session.add.call_args.args[0]
    assert audit.action == "race_status_updated"
    assert audit.admin_id == 7
    assert audit.entity_id == "1"
    assert audit.payload == {
        "old": {"status": "upcoming", "current_stage_id": None},
        "new": {"status": "live", "current_stage_id": 42},
    }
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(current)


async def test_finishing_without_stage_does_not_query_stage_repository():
    """Завершение гонки без текущего этапа не требует поиска этапа"""
    current = RaceStatus(id=1, status="finished", current_stage_id=None)
    service, session = _service()
    service.race_statuses.create_current = MagicMock(return_value=current)

    await service.update_status(admin_id=7, status=RaceState.FINISHED, current_stage_id=None)

    service.stages.exists_by_id.assert_not_awaited()
    assert session.add.call_args.args[0].payload["new"] == {
        "status": "finished",
        "current_stage_id": None,
    }
    session.commit.assert_awaited_once()
