"""Проверки безопасного нагрузочного сценария публичного API"""

import httpx
import pytest

from scripts.load_public_api import (
    LoadConfig,
    Sample,
    build_scenarios,
    run_load,
    summarize,
    validate_config,
)


def test_remote_target_requires_explicit_permission() -> None:
    """Случайный запуск против удалённого сервера запрещён."""
    config = LoadConfig(base_url="https://example.org", stage_id=1)

    with pytest.raises(ValueError, match="удалённ"):
        validate_config(config)

    validate_config(LoadConfig(base_url="https://example.org", stage_id=1, allow_remote=True))


@pytest.mark.parametrize(
    "overrides",
    [
        {"users": 0},
        {"users": 5001},
        {"duration_seconds": 0},
        {"max_rps": 0},
        {"max_rps": float("inf")},
        {"duration_seconds": float("nan")},
        {"think_seconds": -1},
        {"think_seconds": float("inf")},
        {"stage_id": 0},
    ],
)
def test_invalid_load_limits_are_rejected(overrides: dict) -> None:
    """Ошибочные лимиты не запускают бесконтрольную нагрузку."""
    config = LoadConfig(base_url="http://127.0.0.1:8000", **{"stage_id": 1, **overrides})

    with pytest.raises(ValueError):
        validate_config(config)


def test_scenarios_cover_map_directory_and_results() -> None:
    """Сценарий обращается к публичным маршрутам без записи данных."""
    paths = {scenario.path for scenario in build_scenarios(7)}

    assert paths == {
        "/api/v1/map/participants?stage_id=7&limit=100&offset=0",
        "/api/v1/map/checkpoints?stage_id=7",
        "/api/v1/directory/stages",
        "/api/v1/results/standings",
    }


def test_summary_counts_failures_and_latency_percentiles() -> None:
    """Отчёт считает HTTP-ошибки, сетевые сбои и перцентили задержки."""
    samples = [
        Sample("map", 100.0, 200),
        Sample("map", 200.0, 503),
        Sample("results", 400.0, None),
    ]

    summary = summarize(samples, elapsed_seconds=2.0)

    assert summary.total_requests == 3
    assert summary.successful_requests == 1
    assert summary.failed_requests == 2
    assert summary.status_counts == {200: 1, 503: 1}
    assert summary.network_errors == 1
    assert summary.requests_per_second == 1.5
    assert summary.p50_ms == 200.0
    assert summary.p95_ms == 400.0


@pytest.mark.asyncio
async def test_preflight_stops_before_load_on_bad_response() -> None:
    """Недоступный маршрут останавливает прогон до запуска пользователей."""
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404)

    config = LoadConfig(base_url="http://127.0.0.1:8000", stage_id=1, duration_seconds=0.05)

    with pytest.raises(RuntimeError, match="Предварительн"):
        await run_load(config, transport=httpx.MockTransport(handle))

    assert len(requests) == 1


@pytest.mark.asyncio
async def test_load_uses_get_and_excludes_preflight_from_metrics() -> None:
    """Виртуальные пользователи читают API, а прогрев не портит метрики."""
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    config = LoadConfig(
        base_url="http://127.0.0.1:8000",
        stage_id=1,
        users=2,
        duration_seconds=0.05,
        max_rps=100,
        think_seconds=0,
    )
    report = await run_load(config, transport=httpx.MockTransport(handle))

    assert report.samples
    assert len(requests) == len(report.samples) + len(build_scenarios(1))
    assert all(request.method == "GET" for request in requests)
    assert summarize(report.samples, report.elapsed_seconds).failed_requests == 0


@pytest.mark.asyncio
async def test_shared_rate_limit_applies_to_all_users() -> None:
    """Все виртуальные пользователи делят один лимит запросов в секунду."""
    config = LoadConfig(
        base_url="http://127.0.0.1:8000",
        stage_id=1,
        users=4,
        duration_seconds=0.1,
        max_rps=1,
        think_seconds=0,
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))

    report = await run_load(config, transport=transport)

    assert len(report.samples) == 1
