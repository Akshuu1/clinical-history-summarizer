"""
LLM Extraction Service — calls Gemini and returns a raw ClinicalSummary.

Key design decisions:
  - We number every input line (L1, L2, ...) before the LLM sees it.
  - The prompt demands a strict JSON schema; no free-form prose.
  - The prompt explicitly tells the model to cite SOURCE LINE NUMBERS, not
    to make up data if unsure, and to use null for fields it cannot find.
  - After this function returns, validator.py checks every citation.
    This function trusts nothing the model says about citations.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

from app.models.summary import (
    ClinicalSummary,
    ChiefComplaint,
    ActiveProblem,
    MedicationItem,
    LabResult,
    AllergyItem,
    PendingItem,
)

load_dotenv()

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ── Prompt ─────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT_TEMPLATE = textwrap.dedent("""
You are a clinical data extraction assistant. Your task is to read line-numbered
clinical notes and extract structured information. You MUST follow these rules:

RULES (non-negotiable):
1. For EVERY field you fill in, you MUST provide the exact line number (source_line)
   and verbatim text (source_text) from that line that supports the claim.
2. If you cannot find clear evidence for a field in the notes, return null for that
   field. Do NOT guess or infer. Leave it null.
3. Do not combine or paraphrase source_text — copy it exactly as it appears.
4. Return ONLY valid JSON matching the schema below. No prose, no markdown fences.
5. source_line must be an integer (the L-number prefix on each line).

OUTPUT SCHEMA (JSON):
{{
  "patient_id": "<string — use the ID provided>",
  "chief_complaint": {{
    "value": "<main reason for visit/admission>",
    "source_line": <integer>,
    "source_text": "<exact quote from that line>"
  }} | null,
  "active_problems": [
    {{
      "value": "<diagnosis or condition>",
      "source_line": <integer>,
      "source_text": "<exact quote from that line>"
    }}
  ],
  "current_medications": [
    {{
      "name": "<drug name>",
      "dose": "<dose or null>",
      "frequency": "<frequency or null>",
      "route": "<route or null>",
      "source_line": <integer>,
      "source_text": "<exact quote from that line>"
    }}
  ],
  "allergies": [
    {{
      "substance": "<allergen>",
      "reaction": "<reaction or null>",
      "severity": "<severity or null>",
      "source_line": <integer>,
      "source_text": "<exact quote from that line>"
    }}
  ],
  "recent_labs": [
    {{
      "test": "<test name>",
      "result": "<result value>",
      "date": "<date or null>",
      "unit": "<unit or null>",
      "flag": "<HIGH/LOW/CRITICAL/NORMAL or null>",
      "source_line": <integer>,
      "source_text": "<exact quote from that line>"
    }}
  ],
  "pending_items": [
    {{
      "value": "<pending test, referral, or action>",
      "source_line": <integer>,
      "source_text": "<exact quote from that line>"
    }}
  ]
}}

PATIENT ID: {patient_id}

CLINICAL NOTES (each line is prefixed with its line number):
{numbered_notes}

Extract the clinical summary now. Return JSON only.
""").strip()


# ── Line normalisation ─────────────────────────────────────────────────────────

def normalise_and_number_lines(raw_text: str) -> list[str]:
    """
    Split raw notes into lines, strip excess whitespace, and return
    a list where index 0 = line 1 (i.e. 1-indexed via source_line).
    Empty lines are preserved (as "") so line numbers stay stable.
    """
    lines = raw_text.splitlines()
    normalised = [line.strip() for line in lines]
    return normalised


def build_numbered_text(lines: list[str]) -> str:
    """Format lines as: 'L1: text\nL2: text\n...' for the prompt."""
    return "\n".join(f"L{i+1}: {line}" for i, line in enumerate(lines))


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """Raw call to Gemini. Returns the text response."""
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,  # deterministic extraction, not creative
        ),
    )
    response = model.generate_content(prompt)
    return response.text


def _parse_llm_json(raw_response: str) -> dict:
    """
    Parse the LLM's JSON response.
    Strips markdown fences if the model wrapped the output despite instructions.
    """
    text = raw_response.strip()
    # Remove ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _dict_to_clinical_summary(data: dict, patient_id: str) -> ClinicalSummary:
    """
    Convert the raw dict from the LLM into a ClinicalSummary Pydantic model.
    Handles missing/null fields gracefully.
    """
    def safe_ref(d: Optional[dict], cls):
        if not d:
            return None
        try:
            return cls(**d)
        except Exception:
            return None

    def safe_list(lst: Optional[list], cls):
        if not lst:
            return []
        result = []
        for item in lst:
            try:
                result.append(cls(**item))
            except Exception:
                pass  # malformed items are silently dropped here; validator flags them
        return result

    return ClinicalSummary(
        patient_id=patient_id,
        chief_complaint=safe_ref(data.get("chief_complaint"), ChiefComplaint),
        active_problems=safe_list(data.get("active_problems", []), ActiveProblem),
        current_medications=safe_list(data.get("current_medications", []), MedicationItem),
        allergies=safe_list(data.get("allergies", []), AllergyItem),
        recent_labs=safe_list(data.get("recent_labs", []), LabResult),
        pending_items=safe_list(data.get("pending_items", []), PendingItem),
        model_used=GEMINI_MODEL,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_summary_raw(
    patient_id: str,
    raw_notes: str,
) -> tuple[ClinicalSummary, list[str]]:
    """
    Full extraction pipeline (without validation — that's done in the route).
    
    Returns:
        (clinical_summary, normalised_lines)
        
    The caller (route/extract.py) should then call validate_summary() from
    validator.py to check all citations before storing or returning to the user.
    """
    normalised_lines = normalise_and_number_lines(raw_notes)
    numbered_text = build_numbered_text(normalised_lines)

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        patient_id=patient_id,
        numbered_notes=numbered_text,
    )

    raw_response = _call_gemini(prompt)
    data = _parse_llm_json(raw_response)
    summary = _dict_to_clinical_summary(data, patient_id)
    summary = summary.model_copy(update={"total_source_lines": len(normalised_lines)})

    return summary, normalised_lines
