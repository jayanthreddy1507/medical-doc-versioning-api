"""Tests for version matching and tree diffing between CardioTrack CT-200 V1 and V2."""

import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.versioning import DiffStatus


@pytest.fixture(scope="session")
def ct200_v1_bytes() -> bytes:
    """Read generated CardioTrack CT-200 V1 PDF bytes."""
    with open("data/ct200_manual_v1.pdf", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def ct200_v2_bytes() -> bytes:
    """Read generated CardioTrack CT-200 V2 PDF bytes."""
    with open("data/ct200_manual_v2.pdf", "rb") as f:
        return f.read()


@pytest.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_versioning_diff_flow(client, ct200_v1_bytes, ct200_v2_bytes):
    """Test the complete versioning and diff workflow with real CardioTrack PDFs."""
    # 1. Ingest V1
    v1_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_manual.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    assert v1_resp.status_code == 201
    v1_data = v1_resp.json()
    doc_id = v1_data["document_id"]
    assert v1_data["version_number"] == 1

    # 2. Ingest V2 (same filename)
    v2_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_manual.pdf", io.BytesIO(ct200_v2_bytes), "application/pdf")},
    )
    assert v2_resp.status_code == 201
    v2_data = v2_resp.json()
    assert v2_data["version_number"] == 2

    # 3. Call the Diff Endpoint
    diff_resp = await client.get(
        f"/api/v1/documents/{doc_id}/diff?v1=1&v2=2"
    )
    assert diff_resp.status_code == 200
    diff_summary = diff_resp.json()

    # Assert correct summary metadata
    assert diff_summary["document_id"] == doc_id
    assert diff_summary["v1_version_number"] == 1
    assert diff_summary["v2_version_number"] == 2

    # Assert we have counts for all diff states
    assert diff_summary["added_count"] >= 1
    assert diff_summary["modified_count"] >= 1
    assert diff_summary["unchanged_count"] >= 1

    # Get flat list of diff nodes to check specific updates
    flat_diff = []
    def flatten_diff(node):
        flat_diff.append(node)
        for child in node.get("children", []):
            flatten_diff(child)

    flatten_diff(diff_summary["diff_tree"])

    # ── Verify Specific Node Matches and Statuses ─────────────────────────────

    # 1. 2.1.1.1 Battery Life (should be modified)
    battery_node = next((n for n in flat_diff if n["section_number"] == "2.1.1.1"), None)
    assert battery_node is not None, "2.1.1.1 Battery Life node not found"
    assert battery_node["status"] == DiffStatus.MODIFIED
    # Content should show the diff from 300 to 250 cycles
    assert "250" in battery_node["content"]

    # 2. 3.2 Cuff Inflation Sequence (should be modified)
    inflation_node = next((n for n in flat_diff if n["section_number"] == "3.2"), None)
    assert inflation_node is not None, "3.2 Inflation Sequence node not found"
    assert inflation_node["status"] == DiffStatus.MODIFIED
    # Should contain 30 mmHg in V2
    assert "30 mmHg" in inflation_node["content"]

    # 3. 3.3 Result Display (should match and be UNCHANGED, despite reordering in V1)
    display_node = next((n for n in flat_diff if n["section_number"] == "3.3"), None)
    assert display_node is not None, "3.3 Result Display node not found"
    assert display_node["status"] == DiffStatus.UNCHANGED

    # 4. 5.3 Data Export (should be ADDED)
    data_export_node = next((n for n in flat_diff if n["section_number"] == "5.3"), None)
    assert data_export_node is not None, "5.3 Data Export node not found"
    assert data_export_node["status"] == DiffStatus.ADDED

    # 5. 4.2 Error Code Reference Table (should be modified)
    # Filter by section number '4.2' and title matching 'Error Code Reference'
    error_node = next((n for n in flat_diff if n["section_number"] == "4.2" and "Error" in n["title"]), None)
    assert error_node is not None, "4.2 Error Code Reference node not found"
    assert error_node["status"] == DiffStatus.MODIFIED
    # Should contain the new error code E6
    assert "E6" in error_node["content"]

    # 6. Unmodified node like 1.2 Indications and Contraindications
    indications_node = next((n for n in flat_diff if n["section_number"] == "1.2"), None)
    assert indications_node is not None
    assert indications_node["status"] == DiffStatus.UNCHANGED
