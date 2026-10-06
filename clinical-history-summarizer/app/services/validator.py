"""
Citation Validator — the core safety layer (Prompt 5.2).

This module verifies every SourceReference the LLM returns. It does NOT
trust the model's claims — it checks them independently against the raw
source text.

For every field that has a SourceReference, it:
  1. Looks up the actual text at that line_number in raw_notes.
  2. Checks if quoted_text is genuinely present in that line, using a
     normalised (lowercase, collapsed whitespace) substring match.
  3. If the check FAILS: nulls out that field's source and adds the
     field name to summary.unverified_fields.
  4. If a field has NO source at all (was None from the LLM): also adds
     it to unverified_fields.

The public function is:

    validate_source_references(summary: ClinicalSummary, raw_notes: str)
        -> ClinicalSummary

It is a pure function — it never mutates its inputs and has no side
effects, making it straightforward to unit-test independently.
"""

from __future__ import annotations

import copy
import re
from typing import Optional

from app.models.summary import (
    ClinicalSummary,
    MedicationItem,
    LabResult,
    SourceReference,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """
    Lowercase and collapse all whitespace runs to a single space.
    Used for tolerant-but-honest substring matching: the core claim must
    genuinely appear in the line, not just be thematically related.
    """
    return re.sub(r"\s+", " ", text.lower()).strip()


def _citation_passes(
    ref: Optional[SourceReference],
    lines: list[str],
) -> bool:
    """
    Return True iff ALL of the following hold:
      - ref is not None
      - ref.line_number is within bounds (1-indexed)
      - _normalise(ref.quoted_text) is a substring of _normalise(lines[ref.line_number - 1])

    If ANY condition fails, returns False.  The caller is responsible for
    nulling out the source and marking the field as unverified.
    """
    if ref is None:
        return False

    if ref.line_number < 1 or ref.line_number > len(lines):
        return False

    actual_line = lines[ref.line_number - 1]          # 0-indexed access
    return _normalise(ref.quoted_text) in _normalise(actual_line)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate_source_references(
    summary: ClinicalSummary,
    raw_notes: str,
) -> ClinicalSummary:
    """
    Verify every SourceReference in *summary* against *raw_notes*.

    For each field that carries a citation:
      - Valid citation  → kept as-is.
      - Invalid citation → source is set to None; field name added to
        unverified_fields.
      - No citation at all → field name added to unverified_fields.

    Returns a deep-copied, modified ClinicalSummary.  The original
    *summary* object is never mutated.

    Args:
        summary:   The ClinicalSummary returned by extract_summary_with_sources().
        raw_notes: The exact raw text that was originally sent to the LLM.

    Returns:
        A new ClinicalSummary with invalid / missing sources flagged.
    """
    # Work on a deep copy so this function is pure — no side effects.
    s = copy.deepcopy(summary)
    lines: list[str] = raw_notes.splitlines()
    unverified: list[str] = list(s.unverified_fields)   # carry forward any LLM-flagged items

    # ── chief_complaint ───────────────────────────────────────────────────────
    if s.chief_complaint is not None:
        if not _citation_passes(s.chief_complaint_source, lines):
            s.chief_complaint_source = None
            if "chief_complaint" not in unverified:
                unverified.append("chief_complaint")

    # ── clinical_impression ───────────────────────────────────────────────────
    if s.clinical_impression is not None:
        if not _citation_passes(s.clinical_impression_source, lines):
            s.clinical_impression_source = None
            if "clinical_impression" not in unverified:
                unverified.append("clinical_impression")

    # Helper for generic list+source fields
    def _validate_list_with_sources(field_name: str, item_list: list[str], source_list: list):
        for idx in range(len(item_list)):
            ref = source_list[idx] if idx < len(source_list) else None
            if not _citation_passes(ref, lines):
                if idx < len(source_list):
                    source_list[idx] = None
                field_key = f"{field_name}[{idx}]"
                if field_key not in unverified:
                    unverified.append(field_key)

    _validate_list_with_sources("documented_conditions", s.documented_conditions, s.documented_conditions_sources)
    _validate_list_with_sources("symptoms", s.symptoms, s.symptoms_sources)
    _validate_list_with_sources("clinical_findings", s.clinical_findings, s.clinical_findings_sources)
    _validate_list_with_sources("pertinent_negatives", s.pertinent_negatives, s.pertinent_negatives_sources)
    _validate_list_with_sources("risk_factors", s.risk_factors, s.risk_factors_sources)
    _validate_list_with_sources("differential_diagnoses", s.differential_diagnoses, s.differential_diagnoses_sources)
    _validate_list_with_sources("red_flags", s.red_flags, s.red_flags_sources)
    _validate_list_with_sources("uncertainties", s.uncertainties, s.uncertainties_sources)

    # ── current_medications ───────────────────────────────────────────────────
    for idx, med in enumerate(s.current_medications):
        if not _citation_passes(med.source, lines):
            med.source = None
            field_key = f"current_medications[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── recent_labs ───────────────────────────────────────────────────────────
    for idx, lab in enumerate(s.recent_labs):
        if not _citation_passes(lab.source, lines):
            lab.source = None
            field_key = f"recent_labs[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── allergies ─────────────────────────────────────────────────────────────
    for idx, allergy in enumerate(s.allergies):
        if not _citation_passes(allergy.source, lines):
            allergy.source = None
            field_key = f"allergies[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── pending_items ─────────────────────────────────────────────────────────
    # No source citations are tracked for pending items (by design).

    # Deduplicate while preserving insertion order
    s.unverified_fields = list(dict.fromkeys(unverified))

    # Detect fields entirely absent from the notes (separate from unverified)
    s = detect_missing_fields(s)

    return s


# ---------------------------------------------------------------------------
# Keep validate_summary as a thin alias so existing callers don't break
# ---------------------------------------------------------------------------
def validate_summary(
    summary: ClinicalSummary,
    normalised_lines: list[str],
) -> ClinicalSummary:
    raw_notes = "\n".join(normalised_lines)
    return validate_source_references(summary, raw_notes)


# ---------------------------------------------------------------------------
# Missing field detection
# ---------------------------------------------------------------------------
def detect_missing_fields(s: ClinicalSummary) -> ClinicalSummary:
    missing: list[str] = []
    already_flagged = set(s.unverified_fields)

    def _check_missing_single(field_name: str, val, source):
        if val is None and source is None and field_name not in already_flagged:
            missing.append(field_name)

    def _check_missing_list(field_name: str, item_list, source_list=None):
        if not item_list and (source_list is None or not source_list):
            if not any(f.startswith(field_name) for f in already_flagged):
                missing.append(field_name)

    _check_missing_single("chief_complaint", s.chief_complaint, s.chief_complaint_source)
    _check_missing_single("clinical_impression", s.clinical_impression, s.clinical_impression_source)
    
    _check_missing_list("documented_conditions", s.documented_conditions, s.documented_conditions_sources)
    _check_missing_list("symptoms", s.symptoms, s.symptoms_sources)
    _check_missing_list("clinical_findings", s.clinical_findings, s.clinical_findings_sources)
    _check_missing_list("pertinent_negatives", s.pertinent_negatives, s.pertinent_negatives_sources)
    _check_missing_list("risk_factors", s.risk_factors, s.risk_factors_sources)
    _check_missing_list("differential_diagnoses", s.differential_diagnoses, s.differential_diagnoses_sources)
    _check_missing_list("red_flags", s.red_flags, s.red_flags_sources)
    _check_missing_list("uncertainties", s.uncertainties, s.uncertainties_sources)
    
    _check_missing_list("current_medications", s.current_medications)
    _check_missing_list("recent_labs", s.recent_labs)
    _check_missing_list("allergies", s.allergies)

    s.missing_fields = missing
    return s

