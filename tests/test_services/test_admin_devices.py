from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.router import admin_router
from app.api.deps import require_admin
from app.db.base import get_session
from app.db.models.audit_log import AuditLog
from app.db.models.device import Device
from app.db.models.discipline import Discipline
from app.db.models.participant import Participant
from app.db.models.stage import Stage
from app.repositories.device import DeviceRepository
from app.schemas.admin_devices import DeviceAssignRequest
from app.services.admin_devices import AdminDeviceService


def _device(participant_id: int | None = None, stage_id: int | None = None) -> Device:
    return Device(
        id=1,
        iridium_number="001",
        imei="300234000000001",
        name="Tracker",
        participant_id=participant_id,
        stage_id=stage_id,
        is_active=True,
    )


def _service(
    device: Device | None = None,
) -> tuple[AdminDeviceService, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    service = AdminDeviceService(session)
    service.devices.get_for_update = AsyncMock(return_value=device)
    service.participants.get_by_id = AsyncMock(
        return_value=Participant(id=2, name="Racer", number=20, discipline_id=3)
    )
    service.stages.get_by_id = AsyncMock(return_value=Stage(id=4, name="Stage", season_id=5))
    service.disciplines.get_by_id = AsyncMock(
        return_value=Discipline(id=3, season_id=5, code="ski", name="Ski")
    )
    return service, session


def _body(participant_id: int | None = 2, stage_id: int | None = 4) -> DeviceAssignRequest:
    return DeviceAssignRequest(device_id=1, participant_id=participant_id, stage_id=stage_id)


def test_assign_endpoint_is_registered_and_protected() -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)

    path = "/api/v1/admin/devices/assign"
    assert "post" in app.openapi()["paths"][path]
    assert TestClient(app).post(path, json=_body().model_dump()).status_code == 401


def test_assign_endpoint_returns_updated_device(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=7)
    service = MagicMock()
    service.assign = AsyncMock(return_value=_device(participant_id=2, stage_id=4))
    monkeypatch.setattr("app.api.admin.devices.AdminDeviceService", lambda _: service)

    response = TestClient(app).post("/api/v1/admin/devices/assign", json=_body().model_dump())

    assert response.status_code == 200
    assert response.json()["participant_id"] == 2
    assert response.json()["stage_id"] == 4
    service.assign.assert_awaited_once_with(_body(), admin_id=7)


def test_assign_requires_explicit_assignment_fields() -> None:
    with pytest.raises(ValidationError):
        DeviceAssignRequest(device_id=1, participant_id=2)
    with pytest.raises(ValidationError):
        DeviceAssignRequest(device_id=1, participant_id=-2, stage_id=4)


@pytest.mark.asyncio
async def test_assign_locks_device_and_audits_change() -> None:
    service, session = _service(_device())

    device = await service.assign(_body(), admin_id=7)

    assert (device.participant_id, device.stage_id) == (2, 4)
    service.devices.get_for_update.assert_awaited_once_with(1)
    service.disciplines.get_by_id.assert_awaited_once_with(3)
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditLog)
    assert (audit.admin_id, audit.action, audit.entity_type, audit.entity_id) == (
        7,
        "device_assignment_changed",
        "device",
        "1",
    )
    assert audit.payload == {
        "old": {"participant_id": None, "stage_id": None},
        "new": {"participant_id": 2, "stage_id": 4},
    }
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(device)


@pytest.mark.asyncio
async def test_same_assignment_does_not_add_audit() -> None:
    service, session = _service(_device(participant_id=2, stage_id=4))

    await service.assign(_body(), admin_id=7)

    session.add.assert_not_called()
    session.commit.assert_awaited_once()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_nulls_unassign_device_with_audit() -> None:
    service, session = _service(_device(participant_id=2, stage_id=4))

    device = await service.assign(_body(None, None), admin_id=7)

    assert (device.participant_id, device.stage_id) == (None, None)
    assert session.add.call_args.args[0].payload == {
        "old": {"participant_id": 2, "stage_id": 4},
        "new": {"participant_id": None, "stage_id": None},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("device", "Трекер не найден"),
        ("participant", "Участник не найден"),
        ("stage", "Этап не найден"),
    ],
)
async def test_assign_rejects_missing_records(missing: str, message: str) -> None:
    service, session = _service(_device())
    if missing == "device":
        service.devices.get_for_update = AsyncMock(return_value=None)
    elif missing == "participant":
        service.participants.get_by_id = AsyncMock(return_value=None)
    else:
        service.stages.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as error:
        await service.assign(_body(), admin_id=7)

    assert error.value.status_code == 404
    assert error.value.detail == message
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_rejects_cross_season_participant() -> None:
    service, session = _service(_device())
    service.disciplines.get_by_id = AsyncMock(
        return_value=Discipline(id=3, season_id=6, code="ski", name="Ski")
    )

    with pytest.raises(HTTPException) as error:
        await service.assign(_body(), admin_id=7)

    assert error.value.status_code == 409
    assert error.value.detail == "Участник и этап относятся к разным сезонам"
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_device_lookup_uses_row_lock() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = _device()
    session.execute = AsyncMock(return_value=result)

    await DeviceRepository(session).get_for_update(1)

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
