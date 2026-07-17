"""Tests for PDF parser targeting real irregularities.

Tests cover:
  1. Out-of-order subsections (3.4 before 3.3 in reading order)
  2. Skipped heading levels (2.1.1.1 without 2.1.1)
  3. Duplicate section numbering (two 4.2 sections)
  4. Table extraction (error codes table, maintenance table)
  5. Overall tree structure integrity
  6. Content hash computation and stability
  7. Section search and traversal
"""

import os
import pytest

from app.models.document import DocumentNode, NodeType, ParsedDocument
from app.services.parser import PDFParser
from tests.generate_test_pdf import generate_test_pdf


# ── Fixture: generate test PDF once per session ─────────────────────────

@pytest.fixture(scope="session")
def test_pdf_path(tmp_path_factory):
    """Generate the test PDF in a temp directory, shared across all tests."""
    tmp_dir = tmp_path_factory.mktemp("test_pdfs")
    pdf_path = str(tmp_dir / "test_manual.pdf")
    generate_test_pdf(pdf_path)
    return pdf_path


@pytest.fixture(scope="session")
def parsed_doc(test_pdf_path) -> ParsedDocument:
    """Parse the test PDF once and share across all tests."""
    parser = PDFParser()
    return parser.parse(test_pdf_path)


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Out-of-order subsections (3.4 appears before 3.3)
# ═══════════════════════════════════════════════════════════════════════

