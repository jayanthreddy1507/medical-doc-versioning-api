# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0, 1, 2, 3
- **Phase in progress**: None (Phase 3 just completed)
- **Key decisions made**:
  - FastAPI as web framework
  - SQLAlchemy (async) as ORM with SQLite for dev
  - Pydantic v2 for schemas/validation
  - PyMuPDF for PDF parsing (per-span font metadata)
  - Adjacency list pattern for node tree in DB (parent_id self-join)
  - Documents → Versions → Nodes hierarchy in DB
  - **Hierarchical Path + Title Match Strategy** for version comparison
  - Gesture/Gestalt pattern matching via SequenceMatcher for fuzzy title matching ($70\%$ threshold)
  - Unified diff summaries comparing `content_hash` across versions
  - Trailing-dot normalized section numbers (e.g., `"2. Physical Specifications"` $\rightarrow$ `"2"`)
  - See [docs/parsing_notes.md](docs/parsing_notes.md) for irregularity catalog
  - See [docs/matching_strategy.md](docs/matching_strategy.md) for versioning/matching strategy details
- **Known broken/unfinished**: Nothing broken; all 40 tests pass
- **Next steps**:
  - **Phase 4**: Selection API (version-pinned selection of node IDs)
  - **Phase 5**: LLM-powered test-case generation API (structured output validation)
  - **Phase 6**: Staleness / impact detection of generated test cases when document is re-versioned
  - **Phase 7**: Retrieval API (fetch test cases by selection ID or node ID)

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
│   │   └── document.py       # Ingest, Document, Version, Node, Diff schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health
│   │   └── documents.py      # Ingest, Documents, Versions, Diff GET endpoints
│   └── services/
│       ├── __init__.py
│       ├── parser.py         # PDFParser — PDF → document tree
│       ├── ingestion.py      # IngestionService — parse → persist
│       └── versioning.py     # VersioningService — matched node tree diffs
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # DB table drop & create for tests
│   ├── test_health.py        # 1 test
│   ├── test_parser.py        # 28 tests
│   ├── test_ingest.py        # 10 tests
│   ├── test_versioning.py    # 1 test (CardioTrack CT-200 v1/v2 complete flow)
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

---

## Phase Log

### Phase 0 — Repo Scaffolding ✅
- **Commit**: `chore: project scaffolding` (`14f338a`)

### Phase 1 — PDF Parsing & Hierarchy Extraction ✅
- **Commit**: `feat: PDF parsing with hierarchy extraction and irregularity handling` (`d10a233`)

### Phase 2 — Persistence Layer ✅
- **Commit**: `feat: persistence layer with SQLite + ingestion endpoint` (`62e52cc`)

### Phase 3 — Versioning & Matching Strategy ✅
- **Commit**: `feat: version matching strategy and document diff endpoint`
- **What**:
  - `app/services/versioning.py` — Hierarchical path-based matching with SequenceMatcher fallback
  - `app/routers/documents.py` — `GET /documents/{document_id}/diff` endpoint
  - `app/schemas/document.py` — Pydantic diff response schemas
  - `tests/generate_ct200_pdfs.py` — Exact V1/V2 CardioTrack CT-200 PDF generator
  - `tests/test_versioning.py` — E2E integration test diffing CT-200 versions
  - `docs/matching_strategy.md` — Detail matching edge cases and "where it breaks"
- **Tests**: 40 passing (1 health + 28 parser + 10 ingest + 1 E2E versioning diff)
