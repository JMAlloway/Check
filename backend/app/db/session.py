"""Database session configuration."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    IMPORTANT: This does NOT auto-commit. Endpoints that modify data must
    explicitly call `await db.commit()` to persist changes. This prevents
    accidental data persistence from read-only operations.

    For write operations, use the pattern:
        await db.add(obj)
        await db.commit()
        await db.refresh(obj)

    For read-only operations, no commit is needed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # NO AUTO-COMMIT: Endpoints must explicitly commit writes
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
