"""Базовые фикстуры для тестов: engine, db_session, app, client."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Регистрируем все модели в Base.metadata до create_all.
import app.db.models  # noqa: F401
from app.config import get_settings
from app.db.base import Base, get_session
from app.db.models import AdminAccount, Discipline, Season, Stage
from app.main import app as fastapi_app
from app.security.passwords import hash_password
from app.services.cache import cache


@pytest.fixture(scope="session")
def test_settings():
    """Настройки приложения (session-scoped, один раз за сессию)."""
    return get_settings()


@pytest.fixture(scope="session")
def engine(test_settings):
    """Async-движок с NullPool (без утечки соединений между тестами)."""
    return create_async_engine(
        test_settings.DATABASE_URL,
        poolclass=NullPool,
    )


@pytest.fixture(scope="session", autouse=True)
async def _prepare_db(engine):
    """Создаёт схему БД перед тестами и чистит после."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def _clear_cache(request):
    """Очищает Redis-кэш до и после каждого теста."""
    await cache.invalidate_pattern("*")
    yield
    await cache.invalidate_pattern("*")


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Функциональная транзакция с SAVEPOINT-изоляцией.

    Каждый тест работает внутри вложенной транзакции, которая
    автоматически откатывается после завершения теста.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture(scope="session")
def app():
    """FastAPI-приложение (session-scoped)."""
    return fastapi_app


@pytest.fixture
async def client(db_session, app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент с переопределённой зависимостью get_session.

    Все запросы внутри теста используют транзакцию db_session,
    которая будет откачена после завершения теста.
    """

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def create_admin(db_session):
    async def _factory(*, login="admin", password="admin123", is_active=True):
        admin = AdminAccount(
            login=login,
            password_hash=hash_password(password),
            display_name="Test Admin",
            is_active=is_active,
        )
        db_session.add(admin)
        await db_session.flush()
        return admin

    return _factory


@pytest.fixture
async def create_season(db_session):
    async def _factory(
        *,
        year: int = 2027,
        title: str = "Авача 2027",
        is_active: bool = True,
    ) -> Season:
        season = Season(
            year=year,
            title=title,
            starts_at=datetime(2027, 2, 27, tzinfo=UTC),
            ends_at=datetime(2027, 3, 6, tzinfo=UTC),
            is_active=is_active,
        )
        db_session.add(season)
        await db_session.flush()
        return season

    return _factory


@pytest.fixture
async def create_discipline(db_session):
    async def _factory(
        *,
        season_id: int,
        code: str = "long",
        name: str = "Длинная",
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Discipline:
        discipline = Discipline(
            season_id=season_id,
            code=code,
            name=name,
            sort_order=sort_order,
            is_active=is_active,
        )
        db_session.add(discipline)
        await db_session.flush()
        return discipline

    return _factory


@pytest.fixture
async def create_stage(db_session):
    async def _factory(
        *,
        season_id: int,
        number: int = 1,
        name: str = "Этап 1",
        distance_km: float = 100.0,
        order_index: int = 0,
    ) -> Stage:
        stage = Stage(
            season_id=season_id,
            number=number,
            name=name,
            distance_km=distance_km,
            start_time=datetime(2027, 3, 1, 2, 0, tzinfo=UTC),
            finish_time=datetime(2027, 3, 1, 8, 0, tzinfo=UTC),
            order_index=order_index,
            tracker_interval_seconds=1200,
            status="planned",
        )
        db_session.add(stage)
        await db_session.flush()
        return stage

    return _factory
