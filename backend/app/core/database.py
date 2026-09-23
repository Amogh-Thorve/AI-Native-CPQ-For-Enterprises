from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings

import sys
from sqlalchemy.pool import NullPool

# Create async engine with pool configuration suitable for enterprise applications
# Use NullPool in pytest to avoid event-loop connection sharing across test cases
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if "pytest" in sys.modules:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy domain models.
    Provides metadata registry and general object representation.
    """
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency helper that yields an asynchronous database session.
    Automatically closes the session after request completion.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
