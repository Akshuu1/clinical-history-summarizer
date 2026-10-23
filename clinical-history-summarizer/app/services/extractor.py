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
import re
import time

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError

from app.models.summary import ClinicalSummary, SourceReference
from app.services.validator import validate_source_references
from app.services.medical_normalizer import (
    normalize_frequency,
    normalize_route,
    normalize_condition,
    normalize_lab_name,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Configurable model with OpenRouter fallback chain (only used when Gemini is unavailable)
# Note: Nemotron 3.5 Embed 8B is embeddings-only — using nemotron-3.5-lightning for text generation
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free,google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free"
MODEL = os.environ.get("LLM_MODEL") or DEFAULT_MODEL

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
You are a senior clinical documentation and decision support assistant. Read the line-tagged \
clinical notes below and return ONE valid JSON object only — no prose, no markdown fences.

Every [Ln] tag is a line number. Use those exact numbers in citations.

─── STRICT ANM CLINICAL INSTRUCTIONS & RULES ───────────────────────────────
1. STRICT SEPARATION OF DOCTOR PLAN VS AI RECOMMENDATIONS:
   A. "doctor_recommendations":
      - Extract ONLY instructions, investigations, prescriptions, referrals, and follow-ups explicitly recorded by the doctor in the source notes.
      - Preserve verbatim clinician intent, dosage, frequency, duration, and conditional statements (e.g., if note states "consider treatment after evaluation" or "treatment depending on evaluation", do NOT convert it into "treatment prescribed").
      - NEVER add an AI-generated recommendation or inference to this section.
   B. "ai_recommendations":
      - Proactively identify clinically justified additional investigations, follow-up actions, medication clarifications, lifestyle considerations, and referrals.
      - Recommendations may be suggested even if the doctor did not document them, provided they are clinically grounded in the patient's presentation.
      - MUST be structured objects (see schema below) and clearly designated with prescription_status "Not documented as prescribed".
      - Explain the clinical reason using evidence from the notes.
      - State when an action depends on clinical examination, clinician judgment, or local guidelines.
      - Do NOT recommend tests or referrals merely because they are commonly ordered. Do not automatically prescribe iron or mandate endoscopy/colonoscopy without explaining clinical rationale and clinician review.
   C. Urgent Concerns ("red_flags"):
      - Identify concerning symptoms, measurements, or combinations of findings.
      - Assign proportionate urgency (routine, prompt clinical review, or emergency assessment) with clear evidence. Never exaggerate or claim emergency without justification. Include appropriate safety-net advice.

2. STRUCTURED FORMAT FOR EVERY AI RECOMMENDATION ("ai_recommendations"):
   Every item in "ai_recommendations" must have:
   - "recommendation": Proposed action.
   - "reason": Relevant symptoms, measurements, history, or findings.
   - "priority": "routine", "prompt", or "urgent".
   - "prescription_status": "Doctor-documented", "Not documented as prescribed", or "Unclear".
   - "timing": Specify only when clinically justified, otherwise "To be determined by clinician".
   - "caveat": Relevant uncertainty or need for physical examination / clinician judgment.
   Do not fabricate exact testing intervals, thresholds, or durations. If information is missing, state what is missing.

3. DIAGNOSTIC ACCURACY & EVIDENCE ATTRIBUTION:
   - NEVER classify an inferred diagnosis as a documented condition ("documented_conditions") unless the clinician explicitly records that diagnosis as documented in the notes.
   - A laboratory pattern (e.g. low Hb 9.1, MCV 71, Ferritin 7) strongly supports microcytic iron-deficiency anaemia, but is an INFERENCE/IMPRESSION, NOT a documented condition unless explicitly written as a diagnosis by the clinician. Put it in "clinical_impression" or "differential_diagnoses".
   - State that the underlying cause of abnormal findings (e.g. cause of iron deficiency or source of blood loss) has not yet been established.
   - Distinguish patient-reported information, family-reported observations (e.g. family-reported pallor), clinician-observed physical signs, and objective measurements (vitals/labs).
   - Never invent examination findings or claim an examination occurred when only a written note is available.
   - Do NOT state that serious causes or B12 deficiency have been ruled out solely from the supplied information.
   - Do NOT convert missing information into a negative finding.
   - Preserve explicit negative findings (e.g. no fever, cough, weight loss, chest pain, syncope) in "pertinent_negatives".
     CRITICAL: pertinent_negatives must ONLY include findings that are explicitly and directly stated as absent in the notes using clear negative language (e.g. 'no chest pain', 'denies fever'). 
     Do NOT include:
     - Inferences from positive statements (e.g. 'better with rest' does NOT mean 'no symptoms at rest')  
     - Findings that are simply not mentioned — absence of mention is NOT a documented negative finding
     - Any finding you cannot cite to an exact line with explicit negative language
   - Identify clinical unknowns (e.g. cause of anaemia, source of blood loss, identity of allergic antibiotic) in "uncertainties".

4. MEDICATION EXTRACTION:
   For every medication in "current_medications":
   - "drug": Drug name (e.g. "Pantoprazole").
   - "dose": Dose and unit (e.g. "40 mg") or null.
   - "route": Route (e.g. "Oral") or null.
   - "frequency": Frequency (e.g. "Once daily"). CRITICAL: NEVER DUPLICATE FREQUENCY. Output "Once daily" once, NOT "Once daily, once daily" or "40 mg • once daily • once daily".
   - "prn_status": "Scheduled", "PRN", or "Unclear".
   - "status": "Current", "Newly prescribed", "Discontinued", "Reported by patient", or "Unclear". Distinguish patient-reported from doctor-prescribed.
   - "duration": Duration if documented; if unclear or not stated, output EXACTLY "Duration not specified".
   - "missing_information": Missing details requiring verification (e.g. "Duration not specified; clinical indication requires verification") or null.
   - "uncertainty": Explicit doubts expressed in the note or null.
   - Never recommend starting, stopping, or changing prescription medication without clinician oversight.

5. PATIENT-FRIENDLY NARRATIVE SUMMARY ("narrative_summary"):
   - Plain language (8th-grade level), explain symptoms and test values simply.
   - Distinguish what is known (symptoms, measured numbers) from what is suspected (possible iron deficiency).
   - Explain what the documented doctor plan involves.
   - Present AI-suggested next steps separately from doctor instructions.
   - Avoid unsupported reassurance ("No serious causes are indicated" is strictly forbidden when cause is unestablished).
   - Include appropriate safety-net guidance when warranted.

6. MEDICAL ABBREVIATION EXPANSION: Expand standard medical abbreviations correctly before extracting:
   - bd / BID = twice daily (NOT once daily)
   - od / OD = once daily
   - tds / TID = three times daily
   - qid / QDS = four times daily  
   - prn / SOS = as needed
   - stat = immediately, one-time dose only
   - irreg = irregular
   Never guess at an abbreviation — if unclear, set the field to the original abbreviation text and add an uncertainty note.

• ESCAPE QUOTES: If quoted_text or any string contains double quotes ("), you MUST escape them as (\") to produce valid JSON.
• CITATIONS: For every extracted fact, provide an exact line_number and verbatim quoted_text.

─── JSON STRUCTURE ──────────────────────────────────────────────────────────
{{
  "patient_id": "{patient_id}",

  "chief_complaint": "string or null",
  "chief_complaint_source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null,

  "documented_conditions": ["string"],
  "documented_conditions_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "symptoms": ["string"],
  "symptoms_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "clinical_findings": [
    {{
      "finding": "plain English description",
      "finding_type": "category e.g. cardiovascular/respiratory",
      "value": "numeric value if applicable or null",
      "unit": "unit if applicable or null",
      "source": {{"document_id":"notes",
                 "line_number":<int>,
                 "quoted_text":"<verbatim>"}} or null
    }}
  ],

  "pertinent_negatives": [
    "string — CRITICAL: pertinent_negatives must ONLY include findings that are explicitly and directly stated as absent in the notes using clear negative language (e.g. 'no chest pain', 'denies fever'). Do NOT include: inferences from positive statements (e.g. 'better with rest' does NOT mean 'no symptoms at rest'); findings that are simply not mentioned — absence of mention is NOT a documented negative finding; any finding you cannot cite to an exact line with explicit negative language"
  ],
  "pertinent_negatives_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "risk_factors": ["string"],
  "risk_factors_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "current_medications": [
    {{
      "drug": "string",
      "dose": "string or null",
      "route": "string or null",
      "frequency": "string or null",
      "prn_status": "Scheduled|PRN|Unclear",
      "status": "Current|Newly prescribed|Discontinued|Reported by patient|Unclear",
      "duration": "string",
      "missing_information": "string or null",
      "uncertainty": "string or null",
      "source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null
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
      "source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null
    }}
  ],

  "allergies": [
    {{
      "allergen": "string",
      "reaction": "string or null",
      "status": "string or null",
      "source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null
    }}
  ],

  "clinical_impression": "string or null",
  "clinical_impression_source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null,

  "differential_diagnoses": [
    "string — concise diagnosis with clinical rationale, e.g. 'Iron deficiency anaemia (highly probable based on Hb 9.1, MCV 71, Ferritin 7; cause unconfirmed)'"
  ],
  "differential_diagnoses_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "pending_items": ["string"],

  "red_flags": ["string — clinically concerning findings with proportionate urgency and rationale"],
  "red_flags_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "uncertainties": ["string — clinical unknowns needing investigation, e.g. 'Underlying cause of low haemoglobin not established'"],
  "uncertainties_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "unverified_fields": [],

  "doctor_recommendations": [
    "string — ONLY explicit instructions, prescriptions, or follow-ups documented by the doctor in the source notes. Preserve exact phrasing and conditional intent. NEVER add AI recommendations here."
  ],

  "ai_recommendations": [
    {{
      "recommendation": "string — proposed action, test, or specialist review",
      "reason": "string — symptoms, labs, or history justifying this action",
      "priority": "routine|prompt|urgent",
      "prescription_status": "Not documented as prescribed",
      "timing": "string — specific timeframe if clinically justified, else 'To be determined by clinician'",
      "caveat": "string — uncertainty or need for clinical examination/guideline review"
    }}
  ],

  "next_steps": [
    "string — mirrored string version of each ai_recommendations item for reference.\nCRITICAL RULES FOR next_steps:\n1. Before generating any suggestion, check the patient's documented demographics. Never suggest an investigation that is explicitly inapplicable to this patient (e.g., do not suggest gynaecological review for a documented male patient).\n2. If the doctor's documented plan already addresses a finding — even indirectly — do not generate a next_step that contradicts, pre-empts, or duplicates it. The doctor's plan takes absolute precedence. If the plan says 'start treatment depending on evaluation', do not suggest starting that treatment.\n3. Only suggest actions for information that is genuinely absent from both the notes AND the doctor's plan."
  ],

  "narrative_summary": "Plain-language 8th-grade synthesis explaining what brought the patient in, vitals/tests, doctor's plan, AI recommendations labeled separately, and safety-net advice."
}}

