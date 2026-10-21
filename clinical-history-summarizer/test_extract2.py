from app.services.extractor import extract_summary_with_sources

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
    summary = extract_summary_with_sources(raw_notes=notes, patient_id="DEMO-001")
    print("SUCCESS: JSON Parsed properly without truncation or quote issues.")
    print("Extracted narrative:")
    print(summary.narrative_summary)
except Exception as e:
    import traceback
    traceback.print_exc()
