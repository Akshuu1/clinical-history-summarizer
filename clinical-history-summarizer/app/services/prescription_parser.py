"""
Prescription and Clinical Document Ingestion Service.

Extracts high-fidelity clinical text from ANY uploaded prescription:
- PDF documents (via pypdf)
- Prescription Images / Scans (PNG, JPG, JPEG, WEBP via Multimodal Vision AI)
- Plain Text files (TXT, MD)
"""

import io
import re
import base64
import logging
from typing import Optional
import pypdf
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

VISION_MODELS = [
    "minimax/minimax-m3.1-flash:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
]


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract embedded text from a PDF document page by page."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    extracted_pages = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            extracted_pages.append(text.strip())
    
    return "\n\n".join(extracted_pages).strip()


def _transcribe_image_with_vision(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """
    Transcribe a prescription or medical document image verbatim using Multimodal Vision LLM.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to transcribe prescription images.")

    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    prompt = (
        "You are an expert clinical medical transcriptionist. "
        "Transcribe all text, numbers, dates, patient details, clinical symptoms, "
        "diagnoses, medications (drug name, dose, frequency, duration), lab tests, "
        "and doctor instructions from this prescription image verbatim line by line. "
        "Format line-by-line so each medical entry is unambiguous. "
        "Do NOT invent or infer unwritten information. "
        "Output ONLY the transcribed clinical text — no introductory or concluding chatter."
    )

    last_error = None
    for model in VISION_MODELS:
        try:
            logger.info("Transcribing prescription image using vision model: %s", model)
            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
                    ]
                }],
                max_tokens=2000,
                extra_headers={
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Clinical History Summarizer",
                },
                extra_body={"reasoning": {"effort": "none"}},
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw:
                return raw
        except Exception as exc:
            logger.warning("Vision model %s failed: %s", model, exc)
            last_error = exc

    raise RuntimeError(f"All vision models failed to transcribe prescription image: {last_error}")


def _detect_patient_id(text: str, filename: str) -> Optional[str]:
    """Attempt to extract patient ID or name from transcribed text or filename."""
    # Check for Pt: or Patient ID: patterns
    match = re.search(r"(?:Pt|Patient|PID|ID|MRN)\s*[:#\-]?\s*([A-Za-z0-9_\-]+)", text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        if len(candidate) >= 2 and candidate.isalnum():
            return candidate.upper()

    # Fallback to sanitized filename
    base = re.sub(r"\.[^.]+$", "", filename)
    clean_base = re.sub(r"[^A-Za-z0-9_\-]", "_", base).strip("_")
    if clean_base:
        return clean_base[:20].upper()

    return None


def extract_text_from_prescription(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None
) -> tuple[str, str]:
    """
    Ingests any prescription or medical file (PDF, Image, Text)
    and returns (extracted_text, suggested_patient_id).
    """
    fn_lower = filename.lower()
    ct_lower = (content_type or "").lower()

    extracted_text = ""

    # 1. PDF File
    if fn_lower.endswith(".pdf") or "pdf" in ct_lower:
        extracted_text = _extract_text_from_pdf(file_bytes)
        if not extracted_text:
            # If PDF contains no embedded text (likely scanned images)
            try:
                # Extract first page image if available
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages:
                    for img in page.images:
                        transcription = _transcribe_image_with_vision(img.data, mime_type="image/png")
                        if transcription:
                            extracted_text += transcription + "\n\n"
            except Exception as e:
                logger.warning("Scanned PDF vision fallback failed: %s", e)

        if not extracted_text:
            raise ValueError("The uploaded PDF does not contain extractable text or readable images.")

    # 2. Image File (JPG, PNG, WEBP, etc.)
    elif any(fn_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]) or "image/" in ct_lower:
        mime = "image/jpeg" if (fn_lower.endswith(".jpg") or fn_lower.endswith(".jpeg")) else "image/png"
        extracted_text = _transcribe_image_with_vision(file_bytes, mime_type=mime)

    # 3. Plain Text File
    else:
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="replace")

    extracted_text = extracted_text.strip()
    if not extracted_text:
        raise ValueError(f"Could not extract any clinical text from '{filename}'.")

    suggested_patient_id = _detect_patient_id(extracted_text, filename) or "PT-NEW"
    return extracted_text, suggested_patient_id
