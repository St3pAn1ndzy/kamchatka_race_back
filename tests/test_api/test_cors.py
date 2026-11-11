"""Тесты CORS для production-доменов VK Mini App."""


async def test_cors_preflight_vk_apps_production(client) -> None:
    """Preflight с прод-домена *.vk-apps.com проходит."""
    response = await client.options(
        "/api/v1/map/participants?stage_id=1",
        headers={
            "Origin": "https://prod-app1234567.pages-ac.vk-apps.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://prod-app1234567.pages-ac.vk-apps.com"
    )
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_preflight_vk_com(client) -> None:
    """Preflight с vk.com проходит (iframe-контекст в ленте VK)."""
    response = await client.options(
        "/api/v1/map/participants?stage_id=1",
        headers={
            "Origin": "https://vk.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://vk.com"


async def test_cors_rejects_unknown_origin(client) -> None:
    """Левый origin получает 400 без allow-origin в заголовках."""
    response = await client.options(
        "/api/v1/map/participants?stage_id=1",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_cors_vk_ru_accepted(client) -> None:
    """vk.ru (новый домен VK с 2023) тоже разрешён."""
    response = await client.options(
        "/api/v1/map/participants?stage_id=1",
        headers={
            "Origin": "https://vk.ru",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://vk.ru"
