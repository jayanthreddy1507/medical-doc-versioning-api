"""Tests for staleness detection and test-case generation retrieval APIs."""

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
async def test_staleness_detection_lifecycle(client, ct200_v1_bytes, ct200_v2_bytes):
    """E2E test validating staleness flags and cross-version node ID retrieval."""
    # 1. Ingest V1
    v1_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_staleness_test.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    assert v1_resp.status_code == 201
    doc_id = v1_resp.json()["document_id"]

    # Locate V1 node 2.1.1.1 (Battery Life)
    v1_detail = await client.get(f"/api/v1/documents/{doc_id}/versions/1")
    v1_tree = v1_detail.json()["tree"]

    def find_node(node, section_num):
        if node["section_number"] == section_num:
            return node
        for child in node.get("children", []):
            res = find_node(child, section_num)
            if res:
                return res
        return None

    node_2111_v1 = find_node(v1_tree, "2.1.1.1")
    assert node_2111_v1 is not None
    node_v1_id = node_2111_v1["id"]

    # 2. Create selection containing this node
    sel_payload = {
        "name": "Staleness Test Selection",
        "node_ids": [node_v1_id]
    }
    sel_resp = await client.post("/api/v1/selections", json=sel_payload)
    assert sel_resp.status_code == 201
    sel_id = sel_resp.json()["id"]

    # 3. Generate test cases (V1 is currently the latest version)
    gen_resp = await client.post(f"/api/v1/selections/{sel_id}/generate")
    assert gen_resp.status_code == 200

    # 4. Retrieve and verify NOT stale
    ret1_resp = await client.get(f"/api/v1/selections/{sel_id}/generations")
    assert ret1_resp.status_code == 200
    ret1 = ret1_resp.json()
    
    assert len(ret1) == 1
    assert ret1[0]["is_stale"] is False
    assert ret1[0]["latest_version_number"] == 1
    assert len(ret1[0]["staleness_details"]) == 1
    assert ret1[0]["staleness_details"][0]["node_id"] == node_v1_id
    assert ret1[0]["staleness_details"][0]["status"] == "up_to_date"

    # 5. Ingest V2 (which modifies node 2.1.1.1 content)
    v2_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_staleness_test.pdf", io.BytesIO(ct200_v2_bytes), "application/pdf")},
    )
    assert v2_resp.status_code == 201
    assert v2_resp.json()["version_number"] == 2

    # Locate V2 node 2.1.1.1 ID
    v2_detail = await client.get(f"/api/v1/documents/{doc_id}/versions/2")
    v2_tree = v2_detail.json()["tree"]
    node_2111_v2 = find_node(v2_tree, "2.1.1.1")
    assert node_2111_v2 is not None
    node_v2_id = node_2111_v2["id"]

    # 6. Retrieve selection generations and verify it is now flagged as STALE
    ret2_resp = await client.get(f"/api/v1/selections/{sel_id}/generations")
    assert ret2_resp.status_code == 200
    ret2 = ret2_resp.json()
    
    assert len(ret2) == 1
    assert ret2[0]["is_stale"] is True
    assert ret2[0]["latest_version_number"] == 2
    assert len(ret2[0]["staleness_details"]) == 1
    assert ret2[0]["staleness_details"][0]["node_id"] == node_v1_id
    assert ret2[0]["staleness_details"][0]["status"] == "stale"

    # 7. Retrieve generations by V1 Node ID
    node_v1_gen_resp = await client.get(f"/api/v1/nodes/{node_v1_id}/generations")
    assert node_v1_gen_resp.status_code == 200
    node_v1_gens = node_v1_gen_resp.json()
    
    assert len(node_v1_gens) == 1
    assert node_v1_gens[0]["is_stale"] is True
    assert node_v1_gens[0]["staleness_details"][0]["status"] == "stale"

    # 8. Retrieve generations by V2 Node ID (recovers the V1 generation via path matching!)
    node_v2_gen_resp = await client.get(f"/api/v1/nodes/{node_v2_id}/generations")
    assert node_v2_gen_resp.status_code == 200
    node_v2_gens = node_v2_gen_resp.json()
    
    assert len(node_v2_gens) == 1
    assert node_v2_gens[0]["is_stale"] is True
    assert node_v2_gens[0]["staleness_details"][0]["status"] == "stale"
