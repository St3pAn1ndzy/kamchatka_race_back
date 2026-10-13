from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateIndex

from app.api.admin.router import admin_router
from app.api.deps import require_admin
from app.db.base import get_session
from app.db.models.audit_log import AuditLog
from app.db.models.checkpoint import Checkpoint
from app.db.models.discipline import Discipline
from app.db.models.official_mark import OfficialMark
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.schemas.admin_marks import OfficialMarkCorrectRequest, OfficialMarkCreateRequest
from app.services.admin_marks import AdminMarkService

MARK_TIME = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def _create_body() -> OfficialMarkCreateRequest:
    return OfficialMarkCreateRequest(
        participant_id=2,
        checkpoint_id=3,
        mark_time=MARK_TIME,
        penalty_minutes=5,
        mandatory_stop_minutes=2,
        comment="Judge",
    )


def _correct_body(reason: str = "  Ошибка времени  ") -> OfficialMarkCorrectRequest:
    return OfficialMarkCorrectRequest(
        mark_time=MARK_TIME,
        penalty_minutes=3,
        mandatory_stop_minutes=1,
        comment="Correction",
        cancel_reason=reason,
    )


def _old_mark() -> OfficialMark:
    return OfficialMark(
        id=11,
        participant_id=2,
        checkpoint_id=3,
        mark_time=MARK_TIME,
        penalty_minutes=5,
        mandatory_stop_minutes=2,
        comment="Judge",
        entered_by_admin_id=6,
        is_cancelled=False,
    )


def _service() -> tuple[AdminMarkService, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    service = AdminMarkService(session)
    service.participants.get_by_id = AsyncMock(
        return_value=Participant(id=2, name="Racer", number=20, discipline_id=4)
    )
    service.checkpoints.get_for_update = AsyncMock(
        return_value=Checkpoint(id=3, stage_id=5, code="CP", name="CP", lat=0, lon=0)
    )
    service.stages.get_by_id = AsyncMock(return_value=Stage(id=5, name="Stage", season_id=7))
    service.disciplines.get_by_id = AsyncMock(
        return_value=Discipline(id=4, season_id=7, code="ski", name="Ski")
    )
    service.marks.get_active = AsyncMock(return_value=None)
    service.marks.get_by_id = AsyncMock(return_value=_old_mark())
    service.marks.get_for_update = AsyncMock(return_value=_old_mark())

    def add_mark(mark: OfficialMark) -> OfficialMark:
        mark.id = 12
        session.add(mark)
        return mark

    service.marks.add = MagicMock(side_effect=add_mark)
    return service, session


def test_mark_endpoints_are_registered_and_protected() -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    paths = app.openapi()["paths"]

    assert paths["/api/v1/admin/marks"]["post"]["responses"].get("201")
    assert "post" in paths["/api/v1/admin/marks/{mark_id}/correct"]
    response = TestClient(app).post(
        "/api/v1/admin/marks", json=_create_body().model_dump(mode="json")
    )
    assert response.status_code == 401


def test_create_endpoint_returns_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=7)
    service = MagicMock()
    mark = _old_mark()
    mark.created_at = MARK_TIME
    service.create = AsyncMock(return_value=mark)
    monkeypatch.setattr("app.api.admin.marks.AdminMarkService", lambda _: service)

    response = TestClient(app).post(
        "/api/v1/admin/marks", json=_create_body().model_dump(mode="json")
    )

    assert response.status_code == 201
    assert response.json()["id"] == 11
    service.create.assert_awaited_once_with(_create_body(), admin_id=7)


