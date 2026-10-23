"""
Pydantic schemas for the Clinical History Summarizer pipeline.

`unverified_fields` holds the names of any field (e.g. "chief_complaint"
or "current_medications[1]") that could not be matched to a valid source
line in the original notes. Any field named here should be treated as
low-confidence by anyone reading the summary — it was returned by the LLM
but could not be independently verified against a specific line of text.

`missing_fields` holds the names of core fields that appear to be entirely
absent from the notes — nothing resembling that category was written by the
doctor. This is distinct from unverified_fields: unverified means "found
but couldn't confirm"; missing means "not present in the source at all".

`raw_extra_fields` captures any meaningful content the doctor wrote that
does not map to one of the standard schema fields (e.g. diet advice,
lifestyle instructions, referral details beyond a simple task).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SourceReference(BaseModel):
    """Points to the exact location in a source document that supports a claim."""

    document_id: str
    """
    Identifier for the source document this reference points to.
    For single-document inputs this will be a constant like "note_1";
    for multi-document inputs it distinguishes which uploaded file
    the claim was found in.
    """

    line_number: int
    """
    1-indexed line number within the identified document.
    The validator checks that this line actually exists and contains
    the quoted_text before accepting the reference as verified.
    """

    quoted_text: str
    """
    Verbatim text copied from that line in the source document.
    Must be an exact substring of the line at line_number — the validator
    rejects any reference where this text cannot be found at that position.
    """


class MedicationItem(BaseModel):
    """A single medication entry extracted from the clinical notes."""
    drug: str
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    prn_status: Optional[str] = Field(default="Scheduled", description="'Scheduled', 'PRN', or 'Unclear'")
    status: Optional[str] = Field(default="Current", description="'Current', 'Newly prescribed', 'Discontinued', 'Reported by patient', or 'Unclear'")
    duration: Optional[str] = Field(default="Duration not specified", description="Duration if documented, else 'Duration not specified'")
    missing_information: Optional[str] = None
    uncertainty: Optional[str] = None
    source: Optional[SourceReference] = None


class AllergyItem(BaseModel):
    """A single allergy entry extracted from the clinical notes."""
    allergen: Optional[str] = None
    reaction: Optional[str] = None
    status: Optional[str] = None
    source: Optional[SourceReference] = None


class LabResult(BaseModel):
    """A single laboratory investigation result extracted from the notes."""
    test_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    date: Optional[str] = None
    abnormality: Optional[str] = None
    source: Optional[SourceReference] = None

    @field_validator("value", "unit", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        if v is not None:
            return str(v)
        return None


class ClinicalFinding(BaseModel):
    finding: str
    finding_type: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    source: Optional[SourceReference] = None

    @field_validator("value", "unit", "finding_type", mode="before")
    @classmethod
    def coerce_to_str(cls, v: Any) -> Optional[str]:
        if v is not None:
            return str(v)
        return None


class AIRecommendation(BaseModel):
    recommendation: str
    reason: Optional[str] = None
    priority: Optional[str] = None  
    prescription_status: str = "Not documented as prescribed"
    timing: Optional[str] = None
    caveat: Optional[str] = None


# Alias for backward compatibility
StructuredRecommendation = AIRecommendation


class ClinicalSummary(BaseModel):
    patient_id: str
    chief_complaint: Optional[str] = None
    chief_complaint_source: Optional[SourceReference] = None

    documented_conditions: List[str] = []
    documented_conditions_sources: List[SourceReference] = []

    symptoms: List[str] = []
    symptoms_sources: List[SourceReference] = []

    clinical_findings: List[ClinicalFinding] = []

    pertinent_negatives: List[str] = []
    pertinent_negatives_sources: List[SourceReference] = []

    risk_factors: List[str] = []
    risk_factors_sources: List[SourceReference] = []

    current_medications: List[MedicationItem] = []
    allergies: List[AllergyItem] = []
    recent_labs: List[LabResult] = []

    clinical_impression: Optional[str] = None
    clinical_impression_source: Optional[SourceReference] = None

    differential_diagnoses: List[str] = []
    differential_diagnoses_sources: List[SourceReference] = []

    pending_items: List[str] = []
    
    red_flags: List[str] = []
    red_flags_sources: List[SourceReference] = []

    uncertainties: List[str] = []
    uncertainties_sources: List[SourceReference] = []

    unverified_fields: List[str] = []
    """
    Names of fields whose values could not be matched to a valid source line.
    """

    missing_fields: List[str] = []
    """
    Names of core fields that appear to be entirely absent from the notes.
    """

    raw_extra_fields: Dict[str, Any] = Field(default_factory=dict)
    """
    Anything meaningful the doctor wrote that does not map to a standard schema field.
    """

    narrative_summary: Optional[str] = None
    """
    AI-generated plain-English synthesis of the entire clinical encounter.
    """

    next_steps: List[str] = []
    """
    List of AI-suggested recommendations (formatted strings).
    """

    ai_recommendations: List[AIRecommendation] = []
    """
    Structured AI-generated suggestions. These are clearly labeled
    as AI-generated and not prescribed by the doctor. Always shown
    separately from doctor_recommendations. Never treat these as
    clinical instructions.
    """

    doctor_recommendations: List[str] = []
    """
    All explicit recommendations, prescriptions, and instructions documented
    by the doctor — extracted verbatim from plan/management sections.
    Preserves exact intent, dosage, and follow-up without adding AI suggestions.
    """

