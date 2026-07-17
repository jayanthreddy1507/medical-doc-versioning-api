"""Pydantic schemas for document ingestion and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Ingestion ────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    """Response after successfully ingesting a PDF."""

    document_id: int
    version_id: int
    version_number: int
    filename: str
    total_pages: int
    node_count: int
    irregularities: list[str] = Field(default_factory=list)
    message: str = "Document ingested successfully"


# ── Document listing ─────────────────────────────────────────────────────

class DocumentSummary(BaseModel):
    """Summary of a document (for listing endpoints)."""

    id: int
    filename: str
    title: Optional[str] = None
    version_count: int = 0
    latest_version: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VersionSummary(BaseModel):
    """Summary of a specific document version."""

    id: int
    version_number: int
    total_pages: int
    node_count: int
    irregularities: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Node tree ────────────────────────────────────────────────────────────

class NodeResponse(BaseModel):
    """A single node in the document tree."""

    id: int
    section_number: str = ""
    title: str = ""
    content: str = ""
    level: int = 0
    node_type: str = "heading"
    page_number: int = 0
    content_hash: str = ""
    reading_order: int = 0
    children: list[NodeResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class VersionDetailResponse(BaseModel):
    """Full version detail including the node tree."""

    id: int
    document_id: int
    version_number: int
    total_pages: int
    node_count: int
    irregularities: list[str] = Field(default_factory=list)
    created_at: datetime
    tree: Optional[NodeResponse] = None

    model_config = {"from_attributes": True}


# ── Diff and Version Matching ────────────────────────────────────────────

class NodeDiffResponse(BaseModel):
    """A single node in the hierarchical diff tree showing its change status."""

    id: Optional[int] = None  # None for removed nodes (since they only exist in v1 database)
    section_number: str = ""
    title: str = ""
    content: str = ""
    level: int = 0
    node_type: str = "heading"
    page_number: int = 0
    content_hash: str = ""
    reading_order: int = 0
    status: str  # "unchanged", "added", "removed", "modified"
    content_diff: Optional[str] = None  # Textual description of changes
    children: list[NodeDiffResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DiffSummaryResponse(BaseModel):
    """Summary of all changes between two document versions."""

    document_id: int
    v1_version_number: int
    v2_version_number: int
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    diff_tree: Optional[NodeDiffResponse] = None

