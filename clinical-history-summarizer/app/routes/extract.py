"""
API routes for the extraction pipeline.

  POST /extract-raw  — Stage 4: basic extraction, no citations (returns dict)
  POST /extract      — Stage 5: source-traced extraction with [Ln] citations.
                       Citation validation is automatic — built into the service.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.extractor import (
    extract_summary_raw,
    extract_summary_with_sources,
    ExtractionError,
)
from app.models.summary import ClinicalSummary

router = APIRouter()


class ExtractRequest(BaseModel):
    raw_notes: str
    patient_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no source tracing)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/extract-raw",
    summary="[Stage 4] Extract structured fields — no citations",
    tags=["Extraction"],
)
def extract_raw(request: ExtractRequest) -> dict:
    """
    Stage 4 endpoint. Sends raw notes to the LLM and returns a plain dict.
    No source tracing. Useful for comparison against the Stage 5 endpoint.
    """
    try:
        return extract_summary_raw(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Traced extraction (validation is automatic inside the service)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/extract",
    summary="[Stage 5] Extract with [Ln] citations + automatic validation",
    tags=["Extraction"],
    response_model=ClinicalSummary,
)
def extract_with_sources(request: ExtractRequest) -> ClinicalSummary:
    """
    Stage 5 endpoint.

    Internally: tags notes with [L1]...[Ln], calls the LLM with a citation
    requirement, parses into ClinicalSummary, then automatically runs
    validate_source_references() to independently check every cited line.

    Any field whose citation fails (bad line number, quoted_text not found
    in that line, or no source at all) is listed in `unverified_fields`
    and its source is set to null.
    """
    try:
        # Validation is wired inside extract_summary_with_sources.
        return extract_summary_with_sources(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
