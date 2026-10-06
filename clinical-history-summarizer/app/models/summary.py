"""
Pydantic schemas for the Clinical History Summarizer pipeline.

`unverified_fields` holds the names of any field (e.g. "chief_complaint"
or "current_medications[1]") that could not be matched to a valid source
line in the original notes. Any field named here should be treated as
low-confidence by anyone reading the summary — it was returned by the LLM
but could not be independently verified against a specific line of text.
"""

from typing import List, Optional
from pydantic import BaseModel


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

    name: str
    """Drug name as it appears in the source notes (not normalised)."""

    dose: Optional[str] = None
    """
    Dose as stated in the notes (e.g. "500mg", "10 units").
    None if the dose was not mentioned or could not be extracted.
    """

    timing: Optional[str] = None
    """
    Dosing schedule or frequency (e.g. "twice daily", "PRN", "at night").
    None if not stated in the notes.
    """

    source: Optional[SourceReference] = None
    """
    Citation pointing to the line in the source document that mentions
    this medication. If None, this medication entry could not be traced
    to a specific source line and will be added to unverified_fields.
    """


class LabResult(BaseModel):
    """A single laboratory investigation result extracted from the notes."""

    test_name: str
    """Name of the test as it appears in the source (e.g. "Troponin I", "HbA1c")."""

    value: Optional[str] = None
    """
    Result value as a string to preserve units and qualifiers
    (e.g. "0.08 ng/mL", "7.9%", ">90 mL/min").
    None if only the test name was mentioned without a result.
    """

    date: Optional[str] = None
    """
    Date the test was performed or reported, as stated in the notes.
    None if not explicitly mentioned alongside this result.
    """

    source: Optional[SourceReference] = None
    """
    Citation pointing to the line in the source document that contains
    this result. If None, the entry could not be traced to a specific
    source line and will be added to unverified_fields.
    """


class ClinicalSummary(BaseModel):
    """
    The complete structured output of one extraction run.

    Every data field is paired with source citation(s). Any field that
    the LLM returned but that could not be validated against the source
    text is listed by name in `unverified_fields` and should be treated
    as low-confidence.
    """

    patient_id: str
    """Unique identifier for the patient this summary belongs to."""

    chief_complaint: Optional[str] = None
    """
    The primary reason for the visit or admission, in plain text.
    None if not clearly stated in the notes.
    """

    chief_complaint_source: Optional[SourceReference] = None
    """
    Citation for the line that states the chief complaint.
    If None and chief_complaint is set, "chief_complaint" will appear
    in unverified_fields.
    """

    active_problems: List[str] = []
    """
    List of active diagnoses or clinical problems identified in the notes
    (e.g. ["Type 2 Diabetes Mellitus", "Hypertension"]).
    """

    active_problems_sources: List[SourceReference] = []
    """
    One SourceReference per entry in active_problems, in the same order.
    If the lengths differ, unmatched problems are added to unverified_fields.
    """

    current_medications: List[MedicationItem] = []
    """
    All medications currently prescribed or taken, each with optional
    dose, timing, and a source citation embedded in the MedicationItem.
    """

    recent_labs: List[LabResult] = []
    """
    Recent laboratory results mentioned in the notes, each with optional
    value, date, and source citation embedded in the LabResult.
    """

    allergies: List[str] = []
    """
    List of documented allergens (e.g. ["Penicillin", "Contrast dye"]).
    Reactions are not separated here — see allergies_sources for context.
    """

    allergies_sources: List[SourceReference] = []
    """
    One SourceReference per entry in allergies, in the same order.
    If the lengths differ, unmatched allergens are added to unverified_fields.
    """

    pending_items: List[str] = []
    """
    Tests, referrals, or actions documented as pending or outstanding
    (e.g. ["Repeat Troponin at 3h", "Cardiology consult requested"]).
    No source citations are tracked for pending items in this version.
    """

    unverified_fields: List[str] = []
    """
    Names of fields whose values could not be matched to a valid source line.
    Examples: "chief_complaint", "current_medications[1]", "allergies[0]".
    Consumers of this summary should treat these entries as low-confidence
    and not act on them without independent verification.
    """
