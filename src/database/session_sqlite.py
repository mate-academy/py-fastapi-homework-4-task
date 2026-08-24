from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models.base import Base  # Sync path to your Base metadata module

# Global placeholders initialized on demand
_sqlite_engine = None
_AsyncSQLiteSessionLocal = None


def _init_sqlite_factory():
    """On-demand initialization to break top-level circular imports."""
    global _sqlite_engine, _AsyncSQLiteSessionLocal
    if _sqlite_engine is None:
        # Inline import breaks the top-level initialization loop cleanly
        from config.dependencies import get_settings

        settings = get_settings()
        # Fallback to PATH_TO_DB mapping syntax if explicit string URL is not provided
        database_url = getattr(settings, "DATABASE_URL_SQLITE", f"sqlite+aiosqlite:///{settings.PATH_TO_DB}")

        _sqlite_engine = create_async_engine(database_url, echo=False)
        _AsyncSQLiteSessionLocal = sessionmaker(  # type: ignore
            bind=_sqlite_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _sqlite_engine, _AsyncSQLiteSessionLocal


async def get_sqlite_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous database session.
    """
    _, session_factory = _init_sqlite_factory()
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def get_sqlite_db_contextmanager() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous database session using a context manager.
    """
    _, session_factory = _init_sqlite_factory()
    async with session_factory() as session:
        yield session


async def reset_sqlite_database() -> None:
    """
    Reset the SQLite database by dropping all existing tables and recreating them.
    """
    engine, _ = _init_sqlite_factory()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
