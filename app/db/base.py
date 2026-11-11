"""База данных: engine, session factory, Base."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


# Engine для FastAPI
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)


# Engine для Celery (создается после fork'а)
# Глобальные переменные для хранения движка и фабрики сессий в рамках одного worker-процесса
_celery_engine = None
_celery_session_factory = None


def init_celery_engine() -> None:
    """Создает движок и фабрику сессий для Celery-воркера.

    Вызывается один раз в каждом дочернем процессе через сигнал worker_process_init.
    """
    global _celery_engine, _celery_session_factory
    if _celery_engine is None:
        _celery_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        _celery_session_factory = async_sessionmaker(
            _celery_engine, expire_on_commit=False, class_=AsyncSession
        )


def get_celery_session_factory() -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику сессий для Celery, создавая её при необходимости."""
    if _celery_session_factory is None:
        # Ленивая инициализация, если по какой-то причине сигнал не сработал (например, в тестах)
        init_celery_engine()
    return _celery_session_factory


async def dispose_celery_engine() -> None:
    """Закрывает соединения Celery-движка перед завершением event loop."""
    global _celery_engine
    if _celery_engine is not None:
        await _celery_engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
