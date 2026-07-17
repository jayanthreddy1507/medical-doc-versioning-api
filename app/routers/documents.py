"""Ingestion and document retrieval endpoints."""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import DocumentORM, VersionORM, SelectionORM, NodeORM
from app.schemas.document import (
    DocumentSummary,
    IngestResponse,
    VersionDetailResponse,
    VersionSummary,
    DiffSummaryResponse,
    NodeDetailResponse,
    NodeSearchResponse,
    NodeHistoryResponse,
    SelectionCreate,
    SelectionResponse,
    GenerationDetailResponse,
)
from app.services.ingestion import IngestionService
from app.services.versioning import VersioningService
from app.services.generation import GenerationService

router = APIRouter(tags=["documents"])

# Singleton service instance
_ingestion_service = IngestionService()


@router.post("/ingest", response_model=IngestResponse, status_code=201)
async def ingest_document(
    file: UploadFile = File(..., description="PDF file to ingest"),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Upload and ingest a PDF document.

    Parses the PDF, extracts the document hierarchy, and persists
    it to the database. If the filename already exists, a new version
    is created.

    Returns document ID, version ID, and parsing metadata.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Upload a file with .pdf extension.",
        )

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = await _ingestion_service.ingest(
            db=db,
            filename=file.filename,
            file_content=content,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse PDF: {str(e)}",
        )

    return IngestResponse(**result)


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[DocumentSummary]:
    """List all ingested documents with version counts."""
    result = await db.execute(
        select(DocumentORM).order_by(DocumentORM.updated_at.desc())
    )
    documents = result.scalars().all()

    summaries = []
    for doc in documents:
        # Count versions
        ver_result = await db.execute(
            select(func.count(VersionORM.id)).where(
                VersionORM.document_id == doc.id
            )
        )
        version_count = ver_result.scalar() or 0

        # Get latest version number
        latest_result = await db.execute(
            select(func.max(VersionORM.version_number)).where(
                VersionORM.document_id == doc.id
            )
        )
        latest_version = latest_result.scalar()

        summaries.append(DocumentSummary(
            id=doc.id,
            filename=doc.filename,
            title=doc.title,
            version_count=version_count,
            latest_version=latest_version,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    return summaries


@router.get("/documents/{document_id}/versions", response_model=list[VersionSummary])
async def list_versions(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[VersionSummary]:
    """List all versions for a specific document."""
    # Verify document exists
    doc_result = await db.execute(
        select(DocumentORM).where(DocumentORM.id == document_id)
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    result = await db.execute(
        select(VersionORM)
        .where(VersionORM.document_id == document_id)
        .order_by(VersionORM.version_number)
    )
    versions = result.scalars().all()

    return [
        VersionSummary(
            id=v.id,
            version_number=v.version_number,
            total_pages=v.total_pages,
            node_count=v.node_count,
            irregularities=_parse_irregularities(v.irregularities),
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/documents/{document_id}/versions/{version_number}", response_model=VersionDetailResponse)
async def get_version_detail(
    document_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db),
) -> VersionDetailResponse:
    """Get full version detail including the document tree."""
    result = await db.execute(
        select(VersionORM).where(
            VersionORM.document_id == document_id,
            VersionORM.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version_number} not found for document {document_id}",
        )

    # Reconstruct the tree
    tree = await _ingestion_service.get_document_tree(db, version.id)

    return VersionDetailResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        total_pages=version.total_pages,
        node_count=version.node_count,
        irregularities=_parse_irregularities(version.irregularities),
        created_at=version.created_at,
        tree=tree,
    )


def _parse_irregularities(raw: str | None) -> list[str]:
    """Parse JSON-encoded irregularities string back to a list."""
    if not raw:
        return []
    try:
        import json
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [raw]


# Singleton versioning service instance
_versioning_service = VersioningService()


@router.get("/documents/{document_id}/diff", response_model=DiffSummaryResponse)
async def diff_document_versions(
    document_id: int,
    v1: int,
    v2: int,
    db: AsyncSession = Depends(get_db),
) -> DiffSummaryResponse:
    """Compare two versions of a document to find added, removed, modified, or unchanged sections.

    Returns the counts of changes and a hierarchical diff tree.
    """
    # Verify document exists
    doc_result = await db.execute(
        select(DocumentORM).where(DocumentORM.id == document_id)
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found",
        )

    try:
        diff_summary = await _versioning_service.diff_versions(
            db=db,
            document_id=document_id,
            v1_num=v1,
            v2_num=v2,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate diff: {str(e)}",
        )

    return DiffSummaryResponse(**diff_summary)


# ── Browse API Router Endpoints ──────────────────────────────────────────

@router.get("/documents/{document_id}/sections", response_model=list[NodeSearchResponse])
async def list_top_level_sections(
    document_id: int,
    version: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[NodeSearchResponse]:
    """List all top-level sections (level 1 nodes) of a document.

    If version is not provided, defaults to the latest version.
    """
    # Verify document exists
    doc_result = await db.execute(
        select(DocumentORM).where(DocumentORM.id == document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    # Resolve latest version if not provided
    if version is None:
        latest_result = await db.execute(
            select(func.max(VersionORM.version_number)).where(
                VersionORM.document_id == document_id
            )
        )
        version = latest_result.scalar()
        if version is None:
            return []

    sections = await _ingestion_service.get_top_level_sections(
        db=db,
        document_id=document_id,
        version_number=version,
    )
    return [NodeSearchResponse(**s) for s in sections]


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node_details(
    node_id: int,
    db: AsyncSession = Depends(get_db),
) -> NodeDetailResponse:
    """Retrieve details for a specific node by ID, including its immediate children."""
    node_details = await _ingestion_service.get_node_by_id(db, node_id)
    if node_details is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return NodeDetailResponse(**node_details)


@router.get("/documents/{document_id}/search", response_model=list[NodeSearchResponse])
async def search_nodes(
    document_id: int,
    q: str,
    version: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[NodeSearchResponse]:
    """Search/filter nodes by title or content within a specific document version.

    If version is not provided, defaults to the latest version.
    """
    # Verify document exists
    doc_result = await db.execute(
        select(DocumentORM).where(DocumentORM.id == document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    # Resolve latest version if not provided
    if version is None:
        latest_result = await db.execute(
            select(func.max(VersionORM.version_number)).where(
                VersionORM.document_id == document_id
            )
        )
        version = latest_result.scalar()
        if version is None:
            return []

    results = await _ingestion_service.search_nodes(
        db=db,
        document_id=document_id,
        query=q,
        version_number=version,
    )
    return [NodeSearchResponse(**r) for r in results]


@router.get("/nodes/{node_id}/diff", response_model=NodeHistoryResponse)
async def get_node_diff_history(
    node_id: int,
    db: AsyncSession = Depends(get_db),
) -> NodeHistoryResponse:
    """Retrieve the change history of a specific node across all versions of the document.

    Matches the node by path/title across revisions to verify if it was modified, added,
    or removed, returning a unified diff summary of content modifications.
    """
    history = await _versioning_service.get_node_history(db, node_id)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return NodeHistoryResponse(**history)


# ── Selection API Router Endpoints ───────────────────────────────────────

@router.post("/selections", response_model=SelectionResponse, status_code=201)
async def create_node_selection(
    payload: SelectionCreate,
    db: AsyncSession = Depends(get_db),
) -> SelectionResponse:
    """Create a named, version-pinned selection of document nodes.

    Verifies that all node IDs exist. The nodes remain bound to their specific
    revisions, protecting the selection against future document re-ingestions.
    """
    if not payload.node_ids:
        raise HTTPException(status_code=400, detail="Node IDs list cannot be empty")

    # Fetch and verify all nodes exist
    nodes = []
    for nid in payload.node_ids:
        node_res = await db.execute(select(NodeORM).where(NodeORM.id == nid))
        node = node_res.scalar_one_or_none()
        if not node:
            raise HTTPException(
                status_code=400,
                detail=f"Node ID {nid} does not exist",
            )
        nodes.append(node)

    # Create selection record
    selection = SelectionORM(name=payload.name)
    selection.nodes.extend(nodes)
    db.add(selection)
    await db.flush()  # Retrieve selection.id and selection.created_at

    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        created_at=selection.created_at,
        nodes=[
            NodeSearchResponse(
                id=n.id,
                section_number=n.section_number,
                title=n.title,
                content=n.content,
                level=n.level,
                node_type=n.node_type,
                page_number=n.page_number,
                content_hash=n.content_hash,
                reading_order=n.reading_order,
            )
            for n in nodes
        ],
    )


@router.get("/selections/{selection_id}", response_model=SelectionResponse)
async def get_node_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
) -> SelectionResponse:
    """Retrieve a version-pinned selection by ID, resolving its nodes and text."""
    # Fetch selection with joined nodes relationship
    from sqlalchemy.orm import selectinload
    sel_res = await db.execute(
        select(SelectionORM)
        .where(SelectionORM.id == selection_id)
        .options(selectinload(SelectionORM.nodes))
    )
    selection = sel_res.scalar_one_or_none()
    if not selection:
        raise HTTPException(
            status_code=404,
            detail=f"Selection {selection_id} not found",
        )

    # Sort nodes by reading order
    sorted_nodes = sorted(selection.nodes, key=lambda n: n.reading_order)

    return SelectionResponse(
        id=selection.id,
        name=selection.name,
        created_at=selection.created_at,
        nodes=[
            NodeSearchResponse(
                id=n.id,
                section_number=n.section_number,
                title=n.title,
                content=n.content,
                level=n.level,
                node_type=n.node_type,
                page_number=n.page_number,
                content_hash=n.content_hash,
                reading_order=n.reading_order,
            )
            for n in sorted_nodes
        ],
    )


# Singleton generation service instance
_generation_service = GenerationService()


@router.post("/selections/{selection_id}/generate", response_model=GenerationDetailResponse)
async def generate_selection_test_cases(
    selection_id: int,
    force_regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
) -> GenerationDetailResponse:
    """Generate QA test case ideas for a version-pinned selection.

    By default, returns cached results if already generated. Pass force_regenerate=true
    to trigger a new model call and overwrite the cached generation.
    """
    # Fetch selection with joined nodes relationship
    from sqlalchemy.orm import selectinload
    sel_res = await db.execute(
        select(SelectionORM)
        .where(SelectionORM.id == selection_id)
        .options(selectinload(SelectionORM.nodes))
    )
    selection = sel_res.scalar_one_or_none()
    if not selection:
        raise HTTPException(
            status_code=404,
            detail=f"Selection {selection_id} not found",
        )

    try:
        generation = await _generation_service.generate_test_cases(
            db=db,
            selection=selection,
            force_regenerate=force_regenerate,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate test cases: {str(e)}",
        )

    # Parse JSON serialized test cases back to TestCaseIdea objects
    test_cases_list = json.loads(generation.test_cases)["test_cases"]

    return GenerationDetailResponse(
        id=generation.id,
        selection_id=generation.selection_id,
        prompt=generation.prompt,
        test_cases=test_cases_list,
        created_at=generation.created_at,
    )
