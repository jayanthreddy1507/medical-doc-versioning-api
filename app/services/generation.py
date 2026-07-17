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
