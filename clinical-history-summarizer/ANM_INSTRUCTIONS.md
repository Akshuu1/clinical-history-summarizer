# ANM Clinical Extraction & Safety Instructions

These 18 core clinical instructions govern the extraction, summarization, and validation pipeline for clinical notes within the Health Report System. They are enforced in prompt engineering, citation validation, schema mappings, and clinical safety layers.

---

## The 18 Core ANM Rules

### 1. Source Fidelity
> **Rule:** Never claim an examination, investigation, or clinical history occurred unless it appears in the source.
- **Guidance:** If an examination (e.g., palpation, auscultation), test (e.g., ECG, CBC), or clinical history was not written in the note, do not assume or invent that it was performed.
- **Enforcement:** Every extracted item must cite an exact line number (`line_number`) and verbatim quoted text (`quoted_text`).

### 2. Evidence versus Inference
> **Rule:** Keep documented diagnoses separate from inferred diagnoses.
- **Guidance:** 
  - Confirmed, explicitly documented diagnoses go to `documented_conditions`.
  - Objective test results (e.g., "ST depression", "elevated troponin") go to `clinical_findings` or `recent_labs`.
  - Do NOT infer a diagnosis (e.g., diagnosing "Acute Coronary Syndrome") simply because a lab or finding is abnormal, unless the clinician explicitly diagnosed it.

### 3. Uncertainty
> **Rule:** Do not label explicitly reported symptoms as unverified without a specific reason.
- **Guidance:** When a patient or clinician reports a symptom (e.g., "headache for 3 days"), record it under `symptoms`. Only flag uncertainty in `uncertainties` if the patient or clinician explicitly expresses doubt (e.g., "patient unsure if fever occurred").

### 4. Differential Quality
> **Rule:** Every differential must have a clinical rationale; avoid listing conditions merely because they are theoretically possible.
- **Guidance:** Only include conditions in `differential_diagnoses` that are explicitly considered by the clinician (e.g., "query PE", "r/o appendicitis") or clearly substantiated by documented clinical signs. Do not hallucinate broad textbook differential lists.

### 5. Completeness
> **Rule:** Extract all relevant positive and negative findings, medications, allergies, and plans.
- **Guidance:** Capture the complete clinical picture without omission:
  - Positive symptoms and clinical signs.
  - Pertinent negatives explicitly ruled out (e.g., "denies chest pain", "no pedal edema").
  - Current medications, dosages, frequencies, and statuses.
  - Allergies with reactions.
  - Clinician management plans and pending tasks.

### 6. No Unsupported Causality
> **Rule:** Do not infer the cause of a condition from a risk factor alone.
- **Guidance:** A documented risk factor (e.g., "40 pack-year smoking history") belongs in `risk_factors`. Do NOT state that the patient's cough or dyspnoea was "caused by smoking" unless the treating clinician explicitly established that causal relationship.

### 7. No Invented Reference Ranges
> **Rule:** If the source doesn't provide a reference range, label it as unavailable rather than fabricating one.
- **Guidance:** Lab reference ranges vary significantly across laboratories, assays, and clinical contexts. When `reference_range` is not written in the clinical document, set it to `"Not provided in source"` or `null`. Never invent standard laboratory reference ranges.

### 8. No Redundant Sections
> **Rule:** Keep explicit clinician plans separate from AI-generated recommendations.
- **Guidance:**
  - `doctor_recommendations`: Holds verbatim clinician instructions, prescriptions, referrals, and advice documented in the note.
  - `next_steps`: Holds AI-generated suggestions strictly to fill unrecorded clinical categories (e.g., "Vital signs not recorded — measure BP, HR, RR, SpO2"). Never duplicate doctor plans into AI suggestions.

### 9. Consistent Empty Fields
> **Rule:** Use "Not mentioned in notes" when absent, not "None" or "negative."
- **Guidance:** "None" implies the clinician checked and found zero/absent (e.g., "Allergies: None"). If a clinical category was omitted entirely, record it as `"Not mentioned in notes"` so readers know the information was missing rather than negative.

### 10. Safety
> **Rule:** Identify clinically concerning combinations and recommend appropriate human assessment without pretending that a diagnosis is confirmed.
- **Guidance:** When concerning findings co-occur (e.g., chest pain with diaphoresis, or severe hypertension with headache), highlight them under `red_flags` and recommend urgent evaluation by a human physician, while maintaining humility and never asserting an unconfirmed medical diagnosis.

