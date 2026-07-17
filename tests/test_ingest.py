"""Tests for the ingestion endpoint and persistence layer.

Tests cover:
  1. POST /ingest — successful PDF upload and parsing
  2. POST /ingest — validation (non-PDF, empty file)
  3. GET /documents — list documents after ingestion
  4. GET /documents/{id}/versions — list versions
  5. GET /documents/{id}/versions/{n} — full tree retrieval
  6. Version increment on re-upload of same filename
  7. Tree structure integrity in the database
"""

import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.generate_test_pdf import generate_test_pdf


@pytest.fixture(scope="session")
def test_pdf_bytes(tmp_path_factory) -> bytes:
    """Generate a test PDF and return its bytes."""
    tmp_dir = tmp_path_factory.mktemp("ingest_pdfs")
    pdf_path = str(tmp_dir / "test_manual.pdf")
    generate_test_pdf(pdf_path)
    with open(pdf_path, "rb") as f:
        return f.read()


@pytest.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Successful ingestion
# ═══════════════════════════════════════════════════════════════════════

class TestIngestion:
    """POST /api/v1/ingest with a valid PDF."""

    @pytest.mark.asyncio
    async def test_ingest_returns_201(self, client, test_pdf_bytes):
        """First upload should return 201 with document metadata."""
        response = await client.post(
            "/api/v1/ingest",
            files={"file": ("medical_manual.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["document_id"] >= 1
        assert data["version_id"] >= 1
        assert data["version_number"] == 1
        assert data["filename"] == "medical_manual.pdf"
        assert data["total_pages"] == 4
        assert data["node_count"] > 0
        assert len(data["irregularities"]) == 3

    @pytest.mark.asyncio
    async def test_reingest_increments_version(self, client, test_pdf_bytes):
        """Re-uploading same filename should create version 2."""
        # First upload
        await client.post(
            "/api/v1/ingest",
            files={"file": ("versioned_doc.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        # Second upload — same filename
        response = await client.post(
            "/api/v1/ingest",
            files={"file": ("versioned_doc.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version_number"] == 2

    @pytest.mark.asyncio
    async def test_ingest_populates_irregularities(self, client, test_pdf_bytes):
        """Ingestion result should list all detected irregularities."""
        response = await client.post(
            "/api/v1/ingest",
            files={"file": ("irregularity_test.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        data = response.json()
        irregularities = data["irregularities"]
        assert any("OUT_OF_ORDER" in i for i in irregularities)
        assert any("SKIPPED_LEVEL" in i for i in irregularities)
        assert any("DUPLICATE_NUMBER" in i for i in irregularities)


# ═══════════════════════════════════════════════════════════════════════
# Test 2: Validation
# ═══════════════════════════════════════════════════════════════════════

class TestIngestionValidation:
    """POST /api/v1/ingest with invalid inputs."""

    @pytest.mark.asyncio
    async def test_reject_non_pdf(self, client):
        """Should reject non-PDF files with 400."""
        response = await client.post(
            "/api/v1/ingest",
            files={"file": ("readme.txt", io.BytesIO(b"not a pdf"), "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_reject_empty_file(self, client):
        """Should reject empty files with 400."""
        response = await client.post(
            "/api/v1/ingest",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Document listing
# ═══════════════════════════════════════════════════════════════════════

class TestDocumentListing:
    """GET /api/v1/documents."""

    @pytest.mark.asyncio
    async def test_list_documents_after_ingest(self, client, test_pdf_bytes):
        """After ingestion, document should appear in listing."""
        # Ingest first
        await client.post(
            "/api/v1/ingest",
            files={"file": ("list_test.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )

        response = await client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find our document
        doc = next((d for d in data if d["filename"] == "list_test.pdf"), None)
        assert doc is not None, f"list_test.pdf not found in: {[d['filename'] for d in data]}"
        assert doc["version_count"] >= 1


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Version listing & detail
# ═══════════════════════════════════════════════════════════════════════

class TestVersionRetrieval:
    """GET /api/v1/documents/{id}/versions endpoints."""

    @pytest.mark.asyncio
    async def test_list_versions(self, client, test_pdf_bytes):
        """Should list all versions for a document."""
        # Ingest
        ingest_resp = await client.post(
            "/api/v1/ingest",
            files={"file": ("ver_test.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        doc_id = ingest_resp.json()["document_id"]

        response = await client.get(f"/api/v1/documents/{doc_id}/versions")
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) >= 1
        assert versions[0]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_get_version_detail_with_tree(self, client, test_pdf_bytes):
        """Should return the full node tree for a version."""
        # Ingest
        ingest_resp = await client.post(
            "/api/v1/ingest",
            files={"file": ("tree_test.pdf", io.BytesIO(test_pdf_bytes), "application/pdf")},
        )
        data = ingest_resp.json()
        doc_id = data["document_id"]

        response = await client.get(f"/api/v1/documents/{doc_id}/versions/1")
        assert response.status_code == 200
        detail = response.json()
        assert detail["version_number"] == 1
        assert detail["total_pages"] == 4

        # Tree should exist with children
        tree = detail["tree"]
        assert tree is not None
        assert tree["title"] == "Document Root"
        assert len(tree["children"]) == 5  # Sections 1-5

    @pytest.mark.asyncio
    async def test_version_not_found(self, client):
        """Non-existent version should return 404."""
        response = await client.get("/api/v1/documents/9999/versions/99")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_document_not_found(self, client):
        """Non-existent document should return 404."""
        response = await client.get("/api/v1/documents/9999/versions")
        assert response.status_code == 404
