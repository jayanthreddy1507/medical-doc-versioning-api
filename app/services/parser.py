"""PDF parser with hierarchy extraction and irregularity handling.

Architecture:
  1. Extract raw text spans with font metadata (PyMuPDF dict mode)
  2. Merge spans into logical lines
  3. Classify each line as heading vs body vs table content
  4. Detect section numbers via regex
  5. Build the document tree, handling:
     - Out-of-order section numbers (preserve reading order)
     - Skipped heading levels (create synthetic parents)
     - Duplicate section numbers (disambiguate with suffix)
     - Table detection via same-y-coordinate clustering
  6. Compute content hashes per node

Why PyMuPDF over pdfplumber:
  - PyMuPDF gives per-span font metadata (size, bold flags, font name)
    which is critical for heading detection heuristics
  - 10-50× faster than pdfplumber for large documents
  - Native support for text dict extraction with bbox coordinates
  - pdfplumber is better for table extraction but we can handle simple
    tables with y-coordinate clustering in PyMuPDF
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.models.document import (
    DocumentNode,
    FontInfo,
    NodeType,
    ParsedDocument,
)

# ── Section number regex ────────────────────────────────────────────────
# Matches patterns like "1", "1.1", "2.1.1.1", etc. at start of text.
# Supports optional trailing dot like "1. Device Overview"
SECTION_NUMBER_RE = re.compile(
    r"^(\d+(?:\.\d+)*\.?)\s+"
)


@dataclass
class RawSpan:
    """A single text span extracted from the PDF with its metadata."""

    text: str
    font_size: float
    is_bold: bool
    is_italic: bool
    font_name: str
    page_number: int  # 1-indexed
    x: float
    y: float
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)


@dataclass
class LogicalLine:
    """Merged spans that form a single logical line of text."""

    text: str
    font_size: float
    is_bold: bool
    is_italic: bool
    font_name: str
    page_number: int
    y: float
    x: float
    spans: list[RawSpan] = field(default_factory=list)

    @property
    def font_info(self) -> FontInfo:
        return FontInfo(
            size=self.font_size,
            is_bold=self.is_bold,
            is_italic=self.is_italic,
            font_name=self.font_name,
        )


@dataclass
class TableBlock:
    """A detected table: rows of cells at same y-coordinates."""

    page_number: int
    header_row: list[str]
    data_rows: list[list[str]]
    y_start: float
    y_end: float

    @property
    def as_text(self) -> str:
        """Render table as plain text for content hashing."""
        lines = [" | ".join(self.header_row)]
        lines.append("-" * len(lines[0]))
        for row in self.data_rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)


class PDFParser:
    """Parses a PDF into a structured document tree.

    Usage:
        parser = PDFParser()
        doc = parser.parse("path/to/manual.pdf")
        # doc.root contains the full tree
        # doc.irregularities lists all anomalies found
    """

    # Font size thresholds for heading detection (tuned from real inspection)
    # These are configurable per-document if needed
    TITLE_MIN_SIZE = 16.0
    H1_MIN_SIZE = 14.0
    H2_MIN_SIZE = 12.0
    H3_MIN_SIZE = 11.0
    H4_MIN_SIZE = 10.2
    BODY_MAX_SIZE = 10.0
    TABLE_MAX_SIZE = 9.5

    # Y-coordinate tolerance for grouping spans into same line
    Y_TOLERANCE = 2.0

    def __init__(self, font_thresholds: Optional[dict] = None):
        """Initialize parser with optional custom font size thresholds."""
        if font_thresholds:
            for key, value in font_thresholds.items():
                if hasattr(self, key):
                    setattr(self, key, value)

        self._irregularities: list[str] = []
        self._reading_order_counter = 0

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        """Parse a PDF file and return a structured document tree.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ParsedDocument with the full hierarchy tree and irregularity log.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self._irregularities = []
        self._reading_order_counter = 0

        doc = fitz.open(str(pdf_path))

        try:
            # Step 1: Extract raw spans
            raw_spans = self._extract_spans(doc)

            # Step 2: Merge into logical lines
            lines = self._merge_into_lines(raw_spans)

            # Step 3: Detect tables and separate them
            lines, tables = self._detect_tables(lines)

            # Step 4: Classify lines and build tree
            root = self._build_tree(lines, tables)

            # Step 5: Recompute all hashes
            root.recompute_hashes()

            return ParsedDocument(
                filename=pdf_path.name,
                total_pages=doc.page_count,
                root=root,
                irregularities=list(self._irregularities),
            )
        finally:
            doc.close()

    def _extract_spans(self, doc: fitz.Document) -> list[RawSpan]:
        """Extract all text spans with font metadata from the PDF."""
        spans = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] != 0:  # Skip non-text blocks
                    continue

                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"]
                        if not text.strip():
                            continue

                        flags = span["flags"]
                        spans.append(RawSpan(
                            text=text,
                            font_size=round(span["size"], 1),
                            is_bold=bool(flags & (1 << 4)),  # bit 4
                            is_italic=bool(flags & (1 << 1)),  # bit 1
                            font_name=span["font"],
                            page_number=page_num + 1,
                            x=span["origin"][0],
                            y=span["origin"][1],
                            bbox=tuple(span["bbox"]),
                        ))

        return spans

    def _merge_into_lines(self, spans: list[RawSpan]) -> list[LogicalLine]:
        """Merge spans at the same y-coordinate into logical lines.

        Spans on the same line (within Y_TOLERANCE) with the same font
        properties are merged. Spans with different fonts at the same y
        are kept separate (these are likely table cells).
        """
        if not spans:
            return []

        # Group by (page, approximate y)
        lines: list[LogicalLine] = []
        current_line_spans: list[RawSpan] = [spans[0]]

        for span in spans[1:]:
            prev = current_line_spans[-1]

            same_page = span.page_number == prev.page_number
            same_y = abs(span.y - prev.y) < self.Y_TOLERANCE
            same_font = (
                abs(span.font_size - prev.font_size) < 0.5
                and span.is_bold == prev.is_bold
            )

            if same_page and same_y and same_font:
                # Same logical line, same font → merge text
                current_line_spans.append(span)
            elif same_page and same_y and not same_font:
                # Same y but different font — for small fonts (tables),
                # merge anyway since table rows mix bold headers and data
                if span.font_size <= self.TABLE_MAX_SIZE:
                    current_line_spans.append(span)
                else:
                    lines.append(self._finalize_line(current_line_spans))
                    current_line_spans = [span]
            else:
                # Different line entirely
                lines.append(self._finalize_line(current_line_spans))
                current_line_spans = [span]

        if current_line_spans:
            lines.append(self._finalize_line(current_line_spans))

        return lines

    def _finalize_line(self, spans: list[RawSpan]) -> LogicalLine:
        """Create a LogicalLine from a group of same-line spans."""
        text = " ".join(s.text for s in spans)
        # Use dominant font properties
        first = spans[0]
        return LogicalLine(
            text=text.strip(),
            font_size=first.font_size,
            is_bold=first.is_bold,
            is_italic=first.is_italic,
            font_name=first.font_name,
            page_number=first.page_number,
            y=first.y,
            x=first.x,
            spans=list(spans),
        )

    def _detect_tables(
        self, lines: list[LogicalLine]
    ) -> tuple[list[LogicalLine], list[TableBlock]]:
        """Detect table regions and extract them from the line stream.

        Heuristic: Lines at ≤TABLE_MAX_SIZE font with multiple spans
        at the same y-coordinate are table rows. A sequence of such
        rows forms a table.

        Returns:
            (non_table_lines, detected_tables)
        """
        non_table_lines: list[LogicalLine] = []
        tables: list[TableBlock] = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Table detection: small font + multiple spans at same y
            if (
                line.font_size <= self.TABLE_MAX_SIZE
                and len(line.spans) >= 2
            ):
                # Found potential table start — collect consecutive table rows
                table_lines = []
                table_page = lines[i].page_number  # Save page before i advances
                while i < len(lines) and lines[i].font_size <= self.TABLE_MAX_SIZE:
                    # Collect ALL spans at this y-coordinate (they may have been
                    # split into separate LogicalLines for different fonts)
                    row_y = lines[i].y
                    row_page = lines[i].page_number
                    row_spans = []

                    while (
                        i < len(lines)
                        and lines[i].page_number == row_page
                        and abs(lines[i].y - row_y) < self.Y_TOLERANCE
                    ):
                        row_spans.extend(lines[i].spans)
                        i += 1

                    if row_spans:
                        # Sort spans by x-coordinate to get column order
                        row_spans.sort(key=lambda s: s.x)
                        cells = [s.text.strip() for s in row_spans]
                        table_lines.append((cells, row_spans[0].is_bold, row_y))

                if table_lines:
                    # First bold row is the header
                    header_idx = 0
                    for idx, (cells, is_bold, _) in enumerate(table_lines):
                        if is_bold:
                            header_idx = idx
                            break

                    header = table_lines[header_idx][0]
                    data_rows = [
                        cells for cells, is_bold, _ in table_lines
                        if not is_bold or cells == header
                    ]
                    # Remove header from data if it's there
                    data_rows = [r for r in data_rows if r != header]

                    tables.append(TableBlock(
                        page_number=table_page,
                        header_row=header,
                        data_rows=data_rows,
                        y_start=table_lines[0][2],
                        y_end=table_lines[-1][2],
                    ))
                continue

            non_table_lines.append(line)
            i += 1

        return non_table_lines, tables

    def _classify_heading_level(self, line: LogicalLine) -> int:
        """Determine heading level from font size and section number.

        Returns 0 for body text, 1-4 for heading levels.
        The section number depth takes precedence when available.
        """
        match = SECTION_NUMBER_RE.match(line.text)
        if match and line.is_bold and line.font_size > self.BODY_MAX_SIZE:
            # Has section number AND looks like a heading
            section_num = match.group(1).rstrip(".")
            return DocumentNode.parse_level_from_number(section_num)

        # Title detection (no section number, very large)
        if line.font_size >= self.TITLE_MIN_SIZE and line.is_bold:
            return 0  # treated as document title, not a numbered section

        # Fallback to font-size based classification
        if line.is_bold:
            if line.font_size >= self.H1_MIN_SIZE:
                return 1
            elif line.font_size >= self.H2_MIN_SIZE:
                return 2
            elif line.font_size >= self.H3_MIN_SIZE:
                return 3
            elif line.font_size >= self.H4_MIN_SIZE:
                return 4

        return 0  # body text

    def _build_tree(
        self, lines: list[LogicalLine], tables: list[TableBlock]
    ) -> DocumentNode:
        """Build the document hierarchy tree from classified lines.

        Handles:
          - Out-of-order sections: preserves reading order in children list
          - Skipped levels: logs irregularity but inserts at correct depth
          - Duplicate numbers: appends suffix like "4.2_dup1"
        """
        root = DocumentNode(
            node_type=NodeType.ROOT,
            title="Document Root",
            level=0,
            reading_order=self._next_reading_order(),
        )

        # Track seen section numbers for duplicate detection
        seen_sections: dict[str, int] = {}

        # Stack-based tree building: stack holds (level, node) pairs
        # representing the current path from root to the active insertion point
        stack: list[tuple[int, DocumentNode]] = [(0, root)]

        # Track previous heading's section number for out-of-order detection
        prev_section_by_level: dict[int, str] = {}

        # Pending body text accumulator
        pending_content_lines: list[str] = []
        table_idx = 0  # Index into tables list

        for line in lines:
            heading_level = self._classify_heading_level(line)

            if heading_level == 0:
                # Body text — accumulate for current heading
                pending_content_lines.append(line.text)
                continue

            # ── We have a heading ──────────────────────────────────────

            # Flush pending body text to the current node
            self._flush_content(stack, pending_content_lines)
            pending_content_lines = []

            # Attach any tables that appeared before this heading
            while table_idx < len(tables):
                table = tables[table_idx]
                # Simple heuristic: table belongs to the section that
                # precedes it (by page and y-position)
                if (
                    table.page_number < line.page_number
                    or (
                        table.page_number == line.page_number
                        and table.y_start < line.y
                    )
                ):
                    self._attach_table(stack, table)
                    table_idx += 1
                else:
                    break

            # Parse section number and title
            match = SECTION_NUMBER_RE.match(line.text)
            if match:
                section_number = match.group(1).rstrip(".")
                title = line.text[match.end():].strip()
            else:
                section_number = ""
                title = line.text.strip()

            # ── Irregularity detection ─────────────────────────────────

            # Check for duplicate section numbers
            original_section = section_number
            if section_number in seen_sections:
                seen_sections[section_number] += 1
                dup_count = seen_sections[section_number]
                self._irregularities.append(
                    f"DUPLICATE_NUMBER: Section '{section_number}' appears "
                    f"multiple times (occurrence #{dup_count + 1}). "
                    f"Title: '{title}'"
                )
                section_number = f"{section_number}_dup{dup_count}"
            else:
                seen_sections[original_section] = 0

            # Check for out-of-order sections
            if section_number and heading_level in prev_section_by_level:
                prev = prev_section_by_level[heading_level]
                if prev and self._compare_section_numbers(section_number, prev) < 0:
                    self._irregularities.append(
                        f"OUT_OF_ORDER: Section '{original_section} {title}' "
                        f"appears after '{prev}' in reading order "
                        f"(expected numeric order)"
                    )

            # Check for skipped heading levels
            if heading_level > 1 and section_number:
                expected_parent_level = heading_level - 1
                parent_found = any(
                    lvl == expected_parent_level for lvl, _ in stack
                )
                if not parent_found:
                    # Find the deepest section number parts
                    parts = section_number.split(".")
                    if len(parts) >= 2:
                        expected_parent_num = ".".join(parts[:-1])
                        if expected_parent_num not in seen_sections:
                            self._irregularities.append(
                                f"SKIPPED_LEVEL: Section '{original_section} {title}' "
                                f"at level {heading_level} has no parent section "
                                f"'{expected_parent_num}' (level {expected_parent_level})"
                            )

            if section_number:
                prev_section_by_level[heading_level] = original_section

            # ── Create and insert the node ─────────────────────────────
            node = DocumentNode(
                section_number=section_number,
                title=title,
                level=heading_level,
                node_type=NodeType.HEADING,
                page_number=line.page_number,
                font_info=line.font_info,
                reading_order=self._next_reading_order(),
            )

            # Pop stack until we find the correct parent level
            while len(stack) > 1 and stack[-1][0] >= heading_level:
                stack.pop()

            # Attach to parent
            parent = stack[-1][1]
            parent.children.append(node)

            # Push this node onto the stack
            stack.append((heading_level, node))

        # Flush remaining body text
        self._flush_content(stack, pending_content_lines)

        # Attach any remaining tables
        while table_idx < len(tables):
            self._attach_table(stack, tables[table_idx])
            table_idx += 1

        return root

    def _flush_content(
        self,
        stack: list[tuple[int, DocumentNode]],
        content_lines: list[str],
    ) -> None:
        """Append accumulated body text to the current (deepest) node."""
        if not content_lines:
            return
        current_node = stack[-1][1]
        text = " ".join(content_lines).strip()
        if current_node.content:
            current_node.content += " " + text
        else:
            current_node.content = text

    def _attach_table(
        self,
        stack: list[tuple[int, DocumentNode]],
        table: TableBlock,
    ) -> None:
        """Attach a detected table as content of the current node."""
        current_node = stack[-1][1]
        table_text = table.as_text
        if current_node.content:
            current_node.content += "\n\n" + table_text
        else:
            current_node.content = table_text

    def _compare_section_numbers(self, a: str, b: str) -> int:
        """Compare two section numbers numerically.

        Returns:
            -1 if a < b, 0 if equal, 1 if a > b
        """
        # Strip any duplicate suffixes for comparison
        a_clean = a.split("_dup")[0]
        b_clean = b.split("_dup")[0]

        a_parts = [int(p) for p in a_clean.split(".") if p.isdigit()]
        b_parts = [int(p) for p in b_clean.split(".") if p.isdigit()]

        for ap, bp in zip(a_parts, b_parts):
            if ap < bp:
                return -1
            if ap > bp:
                return 1

        if len(a_parts) < len(b_parts):
            return -1
        if len(a_parts) > len(b_parts):
            return 1
        return 0

    def _next_reading_order(self) -> int:
        """Get the next reading order index."""
        idx = self._reading_order_counter
        self._reading_order_counter += 1
        return idx
