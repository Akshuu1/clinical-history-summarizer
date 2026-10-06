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

    # ── active_problems ───────────────────────────────────────────────────────
    for idx in range(len(s.active_problems)):
        # Source list may be shorter than the problems list
        ref = s.active_problems_sources[idx] if idx < len(s.active_problems_sources) else None
        if not _citation_passes(ref, lines):
            # Null out the source slot if it exists
            if idx < len(s.active_problems_sources):
                s.active_problems_sources[idx] = None   # type: ignore[assignment]
            field_key = f"active_problems[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── current_medications ───────────────────────────────────────────────────
    for idx, med in enumerate(s.current_medications):
        if not _citation_passes(med.source, lines):
            s.current_medications[idx] = MedicationItem(
                name=med.name,
                dose=med.dose,
                timing=med.timing,
                source=None,
            )
            field_key = f"current_medications[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── recent_labs ───────────────────────────────────────────────────────────
    for idx, lab in enumerate(s.recent_labs):
        if not _citation_passes(lab.source, lines):
            s.recent_labs[idx] = LabResult(
                test_name=lab.test_name,
                value=lab.value,
                date=lab.date,
                source=None,
            )
            field_key = f"recent_labs[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # ── allergies ─────────────────────────────────────────────────────────────
    for idx in range(len(s.allergies)):
        ref = s.allergies_sources[idx] if idx < len(s.allergies_sources) else None
        if not _citation_passes(ref, lines):
            if idx < len(s.allergies_sources):
                s.allergies_sources[idx] = None   # type: ignore[assignment]
            field_key = f"allergies[{idx}]"
            if field_key not in unverified:
                unverified.append(field_key)

    # If allergies is empty (NKDA), strip any orphan sources the LLM attached.
    # Keeping them would be misleading — they look like citations for allergens
    # that don't exist in the list.
    if not s.allergies:
        s.allergies_sources = []

    # ── pending_items ─────────────────────────────────────────────────────────
    # No source citations are tracked for pending items (by design — Prompt 2.1).

    # Deduplicate while preserving insertion order
    s.unverified_fields = list(dict.fromkeys(unverified))

    return s


# ---------------------------------------------------------------------------
# Keep validate_summary as a thin alias so existing callers don't break
# ---------------------------------------------------------------------------
def validate_summary(
    summary: ClinicalSummary,
    normalised_lines: list[str],
) -> ClinicalSummary:
    """
    Deprecated alias for validate_source_references().

    Accepts the old `normalised_lines: list[str]` signature for
    backwards-compatibility with the route layer.  Internally delegates
    to validate_source_references() by joining the lines.
    """
    raw_notes = "\n".join(normalised_lines)
    return validate_source_references(summary, raw_notes)
