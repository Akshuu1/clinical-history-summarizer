"""
Extraction service — two levels of extraction:

  extract_summary_raw()          — Stage 4: basic extraction, returns a raw dict.
                                   No citations. Kept for comparison/fallback.

  extract_summary_with_sources() — Stage 5: line-tagged input + citation requirement.
                                   Returns a fully validated ClinicalSummary model
                                   where every field is traced back to an exact [Ln]
                                   line in the source notes, or explicitly flagged null.
"""

import json
import logging
import os

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError

from app.models.summary import ClinicalSummary
from app.services.validator import validate_source_references

load_dotenv()

logger = logging.getLogger(__name__)

# Model used on Groq for both extraction functions
MODEL = "qwen/qwen3.8-27b"


# ─────────────────────────────────────────────────────────────────────────────
# Shared prompt for Stage 4 (no citations)
# ─────────────────────────────────────────────────────────────────────────────
_RAW_PROMPT_TEMPLATE = """\
You are a clinical data extraction assistant. Read the following clinical \
notes and return ONLY a valid JSON object — no prose, no markdown fences, \
no explanation before or after.

The JSON must have exactly these keys:
  "chief_complaint"      — string or null
  "active_problems"      — list of strings (each a diagnosis or problem)
  "current_medications"  — list of objects, each with keys:
                             "name"   (string),
                             "dose"   (string or null),
                             "timing" (string or null)
  "recent_labs"          — list of objects, each with keys:
                             "test_name" (string),
                             "value"     (string or null),
                             "date"      (string or null)
  "allergies"            — list of strings (each an allergen, with reaction
                           in parentheses if stated)
  "pending_items"        — list of strings (pending tests, referrals, actions)

Important rules:
- If information for a field is not present in the notes, return null \
for string fields or an empty list for list fields.
- Do not invent or infer information that is not explicitly stated in the \
notes.

Clinical notes:
---
{raw_notes}
---

Return the JSON object now. Nothing else.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 prompt — requires [Ln]-tagged input and citation objects
# ─────────────────────────────────────────────────────────────────────────────
_SOURCES_PROMPT_TEMPLATE = """\
You are a clinical data extraction assistant. Read the following clinical \
notes — every line is tagged with a label like [L1], [L2], etc.

Return ONLY a valid JSON object — no prose, no markdown fences.

For every piece of information you extract, you MUST provide a source \
citation:
  "line_number": the integer from the [Ln] tag of the line the fact came from
  "quoted_text": a verbatim substring copied from that line exactly as written

CRITICAL: If you cannot point to a specific [Ln] line that directly supports \
a field, you MUST set that field's source to null rather than guessing a line \
number. Never invent a citation.

The JSON must match this exact structure:
{{
  "patient_id": "{patient_id}",
  "chief_complaint": "string or null",
  "chief_complaint_source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null,
  "active_problems": ["string"],
  "active_problems_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  "current_medications": [
    {{
      "name": "string",
      "dose": "string or null",
      "timing": "string or null",
      "source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null
    }}
  ],
  "recent_labs": [
    {{
      "test_name": "string",
      "value": "string or null",
      "date": "string or null",
      "source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null
    }}
  ],
  "allergies": ["string"],
  "allergies_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  "pending_items": ["string"],
  "unverified_fields": []
}}

Rules:
- quoted_text must be EXACTLY copied from the source line. Do not paraphrase \
or alter capitalisation/punctuation.
- Do not include the [Ln] tag itself in quoted_text.
- If information is missing, use null or []. Never guess or invent facts.

Clinical notes (line-tagged):
---
{tagged_notes}
---

Return the JSON object now. Nothing else.
"""


class ExtractionError(Exception):
    """Raised when the LLM response cannot be parsed or schema-validated."""
    pass


def _get_client() -> OpenAI:
    """Build an OpenAI-compatible client pointed at Groq."""
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise ExtractionError(
            "No Groq API key found. Set GROQ_API_KEY in .env"
        )
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )


def _call_llm(client: OpenAI, prompt: str, max_tokens: int = 1800) -> str:
    """
    Make a single LLM call and return the raw text response.
    Strips markdown fences if the model ignores that instruction.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Clinical History Summarizer",
            },
        )
        raw = response.choices[0].message.content.strip()
    except Exception as exc:
        raise ExtractionError(f"API call failed: {exc}")

    # Strip markdown code fences if present despite instructions
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("```")
        ).strip()

    return raw


