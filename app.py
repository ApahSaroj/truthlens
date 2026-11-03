"""Run with: uvicorn app:app --reload

Serves the TruthLens India API (GET /health, POST /check, POST /check/file) plus the
original generic POST /analyze endpoint.
"""
from api.routes import router as legacy_router
from truthlens.api import app

app.include_router(legacy_router)
