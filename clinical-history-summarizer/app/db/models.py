"""
SQLAlchemy ORM models — Stage 6.

Tables:
  patients      — one row per patient ID (synthetic in this build)
  source_notes  — each raw text block uploaded/submitted for a patient
  summaries     — the validated ClinicalSummary JSON output, linked to
                  a patient and optionally to a specific source_note.
                  Includes verified_count / unverified_count for fast
                  dashboard queries without deserialising summary_json.
"""

from __future__ import annotations

import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import relationship
from .database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(64), primary_key=True, index=True)
    """
    Patient identifier — used as-is from the request (e.g. 'case_7').
    String PK so it matches the patient_id field in ClinicalSummary
    directly, with no numeric surrogate key needed.
    """

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    source_notes = relationship("SourceNote", back_populates="patient")
    summaries    = relationship("Summary", back_populates="patient")

    def __repr__(self) -> str:
        return f"<Patient id={self.id!r}>"


class SourceNote(Base):
    __tablename__ = "source_notes"

    id         = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    raw_text   = Column(Text, nullable=False)
    """The exact raw note text as submitted, before any pre-processing."""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    patient   = relationship("Patient", back_populates="source_notes")
    summaries = relationship("Summary", back_populates="source_note")

    def __repr__(self) -> str:
        return f"<SourceNote id={self.id} patient={self.patient_id!r}>"


class Summary(Base):
    __tablename__ = "summaries"

    id             = Column(Integer, primary_key=True, index=True)
    patient_id     = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    source_note_id = Column(Integer, ForeignKey("source_notes.id"), nullable=True)

    # Full validated ClinicalSummary stored as JSONB
    summary_json   = Column(JSON, nullable=False)
    """
    The complete ClinicalSummary Pydantic model serialised to JSON.
    Contains all fields, source references, and unverified_fields list.
    """

    # Denormalised stats — kept in sync with summary_json for fast queries
    verified_count   = Column(Integer, nullable=False, default=0)
    unverified_count = Column(Integer, nullable=False, default=0)

    model_used = Column(String(128), nullable=True)
    """Name of the LLM model used for this extraction run."""

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    patient     = relationship("Patient", back_populates="summaries")
    source_note = relationship("SourceNote", back_populates="summaries")

    def __repr__(self) -> str:
        return (
            f"<Summary id={self.id} patient={self.patient_id!r} "
            f"verified={self.verified_count} unverified={self.unverified_count}>"
        )
