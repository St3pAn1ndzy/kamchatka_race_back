"""Фабрика клиента Iridium360.

В dev без ключа — мок. Иначе — реальный клиент.
"""

import logging

from app.config import get_settings
from app.integrations.iridium.client import IridiumClient, IridiumClientProtocol
from app.integrations.iridium.mock import MockIridiumClient

logger = logging.getLogger("avacha.iridium")
settings = get_settings()


def get_iridium_client() -> IridiumClientProtocol:
    """В dev без ключа — мок, иначе — реальный клиент."""
    if settings.ENV == "dev" and not settings.IRIDIUM_API_KEY:
        logger.info("Using MockIridiumClient (dev, no key)")
        return MockIridiumClient()
    if settings.ENV == "prod" and not settings.IRIDIUM_API_KEY:
        logger.warning("No IRIDIUM_API_KEY in prod!")
        raise RuntimeError("IRIDIUM_API_KEY обязателен в prod")
    return IridiumClient()
