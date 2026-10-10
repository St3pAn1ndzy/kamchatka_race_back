"""Базовые фикстуры для тестов.

Сейчас тесты unit-уровня — мокают БД и клиентов.
Здесь — общие фикстуры; TODO: integration-тесты БД в эпике тестов.
"""

# Ничего не импортируем пока — все тесты самодостаточны.
# TODO: в эпике тестов добавить:
#   - engine  — async engine на avacha_test
#   - session — AsyncSession с откатом транзакции после теста
#   - client  — httpx.AsyncClient с ASGITransport (для API)
#   - user_factory, device_factory, participant_factory
