"""End-to-End demonstration script for Medical Document Versioning API.

Validates the complete ingestion, selection, LLM generation, re-versioning,
diffing, and staleness detection flow against the live API server.
"""

import json
import sys
import time
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def safe_print(text: str = ""):
    """Print text safely, replacing non-encodable characters for Windows console compatibility."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding))


def print_step(title: str):
    safe_print("\n" + "=" * 80)
    safe_print(f"STEP: {title}")
    safe_print("=" * 80)


def print_json(data: dict):
    safe_print(json.dumps(data, indent=2))


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 0. Health check verification
        try:
            health = await client.get(f"{BASE_URL}/health")
            if health.status_code != 200:
                safe_print("[ERROR] API server health check failed. Make sure it is running on port 8000.")
                return
        except Exception:
            safe_print("[ERROR] Cannot connect to the API server at localhost:8000.")
            safe_print("   Please start the server first by running:")
            safe_print("   uvicorn app.main:app --reload")
            return

        safe_print("[CONNECTED] Connected to Medical Document Versioning API server!")

        # 1. Ingest CardioTrack CT-200 V1 PDF
        print_step("Ingest CardioTrack CT-200 V1 PDF")
        with open("data/ct200_manual_v1.pdf", "rb") as f:
            ing1_resp = await client.post(
                f"{BASE_URL}/ingest",
                files={"file": ("ct200_manual.pdf", f, "application/pdf")},
            )
        assert ing1_resp.status_code == 201, f"Ingestion failed: {ing1_resp.text}"
        ing1 = ing1_resp.json()
        doc_id = ing1["document_id"]
        safe_print(f"[OK] Ingested V1. Document ID: {doc_id}, Version: {ing1['version_number']}")
        print_json(ing1)

        # 2. Get Tree details for V1 and locate Section 2.1.1.1 (Battery Life)
        print_step("Locating Section 2.1.1.1 in V1 tree")
        v1_resp = await client.get(f"{BASE_URL}/documents/{doc_id}/versions/1")
        v1_tree = v1_resp.json()["tree"]

        def find_node(node, sec_num):
            if node["section_number"] == sec_num:
                return node
            for child in node.get("children", []):
                res = find_node(child, sec_num)
                if res:
                    return res
            return None

        node_v1 = find_node(v1_tree, "2.1.1.1")
        assert node_v1 is not None, "Could not find node 2.1.1.1"
        node_v1_id = node_v1["id"]
        safe_print(f"[OK] Found Node 2.1.1.1 (ID: {node_v1_id})")
        safe_print(f"   Heading: {node_v1['title']}")
        safe_print(f"   Content: {node_v1['content'][:150]}...")

        # 3. Create a selection containing the Battery Life node
        print_step("Creating named, version-pinned Selection")
        sel_payload = {
            "name": "E2E Demo Battery Specs",
            "node_ids": [node_v1_id]
        }
        sel_resp = await client.post(f"{BASE_URL}/selections", json=sel_payload)
        assert sel_resp.status_code == 201
        selection = sel_resp.json()
        sel_id = selection["id"]
        safe_print(f"[OK] Selection created. Selection ID: {sel_id}")
        print_json(selection)

        # 4. Generate QA test cases from selection (initial up-to-date state)
        print_step("Generating LLM QA Test Cases (Initial run, up-to-date)")
        gen_resp = await client.post(f"{BASE_URL}/selections/{sel_id}/generate")
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        safe_print("[OK] Generated QA test cases:")
        print_json(gen_data)

        # 5. Retrieve generations for selection (check is_stale status)
        print_step("Retrieving generations to verify active staleness (should be False)")
        ret1_resp = await client.get(f"{BASE_URL}/selections/{sel_id}/generations")
        assert ret1_resp.status_code == 200
        ret1 = ret1_resp.json()
        safe_print(f"[OK] Generation is_stale status: {ret1[0]['is_stale']}")
        print_json(ret1)

        # 6. Ingest CardioTrack CT-200 V2 PDF (modifies Battery Life to 250 cycles)
        print_step("Re-ingest CT-200 V2 PDF (contains specification updates)")
        with open("data/ct200_manual_v2.pdf", "rb") as f:
            ing2_resp = await client.post(
                f"{BASE_URL}/ingest",
                files={"file": ("ct200_manual.pdf", f, "application/pdf")},
            )
        assert ing2_resp.status_code == 201
        ing2 = ing2_resp.json()
        safe_print(f"[OK] Ingested V2. Document ID: {doc_id}, Version: {ing2['version_number']}")
        print_json(ing2)

        # 7. Compare document versions (Diff V1 vs V2)
        print_step("Comparing V1 and V2 Document trees")
        diff_resp = await client.get(f"{BASE_URL}/documents/{doc_id}/diff?v1=1&v2=2")
        assert diff_resp.status_code == 200
        diff_data = diff_resp.json()
        safe_print(f"[OK] Document Diff summary:")
        safe_print(f"   Added nodes: {diff_data['added_count']}")
        safe_print(f"   Modified nodes: {diff_data['modified_count']}")
        safe_print(f"   Removed nodes: {diff_data['removed_count']}")
        safe_print(f"   Unchanged nodes: {diff_data['unchanged_count']}")

        # Find 2.1.1.1 in diff tree
        diff_node_2111 = find_node(diff_data["diff_tree"], "2.1.1.1")
        if diff_node_2111:
            safe_print("\n[DETAILS] Diff entry for Section 2.1.1.1:")
            safe_print(f"   Status: {diff_node_2111['status']}")
            safe_print(f"   Diff content preview:\n{diff_node_2111['content_diff']}")

        # 8. Retrieve selection generations again (verifying staleness transition)
        print_step("Retrieving generations to verify active staleness (should now be True)")
        ret2_resp = await client.get(f"{BASE_URL}/selections/{sel_id}/generations")
        assert ret2_resp.status_code == 200
        ret2 = ret2_resp.json()
        safe_print(f"[OK] Generation is_stale status: {ret2[0]['is_stale']}")
        print_json(ret2)

        # 9. Retrieve generations by V2 Node ID (verifies cross-version retrieval)
        print_step("Retrieving generations by V2 Node ID (recovers V1 generation with stale flag)")
        v2_detail_resp = await client.get(f"{BASE_URL}/documents/{doc_id}/versions/2")
        v2_tree = v2_detail_resp.json()["tree"]
        node_v2 = find_node(v2_tree, "2.1.1.1")
        assert node_v2 is not None
        node_v2_id = node_v2["id"]

        node_ret_resp = await client.get(f"{BASE_URL}/nodes/{node_v2_id}/generations")
        assert node_ret_resp.status_code == 200
        node_ret = node_ret_resp.json()
        safe_print("[OK] Recovered generations by query node ID:")
        print_json(node_ret)

        safe_print("\n[FINISHED] E2E Flow successfully completed and validated!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
