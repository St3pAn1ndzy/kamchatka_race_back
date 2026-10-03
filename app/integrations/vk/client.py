"""Клиент VK API для отправки уведомлений.

VK Notify API: notifications.sendMessage.
Лимиты: 2/час, 10/сутки на пользователя.
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger("avacha.vk")
settings = get_settings()

VK_API_URL = "https://api.vk.com/method"


class VKAPIError(Exception):
    """Ошибка VK API."""


class VKClient:
    """Клиент VK API для отправки уведомлений."""

    def __init__(
        self,
        service_token: str | None = None,
        group_id: int | None = None,
        api_version: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.service_token = service_token or settings.VK_SERVICE_TOKEN
        self.group_id = group_id or settings.VK_GROUP_ID
        self.api_version = api_version or settings.VK_API_VERSION
        self.timeout = timeout

    async def send_notification(
        self,
        vk_user_id: int,
        message: str,
        fragment: str = "notifications",
    ) -> bool:
        """Отправить уведомление пользователю. True при успехе."""
        if not self.service_token:
            logger.warning("VK_SERVICE_TOKEN не задан, отправка пропущена")
            return False

        params = {
            "user_id": vk_user_id,
            "message": message,
            "fragment": fragment,
            "access_token": self.service_token,
            "v": self.api_version,
        }
        if self.group_id:
            params["group_id"] = self.group_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{VK_API_URL}/notifications.sendMessage", data=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            logger.error("VK timeout, vk_user_id=%d", vk_user_id)
            return False
        except httpx.HTTPStatusError as exc:
            logger.error("VK HTTP error %s, vk_user_id=%d", exc.response.status_code, vk_user_id)
            return False
        except httpx.RequestError as exc:
            logger.error("VK request error: %s", exc)
            return False

        if "error" in data:
            err = data["error"]
            logger.error(
                "VK API error: code=%s, msg=%s",
                err.get("error_code"),
                err.get("error_msg"),
            )
            return False

        return True


def get_vk_client() -> VKClient:
    return VKClient()
