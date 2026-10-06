## Project Name
Clinical History Summarizer

## Goal
Take messy, multi-source clinical notes (synthetic data only — no real 
patient data at any stage) and produce a structured clinical summary 
where every field is either (a) cited to an exact source line, or 
(b) explicitly flagged as unverified if no clear source exists. 
The core value is trustworthiness and traceability, not just fluent 
summarization.

## Tech Stack
- Backend: Python, FastAPI
- Database: PostgreSQL + SQLAlchemy + Alembic
- AI: Anthropic API (claude-sonnet-4-6) for structured extraction
- Frontend: Streamlit
- Evaluation: custom precision/recall scoring script against 
  hand-written gold-standard summaries

## Current Status
[Update this after every stage — right now: "Just starting, no code written."]

## Explicit Non-Goals (this build)
- No handwriting OCR
- No real WhatsApp message delivery (demo stub only)
- No multi-hospital data sharing / ABDM integration (architecture only)
- No authentication or multi-user access control
- No real patient data under any circumstances

## Core Schema Fields (see /app/models/summary.py once created)
chief_complaint, active_problems, current_medications, recent_labs, 
allergies, pending_items, unverified_fields — each field (except 
unverified_fields) should support a source citation.

## Current Status
Stage 5 complete — source-traced extraction pipeline working end-to-end.
Stage 6 complete — PostgreSQL storage layer set up and migrated.

## Database (Stage 6)
PostgreSQL via SQLAlchemy ORM + Alembic migrations.

### Tables
- **patients** — `id` (VARCHAR 64, PK = patient_id string), `created_at`
- **source_notes** — `id`, `patient_id` (FK → patients.id), `raw_text`, `created_at`
- **summaries** — `id`, `patient_id` (FK), `source_note_id` (FK, nullable),
  `summary_json` (JSON — full ClinicalSummary), `verified_count`,
  `unverified_count`, `model_used`, `created_at`

### Running migrations
```
cd clinical-history-summarizer
alembic upgrade head
```

### Checking current migration state
```
alembic current
alembic history
```

### Generating a new migration after model changes
```
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```