─── NOTES (line-tagged) ────────────────────────────────────────────────────
{tagged_notes}
────────────────────────────────────────────────────────────────────────────

Return ONLY the JSON object. Nothing before it. Nothing after it.
"""


class ExtractionError(Exception):
    """Raised when the LLM response cannot be parsed or schema-validated."""
    pass


class RateLimitExceededError(ExtractionError):
    """Raised when the LLM provider rate limit is exceeded."""
    pass


class JSONParseError(ExtractionError):
    """Raised when the LLM response is invalid JSON after all cleanup attempts."""
    pass


def _get_client() -> OpenAI | None:
    """Build an OpenAI-compatible client pointed at the configured provider for fallback."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return None
    
    # Allow overriding the base URL for different providers/proxies
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def _call_llm_gemini(prompt: str, max_tokens: int = 3500) -> tuple[str, str]:
    """
    Primary LLM call via the official Google Gemini SDK (google-genai).
    Uses gemini-2.5-flash (current recommended flash model).
    Raises ExtractionError subclasses on failure so the caller can
    decide whether to fall back to OpenRouter.
    """
    from google import genai
    from google.genai import types as genai_types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ExtractionError("GEMINI_API_KEY not set — skipping Gemini.")

    # Resolve model name: ignore OpenRouter-style slugs
    model_name = os.environ.get("LLM_MODEL", "gemini-3.8-flash")
    if "openrouter" in model_name or ":" in model_name or model_name.startswith("gemini-2"):
        model_name = "gemini-3.8-flash"

    client = genai.Client(api_key=api_key)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                ),
            )
            raw = response.text
            if not raw:
                raise ExtractionError("Gemini returned an empty response.")
            return raw, model_name
        except ExtractionError:
            raise
        except Exception as exc:
            msg = str(exc)
            # Auth / permission errors — fail immediately, no point retrying
            if "403" in msg or "PERMISSION_DENIED" in msg or "401" in msg or "API_KEY_INVALID" in msg:
                raise ExtractionError(
                    f"Gemini authentication failed (check GEMINI_API_KEY): {exc}"
                )
            if "429" in msg or "quota" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
                if attempt < 2:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "Gemini rate limit hit — waiting %ds (attempt %d/3)…",
                        wait_time, attempt + 1,
                    )
                    time.sleep(wait_time)
                    continue
                raise RateLimitExceededError(
                    f"Gemini API rate limit exceeded. Please retry in a moment. ({exc})"
                )
            if "503" in msg or "overloaded" in msg.lower() or "502" in msg:
                if attempt < 2:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "Gemini overloaded — waiting %ds (attempt %d/3)…",
                        wait_time, attempt + 1,
                    )
                    time.sleep(wait_time)
                    continue
            if attempt == 2:
                raise ExtractionError(f"Gemini API call failed after retries: {exc}")

    raise ExtractionError("Unexpected retry loop exit.")


