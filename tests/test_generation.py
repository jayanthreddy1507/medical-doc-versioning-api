"""Tests for the LLM-powered QA test-case generation endpoint, caching, and retries."""

import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def ct200_v1_bytes() -> bytes:
    with open("data/ct200_manual_v1.pdf", "rb") as f:
        return f.read()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_llm_generation_and_cache_policy(client, ct200_v1_bytes):
    """Test generating test cases, verify caching by default, and forced regeneration."""
    # 1. Ingest document
    ing_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_gen_test.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    doc_id = ing_resp.json()["document_id"]

    # 2. Get tree detail to locate a node
    ver_detail_resp = await client.get(f"/api/v1/documents/{doc_id}/versions/1")
    v1_tree = ver_detail_resp.json()["tree"]

    # Find Section 4.1 Overpressure Protection node
    def find_node(node, section_num):
        if node["section_number"] == section_num:
            return node
        for child in node.get("children", []):
            res = find_node(child, section_num)
            if res:
                return res
        return None

    node_41 = find_node(v1_tree, "4.1")
    assert node_41 is not None
    node_41_id = node_41["id"]

    # 3. Create a named selection
    sel_payload = {
        "name": "Overpressure Safety Section",
        "node_ids": [node_41_id]
    }
    sel_resp = await client.post("/api/v1/selections", json=sel_payload)
    assert sel_resp.status_code == 201
    sel_id = sel_resp.json()["id"]

    # 4. First Generation Call (invokes LLM mock)
    gen1_resp = await client.post(f"/api/v1/selections/{sel_id}/generate")
    assert gen1_resp.status_code == 200
    gen1 = gen1_resp.json()
    
    assert gen1["selection_id"] == sel_id
    assert len(gen1["test_cases"]) == 2
    assert gen1["test_cases"][0]["id"] == "TC001"
    assert gen1["test_cases"][0]["traceability_node_id"] == node_41_id

    gen1_id = gen1["id"]
    gen1_time = gen1["created_at"]

    # 5. Duplicate Submission Check (cache hit)
    # Second call should return cached response instantly (same ID and timestamp)
    gen2_resp = await client.post(f"/api/v1/selections/{sel_id}/generate")
    assert gen2_resp.status_code == 200
    gen2 = gen2_resp.json()
    
    assert gen2["id"] == gen1_id
    assert gen2["created_at"] == gen1_time

    # 6. Forced Regeneration Check (cache bypass)
    # Third call with force_regenerate=true should trigger new call (new ID)
    gen3_resp = await client.post(
        f"/api/v1/selections/{sel_id}/generate?force_regenerate=true"
    )
    assert gen3_resp.status_code == 200
    gen3 = gen3_resp.json()
    
    assert gen3["id"] != gen1_id


@pytest.mark.asyncio
async def test_llm_self_repair_retry_loop(client, ct200_v1_bytes):
    """Test the self-repair loop by triggering a simulated malformed output on attempt 1."""
    # Ingest document
    ing_resp = await client.post(
        "/api/v1/ingest",
        files={"file": ("ct200_repair_test.pdf", io.BytesIO(ct200_v1_bytes), "application/pdf")},
    )
    doc_id = ing_resp.json()["document_id"]

    # Get a node ID
    ver_detail_resp = await client.get(f"/api/v1/documents/{doc_id}/versions/1")
    node_id = ver_detail_resp.json()["tree"]["id"]

    # Create a selection with TRIGGER_MALFORMED in its name
    sel_payload = {
        "name": "TRIGGER_MALFORMED Selection",
        "node_ids": [node_id]
    }
    sel_resp = await client.post("/api/v1/selections", json=sel_payload)
    sel_id = sel_resp.json()["id"]

    # Generate
    # The first model call will return 'This is not JSON text!'
    # The service catches the parse failure, prompts the LLM again with the validation error,
    # and the mock client returns valid JSON on the second call, saving successfully.
    gen_resp = await client.post(f"/api/v1/selections/{sel_id}/generate")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    
    assert len(gen_data["test_cases"]) == 2
    assert gen_data["test_cases"][0]["id"] == "TC001"
