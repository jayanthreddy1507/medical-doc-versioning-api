"""SQLAlchemy declarative base for all models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models.

    Add common columns (id, created_at, updated_at) here
    when domain models are introduced in Phase 1.
    """

    pass
