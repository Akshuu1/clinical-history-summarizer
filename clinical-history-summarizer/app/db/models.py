"""
SQLAlchemy ORM models.

Tables:
  patients      — one row per patient ID (synthetic in this build)
  source_notes  — each raw text block uploaded for a patient
  summaries     — the verified ClinicalSummary JSON output, linked to a patient
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

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    source_notes = relationship("SourceNote", back_populates="patient")
    summaries = relationship("Summary", back_populates="patient")

    def __repr__(self) -> str:
        return f"<Patient patient_id={self.patient_id!r}>"


class SourceNote(Base):
    __tablename__ = "source_notes"

    id = Column(Integer, primary_key=True, index=True)
    patient_fk = Column(Integer, ForeignKey("patients.id"), nullable=False)
    source_label = Column(String(128), default="general")  # e.g. "ED admission"
    raw_text = Column(Text, nullable=False)
    normalised_lines = Column(JSON, nullable=False)  # list[str] — L1, L2, ...
    line_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="source_notes")
    summaries = relationship("Summary", back_populates="source_note")

    def __repr__(self) -> str:
        return f"<SourceNote id={self.id} label={self.source_label!r} lines={self.line_count}>"


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    patient_fk = Column(Integer, ForeignKey("patients.id"), nullable=False)
    source_note_fk = Column(Integer, ForeignKey("source_notes.id"), nullable=True)

    # The full verified ClinicalSummary stored as JSONB
    summary_json = Column(JSON, nullable=False)

    # Quick-access columns for dashboard queries (denormalised)
    chief_complaint = Column(Text, nullable=True)
    allergy_count = Column(Integer, default=0)
    medication_count = Column(Integer, default=0)
    unverified_field_count = Column(Integer, default=0)
    has_unverified = Column(Boolean, default=False)

    model_used = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="summaries")
    source_note = relationship("SourceNote", back_populates="summaries")

    def __repr__(self) -> str:
        return (
            f"<Summary id={self.id} patient={self.patient_fk} "
            f"unverified={self.unverified_field_count}>"
        )
