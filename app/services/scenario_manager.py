import logging

from sqlalchemy import text

from app.db.base import async_session_factory
from app.services.cache import cache
from scripts.scenarios.finished import seed as seed_finished
from scripts.scenarios.live import seed as seed_live
from scripts.scenarios.upcoming import seed as seed_upcoming

logger = logging.getLogger(__name__)

# Реестр сценариев. Ключ — это то, что будет в URL
SCENARIOS = {
    "upcoming": seed_upcoming,
    "live": seed_live,
    "finished": seed_finished,
}


async def apply_scenario(scenario_name: str):
    """Очищает БД, применяет сценарий и сбрасывает кэш."""
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Сценарий '{scenario_name}' не найден")

    logger.info(f"Переключение на сценарий: {scenario_name}")

    async with async_session_factory() as session:
        tables = (
            "audit_logs, official_marks, track_points, stage_route_points, "
            "devices, checkpoints, stages, disciplines, seasons, fan_subscriptions, "
            "saved_items, share_events, notification_queue, push_subscriptions, "
            "user_feedbacks, participants, news_posts, schedule_events, faq_items, "
            "viewer_locations, static_pages, guest_items, admin_accounts, users"
        )
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

        created = {}
        await SCENARIOS[scenario_name](session, created)

        await session.commit()
        logger.info(f"Сценарий '{scenario_name}' успешно применен.")

    await cache.invalidate_pattern("public:*")
    await cache.invalidate_pattern("admin:*")
    logger.info("Кэш успешно сброшен.")
