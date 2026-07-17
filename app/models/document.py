"""Domain models for parsed document tree structure.

The document hierarchy is represented as a tree of DocumentNode objects.
Each node captures:
  - Its position in the numbering scheme (section_number)
  - Its heading text and body content
  - A content hash for change detection across versions
  - Font metadata used during parsing (size, flags)
  - Child nodes forming the subtree

Design decisions:
  - content_hash uses SHA-256 over (section_number + title + content) so
    moves/renames are detected as changes.
  - children are an ordered list; insertion order matches document order,
    NOT necessarily numeric order (to preserve out-of-order sections like
    3.4 appearing before 3.3 in reading order).
  - level is derived from the section_number depth (e.g. "2.1.1" → level 3),
    but stored explicitly to handle edge cases like skipped levels.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    """Classification of document nodes."""

    ROOT = "root"
    HEADING = "heading"
    TABLE = "table"
    FIGURE = "figure"
    BODY_TEXT = "body_text"


@dataclass
class FontInfo:
    """Font metadata extracted from PDF for heading heuristics."""

    size: float = 12.0
    is_bold: bool = False
    is_italic: bool = False
    font_name: str = ""

    @property
    def weight_score(self) -> float:
        """Heuristic score: larger/bolder text → higher score → higher heading level."""
        score = self.size
        if self.is_bold:
            score += 2.0
        return score


@dataclass
class DocumentNode:
    """A single node in the document hierarchy tree.

    Attributes:
        section_number: The original numbering string, e.g. "3.4.1".
                        Empty string for root or unnumbered content.
        title:          Heading text (e.g. "Auto Shutoff").
        content:        Body text under this heading, before the next heading.
        level:          Depth in the tree (0 = root, 1 = top-level section).
        node_type:      Classification (heading, table, etc.).
        page_number:    1-indexed page where this node starts.
        font_info:      Font metadata from the PDF.
        children:       Ordered child nodes.
        content_hash:   SHA-256 hash for version comparison.
        reading_order:  Position in document reading order (0-indexed).
    """

    section_number: str = ""
    title: str = ""
    content: str = ""
    level: int = 0
    node_type: NodeType = NodeType.HEADING
    page_number: int = 0
    font_info: Optional[FontInfo] = None
    children: list[DocumentNode] = field(default_factory=list)
    content_hash: str = ""
    reading_order: int = 0

    def __post_init__(self):
        """Compute content hash if not already set."""
        if not self.content_hash:
            self.content_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """SHA-256 of (section_number + title + content) for change detection."""
        payload = f"{self.section_number}|{self.title}|{self.content}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def recompute_hashes(self) -> None:
        """Recursively recompute hashes for this node and all descendants."""
        self.content_hash = self.compute_hash()
        for child in self.children:
            child.recompute_hashes()

    @staticmethod
    def parse_level_from_number(section_number: str) -> int:
        """Derive tree depth from section number.

        Examples:
            "1"       → 1
            "2.1"     → 2
            "2.1.1.1" → 4
            ""        → 0  (root/unnumbered)
        """
        if not section_number or not section_number.strip():
            return 0
        parts = section_number.strip().split(".")
        # Filter out empty parts from trailing dots like "3."
        parts = [p for p in parts if p.strip()]
        return len(parts)

    def find_by_section(self, section_number: str) -> Optional[DocumentNode]:
        """DFS search for a node with the given section number."""
        if self.section_number == section_number:
            return self
        for child in self.children:
            result = child.find_by_section(section_number)
            if result:
                return result
        return None

    def flatten(self) -> list[DocumentNode]:
        """Return all nodes in pre-order traversal (reading order)."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def to_dict(self) -> dict:
        """Serialize to a dictionary for JSON export."""
        return {
            "section_number": self.section_number,
            "title": self.title,
            "content": self.content[:200] + ("..." if len(self.content) > 200 else ""),
            "level": self.level,
            "node_type": self.node_type.value,
            "page_number": self.page_number,
            "content_hash": self.content_hash,
            "reading_order": self.reading_order,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ParsedDocument:
    """Root container for a fully parsed PDF document.

    Attributes:
        filename:       Original PDF filename.
        total_pages:    Number of pages in the PDF.
        root:           The root DocumentNode (level 0).
        irregularities: List of parsing warnings/notes found.
    """

    filename: str = ""
    total_pages: int = 0
    root: DocumentNode = field(default_factory=lambda: DocumentNode(
        node_type=NodeType.ROOT, title="Document Root"
    ))
    irregularities: list[str] = field(default_factory=list)

    @property
    def all_nodes(self) -> list[DocumentNode]:
        """Flat list of all nodes in reading order."""
        return self.root.flatten()

    @property
    def node_count(self) -> int:
        """Total number of nodes including root."""
        return len(self.all_nodes)