---

## New Prompt-Level Quality Rules (Rules 11–18)

### 11. No False Provenance
> **Rule:** Never cite a lab value as the source of a documented diagnosis.
- **Guidance:** A lab result can support an inference but cannot prove a clinician documented a diagnosis. If a clinician documents "Diabetes mellitus" and a lab shows elevated HbA1c, the diagnosis source is the clinician's note text — not the lab value. Citation must point to the text where the clinician states the diagnosis.

### 12. No Plan Contamination
> **Rule:** Never place AI-generated recommendations under `doctor_recommendations`.
- **Guidance:** `doctor_recommendations` is a verbatim extraction field — it only holds what the treating clinician wrote in the plan section of the notes. Any AI-generated clinical suggestion (however valid) must be placed exclusively in `next_steps`. Cross-contamination makes the output untrustworthy.

### 13. No Invented Examination
> **Rule:** Clearly distinguish between measured vitals, patient-reported observations, and clinician-observed findings.
- **Guidance:**
  - **Measured vitals**: Recorded numbers (BP 140/90 mmHg, Temp 38.2°C) — go to `clinical_findings` with source.
  - **Patient-reported**: "Patient says he had a fever at home" — label as patient-reported in `symptoms`.
  - **Clinician-observed**: "On examination: bibasal crepitations" — go to `clinical_findings`.
  - Do not present a patient's self-report as a clinician-observed finding.

### 14. Correct Uncertainty Classification
> **Rule:** Explicitly reported symptoms and documented negatives are NOT unverified merely because they are self-reported.
- **Guidance:** Self-reported symptoms are valid clinical data. Only mark a finding as uncertain if the source text itself contains explicit doubt language such as "possible", "query", "?", "rule out", "uncertain", or "patient unsure". The threshold is the source text, not the type of informant.

### 15. Clinical Relevance
> **Rule:** Avoid generic investigations and differentials not supported by the patient's specific presentation.
- **Guidance:** Every item in `differential_diagnoses` and `next_steps` must be traceable to at least one specific documented finding. A vague possibility (e.g., adding "malignancy" to every differential) without documented supporting findings is a hallucination in the clinical sense and must be excluded.

### 16. Demographic Consistency
> **Rule:** Cross-check all recommendations against the patient's documented age, sex, and clinical context.
- **Guidance:** Do not recommend cervical screening for male patients, prostate checks for female patients, or paediatric doses for adults. If demographic data is absent from the note, acknowledge the gap in `missing_fields` rather than making age/sex assumptions.

### 17. Normalised Output
> **Rule:** Remove duplicate units, doses, frequencies, and repeated plan items.
- **Guidance:** Each medication, investigation, and plan item must appear exactly once in the output. Common sources of duplication include Stage 1 vs Stage 2 merging, multi-document notes, and LLM repetition artefacts. The normalisation post-processing step in `_normalize_summary_data` handles structural deduplication, but the LLM must also avoid generating duplicates in the first place.

### 18. Evidence-Linked Reasoning
> **Rule:** Every inferred diagnosis must state supporting evidence and a clear uncertainty level.
- **Guidance:** Do not state "Patient has heart failure" when the note says "bilateral leg swelling and raised JVP." Instead, write: "Possible heart failure (bilateral leg swelling, raised JVP documented — clinician has not confirmed this diagnosis)." Use uncertainty levels: `"possible"`, `"probable"`, or `"unlikely"`. Never present an inference as confirmed fact.

---

## System Integration & Locations
These rules are implemented in:
1. `app/services/extractor.py` — `_SOURCES_PROMPT_TEMPLATE` (Stage 5 Extraction Prompt) — **18 rules**
2. `app/services/extractor.py` — `_STAGE2_MAP_PROMPT` (Stage 7 Schema Mapping Prompt) — **19 rules (+ section mapping)**
3. `app/services/extractor.py` — `_call_llm_openrouter` System Instructions
4. `app/services/validator.py` — Verbatim citation and line number validation
5. `app/models/summary.py` — Schema definitions for unverified, missing, and extra fields


---

## The 10 Core ANM Rules

### 1. Source Fidelity
> **Rule:** Never claim an examination, investigation, or clinical history occurred unless it appears in the source.
- **Guidance:** If an examination (e.g., palpation, auscultation), test (e.g., ECG, CBC), or clinical history was not written in the note, do not assume or invent that it was performed.
- **Enforcement:** Every extracted item must cite an exact line number (`line_number`) and verbatim quoted text (`quoted_text`).

