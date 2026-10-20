from types import SimpleNamespace

import pytest

from tests.conftest import assert_test_resources


def _settings(**overrides: object) -> SimpleNamespace:
    values = {
        "ENV": "test",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "avacha_test",
        "REDIS_HOST": "localhost",
        "REDIS_DB": 15,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("postgres_host", "redis_host"),
    [("localhost", "localhost"), ("127.0.0.1", "127.0.0.1"), ("postgres", "redis")],
)
def test_isolated_test_resources_are_accepted(postgres_host: str, redis_host: str) -> None:
    """Локальные и контейнерные тестовые БД доступны фикстурам"""
    assert_test_resources(_settings(POSTGRES_HOST=postgres_host, REDIS_HOST=redis_host))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ENV": "dev"}, "ENV=test"),
        ({"POSTGRES_DB": "avacha"}, "_test"),
        ({"POSTGRES_HOST": "production.example"}, "PostgreSQL"),
        ({"REDIS_DB": 0}, "Redis DB"),
        ({"REDIS_HOST": "production.example"}, "Redis"),
    ],
)
def test_unsafe_test_resources_are_rejected(overrides: dict, message: str) -> None:
    """Опасная конфигурация останавливает тесты до очистки данных"""
    with pytest.raises(RuntimeError, match=message):
        assert_test_resources(_settings(**overrides))
