"""Tests for the Browse API endpoints."""

import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def ct200_v1_bytes() -> bytes:
    with open("data/ct200_manual_v1.pdf", "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def ct200_v2_bytes() -> bytes:
    with open("data/ct200_manual_v2.pdf", "rb") as f:
        return f.read()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_browse_api_endpoints(client, ct200_v1_bytes, ct200_v2_bytes):
    """E2E test validating listing, search, details, and change history diff."""
    # 1. Ingest V1 & V2 to set up version history
    v1_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_browse_test.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    doc_id = v1_resp.json()["document_id"]

    await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_browse_test.pdf", io.BytesIO(ct200_v2_bytes), "application/pdf")},
    )

    # ── Test 1: List Top-Level Sections ────────────────────────────────────
    sections_resp = await client.get(f"/api/v1/documents/{doc_id}/sections?version=1")
    assert sections_resp.status_code == 200
    sections = sections_resp.json()
    assert len(sections) == 8  # Sections 1 to 8 of CT-200
    section_numbers = [s["section_number"] for s in sections]
    assert "1" in section_numbers
    assert "8" in section_numbers

    # Default to latest version if parameter omitted
    sections_latest_resp = await client.get(f"/api/v1/documents/{doc_id}/sections")
    assert sections_latest_resp.status_code == 200
    assert len(sections_latest_resp.json()) == 8

    # ── Test 2: Search Nodes ────────────────────────────────────────────────
    # Search for 'cuff' in v1
    search_resp = await client.get(f"/api/v1/documents/{doc_id}/search?q=cuff&version=1")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    # Check that search matches content/headings with 'cuff'
    assert any("cuff" in r["title"].lower() or "cuff" in r["content"].lower() for r in results)

    # Search defaults to latest version
    search_latest_resp = await client.get(f"/api/v1/documents/{doc_id}/search?q=CSV")
    assert search_latest_resp.status_code == 200
    # V2 has CSV data export, so it should match
    assert len(search_latest_resp.json()) >= 1

    # ── Test 3: Get Node Details by ID ──────────────────────────────────────
    # Get details of section '2.1' in v2
    ver_detail_resp = await client.get(f"/api/v1/documents/{doc_id}/versions/2")
    v2_tree = ver_detail_resp.json()["tree"]
    
    # Traverse to find Section 2.1 General Specifications node id
    def find_node(node, section_num):
        if node["section_number"] == section_num:
            return node
        for child in node.get("children", []):
            res = find_node(child, section_num)
            if res:
                return res
        return None

    node_21 = find_node(v2_tree, "2.1")
    assert node_21 is not None
    node_21_id = node_21["id"]

    node_detail_resp = await client.get(f"/api/v1/nodes/{node_21_id}")
    assert node_detail_resp.status_code == 200
    node_detail = node_detail_resp.json()
    assert node_detail["title"] == "General Specifications"
    # Should include immediate children (like 2.1.1.1 Battery Life)
    assert len(node_detail["children"]) == 1
    assert node_detail["children"][0]["section_number"] == "2.1.1.1"

    # ── Test 4: Node History Diff ───────────────────────────────────────────
    # Trace 2.1.1.1 (Battery Life)
    node_2111 = find_node(v2_tree, "2.1.1.1")
    node_2111_id = node_2111["id"]

    history_resp = await client.get(f"/api/v1/nodes/{node_2111_id}/diff")
    assert history_resp.status_code == 200
    history = history_resp.json()

    assert history["node_id"] == node_2111_id
    assert history["path"] == "/Document Root/Physical and Electrical Specifications/General Specifications/Battery Life Under Typical Use"
    assert history["has_changed"] is True
    assert len(history["history"]) == 2  # v1 and v2

    v1_entry = history["history"][0]
    assert v1_entry["version_number"] == 1
    assert v1_entry["status"] == "added"

    v2_entry = history["history"][1]
    assert v2_entry["version_number"] == 2
    assert v2_entry["status"] == "modified"
    assert v2_entry["content_diff"] is not None
    assert "300" in v2_entry["content_diff"]
    assert "250" in v2_entry["content_diff"]
