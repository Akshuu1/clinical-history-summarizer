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
  
  "documented_conditions": ["string"],
  "documented_conditions_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "symptoms": ["string"],
  "symptoms_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "clinical_findings": ["string"],
  "clinical_findings_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "pertinent_negatives": ["string"],
  "pertinent_negatives_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "risk_factors": ["string"],
  "risk_factors_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "current_medications": [
    {{
      "drug": "string",
      "dose": "string or null",
      "route": "string or null",
      "frequency": "string or null",
      "status": "string (Current, Started, Stopped, Held, PRN, Historical, Unknown) or null",
      "uncertainty": "string or null",
      "source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null
    }}
  ],
  "recent_labs": [
    {{
      "test_name": "string",
      "value": "string or null",
      "unit": "string or null",
      "reference_range": "string or null",
      "date": "string or null",
      "abnormality": "string or null",
      "source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null
    }}
  ],
  "allergies": [
    {{
      "allergen": "string",
      "reaction": "string or null",
      "status": "string or null",
      "source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null
    }}
  ],
  "clinical_impression": "string or null",
  "clinical_impression_source": {{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}} or null,
  
  "differential_diagnoses": ["string"],
  "differential_diagnoses_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "pending_items": ["string"],
  "red_flags": ["string"],
  "red_flags_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "uncertainties": ["string"],
  "uncertainties_sources": [{{"document_id": "notes", "line_number": <int>, "quoted_text": "<verbatim>"}}],
  
  "unverified_fields": []
}}

Rules:
- MOST IMPORTANT RULE: Never treat an inference as a documented fact. Never treat missing information as a negative finding. Never silently resolve uncertainty. Preserve clinically relevant information even when it does not fit a predefined field.
- quoted_text must be EXACTLY copied from the source line. Do not paraphrase or alter capitalisation/punctuation.
- Do not include the [Ln] tag itself in quoted_text.
- CRITICAL — current_medications: extract all documented medications. Use the 'uncertainty' field if dose/route is unsure.
- CRITICAL — Diagnosis vs Finding vs Symptom: 
   * Symptoms (e.g., "chest pain", "diaphoresis") go to symptoms.
   * Clinical findings (e.g., "ST depression", "elevated JVP") go to clinical_findings.
   * Documented conditions (e.g., "Decompensated heart failure", "T2DM") go to documented_conditions.
   * Risk factors (e.g., "former smoker") go to risk_factors.
- CRITICAL — Inference: Do NOT infer a diagnosis from an abnormal lab result or finding.
- CRITICAL — Differentials: Put differential or suspected diagnoses (e.g., "query PE", "r/o appendicitis") in differential_diagnoses, NOT documented_conditions.
- pertinent_negatives: Extract explicitly documented absent findings (e.g., "No flank pain"). NEVER treat "not mentioned" as negative.
- red_flags: Extract explicitly documented concerning signs (e.g. "Hemodynamic instability", "Fever").
- uncertainties: If the text says the patient or doctor is unsure (e.g., "patient says 5 or 10mg, not certain", "unknown if allergic"), extract that into uncertainties.

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


# =============================================================================
# Stage 6 — Patient-friendly rewrite (mode=patient)
# =============================================================================

_PATIENT_FRIENDLY_PROMPT = """\
You are a medical communication assistant. Your job is to rewrite a \
structured clinical summary into plain, friendly language that a patient \
can easily understand. Use short sentences. Avoid medical jargon; if a \
medical term is necessary, explain it in plain English in parentheses \
immediately after.

CRITICAL RULES — you must follow all of these:
1. Do NOT add any new medical information, interpretation, diagnosis, or \
   advice that is not already present in the input.
2. Do NOT mention any field that is listed in "unverified_fields" — omit \
   it silently from the patient output.
3. Do NOT mention any field that is listed in "missing_fields".
4. If a field is empty or null, skip it — do not say "no allergies were \
   documented", just leave that section out.
5. Write in second person ("You came in because...", "Your medications \
   include...").
6. Keep the output under 300 words.
7. Return ONLY the plain-text patient summary — no JSON, no markdown \
   headers, no bullet points. Just clear, friendly prose paragraphs.

VERIFIED CLINICAL SUMMARY (JSON):
{summary_json}

FIELDS TO OMIT (unverified or missing):
{skip_fields}

Write the patient-friendly summary now:
"""


