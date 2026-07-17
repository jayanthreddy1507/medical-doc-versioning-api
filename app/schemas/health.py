"""Pydantic schemas for the health endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str = "ok"
    app_name: str
    version: str
