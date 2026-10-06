import os
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY environment variable not set")

client = OpenAI(
  base_url="https://api.groq.com/openai/v1",
  api_key=api_key,
)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "test_cases"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATE = """
You are a brilliant clinical data generator and evaluator. We are testing a clinical extraction pipeline that parses medical notes into a strict 13-section JSON schema.

I need you to generate a unique synthetic clinical note and its corresponding EXACT "Gold Standard" JSON extraction.

The note should be of style: {style}

The strict rules for extraction are:
1. No inference goes into DOCUMENTED CONDITIONS (only explicit diagnoses).
2. No missing information becomes a negative finding (e.g., if allergies aren't mentioned, leave empty array).
3. Every extracted item MUST have a source containing `document_id: "notes"`, exact `line_number` (1-indexed), and exact `quoted_text` from the note.
4. Uncertain information (e.g. "not sure if 5 or 10mg") MUST go into `uncertainties` and its fields should be marked appropriately.
5. Medications must always be extracted when present, including drug, dose, frequency, route, status, and uncertainty.
6. Clinical reasoning goes only into CLINICAL IMPRESSION / DIFFERENTIAL DIAGNOSES.

Generate your response strictly as a JSON object with two top-level keys:
- "raw_notes": A string containing the synthetic medical note (make sure to include newlines).
- "gold_summary": A JSON object representing the expected `ClinicalSummary` schema.

The `gold_summary` MUST have these keys (even if empty lists/null):
- patient_id (string, e.g., "CASE_{index}")
- chief_complaint (string or null)
- chief_complaint_source (object or null)
- documented_conditions (list of strings)
- documented_conditions_sources (list of objects)
- symptoms (list of strings)
- symptoms_sources (list of objects)
- clinical_findings (list of strings)
- clinical_findings_sources (list of objects)
- pertinent_negatives (list of strings)
- pertinent_negatives_sources (list of objects)
- risk_factors (list of strings)
- risk_factors_sources (list of objects)
- current_medications (list of objects with drug, dose, route, frequency, status, uncertainty, source)
- allergies (list of objects with allergen, reaction, status, source)
- recent_labs (list of objects with test_name, value, unit, reference_range, abnormality, date, source)
- clinical_impression (string or null)
- clinical_impression_source (object or null)
- differential_diagnoses (list of strings)
- differential_diagnoses_sources (list of objects)
- pending_items (list of strings)
- red_flags (list of strings)
- red_flags_sources (list of objects)
- uncertainties (list of strings)
- uncertainties_sources (list of objects)
- unverified_fields (list of strings - usually empty for gold standard)
- missing_fields (list of strings)
- raw_extra_fields (object)

Make sure the citations in `gold_summary` perfectly match the lines and text in `raw_notes`.

Respond ONLY with valid JSON.
"""

STYLES = [
    "highly structured and clear",
    "messy, poorly formatted, lots of abbreviations",
    "missing critical information like allergies and medications",
    "contains conflicting or wrong data (e.g., patient says one dose, GP letter says another)",
    "heavy on clinical reasoning vs documented facts, requiring the model to separate inference from facts",
    "contains ambiguous information requiring verification (e.g., 'not sure if allergic to penicillin or amoxicillin')"
]

def generate_case(index: int):
    style = STYLES[index % len(STYLES)]
    prompt = PROMPT_TEMPLATE.format(style=style, index=index)
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        file_path = OUTPUT_DIR / f"case_{index}.json"
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Generated case {index} ({style})")
    except Exception as e:
        print(f"Failed to parse case {index}: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=16)
    parser.add_argument("--end", type=int, default=110)
    args = parser.parse_args()
    
    print(f"Generating cases {args.start} to {args.end}...")
    for i in range(args.start, args.end + 1):
        generate_case(i)
        time.sleep(2) # rate limit protection

if __name__ == "__main__":
    main()
