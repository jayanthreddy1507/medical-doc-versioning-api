# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0, 1, 2, 3, 4
- **Phase in progress**: None (Phase 4 just completed)
- **Key decisions made**:
  - FastAPI as web framework
  - SQLAlchemy (async) as ORM with SQLite for dev
  - Pydantic v2 for schemas/validation
  - PyMuPDF for PDF parsing (per-span font metadata)
  - Adjacency list pattern for node tree in DB (parent_id self-join)
  - Documents → Versions → Nodes hierarchy in DB
  - Hierarchical Path + Title Match Strategy for version comparison
  - Gesture/Gestalt pattern matching via SequenceMatcher for fuzzy title matching ($70\%$ threshold)
  - Unified diff summaries comparing `content_hash` across versions
  - Trailing-dot normalized section numbers (e.g., `"2. Physical Specifications"` $\rightarrow$ `"2"`)
  - **Browse API Endpoints**: Lists top-level sections, node detail (including children), keyword search, and node history diff across versions
- **Known broken/unfinished**: Nothing broken; all 41 tests pass
- **Next steps**:
  - **Phase 5**: Selection API (version-pinned selections of node IDs)
  - **Phase 6**: LLM-powered test-case generation API (structured output validation)
  - **Phase 7**: Staleness / impact detection of generated test cases when document is re-versioned
  - **Phase 8**: Retrieval API (fetch test cases by selection ID or node ID)

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
│   │   └── document.py       # Ingest, Document, Version, Node, Diff, Browse schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health
│   │   └── documents.py      # Ingest, Documents, Sections, Search, Node details, History
│   └── services/
│       ├── __init__.py
│       ├── parser.py         # PDFParser — PDF → document tree
│       ├── ingestion.py      # IngestionService — parse → persist, browse helpers
│       └── versioning.py     # VersioningService — matched node tree diffs, history trace
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # DB table drop & create for tests
│   ├── test_health.py        # 1 test
│   ├── test_parser.py        # 28 tests
│   ├── test_ingest.py        # 10 tests
│   ├── test_versioning.py    # 1 test
│   ├── test_browse.py        # 1 test (E2E browse API validation)
│   ├── generate_test_pdf.py  # Test PDF generator (Phase 1)
│   ├── generate_ct200_pdfs.py# Exact CardioTrack CT-200 PDF generator (Phase 3)
│   └── inspect_pdf.py        # PDF structure inspector
├── data/
│   ├── .gitkeep
│   ├── ct200_manual_v1.pdf   # Real CT-200 v1 PDF
│   ├── ct200_manual_v2.pdf   # Real CT-200 v2 PDF
│   └── test_manual.pdf
├── docs/
│   ├── approach.md
│   ├── parsing_notes.md
│   └── matching_strategy.md  # Detailed version matching strategy
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── HANDOFF.md                # ← You are here
└── README.md
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
| GET | `/api/v1/documents/{id}/diff?v1=1&v2=2` | Generate version tree comparison diff |
| GET | `/api/v1/documents/{id}/sections?version=1`| List top-level sections (defaults to latest) |
| GET | `/api/v1/nodes/{id}` | Get node details (includes immediate children) |
| GET | `/api/v1/documents/{id}/search?q=query` | Case-insensitive substring search (defaults to latest) |
| GET | `/api/v1/nodes/{id}/diff` | Track changes/diff history of a node across versions |

---

## Phase Log

### Phase 0 — Repo Scaffolding ✅
- **Commit**: `chore: project scaffolding` (`14f338a`)

### Phase 1 — PDF Parsing & Hierarchy Extraction ✅
- **Commit**: `feat: PDF parsing with hierarchy extraction and irregularity handling` (`d10a233`)

### Phase 2 — Persistence Layer ✅
- **Commit**: `feat: persistence layer with SQLite + ingestion endpoint` (`62e52cc`)

### Phase 3 — Versioning & Matching Strategy ✅
- **Commit**: `feat: version matching strategy and document diff endpoint` (`e1ee8fe`)

### Phase 4 — Browse API ✅
- **Commit**: `feat: Browse API endpoints and change status tracing`
- **What**:
  - `app/services/ingestion.py` — Added `get_top_level_sections`, `get_node_by_id`, and `search_nodes`
  - `app/services/versioning.py` — Added `get_node_history` tracing life cycles and inline diffs
  - `app/routers/documents.py` — Exposed all 4 Browse API router endpoints
  - `tests/test_browse.py` — Full E2E validation of browse capabilities on CT-200 v1/v2
  - `README.md` — Added detailed API reference and curl examples
- **Tests**: 42 passing (1 health + 28 parser + 10 ingest + 1 versioning + 2 browse)
