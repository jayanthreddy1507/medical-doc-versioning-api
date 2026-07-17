"""Shared test fixtures — ensures DB tables exist before tests run."""

import pytest

from app.database import engine
from app.models.base import Base
# Import all ORM models so Base.metadata knows about them
from app.models import DocumentORM, NodeORM, VersionORM  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all database tables before the test session starts.

    The app's lifespan event doesn't fire during tests via ASGITransport,
    so we manually create tables here. Uses the same in-memory/file DB
    as the app (configured via DATABASE_URL).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Optionally drop tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
