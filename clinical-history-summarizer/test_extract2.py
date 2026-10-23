from app.services.extractor import extract_summary_agentic

notes = '''Patient: R.K., 47 years, Male
Date: 07 October 2026
Setting: OPD

Patient says he has been feeling very tired for the last 3-4 months. Gets breathless while climbing stairs to the 2nd floor, which he says was not the case earlier. Also says he feels his heart "beats fast" sometimes, especially after walking.

Diet is mostly vegetarian. Eats roti, rice, dal and vegetables regularly. Says he doesn't eat much outside food. No recent fever, cough or weight loss. Sleep okay.

He mentions that his wife has noticed he looks "pale" recently.

On questioning, he says he sometimes feels dizzy when getting up quickly. No fainting. No chest pain.

Periods/history not applicable.

BP 128/78 mmHg
Pulse 102/min
SpO2 98% RA

Hb 9.1 g/dL
MCV 71 fL
MCH 22 pg
Ferritin 7 ng/mL
Vitamin B12 312 pg/mL
Creatinine 0.9 mg/dL
TSH 2.4 mIU/L

Current meds:
- Pantoprazole 40 mg once daily — has been taking for "many months", exact start date unclear
- No other regular medicines

Allergy: says "one antibiotic once caused itching", doesn't remember the name. No breathing difficulty or swelling.

Plan discussed: further evaluation of low Hb, dietary history, check for possible source of blood loss, start treatment depending on evaluation. Follow-up after additional tests.'''

try:
    summary, model_used = extract_summary_agentic(raw_notes=notes, patient_id="DEMO-001")
    print(f"SUCCESS: Model used: {model_used}")
    print("\n--- NARRATIVE SUMMARY ---")
    print(summary.narrative_summary)
    print("\n--- DOCUMENTED CONDITIONS (should NOT contain inferred IDA) ---")
    print(summary.documented_conditions)
    print("\n--- CLINICAL IMPRESSION / DIFFERENTIALS ---")
    print("Impression:", summary.clinical_impression)
    print("Differentials:", summary.differential_diagnoses)
    print("\n--- PERTINENT NEGATIVES (should preserve fever, cough, weight loss, chest pain, fainting) ---")
    print(summary.pertinent_negatives)
    print("\n--- CURRENT MEDICATIONS (should have pantoprazole 40mg once daily, duration unclear, no duplicate freq) ---")
    for m in summary.current_medications:
        print(f"Med: {m.drug} | Dose: {m.dose} | Freq: {m.frequency} | Status: {m.status} | Duration: {m.duration} | PRN: {m.prn_status}")
    print("\n--- ALLERGIES ---")
    for a in summary.allergies:
        print(f"Allergy: {a.allergen} | Reaction: {a.reaction}")
    print("\n--- DOCTOR DOCUMENTED PLAN (preserves exact clinician intent, no AI recs) ---")
    for d in summary.doctor_recommendations:
        print(f"Doc: {d}")
    print("\n--- AI SUGGESTED NEXT STEPS (structured, labeled not prescribed) ---")
    for r in summary.ai_recommendations:
        print(f"AI Rec: [{r.priority.upper()}] {r.recommendation} | Reason: {r.reason} | Status: {r.prescription_status} | Timing: {r.timing} | Caveat: {r.caveat}")
    print("\n--- UNCERTAINTIES & RED FLAGS ---")
    print("Uncertainties:", summary.uncertainties)
    print("Red flags:", summary.red_flags)
    print("Unverified fields:", summary.unverified_fields)
except Exception as e:
    import traceback
    traceback.print_exc()
