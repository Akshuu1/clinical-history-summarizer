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

from app.models.summary import ClinicalSummary
from app.services.validator import validate_source_references

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
You are a senior clinical documentation assistant. Read the line-tagged \
clinical notes below and return ONE valid JSON object only — no prose, no \
markdown fences.

Every [Ln] tag is a line number. Use those numbers in citations.

─── ANM CLINICAL INSTRUCTIONS & RULES ───────────────────────────────────────
1. Source fidelity: Never claim an examination, investigation, or clinical history occurred unless it appears in the source.
2. Evidence versus inference: Keep documented diagnoses (documented_conditions) strictly separate from inferred diagnoses or findings. Do not infer diagnoses from abnormal lab results or clinical signs.
3. Uncertainty: Do not label explicitly reported symptoms as unverified without a specific reason. Only mark as uncertainty if the patient or clinician explicitly expressed doubt.
4. Differential quality: Every differential must have a clinical rationale supported by the text; avoid listing conditions merely because they are theoretically possible. Suspected/differential diagnoses go to differential_diagnoses.
5. Completeness: Extract all relevant positive and negative findings, medications, allergies, and plans thoroughly.
6. No unsupported causality: Do not infer the cause of a condition from a risk factor alone (e.g., do not attribute dyspnoea to smoking history unless explicitly stated).
7. No invented reference ranges: If the source doesn't provide a reference range, label it as "Not provided in source" (or null) rather than fabricating one.
8. No redundant sections: Keep explicit clinician plans ("doctor_recommendations") strictly separate from AI-generated recommendations ("next_steps").
9. Consistent empty fields: Use "Not mentioned in notes" when absent, not "None" or "negative" (unless the clinician explicitly wrote "None" or "negative").
10. Safety: Identify clinically concerning combinations (red_flags) and recommend appropriate human assessment without pretending that a diagnosis is confirmed.
11. No false provenance: Never cite a lab value as the direct source of a documented diagnosis. A lab value can support an inference but cannot prove that a diagnosis was documented by the clinician.
12. No plan contamination: Never place AI-generated recommendations under "doctor_recommendations". That field is ONLY for verbatim clinician plans found in the source. AI-generated actions go exclusively into "next_steps".
13. No invented examination: Carefully distinguish between (a) measured/recorded vitals, (b) patient-reported observations, and (c) clinician-observed findings. Label each accordingly; do not promote one category to another.
14. Correct uncertainty classification: Explicitly reported symptoms and stated negatives are NOT unverified merely because they are self-reported. Only mark a finding as uncertain if the source text itself contains doubt language (e.g., "possible", "query", "?", "rule out").
15. Clinical relevance: Avoid generic investigations or differentials that are not supported by the patient's actual presentation. Every item in differential_diagnoses and next_steps must be traceable to a specific finding in the notes.
16. Demographic consistency: Cross-check all recommendations, differentials, and risk assessments against the patient's documented age, sex, and clinical context. Do not suggest age-inappropriate screening or sex-inappropriate conditions.
17. Normalised output: Remove duplicate units, duplicate doses, duplicate frequencies, and repeated plan items. Each medication, investigation, and plan item should appear exactly once.
18. Evidence-linked reasoning: Every inferred or differential diagnosis must include (a) the supporting evidence from the note, and (b) an explicit uncertainty level ("possible", "probable", "unlikely") — never state an inference as fact.

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

  "clinical_findings": ["string"],
  "clinical_findings_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "pertinent_negatives": ["string"],
  "pertinent_negatives_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "risk_factors": ["string"],
  "risk_factors_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "current_medications": [
    {{"drug":"string","dose":"string or null","route":"string or null","frequency":"string or null",
      "status":"Current|Started|Stopped|Held|PRN|Historical|Unknown","uncertainty":"string or null",
      "source":{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null}}
  ],

  "recent_labs": [
    {{"test_name":"string","value":"string or null","unit":"string or null",
      "reference_range":"string or null","date":"string or null","abnormality":"string or null",
      "source":{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null}}
  ],

  "allergies": [
    {{"allergen":"string","reaction":"string or null","status":"string or null",
      "source":{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null}}
  ],

  "clinical_impression": "string or null",
  "clinical_impression_source": {{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}} or null,

  "differential_diagnoses": [
    "string — concise diagnosis with clinical rationale as a single string (not an object), e.g. 'Iron deficiency anaemia — microcytic fatigue'"
  ],
  "differential_diagnoses_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "pending_items": ["string"],

  "red_flags": ["string"],
  "red_flags_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "uncertainties": ["string"],
  "uncertainties_sources": [{{"document_id":"notes","line_number":<int>,"quoted_text":"<verbatim>"}}],

  "unverified_fields": [],

  "doctor_recommendations": [
    "Every explicit recommendation, prescription, referral, or instruction the doctor documented. Extract verbatim from the plan/management section. Explicitly preserve exact medicine names, test names, and doctor roles. One string per recommendation."
  ],

  "next_steps": [
    "Concrete suggested actions and recommendations. ALWAYS NAME THE EXACT TEST, SPECIALIST, OR CHECKUP so the patient and clinician know exactly what to do next. Examples: 'Diagnostic Test: Repeat Troponin-I blood test at 3 hours to monitor heart muscle.', 'Specialist Consultation: Urgent review by a Cardiologist (heart specialist).', 'Vital Monitoring: Measure blood pressure, heart rate, and oxygen saturation.', 'Medication Verification: Confirm exact prescribed dose of Amlodipine (5mg vs 10mg) with GP records.' Give specific named actions, not vague advice."
  ],

  "narrative_summary": "Write a clear, patient-friendly summary in very simple everyday language (8th-grade reading level) so any patient or family member can understand it completely without medical confusion.
    Summarise simply and clearly:
    (1) What brought the patient in and their symptoms in plain words (e.g. chest pressure radiating to the left arm with sweating),
    (2) What the doctor found and what the test numbers mean in simple words (e.g. 'The heart strain enzyme test, Troponin-I, was 0.06 (higher than the normal 0.04 limit), showing heart muscle stress; ECG showed heart electrical changes'),
    (3) All prescribed or continued medicines by name (e.g. Metformin for diabetes, Ramipril and Amlodipine for blood pressure),
    (4) Exactly what needs to happen next (naming the specific tests and doctors: repeating the blood test in 3 hours, and having a heart specialist / cardiologist review).
    Use plain, reassuring, easy-to-read language — no unexplained medical jargon. Do NOT invent facts not in the notes."
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


def _normalize_summary_data(data: dict) -> dict:
    """
    Defensively normalizes string-list fields in data.
    If the LLM returned structured objects (such as {"dx": ..., "rationale": ...})
    for differential_diagnoses or conditions instead of plain strings, convert
    them into clean strings to prevent schema validation crashes.
    """
    if not isinstance(data, dict):
        return data

    string_list_fields = [
        "documented_conditions",
        "symptoms",
        "clinical_findings",
        "pertinent_negatives",
        "risk_factors",
        "differential_diagnoses",
        "pending_items",
        "red_flags",
        "uncertainties",
        "doctor_recommendations",
        "next_steps",
    ]

    for field in string_list_fields:
        if field in data and isinstance(data[field], list):
            normalized_list = []
            for item in data[field]:
                if isinstance(item, str):
                    normalized_list.append(item)
                elif isinstance(item, dict):
                    dx = item.get("dx") or item.get("diagnosis") or item.get("condition") or item.get("name")
                    rationale = item.get("rationale") or item.get("reason") or item.get("description")
                    if dx and rationale:
                        normalized_list.append(f"{dx} — {rationale}")
                    elif dx:
                        normalized_list.append(str(dx))
                    elif rationale:
                        normalized_list.append(str(rationale))
                    else:
                        normalized_list.append(", ".join(f"{k}: {v}" for k, v in item.items() if v))
                elif item is not None:
                    normalized_list.append(str(item))
            data[field] = normalized_list

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

    # ── 5. Verify every citation independently against the raw source lines  ───
    # This is the core safety layer: we never trust the LLM's own citations.
    # validate_source_references() nulls out bad/missing sources and populates
    # unverified_fields for anything it cannot confirm.
    return validate_source_references(summary, raw_notes), model_used_actual


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
        "documented_conditions": summary.documented_conditions,
        "current_medications": [
            {
                "drug": m.drug,
                "dose": m.dose,
                "frequency": m.frequency,
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
        "allergies": [
            a.allergen
            for i, a in enumerate(summary.allergies)
            if f"allergies[{i}]" not in skip
        ],
        "pending_items": summary.pending_items,
    }

    # Remove top-level fields that are flagged as unverified/missing
    if "chief_complaint" in skip:
        verified_data["chief_complaint"] = None
    if "documented_conditions" in skip:
        verified_data["documented_conditions"] = []

    prompt = _PATIENT_FRIENDLY_PROMPT.format(
        summary_json=json.dumps(verified_data, indent=2),
        skip_fields=", ".join(sorted(skip)) if skip else "none",
    )

    # Use _call_llm so we get /no_think and retry-on-429
    try:
        raw, _ = _call_llm(client, prompt, max_tokens=600)
        return raw
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
