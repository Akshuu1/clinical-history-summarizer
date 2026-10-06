"""
API routes for the extraction pipeline.

  POST /extract-raw  — Stage 4: basic extraction, no citations (returns dict).
                       Kept as-is for comparison/debugging.

  POST /extract      — Stage 5: source-traced extraction with [Ln] citations,
                       automatic citation validation, and summary_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.extractor import (
    extract_summary_raw,
    extract_summary_with_sources,
    ExtractionError,
)
from app.models.summary import ClinicalSummary

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    raw_notes: str = Field(..., description="Raw clinical notes text to extract from.")
    patient_id: str = Field(..., description="Unique identifier for this patient.")


class SummaryStats(BaseModel):
    """
    Counts of extractable fields in the returned ClinicalSummary.

    'extractable fields' are every discrete fact the system can cite:
      - chief_complaint (1 if present)
      - each active_problem
      - each current_medication
      - each recent_lab
      - each allergy

    pending_items are intentionally excluded — they carry no source
    citations by design (Prompt 2.1).
    """
    total_fields_extracted: int = Field(
        ...,
        description="Total number of discrete facts extracted (cited or not)."
    )
    verified_count: int = Field(
        ...,
        description="Number of fields with a valid, independently-confirmed citation."
    )
    unverified_count: int = Field(
        ...,
        description="Number of fields whose citation is missing or could not be confirmed."
    )


class ExtractResponse(BaseModel):
    """Full Stage 5 response: the validated summary plus high-level stats."""
    summary: ClinicalSummary
    summary_stats: SummaryStats


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_stats(summary: ClinicalSummary) -> SummaryStats:
    """
    Count total extractable fields vs. those flagged as unverified.

    Each discrete, citable fact counts as 1:
      - chief_complaint        → 1 if not None
      - active_problems        → len(list)
      - current_medications    → len(list)
      - recent_labs            → len(list)
      - allergies              → len(list)
    """
    total = 0

    # chief_complaint
    if summary.chief_complaint is not None:
        total += 1

    # list fields
    total += len(summary.active_problems)
    total += len(summary.current_medications)
    total += len(summary.recent_labs)
    total += len(summary.allergies)

    unverified = len(summary.unverified_fields)
    # Clamp: unverified can't exceed total (defensive guard)
    unverified = min(unverified, total)
    verified = total - unverified

    return SummaryStats(
        total_fields_extracted=total,
        verified_count=verified,
        unverified_count=unverified,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no source tracing) — kept as-is
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/extract-raw",
    summary="[Stage 4] Extract structured fields — no citations",
    tags=["Extraction"],
)
def extract_raw(request: ExtractRequest) -> dict:
    """
    Stage 4 endpoint. Sends raw notes to the LLM and returns a plain dict.
    No source tracing. Kept for comparison and debugging against /extract.
    """
    try:
        return extract_summary_raw(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Traced extraction + validation + summary_stats
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/extract",
    summary="[Stage 5] Extract with [Ln] citations, validation, and summary_stats",
    tags=["Extraction"],
    response_model=ExtractResponse,
)
def extract_with_sources(request: ExtractRequest) -> ExtractResponse:
    """
    Stage 5 endpoint — the main production endpoint.

    Pipeline:
      1. Pre-process notes: tag each line [L1], [L2], …
      2. Call LLM demanding verbatim citations for every field.
         Instruction: 'If you cannot point to a specific line, set source to null.'
      3. Parse response into ClinicalSummary Pydantic model.
      4. Independently validate every citation:
           - Is the line_number within bounds?
           - Is quoted_text a genuine substring of that line?
         Failures → source set to None + field added to unverified_fields.
      5. Compute summary_stats: total_fields_extracted, verified_count,
         unverified_count.

    Returns ExtractResponse containing the full validated ClinicalSummary
    and the summary_stats block.
    """
    try:
        summary = extract_summary_with_sources(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    stats = _compute_stats(summary)

    return ExtractResponse(summary=summary, summary_stats=stats)
