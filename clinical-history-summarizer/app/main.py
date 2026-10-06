"""
FastAPI application entry point.

Run locally:
  uvicorn app.main:app --reload --port 8000

API docs available at:
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine
from app.db.models import Base  # ensures all models are registered
from app.routes.extract import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup if they don't exist (dev mode)."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Clinical History Summarizer API",
    description=(
        "AI-powered pipeline that extracts structured, source-verified clinical "
        "summaries from messy multi-source medical notes. "
        "Every claim is either cited to a specific line in the source text, "
        "or explicitly flagged as unverified."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (allow Next.js frontend dev server) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev
        "http://localhost:8501",   # Streamlit demo
        "*",                       # Open for demo — restrict before real deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["System"])
def root():
    return {
        "service": "Clinical History Summarizer",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
