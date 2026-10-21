"""Ограниченная нагрузочная проверка публичного API на локальном стенде.

Пример:
    poetry run python -m scripts.load_public_api --stage-id 1 --users 100 --duration 60
"""

import argparse
import asyncio
import math
import random
import time
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class LoadConfig:
    base_url: str
    stage_id: int
    users: int = 50
    duration_seconds: float = 30.0
    max_rps: float = 20.0
    think_seconds: float = 1.0
    allow_remote: bool = False


@dataclass(frozen=True)
class Scenario:
    name: str
    path: str


@dataclass(frozen=True)
class Sample:
    scenario: str
    elapsed_ms: float
    status_code: int | None


@dataclass(frozen=True)
class LoadReport:
    samples: list[Sample]
    elapsed_seconds: float


@dataclass(frozen=True)
class Summary:
    total_requests: int
    successful_requests: int
    failed_requests: int
    status_counts: dict[int, int]
    network_errors: int
    requests_per_second: float
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None


def validate_config(config: LoadConfig) -> None:
    """Проверяет адрес стенда и жёсткие ограничения генератора нагрузки."""
    parsed = urlsplit(config.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Укажите полный HTTP-адрес стенда")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("Базовый адрес должен содержать только схему, хост и порт")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and not config.allow_remote:
        raise ValueError("Для удалённого стенда требуется --allow-remote")
    if config.stage_id < 1:
        raise ValueError("Номер этапа должен быть положительным")
    if not 1 <= config.users <= 5000:
        raise ValueError("Число пользователей должно быть от 1 до 5000")
    if not 0 < config.duration_seconds <= 600:
        raise ValueError("Длительность должна быть от 0 до 600 секунд")
    if not 0 < config.max_rps <= 1000:
        raise ValueError("Лимит запросов должен быть от 0 до 1000 RPS")
    if not 0 <= config.think_seconds <= 60:
        raise ValueError("Пауза пользователя должна быть от 0 до 60 секунд")


def build_scenarios(stage_id: int) -> tuple[Scenario, ...]:
    """Возвращает только публичные маршруты чтения."""
    return (
        Scenario(
            "Участники на карте",
            f"/api/v1/map/participants?stage_id={stage_id}&limit=100&offset=0",
        ),
        Scenario("Контрольные пункты", f"/api/v1/map/checkpoints?stage_id={stage_id}"),
        Scenario("Список этапов", "/api/v1/directory/stages"),
        Scenario("Сводные результаты", "/api/v1/results/standings"),
    )


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percent) - 1]


def summarize(samples: list[Sample], elapsed_seconds: float) -> Summary:
    """Считает пропускную способность, ошибки и задержки всех ответов."""
    successful = sum(
        sample.status_code is not None and 200 <= sample.status_code < 300 for sample in samples
    )
    latencies = [sample.elapsed_ms for sample in samples]
    return Summary(
        total_requests=len(samples),
        successful_requests=successful,
        failed_requests=len(samples) - successful,
        status_counts=dict(
            sorted(Counter(sample.status_code for sample in samples if sample.status_code).items())
        ),
        network_errors=sum(sample.status_code is None for sample in samples),
        requests_per_second=len(samples) / elapsed_seconds if elapsed_seconds > 0 else 0.0,
        p50_ms=_percentile(latencies, 0.50),
        p95_ms=_percentile(latencies, 0.95),
        p99_ms=_percentile(latencies, 0.99),
    )


class _Pacer:
    def __init__(self, max_rps: float) -> None:
        self._interval = 1 / max_rps
        self._next_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self, deadline: float) -> bool:
        """Резервирует один слот, не ставя запросы за пределами прогона."""
        async with self._lock:
            now = asyncio.get_running_loop().time()
            slot = max(now, self._next_at)
            if slot >= deadline:
                return False
            self._next_at = slot + self._interval
        await asyncio.sleep(max(0.0, slot - now))
        return asyncio.get_running_loop().time() < deadline


