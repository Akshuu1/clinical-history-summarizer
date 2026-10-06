"""
API routes for the extraction pipeline.

  POST /extract-raw        — Stage 4: basic extraction, no citations, no DB.
  POST /extract            — Stage 5+6: cited + validated + stored.
                             ?mode=clinical (default) | ?mode=patient
                             patient mode adds `patient_friendly_summary` to response.
  POST /extract-two-stage  — Stage 7: schema-free two-step extraction.
                             Populates raw_extra_fields for non-standard content.
  GET  /summary/{id}       — Most recent stored summary for a patient.
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import crud
from app.services.extractor import (
    extract_summary_raw,
    extract_summary_with_sources,
    extract_summary_two_stage,
    generate_patient_friendly_summary,
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
    raw_notes: str = Field(..., description="Raw clinical notes text.")
    patient_id: str = Field(..., description="Unique identifier for this patient.")


class SummaryStats(BaseModel):
    total_fields_extracted: int
    verified_count: int
    unverified_count: int
    missing_count: int = Field(
        0, description="Fields not mentioned in the notes at all."
    )


class ExtractResponse(BaseModel):
    summary: ClinicalSummary
    summary_stats: SummaryStats
    stored_summary_id: int
    patient_friendly_summary: Optional[str] = Field(
        None,
        description="Plain-language rewrite for the patient. "
                    "Only present when ?mode=patient is set. "
                    "Contains only verified fields — unverified fields are silently omitted.",
    )


class StoredSummaryResponse(BaseModel):
    summary_id: int
    patient_id: str
    model_used: Optional[str]
    verified_count: int
    unverified_count: int
    created_at: str
    summary: ClinicalSummary


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_stats(summary: ClinicalSummary) -> SummaryStats:
    """
    Count total extractable, citable fields vs. verified vs. unverified.

    Citable facts:
      chief_complaint (1 if present) + active_problems + current_medications
      + recent_labs + allergies

    pending_items and raw_extra_fields are excluded (no citations tracked).
    """
    total = 0
    if summary.chief_complaint is not None:
        total += 1
    if summary.clinical_impression is not None:
        total += 1
    total += len(summary.documented_conditions)
    total += len(summary.symptoms)
    total += len(summary.clinical_findings)
    total += len(summary.pertinent_negatives)
    total += len(summary.risk_factors)
    total += len(summary.differential_diagnoses)
    total += len(summary.red_flags)
    total += len(summary.uncertainties)
    total += len(summary.current_medications)
    total += len(summary.recent_labs)
    total += len(summary.allergies)

    unverified = min(len(summary.unverified_fields), total)
    return SummaryStats(
        total_fields_extracted=total,
        verified_count=total - unverified,
        unverified_count=unverified,
        missing_count=len(summary.missing_fields),
    )


def _persist(
    db: Session,
    patient_id: str,
    raw_notes: str,
    summary: ClinicalSummary,
    stats: SummaryStats,
) -> int:
    """Write Patient, SourceNote, Summary rows in a single transaction."""
    try:
        crud.get_or_create_patient(db, patient_id=patient_id)
        note = crud.save_source_note(db, patient_id=patient_id, raw_text=raw_notes)
        db_row = crud.save_summary(
            db,
            patient_id=patient_id,
            source_note_id=note.id,
            summary_dict=summary.model_dump(mode="json"),
            verified_count=stats.verified_count,
            unverified_count=stats.unverified_count,
            model_used=MODEL,
        )
        db.commit()
        logger.info(
            "Stored summary id=%d patient=%r verified=%d unverified=%d missing=%d",
            db_row.id, patient_id,
            stats.verified_count, stats.unverified_count, stats.missing_count,
        )
        return db_row.id
    except Exception as exc:
        db.rollback()
        logger.error("DB write failed for patient=%r: %s", patient_id, exc)
        raise HTTPException(status_code=500, detail=f"Storage failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no tracing, no DB)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/extract-raw",
    summary="[Stage 4] Extract structured fields — no citations, no storage",
    tags=["Extraction"],
)
def extract_raw(request: ExtractRequest) -> dict:
    """Stage 4: plain dict response, no source tracing, no DB writes."""
    try:
        return extract_summary_raw(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5+6 — Cited extraction + validation + storage
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/extract",
    summary="[Stage 5+6] Cited extraction, validation, storage — with optional patient mode",
    tags=["Extraction"],
    response_model=ExtractResponse,
)
def extract_with_sources(
    request: ExtractRequest,
    mode: Literal["clinical", "patient"] = Query(
        default="clinical",
        description=(
            "Output mode. "
            "'clinical' (default): structured JSON summary for clinical use. "
            "'patient': adds `patient_friendly_summary` — a plain-language rewrite "
            "of only the verified fields, suitable for handing to the patient. "
            "Unverified and missing fields are silently omitted from patient text."
        ),
    ),
    db: Session = Depends(get_db),
) -> ExtractResponse:
    """
    Main production endpoint.

    Pipeline:
      1. Tag lines [L1], [L2], ...
      2. LLM extraction with verbatim citation requirement.
      3. Parse into ClinicalSummary.
      4. Validate citations independently.
      5. Detect missing fields (fields not mentioned at all).
      6. Compute summary_stats.
      7. Persist to DB (Patient → SourceNote → Summary).
      8. [mode=patient only] Second LLM call rewrites verified fields
         into plain patient language — unverified/missing fields omitted.
    """
    # ── 1–5. Extract + validate ────────────────────────────────────────────
    try:
        summary = extract_summary_with_sources(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # ── 6. Stats ───────────────────────────────────────────────────────────
    stats = _compute_stats(summary)

    # ── 7. Persist ─────────────────────────────────────────────────────────
    stored_id = _persist(db, request.patient_id, request.raw_notes, summary, stats)

    # ── 8. Patient-friendly rewrite ────────────────────────────────────────
    patient_text: Optional[str] = None
    if mode == "patient":
        patient_text = generate_patient_friendly_summary(summary)

    return ExtractResponse(
        summary=summary,
        summary_stats=stats,
        stored_summary_id=stored_id,
        patient_friendly_summary=patient_text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 7 — Two-stage schema-free extraction
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/extract-two-stage",
    summary="[Stage 7] Schema-free two-step extraction — populates raw_extra_fields",
    tags=["Extraction"],
    response_model=ExtractResponse,
)
def extract_two_stage(
    request: ExtractRequest,
    mode: Literal["clinical", "patient"] = Query(default="clinical"),
    db: Session = Depends(get_db),
) -> ExtractResponse:
    """
    Two-stage pipeline:
      Stage 1 — Free-form: LLM identifies what sections exist in the notes
                           (no schema imposed).
      Stage 2 — Mapping:   LLM maps sections to standard fields where obvious.
                           Anything else goes into raw_extra_fields.

    Use this when the input format is unpredictable or when you want to
    capture non-standard content (diet advice, lifestyle instructions, etc.)
    alongside the standard clinical fields.
    """
    try:
        summary = extract_summary_two_stage(
            raw_notes=request.raw_notes,
            patient_id=request.patient_id,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    stats = _compute_stats(summary)
    stored_id = _persist(db, request.patient_id, request.raw_notes, summary, stats)

    patient_text = None
    if mode == "patient":
        patient_text = generate_patient_friendly_summary(summary)

    return ExtractResponse(
        summary=summary,
        summary_stats=stats,
        stored_summary_id=stored_id,
        patient_friendly_summary=patient_text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /summary/{patient_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/summary/{patient_id}",
    summary="Most recent stored summary for a patient",
    tags=["Storage"],
    response_model=StoredSummaryResponse,
)
def get_summary(
    patient_id: str,
    db: Session = Depends(get_db),
) -> StoredSummaryResponse:
    """
    Returns the most recent Summary row stored for patient_id.
    Returns 404 if no summaries have been stored yet.
    """
    row = crud.get_latest_summary(db, patient_id=patient_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No summary found for patient '{patient_id}'. Call POST /extract first.",
        )

    return StoredSummaryResponse(
        summary_id=row.id,
        patient_id=row.patient_id,
        model_used=row.model_used,
        verified_count=row.verified_count,
        unverified_count=row.unverified_count,
        created_at=row.created_at.isoformat(),
        summary=ClinicalSummary(**row.summary_json),  # type: ignore
    )
