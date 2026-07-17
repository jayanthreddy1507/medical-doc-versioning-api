# Project Handoff Document

> **Purpose**: This file is the continuity mechanism when switching AIs mid-project.  
> Every phase, whichever AI is working updates this before credits run out.

---

## Current State

- **Phases done**: 0
- **Phase in progress**: None (Phase 0 just completed)
- **Key decisions made**:
  - FastAPI as web framework
  - SQLAlchemy (async) as ORM with SQLite for dev
  - Pydantic v2 for schemas/validation
  - Alembic-ready project structure
  - Folder layout: `app/` (source), `tests/`, `data/`, `docs/`
- **Known broken/unfinished**: Nothing broken; all scaffolding is in place and runnable
- **Next steps**:
  - **Phase 1**: Define domain models in `app/models/` (actual tables)
  - **Phase 1**: Flesh out Pydantic schemas in `app/schemas/`
  - **Phase 1**: Add first real API routes in `app/routers/`
  - **Phase 1**: Set up Alembic migrations

---

## Architecture Overview

```
Affine/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app entry point
│   ├── config.py           # Settings via pydantic-settings
│   ├── database.py         # SQLAlchemy engine & session
│   ├── models/
│   │   ├── __init__.py     # Base model import hub
│   │   └── base.py         # DeclarativeBase
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── health.py       # Health check response schema
│   ├── routers/
│   │   ├── __init__.py
│   │   └── health.py       # /health endpoint
│   └── services/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_health.py      # Smoke test for /health
├── data/                    # Runtime data (DB files, uploads, etc.)
│   └── .gitkeep
├── docs/
│   └── approach.md          # High-level design decisions
├── requirements.txt
├── .gitignore
├── HANDOFF.md               # ← You are here
└── README.md
```

---

## Phase Log

### Phase 0 — Repo Scaffolding ✅
- **Commit message**: `chore: project scaffolding`
- **What was done**: Created folder structure, FastAPI skeleton, SQLAlchemy base, empty Pydantic schemas, health endpoint, requirements.txt, .gitignore
- **Runnable**: Yes — `uvicorn app.main:app --reload` serves at http://localhost:8000
- **Tests**: `pytest` runs 1 smoke test (health check)
