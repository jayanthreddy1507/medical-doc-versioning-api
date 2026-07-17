"""LLM Generation service for generating QA test cases from document selections."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import GenerationORM, SelectionORM
from app.schemas.document import TestCaseIdea, QAGenerationResponse

logger = logging.getLogger(__name__)


class GenerationService:
    """Orchestrates structured QA test case generation via Gemini API with self-repair retries."""

    def __init__(self):
        # Allow overriding API key or base URL
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model = "gemini-1.5-flash"
        # Used for testing self-repair loop
        self._test_malformed_attempts = 0

    async def generate_test_cases(
        self,
        db: AsyncSession,
        selection: SelectionORM,
        force_regenerate: bool = False,
    ) -> GenerationORM:
        """Generate test cases for a selection, checking cache first unless force_regenerate is True."""
        # 1. Check duplicate policy: return cached generation if it exists and force_regenerate is False
        if not force_regenerate:
            result = await db.execute(
                select(GenerationORM)
                .where(GenerationORM.selection_id == selection.id)
                .order_by(GenerationORM.created_at.desc())
            )
            cached_gen = result.scalar_one_or_none()
            if cached_gen:
                logger.info(f"Returning cached generation for selection {selection.id}")
                return cached_gen

        # 2. Reconstruct context text from selection nodes
        context_text = self._reconstruct_context(selection)

        # 3. Construct prompt
        prompt = self._build_prompt(context_text, selection)

        # 4. Generate structured output with retries
        test_cases_json = await self._call_llm_with_retry(prompt)

        # 5. Extract current node hashes for staleness detection
        node_hashes = {node.id: node.content_hash for node in selection.nodes}

        # 6. Persist to JSON database store
        generation = GenerationORM(
            selection_id=selection.id,
            prompt=prompt,
            test_cases=test_cases_json,
            node_hashes=json.dumps(node_hashes),
        )
        db.add(generation)
        await db.flush()

        return generation

    def _reconstruct_context(self, selection: SelectionORM) -> str:
        """Combine selection nodes into a single text block representing the selected scope."""
        sorted_nodes = sorted(selection.nodes, key=lambda n: n.reading_order)
        blocks = []
        for node in sorted_nodes:
            header = f"Node ID: {node.id} | Section: {node.section_number} | Title: {node.title}"
            content = node.content if node.content else "[No content text]"
            blocks.append(f"{header}\n{content}\n")
        return "\n---\n".join(blocks)

    def _build_prompt(self, context_text: str, selection: SelectionORM) -> str:
        """Construct the prompt instructs the LLM to output valid JSON matching our schema."""
        sorted_nodes = sorted(selection.nodes, key=lambda n: n.reading_order)
        node_ids_str = ", ".join(str(n.id) for n in sorted_nodes)

        return (
            "You are a QA Engineer for high-integrity medical device software. "
            "Your task is to generate 3 to 5 clear, concrete QA test case ideas based strictly "
            "on the following device manual content.\n\n"
            "--- DEVICE MANUAL CONTENT ---\n"
            f"{context_text}\n"
            "-----------------------------\n\n"
            "Instructions:\n"
            "1. Focus only on testing the requirements/specifications mentioned in the provided text.\n"
            "2. Each test case idea must contain:\n"
            "   - A unique ID (e.g. 'TC001', 'TC002')\n"
            "   - A short name summarizing the test case\n"
            "   - A detailed description/steps of how to run the test case\n"
            "   - An expected result detailing correct device behavior\n"
            "   - A traceability_node_id indicating the exact Node ID this test case targets. "
            f"You MUST only select from the following valid Node IDs: [{node_ids_str}].\n"
            "3. You must output a JSON object strictly matching this schema:\n"
            "{\n"
            '  "test_cases": [\n'
            "    {\n"
            '      "id": "string",\n'
            '      "name": "string",\n'
            '      "description": "string",\n'
            '      "expected_result": "string",\n'
            '      "traceability_node_id": integer\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Do not include any Markdown wrapper, explanation, or notes. Output valid raw JSON only."
        )

    async def _call_llm_with_retry(self, base_prompt: str, retries: int = 3) -> str:
        """Call the LLM, implementing a self-correcting retry loop if the output is malformed."""
        prompt = base_prompt
        last_error = None

        for attempt in range(retries):
            try:
                raw_response = await self._call_raw_api(prompt)
                # Parse to validate JSON and schema structure
                parsed_json = json.loads(raw_response)
                
                # Validation check: must have test_cases list
                if "test_cases" not in parsed_json or not isinstance(parsed_json["test_cases"], list):
                    raise ValueError("JSON response must contain a top-level 'test_cases' list.")

                # Validate each test case contains the required fields
                for idx, tc in enumerate(parsed_json["test_cases"]):
                    required = {"id", "name", "description", "expected_result", "traceability_node_id"}
                    missing = required - set(tc.keys())
                    if missing:
                        raise ValueError(
                            f"Test case at index {idx} is missing required fields: {missing}"
                        )

                # Return valid JSON string
                return json.dumps(parsed_json)

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"LLM generation validation failed on attempt {attempt + 1}: {last_error}. "
                    "Prompting LLM with validation error for self-repair..."
                )
                # Build correction prompt
                prompt = (
                    f"{base_prompt}\n\n"
                    f"WARNING: Your previous response was malformed/invalid and failed with error: {last_error}\n"
                    f"Your previous output was:\n{raw_response if 'raw_response' in locals() else '[Empty response]'}\n\n"
                    "Please correct your response, ensuring it is 100% valid JSON matching the exact schema requested."
                )

        raise ValueError(
            f"Failed to generate valid QA test cases after {retries} attempts. Last error: {last_error}"
        )

    async def _call_raw_api(self, prompt: str) -> str:
        """Interact with the real Gemini API or fall back to a local mock if no API key is set."""
        if not self.api_key:
            return self._generate_mock_response(prompt)

        # Real Gemini API POST call (beta version supports responseMimeType: application/json)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    f"Gemini API returned status code {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )
            
            data = response.json()
            try:
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                return text_content.strip()
            except (KeyError, IndexError):
                raise ValueError(f"Malformed API response structure: {data}")

    def _generate_mock_response(self, prompt: str) -> str:
        """Local mock response generator for testing self-repair loop and offline operations."""
        # Check if we should trigger a validation failure for self-repair loop testing
        # If the prompt contains 'TRIGGER_MALFORMED' and it's our first attempt
        if "TRIGGER_MALFORMED" in prompt and self._test_malformed_attempts == 0:
            self._test_malformed_attempts += 1
            # Return invalid JSON text to trigger validation exception
            return "This is not JSON text! Malformed LLM response."

        # Extract target node ID from prompt for traceability mock matching
        traceability_id = 1
        # Try to locate node ID in the prompt
        import re
        m = re.search(r"traceability_node_id.*?\[(.*?)]", prompt)
        if m:
            ids = [int(i.strip()) for i in m.group(1).split(",") if i.strip()]
            if ids:
                traceability_id = ids[0]

        return json.dumps({
            "test_cases": [
                {
                    "id": "TC001",
                    "name": "Basic Operation Verification",
                    "description": "Simulate standard operational workflow under standard pressure guidelines.",
                    "expected_result": "Device starts up and performs normal self-test without triggering error screens.",
                    "traceability_node_id": traceability_id
                },
                {
                    "id": "TC002",
                    "name": "Parameter Safety Threshold Limit",
                    "description": "Exceed default parameter thresholds and verify emergency relief valve trigger.",
                    "expected_result": "Vent valve activates automatically within standard specifications.",
                    "traceability_node_id": traceability_id
                }
            ]
        })

    async def check_staleness(
        self, db: AsyncSession, generation: GenerationORM
    ) -> dict[str, Any]:
        """Compute the staleness status for a generation relative to the latest document version."""
        # 1. Fetch selection and its nodes
        from sqlalchemy.orm import selectinload
        sel_res = await db.execute(
            select(SelectionORM)
            .where(SelectionORM.id == generation.selection_id)
            .options(selectinload(SelectionORM.nodes))
        )
        selection = sel_res.scalar_one()

        # 2. Get the selection's document and latest version ID
        # Since selection nodes must belong to a version, check the first node's version
        if not selection.nodes:
            return {
                "id": generation.id,
                "selection_id": generation.selection_id,
                "prompt": generation.prompt,
                "test_cases": json.loads(generation.test_cases)["test_cases"],
                "created_at": generation.created_at,
                "is_stale": False,
                "latest_version_number": 1,
                "staleness_details": [],
            }

        first_node = selection.nodes[0]
        from app.models.db_models import VersionORM, NodeORM
        v_res = await db.execute(select(VersionORM).where(VersionORM.id == first_node.version_id))
        gen_version = v_res.scalar_one()
        doc_id = gen_version.document_id

        # Resolve latest version
        from sqlalchemy import func
        latest_v_num_res = await db.execute(
            select(func.max(VersionORM.version_number)).where(VersionORM.document_id == doc_id)
        )
        latest_v_num = latest_v_num_res.scalar() or gen_version.version_number

        # Fetch latest version details
        latest_v_res = await db.execute(
            select(VersionORM).where(
                VersionORM.document_id == doc_id,
                VersionORM.version_number == latest_v_num,
            )
        )
        latest_version = latest_v_res.scalar_one()

        # 3. Load latest version nodes to map paths in memory
        latest_nodes_res = await db.execute(
            select(NodeORM).where(NodeORM.version_id == latest_version.id)
        )
        latest_nodes = latest_nodes_res.scalars().all()
        latest_node_map = {n.id: n for n in latest_nodes}

        # 4. Load selection version nodes to map paths in memory
        sel_version_nodes_res = await db.execute(
            select(NodeORM).where(NodeORM.version_id == gen_version.id)
        )
        sel_version_nodes = sel_version_nodes_res.scalars().all()
        sel_node_map = {n.id: n for n in sel_version_nodes}

        def compute_path(n_obj, nodes_map):
            parts = []
            curr = n_obj
            while curr is not None:
                parts.insert(0, curr.title)
                curr = nodes_map.get(curr.parent_id) if curr.parent_id else None
            return "/" + "/".join(parts)

        # Build path map for latest version nodes
        latest_path_map = {compute_path(vn, latest_node_map): vn for vn in latest_nodes}

        # 5. Parse node hashes stored at generation time
        saved_hashes = json.loads(generation.node_hashes)  # maps node_id (str) -> content_hash

        is_stale = False
        staleness_details = []

        # For each node in the selection
        for node in selection.nodes:
            node_id_str = str(node.id)
            gen_time_hash = saved_hashes.get(node_id_str, "")

            # Compute path in original selection version
            node_path = compute_path(node, sel_node_map)

            # Match in latest version
            match_node = latest_path_map.get(node_path)
            
            # Fallback signature match if path match fails
            if not match_node:
                for vn in latest_nodes:
                    if (
                        vn.section_number == node.section_number
                        and vn.title.strip().lower() == node.title.strip().lower()
                    ):
                        match_node = vn
                        break

            if not match_node:
                # Node has been removed in latest version
                status = "removed"
                is_stale = True
            else:
                # Compare content hash
                if match_node.content_hash == gen_time_hash:
                    status = "up_to_date"
                else:
                    status = "stale"
                    is_stale = True

            staleness_details.append({
                "node_id": node.id,
                "section_number": node.section_number,
                "title": node.title,
                "status": status,
            })

        return {
            "id": generation.id,
            "selection_id": generation.selection_id,
            "prompt": generation.prompt,
            "test_cases": json.loads(generation.test_cases)["test_cases"],
            "created_at": generation.created_at,
            "is_stale": is_stale,
            "latest_version_number": latest_v_num,
            "staleness_details": staleness_details,
        }

    async def get_generations_by_node_id(
        self, db: AsyncSession, node_id: int
    ) -> list[dict[str, Any]]:
        """Retrieve all test case generations that trace back to this node across versions."""
        # 1. Fetch query node
        from app.models.db_models import NodeORM, VersionORM, selection_nodes
        result = await db.execute(select(NodeORM).where(NodeORM.id == node_id))
        q_node = result.scalar_one_or_none()
        if not q_node:
            return []

        # 2. Get document and all its versions
        v_res = await db.execute(select(VersionORM).where(VersionORM.id == q_node.version_id))
        q_version = v_res.scalar_one()
        doc_id = q_version.document_id

        # 3. Reconstruct path of query node in its version
        q_version_nodes_res = await db.execute(
            select(NodeORM).where(NodeORM.version_id == q_version.id)
        )
        q_nodes = q_version_nodes_res.scalars().all()
        q_node_map = {n.id: n for n in q_nodes}

        def compute_path(n_obj, nodes_map):
            parts = []
            curr = n_obj
            while curr is not None:
                parts.insert(0, curr.title)
                curr = nodes_map.get(curr.parent_id) if curr.parent_id else None
            return "/" + "/".join(parts)

        target_path = compute_path(q_node, q_node_map)

        # 4. For each version of this document, find the matching node ID
        ver_res = await db.execute(
            select(VersionORM).where(VersionORM.document_id == doc_id)
        )
        all_versions = ver_res.scalars().all()

        matched_node_ids = set()

        for ver in all_versions:
            ver_nodes_res = await db.execute(select(NodeORM).where(NodeORM.version_id == ver.id))
            ver_nodes = ver_nodes_res.scalars().all()
            ver_node_map = {n.id: n for n in ver_nodes}

            # Find matching node in this version
            for vn in ver_nodes:
                vn_path = compute_path(vn, ver_node_map)
                if vn_path == target_path:
                    matched_node_ids.add(vn.id)
                    break
            # Fallback matching
            for vn in ver_nodes:
                if (
                    vn.id not in matched_node_ids
                    and vn.section_number == q_node.section_number
                    and vn.title.strip().lower() == q_node.title.strip().lower()
                ):
                    matched_node_ids.add(vn.id)
                    break

        if not matched_node_ids:
            return []

        # 5. Fetch selections containing any of these node IDs
        sel_ids_res = await db.execute(
            select(selection_nodes.c.selection_id)
            .where(selection_nodes.c.node_id.in_(matched_node_ids))
        )
        selection_ids = [r[0] for r in sel_ids_res.all()]

        if not selection_ids:
            return []

        # 6. Fetch generations for these selections
        gen_res = await db.execute(
            select(GenerationORM)
            .where(GenerationORM.selection_id.in_(selection_ids))
            .order_by(GenerationORM.created_at.desc())
        )
        generations = gen_res.scalars().all()

        # 7. Compute staleness for each retrieved generation
        results = []
        for gen in generations:
            stale_info = await self.check_staleness(db, gen)
            results.append(stale_info)

        return results