def generate_patient_friendly_summary(
    summary: "ClinicalSummary",
) -> str:
    """
    Makes a second LLM call that rewrites only the verified fields of a
    ClinicalSummary into plain, patient-readable language.

    Fields in unverified_fields or missing_fields are silently omitted
    so the patient never receives unconfirmed information.

    Returns:
        A plain-text string suitable for showing directly to a patient.
    """
    client = _get_client()

    # Build a trimmed view of the summary — only verified, non-empty data
    skip = set(summary.unverified_fields) | set(summary.missing_fields)

    # Give the LLM a clean dict of only the fields we want included
    verified_data = {
        "chief_complaint": summary.chief_complaint,
        "active_problems": summary.active_problems,
        "current_medications": [
            {
                "name": m.name,
                "dose": m.dose,
                "timing": m.timing,
            }
            for i, m in enumerate(summary.current_medications)
            if f"current_medications[{i}]" not in skip
        ],
        "recent_labs": [
            {
                "test_name": lab.test_name,
                "value": lab.value,
                "date": lab.date,
            }
            for i, lab in enumerate(summary.recent_labs)
            if f"recent_labs[{i}]" not in skip
        ],
        "allergies": summary.allergies,
        "pending_items": summary.pending_items,
    }

    # Remove top-level fields that are flagged as unverified/missing
    if "chief_complaint" in skip:
        verified_data["chief_complaint"] = None
    if "active_problems" in skip:
        verified_data["active_problems"] = []

    prompt = _PATIENT_FRIENDLY_PROMPT.format(
        summary_json=json.dumps(verified_data, indent=2),
        skip_fields=", ".join(sorted(skip)) if skip else "none",
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        text = response.choices[0].message.content or ""
        return text.strip()
    except Exception as exc:
        logger.warning("Patient-friendly rewrite failed: %s", exc)
        return (
            "A plain-language version of your summary could not be generated. "
            "Please ask your doctor to explain the clinical summary above."
        )


# =============================================================================
# Stage 7 — Two-stage schema-free extraction
# =============================================================================

_STAGE1_SECTION_PROMPT = """\
You are a clinical document analyst. Read the following clinical notes \
and identify every distinct type of information the doctor has written.

Return ONLY a valid JSON array — no markdown, no prose. Each element \
in the array represents one identified section and must have exactly \
these keys:
  "section_label"  — a short, descriptive label in snake_case \
                     (e.g. "chief_complaint", "medications", "diet_advice", \
                     "referral_notes", "lifestyle_instructions", \
                     "follow_up_date", "vital_signs")
  "line_numbers"   — list of 1-indexed line numbers that contain this \
                     section's content
  "quoted_text"    — the verbatim text from those lines (concatenated if \
                     multiple lines)

Do not force any fixed schema. Just describe what IS in the document.
If two adjacent lines clearly belong to the same topic, group them.

Clinical notes (line-tagged):
---
{tagged_notes}
---
"""

_STAGE2_MAP_PROMPT = """\
You are a clinical data structuring assistant. You have been given a list \
of sections identified in a clinical document (Step 1 output) and you must \
now map each section to the closest standard clinical schema field.

The standard fields are:
  chief_complaint, clinical_impression, documented_conditions, symptoms, \
  clinical_findings, pertinent_negatives, risk_factors, differential_diagnoses, \
  red_flags, current_medications, recent_labs, \
  allergies, pending_items, uncertainties

Rules:
1. Map each section_label to one of the standard fields above ONLY if \
   the mapping is clear and obvious.
2. If a section does NOT clearly map to any standard field, mark it \
   as "extra" — it will go into raw_extra_fields.
3. For mapped sections, extract the data in exactly the same citation \
   format required by the main extraction schema.
4. For extra sections, preserve the section_label and quoted_text as-is.
5. MOST IMPORTANT RULE: Never treat an inference as a documented fact. Never treat missing information as a negative finding. Never silently resolve uncertainty. Preserve clinically relevant information even when it does not fit a predefined field.
6. CRITICAL — Diagnosis vs Finding vs Symptom: 
   * Symptoms (e.g., "chest pain", "diaphoresis") go to symptoms.
   * Clinical findings (e.g., "ST depression", "elevated JVP") go to clinical_findings.
   * Documented conditions (e.g., "Decompensated heart failure", "T2DM") go to documented_conditions.
   * Risk factors (e.g., "former smoker") go to risk_factors.
7. CRITICAL — Inference: Do NOT infer a diagnosis from an abnormal lab result or finding.
8. CRITICAL — Differentials: Put differential or suspected diagnoses (e.g., "query PE", "r/o appendicitis") in differential_diagnoses, NOT documented_conditions.

Return ONLY a valid JSON object with exactly these top-level keys:
{{
  "patient_id": "{patient_id}",
  "chief_complaint": string or null,
  "chief_complaint_source": {{"document_id":"notes","line_number":N,"quoted_text":"..."}} or null,
  "clinical_impression": string or null,
  "clinical_impression_source": {{"document_id":"notes","line_number":N,"quoted_text":"..."}} or null,
  "documented_conditions": [...],
  "documented_conditions_sources": [...],
  "symptoms": [...],
  "symptoms_sources": [...],
  "clinical_findings": [...],
  "clinical_findings_sources": [...],
  "pertinent_negatives": [...],
  "pertinent_negatives_sources": [...],
  "risk_factors": [...],
  "risk_factors_sources": [...],
  "differential_diagnoses": [...],
  "differential_diagnoses_sources": [...],
  "red_flags": [...],
  "red_flags_sources": [...],
  "current_medications": [...each with drug/dose/route/frequency/status/uncertainty/source...],
  "recent_labs": [...each with test_name/value/unit/reference_range/date/abnormality/source...],
  "allergies": [...each with allergen/reaction/status/source...],
  "pending_items": [...strings...],
  "uncertainties": [...],
  "uncertainties_sources": [...],
  "unverified_fields": [],
  "missing_fields": [],
  "raw_extra_fields": {{
    "section_label": {{"content": "...", "line_numbers": [...], "quoted_text": "..."}}
  }}
}}

Step 1 identified sections:
{sections_json}

Original notes (line-tagged, for reference):
---
{tagged_notes}
---
"""


def extract_summary_two_stage(raw_notes: str, patient_id: str) -> "ClinicalSummary":
    """
    Two-stage schema-free extraction.

    Stage 1: Ask the LLM to identify, free-form, what distinct sections
             exist in the document — no schema imposed.
    Stage 2: Pass the section list back and ask it to map sections to
             ClinicalSummary fields. Anything that doesn't clearly map
             goes into raw_extra_fields.

    The result is then passed through validate_source_references() exactly
    like the single-stage pipeline.

    Keeps extract_summary_with_sources() unchanged — this is an
    alternative, not a replacement.
    """
    client = _get_client()

    # Pre-process: tag lines [L1], [L2], ...
    lines = raw_notes.splitlines()
    tagged_notes = "\n".join(
        f"[L{i}] {line}" for i, line in enumerate(lines, 1)
    )

    # ── Stage 1: free-form section identification ────────────────────────────
    stage1_prompt = _STAGE1_SECTION_PROMPT.format(tagged_notes=tagged_notes)
    raw1 = _call_llm(client, stage1_prompt, max_tokens=1000)
    data1 = _parse_json(raw1, patient_id)
    if not isinstance(data1, list):
        # If the model wrapped it in an object, try to extract the list
        if isinstance(data1, dict) and "sections" in data1:
            data1 = data1["sections"]
        else:
            logger.warning(
                "Stage 1 did not return a list for patient_id=%r — "
                "falling back to single-stage extraction.",
                patient_id,
            )
            return extract_summary_with_sources(raw_notes, patient_id)

    logger.info(
        "Two-stage extraction: Stage 1 identified %d sections for patient_id=%r",
        len(data1), patient_id,
    )

    # ── Stage 2: map sections to schema ─────────────────────────────────────
    stage2_prompt = _STAGE2_MAP_PROMPT.format(
        patient_id=patient_id,
        sections_json=json.dumps(data1, indent=2),
        tagged_notes=tagged_notes,
    )
    raw2 = _call_llm(client, stage2_prompt, max_tokens=2000)
    data2 = _parse_json(raw2, patient_id)

    # Ensure patient_id is set
    if isinstance(data2, dict):
        data2["patient_id"] = patient_id

    # ── Parse + validate ─────────────────────────────────────────────────────
    try:
        summary = ClinicalSummary(**data2)
    except ValidationError as exc:
        logger.error(
            "Two-stage schema validation failed for patient_id=%r: %s",
            patient_id, exc,
        )
        raise ExtractionError(
            f"Two-stage schema mismatch for patient '{patient_id}': {exc}"
        ) from exc

    return validate_source_references(summary, raw_notes)
