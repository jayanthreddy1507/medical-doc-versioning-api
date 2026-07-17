"""Tests for the named, version-pinned Selection API."""

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
async def test_selection_version_pinning(client, ct200_v1_bytes, ct200_v2_bytes):
    """E2E test verifying selections are version-pinned and immune to updates."""
    # 1. Ingest V1
    v1_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_selection_test.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    assert v1_resp.status_code == 201
    doc_id = v1_resp.json()["document_id"]

    # 2. Get tree detail for V1 to locate 2.1.1.1 (Battery Life)
    ver_detail_resp = await client.get(f"/api/v1/documents/{doc_id}/versions/1")
    v1_tree = ver_detail_resp.json()["tree"]

    def find_node(node, section_num):
        if node["section_number"] == section_num:
            return node
        for child in node.get("children", []):
            res = find_node(child, section_num)
            if res:
                return res
        return None

    node_2111 = find_node(v1_tree, "2.1.1.1")
    assert node_2111 is not None
    node_2111_id = node_2111["id"]

    # Verify V1 text contains 300 cycles
    assert "300" in node_2111["content"]

    # 3. Create a selection containing this node
    sel_payload = {
        "name": "Battery Specs v1",
        "node_ids": [node_2111_id]
    }
    create_resp = await client.post("/api/v1/selections", json=sel_payload)
    assert create_resp.status_code == 201
    sel_data = create_resp.json()
    sel_id = sel_data["id"]
    assert sel_data["name"] == "Battery Specs v1"
    assert len(sel_data["nodes"]) == 1
    assert sel_data["nodes"][0]["id"] == node_2111_id
    assert "300" in sel_data["nodes"][0]["content"]

    # 4. Ingest V2 (which updates 2.1.1.1 content to 250 cycles)
    v2_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_selection_test.pdf", io.BytesIO(ct200_v2_bytes), "application/pdf")},
    )
    assert v2_resp.status_code == 201
    assert v2_resp.json()["version_number"] == 2

    # 5. Retrieve the selection and verify it still returns the original V1 text
    get_resp = await client.get(f"/api/v1/selections/{sel_id}")
    assert get_resp.status_code == 200
    sel_retrieved = get_resp.json()
    
    assert sel_retrieved["id"] == sel_id
    assert sel_retrieved["name"] == "Battery Specs v1"
    assert len(sel_retrieved["nodes"]) == 1
    # Pinned to the old node ID and original V1 text (300 cycles), not V2 text (250 cycles)
    assert sel_retrieved["nodes"][0]["id"] == node_2111_id
    assert "300" in sel_retrieved["nodes"][0]["content"]
    assert "250" not in sel_retrieved["nodes"][0]["content"]


@pytest.mark.asyncio
async def test_create_selection_invalid_nodes(client):
    """Creating a selection with non-existent node IDs should fail with 400."""
    sel_payload = {
        "name": "Invalid Selection",
        "node_ids": [99999, 88888]
    }
    create_resp = await client.post("/api/v1/selections", json=sel_payload)
    assert create_resp.status_code == 400
    assert "does not exist" in create_resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_selection_not_found(client):
    """Retrieving a non-existent selection should fail with 404."""
    get_resp = await client.get("/api/v1/selections/99999")
    assert get_resp.status_code == 404
    assert "not found" in get_resp.json()["detail"].lower()
