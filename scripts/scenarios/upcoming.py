"""Сценарий 1: «До старта гонки». Например, 30 октября 2026 г."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FanSubscription, NotificationQueue, RaceStatus
from app.enums import NotificationEventType, NotificationStatus, RaceState
from scripts.scenarios.app_scenarios_data import APP_DISCIPLINES, APP_MUSHERS
from scripts.scenarios.common import seed_base


async def seed(session: AsyncSession, created: dict[str, int]) -> None:
    """До старта гонки:
    - RaceStatus = upcoming (или отсутствует)
    - Все Stage = planned
    - Все Participant = registered
    - Нет TrackPoint, нет OfficialMark
    - Есть FanSubscription у тестового пользователя (для «Болею за»)
    - Есть NotificationQueue (для профиля)
    """
    base = await seed_base(
        session, created, custom_disciplines=APP_DISCIPLINES, custom_mushers=APP_MUSHERS
    )
    users = base["users"]
    participants = base["participants"]

    # ═══ Ключевое: RaceStatus = upcoming ═══
    session.add(RaceStatus(status=RaceState.UPCOMING.value, current_stage_id=None))
    created["RaceStatus"] = 1

    # ═══ FanSubscription: у первого юзера 3 подписки (для демо «Болею за») ═══
    demo_user = users[0]
    fan_subs = [
        FanSubscription(user_id=demo_user.id, participant_id=participants[i].id)
        for i in (1, 4, 7)  # участники №2, 5, 8
    ]
    session.add_all(fan_subs)
    created["FanSubscription"] = len(fan_subs)

    # ═══ NotificationQueue: у демо-юзера пара «отправленных» пушей ═══
    notifications = [
        NotificationQueue(
            user_id=demo_user.id,
            event_type=NotificationEventType.STAGE_START.value,
            title="Гонка «Авача» скоро начнётся",
            body="Старт первого этапа 1 марта 2027. Следите за обновлениями.",
            status=NotificationStatus.SENT.value,
            attempts=1,
            scheduled_at=None,
            sent_at=None,
        ),
        NotificationQueue(
            user_id=demo_user.id,
            event_type=NotificationEventType.FAVORITE_UPDATE.value,
            title="Ваш каюр подал заявку",
            body="Участник №2 Мария Кравцова подала заявку на участие.",
            status=NotificationStatus.SENT.value,
            attempts=1,
            scheduled_at=None,
            sent_at=None,
        ),
    ]
    session.add_all(notifications)
    created["NotificationQueue"] = len(notifications)

    # ═══ Device: НЕ создаём (нет GPS-данных, иначе «Связь 0/15» выглядит странно) ═══
    # В сценарии «До старта» трекеры ещё не выдали на руки участникам.
