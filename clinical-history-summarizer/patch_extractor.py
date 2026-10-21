import sys

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Define the new blocks
    exceptions_block = """class ExtractionError(Exception):
    \"\"\"Raised when the LLM response cannot be parsed or schema-validated.\"\"\"
    pass

class RateLimitExceededError(ExtractionError):
    \"\"\"Raised when the LLM provider rate limit is exceeded.\"\"\"
    pass

class JSONParseError(ExtractionError):
    \"\"\"Raised when the LLM response is invalid JSON after all cleanup attempts.\"\"\"
    pass"""

    get_client_block = """def _get_client():
    \"\"\"Build an OpenAI-compatible client pointed at the configured provider for OpenRouter fallback.\"\"\"
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return None
    
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )"""

    call_llm_gemini_block = """def _call_llm_gemini(prompt: str, max_tokens: int = 3500) -> str:
    import google.generativeai as genai
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
        
    genai.configure(api_key=api_key)
    model_name = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
    # If the user sets OpenRouter fallback model list, just use flash
    if "," in model_name or "openrouter" in model_name or ":" in model_name:
        model_name = "gemini-2.0-flash"
        
    model = genai.GenerativeModel(model_name)
    
    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                )
            )
            raw = response.text
            if not raw:
                raise ExtractionError("Gemini returned an empty response.")
            return raw
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "quota" in msg.lower():
                if attempt < 2:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning("Gemini API rate limit hit — waiting %ds (attempt %d/3)…", wait_time, attempt + 1)
                    time.sleep(wait_time)
                    continue
                raise RateLimitExceededError(f"Gemini API rate limit exceeded. Please retry in a moment. ({exc})")
            
            # For 503 or other transient errors
            if "503" in msg or "overloaded" in msg.lower() or "502" in msg:
                if attempt < 2:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning("Gemini API overloaded — waiting %ds (attempt %d/3)…", wait_time, attempt + 1)
                    time.sleep(wait_time)
                    continue
            
            if attempt == 2:
                raise ExtractionError(f"Gemini API call failed after retries: {exc}")
                
    raise RateLimitExceededError("Unexpected retry loop exit.")"""

    call_llm_openrouter_block = """def _call_llm_openrouter(client, prompt: str, max_tokens: int = 3500) -> str:
    \"\"\"
    Secondary/fallback function: Make a single LLM call to OpenRouter.
    (Kept intact but not primary due to observed free-tier reliability issues).
    \"\"\"
    if not client:
        raise ExtractionError("No OpenRouter API key found for fallback.")
        
    messages = [
        {"role": "system", "content": "You are a specialized clinical extraction assistant. Respond ONLY with the requested JSON object. Do not include reasoning or chain of thought."},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(3):
        try:
            extra_body = {}
            primary_model = MODEL
            if "," in MODEL:
                models_list = [m.strip() for m in MODEL.split(",") if m.strip()]
                models_list = models_list[:3]
                primary_model = models_list[0]
                extra_body = {
                    "route": "fallback",
                    "models": models_list
                }
                
            response = client.chat.completions.create(
                model=primary_model,
                max_tokens=max_tokens,
                messages=messages,
                extra_headers={
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Clinical History Summarizer",
                },
                extra_body=extra_body if extra_body else None
            )
            raw = (response.choices[0].message.content or "").strip()
            if not raw:
                raise ExtractionError("Model returned an empty response. The upstream model may be overloaded.")
            return raw
        except ExtractionError:
            raise
        except Exception as exc:
            msg = str(exc)
            is_rate_limit = "429" in msg or "rate_limit" in msg.lower()
            is_overloaded = "503" in msg or "502" in msg or "overloaded" in msg.lower()
            
            if (is_rate_limit or is_overloaded) and attempt < 2:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    "OpenRouter API issue hit (%s) — waiting %ds before retry (attempt %d/3)…",
                    'rate limit' if is_rate_limit else 'overloaded',
                    wait_time,
                    attempt + 1
                )
                time.sleep(wait_time)
                continue
                
            if is_rate_limit:
                raise RateLimitExceededError("OpenRouter API rate limit exceeded. Free-tier quota exhausted.")
            if is_overloaded:
                raise ExtractionError("The model API is currently overloaded or unavailable. Please try again in a moment.")
            raise ExtractionError(f"API call failed: {exc}")
    raise ExtractionError("Unexpected retry loop exit.")"""

    call_llm_block = """def _call_llm(client, prompt: str, max_tokens: int = 3500) -> str:
    \"\"\"
    Main LLM dispatcher. Uses Gemini SDK directly as primary if key is available.
    Falls back to OpenRouter if Gemini fails or is unconfigured.
    \"\"\"
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return _call_llm_gemini(prompt, max_tokens)
        except Exception as exc:
            logger.warning("Gemini API call failed: %s. Falling back to OpenRouter...", exc)
            if not client:
                raise
            
    return _call_llm_openrouter(client, prompt, max_tokens)"""

    parse_json_block = """def _parse_json(raw: str, patient_id: str) -> dict:
    \"\"\"Parse raw LLM text as JSON with robust cleaning of reasoning traces and fences.\"\"\"
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

    logger.error(
        "JSON parse failed for patient_id=%r.\nRaw response:\n%s",
        patient_id, raw
    )
    raise JSONParseError(
        f"LLM returned invalid or malformed JSON for patient '{patient_id}'."
    )"""

    import re

    # Replace from class ExtractionError(Exception): up to the end of _parse_json
    pattern = re.compile(r'class ExtractionError\(Exception\):.*?def _parse_json[^\n]+\n(?:.*?)(?=\n# ─────────────────────────────────────────────────────────────────────────────\n# Stage 4)', re.DOTALL)
    
    replacement = f"{exceptions_block}\n\n\n{get_client_block}\n\n\n{call_llm_gemini_block}\n\n\n{call_llm_openrouter_block}\n\n\n{call_llm_block}\n\n\n{parse_json_block}\n\n"
    
    new_content = pattern.sub(replacement, content)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("Patched successfully")

if __name__ == "__main__":
    patch_file("app/services/extractor.py")
