# Clinical History Summarizer — Living Context File
> Paste this file into every AI session. It is the source of truth.

## What this system does
Takes messy multi-source clinical notes (typed/pasted), runs them through a structured LLM extraction pipeline, and produces a verified, source-traceable clinical summary. Every claim in the output is either:
- **Cited** (line number in the original notes that confirms it), or
- **Flagged as unverified** (explicitly, never silently dropped)

This is the core safety property. The system never invents facts.

## Stack
| Layer | Technology |
|---|---|
| Backend API | Python FastAPI |
| Database | PostgreSQL 16 (SQLAlchemy + Alembic) |
| LLM | Google Gemini 2.0 Flash |
| Frontend | Next.js (React) |
| Demo UI | Streamlit (optional local testing) |

## Key pipeline steps (in order)
1. **Input** — paste or upload raw notes, labs, medication lists
2. **Normalise** — strip/tag every line with L1, L2, L3... for citation
3. **Extract** — LLM call returns strict JSON (ClinicalSummary schema) with line-number citations per field
4. **Validate** — `validator.py` checks that each cited line actually contains the claimed text
5. **Flag** — fields without valid citations go to `unverified_fields` list
6. **Store** — raw notes + verified summary saved in PostgreSQL
7. **Display** — side-by-side view: original notes | structured summary

## ClinicalSummary JSON schema
```json
{
  "patient_id": "string",
  "chief_complaint": { "value": "string", "source_line": 5, "source_text": "..." },
  "active_problems": [{ "value": "string", "source_line": 12, "source_text": "..." }],
  "current_medications": [{ "name": "string", "dose": "string", "frequency": "string", "source_line": 18, "source_text": "..." }],
  "allergies": [{ "substance": "string", "reaction": "string", "source_line": 3, "source_text": "..." }],
  "recent_labs": [{ "test": "string", "result": "string", "date": "string", "source_line": 25, "source_text": "..." }],
  "pending_items": [{ "value": "string", "source_line": 31, "source_text": "..." }],
  "unverified_fields": ["field_name_1", "field_name_2"]
}
```

## Non-goals (this build)
- No handwriting OCR
- No real WhatsApp delivery (stub endpoint only)
- No ABDM / multi-hospital integration (architecture doc only)
- No authentication / RBAC
- No real patient data, ever

## Evaluation target
- Precision + Recall on allergies & active_medications > 85%
- Zero hallucinations in the test set (system cites or flags, never invents)
- 15 synthetic cases in `data/synthetic_notes/`, hand-labelled gold in `data/gold_summaries/`
