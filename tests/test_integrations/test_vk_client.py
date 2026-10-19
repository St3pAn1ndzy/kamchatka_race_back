import httpx
import pytest

from app.integrations.vk.client import VKClient


def _install_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.integrations.vk.client.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )


async def test_success_sends_expected_vk_method_and_parameters(monkeypatch):
    """Успешная отправка использует нужный метод VK и параметры запроса"""
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"response": 1})

    _install_transport(monkeypatch, handler)
    client = VKClient(service_token="secret", group_id=7, api_version="5.199")
    assert await client.send_notification(42, "Hello", fragment="race") is True
    assert len(captured) == 1
    assert captured[0].url.path.endswith("/notifications.sendMessage")
    body = captured[0].content.decode()
    assert "user_id=42" in body
    assert "message=Hello" in body
    assert "group_id=7" in body
    assert "access_token=secret" in body
    assert "fragment=race" in body


async def test_missing_token_skips_network(monkeypatch):
    """Без сервисного токена клиент не обращается к сети"""

    def handler(_request):
        pytest.fail("VK must not be called without a service token")

    _install_transport(monkeypatch, handler)
    client = VKClient(service_token="secret")
    client.service_token = ""
    assert await client.send_notification(42, "Hello") is False


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"error": {"error_code": 9, "error_msg": "Rate limit"}}),
        httpx.Response(500, json={"error": "down"}),
    ],
)
async def test_vk_and_http_errors_return_false(monkeypatch, response):
    """Ошибка в ответе VK или HTTP-ошибка дают False без исключения"""
    _install_transport(monkeypatch, lambda _request: response)
    assert await VKClient(service_token="secret").send_notification(42, "Hello") is False


@pytest.mark.parametrize("exception", [httpx.ReadTimeout("timeout"), httpx.ConnectError("offline")])
async def test_transport_errors_return_false(monkeypatch, exception):
    """Таймаут и ошибка соединения дают False без исключения"""

    def handler(_request):
        raise exception

    _install_transport(monkeypatch, handler)
    assert await VKClient(service_token="secret").send_notification(42, "Hello") is False
