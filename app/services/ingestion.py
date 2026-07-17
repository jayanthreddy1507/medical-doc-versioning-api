"""Ingestion service — orchestrates PDF parsing and database persistence.

Flow:
  1. Save uploaded PDF to data/ directory
  2. Parse PDF into a DocumentNode tree via PDFParser
  3. Upsert the Document record (find-or-create by filename)
  4. Create a new Version record
  5. Recursively persist the node tree (DocumentNode → NodeORM)
  6. Return the ingestion result
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import DocumentORM, NodeORM, VersionORM
from app.models.document import DocumentNode, ParsedDocument
from app.services.parser import PDFParser


class IngestionService:
    """Handles end-to-end PDF ingestion: parse → persist."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.parser = PDFParser()

    async def ingest(
        self,
        db: AsyncSession,
        filename: str,
        file_content: bytes,
    ) -> dict:
        """Ingest a PDF file: save, parse, and persist to database.

        Args:
            db: Async database session.
            filename: Original filename of the uploaded PDF.
            file_content: Raw bytes of the PDF file.

        Returns:
            Dictionary with ingestion results (document_id, version_id, etc.)
        """
        # Step 1: Save PDF to disk
        pdf_path = self._save_pdf(filename, file_content)

        try:
            # Step 2: Parse PDF
            parsed = self.parser.parse(str(pdf_path))

            # Step 3: Find or create Document record
            doc_orm = await self._get_or_create_document(db, filename, parsed)

            # Step 4: Determine version number
            version_number = await self._next_version_number(db, doc_orm.id)

            # Step 5: Create Version record
            version_orm = VersionORM(
                document_id=doc_orm.id,
                version_number=version_number,
                total_pages=parsed.total_pages,
                node_count=parsed.node_count,
                irregularities=json.dumps(parsed.irregularities),
            )
            db.add(version_orm)
            await db.flush()  # Get version_orm.id

            # Step 6: Persist the node tree
            await self._persist_tree(db, version_orm.id, parsed.root, parent_id=None)

            # Count nodes actually persisted
            node_count_result = await db.execute(
                select(func.count(NodeORM.id)).where(NodeORM.version_id == version_orm.id)
            )
            actual_node_count = node_count_result.scalar()
            version_orm.node_count = actual_node_count

            return {
                "document_id": doc_orm.id,
                "version_id": version_orm.id,
                "version_number": version_number,
                "filename": filename,
                "total_pages": parsed.total_pages,
                "node_count": actual_node_count,
                "irregularities": parsed.irregularities,
            }

        except Exception:
            # Clean up saved PDF on failure
            if pdf_path.exists():
                pdf_path.unlink()
            raise

    def _save_pdf(self, filename: str, content: bytes) -> Path:
        """Save uploaded PDF bytes to the data directory."""
        # Sanitize filename
        safe_name = filename.replace("..", "").replace("/", "_").replace("\\", "_")
        pdf_path = self.data_dir / safe_name

        # Write atomically via temp file
        tmp_path = pdf_path.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(content)
            shutil.move(str(tmp_path), str(pdf_path))
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

        return pdf_path

    async def _get_or_create_document(
        self,
        db: AsyncSession,
        filename: str,
        parsed: ParsedDocument,
    ) -> DocumentORM:
        """Find existing document by filename or create a new one."""
        result = await db.execute(
            select(DocumentORM).where(DocumentORM.filename == filename)
        )
        doc_orm = result.scalar_one_or_none()

        if doc_orm is None:
            # Extract title from the parsed tree root content
            title = self._extract_title(parsed)
            doc_orm = DocumentORM(filename=filename, title=title)
            db.add(doc_orm)
            await db.flush()  # Get doc_orm.id

        return doc_orm

    async def _next_version_number(self, db: AsyncSession, document_id: int) -> int:
        """Get the next version number for a document."""
        result = await db.execute(
            select(func.max(VersionORM.version_number)).where(
                VersionORM.document_id == document_id
            )
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def _persist_tree(
        self,
        db: AsyncSession,
        version_id: int,
        node: DocumentNode,
        parent_id: Optional[int],
    ) -> int:
        """Recursively persist a DocumentNode tree to the database.

        Returns the ID of the persisted root node.
        """
        node_orm = NodeORM(
            version_id=version_id,
            parent_id=parent_id,
            section_number=node.section_number,
            title=node.title,
            content=node.content,
            level=node.level,
            node_type=node.node_type.value,
            page_number=node.page_number,
            content_hash=node.content_hash,
            reading_order=node.reading_order,
            font_size=node.font_info.size if node.font_info else None,
            font_bold=node.font_info.is_bold if node.font_info else None,
            font_name=node.font_info.font_name if node.font_info else None,
        )
        db.add(node_orm)
        await db.flush()  # Get node_orm.id

        # Recursively persist children
        for child in node.children:
            await self._persist_tree(db, version_id, child, parent_id=node_orm.id)

        return node_orm.id

    def _extract_title(self, parsed: ParsedDocument) -> str:
        """Extract a human-readable title from the parsed document."""
        # Try root content (title page text)
        if parsed.root.content:
            # First line of root content is usually the document title
            first_line = parsed.root.content.split("\n")[0].strip()
            if first_line:
                return first_line[:500]

        # Fallback: first child's title
        if parsed.root.children:
            return parsed.root.children[0].title[:500]

        return parsed.filename

    async def get_document_tree(
        self, db: AsyncSession, version_id: int
    ) -> Optional[dict]:
        """Reconstruct the document tree from the database for a given version.

        Returns a nested dictionary matching the NodeResponse schema.
        """
        result = await db.execute(
            select(NodeORM)
            .where(NodeORM.version_id == version_id)
            .order_by(NodeORM.reading_order)
        )
        nodes = result.scalars().all()

        if not nodes:
            return None

        # Build a lookup and reconstruct the tree
        node_map: dict[int, dict] = {}
        root = None

        for node in nodes:
            node_dict = {
                "id": node.id,
                "section_number": node.section_number,
                "title": node.title,
                "content": node.content,
                "level": node.level,
                "node_type": node.node_type,
                "page_number": node.page_number,
                "content_hash": node.content_hash,
                "reading_order": node.reading_order,
                "children": [],
            }
            node_map[node.id] = node_dict

            if node.parent_id is None:
                root = node_dict
            elif node.parent_id in node_map:
                node_map[node.parent_id]["children"].append(node_dict)

        return root

    async def get_top_level_sections(
        self, db: AsyncSession, document_id: int, version_number: int
    ) -> list[dict]:
        """Get top-level sections (level 1) of a specific document version."""
        # Find the version ID first
        result = await db.execute(
            select(VersionORM).where(
                VersionORM.document_id == document_id,
                VersionORM.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            return []

        # Get level 1 nodes for this version
        node_result = await db.execute(
            select(NodeORM)
            .where(NodeORM.version_id == version.id, NodeORM.level == 1)
            .order_by(NodeORM.reading_order)
        )
        nodes = node_result.scalars().all()

        return [
            {
                "id": node.id,
                "section_number": node.section_number,
                "title": node.title,
                "content": node.content,
                "level": node.level,
                "node_type": node.node_type,
                "page_number": node.page_number,
                "content_hash": node.content_hash,
                "reading_order": node.reading_order,
                "children": []  # Flat list of top-level sections, children excluded
            }
            for node in nodes
        ]

    async def get_node_by_id(self, db: AsyncSession, node_id: int) -> Optional[dict]:
        """Retrieve a specific node by ID, including its immediate children."""
        result = await db.execute(select(NodeORM).where(NodeORM.id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            return None

        # Fetch immediate children
        child_result = await db.execute(
            select(NodeORM)
            .where(NodeORM.parent_id == node_id)
            .order_by(NodeORM.reading_order)
        )
        children = child_result.scalars().all()

        return {
            "id": node.id,
            "section_number": node.section_number,
            "title": node.title,
            "content": node.content,
            "level": node.level,
            "node_type": node.node_type,
            "page_number": node.page_number,
            "content_hash": node.content_hash,
            "reading_order": node.reading_order,
            "children": [
                {
                    "id": c.id,
                    "section_number": c.section_number,
                    "title": c.title,
                    "content": c.content,
                    "level": c.level,
                    "node_type": c.node_type,
                    "page_number": c.page_number,
                    "content_hash": c.content_hash,
                    "reading_order": c.reading_order,
                    "children": []
                }
                for c in children
            ]
        }

    async def search_nodes(
        self, db: AsyncSession, document_id: int, query: str, version_number: int
    ) -> list[dict]:
        """Search/filter nodes by title or content in a specific document version."""
        result = await db.execute(
            select(VersionORM).where(
                VersionORM.document_id == document_id,
                VersionORM.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            return []

        # Find matching nodes
        search_query = f"%{query}%"
        node_result = await db.execute(
            select(NodeORM)
            .where(
                NodeORM.version_id == version.id,
                (NodeORM.title.like(search_query) | NodeORM.content.like(search_query))
            )
            .order_by(NodeORM.reading_order)
        )
        nodes = node_result.scalars().all()

        return [
            {
                "id": node.id,
                "section_number": node.section_number,
                "title": node.title,
                "content": node.content,
                "level": node.level,
                "node_type": node.node_type,
                "page_number": node.page_number,
                "content_hash": node.content_hash,
                "reading_order": node.reading_order,
            }
            for node in nodes
        ]