class TestOutOfOrderSections:
    """Section 3.4 'Auto Shutoff' appears before 3.3 'Result Display'
    in the PDF reading order. The parser must:
      - Preserve reading order in children list
      - Log the irregularity
    """

    def test_out_of_order_detected_in_irregularities(self, parsed_doc: ParsedDocument):
        """Parser should flag the out-of-order section."""
        out_of_order = [
            i for i in parsed_doc.irregularities if "OUT_OF_ORDER" in i
        ]
        assert len(out_of_order) >= 1, (
            f"Expected OUT_OF_ORDER irregularity, got: {parsed_doc.irregularities}"
        )
        # Should mention section 3.3
        assert any("3.3" in i for i in out_of_order), (
            f"OUT_OF_ORDER should reference section 3.3, got: {out_of_order}"
        )

    def test_reading_order_preserved(self, parsed_doc: ParsedDocument):
        """3.4 should appear before 3.3 in children order (reading order)."""
        section_3 = parsed_doc.root.find_by_section("3")
        assert section_3 is not None, "Section 3 not found"

        child_numbers = [c.section_number for c in section_3.children]
        assert "3.4" in child_numbers, f"3.4 not in children: {child_numbers}"
        assert "3.3" in child_numbers, f"3.3 not in children: {child_numbers}"

        idx_34 = child_numbers.index("3.4")
        idx_33 = child_numbers.index("3.3")
        assert idx_34 < idx_33, (
            f"3.4 (idx={idx_34}) should appear before 3.3 (idx={idx_33}) "
            f"to preserve reading order. Children: {child_numbers}"
        )

    def test_auto_shutoff_content(self, parsed_doc: ParsedDocument):
        """3.4 'Auto Shutoff' should have the correct content."""
        node = parsed_doc.root.find_by_section("3.4")
        assert node is not None, "Section 3.4 not found"
        assert node.title == "Auto Shutoff", f"Wrong title: {node.title}"
        assert "3 minutes" in node.content, (
            f"Expected '3 minutes' in content: {node.content}"
        )

    def test_result_display_has_child(self, parsed_doc: ParsedDocument):
        """3.3 'Result Display' should have 3.3.1 as a child."""
        node_33 = parsed_doc.root.find_by_section("3.3")
        assert node_33 is not None, "Section 3.3 not found"
        assert node_33.title == "Result Display", f"Wrong title: {node_33.title}"

        child_numbers = [c.section_number for c in node_33.children]
        assert "3.3.1" in child_numbers, (
            f"3.3.1 'Display Symbols' should be a child of 3.3. "
            f"Children: {child_numbers}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Skipped heading levels (2.1.1.1 without 2.1.1)
# ═══════════════════════════════════════════════════════════════════════

class TestSkippedHeadingLevels:
    """Section 2.1.1.1 'Electrode Specifications' exists at level 4
    but there is no parent 2.1.1 at level 3. The parser must:
      - Still build the node and place it under the nearest ancestor (2.1)
      - Log the skipped level irregularity
    """

    def test_skipped_level_detected(self, parsed_doc: ParsedDocument):
        """Parser should flag the skipped heading level."""
        skipped = [
            i for i in parsed_doc.irregularities if "SKIPPED_LEVEL" in i
        ]
        assert len(skipped) >= 1, (
            f"Expected SKIPPED_LEVEL irregularity, got: {parsed_doc.irregularities}"
        )
        assert any("2.1.1.1" in i for i in skipped), (
            f"SKIPPED_LEVEL should reference 2.1.1.1, got: {skipped}"
        )

    def test_node_exists_at_correct_level(self, parsed_doc: ParsedDocument):
        """2.1.1.1 should exist with level=4 despite skipped parent."""
        node = parsed_doc.root.find_by_section("2.1.1.1")
        assert node is not None, "Section 2.1.1.1 not found"
        assert node.level == 4, f"Expected level 4, got {node.level}"
        assert node.title == "Electrode Specifications", (
            f"Wrong title: {node.title}"
        )

    def test_parent_is_nearest_ancestor(self, parsed_doc: ParsedDocument):
        """2.1.1.1 should be placed under 2.1 (nearest existing ancestor)."""
        section_21 = parsed_doc.root.find_by_section("2.1")
        assert section_21 is not None, "Section 2.1 not found"

        # 2.1.1.1 should be somewhere in the subtree of 2.1
        node = section_21.find_by_section("2.1.1.1")
        assert node is not None, (
            "2.1.1.1 should be in the subtree of 2.1"
        )

    def test_electrode_content(self, parsed_doc: ParsedDocument):
        """The electrode specs should have the technical content."""
        node = parsed_doc.root.find_by_section("2.1.1.1")
        assert node is not None
        assert "Platinum" in node.content or "platinum" in node.content.lower(), (
            f"Expected electrode content, got: {node.content}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Duplicate section numbering (two sections labeled 4.2)
# ═══════════════════════════════════════════════════════════════════════

class TestDuplicateNumbering:
    """Two sections are numbered '4.2' in the PDF:
      - 4.2 'Error Code Reference' (with table)
      - 4.2 'Warning Indicators'
    The parser must:
      - Log the duplicate
      - Disambiguate (the second becomes '4.2_dup1')
      - Preserve both in the tree
    """

    def test_duplicate_detected(self, parsed_doc: ParsedDocument):
        """Parser should flag the duplicate numbering."""
        duplicates = [
            i for i in parsed_doc.irregularities if "DUPLICATE_NUMBER" in i
        ]
        assert len(duplicates) >= 1, (
            f"Expected DUPLICATE_NUMBER irregularity, got: {parsed_doc.irregularities}"
        )
        assert any("4.2" in i for i in duplicates), (
            f"DUPLICATE_NUMBER should reference 4.2, got: {duplicates}"
        )

    def test_both_sections_exist(self, parsed_doc: ParsedDocument):
        """Both 4.2 sections should be in the tree (second as 4.2_dup1)."""
        first = parsed_doc.root.find_by_section("4.2")
        second = parsed_doc.root.find_by_section("4.2_dup1")

        assert first is not None, "First 4.2 (Error Code Reference) not found"
        assert second is not None, (
            "Second 4.2 should be stored as '4.2_dup1'"
        )

    def test_first_42_is_error_codes(self, parsed_doc: ParsedDocument):
        """First 4.2 should be 'Error Code Reference'."""
        node = parsed_doc.root.find_by_section("4.2")
        assert node is not None
        assert "Error Code" in node.title, f"Wrong title: {node.title}"

    def test_second_42_is_warnings(self, parsed_doc: ParsedDocument):
        """Second 4.2 (renamed 4.2_dup1) should be 'Warning Indicators'."""
        node = parsed_doc.root.find_by_section("4.2_dup1")
        assert node is not None
        assert "Warning" in node.title, f"Wrong title: {node.title}"

    def test_different_hashes(self, parsed_doc: ParsedDocument):
        """Duplicate sections must have different content hashes."""
        first = parsed_doc.root.find_by_section("4.2")
        second = parsed_doc.root.find_by_section("4.2_dup1")
        assert first is not None and second is not None
        assert first.content_hash != second.content_hash, (
            "Duplicate sections should have different hashes"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Table extraction
# ═══════════════════════════════════════════════════════════════════════

class TestTableExtraction:
    """The PDF contains two tables:
      - Error code table under 4.2 (5 error codes)
      - Maintenance schedule under 5.1 (4 tasks)
    """

    def test_error_code_table_content(self, parsed_doc: ParsedDocument):
        """Section 4.2 should contain the error code table data."""
        node = parsed_doc.root.find_by_section("4.2")
        assert node is not None, "Section 4.2 not found"
        content = node.content

        # Check for error codes from the table
        assert "E001" in content, f"E001 not in table content: {content[:200]}"
        assert "E005" in content, f"E005 not in table content: {content[:200]}"
        assert "Strip not detected" in content, (
            f"Expected 'Strip not detected' in table: {content[:200]}"
        )

    def test_maintenance_table_content(self, parsed_doc: ParsedDocument):
        """Section 5.1 should contain the maintenance schedule table."""
        node = parsed_doc.root.find_by_section("5.1")
        assert node is not None, "Section 5.1 not found"
        content = node.content

        # Check for maintenance tasks
        assert "Weekly" in content, f"'Weekly' not in table content: {content[:200]}"
        assert "Quarterly" in content, (
            f"'Quarterly' not in table content: {content[:200]}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Overall tree structure
# ═══════════════════════════════════════════════════════════════════════

class TestTreeStructure:
    """Verify the overall document tree is well-formed."""

    def test_root_has_five_top_level_sections(self, parsed_doc: ParsedDocument):
        """Root should have sections 1-5 as direct children."""
        top_level = [c.section_number for c in parsed_doc.root.children]
        for expected in ["1", "2", "3", "4", "5"]:
            assert expected in top_level, (
                f"Section {expected} missing from top level: {top_level}"
            )

    def test_total_pages(self, parsed_doc: ParsedDocument):
        """Document should be 4 pages."""
        assert parsed_doc.total_pages == 4

    def test_all_nodes_have_hashes(self, parsed_doc: ParsedDocument):
        """Every node should have a non-empty content hash."""
        for node in parsed_doc.all_nodes:
            assert node.content_hash, (
                f"Node '{node.section_number} {node.title}' has no content hash"
            )

    def test_reading_order_monotonic(self, parsed_doc: ParsedDocument):
        """Reading order should be monotonically increasing in pre-order."""
        nodes = parsed_doc.all_nodes
        for i in range(1, len(nodes)):
            assert nodes[i].reading_order > nodes[i - 1].reading_order, (
                f"Reading order not monotonic: "
                f"node[{i - 1}]={nodes[i - 1].reading_order} "
                f"node[{i}]={nodes[i].reading_order}"
            )

    def test_flatten_includes_all_nodes(self, parsed_doc: ParsedDocument):
        """Flatten should return all nodes including root."""
        flat = parsed_doc.root.flatten()
        assert len(flat) == parsed_doc.node_count

    def test_three_irregularities_detected(self, parsed_doc: ParsedDocument):
        """Parser should detect exactly 3 irregularities in our test PDF."""
        assert len(parsed_doc.irregularities) == 3, (
            f"Expected 3 irregularities, got {len(parsed_doc.irregularities)}: "
            f"{parsed_doc.irregularities}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Content hashing
# ═══════════════════════════════════════════════════════════════════════

class TestContentHashing:
    """Verify content hash behavior for version comparison."""

    def test_hash_deterministic(self, parsed_doc: ParsedDocument):
        """Same content should produce the same hash."""
        node = DocumentNode(
            section_number="1.1",
            title="Test",
            content="Hello world",
        )
        hash1 = node.content_hash
        node2 = DocumentNode(
            section_number="1.1",
            title="Test",
            content="Hello world",
        )
        assert hash1 == node2.content_hash

    def test_hash_changes_with_content(self):
        """Different content should produce different hashes."""
        node1 = DocumentNode(section_number="1", title="A", content="x")
        node2 = DocumentNode(section_number="1", title="A", content="y")
        assert node1.content_hash != node2.content_hash

    def test_hash_changes_with_section_number(self):
        """Renumbering should change the hash (it's a structural change)."""
        node1 = DocumentNode(section_number="1.1", title="X", content="same")
        node2 = DocumentNode(section_number="1.2", title="X", content="same")
        assert node1.content_hash != node2.content_hash

    def test_recompute_hashes_recursive(self, parsed_doc: ParsedDocument):
        """recompute_hashes should update all nodes in the tree."""
        # Mutate a deep node
        node = parsed_doc.root.find_by_section("1.1")
        assert node is not None
        original_hash = node.content_hash
        node.content = "Modified content for test"

        # Hash should still be stale
        assert node.content_hash == original_hash

        # Recompute from root
        parsed_doc.root.recompute_hashes()

        # Now it should be updated
        assert node.content_hash != original_hash
        assert node.content_hash == node.compute_hash()

        # Restore original
        node.content = (
            "This device is intended for in-vitro diagnostic use by "
            "healthcare professionals in clinical laboratory and "
            "point-of-care settings."
        )
        parsed_doc.root.recompute_hashes()


# ═══════════════════════════════════════════════════════════════════════
# Test 7: Edge cases and model utilities
# ═══════════════════════════════════════════════════════════════════════

class TestModelUtilities:
    """Test DocumentNode utility methods."""

    def test_parse_level_from_number(self):
        """Section number depth should map to levels correctly."""
        assert DocumentNode.parse_level_from_number("1") == 1
        assert DocumentNode.parse_level_from_number("2.1") == 2
        assert DocumentNode.parse_level_from_number("2.1.1") == 3
        assert DocumentNode.parse_level_from_number("2.1.1.1") == 4
        assert DocumentNode.parse_level_from_number("") == 0
        assert DocumentNode.parse_level_from_number("  ") == 0

    def test_find_by_section_returns_none_for_missing(self, parsed_doc: ParsedDocument):
        """Searching for non-existent section should return None."""
        assert parsed_doc.root.find_by_section("99.99") is None

    def test_to_dict_serialization(self, parsed_doc: ParsedDocument):
        """to_dict should produce a valid dictionary with expected keys."""
        d = parsed_doc.root.to_dict()
        assert "section_number" in d
        assert "children" in d
        assert isinstance(d["children"], list)
        assert len(d["children"]) > 0
