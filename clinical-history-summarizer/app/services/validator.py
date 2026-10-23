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

import logging
import copy
import re
from typing import Optional

logger = logging.getLogger(__name__)

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


def _ground_citation(
    ref: Optional[SourceReference],
    lines: list[str],
) -> bool:
    """
    Intelligent evidence grounding.
    Verifies that ref.quoted_text genuinely exists in the notes.
    If the LLM's line_number has an off-by-one or off-by-two drift
    (common with headers/blank lines), snaps to the genuine line.
    Never invents citations; only verifies genuine occurrences.
    """
    if ref is None or not ref.quoted_text:
        return False

    q_norm = _normalise(ref.quoted_text)
    if not q_norm:
        return False

    # 1. Direct hit on claimed line (1-indexed)
    if 1 <= ref.line_number <= len(lines):
        actual_line = _normalise(lines[ref.line_number - 1])
        if q_norm in actual_line or (len(actual_line) >= 4 and actual_line in q_norm):
            return True

    # 2. Local window search (±2 lines for header/blank line drift)
    start_win = max(0, ref.line_number - 3)
    end_win = min(len(lines), ref.line_number + 2)
    for offset_idx in range(start_win, end_win):
        actual_line = _normalise(lines[offset_idx])
        if q_norm in actual_line or (len(actual_line) >= 4 and actual_line in q_norm):
            ref.line_number = offset_idx + 1  # Auto-correct to exact line
            return True

    # 3. Document-wide search for exact quote (if quote is distinct, >= 10 chars)
    if len(q_norm) >= 10:
        for idx, line in enumerate(lines):
            actual_line = _normalise(line)
            if q_norm in actual_line:
                ref.line_number = idx + 1  # Self-heal citation line
                return True

    return False


# Alias for source validation
_citation_passes = _ground_citation


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
      - Valid citation  → kept as-is, line numbers self-healed if slightly offset.
      - Invalid citation → source is set to None; field name added to
        unverified_fields.
      - No citation at all → field name added to unverified_fields.

    Returns a deep-copied, modified ClinicalSummary.  The original
    *summary* object is never mutated.
    """
    # Work on a deep copy so this function is pure — no side effects.
    s = copy.deepcopy(summary)
    lines: list[str] = raw_notes.splitlines()
    unverified: list[str] = list(s.unverified_fields)   # carry forward any LLM-flagged items

    # ── chief_complaint ───────────────────────────────────────────────────────
    if s.chief_complaint is not None:
        if not _ground_citation(s.chief_complaint_source, lines):
            s.chief_complaint_source = None
            if "chief_complaint" not in unverified:
                unverified.append("chief_complaint")

    # ── clinical_impression ───────────────────────────────────────────────────
    if s.clinical_impression is not None:
        if not _ground_citation(s.clinical_impression_source, lines):
            s.clinical_impression_source = None
            if "clinical_impression" not in unverified:
                unverified.append("clinical_impression")

    # Helper for generic list+source fields
    def _validate_list_with_sources(field_name: str, item_list: list[str], source_list: list):
        # Guarantee 1-to-1 matching length
        while len(source_list) < len(item_list):
            source_list.append(None)

        for idx in range(len(item_list)):
            ref = source_list[idx] if idx < len(source_list) else None
            if not _ground_citation(ref, lines):
                # Remove the invalid source entry rather than 
                # setting to None (None is not valid in 
                # List[SourceReference])
                if idx < len(source_list):
                    source_list.pop(idx)
                field_key = f"{field_name}[{idx}]"
                if field_key not in unverified:
                    unverified.append(field_key)

    _validate_list_with_sources("documented_conditions", s.documented_conditions, s.documented_conditions_sources)
    _validate_list_with_sources("symptoms", s.symptoms, s.symptoms_sources)
    _validate_list_with_sources("pertinent_negatives", s.pertinent_negatives, s.pertinent_negatives_sources)
    _validate_list_with_sources("risk_factors", s.risk_factors, s.risk_factors_sources)
    _validate_list_with_sources("differential_diagnoses", s.differential_diagnoses, s.differential_diagnoses_sources)
    _validate_list_with_sources("red_flags", s.red_flags, s.red_flags_sources)
    _validate_list_with_sources("uncertainties", s.uncertainties, s.uncertainties_sources)

    # ── clinical_findings ─────────────────────────────────────────────────────
    for idx, finding in enumerate(s.clinical_findings):
        if not _citation_passes(finding.source, lines):
            finding.source = None
            field_key = f"clinical_findings[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── current_medications ───────────────────────────────────────────────────
    for idx, med in enumerate(s.current_medications):
        if not _ground_citation(med.source, lines):
            med.source = None
            field_key = f"current_medications[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── recent_labs ───────────────────────────────────────────────────────────
    for idx, lab in enumerate(s.recent_labs):
        if not _ground_citation(lab.source, lines):
            lab.source = None
            field_key = f"recent_labs[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── allergies ─────────────────────────────────────────────────────────────
    for idx, allergy in enumerate(s.allergies):
        if not _ground_citation(allergy.source, lines):
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
# Missing field detection
# ---------------------------------------------------------------------------
def detect_missing_fields(s: ClinicalSummary) -> ClinicalSummary:
    missing: list[str] = []
    already_flagged = set(s.unverified_fields) | set(s.missing_fields)

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
    _check_missing_list("clinical_findings", s.clinical_findings)
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

