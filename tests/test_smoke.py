"""Smoke-тесты: проверка engine и изоляции транзакций."""

from sqlalchemy import text


async def test_engine_works(db_session):
    """Базовый запрос — проверка, что engine жив."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


async def test_a_inserts(db_session):
    """Вставка пользователя в рамках тестовой транзакции."""
    await db_session.execute(
        text(
            "INSERT INTO users (vk_user_id, first_name, last_name, platform, "
            "notifications_allowed, consent_version, consent_accepted_at) "
            "VALUES (999999, 'x', 'y', 'vk', false, '1.0', now())"
        )
    )


async def test_b_sees_nothing(db_session):
    """После отката транзакции теста test_a — данных нет."""
    result = await db_session.execute(text("SELECT COUNT(*) FROM users WHERE vk_user_id = 999999"))
    assert result.scalar() == 0
