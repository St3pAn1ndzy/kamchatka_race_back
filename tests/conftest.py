"""Базовые фикстуры для тестов: engine, db_session, app, client."""

import hashlib
import uuid
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
from app.db.models import (
    AdminAccount,
    Checkpoint,
    Device,
    Discipline,
    OfficialMark,
    Participant,
    Season,
    Stage,
    StageRoutePoint,
    TrackPoint,
    FanSubscription,
    User,
)
from app.main import app as fastapi_app
from app.security.passwords import hash_password
from app.services.cache import cache


def assert_test_resources(settings) -> None:
    """Не допускает очистку рабочих PostgreSQL и Redis тестовыми фикстурами"""
    if settings.ENV != "test":
        raise RuntimeError("Для запуска тестов требуется ENV=test")
    if not settings.POSTGRES_DB.endswith("_test"):
        raise RuntimeError("Имя тестовой базы PostgreSQL должно оканчиваться на _test")
    if settings.POSTGRES_HOST not in {"localhost", "127.0.0.1", "postgres"}:
        raise RuntimeError("PostgreSQL для тестов должен быть локальным или тестовым контейнером")
    if settings.REDIS_DB != 15:
        raise RuntimeError("Redis DB для тестов должен быть равен 15")
    if settings.REDIS_HOST not in {"localhost", "127.0.0.1", "redis"}:
        raise RuntimeError("Redis для тестов должен быть локальным или тестовым контейнером")


@pytest.fixture(scope="session")
def test_settings():
    """Настройки приложения (session-scoped, один раз за сессию)."""
    settings = get_settings()
    assert_test_resources(settings)
    return settings


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
async def _clear_cache(test_settings):
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


@pytest.fixture
async def create_route_point(db_session):
    async def _factory(
        *,
        stage_id: int,
        position: int = 0,
        lat: float = 55.0,
        lon: float = 160.0,
    ) -> StageRoutePoint:
        point = StageRoutePoint(
            stage_id=stage_id,
            position=position,
            lat=lat,
            lon=lon,
        )
        db_session.add(point)
        await db_session.flush()
        return point

    return _factory


@pytest.fixture
async def create_track_point(db_session, create_device):
    async def _factory(
        *,
        participant_id: int,
        stage_id: int,
        device_id: int | None = None,
        lat: float = 55.0,
        lon: float = 160.0,
        recorded_at: datetime | None = None,
        km_from_start: float = 10.0,
    ) -> TrackPoint:
        if device_id is None:
            # Создаем фейковый девайс, чтобы удовлетворить ForeignKey
            device = await create_device(participant_id=participant_id, stage_id=stage_id)
            device_id = device.id

        ts = recorded_at or datetime.now(tz=UTC)
        key = hashlib.sha256(f"{participant_id}:{ts.isoformat()}".encode()).hexdigest()

        point = TrackPoint(
            participant_id=participant_id,
            stage_id=stage_id,
            device_id=device_id,
            lat=lat,
            lon=lon,
            recorded_at=ts,
            km_from_start=km_from_start,
            deduplication_key=key,
            is_confirmed=True,
        )
        db_session.add(point)
        await db_session.flush()
        return point

    return _factory


@pytest.fixture
async def create_official_mark(db_session, create_admin):
    async def _factory(
        *,
        participant_id: int,
        checkpoint_id: int,
        mark_time: datetime | None = None,
        is_cancelled: bool = False,
    ) -> OfficialMark:
        if not hasattr(_factory, "_admin"):
            _factory._admin = await create_admin(login="test_admin")

        mark = OfficialMark(
            participant_id=participant_id,
            checkpoint_id=checkpoint_id,
            mark_time=mark_time or datetime.now(tz=UTC),
            entered_by_admin_id=_factory._admin.id,
            is_cancelled=is_cancelled,
        )
        db_session.add(mark)
        await db_session.flush()
        return mark

    return _factory


@pytest.fixture
async def create_participant(db_session):
    async def _factory(
        *,
        number: int = 1,
        name: str = "Иван Иванов",
        region: str = "Камчатский край",
        discipline_id: int | None = None,
        status: str = "registered",
    ) -> Participant:
        participant = Participant(
            number=number,
            name=name,
            region=region,
            discipline_id=discipline_id,
            status=status,
            dogs_count=8,
        )
        db_session.add(participant)
        await db_session.flush()
        return participant

    return _factory


@pytest.fixture
async def create_checkpoint(db_session):
    async def _factory(
        *,
        stage_id: int,
        kind: str = "checkpoint",
        code: str = "КП-1",
        name: str = "Контрольный пункт",
        order_index: int = 1,
        lat: float = 55.0,
        lon: float = 160.0,
        km_from_race_start: float = 10.0,
        is_public: bool = True,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            stage_id=stage_id,
            kind=kind,
            code=code,
            name=name,
            order_index=order_index,
            lat=lat,
            lon=lon,
            km_from_race_start=km_from_race_start,
            is_public=is_public,
        )
        db_session.add(checkpoint)
        await db_session.flush()
        return checkpoint

    return _factory


@pytest.fixture
async def create_device(db_session):
    async def _factory(
        *,
        participant_id: int | None = None,
        stage_id: int | None = None,
        imei: str | None = None,
    ) -> Device:
        # Генерируем уникальный IMEI и Iridium номер для каждого вызова
        unique_imei = imei or uuid.uuid4().hex[:15]
        unique_iridium = uuid.uuid4().hex[:5]

        device = Device(
            iridium_number=unique_iridium,
            imei=unique_imei,
            name=f"Трекер {unique_iridium}",
            participant_id=participant_id,
            stage_id=stage_id,
            is_active=True,
        )
        db_session.add(device)
        await db_session.flush()
        return device

    return _factory


@pytest.fixture
async def create_user(db_session):
    async def _factory(
        *,
        vk_user_id: int | None = None,
        first_name: str = "Иван",
        last_name: str = "Болельщик",
        notifications_allowed: bool = False,
    ) -> User:
        if vk_user_id is None:
            # Уникальный ID, чтобы не ловить UniqueViolationError
            vk_user_id = uuid.uuid4().int % 10**9 + 1_000_000_000

        user = User(
            vk_user_id=vk_user_id,
            first_name=first_name,
            last_name=last_name,
            notifications_allowed=notifications_allowed,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _factory


@pytest.fixture
async def create_fan_subscription(db_session):
    async def _factory(
        *,
        user_id: int,
        participant_id: int,
        created_at: datetime | None = None,
    ) -> FanSubscription:
        sub = FanSubscription(
            user_id=user_id,
            participant_id=participant_id,
        )
        # Если передали created_at — переопределяем server_default
        if created_at is not None:
            sub.created_at = created_at

        db_session.add(sub)
        await db_session.flush()
        return sub

    return _factory
