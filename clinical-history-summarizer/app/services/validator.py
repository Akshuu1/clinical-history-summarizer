"""
Source Reference Validator — the core safety layer.

For every SourceReference the LLM returns, this module checks:
  1. The cited line number actually exists in the normalised lines list.
  2. The source_text the model claims appears at that line is a
     genuine substring of that line (case-insensitive, stripped).

If EITHER check fails, the field is added to `unverified_fields`.

This code does NOT trust the LLM. It does the check itself.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.summary import (
    ClinicalSummary,
    ActiveProblem,
    MedicationItem,
    LabResult,
    AllergyItem,
    PendingItem,
)


def _normalise_for_comparison(text: str) -> str:
    """Lowercase, collapse whitespace — for fuzzy-but-honest matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _citation_is_valid(
    source_line_no: int,
    source_text_claimed: str,
    normalised_lines: list[str],
) -> bool:
    """
    Returns True iff:
      - source_line_no is within bounds (1-indexed)
      - source_text_claimed is a substring of the actual line at that position
    """
    if source_line_no < 1 or source_line_no > len(normalised_lines):
        return False

    actual_line = normalised_lines[source_line_no - 1]  # convert to 0-indexed

    # Allow partial match: the claimed excerpt just has to appear inside the line
    claimed_norm = _normalise_for_comparison(source_text_claimed)
    actual_norm = _normalise_for_comparison(actual_line)

    return claimed_norm in actual_norm


def validate_summary(
    summary: ClinicalSummary,
    normalised_lines: list[str],
) -> ClinicalSummary:
    """
    Walk every cited field in the summary.
    - Valid citations: kept as-is.
    - Invalid citations: item removed from its list, field name added to
      `unverified_fields`, raw data preserved in `unverified_data`.

    Returns a new ClinicalSummary (the input is not mutated).
    """
    unverified_fields: list[str] = list(summary.unverified_fields)
    unverified_data: dict[str, Any] = dict(summary.unverified_data)

    # ── chief_complaint ────────────────────────────────────────────────────────
    chief_complaint = summary.chief_complaint
    if chief_complaint is not None:
        if not _citation_is_valid(
            chief_complaint.source_line,
            chief_complaint.source_text,
            normalised_lines,
        ):
            unverified_fields.append("chief_complaint")
            unverified_data["chief_complaint"] = chief_complaint.model_dump()
            chief_complaint = None

    # ── active_problems ────────────────────────────────────────────────────────
    valid_problems: list[ActiveProblem] = []
    bad_problems: list[dict] = []
    for item in summary.active_problems:
        if _citation_is_valid(item.source_line, item.source_text, normalised_lines):
            valid_problems.append(item)
        else:
            bad_problems.append(item.model_dump())
    if bad_problems:
        if "active_problems" not in unverified_fields:
            unverified_fields.append("active_problems")
        unverified_data["active_problems"] = bad_problems

    # ── current_medications ────────────────────────────────────────────────────
    valid_meds: list[MedicationItem] = []
    bad_meds: list[dict] = []
    for item in summary.current_medications:
        if _citation_is_valid(item.source_line, item.source_text, normalised_lines):
            valid_meds.append(item)
        else:
            bad_meds.append(item.model_dump())
    if bad_meds:
        if "current_medications" not in unverified_fields:
            unverified_fields.append("current_medications")
        unverified_data["current_medications"] = bad_meds

    # ── allergies ──────────────────────────────────────────────────────────────
    valid_allergies: list[AllergyItem] = []
    bad_allergies: list[dict] = []
    for item in summary.allergies:
        if _citation_is_valid(item.source_line, item.source_text, normalised_lines):
            valid_allergies.append(item)
        else:
            bad_allergies.append(item.model_dump())
    if bad_allergies:
        if "allergies" not in unverified_fields:
            unverified_fields.append("allergies")
        unverified_data["allergies"] = bad_allergies

    # ── recent_labs ────────────────────────────────────────────────────────────
    valid_labs: list[LabResult] = []
    bad_labs: list[dict] = []
    for item in summary.recent_labs:
        if _citation_is_valid(item.source_line, item.source_text, normalised_lines):
            valid_labs.append(item)
        else:
            bad_labs.append(item.model_dump())
    if bad_labs:
        if "recent_labs" not in unverified_fields:
            unverified_fields.append("recent_labs")
        unverified_data["recent_labs"] = bad_labs

    # ── pending_items ──────────────────────────────────────────────────────────
    valid_pending: list[PendingItem] = []
    bad_pending: list[dict] = []
    for item in summary.pending_items:
        if _citation_is_valid(item.source_line, item.source_text, normalised_lines):
            valid_pending.append(item)
        else:
            bad_pending.append(item.model_dump())
    if bad_pending:
        if "pending_items" not in unverified_fields:
            unverified_fields.append("pending_items")
        unverified_data["pending_items"] = bad_pending

    return summary.model_copy(
        update={
            "chief_complaint": chief_complaint,
            "active_problems": valid_problems,
            "current_medications": valid_meds,
            "allergies": valid_allergies,
            "recent_labs": valid_labs,
            "pending_items": valid_pending,
            "unverified_fields": unverified_fields,
            "unverified_data": unverified_data,
        }
    )