def test_correct_endpoint_returns_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=7)
    service = MagicMock()
    mark = _old_mark()
    mark.id = 12
    mark.cancels_mark_id = 11
    mark.created_at = MARK_TIME
    service.correct = AsyncMock(return_value=mark)
    monkeypatch.setattr("app.api.admin.marks.AdminMarkService", lambda _: service)

    response = TestClient(app).post(
        "/api/v1/admin/marks/11/correct",
        json=_correct_body().model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["cancels_mark_id"] == 11
    service.correct.assert_awaited_once_with(11, _correct_body(), admin_id=7)


def test_mark_input_requires_aware_time_and_reason() -> None:
    with pytest.raises(ValidationError):
        OfficialMarkCreateRequest(
            participant_id=2, checkpoint_id=3, mark_time="2026-10-12T12:00:00"
        )
    with pytest.raises(ValidationError):
        OfficialMarkCreateRequest(
            participant_id=2, checkpoint_id=3, mark_time=MARK_TIME, penalty_minutes=-1
        )
    with pytest.raises(ValidationError):
        _correct_body("   ")


@pytest.mark.asyncio
async def test_create_writes_mark_and_audit_in_one_transaction() -> None:
    service, session = _service()

    mark = await service.create(_create_body(), admin_id=7)

    assert mark.id == 12
    service.checkpoints.get_for_update.assert_awaited_once_with(3)
    service.marks.get_active.assert_awaited_once_with(2, 3)
    added = [call.args[0] for call in session.add.call_args_list]
    assert added[0] is mark
    audit = added[1]
    assert isinstance(audit, AuditLog)
    assert (audit.admin_id, audit.action, audit.entity_id) == (7, "official_mark_created", "12")
    assert audit.payload["checkpoint_id"] == 3
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(mark)


@pytest.mark.asyncio
async def test_create_rejects_existing_active_mark() -> None:
    service, session = _service()
    service.marks.get_active = AsyncMock(return_value=_old_mark())

    with pytest.raises(HTTPException) as error:
        await service.create(_create_body(), admin_id=7)

    assert error.value.status_code == 409
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["participant", "checkpoint", "stage"])
async def test_create_rejects_missing_records(missing: str) -> None:
    service, session = _service()
    if missing == "participant":
        service.participants.get_by_id = AsyncMock(return_value=None)
    elif missing == "checkpoint":
        service.checkpoints.get_for_update = AsyncMock(return_value=None)
    else:
        service.stages.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.create(_create_body(), admin_id=7)

    assert error.value.status_code == 404
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rejects_cross_season_mark() -> None:
    service, session = _service()
    service.disciplines.get_by_id = AsyncMock(
        return_value=Discipline(id=4, season_id=8, code="ski", name="Ski")
    )

    with pytest.raises(HTTPException) as error:
        await service.create(_create_body(), admin_id=7)

    assert error.value.status_code == 409
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_correction_cancels_old_mark_before_inserting_new() -> None:
    service, session = _service()
    old = _old_mark()
    service.marks.get_by_id = AsyncMock(return_value=old)
    service.marks.get_for_update = AsyncMock(return_value=old)
    operations: list[tuple[str, bool]] = []

    def add_mark(mark: OfficialMark) -> OfficialMark:
        operations.append(("add", old.is_cancelled))
        mark.id = 12
        session.add(mark)
        return mark

    def flush() -> None:
        operations.append(("flush", old.is_cancelled))

    service.marks.add = MagicMock(side_effect=add_mark)
    session.flush = AsyncMock(side_effect=flush)

    new = await service.correct(11, _correct_body(), admin_id=7)

    assert operations == [("flush", True), ("add", True), ("flush", True)]
    assert old.cancel_reason == "Ошибка времени"
    assert new.id == 12
    assert new.cancels_mark_id == 11
    assert new.entered_by_admin_id == 7
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditLog)
    assert audit.action == "official_mark_corrected"
    assert audit.payload["old"]["mark_id"] == 11
    assert audit.payload["new"]["mark_id"] == 12
    assert audit.payload["cancel_reason"] == "Ошибка времени"
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(new)


@pytest.mark.asyncio
async def test_correction_rejects_cancelled_mark() -> None:
    service, session = _service()
    cancelled = _old_mark()
    cancelled.is_cancelled = True
    service.marks.get_for_update = AsyncMock(return_value=cancelled)

    with pytest.raises(HTTPException) as error:
        await service.correct(11, _correct_body(), admin_id=7)

    assert error.value.status_code == 409
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_correction_rejects_missing_mark() -> None:
    service, session = _service()
    service.marks.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.correct(11, _correct_body(), admin_id=7)

    assert error.value.status_code == 404
    service.checkpoints.get_for_update.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_active_mark_index_excludes_cancelled_history() -> None:
    index = next(
        index
        for index in OfficialMark.__table__.indexes
        if index.name == "uq_official_marks_active_participant_checkpoint"
    )
    sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))

    assert "UNIQUE INDEX" in sql
    assert "(participant_id, checkpoint_id)" in sql
    assert "WHERE is_cancelled = false" in sql
