"""
API routes for the extraction pipeline — Stage 6.2.

  POST /extract-raw           — Stage 4: basic extraction, no citations (returns dict).
                                Kept for comparison/debugging. No DB writes.

  POST /extract               — Stage 5+6: source-traced extraction, citation validation,
                                summary_stats, AND persistent storage.

  GET  /summary/{patient_id}  — Returns the most recently stored Summary for a patient.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import crud
from app.services.extractor import (
    extract_summary_raw,
    extract_summary_with_sources,
    ExtractionError,
    MODEL,
)
from app.models.summary import ClinicalSummary

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    raw_notes: str = Field(..., description="Raw clinical notes text to extract from.")
    patient_id: str = Field(..., description="Unique identifier for this patient.")


class SummaryStats(BaseModel):
    """High-level counts of extractable, citable fields in the summary."""
    total_fields_extracted: int = Field(
        ..., description="Total discrete facts extracted (cited or not)."
    )
    verified_count: int = Field(
        ..., description="Fields with a valid, confirmed citation."
    )
    unverified_count: int = Field(
        ..., description="Fields missing a valid citation."
    )


class ExtractResponse(BaseModel):
    """Full Stage 5 response: validated summary + stats + storage metadata."""
    summary: ClinicalSummary
    summary_stats: SummaryStats
    stored_summary_id: int = Field(
        ..., description="DB row ID of the persisted Summary. Use with GET /summary/{patient_id}."
    )


class StoredSummaryResponse(BaseModel):
    """Response for GET /summary/{patient_id}."""
    summary_id: int
    patient_id: str
    model_used: str | None
    verified_count: int
    unverified_count: int
    created_at: str
    summary: ClinicalSummary


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_stats(summary: ClinicalSummary) -> SummaryStats:
    """
    Count total extractable, citable fields vs. those flagged as unverified.

    Each discrete fact counts as 1:
      chief_complaint (if present) + len(active_problems)
      + len(current_medications) + len(recent_labs) + len(allergies)

    pending_items are excluded — no citations tracked for them by design.
    """
    total = 0
    if summary.chief_complaint is not None:
        total += 1
    total += len(summary.active_problems)
    total += len(summary.current_medications)
    total += len(summary.recent_labs)
    total += len(summary.allergies)

    unverified = min(len(summary.unverified_fields), total)
    return SummaryStats(
        total_fields_extracted=total,
        verified_count=total - unverified,
        unverified_count=unverified,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no tracing, no DB writes)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/extract-raw",
    summary="[Stage 4] Extract structured fields — no citations, no storage",
    tags=["Extraction"],
)
def extract_raw(request: ExtractRequest) -> dict:
    """
    Stage 4 endpoint. Sends raw notes to the LLM and returns a plain dict.
    No source tracing, no citation validation, no DB writes.
    Kept for comparison and debugging against /extract.
    """
    try:
        return extract_summary_raw(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5+6 — Traced extraction + validation + persistent storage
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/extract",
    summary="[Stage 5+6] Extract with citations, validation, and DB storage",
    tags=["Extraction"],
    response_model=ExtractResponse,
)
def extract_with_sources(
    request: ExtractRequest,
    db: Session = Depends(get_db),
) -> ExtractResponse:
    """
    Main production endpoint.

    Pipeline:
      1. Pre-process: tag each line [L1], [L2], ...
      2. Call LLM demanding verbatim citations for every field.
      3. Parse response into a ClinicalSummary Pydantic model.
      4. Independently validate every citation against the raw notes.
      5. Compute summary_stats.
      6. Persist to DB:
           a. get_or_create Patient row for patient_id
           b. save SourceNote (raw_notes stored verbatim, NOT logged)
           c. save Summary (summary_json, verified_count, unverified_count)
      7. Return ExtractResponse with summary, stats, and stored_summary_id.

    The DB session is managed by FastAPI's Depends(get_db) and is
    always closed after the request — even on error.
    """
    # ── 1–4. Extraction + validation (validation is auto-wired inside) ────────
    try:
        summary = extract_summary_with_sources(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # ── 5. Compute stats ──────────────────────────────────────────────────────
    stats = _compute_stats(summary)

    # ── 6. Persist to DB (single transaction) ────────────────────────────────
    try:
        crud.get_or_create_patient(db, patient_id=request.patient_id)

        note = crud.save_source_note(
            db,
            patient_id=request.patient_id,
            raw_text=request.raw_notes,   # stored, but never logged
        )

        db_summary = crud.save_summary(
            db,
            patient_id=request.patient_id,
            source_note_id=note.id,
            summary_dict=summary.model_dump(mode="json"),
            verified_count=stats.verified_count,
            unverified_count=stats.unverified_count,
            model_used=MODEL,
        )

        db.commit()
        logger.info(
            "Stored summary id=%d patient=%r verified=%d unverified=%d",
            db_summary.id,
            request.patient_id,
            stats.verified_count,
            stats.unverified_count,
        )
    except Exception as exc:
        db.rollback()
        logger.error("DB write failed for patient=%r: %s", request.patient_id, exc)
        raise HTTPException(status_code=500, detail=f"Storage failed: {exc}")

    return ExtractResponse(
        summary=summary,
        summary_stats=stats,
        stored_summary_id=db_summary.id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /summary/{patient_id} — retrieve most recent stored summary
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/summary/{patient_id}",
    summary="Retrieve the most recent stored summary for a patient",
    tags=["Storage"],
    response_model=StoredSummaryResponse,
)
def get_summary(
    patient_id: str,
    db: Session = Depends(get_db),
) -> StoredSummaryResponse:
    """
    Returns the most recent Summary row stored for *patient_id*.

    The response includes the full ClinicalSummary (deserialized from
    summary_json), the verified/unverified counts, and metadata about
    when and with which model the summary was generated.

    Returns 404 if no summary exists for the given patient_id.
    """
    row = crud.get_latest_summary(db, patient_id=patient_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No summary found for patient '{patient_id}'. "
                   "Call POST /extract first.",
        )

    return StoredSummaryResponse(
        summary_id=row.id,
        patient_id=row.patient_id,
        model_used=row.model_used,
        verified_count=row.verified_count,
        unverified_count=row.unverified_count,
        created_at=row.created_at.isoformat(),
        summary=ClinicalSummary(**row.summary_json),
    )