### 2. Evidence versus Inference
> **Rule:** Keep documented diagnoses separate from inferred diagnoses.
- **Guidance:** 
  - Confirmed, explicitly documented diagnoses go to `documented_conditions`.
  - Objective test results (e.g., "ST depression", "elevated troponin") go to `clinical_findings` or `recent_labs`.
  - Do NOT infer a diagnosis (e.g., diagnosing "Acute Coronary Syndrome") simply because a lab or finding is abnormal, unless the clinician explicitly diagnosed it.

### 3. Uncertainty
> **Rule:** Do not label explicitly reported symptoms as unverified without a specific reason.
- **Guidance:** When a patient or clinician reports a symptom (e.g., "headache for 3 days"), record it under `symptoms`. Only flag uncertainty in `uncertainties` if the patient or clinician explicitly expresses doubt (e.g., "patient unsure if fever occurred").

### 4. Differential Quality
> **Rule:** Every differential must have a clinical rationale; avoid listing conditions merely because they are theoretically possible.
- **Guidance:** Only include conditions in `differential_diagnoses` that are explicitly considered by the clinician (e.g., "query PE", "r/o appendicitis") or clearly substantiated by documented clinical signs. Do not hallucinate broad textbook differential lists.

### 5. Completeness
> **Rule:** Extract all relevant positive and negative findings, medications, allergies, and plans.
- **Guidance:** Capture the complete clinical picture without omission:
  - Positive symptoms and clinical signs.
  - Pertinent negatives explicitly ruled out (e.g., "denies chest pain", "no pedal edema").
  - Current medications, dosages, frequencies, and statuses.
  - Allergies with reactions.
  - Clinician management plans and pending tasks.

### 6. No Unsupported Causality
> **Rule:** Do not infer the cause of a condition from a risk factor alone.
- **Guidance:** A documented risk factor (e.g., "40 pack-year smoking history") belongs in `risk_factors`. Do NOT state that the patient's cough or dyspnoea was "caused by smoking" unless the treating clinician explicitly established that causal relationship.

### 7. No Invented Reference Ranges
> **Rule:** If the source doesn't provide a reference range, label it as unavailable rather than fabricating one.
- **Guidance:** Lab reference ranges vary significantly across laboratories, assays, and clinical contexts. When `reference_range` is not written in the clinical document, set it to `"Not provided in source"` or `null`. Never invent standard laboratory reference ranges.

### 8. No Redundant Sections
> **Rule:** Keep explicit clinician plans separate from AI-generated recommendations.
- **Guidance:**
  - `doctor_recommendations`: Holds verbatim clinician instructions, prescriptions, referrals, and advice documented in the note.
  - `next_steps`: Holds AI-generated suggestions strictly to fill unrecorded clinical categories (e.g., "Vital signs not recorded — measure BP, HR, RR, SpO2"). Never duplicate doctor plans into AI suggestions.

### 9. Consistent Empty Fields
> **Rule:** Use "Not mentioned in notes" when absent, not "None" or "negative."
- **Guidance:** "None" implies the clinician checked and found zero/absent (e.g., "Allergies: None"). If a clinical category was omitted entirely, record it as `"Not mentioned in notes"` so readers know the information was missing rather than negative.

### 10. Safety
> **Rule:** Identify clinically concerning combinations and recommend appropriate human assessment without pretending that a diagnosis is confirmed.
- **Guidance:** When concerning findings co-occur (e.g., chest pain with diaphoresis, or severe hypertension with headache), highlight them under `red_flags` and recommend urgent evaluation by a human physician, while maintaining humility and never asserting an unconfirmed medical diagnosis.

---

## System Integration & Locations
These rules are implemented in:
1. `app/services/extractor.py` — `_SOURCES_PROMPT_TEMPLATE` (Stage 5 Extraction Prompt)
2. `app/services/extractor.py` — `_STAGE2_MAP_PROMPT` (Stage 7 Schema Mapping Prompt)
3. `app/services/extractor.py` — `_call_llm_openrouter` System Instructions
4. `app/services/validator.py` — Verbatim citation and line number validation
5. `app/models/summary.py` — Schema definitions for unverified, missing, and extra fields