async def run_load(
    config: LoadConfig, *, transport: httpx.AsyncBaseTransport | None = None
) -> LoadReport:
    """Прогревает маршруты и запускает ограниченные чтения до срока."""
    validate_config(config)
    scenarios = build_scenarios(config.stage_id)
    samples: list[Sample] = []
    limits = httpx.Limits(
        max_connections=min(config.users, 500),
        max_keepalive_connections=min(config.users, 100),
    )
    async with httpx.AsyncClient(
        base_url=config.base_url,
        timeout=10,
        limits=limits,
        transport=transport,
    ) as client:
        for scenario in scenarios:
            try:
                response = await client.get(scenario.path)
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Предварительная проверка {scenario.name} не прошла: {exc}"
                ) from exc
            if not 200 <= response.status_code < 300:
                raise RuntimeError(
                    f"Предварительная проверка {scenario.name} вернула HTTP {response.status_code}"
                )

        pacer = _Pacer(config.max_rps)
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = started + config.duration_seconds

        async def user_run(user_id: int) -> None:
            rng = random.Random(user_id)
            if config.think_seconds:
                await asyncio.sleep(rng.random() * config.think_seconds)
            request_index = 0
            while await pacer.wait(deadline):
                scenario = scenarios[(user_id + request_index) % len(scenarios)]
                request_index += 1
                request_started = time.perf_counter()
                try:
                    response = await client.get(scenario.path)
                    status_code = response.status_code
                except httpx.RequestError:
                    status_code = None
                samples.append(
                    Sample(
                        scenario=scenario.name,
                        elapsed_ms=(time.perf_counter() - request_started) * 1000,
                        status_code=status_code,
                    )
                )
                if config.think_seconds:
                    await asyncio.sleep(config.think_seconds * rng.uniform(0.5, 1.5))

        await asyncio.gather(*(user_run(user_id) for user_id in range(config.users)))
        elapsed = loop.time() - started
    return LoadReport(samples=samples, elapsed_seconds=elapsed)


def _format_latency(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} мс"


def print_report(report: LoadReport) -> None:
    """Печатает общий итог и отдельные показатели каждого маршрута."""
    all_summary = summarize(report.samples, report.elapsed_seconds)
    print(f"Длительность: {report.elapsed_seconds:.1f} с")
    print(
        f"Запросы: {all_summary.total_requests}, ошибки: {all_summary.failed_requests}, "
        f"скорость: {all_summary.requests_per_second:.1f} RPS"
    )
    print(
        f"Задержка: p50 {_format_latency(all_summary.p50_ms)}, "
        f"p95 {_format_latency(all_summary.p95_ms)}, "
        f"p99 {_format_latency(all_summary.p99_ms)}"
    )
    statuses = ", ".join(
        f"{status}: {count}" for status, count in all_summary.status_counts.items()
    )
    print(f"HTTP: {statuses or 'нет'}, сетевые ошибки: {all_summary.network_errors}")
    for name in sorted({sample.scenario for sample in report.samples}):
        route_samples = [sample for sample in report.samples if sample.scenario == name]
        route = summarize(route_samples, report.elapsed_seconds)
        print(
            f"{name}: {route.total_requests} запросов, {route.failed_requests} ошибок, "
            f"p95 {_format_latency(route.p95_ms)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--stage-id", type=int, required=True)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--max-rps", type=float, default=20.0)
    parser.add_argument("--think-seconds", type=float, default=1.0)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    config = LoadConfig(
        base_url=args.base_url,
        stage_id=args.stage_id,
        users=args.users,
        duration_seconds=args.duration,
        max_rps=args.max_rps,
        think_seconds=args.think_seconds,
        allow_remote=args.allow_remote,
    )
    try:
        report = asyncio.run(run_load(config))
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Ошибка: {exc}\n")
    print_report(report)
    return (
        1
        if not report.samples or summarize(report.samples, report.elapsed_seconds).failed_requests
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
