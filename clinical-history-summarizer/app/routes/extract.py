"""
API Routes for the extraction pipeline.

Endpoints:
  POST /extract              — main endpoint: extract + validate + store + return
  GET  /summary/{patient_id} — retrieve stored summaries for a patient
  GET  /patients             — list all patient IDs in the DB
  POST /demo/schedule        — Phase 2 stub: returns a medicine schedule (no real delivery)
  GET  /health               — liveness check
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db, Patient, SourceNote, Summary
from app.models.summary import ExtractionRequest, ExtractionResponse, ClinicalSummary
from app.services.extractor import extract_summary_raw
from app.services.validator import validate_summary

router = APIRouter()


# ── POST /extract ──────────────────────────────────────────────────────────────

@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract and verify a clinical summary from raw notes",
    tags=["Extraction"],
)
async def extract(
    request: ExtractionRequest,
    db: Session = Depends(get_db),
):
    """
    Full pipeline:
    1. Normalise + number input lines
    2. LLM extraction (Gemini) → ClinicalSummary with citations
    3. Citation validation → unverified fields flagged
    4. Store patient, source note, and summary in PostgreSQL
    5. Return ExtractionResponse with side-by-side data
    """
    warnings: list[str] = []

    # Step 1 & 2: Extract (includes normalisation internally)
    try:
        raw_summary, normalised_lines = extract_summary_raw(
            patient_id=request.patient_id,
            raw_notes=request.notes,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM extraction failed: {exc}",
        )

    # Step 3: Validate citations
    verified_summary = validate_summary(raw_summary, normalised_lines)

    if verified_summary.unverified_fields:
        warnings.append(
            f"The following fields could not be source-verified and are flagged: "
            f"{', '.join(verified_summary.unverified_fields)}"
        )

    # Step 4: Persist to DB
    try:
        # Upsert patient
        patient = db.query(Patient).filter_by(patient_id=request.patient_id).first()
        if not patient:
            patient = Patient(patient_id=request.patient_id)
            db.add(patient)
            db.flush()

        # Store source note
        source_note = SourceNote(
            patient_fk=patient.id,
            source_label=request.source_label or "general",
            raw_text=request.notes,
            normalised_lines=normalised_lines,
            line_count=len(normalised_lines),
        )
        db.add(source_note)
        db.flush()

        # Store summary
        summary_row = Summary(
            patient_fk=patient.id,
            source_note_fk=source_note.id,
            summary_json=verified_summary.model_dump(),
            chief_complaint=(
                verified_summary.chief_complaint.value
                if verified_summary.chief_complaint
                else None
            ),
            allergy_count=len(verified_summary.allergies),
            medication_count=len(verified_summary.current_medications),
            unverified_field_count=len(verified_summary.unverified_fields),
            has_unverified=bool(verified_summary.unverified_fields),
            model_used=verified_summary.model_used,
        )
        db.add(summary_row)
        db.commit()

    except Exception as exc:
        db.rollback()
        # Don't fail the whole request over a storage error — return the result with a warning
        warnings.append(f"Storage warning: could not persist to DB — {exc}")

    return ExtractionResponse(
        patient_id=request.patient_id,
        summary=verified_summary,
        raw_normalised_lines=normalised_lines,
        warnings=warnings,
    )


# ── GET /summary/{patient_id} ─────────────────────────────────────────────────

@router.get(
    "/summary/{patient_id}",
    summary="Get all stored summaries for a patient",
    tags=["Retrieval"],
)
def get_summaries(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(patient_id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")

    summaries = (
        db.query(Summary)
        .filter_by(patient_fk=patient.id)
        .order_by(Summary.created_at.desc())
        .all()
    )
    return {
        "patient_id": patient_id,
        "summary_count": len(summaries),
        "summaries": [s.summary_json for s in summaries],
    }


# ── GET /patients ──────────────────────────────────────────────────────────────

@router.get(
    "/patients",
    summary="List all patient IDs",
    tags=["Retrieval"],
)
def list_patients(db: Session = Depends(get_db)):
    patients = db.query(Patient).order_by(Patient.created_at.desc()).all()
    return {"patients": [p.patient_id for p in patients], "count": len(patients)}


# ── POST /demo/schedule (Phase 2 stub) ───────────────────────────────────────

@router.post(
    "/demo/schedule",
    summary="[STUB] Generate a medicine schedule from extracted medications",
    tags=["Demo / Phase 2"],
)
def demo_schedule(patient_id: str, db: Session = Depends(get_db)):
    """
    Phase 2 stub — shows how the prescription→schedule pipeline would work.
    Does NOT send real WhatsApp messages.
    Returns a mock schedule for demonstration purposes only.
    """
    patient = db.query(Patient).filter_by(patient_id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")

    latest = (
        db.query(Summary)
        .filter_by(patient_fk=patient.id)
        .order_by(Summary.created_at.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No summary found for patient")

    meds = latest.summary_json.get("current_medications", [])
    schedule = []
    for med in meds:
        schedule.append({
            "medication": med.get("name"),
            "dose": med.get("dose"),
            "frequency": med.get("frequency"),
            "reminder_times": ["08:00", "14:00", "20:00"],  # stub values
            "whatsapp_delivery": "NOT IMPLEMENTED — Phase 2 stub only",
        })

    return {
        "patient_id": patient_id,
        "schedule": schedule,
        "note": "This is a Phase 2 stub. No messages are sent. Real WhatsApp delivery is documented in README Phase 2.",
    }


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "clinical-history-summarizer"}
