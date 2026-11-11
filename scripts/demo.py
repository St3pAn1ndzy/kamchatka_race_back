"""Подготовка и запуск двух независимых локальных сценариев показа"""

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings


@dataclass(frozen=True)
class DemoScenario:
    """Локальная база, кеш и адрес одного сценария демонстрации"""

    database: str
    redis_db: int
    port: int
    url: str


SCENARIOS = {
    "overview": DemoScenario("avacha_demo_overview", 13, 8000, "http://127.0.0.1:8000"),
    "route-import": DemoScenario("avacha_demo_import", 14, 8001, "http://localhost:8001"),
}


def scenario_environment(name: str, settings: Settings) -> dict[str, str]:
    """Изолирует данные дочернего процесса без изменения .env и исходного окружения"""
    local = {"localhost", "127.0.0.1"}
    if (
        settings.ENV != "dev"
        or settings.POSTGRES_HOST not in local
        or settings.REDIS_HOST not in local
    ):
        raise ValueError(
            "Показ разрешён только в локальном ENV=dev с локальными PostgreSQL и Redis"
        )
    scenario = SCENARIOS[name]
    return {
        **os.environ,
        "ENV": "dev",
        "DEBUG": "true",
        "POSTGRES_DB": scenario.database,
        "REDIS_DB": str(scenario.redis_db),
    }


def ensure_database(settings: Settings, database: str) -> None:
    """Создаёт только именованную демобазу, не удаляя существующие базы"""
    if database not in {scenario.database for scenario in SCENARIOS.values()}:
        raise ValueError("Неизвестная демонстрационная база")
    scenario_environment("overview", settings)
    engine = create_engine(
        make_url(settings.SYNC_DATABASE_URL).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{database}"'))
    finally:
        engine.dispose()


def prepare_scenarios(settings: Settings, *, reset: bool = False) -> None:
    """Мигрирует и заполняет оба набора, очистка допускается только явным флагом"""
    for name, scenario in SCENARIOS.items():
        environment = scenario_environment(name, settings)
        environment["DEBUG"] = "false"
        ensure_database(settings, scenario.database)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, check=True
        )
        command = [sys.executable, "-m", "scripts.seed_mock", "--scenario", name]
        if reset:
            command.append("--reset")
        subprocess.run(command, env=environment, check=True)
        print(f"Готово: {name} · {scenario.database} · {scenario.url}/admin-panel", flush=True)


def main() -> None:
    """Запускает подготовку, сервер или движение участника нужного сценария"""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Подготовить оба набора mock-данных")
    prepare.add_argument("--reset", action="store_true", help="Пересоздать только две демобазы")
    serve = commands.add_parser("serve", help="Запустить админку выбранного сценария")
    serve.add_argument("scenario", choices=SCENARIOS)
    move = commands.add_parser("move", help="Показать движение и SOS в сценарии обзора")
    move.add_argument("--device-id", type=int, default=1, help="ID демонстрационного трекера")
    move.add_argument("--steps", type=int, default=24, help="Количество обновлений")
    move.add_argument("--interval", type=float, default=5, help="Пауза между обновлениями")
    move.add_argument("--sos-at", type=int, default=6, help="Шаг включения SOS")
    args = parser.parse_args()
    settings = get_settings()
    try:
        if args.command == "prepare":
            prepare_scenarios(settings, reset=args.reset)
            return
        name = args.scenario if args.command == "serve" else "overview"
        environment = scenario_environment(name, settings)
        if args.command == "serve":
            scenario = SCENARIOS[name]
            print(f"Админка: {scenario.url}/admin-panel", flush=True)
            command = [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(scenario.port),
            ]
        else:
            environment["DEBUG"] = "false"
            command = [
                sys.executable,
                "-m",
                "scripts.demo_race",
                "--device-id",
                str(args.device_id),
                "--steps",
                str(args.steps),
                "--interval",
                str(args.interval),
                "--sos-at",
                str(args.sos_at),
            ]
        subprocess.run(command, env=environment, check=True)
    except (ValueError, SQLAlchemyError):
        parser.exit(1, "Проверьте локальный ENV=dev, PostgreSQL и Redis\n")
    except subprocess.CalledProcessError as exc:
        parser.exit(exc.returncode or 1, "Сценарий не завершён, причина указана выше\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
