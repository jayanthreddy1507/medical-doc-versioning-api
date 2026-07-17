"""Models package — import all models here for Alembic auto-detection."""

from app.models.base import Base  # noqa: F401

# Import future models below so Base.metadata picks them up:
# from app.models.user import User  # noqa: F401
