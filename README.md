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
