from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker

from database import Base

_sqlite_engine: Optional[AsyncEngine] = None
_async_sqlite_session_local: Optional[sessionmaker] = None


def get_sqlite_engine_and_session():
    global _sqlite_engine, _async_sqlite_session_local
    if _sqlite_engine is None or _async_sqlite_session_local is None:
        from config import get_settings  # <-- локально!
        settings = get_settings()
        SQLITE_DATABASE_URL = f"sqlite+aiosqlite:///{settings.PATH_TO_DB}"
        _sqlite_engine = create_async_engine(SQLITE_DATABASE_URL, echo=False)
        _async_sqlite_session_local = sessionmaker(
            bind=_sqlite_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _sqlite_engine, _async_sqlite_session_local


async def get_sqlite_db() -> AsyncGenerator[AsyncSession, None]:
    _, AsyncSQLiteSessionLocal = get_sqlite_engine_and_session()
    async with AsyncSQLiteSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_sqlite_db_contextmanager() -> AsyncGenerator[AsyncSession, None]:
    _, AsyncSQLiteSessionLocal = get_sqlite_engine_and_session()
    async with AsyncSQLiteSessionLocal() as session:
        yield session


async def reset_sqlite_database() -> None:
    sqlite_engine, _ = get_sqlite_engine_and_session()
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
