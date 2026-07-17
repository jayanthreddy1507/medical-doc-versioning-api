# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0, 1, 2
- **Phase in progress**: None (Phase 2 just completed)
- **Key decisions made**:
  - FastAPI as web framework
  - SQLAlchemy (async) as ORM with SQLite for dev
  - Pydantic v2 for schemas/validation
  - PyMuPDF for PDF parsing (per-span font metadata)
  - Adjacency list pattern for node tree in DB (parent_id self-join)
  - Documents → Versions → Nodes hierarchy in DB
  - File uploads saved to `data/` with sanitized filenames
  - Version auto-increment per document on re-upload
  - See [docs/parsing_notes.md](docs/parsing_notes.md) for irregularity catalog
  - See [docs/approach.md](docs/approach.md) for architecture decisions
- **Known broken/unfinished**: Nothing broken; all 39 tests pass
- **Next steps**:
  - **Phase 3**: Version matching / diff (`diff_nodes()` to compare two parsed trees)
  - **Phase 3**: Diff summary endpoint (e.g. `GET /documents/{id}/diff?v1=1&v2=2`)
  - **Phase 3**: Implement `versioning.py::diff_nodes()` comparing content hashes

---

## Architecture Overview

```
Affine/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # SQLAlchemy engine & session
│   ├── models/
│   │   ├── __init__.py       # Model import hub
│   │   ├── base.py           # DeclarativeBase
│   │   ├── db_models.py      # DocumentORM, VersionORM, NodeORM tables
│   │   └── document.py       # DocumentNode, ParsedDocument (in-memory tree)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py         # Health check response schema
│   │   └── document.py       # Ingest, Document, Version, Node schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health
│   │   └── documents.py      # POST /ingest, GET /documents, versions
│   └── services/
│       ├── __init__.py
│       ├── parser.py         # PDFParser — PDF → document tree
│       └── ingestion.py      # IngestionService — parse → persist
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # DB table creation for tests
│   ├── test_health.py        # 1 test
│   ├── test_parser.py        # 28 tests
│   ├── test_ingest.py        # 10 tests
│   ├── generate_test_pdf.py  # Test PDF generator
│   └── inspect_pdf.py        # PDF structure inspector
├── data/
│   ├── .gitkeep
│   └── test_manual.pdf
├── docs/
│   ├── approach.md
│   └── parsing_notes.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── HANDOFF.md
└── README.md
```

## DB Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  documents   │     │   versions   │     │    nodes     │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id (PK)      │◄────│ document_id  │     │ id (PK)      │
│ filename     │     │ id (PK)      │◄────│ version_id   │
│ title        │     │ version_num  │     │ parent_id    │──┐
│ created_at   │     │ total_pages  │     │ section_num  │  │
│ updated_at   │     │ node_count   │     │ title        │  │
└──────────────┘     │ irregulars   │     │ content      │  │
                     │ created_at   │     │ level        │  │
                     └──────────────┘     │ node_type    │  │
                                          │ page_number  │  │
                                          │ content_hash │  │
                                          │ reading_order│  │
                                          │ font_*       │  │
                                          └──────────────┘  │
                                               ▲            │
                                               └────────────┘
                                            (self-join: adjacency list)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/ingest` | Upload & parse PDF |
| GET | `/api/v1/documents` | List all documents |
| GET | `/api/v1/documents/{id}/versions` | List versions for a document |
| GET | `/api/v1/documents/{id}/versions/{n}` | Full version detail with tree |

---

## Phase Log

### Phase 0 — Repo Scaffolding ✅
- **Commit**: `chore: project scaffolding` (`14f338a`)
- **Tests**: 1 passing

### Phase 1 — PDF Parsing & Hierarchy Extraction ✅
- **Commit**: `feat: PDF parsing with hierarchy extraction and irregularity handling` (`d10a233`)
- **Tests**: 29 passing (28 parser + 1 health)

### Phase 2 — Persistence Layer ✅
- **Commit**: `feat: persistence layer with SQLite + ingestion endpoint`
- **What**:
  - `app/models/db_models.py` — ORM: DocumentORM, VersionORM, NodeORM
  - `app/schemas/document.py` — Pydantic schemas for all endpoints
  - `app/services/ingestion.py` — Parse → persist orchestrator
  - `app/routers/documents.py` — POST /ingest + GET endpoints
  - `tests/test_ingest.py` — 10 ingestion/retrieval tests
  - `tests/conftest.py` — DB table setup for tests
- **Tests**: 39 passing (1 health + 28 parser + 10 ingest)
