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
from pydantic import BaseModel, Field


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
    status: Optional[str] = None
    uncertainty: Optional[str] = None
    source: Optional[SourceReference] = None


class AllergyItem(BaseModel):
    """A single allergy entry extracted from the clinical notes."""
    allergen: str
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


class ClinicalSummary(BaseModel):
    patient_id: str
    chief_complaint: Optional[str] = None
    chief_complaint_source: Optional[SourceReference] = None

    documented_conditions: List[str] = []
    documented_conditions_sources: List[SourceReference] = []

    symptoms: List[str] = []
    symptoms_sources: List[SourceReference] = []

    clinical_findings: List[str] = []
    clinical_findings_sources: List[SourceReference] = []

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
    Examples: "chief_complaint", "current_medications[1]", "allergies[0]".
    Consumers of this summary should treat these entries as low-confidence
    and not act on them without independent verification.
    """

    missing_fields: List[str] = []
    """
    Names of core fields that appear to be entirely absent from the notes.
    The doctor wrote nothing that could be interpreted as this category.

    Distinction from unverified_fields:
      - unverified_fields: LLM found something but citation couldn't be confirmed.
      - missing_fields:    Nothing resembling this category exists in the notes.

    Consumers should consider asking the patient directly or checking other
    records for fields listed here.
    """

    raw_extra_fields: Dict[str, Any] = Field(default_factory=dict)
    """
    Anything meaningful the doctor wrote that does not map to a standard
    schema field (e.g. "diet_advice", "lifestyle_instructions",
    "referral_details"). Keyed by short section label; values include
    the content text and optional citation.

    Populated only by the two-stage extraction pipeline
    (extract_summary_two_stage). Always empty in single-stage mode.
    """
