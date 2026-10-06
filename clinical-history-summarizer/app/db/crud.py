"""
CRUD helpers for the storage layer — Stage 6.2.

All functions take an explicit SQLAlchemy Session and have no side
effects beyond the DB operations described. They never log raw note
content.
"""

from __future__ import annotations

import datetime
from sqlalchemy.orm import Session

from app.db.models import Patient, SourceNote, Summary


# ─────────────────────────────────────────────────────────────────────────────
# Patient
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_patient(db: Session, patient_id: str) -> Patient:
    """
    Return the Patient row for *patient_id*, creating it if it does not
    exist yet.  Uses a single round-trip when the patient already exists.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        patient = Patient(
            id=patient_id,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(patient)
        db.flush()   # assign PK without committing yet
    return patient


# ─────────────────────────────────────────────────────────────────────────────
# SourceNote
# ─────────────────────────────────────────────────────────────────────────────

def save_source_note(db: Session, patient_id: str, raw_text: str) -> SourceNote:
    """
    Persist the submitted raw notes text for *patient_id*.

    We store the raw_text exactly as received.  We deliberately do NOT
    log its contents anywhere in this function.
    """
    note = SourceNote(
        patient_id=patient_id,
        raw_text=raw_text,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(note)
    db.flush()   # populate note.id before linking to Summary
    return note


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def save_summary(
    db: Session,
    patient_id: str,
    source_note_id: int,
    summary_dict: dict,
    verified_count: int,
    unverified_count: int,
    model_used: str,
) -> Summary:
    """
    Persist the validated ClinicalSummary for *patient_id*.

    Args:
        db:               Active SQLAlchemy session.
        patient_id:       Patient identifier string.
        source_note_id:   FK to the SourceNote this summary was derived from.
        summary_dict:     ClinicalSummary serialised as a plain dict (no raw note text).
        verified_count:   Number of fields with confirmed citations.
        unverified_count: Number of fields missing or with invalid citations.
        model_used:       Identifier of the LLM model used for extraction.
    """
    summary = Summary(
        patient_id=patient_id,
        source_note_id=source_note_id,
        summary_json=summary_dict,
        verified_count=verified_count,
        unverified_count=unverified_count,
        model_used=model_used,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(summary)
    db.flush()
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_summary(db: Session, patient_id: str) -> Summary | None:
    """
    Return the most recent Summary row for *patient_id*, or None if no
    summaries have been stored for this patient yet.
    """
    return (
        db.query(Summary)
        .filter(Summary.patient_id == patient_id)
        .order_by(Summary.created_at.desc())
        .first()
    )