def _parse_json(raw: str, patient_id: str) -> dict:
    """Parse raw LLM text as JSON, raising ExtractionError on failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(
            "JSON parse failed for patient_id=%r.\nRaw response:\n%s",
            patient_id, raw
        )
        raise ExtractionError(
            f"LLM returned non-JSON for patient '{patient_id}': {exc}"
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no source tracing)
# ─────────────────────────────────────────────────────────────────────────────
def extract_summary_raw(raw_notes: str, patient_id: str) -> dict:
    """
    Stage 4: Send raw clinical notes to the LLM and return a plain dict.

    No source citations are requested or returned. Used for comparison
    and as a fallback when citation overhead is not needed.

    Returns a dict with keys:
        chief_complaint, active_problems, current_medications,
        recent_labs, allergies, pending_items
    """
    client = _get_client()
    prompt = _RAW_PROMPT_TEMPLATE.format(raw_notes=raw_notes)
    raw = _call_llm(client, prompt, max_tokens=800)
    result = _parse_json(raw, patient_id)

    # Ensure all expected keys are present with safe defaults
    for key, default in {
        "chief_complaint": None,
        "active_problems": [],
        "current_medications": [],
        "recent_labs": [],
        "allergies": [],
        "pending_items": [],
    }.items():
        result.setdefault(key, default)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Traced extraction with [Ln]-tagged lines and citation objects
# ─────────────────────────────────────────────────────────────────────────────
def extract_summary_with_sources(raw_notes: str, patient_id: str) -> ClinicalSummary:
    """
    Stage 5: Source-traced extraction.

    Pre-processing:
        Each line of raw_notes is prefixed with a tag "[L1]", "[L2]", etc.
        before being sent to the model. This gives the LLM unambiguous,
        numbered anchors to cite.

    The LLM is instructed to provide a citation object for every extracted
    field:
        { "line_number": int, "quoted_text": "<verbatim from that line>" }

    If the LLM cannot point to a specific line that directly supports a
    field, it is explicitly instructed to set that field's source to null
    rather than guessing. This is the core honesty constraint.

    Returns:
        A fully validated ClinicalSummary Pydantic model. Fields whose
        citations are null will be flagged later by validate_summary().

    Raises:
        ExtractionError: if the API call fails, the response cannot be
                         parsed as JSON, or it fails Pydantic validation.
    """
    # ── 1. Pre-process: tag each line with [L1], [L2], ...  ──────────────────
    lines = raw_notes.splitlines()
    tagged_notes = "\n".join(f"[L{i + 1}] {line}" for i, line in enumerate(lines))

    # ── 2. Build prompt and call the LLM  ────────────────────────────────────
    client = _get_client()
    prompt = _SOURCES_PROMPT_TEMPLATE.format(
        patient_id=patient_id,
        tagged_notes=tagged_notes,
    )
    raw = _call_llm(client, prompt, max_tokens=1800)

    # ── 3. Parse JSON  ────────────────────────────────────────────────────────
    data = _parse_json(raw, patient_id)

    # ── 4. Validate into Pydantic schema  ─────────────────────────────────────
    try:
        summary = ClinicalSummary(**data)
    except ValidationError as exc:
        logger.error(
            "Schema validation failed for patient_id=%r.\nRaw response:\n%s",
            patient_id, raw
        )
        raise ExtractionError(
            f"Schema mismatch for patient '{patient_id}': {exc}"
        ) from exc

    # ── 5. Verify every citation independently against the raw source lines  ───
    # This is the core safety layer: we never trust the LLM's own citations.
    # validate_source_references() nulls out bad/missing sources and populates
    # unverified_fields for anything it cannot confirm.
    return validate_source_references(summary, raw_notes)
