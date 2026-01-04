"""
PostgreSQL async database connection using SQLAlchemy 2.0.
This is the authoritative source of truth for attendance and transactions.

Supports both local PostgreSQL and Render PostgreSQL (with SSL).
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
import ssl

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def _create_engine():
    """Create async engine with appropriate SSL settings."""
    postgres_url = settings.postgres_url
    
    # Engine configuration
    engine_options = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,  # Recycle connections every 5 minutes
    }
    
    # For production (when DATABASE_URL is set), configure SSL
    if settings.DATABASE_URL and not settings.DEBUG:
        # asyncpg handles SSL via the URL parameter sslmode=require
        # which is already added in config.py
        pass
    
    return create_async_engine(postgres_url, **engine_options)


# Create async engine
engine = _create_engine()

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async PostgreSQL session.
    Automatically handles commit/rollback.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_postgres() -> None:
    """Initialize PostgreSQL database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_postgres() -> None:
    """Close PostgreSQL connections."""
    await engine.dispose()
