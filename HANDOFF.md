# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0, 1, 2, 3, 4, 5, 6
- **Phase in progress**: None (Phase 6 just completed)
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
  - Browse API Endpoints: Lists top-level sections, node detail, keyword search, and node history diff across versions
  - Selection API Endpoints: Named, version-pinned selections mapping to specific node IDs
  - **LLM Generation API**: Generates 3-5 QA test case ideas for selections with structured validation and correction retries
  - **Duplicate Submission Policy**: Returns cached test-case generation immediately by default to reduce API latency/cost, with `force_regenerate=true` cache bypass option
  - **NoSQL JSON Store**: SQLite JSON extensions in `generations` table to store LLM prompts, outputs, and node content hashes
  - See [docs/llm_design.md](docs/llm_design.md) for prompting, self-repair retries, and duplicate policies
- **Known broken/unfinished**: Nothing broken; all 46 tests pass
- **Next steps**:
  - **Phase 7**: Staleness / impact detection of generated test cases when document is re-versioned
  - **Phase 8**: Retrieval API (fetch test cases by selection ID or node ID with staleness status)

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
│   │   ├── db_models.py      # DocumentORM, VersionORM, NodeORM, SelectionORM, GenerationORM
│   │   └── document.py       # DocumentNode, ParsedDocument (in-memory tree)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py         # Health check response schema
│   │   └── document.py       # Ingest, Document, Version, Node, Diff, Browse, Selection, Generation schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health
│   │   └── documents.py      # Ingest, Documents, Sections, Search, Node details, History, Selections, Generate
│   └── services/
│       ├── __init__.py
│       ├── parser.py         # PDFParser — PDF → document tree
│       ├── ingestion.py      # IngestionService — parse → persist, browse helpers
│       ├── versioning.py     # VersioningService — matched node tree diffs, history trace
│       └── generation.py     # GenerationService — LLM test case ideas generator, repair retry loop
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # DB table drop & create for tests
│   ├── test_health.py        # 1 test
│   ├── test_parser.py        # 28 tests
│   ├── test_ingest.py        # 10 tests
│   ├── test_versioning.py    # 1 test
│   ├── test_browse.py        # 1 test
│   ├── test_selections.py    # 3 tests
│   ├── test_generation.py    # 2 tests (E2E generation cache & self-repair retry validation)
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
│   ├── matching_strategy.md  # Detailed version matching strategy
│   └── llm_design.md         # LLM prompting, correction loops, and duplicate policies
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
| POST | `/api/v1/selections` | Create a named, version-pinned selection of node IDs |
| GET | `/api/v1/selections/{id}` | Retrieve a selection, resolving its nodes and text content |
| POST | `/api/v1/selections/{id}/generate?force_regenerate=false` | Generate QA test cases for a selection (cached by default) |

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
- **Commit**: `feat: Browse API endpoints and change status tracing` (`0202b5b`)

### Phase 5 — Selection API ✅
- **Commit**: `feat: Named, version-pinned Selection API` (`3e839b6`)

### Phase 6 — LLM generation API ✅
- **Commit**: `feat: LLM test-case generation with self-repair retry loop` (`7d8945a`)
