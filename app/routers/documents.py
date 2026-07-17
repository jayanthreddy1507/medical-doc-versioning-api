"""Ingestion and document retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import DocumentORM, VersionORM
from app.schemas.document import (
    DocumentSummary,
    IngestResponse,
    VersionDetailResponse,
    VersionSummary,
)
from app.services.ingestion import IngestionService

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
