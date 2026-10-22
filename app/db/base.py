from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


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


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
