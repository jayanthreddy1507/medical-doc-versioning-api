"""SQLAlchemy ORM models for persistent document storage.

Tables:
  - documents:  One row per unique PDF document (by filename).
  - versions:   One row per ingested version of a document.
  - nodes:      One row per section/heading in a parsed document tree.
                Linked to a version, with parent_id for tree structure.

Design decisions:
  - documents track the document identity across versions.
  - versions store the parse metadata and link to the document + root node tree.
  - nodes use an adjacency list (parent_id → self-join) for the tree.
    This is simpler than nested sets and sufficient for our read patterns.
  - content_hash on nodes enables fast diff between versions.
  - reading_order preserves the original PDF reading sequence.
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Column,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DocumentORM(Base):
    """A unique document tracked across versions.

    One row per logical document (identified by filename).
    Multiple versions can exist for the same document.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions: Mapped[list["VersionORM"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="VersionORM.version_number"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}')>"


class VersionORM(Base):
    """A specific parsed version of a document.

    Each time a PDF is ingested, a new version is created.
    The version stores metadata and links to the root of the node tree.
    """

    __tablename__ = "versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    irregularities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["DocumentORM"] = relationship(back_populates="versions")
    nodes: Mapped[list["NodeORM"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Version(id={self.id}, doc_id={self.document_id}, v={self.version_number})>"


class NodeORM(Base):
    """A single node in the parsed document tree.

    Uses adjacency list pattern (parent_id → self-join) for hierarchy.
    Each node belongs to exactly one version.
    """

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )

    section_number: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, default="heading")
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Font metadata (nullable — only set for headings)
    font_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    font_bold: Mapped[Optional[bool]] = mapped_column(nullable=True)
    font_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Relationships
    version: Mapped["VersionORM"] = relationship(back_populates="nodes")
    parent: Mapped[Optional["NodeORM"]] = relationship(
        remote_side=[id], backref="children"
    )

    def __repr__(self) -> str:
        return f"<Node(id={self.id}, section='{self.section_number}', title='{self.title[:30]}')>"


# ── Selection and Node Mapping Table ──────────────────────────────────────

selection_nodes = Table(
    "selection_nodes",
    Base.metadata,
    Column(
        "selection_id",
        Integer,
        ForeignKey("selections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "node_id",
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SelectionORM(Base):
    """A named, version-pinned selection of document nodes."""

    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    nodes: Mapped[list["NodeORM"]] = relationship(
        secondary=selection_nodes,
        backref="selections",
    )
    generations: Mapped[list["GenerationORM"]] = relationship(
        back_populates="selection", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Selection(id={self.id}, name='{self.name}')>"


class GenerationORM(Base):
    """An LLM-generated set of QA test cases for a specific selection."""

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    selection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    test_cases: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized list of test cases
    node_hashes: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialized map of node_id -> content_hash
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    selection: Mapped["SelectionORM"] = relationship(back_populates="generations")

    def __repr__(self) -> str:
        return f"<Generation(id={self.id}, selection_id={self.selection_id})>"
