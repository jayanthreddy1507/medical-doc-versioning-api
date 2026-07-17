# Approach & Design Decisions

> This document captures key architectural decisions. Referenced from HANDOFF.md.

---

## Phase 0 Decisions

### Framework: FastAPI
- **Why**: Async-first, auto-generated OpenAPI docs, Pydantic integration, production-proven.
- **Alternative considered**: Flask — rejected because async support is bolted-on and lacks native schema validation.

### ORM: SQLAlchemy 2.0 (async)
- **Why**: Industry standard, supports async via `aiosqlite`/`asyncpg`, excellent migration support via Alembic.
- **Dev DB**: SQLite (zero config). Swap to PostgreSQL for staging/prod by changing `DATABASE_URL`.

### Validation: Pydantic v2
- **Why**: 5-50× faster than v1, native integration with FastAPI, clean schema definitions.

### Project Layout
- **`app/`**: All application source code. Sub-packages: `models/`, `schemas/`, `routers/`, `services/`.
- **`tests/`**: Mirrors `app/` structure. Uses `pytest` + `httpx` for async testing.
- **`data/`**: Runtime artifacts (SQLite DB, uploaded files). Git-ignored contents.
- **`docs/`**: Design docs and approach notes.

---

## Future Decisions (to be filled per phase)

### Phase 1 — Domain Models
_TBD_

### Phase 2 — Business Logic
_TBD_

### Phase 3 — Version Matching
_TBD_
