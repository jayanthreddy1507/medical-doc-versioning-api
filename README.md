# Affine

> A FastAPI application built incrementally across phases with AI handoff continuity.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the app
uvicorn app.main:app --reload

# Run tests
pytest
```

## Project Structure

See [HANDOFF.md](HANDOFF.md) for the full architecture overview and phase log.

## API Docs

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## API Reference & Examples

### Ingestion API

#### 1. Ingest PDF Document
Uploads a PDF manual, parses its heading levels, extracts tables, and persists the tree structure in SQLite.
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@data/ct200_manual_v1.pdf"
```

### Browse API

#### 2. List Top-Level Sections
Retrieves the level-1 chapters of a document. If `version` is omitted, defaults to the latest revision.
```bash
curl "http://localhost:8000/api/v1/documents/1/sections?version=1"
```

#### 3. Search Nodes
Search title or body content of sections within a specific document version.
```bash
curl "http://localhost:8000/api/v1/documents/1/search?q=cuff&version=1"
```

#### 4. Get Node Details
Fetch a specific node by ID, including its immediate children.
```bash
curl "http://localhost:8000/api/v1/nodes/5"
```

#### 5. Get Node History Diff
Trace changes of a single node across all versions of the document (added, modified, unchanged, removed).
```bash
curl "http://localhost:8000/api/v1/nodes/5/diff"
```

### Versioning & Diff API

#### 6. Compare Document Versions
Generate a hierarchical diff tree comparing two versions of a document.
```bash
curl "http://localhost:8000/api/v1/documents/1/diff?v1=1&v2=2"
```

