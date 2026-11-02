from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
def mock_dev_settings(monkeypatch):
    """Мокаем настройки, чтобы роутер думал, что мы в ENV=dev"""
    mock_settings = MagicMock()
    mock_settings.ENV = "dev"
    # Подменяем функцию get_settings только в модуле роутера
    monkeypatch.setattr("app.api.service.scenarios.get_settings", lambda: mock_settings)
    return mock_settings


@pytest.fixture
def mock_prod_settings(monkeypatch):
    """Мокаем настройки для проверки защиты на проде"""
    mock_settings = MagicMock()
    mock_settings.ENV = "production"
    monkeypatch.setattr("app.api.service.scenarios.get_settings", lambda: mock_settings)
    return mock_settings


@pytest.mark.asyncio
async def test_list_scenarios(client: AsyncClient, mock_dev_settings):
    """Проверяем, что ручка возвращает список сценариев"""
    response = await client.get("/api/v1/dev/scenarios/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "scenarios" in data
    assert "upcoming" in data["scenarios"]
    assert "live" in data["scenarios"]
    assert "finished" in data["scenarios"]


@pytest.mark.asyncio
async def test_switch_invalid_scenario(client: AsyncClient, mock_dev_settings, monkeypatch):
    """Проверяем, что при неверном имени сценария возвращается 400, а не 500"""
    # Мокаем apply_scenario через AsyncMock (так как это асинхронная функция)
    mock_apply = AsyncMock(side_effect=ValueError("Сценарий 'invalid' не найден"))
    monkeypatch.setattr("app.api.service.scenarios.apply_scenario", mock_apply)

    response = await client.post("/api/v1/dev/scenarios/invalid_scenario_name")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "не найден" in response.json()["detail"]


@pytest.mark.asyncio
async def test_switch_scenario_success(client: AsyncClient, mock_dev_settings, monkeypatch):
    """Проверяем успешное переключение (мокаем apply_scenario, чтобы не трогать реальную БД)"""
    mock_apply = AsyncMock()
    monkeypatch.setattr("app.api.service.scenarios.apply_scenario", mock_apply)

    response = await client.post("/api/v1/dev/scenarios/upcoming")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "scenario": "upcoming"}
    mock_apply.assert_called_once_with("upcoming")


@pytest.mark.asyncio
async def test_dev_mode_protection(client: AsyncClient, mock_prod_settings):
    """Проверяем, что ручки закрыты, если ENV != dev"""
    response = await client.get("/api/v1/dev/scenarios/")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Service endpoints disabled" in response.json()["detail"]


@pytest.mark.asyncio
async def test_start_demo_movement(client: AsyncClient, mock_dev_settings, monkeypatch):
    """Проверяем, что эндпоинт движения ставит задачу в BackgroundTasks"""
    # Мокаем метод add_task у класса BackgroundTasks
    mock_add_task = MagicMock()
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task", mock_add_task)

    response = await client.post("/api/v1/dev/scenarios/move/7?steps=5")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "movement_started", "device_id": 7}
    assert mock_add_task.called
