"""
Pydantic schemas for the ClinicalSummary pipeline.

Every data-bearing field carries a SourceReference so the API response
always tells the consumer *where* in the original notes a claim came from.
Fields that could not be validated are collected in `unverified_fields`.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """Points back to an exact line in the normalised source text."""
    source_line: int = Field(..., description="1-indexed line number in the normalised note")
    source_text: str = Field(..., description="Verbatim text from that line confirming the claim")


class ChiefComplaint(SourceReference):
    value: str


class ActiveProblem(SourceReference):
    value: str


class MedicationItem(SourceReference):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None


class LabResult(SourceReference):
    test: str
    result: str
    date: Optional[str] = None
    unit: Optional[str] = None
    flag: Optional[str] = None  # e.g. "HIGH", "LOW", "CRITICAL"


class AllergyItem(SourceReference):
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None  # e.g. "mild", "anaphylaxis"


class PendingItem(SourceReference):
    value: str


class ClinicalSummary(BaseModel):
    """
    The core output schema of the extraction pipeline.
    
    After LLM extraction, the validator checks every SourceReference.
    Any field whose citation fails validation is moved to `unverified_fields`
    and its original data is preserved in `unverified_data`.
    """
    patient_id: str
    chief_complaint: Optional[ChiefComplaint] = None
    active_problems: list[ActiveProblem] = Field(default_factory=list)
    current_medications: list[MedicationItem] = Field(default_factory=list)
    allergies: list[AllergyItem] = Field(default_factory=list)
    recent_labs: list[LabResult] = Field(default_factory=list)
    pending_items: list[PendingItem] = Field(default_factory=list)

    # ── Safety fields ──────────────────────────────────────────────────────────
    unverified_fields: list[str] = Field(
        default_factory=list,
        description="Field names whose LLM citations could not be validated. "
                    "Data in these fields should be treated as unconfirmed.",
    )
    unverified_data: dict = Field(
        default_factory=dict,
        description="Raw LLM output for unverified fields, preserved for audit.",
    )

    # ── Meta ───────────────────────────────────────────────────────────────────
    total_source_lines: int = 0
    model_used: str = ""
    extraction_version: str = "1.0"


class ExtractionRequest(BaseModel):
    """Payload sent to /extract."""
    patient_id: str = Field(..., description="Unique ID for this patient (can be synthetic)")
    notes: str = Field(..., description="Raw multi-source clinical notes, pasted as plain text")
    source_label: Optional[str] = Field(
        default="general",
        description="Optional label for the note source (e.g. 'ED admission', 'lab report')"
    )


class ExtractionResponse(BaseModel):
    """Response from /extract."""
    patient_id: str
    summary: ClinicalSummary
    raw_normalised_lines: list[str]
    warnings: list[str] = Field(default_factory=list)
