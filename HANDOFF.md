# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0, 1
- **Phase in progress**: None (Phase 1 just completed)
- **Key decisions made**:
  - FastAPI as web framework
  - SQLAlchemy (async) as ORM with SQLite for dev
  - Pydantic v2 for schemas/validation
  - **PyMuPDF** for PDF parsing (per-span font metadata, 10-50× faster than pdfplumber)
  - Font-size + bold-flag heuristics for heading detection
  - Stack-based tree builder handling out-of-order, skipped levels, duplicates
  - SHA-256 content hashing per node for version comparison
  - See [docs/parsing_notes.md](docs/parsing_notes.md) for full irregularity catalog
  - See [docs/approach.md](docs/approach.md) for architecture decisions
- **Known broken/unfinished**: Nothing broken; all 29 tests pass
- **Next steps**:
  - **Phase 2**: Build versioning logic (`diff_nodes()` to compare two parsed trees)
  - **Phase 2**: Store parsed documents and versions in the database (SQLAlchemy ORM models)
  - **Phase 2**: Add API endpoint to upload and parse a PDF
  - **Phase 3**: Version matching and diff summary

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
│   │   └── document.py       # DocumentNode, ParsedDocument, FontInfo, NodeType
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── health.py         # Health check response schema
│   ├── routers/
│   │   ├── __init__.py
│   │   └── health.py         # /health endpoint
│   └── services/
│       ├── __init__.py
│       └── parser.py         # PDFParser — PDF → document tree
├── tests/
│   ├── __init__.py
│   ├── test_health.py        # Health endpoint smoke test
│   ├── test_parser.py        # 28 parser tests (irregularities, hashing, etc.)
│   ├── generate_test_pdf.py  # Generates test PDF with known irregularities
│   └── inspect_pdf.py        # Raw PDF structure inspector (diagnostic)
├── data/
│   ├── .gitkeep
│   └── test_manual.pdf       # Generated test PDF (4 pages, 5 irregularities)
├── docs/
│   ├── approach.md           # High-level design decisions
│   └── parsing_notes.md      # Every irregularity found + parser architecture
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── HANDOFF.md                # ← You are here
└── README.md
```

---

## Phase Log

### Phase 0 — Repo Scaffolding ✅
- **Commit**: `chore: project scaffolding` (`14f338a`)
- **What**: Folder structure, FastAPI skeleton, SQLAlchemy base, health endpoint
- **Tests**: 1 passing

### Phase 1 — PDF Parsing & Hierarchy Extraction ✅
- **Commit**: `feat: PDF parsing with hierarchy extraction and irregularity handling`
- **What**:
  - `app/models/document.py` — Tree schema: `DocumentNode`, `ParsedDocument`, `FontInfo`, `NodeType`
  - `app/services/parser.py` — Full PDF parser with PyMuPDF
  - `tests/test_parser.py` — 28 tests across 7 test classes
  - `tests/generate_test_pdf.py` — Test PDF generator with 5 embedded irregularities
  - `docs/parsing_notes.md` — Complete irregularity catalog
- **Irregularities detected**:
  1. Out-of-order sections (3.4 before 3.3) — preserved in reading order
  2. Skipped heading levels (2.1.1.1 without 2.1.1) — placed under nearest ancestor
  3. Duplicate numbering (two 4.2 sections) — disambiguated with `_dup1` suffix
  4. Tables with mixed font styles — detected via y-coordinate clustering
  5. Multi-page content — page number tracked per heading
- **Tests**: 29 passing (28 parser + 1 health)
