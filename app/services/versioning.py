"""Versioning and Document Diff engine.

Implements the matching strategy and hierarchical diff generation between
two versions of a document.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import NodeORM


class DiffStatus:
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class DiffNode:
    """In-memory representation of a node in the diff tree."""

    id: Optional[int] = None
    section_number: str = ""
    title: str = ""
    content: str = ""
    level: int = 0
    node_type: str = "heading"
    page_number: int = 0
    content_hash: str = ""
    reading_order: int = 0
    status: str = DiffStatus.UNCHANGED
    content_diff: Optional[str] = None
    children: list[DiffNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the diff node to a nested dictionary."""
        return {
            "id": self.id,
            "section_number": self.section_number,
            "title": self.title,
            "content": self.content,
            "level": self.level,
            "node_type": self.node_type,
            "page_number": self.page_number,
            "content_hash": self.content_hash,
            "reading_order": self.reading_order,
            "status": self.status,
            "content_diff": self.content_diff,
            "children": [c.to_dict() for c in self.children],
        }


class VersioningService:
    """Orchestrates tree-matching and generates detailed diff summaries."""

    def __init__(self):
        pass

    async def diff_versions(
        self,
        db: AsyncSession,
        document_id: int,
        v1_num: int,
        v2_num: int,
    ) -> dict[str, Any]:
        """Compare two versions of a document and return a detailed diff summary.

        Args:
            db: Async database session.
            document_id: The ID of the document.
            v1_num: Version number of the older version.
            v2_num: Version number of the newer version.

        Returns:
            Dict representing the DiffSummaryResponse.
        """
        # 1. Fetch nodes for V1
        v1_nodes = await self._fetch_version_nodes(db, document_id, v1_num)
        # 2. Fetch nodes for V2
        v2_nodes = await self._fetch_version_nodes(db, document_id, v2_num)

        if not v1_nodes or not v2_nodes:
            raise ValueError(f"Could not find nodes for version {v1_num} or {v2_num}")

        # 3. Build trees from lists
        v1_root = self._build_tree_from_nodes(v1_nodes)
        v2_root = self._build_tree_from_nodes(v2_nodes)

        # 4. Perform tree diff
        diff_tree = self.diff_nodes(v1_root, v2_root)

        # 5. Calculate summary counts
        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
        self._collect_counts(diff_tree, counts)

        return {
            "document_id": document_id,
            "v1_version_number": v1_num,
            "v2_version_number": v2_num,
            "added_count": counts["added"],
            "removed_count": counts["removed"],
            "modified_count": counts["modified"],
            "unchanged_count": counts["unchanged"],
            "diff_tree": diff_tree.to_dict() if diff_tree else None,
        }

    async def _fetch_version_nodes(
        self, db: AsyncSession, document_id: int, version_number: int
    ) -> list[NodeORM]:
        """Fetch all nodes for a specific version from the database."""
        # First find the version ID
        from app.models.db_models import VersionORM
        result = await db.execute(
            select(VersionORM).where(
                VersionORM.document_id == document_id,
                VersionORM.version_number == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            return []

        # Now fetch nodes ordered by reading_order
        node_result = await db.execute(
            select(NodeORM)
            .where(NodeORM.version_id == version.id)
            .order_by(NodeORM.reading_order)
        )
        return list(node_result.scalars().all())

    def _build_tree_from_nodes(self, nodes: list[NodeORM]) -> NodeORM:
        """Helper to reconstruct the parent-child relationships in memory."""
        if not nodes:
            raise ValueError("Empty node list")

        node_map: dict[int, NodeORM] = {n.id: n for n in nodes}
        root = None

        # Build child lists dynamically in-memory using python attributes
        for n in nodes:
            n.temp_children = []

        for n in nodes:
            if n.parent_id is None:
                root = n
            else:
                parent = node_map.get(n.parent_id)
                if parent:
                    if not hasattr(parent, "temp_children"):
                        parent.temp_children = []
                    parent.temp_children.append(n)

        if root is None:
            # Fallback if no single root is found
            root = nodes[0]

        return root

    def diff_nodes(self, v1_node: NodeORM, v2_node: NodeORM) -> DiffNode:
        """Recursively match and diff v1 and v2 nodes."""
        status = DiffStatus.UNCHANGED
        content_diff = None

        # Check if content has changed
        if v1_node.content_hash != v2_node.content_hash:
            status = DiffStatus.MODIFIED
            content_diff = self._generate_content_diff(v1_node.content, v2_node.content)

        diff_node = DiffNode(
            id=v2_node.id,
            section_number=v2_node.section_number,
            title=v2_node.title,
            content=v2_node.content,
            level=v2_node.level,
            node_type=v2_node.node_type,
            page_number=v2_node.page_number,
            content_hash=v2_node.content_hash,
            reading_order=v2_node.reading_order,
            status=status,
            content_diff=content_diff,
        )

        # Reconstruct children of v1 and v2
        v1_children = getattr(v1_node, "temp_children", [])
        v2_children = getattr(v2_node, "temp_children", [])

        # Match children of v1 and v2
        matched_pairs: list[tuple[Optional[NodeORM], Optional[NodeORM]]] = []
        matched_v1_ids = set()
        matched_v2_ids = set()

        # Step 1: Match by exact title match (most stable across renumbering)
        for child_v2 in v2_children:
            for child_v1 in v1_children:
                if child_v1.id in matched_v1_ids:
                    continue
                # Normalize titles for matching
                if child_v1.title.strip().lower() == child_v2.title.strip().lower():
                    matched_pairs.append((child_v1, child_v2))
                    matched_v1_ids.add(child_v1.id)
                    matched_v2_ids.add(child_v2.id)
                    break

        # Step 2: Match remaining by section number (covers title corrections/refinements)
        for child_v2 in v2_children:
            if child_v2.id in matched_v2_ids:
                continue
            for child_v1 in v1_children:
                if child_v1.id in matched_v1_ids:
                    continue
                # If section number matches exactly (e.g. 1.1)
                if (
                    child_v1.section_number
                    and child_v1.section_number == child_v2.section_number
                ):
                    matched_pairs.append((child_v1, child_v2))
                    matched_v1_ids.add(child_v1.id)
                    matched_v2_ids.add(child_v2.id)
                    break

        # Step 3: Match remaining by fuzzy title similarity
        for child_v2 in v2_children:
            if child_v2.id in matched_v2_ids:
                continue
            best_match = None
            best_score = 0.0
            for child_v1 in v1_children:
                if child_v1.id in matched_v1_ids:
                    continue
                score = self._title_similarity(child_v1.title, child_v2.title)
                if score > best_score:
                    best_score = score
                    best_match = child_v1

            if best_match and best_score >= 0.7:  # high confidence match
                matched_pairs.append((best_match, child_v2))
                matched_v1_ids.add(best_match.id)
                matched_v2_ids.add(child_v2.id)

        # Step 4: Any remaining v2 children are ADDED
        for child_v2 in v2_children:
            if child_v2.id not in matched_v2_ids:
                matched_pairs.append((None, child_v2))

        # Step 5: Any remaining v1 children are REMOVED
        for child_v1 in v1_children:
            if child_v1.id not in matched_v1_ids:
                matched_pairs.append((child_v1, None))

        # Sort all matched pairs so the resulting diff tree children list respects
        # V2 reading order where possible, followed by any removed V1 nodes at the end.
        def get_sort_key(pair: tuple[Optional[NodeORM], Optional[NodeORM]]) -> int:
            v1_c, v2_c = pair
            if v2_c is not None:
                return v2_c.reading_order
            elif v1_c is not None:
                # Place removed nodes near their original position relative to siblings
                return v1_c.reading_order + 1000000
            return 0

        matched_pairs.sort(key=get_sort_key)

        # Recursively build the diff tree children
        for v1_c, v2_c in matched_pairs:
            if v1_c is not None and v2_c is not None:
                child_diff = self.diff_nodes(v1_c, v2_c)
                diff_node.children.append(child_diff)
            elif v2_c is not None:
                # ADDED node
                child_diff = self._create_subtree_diff(v2_c, DiffStatus.ADDED)
                diff_node.children.append(child_diff)
            elif v1_c is not None:
                # REMOVED node
                child_diff = self._create_subtree_diff(v1_c, DiffStatus.REMOVED)
                diff_node.children.append(child_diff)

        # If any child is modified, added, or removed, propagate modified status
        # upwards if the parent was otherwise unchanged. This helps users spot deep updates.
        has_changes = any(c.status != DiffStatus.UNCHANGED for c in diff_node.children)
        if diff_node.status == DiffStatus.UNCHANGED and has_changes:
            diff_node.status = DiffStatus.MODIFIED

        return diff_node

    def _create_subtree_diff(self, node: NodeORM, status: str) -> DiffNode:
        """Recursively marks an entire subtree with the given status (ADDED/REMOVED)."""
        diff_node = DiffNode(
            id=node.id if status == DiffStatus.ADDED else None,  # None for removed
            section_number=node.section_number,
            title=node.title,
            content=node.content,
            level=node.level,
            node_type=node.node_type,
            page_number=node.page_number,
            content_hash=node.content_hash,
            reading_order=node.reading_order,
            status=status,
            content_diff=None,
        )

        children = getattr(node, "temp_children", [])
        for child in children:
            diff_node.children.append(self._create_subtree_diff(child, status))

        return diff_node

    def _title_similarity(self, t1: str, t2: str) -> float:
        """Returns similarity ratio between two strings (0.0 to 1.0)."""
        return difflib.SequenceMatcher(None, t1.strip().lower(), t2.strip().lower()).ratio()

    def _generate_content_diff(self, old_content: str, new_content: str) -> str:
        """Produce a clean human-readable diff highlight of the content changes."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        diff = list(difflib.ndiff(old_lines, new_lines))
        # Keep only the modified lines (+/-) to make the response compact
        diff_summary = []
        for line in diff:
            if line.startswith("+ ") or line.startswith("- "):
                diff_summary.append(line)

        return "\n".join(diff_summary) if diff_summary else "Content modified"

    def _collect_counts(self, node: Optional[DiffNode], counts: dict[str, int]) -> None:
        """Traverse the diff tree and accumulate status counts."""
        if not node:
            return

        # Skip the virtual root node (level 0) when counting nodes
        if node.level > 0:
            counts[node.status] += 1

        for child in node.children:
            self._collect_counts(child, counts)