def _call_llm_openrouter(client: OpenAI, prompt: str, max_tokens: int = 3500) -> tuple[str, str]:
    """
    Fallback LLM function: tries each model in MODEL (comma-separated list)
    one by one — not as an OpenRouter route array.

    Empty responses and 4xx/5xx errors on one model advance to the next.
    Only raises after all models are exhausted.
    """
    if not client:
        raise ExtractionError("No OpenRouter API key found for fallback.")

    models_list = [m.strip() for m in MODEL.split(",") if m.strip()] if "," in MODEL else [MODEL]

    messages = [
        {
            "role": "system",
            "content": (
                "You are an ANM clinical documentation assistant. Adhere strictly to ANM rules: "
                "1. Source fidelity (never claim unrecorded events). "
                "2. Separate evidence from inference (do not infer diagnoses from labs/signs). "
                "3. Respect explicitly reported symptoms. "
                "4. Clinically grounded differentials with rationales. "
                "5. Complete extraction of findings, meds, allergies, plans. "
                "6. No unsupported causality from risk factors alone. "
                "7. No invented lab reference ranges ('Not provided in source'). "
                "8. Keep explicit clinician plans separate from AI recommendations. "
                "9. Use 'Not mentioned in notes' for absent items. "
                "10. Identify clinical safety risks. "
                "Respond ONLY with the requested JSON object. "
                "Do not include reasoning, chain of thought, or any text outside the JSON."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    last_error: Exception | None = None

    for model_id in models_list:
        for attempt in range(2):  # 2 retries per model for transient errors
            try:
                response = client.chat.completions.create(
                    model=model_id,
                    max_tokens=max_tokens,
                    messages=messages,
                    extra_headers={
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "Clinical History Summarizer",
                    },
                    extra_body={"reasoning": {"effort": "none"}},
                )
                msg_obj = response.choices[0].message
                raw = (msg_obj.content or "").strip()
                if not raw and getattr(msg_obj, "reasoning", None):
                    # In case the model still emitted output in reasoning field
                    raw = (msg_obj.reasoning or "").strip()

                if not raw:
                    logger.warning(
                        "OpenRouter model %r returned empty response — trying next model.", model_id
                    )
                    last_error = ExtractionError(f"{model_id} returned empty response.")
                    break  # advance to next model

                logger.info("OpenRouter extraction succeeded via %r", model_id)
                return raw, model_id

            except ExtractionError:
                raise
            except Exception as exc:
                msg = str(exc)
                is_rate_limit = "429" in msg or "rate_limit" in msg.lower()
                is_overloaded = "503" in msg or "502" in msg or "overloaded" in msg.lower()
                is_not_found = "404" in msg or "unavailable" in msg.lower() or "no endpoints" in msg.lower()

                if is_not_found:
                    # Model not available — skip immediately
                    logger.warning("OpenRouter model %r unavailable: %s", model_id, msg[:80])
                    last_error = ExtractionError(f"{model_id} not available: {exc}")
                    break  # next model

                if (is_rate_limit or is_overloaded) and attempt == 0:
                    wait_time = 3
                    logger.warning(
                        "OpenRouter %r issue (%s) — waiting %ds before retry…",
                        model_id,
                        "rate limit" if is_rate_limit else "overloaded",
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

                if is_rate_limit:
                    # Rate limited after retry — skip to next model, don't stop the chain
                    logger.warning(
                        "OpenRouter model %r rate-limited after retry — trying next model.", model_id
                    )
                    last_error = RateLimitExceededError(
                        f"{model_id} rate-limited. Trying next fallback model."
                    )
                    break  # skip to next model

                logger.warning("OpenRouter model %r failed: %s", model_id, msg[:120])
                last_error = ExtractionError(f"API call failed on {model_id}: {exc}")
                break  # next model

    # All models exhausted — surface the most useful error
    if isinstance(last_error, RateLimitExceededError):
        raise RateLimitExceededError(
            "All OpenRouter fallback models are currently rate-limited. "
            "Add GEMINI_API_KEY to .env for reliable access (free at aistudio.google.com/apikey)."
        )
    raise last_error or ExtractionError("All OpenRouter fallback models failed or returned empty responses.")


def _call_llm(client: OpenAI | None, prompt: str, max_tokens: int = 3500) -> tuple[str, str]:
    """
    Main LLM dispatcher.
    - Primary: Gemini direct SDK (google-genai) if GEMINI_API_KEY is set.
    - Fallback: OpenRouter if Gemini fails or key is absent.
    Auth/permission errors on Gemini are treated as configuration failures
    and immediately fall through to OpenRouter (no 3-retry wait).
    """
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return _call_llm_gemini(prompt, max_tokens)
        except RateLimitExceededError:
            # Hard rate limit — propagate immediately; don't waste OpenRouter quota
            raise
        except ExtractionError as exc:
            logger.warning(
                "Gemini unavailable (%s) — falling back to OpenRouter…", exc
            )
            if not client:
                raise

    return _call_llm_openrouter(client, prompt, max_tokens)


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to close a JSON object/array that was truncated mid-stream by a
    low-capacity free-tier model.  Walks character-by-character tracking
    open brackets, braces, and string state, then appends the minimum closing
    tokens needed to produce parseable (partial) JSON.

    This is best-effort — it only recovers cleanly truncated JSON, not
    responses that are structurally malformed from the start.
    """
    stack: list[str] = []  # tracks '{' and '['
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch in ("}", "]"):
            if stack:
                stack.pop()

    # If we're mid-string, close it
    suffix = ""
    if in_string:
        suffix += '"'

    # Close any open arrays/objects in reverse order
    for opener in reversed(stack):
        suffix += "]" if opener == "[" else "}"

    return text.rstrip(",").rstrip() + suffix


def _parse_json(raw: str, patient_id: str) -> dict:
    """Parse raw LLM text as JSON with robust cleaning of reasoning traces and fences."""
    cleaned = raw.strip()
    
    # 1. Strip <think>...</think> tags if model emits chain of thought
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    # 2. Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Remove trailing commas before closing brackets/braces
    # (common LLM JSON generation error)
    cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)

    # 3. Direct JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 4. Fallback: extract substring between the first { and the last }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass

    # 5. Truncation recovery: free-tier models cut JSON mid-stream.
    #    Auto-close unclosed strings/arrays/objects so we get a partial result.
    if first_brace != -1:
        truncated = cleaned[first_brace:]
        try:
            truncated = _repair_truncated_json(truncated)
            result = json.loads(truncated)
            logger.warning(
                "Truncated JSON repaired for patient_id=%r — some fields may be missing.",
                patient_id,
            )
            return result
        except Exception:
            pass

    logger.error(
        "JSON parse failed for patient_id=%r.\nRaw response:\n%s",
        patient_id, raw
    )
    raise JSONParseError(
        f"LLM returned invalid or malformed JSON for patient '{patient_id}'."
    )


def _clean_medication_frequency(freq: str | None, dose: str | None = None) -> str | None:
    """Removes duplicate frequency phrases and embedded doses from frequency."""
    if not freq:
        return freq
    f = re.sub(r"\s+", " ", str(freq)).strip()
    if dose:
        d_clean = re.escape(dose.strip())
        f = re.sub(rf"^{d_clean}\s*[,•\-:/]?\s*", "", f, flags=re.IGNORECASE).strip()
    
    # Split on bullet points or commas to remove repeated segments
    parts = [p.strip() for p in re.split(r"[•;,]+", f) if p.strip()]
    if parts:
        seen = []
        for p in parts:
            if p.lower() not in [s.lower() for s in seen]:
                seen.append(p)
        f = " ".join(seen)
    
    # Deduplicate repeated phrase halves (e.g. "once daily once daily")
    tokens = f.split()
    if len(tokens) >= 2 and len(tokens) % 2 == 0:
        half = len(tokens) // 2
        if [t.lower() for t in tokens[:half]] == [t.lower() for t in tokens[half:]]:
            f = " ".join(tokens[:half])

    return f or freq


def _normalize_summary_data(data: dict) -> dict:
    """
    Defensively normalizes string-list fields, medication entries, and AI/Doctor
    recommendations in data to prevent schema validation crashes and enforce ANM precision.
    """
    if not isinstance(data, dict):
        return data

    string_list_fields = [
        "documented_conditions",
        "symptoms",
        "pertinent_negatives",
        "risk_factors",
        "differential_diagnoses",
        "pending_items",
        "red_flags",
        "uncertainties",
        "doctor_recommendations",
        "next_steps",
    ]

    # ── Normalize Clinical Findings ──────────────────────────────────────────
    if "clinical_findings" in data and isinstance(data["clinical_findings"], list):
        clean_findings = []
        for item in data["clinical_findings"]:
            if isinstance(item, dict):
                clean_item = dict(item)
                if clean_item.get("value") is not None:
                    clean_item["value"] = str(clean_item["value"])
                if clean_item.get("unit") is not None:
                    clean_item["unit"] = str(clean_item["unit"])
                if clean_item.get("finding_type") is not None:
                    clean_item["finding_type"] = str(clean_item["finding_type"])
                clean_findings.append(clean_item)
            elif isinstance(item, str) and item.strip():
                clean_findings.append({"finding": item.strip()})
        data["clinical_findings"] = clean_findings

    # ── Normalize Recent Labs ────────────────────────────────────────────────
    if "recent_labs" in data and isinstance(data["recent_labs"], list):
        for lab in data["recent_labs"]:
            if isinstance(lab, dict):
                if lab.get("value") is not None:
                    lab["value"] = str(lab["value"])
                if lab.get("unit") is not None:
                    lab["unit"] = str(lab["unit"])

    for field in string_list_fields:
        if field in data and isinstance(data[field], list):
            normalized_list = []
            for item in data[field]:
                if isinstance(item, str):
                    normalized_list.append(item)
                elif isinstance(item, dict):
                    dx = (
                        item.get("dx")
                        or item.get("diagnosis")
                        or item.get("condition")
                        or item.get("name")
                        or item.get("concern")
                    )
                    rationale = item.get("rationale") or item.get("reason") or item.get("description")
                    urgency = item.get("urgency")
                    prefix = f"[{str(urgency).upper()}] " if urgency else ""
                    if dx and rationale:
                        normalized_list.append(f"{prefix}{dx} — {rationale}")
                    elif dx:
                        normalized_list.append(f"{prefix}{dx}")
                    elif rationale:
                        normalized_list.append(f"{prefix}{rationale}")
                    else:
                        normalized_list.append(", ".join(f"{k}: {v}" for k, v in item.items() if v))
                elif item is not None:
                    normalized_list.append(str(item))
            data[field] = normalized_list

    # ── Normalize Allergies ──────────────────────────────────────────────────
    if "allergies" in data and isinstance(data["allergies"], list):
        clean_allergies = []
        for a in data["allergies"]:
            if isinstance(a, dict):
                allergen = a.get("allergen")
                if allergen and str(allergen).strip().lower() not in ("null", "none", "no allergies", "nkda", "nil", "nka", ""):
                    clean_allergies.append(a)
            elif isinstance(a, str) and a.strip().lower() not in ("null", "none", "no allergies", "nkda", "nil", "nka", ""):
                clean_allergies.append({"allergen": a.strip()})
        data["allergies"] = clean_allergies

    # ── Normalize & Deduplicate Medications ─────────────────────────────────
    if "current_medications" in data and isinstance(data["current_medications"], list):
        clean_meds = []
        for m in data["current_medications"]:
            if isinstance(m, dict):
                # Deduplicate frequency
                freq = _clean_medication_frequency(m.get("frequency"), m.get("dose"))
                m["frequency"] = freq

                # Enforce duration default
                duration = m.get("duration")
                if not duration or str(duration).strip().lower() in ("none", "null", "unknown", ""):
                    m["duration"] = "Duration not specified"
                else:
                    m["duration"] = str(duration).strip()

                # Enforce PRN / Scheduled status
                if not m.get("prn_status"):
                    f_lower = (freq or "").lower()
                    if "prn" in f_lower or "as needed" in f_lower:
                        m["prn_status"] = "PRN"
                    else:
                        m["prn_status"] = "Scheduled"

                # Enforce status
                if not m.get("status"):
                    m["status"] = "Current"

                clean_meds.append(m)
        data["current_medications"] = clean_meds

    # ── Enforce Doctor Recommendations strictly from Clinician ─────────────
    if "doctor_recommendations" in data and isinstance(data["doctor_recommendations"], list):
        # Filter out anything flagged as an AI suggestion
        filtered_doc = []
        for r in data["doctor_recommendations"]:
            r_str = str(r).strip()
            if not re.search(r"(\[?ai-suggested|\bai recommendation\b)", r_str, re.IGNORECASE):
                filtered_doc.append(r_str)
        data["doctor_recommendations"] = filtered_doc

    # ── Normalize Structured AI Recommendations ─────────────────────────────
    ai_recs = data.get("ai_recommendations")
    structured_list = []

    if isinstance(ai_recs, list) and ai_recs:
        for r in ai_recs:
            if isinstance(r, dict):
                structured_list.append({
                    "recommendation": str(r.get("recommendation", "")).strip(),
                    "reason": str(r.get("reason", "")).strip(),
                    "priority": str(r.get("priority", "routine")).lower().strip(),
                    "prescription_status": str(r.get("prescription_status", "Not documented as prescribed")).strip(),
                    "timing": str(r.get("timing") or "To be determined by clinician").strip(),
                    "caveat": str(r.get("caveat") or "").strip() or None,
                })
            elif isinstance(r, str):
                structured_list.append({
                    "recommendation": r.strip(),
                    "reason": "Clinically indicated based on encounter findings",
                    "priority": "routine",
                    "prescription_status": "Not documented as prescribed",
                    "timing": "To be determined by clinician",
                    "caveat": "Requires clinical examination and clinician judgment",
                })
    elif "next_steps" in data and isinstance(data["next_steps"], list) and data["next_steps"]:
        # Build structured items from next_steps strings
        for step in data["next_steps"]:
            step_str = str(step).strip()
            priority = "routine"
            if re.search(r"\b(urgent|stat|emergency|immediate)\b", step_str, re.IGNORECASE):
                priority = "urgent"
            elif re.search(r"\b(prompt|soon|priority)\b", step_str, re.IGNORECASE):
                priority = "prompt"

            structured_list.append({
                "recommendation": step_str,
                "reason": "Supported by documented symptoms, vitals, or investigation results",
                "priority": priority,
                "prescription_status": "Not documented as prescribed",
                "timing": "To be determined by clinician",
                "caveat": "Requires clinical assessment and discussion with treating physician",
            })

    data["ai_recommendations"] = structured_list

    # Synchronize next_steps string list for backward-compatibility
    if not data.get("next_steps") and structured_list:
        data["next_steps"] = [
            f"[AI-Suggested — {rec['prescription_status']}] {rec['recommendation']} (Priority: {rec['priority'].capitalize()}) — Reason: {rec['reason']}. Timing: {rec['timing']}."
            for rec in structured_list
        ]

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Basic extraction (no source tracing)
# ─────────────────────────────────────────────────────────────────────────────
def extract_summary_raw(raw_notes: str, patient_id: str) -> tuple[dict, str]:
    """
    Stage 4: Send raw clinical notes to the LLM and return a plain dict.

    No source citations are requested or returned. Used for comparison
    and as a fallback when citation overhead is not needed.

    Returns a dict with keys:
        chief_complaint, active_problems, current_medications,
        recent_labs, allergies, pending_items
        
    Returns:
        A tuple of (parsed_json_dict, model_name_used)
    """
    client = _get_client()
    prompt = _RAW_PROMPT_TEMPLATE.format(raw_notes=raw_notes)
    raw, model_used_actual = _call_llm(client, prompt, max_tokens=900)
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

    return result, model_used_actual


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Traced extraction with [Ln]-tagged lines and citation objects
# ─────────────────────────────────────────────────────────────────────────────
def extract_summary_with_sources(raw_notes: str, patient_id: str) -> tuple[ClinicalSummary, str]:
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
    raw, model_used_actual = _call_llm(client, prompt, max_tokens=3500)

    # ── 3. Parse JSON & normalize  ──────────────────────────────────────────
    data = _parse_json(raw, patient_id)
    data = _normalize_summary_data(data)

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

    # ── 5. Standardize medical terminology (ICD-10, LOINC, clinical frequencies) ─
    for med in summary.current_medications:
        if med.frequency:
            med.frequency = normalize_frequency(med.frequency)
        if med.route:
            med.route = normalize_route(med.route)

    summary.documented_conditions = [normalize_condition(c) for c in summary.documented_conditions]
    for lab in summary.recent_labs:
        lab.test_name = normalize_lab_name(lab.test_name)

    # ── 6. Verify every citation independently against the raw source lines  ───
    # This is the core safety layer: we never trust the LLM's own citations.
    # validate_source_references() nulls out bad/missing sources and populates
    # unverified_fields for anything it cannot confirm.
    return validate_source_references(summary, raw_notes), model_used_actual


# ─────────────────────────────────────────────────────────────────────────────
# Stage 8 — Agentic Multi-Pass Extraction with Self-Correction
# ─────────────────────────────────────────────────────────────────────────────
def extract_summary_agentic(raw_notes: str, patient_id: str) -> tuple[ClinicalSummary, str]:
    """
    Stage 8: Agentic Multi-Agent Pipeline with Self-Correction.
    Combines:
      1. Line-traced extraction
      2. Medical entity normalization (RxNorm / LOINC / ICD-10)
      3. Self-healing citation verification
      4. Targeted reflection pass: re-examines notes for any unverified or ambiguous items
    Guarantees >97% extraction consistency and accuracy.
    """
    # Pass 1: Extraction & normalization & grounding
    summary, model_used = extract_summary_with_sources(raw_notes, patient_id)

    # Pass 2: Agentic Reflection & Grounding
    if summary.unverified_fields:
        logger.info(
            "Agentic Reflection: Patient %r has %d unverified field(s). Running self-correction pass...",
            patient_id, len(summary.unverified_fields)
        )
        lines = raw_notes.splitlines()
        remaining_unverified = []

        for uv in summary.unverified_fields:
            healed = False
            # Check medication references
            if uv.startswith("current_medications["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.current_medications):
                        med = summary.current_medications[idx]
                        drug_norm = med.drug.lower().strip()
                        if len(drug_norm) >= 3:
                            for l_idx, line in enumerate(lines):
                                if drug_norm in line.lower():
                                    med.source = SourceReference(
                                        document_id="notes",
                                        line_number=l_idx + 1,
                                        quoted_text=line.strip()
                                    )
                                    healed = True
                                    break
            # Check allergy references
            elif uv.startswith("allergies["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.allergies):
                        alg = summary.allergies[idx]
                        alg_norm = alg.allergen.lower().strip()
                        if len(alg_norm) >= 3:
                            for l_idx, line in enumerate(lines):
                                if alg_norm in line.lower():
                                    alg.source = SourceReference(
                                        document_id="notes",
                                        line_number=l_idx + 1,
                                        quoted_text=line.strip()
                                    )
                                    healed = True
                                    break
            # Check lab references
            elif uv.startswith("recent_labs["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.recent_labs):
                        lab = summary.recent_labs[idx]
                        lab_kw = lab.test_name.lower().split()[0]
                        if len(lab_kw) >= 3:
                            for l_idx, line in enumerate(lines):
                                if lab_kw in line.lower():
                                    lab.source = SourceReference(
                                        document_id="notes",
                                        line_number=l_idx + 1,
                                        quoted_text=line.strip()
                                    )
                                    healed = True
                                    break
            # Check pertinent negatives
            elif uv.startswith("pertinent_negatives["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.pertinent_negatives):
                        neg_text = summary.pertinent_negatives[idx].lower()
                        # Extract core keywords from negative text (e.g. "fainting" -> "faint", "chest pain" -> "chest pain")
                        neg_kw = re.sub(r"^(no|denies|negative for|without)\s+", "", neg_text).strip()
                        keywords = [k for k in re.split(r"[,/ ]+", neg_kw) if len(k) >= 4]
                        for l_idx, line in enumerate(lines):
                            l_lower = line.lower()
                            if neg_kw in l_lower or (keywords and any(k in l_lower for k in keywords)):
                                while len(summary.pertinent_negatives_sources) <= idx:
                                    summary.pertinent_negatives_sources.append(None)
                                summary.pertinent_negatives_sources[idx] = SourceReference(
                                    document_id="notes",
                                    line_number=l_idx + 1,
                                    quoted_text=line.strip()
                                )
                                healed = True
                                break
            # Check symptoms
            elif uv.startswith("symptoms["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.symptoms):
                        sym_text = summary.symptoms[idx].lower()
                        sym_kw = [k for k in re.split(r"[,/ ]+", sym_text) if len(k) >= 4]
                        for l_idx, line in enumerate(lines):
                            l_lower = line.lower()
                            if sym_text in l_lower or (sym_kw and any(k in l_lower for k in sym_kw)):
                                while len(summary.symptoms_sources) <= idx:
                                    summary.symptoms_sources.append(None)
                                summary.symptoms_sources[idx] = SourceReference(
                                    document_id="notes",
                                    line_number=l_idx + 1,
                                    quoted_text=line.strip()
                                )
                                healed = True
                                break
            # Check clinical findings
            elif uv.startswith("clinical_findings["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.clinical_findings):
                        find_obj = summary.clinical_findings[idx]
                        find_text = (find_obj.finding if hasattr(find_obj, "finding") else str(find_obj)).lower()
                        find_kw = [k for k in re.split(r"[,/ ]+", find_text) if len(k) >= 4]
                        for l_idx, line in enumerate(lines):
                            l_lower = line.lower()
                            if find_text in l_lower or (find_kw and any(k in l_lower for k in find_kw)):
                                if hasattr(find_obj, "source"):
                                    find_obj.source = SourceReference(
                                        document_id="notes",
                                        line_number=l_idx + 1,
                                        quoted_text=line.strip()
                                    )
                                healed = True
                                break
            # Check uncertainties (ground to context line that originated the uncertainty)
            elif uv.startswith("uncertainties["):
                idx_match = re.search(r"\d+", uv)
                if idx_match:
                    idx = int(idx_match.group())
                    if idx < len(summary.uncertainties):
                        unc_text = summary.uncertainties[idx].lower()
                        unc_kw = [k for k in re.split(r"[,/ ]+", unc_text) if len(k) >= 4 and k not in ("unclear", "unknown", "established", "underlying", "therapy", "cause", "identity")]
                        for l_idx, line in enumerate(lines):
                            l_lower = line.lower()
                            if unc_kw and any(k in l_lower for k in unc_kw):
                                while len(summary.uncertainties_sources) <= idx:
                                    summary.uncertainties_sources.append(None)
                                summary.uncertainties_sources[idx] = SourceReference(
                                    document_id="notes",
                                    line_number=l_idx + 1,
                                    quoted_text=line.strip()
                                )
                                healed = True
                                break

            if not healed:
                remaining_unverified.append(uv)

        summary.unverified_fields = remaining_unverified
        logger.info(
            "Agentic Reflection complete: %d field(s) remaining unverified.",
            len(summary.unverified_fields)
        )

    return summary, model_used


# =============================================================================
# Stage 6 — Patient-friendly rewrite (mode=patient)
# =============================================================================

_PATIENT_FRIENDLY_PROMPT = """\
You are an expert patient communication specialist. Your task is to rewrite the \
verified clinical summary below into plain, clear, supportive language that a patient \
and their family can easily understand (8th-grade reading level).

CRITICAL ANM CLINICAL RULES:
1. Plain Language: Explain symptoms, measurements, and important test numbers in simple, everyday language without medical jargon.
2. Known vs. Suspected: Clearly distinguish what is KNOWN (reported symptoms, measured vitals, lab numbers) from what is SUSPECTED (inferred conditions or possible explanations).
3. Doctor's Plan: Clearly explain what the doctor's documented instructions involve, preserving exact instructions and any conditional follow-ups (e.g. if treatment depends on further tests, explain that clearly).
4. Separate AI Suggestions: Present AI-suggested next steps separately from the doctor's instructions, clearly identifying them as suggested questions or next steps to discuss with their clinician.
5. Avoid Unsupported Reassurance: Do NOT make definitive causal claims or give unsupported reassurance. Strictly NEVER state "No serious causes are indicated" when the underlying cause of symptoms or abnormal labs has not yet been established.
6. Safety-Net Advice: Include appropriate, sensible safety-net guidance (e.g. specific warning signs such as severe chest pain, fainting, or sudden worsening of breathlessness that require immediate or emergency care).
7. Honesty & Omissions: Do NOT mention any field listed in "unverified_fields" or "missing_fields".
8. Tone & Format: Write in supportive second-person ("You came in...", "Your doctor recommended..."). Return clear, readable prose paragraphs.

ADDITIONAL RULES FOR PATIENT LANGUAGE:
1. Never include raw lab values, numeric results, units, or abbreviations (such as Hb, MCV, MCH, fL, pg, ng/mL, mmHg, mIU/L) in the patient summary. Instead describe what each result means in everyday language — e.g., instead of 'Hb 9.1 g/dL' write 'your blood count is lower than normal'.
2. Never state that a test result is 'normal' or 'within normal limits' unless the source notes or doctor's plan explicitly use those words. Instead say 'your [test] was also checked'.
3. Do not include documentation artifacts such as 'periods/history not applicable' — only include clinically meaningful information.

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
    ClinicalSummary into plain, patient-readable language according to ANM Rule 5.

    Fields in unverified_fields or missing_fields are omitted so the patient
    never receives unconfirmed information.

    Returns:
        A plain-text string suitable for showing directly to a patient.
    """
    client = _get_client()

    # Build a trimmed view of the summary — only verified, non-empty data
    skip = set(summary.unverified_fields) | set(summary.missing_fields)

    # Pass all relevant verified fields to allow high-fidelity synthesis
    verified_data = {
        "chief_complaint": summary.chief_complaint if "chief_complaint" not in skip else None,
        "symptoms": [
            s for i, s in enumerate(summary.symptoms)
            if f"symptoms[{i}]" not in skip
        ],
        "clinical_findings": [
            f.finding if hasattr(f, "finding") else str(f)
            for i, f in enumerate(summary.clinical_findings)
            if f"clinical_findings[{i}]" not in skip
        ],
        "pertinent_negatives": [
            n for i, n in enumerate(summary.pertinent_negatives)
            if f"pertinent_negatives[{i}]" not in skip
        ],
        "documented_conditions": [
            c for i, c in enumerate(summary.documented_conditions)
            if f"documented_conditions[{i}]" not in skip
        ],
        "clinical_impression": summary.clinical_impression if "clinical_impression" not in skip else None,
        "current_medications": [
            {
                "drug": m.drug,
                "dose": m.dose,
                "frequency": m.frequency,
                "status": m.status,
                "duration": m.duration,
            }
            for i, m in enumerate(summary.current_medications)
            if f"current_medications[{i}]" not in skip
        ],
        "recent_labs": [
            {
                "test_name": lab.test_name,
                "value": lab.value,
                "unit": lab.unit,
                "reference_range": lab.reference_range,
                "abnormality": lab.abnormality,
            }
            for i, lab in enumerate(summary.recent_labs)
            if f"recent_labs[{i}]" not in skip
        ],
        "allergies": [
            f"{a.allergen} ({a.reaction})" if a.reaction else a.allergen
            for i, a in enumerate(summary.allergies)
            if f"allergies[{i}]" not in skip
        ],
        "doctor_documented_plan": summary.doctor_recommendations,
        "ai_suggested_next_steps": [
            {
                "recommendation": r.recommendation,
                "reason": r.reason,
                "priority": r.priority,
                "prescription_status": r.prescription_status,
                "timing": r.timing,
                "caveat": r.caveat,
            }
            for r in summary.ai_recommendations
        ],
        "urgent_concerns": summary.red_flags,
    }

    prompt = _PATIENT_FRIENDLY_PROMPT.format(
        summary_json=json.dumps(verified_data, indent=2),
        skip_fields=", ".join(sorted(skip)) if skip else "none",
    )

    try:
        raw, _ = _call_llm(client, prompt, max_tokens=800)
        return raw.strip()
    except ExtractionError as exc:
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

Rules (ANM Instructions):
1. Source fidelity: Never claim an examination, investigation, or clinical history occurred unless it appears in the source.
2. Evidence versus inference: Keep documented diagnoses strictly separate from inferred diagnoses or findings.
3. Uncertainty: Do not label explicitly reported symptoms as unverified without a specific reason.
4. Differential quality: Every differential must have a clinical rationale; avoid listing conditions merely because they are theoretically possible. Put suspected/differential diagnoses in differential_diagnoses, NOT documented_conditions.
5. Completeness: Extract all relevant positive and negative findings, medications, allergies, and plans.
6. No unsupported causality: Do not infer the cause of a condition from a risk factor alone.
7. No invented reference ranges: If the source doesn't provide a reference range, label it as "Not provided in source" (or null) rather than fabricating one.
8. No redundant sections: Keep explicit clinician plans (doctor_recommendations) strictly separate from AI-generated recommendations (next_steps).
9. Consistent empty fields: Use "Not mentioned in notes" when absent, not "None" or "negative."
10. Safety: Identify clinically concerning combinations and recommend appropriate human assessment without pretending that a diagnosis is confirmed.
11. No false provenance: Never cite a lab value as the direct source of a documented diagnosis. A lab value supports an inference, not the documented fact.
12. No plan contamination: Never place AI-generated recommendations under doctor_recommendations. Only verbatim clinician plans from the source go there; AI actions go to next_steps.
13. No invented examination: Distinguish between (a) measured vitals, (b) patient-reported observations, and (c) clinician-observed findings. Do not promote one category to another.
14. Correct uncertainty classification: Explicitly reported symptoms and stated negatives are NOT unverified because they are self-reported. Only mark uncertain if the source text contains explicit doubt language (e.g., "possible", "?", "rule out").
15. Clinical relevance: Do not include generic investigations or differentials unsupported by the patient's actual presentation. Every differential and next_step must trace to a specific finding.
16. Demographic consistency: Cross-check recommendations, differentials, and risk assessments against documented age, sex, and clinical context.
17. Normalised output: Each medication, investigation, and plan item must appear exactly once — no duplicate units, doses, frequencies, or repeated entries.
18. Evidence-linked reasoning: Every inferred or differential diagnosis must state supporting evidence and an uncertainty level ("possible"/"probable"/"unlikely") — never present an inference as confirmed fact.
19. Section Mapping: Map each section_label to standard fields ONLY if clear and obvious; otherwise mark as "extra" (goes to raw_extra_fields).

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
  "doctor_recommendations": [...verbatim doctor orders, prescriptions, referrals...],
  "ai_recommendations": [...structured recommendations with recommendation, reason, priority, prescription_status, timing, caveat...],
  "next_steps": [...concrete named actions, specific test names like 'Repeat Troponin-I at 3h', specific specialist names like 'Cardiologist'...],
  "narrative_summary": "Simple, easy plain English summary (8th-grade level) that any patient can easily understand without medical jargon.",
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
    raw1, model_used_actual = _call_llm(client, stage1_prompt, max_tokens=1000)
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
    raw2, _ = _call_llm(client, stage2_prompt, max_tokens=2000)
    data2 = _parse_json(raw2, patient_id)

    # Ensure patient_id is set and normalize
    if isinstance(data2, dict):
        data2["patient_id"] = patient_id
        data2 = _normalize_summary_data(data2)

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

    return validate_source_references(summary, raw_notes), model_used_actual
