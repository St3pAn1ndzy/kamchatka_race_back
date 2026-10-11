from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.router import admin_router
from app.api.deps import require_admin
from app.db.base import get_session
from app.db.models.audit_log import AuditLog
from app.db.models.stage import Stage
from app.db.models.stage_route_point import StageRoutePoint
from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.admin_stage_route import AdminStageRouteService


def _point(position: int, lat: float, lon: float) -> StageRoutePoint:
    return StageRoutePoint(stage_id=1, position=position, lat=lat, lon=lon)


def _service(
    *, old_points: list[StageRoutePoint] | None = None, has_track_points: bool = False
) -> tuple[AdminStageRouteService, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    service = AdminStageRouteService(session)
    service.stages.get_for_update = AsyncMock(return_value=Stage(id=1, name="Stage"))
    service.stages.exists_by_id = AsyncMock(return_value=True)
    service.routes.list_for_stage = AsyncMock(return_value=old_points or [])
    service.routes.replace_for_stage = AsyncMock(return_value=[])
    service.track_points.exists_for_stage = AsyncMock(return_value=has_track_points)
    return service, session


def test_route_endpoints_are_registered() -> None:
    app = FastAPI()
    app.include_router(admin_router)
    path = "/api/v1/admin/directory/stages/{stage_id}/route"

    assert {"get", "put", "delete"} <= app.openapi()["paths"][path].keys()


def test_get_route_returns_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    app.dependency_overrides[require_admin] = lambda: object()
    service = MagicMock()
    service.get_route = AsyncMock(return_value=[_point(0, 53.0, 158.0)])
    monkeypatch.setattr("app.api.admin.stage_route.AdminStageRouteService", lambda _: service)

    response = TestClient(app).get("/api/v1/admin/directory/stages/1/route")

    assert response.status_code == 200
    assert response.json() == {
        "stage_id": 1,
        "points": [{"lat": 53.0, "lon": 158.0, "position": 0}],
    }
    service.get_route.assert_awaited_once_with(1)


def test_put_route_rejects_empty_points(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_session] = lambda: MagicMock(spec=AsyncSession)
    app.dependency_overrides[require_admin] = lambda: object()
    service = MagicMock()
    service.replace_route = AsyncMock()
    monkeypatch.setattr("app.api.admin.stage_route.AdminStageRouteService", lambda _: service)

    response = TestClient(app).put("/api/v1/admin/directory/stages/1/route", json={"points": []})

    assert response.status_code == 422
    service.replace_route.assert_not_awaited()


@pytest.mark.parametrize(
    "points",
    [
        [{"lat": 0, "lon": 0}],
        [{"lat": 91, "lon": 0}, {"lat": 0, "lon": 1}],
        [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 0}],
    ],
)
def test_route_rejects_invalid_points(points: list[dict[str, float]]) -> None:
    with pytest.raises(ValidationError):
        StageRouteReplaceRequest(points=points)


@pytest.mark.asyncio
async def test_get_route_returns_ordered_points() -> None:
    points = [_point(0, 53.0, 158.0), _point(1, 53.1, 158.1)]
    service, _ = _service(old_points=points)

    assert await service.get_route(1) == points
    service.stages.exists_by_id.assert_awaited_once_with(1)
    service.routes.list_for_stage.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_route_rejects_missing_stage() -> None:
    service, _ = _service()
    service.stages.exists_by_id = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as error:
        await service.get_route(1)

    assert error.value.status_code == 404
    service.routes.list_for_stage.assert_not_awaited()


@pytest.mark.asyncio
async def test_replace_route_saves_points_and_audit_in_one_transaction() -> None:
    service, session = _service(old_points=[_point(0, 53.0, 158.0)])
    saved = [_point(0, 53.1, 158.1), _point(1, 53.2, 158.2)]
    service.routes.replace_for_stage = AsyncMock(return_value=saved)
    body = StageRouteReplaceRequest(
        points=[{"lat": 53.1, "lon": 158.1}, {"lat": 53.2, "lon": 158.2}]
    )

    assert await service.replace_route(1, body, admin_id=7) == saved

    service.stages.get_for_update.assert_awaited_once_with(1)
    service.track_points.exists_for_stage.assert_awaited_once_with(1)
    service.routes.replace_for_stage.assert_awaited_once_with(1, [(53.1, 158.1), (53.2, 158.2)])
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditLog)
    assert audit.admin_id == 7
    assert audit.action == "stage_route_replaced"
    assert audit.payload == {
        "old": [{"lat": 53.0, "lon": 158.0}],
        "new": [{"lat": 53.1, "lon": 158.1}, {"lat": 53.2, "lon": 158.2}],
    }
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_route_rejects_missing_stage() -> None:
    service, session = _service()
    service.stages.get_for_update = AsyncMock(return_value=None)
    body = StageRouteReplaceRequest(points=[{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}])

    with pytest.raises(HTTPException) as error:
        await service.replace_route(1, body, admin_id=7)

    assert error.value.status_code == 404
    service.routes.replace_for_stage.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_replace_route_rejects_stage_with_track_points() -> None:
    service, session = _service(has_track_points=True)
    body = StageRouteReplaceRequest(points=[{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}])

    with pytest.raises(HTTPException) as error:
        await service.replace_route(1, body, admin_id=7)

    assert error.value.status_code == 409
    service.routes.replace_for_stage.assert_not_awaited()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_replacing_identical_route_does_not_write_audit() -> None:
    old = [_point(0, 53, 158), _point(1, 54, 159)]
    service, session = _service(old_points=old, has_track_points=True)
    body = StageRouteReplaceRequest(points=[{"lat": 53, "lon": 158}, {"lat": 54, "lon": 159}])

    assert await service.replace_route(1, body, admin_id=7) == old
    service.track_points.exists_for_stage.assert_not_awaited()
    service.routes.replace_for_stage.assert_not_awaited()
    session.add.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_route_saves_empty_list_and_audit() -> None:
    service, session = _service(old_points=[_point(0, 53, 158)])

    await service.clear_route(1, admin_id=7)

    service.routes.replace_for_stage.assert_awaited_once_with(1, [])
    audit = session.add.call_args.args[0]
    assert audit.action == "stage_route_cleared"
    assert audit.payload == {"old": [{"lat": 53, "lon": 158}], "new": []}
    session.commit.assert_awaited_once()
