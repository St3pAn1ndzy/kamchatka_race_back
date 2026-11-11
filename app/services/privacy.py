"""Приватность: анонимизация пользователя по 152-ФЗ.

При отзыве согласия — обнуляем персональные данные, но оставляем
vk_user_id (иначе не сможет зайти снова) и агрегаты для аналитики.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.fun_subscription import FanSubscription
from app.db.models.push_subscription import PushSubscription
from app.db.models.saved_item import SavedItem
from app.db.models.share_event import ShareEvent
from app.db.models.user import User

logger = logging.getLogger("avacha.privacy")


class UserNotFoundError(Exception):
    """Пользователь не найден."""


async def anonymize_user(
    session: AsyncSession,
    user_id: int,
    *,
    reason: str,
) -> dict:
    """Анонимизировать пользователя.

    - Обнуляет first_name, last_name, photo_url, platform.
    - Удаляет FanSubscription, SavedItem, ShareEvent, PushSubscription.
    - Сбрасывает notifications_allowed.
    - Оставляет vk_user_id (иначе не сможет зайти снова).
    - Ставит consent_revoked_at.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError(user_id)

    now = datetime.now(tz=UTC)

    # Персональные данные — обнуляем
    user.first_name = ""
    user.last_name = ""
    user.photo_url = None
    user.platform = None

    # Отзыв согласия
    user.consent_revoked_at = now
    user.consent_version = None
    user.consent_accepted_at = None

    # Push — сброс
    user.notifications_allowed = False

    # Связанные данные — удаляем
    await session.execute(delete(FanSubscription).where(FanSubscription.user_id == user_id))
    await session.execute(delete(SavedItem).where(SavedItem.user_id == user_id))
    await session.execute(delete(ShareEvent).where(ShareEvent.user_id == user_id))
    await session.execute(delete(PushSubscription).where(PushSubscription.user_id == user_id))

    await session.flush()
    logger.warning("user_anonymized", extra={"user_id": user_id, "reason": reason})

    return {
        "user_id": user_id,
        "anonymized_at": now.isoformat(),
        "reason": reason,
    }
