"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine
from app.models.base import Base
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (dev convenience — use Alembic in prod)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(
    health.router,
    prefix=settings.API_V1_PREFIX,
)
