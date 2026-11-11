"""Проверки независимого запуска двух локальных сценариев демонстрации"""

from unittest.mock import MagicMock

import pytest

from app.config import Settings
from scripts.demo import SCENARIOS, prepare_scenarios, scenario_environment


def test_scenarios_have_separate_databases_caches_and_cookie_hosts():
    """Переключение вкладок не смешивает данные, кеш и административные сессии"""
    overview = SCENARIOS["overview"]
    importing = SCENARIOS["route-import"]
    assert overview.database != importing.database
    assert overview.redis_db != importing.redis_db
    assert overview.redis_db not in {0, 1, 2, 15}
    assert importing.redis_db not in {0, 1, 2, 15}
    assert overview.url == "http://127.0.0.1:8000"
    assert importing.url == "http://localhost:8001"


def test_environment_does_not_change_project_database_or_settings(monkeypatch):
    """Дочерний процесс получает настройки демо, исходное окружение остаётся прежним"""
    monkeypatch.setenv("POSTGRES_DB", "existing-project")
    settings = Settings(ENV="dev", POSTGRES_HOST="localhost", REDIS_HOST="localhost")
    environment = scenario_environment("overview", settings)
    assert environment["POSTGRES_DB"] == "avacha_demo_overview"
    assert environment["REDIS_DB"] == "13"
    assert environment["DEBUG"] == "true"
    import os

    assert os.environ["POSTGRES_DB"] == "existing-project"
    assert settings.POSTGRES_DB == "existing-project"


@pytest.mark.parametrize(
    "overrides",
    [{"ENV": "prod"}, {"POSTGRES_HOST": "database.example"}, {"REDIS_HOST": "cache.example"}],
)
def test_launcher_rejects_nonlocal_resources(overrides):
    """Демонстрационные команды не запускаются с рабочими или удалёнными ресурсами"""
    settings = Settings(ENV="dev", POSTGRES_HOST="localhost", REDIS_HOST="localhost")
    settings = settings.model_copy(update=overrides)
    with pytest.raises(ValueError, match="локальн"):
        scenario_environment("overview", settings)


@pytest.mark.parametrize("reset", [False, True])
def test_prepare_runs_migrations_before_each_seed_without_implicit_reset(monkeypatch, reset):
    """Каждая демобаза мигрируется до сида, очистка передаётся только явно"""
    run = MagicMock()
    ensure = MagicMock()
    monkeypatch.setattr("scripts.demo.subprocess.run", run)
    monkeypatch.setattr("scripts.demo.ensure_database", ensure)
    settings = Settings(ENV="dev", POSTGRES_HOST="localhost", REDIS_HOST="localhost")
    prepare_scenarios(settings, reset=reset)
    assert ensure.call_count == 2
    assert run.call_count == 4
    calls = run.call_args_list
    for i, name in enumerate(("overview", "route-import")):
        migrate, seed = calls[2 * i : 2 * i + 2]
        assert migrate.args[0][-3:] == ["alembic", "upgrade", "head"]
        assert seed.args[0][1:5] == ["-m", "scripts.seed_mock", "--scenario", name]
        assert ("--reset" in seed.args[0]) is reset
        assert migrate.kwargs["env"]["POSTGRES_DB"] == SCENARIOS[name].database
        assert seed.kwargs["env"]["REDIS_DB"] == str(SCENARIOS[name].redis_db)


@pytest.mark.parametrize(
    ("arguments", "scenario", "debug"),
    [
        (["move", "--device-id", "2"], "overview", "false"),
        (["serve", "overview"], "overview", "true"),
        (["serve", "route-import"], "route-import", "true"),
    ],
)
def test_commands_target_selected_scenario_and_keep_motion_output_readable(
    monkeypatch, arguments, scenario, debug
):
    """Серверы получают свой набор, движение работает без потока SQL в терминале"""
    from scripts import demo

    run = MagicMock()
    monkeypatch.setattr(demo.sys, "argv", ["demo", *arguments])
    monkeypatch.setattr(demo.subprocess, "run", run)
    monkeypatch.setattr(
        demo,
        "get_settings",
        lambda: Settings(ENV="dev", POSTGRES_HOST="localhost", REDIS_HOST="localhost"),
    )
    demo.main()
    environment = run.call_args.kwargs["env"]
    assert environment["POSTGRES_DB"] == SCENARIOS[scenario].database
    assert environment["REDIS_DB"] == str(SCENARIOS[scenario].redis_db)
    assert environment["DEBUG"] == debug
