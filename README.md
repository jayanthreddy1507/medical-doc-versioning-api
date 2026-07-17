# Medical Document Versioning & QA Traceability API

> A robust FastAPI backend that parses hierarchical documents (PDFs), tracks structural variations across versions, creates version-pinned node selections, generates QA test-case ideas via LLM, and detects active staleness when requirements change.

---

## Features

1. **OCR-based Structure Extractor**: Layout-aware parsing using font details (size/bold flags) to construct nested document trees, handling skipped levels, duplicate numbering, and out-of-order subsections.
2. **Version Matching Engine**: Hierarchical path-based and fuzzy-matching comparison classifying nodes as `added`, `removed`, `modified`, or `unchanged` with line-by-line unified diffs.
3. **Selection API**: Named, version-pinned groups of nodes that resolve to their original text even after newer document revisions are ingested.
4. **LLM Test Case Generation**: Generates 3-5 high-integrity QA test case ideas for selections with schema validation and self-repair loops.
5. **Staleness Tracking**: Automated detection verifying whether generated test cases match the latest version of the requirements.

---

## 🛠️ Quick Start & Setup

### 1. Prerequisite Environment
Ensure you have **Python 3.8+** installed.

```bash
# Clone the repository
git clone https://github.com/jayanthreddy1507/medical-doc-versioning-api.git
cd medical-doc-versioning-api

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables (Optional)
Configure variables in your terminal or a `.env` file in the root directory:
- `DATABASE_URL`: SQLAlchemy connection string (defaults to `sqlite+aiosqlite:///./data/document_versioning.db`).
- `GEMINI_API_KEY`: API Key for LLM-powered generation. If omitted, the system falls back to an offline mock generator (fully functional for testing the retry repair loop and caching policies).

### 3. Running the Server
```bash
uvicorn app.main:app --reload
```
Once running, the interactive Swagger documentation is available at: **http://localhost:8000/docs**.

---

## 🧪 Running Tests
The repository contains 47 unit and E2E integration tests validating all aspects of the architecture:

```bash
pytest -v --tb=short
```

---

## 🚀 Tracing the E2E Versioning & Staleness Flow

We provide a standalone demonstration script `demo_flow.py` that hits the live API endpoints to trace the complete ingestion, versioning, selection, generation, and staleness workflow.

### How to Run:
1. Ensure the FastAPI server is running in a terminal:
   ```bash
   uvicorn app.main:app --reload
   ```
2. In a second terminal (with your virtual environment active), run:
   ```bash
   python demo_flow.py
   ```

### What the script demonstrates:
1. **Ingests V1 Manual** (`data/ct200_manual_v1.pdf`).
2. **Locates Node ID** for `2.1.1.1 Electrode Specifications` (initial battery life threshold is 300 cycles).
3. **Creates Selection** pinned to that node ID.
4. **Generates QA Test Cases** (reports `is_stale = False`).
5. **Ingests V2 Manual** (`data/ct200_manual_v2.pdf`) which reduces battery cycles to 250.
6. **Performs Tree Diff** comparing V1 vs V2, identifying the modification and showing unified diff text.
7. **Queries Selection Generations** and detects that the generated test cases are now flagged as `is_stale = True`.
8. **Retrieves Generations by V2 Node ID**, tracing equivalents across document revisions.

---

## 📑 API Reference & Examples

### Ingestion API
#### 1. Ingest PDF Document
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@data/ct200_manual_v1.pdf"
```

### Browse & Diff API
#### 2. Get Document Diff
```bash
curl "http://localhost:8000/api/v1/documents/1/diff?v1=1&v2=2"
```
#### 3. Search Document
```bash
curl "http://localhost:8000/api/v1/documents/1/search?q=cuff&version=1"
```
#### 4. Trace Node History
```bash
curl "http://localhost:8000/api/v1/nodes/5/diff"
```

### Selections & LLM API
#### 5. Create Selection
```bash
curl -X POST "http://localhost:8000/api/v1/selections" \
     -H "Content-Type: application/json" \
     -d '{"name": "Battery Specs", "node_ids": [5]}'
```
#### 6. Generate Test Cases
```bash
curl -X POST "http://localhost:8000/api/v1/selections/1/generate"
```
#### 7. Retrieve Generations with Staleness
```bash
curl "http://localhost:8000/api/v1/selections/1/generations"
```
