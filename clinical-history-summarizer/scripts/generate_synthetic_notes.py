#!/usr/bin/env python3
"""
Generates 15 synthetic patient case files in data/synthetic_notes/.

These are entirely fictional patients — no real medical data.
Each file (case_1.txt ... case_15.txt) contains a realistic but synthetic
clinical note mixing:
  - Admission note style
  - Medication lists
  - Lab results
  - Allergy section
  - Pending tests / referrals

Run from project root:
  python scripts/generate_synthetic_notes.py
"""

import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic_notes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    # case_1 — straightforward ED admission, clear data
    (
        "case_1.txt",
        """Patient: SYNTH-001 | DOB: 1965-03-14 | MRN: SYN0001
Date of Admission: 2024-09-15 | Ward: Emergency Department

CHIEF COMPLAINT:
Patient presents with acute chest pain radiating to the left arm, onset 2 hours ago.

ALLERGIES:
- Penicillin: anaphylaxis (documented 2019)
- Aspirin: GI upset

CURRENT MEDICATIONS:
- Metformin 500mg twice daily (oral)
- Atorvastatin 40mg once at night (oral)
- Amlodipine 5mg once daily (oral)

HISTORY OF PRESENT ILLNESS:
60-year-old male with known T2DM and hypertension presents with chest pain.
Pain described as 8/10, pressure-like, with diaphoresis and nausea.
No fever. No cough. No shortness of breath at rest.

ACTIVE PROBLEMS:
1. Acute coronary syndrome (rule-out)
2. Type 2 Diabetes Mellitus — on Metformin
3. Hypertension — on Amlodipine

RECENT INVESTIGATIONS:
ECG: ST depression in V4-V6 (done at 14:30 today)
Troponin I: 0.08 ng/mL (HIGH) — collected 2024-09-15 at 14:45
HbA1c: 7.9% — dated 2024-08-01
Serum Creatinine: 1.1 mg/dL — dated 2024-09-15
Blood Glucose: 210 mg/dL (HIGH) — dated 2024-09-15

PENDING:
- Repeat Troponin at 3h (due 17:45)
- Cardiology consult requested
- Echo scheduled for tomorrow morning
""",
    ),
    # case_2 — scattered notes, ambiguous medication dose
    (
        "case_2.txt",
        """--- INPATIENT NOTE ---
Pt: SYNTH-002 | Age: 45F | Adm: 2024-10-02

cc: breathlessness on exertion x 3 weeks

PMH: Bronchial asthma since childhood. Hypothyroidism diagnosed 2018.

Drug allergies: NKDA (no known drug allergies)

Meds (from patient report — not verified against pharmacy):
Salbutamol inhaler PRN
Levothyroxine — dose not recalled by patient
Budesonide inhaler (formoterol combination) — 1 puff BD

Examination: SpO2 92% on room air. Bilateral wheeze. No clubbing.

Labs:
- TSH: 8.2 mIU/L (HIGH) — 2024-10-01  [ref: 0.4–4.0]
- FT4: 10.1 pmol/L (LOW)
- Peak Flow: 220 L/min (predicted 420 L/min for age/sex)
- CBC: WBC 9.1, Hb 12.3 g/dL, Plt 210

Plan:
1. Nebulise salbutamol now, repeat Q4H PRN
2. Oral prednisolone 40mg daily x 5 days
3. Endocrinology review for thyroid — pending appointment
4. Spirometry — to be arranged outpatient
""",
    ),
    # case_3 — elderly patient, polypharmacy, illegible dose on one med
    (
        "case_3.txt",
        """WARD ROUND NOTE — Medical Ward B
Patient: SYNTH-003 | 78M | Adm date: 2024-09-28

Presenting complaint: Fall at home, confusion, reduced oral intake x 2 days.

Allergies: Sulfonamides (rash). Codeine (excessive sedation, documented 2021).

Current medications (brought in by family, from home blister pack):
- Ramipril 5mg OD
- Bisoprolol 2.5mg OD
- Furosemide 40mg OD
- Spironolactone [dose illegible on pack]
- Warfarin — dose per INR chart (not brought in)
- Omeprazole 20mg OD
- Donepezil 10mg ON

Active diagnoses:
- Ischemic heart disease
- Heart failure with reduced ejection fraction (EF 35% — echo 2024-04)
- Atrial fibrillation (on anticoagulation)
- Vascular dementia

Labs today:
- INR: 4.2 (HIGH — supratherapeutic) — 2024-09-28
- Na: 128 mmol/L (LOW) — hyponatraemia
- K: 5.8 mmol/L (HIGH)
- Creatinine: 198 umol/L (HIGH) — baseline ~140 umol/L
- eGFR: 29 mL/min/1.73m2

Pending:
- CT Head (to rule out intracranial bleed — given high INR and fall)
- Urine cultures
- Hold Warfarin — monitor INR daily
- Cardiology input re: anticoagulation in setting of high INR and fall risk
""",
    ),
    # case_4 — paediatric case
    (
        "case_4.txt",
        """PAEDIATRIC ED NOTE
Patient: SYNTH-004 | Age: 7 years, Male | Weight: 22kg
Date: 2024-09-20

CC: Fever 39.5°C x 2 days, ear pain right side, reduced hearing.

Allergies: Amoxicillin (urticaria — age 4)

Medications: None regular.

History: Mother reports child pulling at right ear for 2 days.
Fever up to 39.8°C at home. No vomiting. Eating reduced. School-going.

Examination:
- Tympanic membrane: Right TM red, bulging. Left TM normal.
- Throat: Mild erythema, no exudate.
- Lymph nodes: Right submandibular lymphadenopathy.

Active problems:
- Acute otitis media, right ear (bacterial, probable)

Labs: Not done (clinical diagnosis).

Management:
- Azithromycin 250mg oral once daily x 5 days (given amoxicillin allergy)
- Paracetamol 360mg Q6H PRN for fever/pain
- Ibuprofen 200mg Q8H PRN (with food)
- Follow up in 3 days or sooner if worsening
- Audiometry if not resolved in 4 weeks

Pending:
- Review in 3 days
- Audiometry if prolonged — outpatient referral
""",
    ),
    # case_5 — post-op note, multiple pending items
    (
        "case_5.txt",
        """POST-OPERATIVE NOTE — Day 1
Patient: SYNTH-005 | 55F | DOB: 1969-07-22
Procedure: Laparoscopic cholecystectomy for acute cholecystitis
Date of surgery: 2024-09-18

Allergies: Latex (contact dermatitis — documented, latex-free protocol in place)
           Morphine (nausea and vomiting)

Pre-op medications (home):
- Metformin 1000mg BD — HELD peri-operatively
- Ramipril 5mg OD — HELD peri-operatively
- Rosuvastatin 20mg ON — continued

Post-op medications:
- Paracetamol 1g QID IV x 24h then oral
- Ondansetron 4mg IV TDS PRN nausea
- Enoxaparin 40mg SC OD (DVT prophylaxis)
- Tramadol 50mg oral Q6H PRN (morphine allergy — tramadol used instead)

Current status:
- Tolerating sips, no nausea
- Drain output 30mL sero-sanguineous
- Wound: intact, no bleeding
- Ambulating with help

Active problems:
- Day 1 post laparoscopic cholecystectomy
- T2DM (metformin held)
- Hypertension (ramipril held)
- Latex allergy (protocol active)

Labs (post-op day 1):
- Hb: 10.2 g/dL (LOW)
- WBC: 14.3 x10^9/L (HIGH — expected post-operative)
- CRP: 87 mg/L (HIGH)
- LFTs: ALT 42, AST 38, ALP 95, Bilirubin 18 — all within normal limits

Pending:
- Histopathology of gallbladder specimen
- Resume Metformin when eating fully
- Resume Ramipril when BP stable
- Drain removal if output <20mL/24h
- Dietician referral — post-op
""",
    ),
    # case_6 — psychiatric co-morbidity, complex social history
    (
        "case_6.txt",
        """ADMISSION SUMMARY — Internal Medicine
Patient: SYNTH-006 | 34F | Adm: 2024-10-05

Reason for admission: Deliberate self-harm (superficial lacerations), now medically stable.
Also presenting with poorly controlled Type 1 Diabetes.

Allergies: No known drug allergies.

Psychiatric medications (confirmed with psychiatrist on call):
- Sertraline 100mg once daily oral
- Quetiapine 50mg at night oral
- Diazepam 5mg PRN (not to exceed 10mg/day)

Diabetes medications:
- Insulin Glargine 24 units SC at night
- Insulin Novorapid — sliding scale (see chart)

Active problems:
- Type 1 Diabetes Mellitus — poorly controlled (HbA1c 10.2% — 2024-09-01)
- Major Depressive Disorder — under psychiatric care
- Borderline Personality Disorder (diagnosed 2021)

Labs:
- Glucose: 21.4 mmol/L (HIGH) — 2024-10-05
- HbA1c: 10.2% — 2024-09-01
- Ketones (urine): negative — 2024-10-05
- Creatinine: 82 umol/L
- eGFR: >90 mL/min

Pending:
- Psychiatric review — expected morning ward round tomorrow
- Diabetes nurse educator review
- Social work referral (housing instability noted)
- Safe discharge planning — not for same-day discharge
""",
    ),
    # case_7 — oncology patient, multiple complex medications
    (
        "case_7.txt",
        """ONCOLOGY WARD ROUND
Patient: SYNTH-007 | 62M | Adm: 2024-10-03

Diagnosis: Non-small cell lung cancer (NSCLC), adenocarcinoma, Stage IIIB
EGFR mutation: Exon 19 deletion (confirmed 2024-08-15)

Chief complaint: Worsening dyspnoea and haemoptysis x 1 week.

Allergies: Cisplatin (nephrotoxicity — previous cycle)

Current oncology medications:
- Osimertinib 80mg oral once daily (EGFR-targeted therapy)
- Dexamethasone 4mg BD oral (anti-oedema)
- Ondansetron 8mg TDS oral PRN

Supportive medications:
- Omeprazole 20mg OD
- Enoxaparin 60mg SC OD (VTE prophylaxis — active cancer)
- Morphine SR 10mg BD (pain)
- Morphine IR 5mg Q4H PRN (breakthrough)

Active problems:
- NSCLC Stage IIIB on Osimertinib — cycle 3
- Haemoptysis (under investigation)
- Moderate pleural effusion (right) — on imaging 2024-10-02
- VTE prophylaxis

Labs:
- Hb: 9.8 g/dL (LOW — chronic disease anaemia)
- WBC: 3.2 x10^9/L (LOW)
- Plt: 88 x10^9/L (LOW)
- Creatinine: 105 umol/L
- LDH: 320 U/L (HIGH)

Imaging: CT Chest 2024-10-02 — increased right pleural effusion, stable primary tumour.

Pending:
- Bronchoscopy — scheduled 2024-10-07
- Haematology review (pancytopenia)
- Repeat CT in 6 weeks
- Palliative care team involvement — referral made
""",
    ),
    # case_8 — brief triage note (incomplete data — good test for unverified_fields)
    (
        "case_8.txt",
        """TRIAGE NOTE — ED
Time: 03:42
Patient: SYNTH-008 | Approx 50s, Male | No ID presented

CC: Found unconscious by bystanders. GCS 10/15 on arrival.

Bystander reports possible alcohol ingestion. Unknown medical history.

No medication list available.

Allergies: Unknown.

Vitals:
- BP: 88/52 mmHg (LOW)
- HR: 118 bpm
- SpO2: 94% on 4L O2
- Temp: 36.1°C
- RR: 22

Brief exam: Pupils equal and reactive. No external trauma. Breath smells of alcohol.

Labs pending (sent):
- Glucose stat: 3.1 mmol/L (LOW)
- Blood cultures x2
- Toxicology screen
- ABG — result awaited
- Ethanol level — result awaited

Plan:
- IV dextrose 50mL of 50% — given now
- IV fluids — 0.9% NaCl 1L wide open
- Monitor, reassess GCS in 30 mins
""",
    ),
    # case_9 — pregnancy-related admission
    (
        "case_9.txt",
        """OBSTETRIC ADMISSION NOTE
Patient: SYNTH-009 | 28F | Gravida 2 Para 1 | POG: 32 weeks
Date: 2024-10-04

CC: Severe headache, visual disturbance, and pedal oedema x 1 day.

Allergies: NKDA.

Medications (antenatal):
- Folic acid 5mg OD
- Ferrous sulphate 200mg TDS
- Low-dose aspirin 75mg OD (started at 12 weeks for pre-eclampsia risk)

Examination:
- BP: 158/102 mmHg (HIGH)
- Urine dipstick: 3+ protein
- Oedema: bilateral pitting oedema up to knees

Active problems:
- Severe pre-eclampsia (32 weeks gestation)
- Gestational thrombocytopaenia (platelet count 89 x10^9/L)

Labs:
- Plt: 89 x10^9/L (LOW) — 2024-10-04
- Creatinine: 74 umol/L
- ALT: 62 U/L (HIGH — upper limit 40)
- AST: 71 U/L (HIGH)
- LDH: 480 U/L (HIGH)
- Uric acid: 412 umol/L (HIGH)
- 24h urine protein: 4.2g/day (HIGH) — pending formal lab confirmation

Management started:
- MgSO4 4g IV loading dose — given
- MgSO4 1g/h IV infusion — ongoing
- Labetalol 200mg oral BD started
- Corticosteroids: Betamethasone 12mg IM x2 (fetal lung maturity)
- Continuous CTG monitoring

Pending:
- Formal 24h urine protein result
- Obstetric ultrasound — fetal biometry and Doppler
- Anaesthesia review (for possible emergency CS)
- Neonatology briefing — planned
""",
    ),
    # case_10 — diabetic ketoacidosis
    (
        "case_10.txt",
        """DKA PROTOCOL — ACUTE MEDICINE
Patient: SYNTH-010 | 19M | DOB: 2005-06-11
Date: 2024-10-05 | Time: 11:20

CC: Vomiting, abdominal pain, polyuria, polydipsia x 2 days. T1DM known.

Allergies: None known.

Home medications:
- Insulin Degludec 20 units SC at night
- Insulin Aspart — mealtime, dose per sliding scale

Diagnosis: Diabetic Ketoacidosis (moderate-severe)

Clinical findings:
- GCS: 15/15
- BP: 96/62 mmHg
- HR: 124 bpm
- RR: 28 (Kussmaul breathing)
- SpO2: 98%
- Breath: Fruity odour

Labs:
- Glucose: 31.2 mmol/L (HIGH) — 2024-10-05 11:25
- Ketones (blood): 4.8 mmol/L (HIGH, moderate-severe DKA threshold >3.0)
- pH: 7.18 (LOW — acidosis)
- Bicarbonate: 10 mmol/L (LOW)
- K: 3.2 mmol/L (LOW — requires replacement before insulin)
- Na: 133 mmol/L (LOW, corrected)
- Creatinine: 118 umol/L (slightly elevated, likely dehydration)

Management (DKA protocol):
- IV 0.9% NaCl 1L over 1h — running
- KCl 40mmol added to next bag (K replacement)
- Actrapid insulin infusion 0.1 units/kg/h (after K replacement confirmed)
- Strict fluid balance
- Hourly glucose and ketone monitoring
- NBM currently

Pending:
- Trigger factor search (infection? missed insulin dose?)
- ECG (hypokalaemia monitoring)
- Repeat ABG in 2h
- Diabetes team review — requested
""",
    ),
    # case_11 — renal failure, complex background
    (
        "case_11.txt",
        """NEPHROLOGY CONSULT NOTE
Patient: SYNTH-011 | 67F | Date: 2024-10-01

Referral reason: Worsening renal function — creatinine rise from 145 to 312 umol/L over 6 weeks.

Allergies: Contrast dye (anaphylactoid reaction — documented). NSAIDs (worsens renal function — avoid).

Background:
- CKD Stage 3b (baseline Cr ~145, eGFR ~35) — diagnosed 2021
- T2DM on insulin
- Hypertension
- Cardiac failure (EF 40% on echo 2023)

Current medications:
- Insulin Glargine 18 units SC ON
- Amlodipine 10mg OD
- Furosemide 80mg OD
- Carvedilol 12.5mg BD
- Allopurinol 100mg OD
- Calcium carbonate 500mg TDS with meals (phosphate binder)
- Erythropoietin 4000 units SC weekly

Labs (today):
- Creatinine: 312 umol/L (HIGH) — 2024-10-01
- eGFR: 16 mL/min/1.73m2 (LOW — CRITICAL decline)
- K: 6.1 mmol/L (HIGH — hyperkalaemia)
- Hb: 9.1 g/dL (LOW — anaemia of CKD)
- Urine protein:creatinine ratio 480 mg/mmol (HIGH — significant proteinuria)
- eGFR trend: 35 → 28 → 16 over 6 weeks (rapid decline)

Assessment: Acute-on-chronic kidney disease. Likely cause: volume depletion (furosemide overdose?) vs. disease progression vs. ATN.

Pending:
- Renal ultrasound (avoid contrast given allergy)
- Review furosemide dose — consider reducing
- AV fistula planning referral (if trajectory continues)
- Dietitian referral (low-potassium, low-phosphate diet)
- Start sodium bicarbonate 500mg BD for acidosis
""",
    ),
    # case_12 — stroke patient
    (
        "case_12.txt",
        """STROKE UNIT ADMISSION
Patient: SYNTH-012 | 71M | Adm: 2024-09-30 02:15

CC: Sudden onset right arm and leg weakness, facial droop, slurred speech — 1 hour prior to arrival.

Allergies: Warfarin (prior GI bleed — do not re-challenge).

Medications (home):
- Clopidogrel 75mg OD (secondary prevention — prior TIA 2022)
- Atorvastatin 80mg ON
- Lisinopril 10mg OD
- Amlodipine 5mg OD

Exam (on arrival):
- NIHSS: 14 (moderate-severe stroke)
- Right hemiparesis (3/5 power)
- Right facial droop
- Dysarthria
- No neglect, visual fields intact

Imaging:
- CT Brain (non-contrast) 2024-09-30 02:40: No haemorrhage. Hyperdense MCA sign left.
- CT Angiography: Left MCA M1 occlusion.

Active problems:
- Acute ischaemic stroke — left MCA territory
- Hypertension
- Hyperlipidaemia
- Prior TIA (2022)

Thrombolysis:
- IV Alteplase 0.9mg/kg administered 2024-09-30 03:05 (onset to needle: 50 mins)
- BP post-thrombolysis: 148/88 — monitoring Q15min

Labs:
- Glucose: 6.8 mmol/L
- INR: 1.0 (not anticoagulated at admission)
- Plt: 210 x10^9/L
- LDL: 3.8 mmol/L (HIGH)

Pending:
- Mechanical thrombectomy assessment by IR team — urgent
- MRI Brain with DWI — when stable
- Swallow assessment — SALT referral
- Physio + OT assessment
- Echo to rule out cardioembolic source
- Neurology review
""",
    ),
    # case_13 — HIV patient, complex drug interactions
    (
        "case_13.txt",
        """HIV MEDICINE CLINIC NOTE
Patient: SYNTH-013 | 38M | Date: 2024-10-04

CC: Routine follow-up. New complaint: peripheral neuropathy both feet.

Allergies: Nevirapine (Stevens-Johnson syndrome — 2019, do NOT re-challenge).

ART regimen (stable x 2 years):
- Tenofovir alafenamide (TAF) 25mg OD
- Emtricitabine (FTC) 200mg OD
- Dolutegravir 50mg OD

Other medications:
- Cotrimoxazole 960mg OD (PCP prophylaxis — CD4 was 180 at last count)
- Vitamin B complex OD

CD4 and viral load:
- CD4: 320 cells/uL (up from 180 six months ago) — 2024-10-04
- Viral load: <20 copies/mL (undetectable) — 2024-10-04

Other labs:
- Creatinine: 89 umol/L
- eGFR: 82 mL/min
- HBsAg: Negative
- Lipid panel: LDL 3.1, HDL 0.9, TG 2.8 (HIGH) — 2024-10-04

Active problems:
- HIV-1 infection, on ART, virologically suppressed
- Peripheral neuropathy (new) — ?cause (ART vs. nutritional vs. other)
- Hypertriglyceridaemia

Pending:
- EMG/nerve conduction study — referral made
- Neurology review
- Review PCP prophylaxis — consider stopping if CD4 remains >200 x 3 months
- Fenofibrate 145mg OD — consider for triglycerides (discuss with patient)
""",
    ),
    # case_14 — geriatric falls assessment
    (
        "case_14.txt",
        """GERIATRIC FALLS ASSESSMENT
Patient: SYNTH-014 | 82F | Date: 2024-10-02

CC: Third fall in 6 weeks. No loss of consciousness. Minor bruising.

Allergies: Aspirin (asthma exacerbation). ACE inhibitors (angioedema — documented).

Medications (home — verified with carer):
- Bisoprolol 5mg OD
- Lercanidipine 10mg OD
- Simvastatin 20mg ON
- Omeprazole 20mg OD
- Mirtazapine 15mg ON (for depression + sleep)
- Zopiclone 3.75mg ON PRN (patient using nightly — CONCERN: fall risk)
- Calcium + Vitamin D 500mg/800IU OD

Falls risk factors identified:
- Polypharmacy (7 medications)
- Zopiclone use — nightly (not PRN as prescribed) — HIGH FALL RISK
- Postural hypotension: BP sitting 138/82, standing 104/62 (>20mmHg systolic drop)
- Mirtazapine — sedating, contributes to fall risk

Active problems:
- Recurrent falls (x3 in 6 weeks)
- Postural hypotension
- Depression (on Mirtazapine)
- Osteoporosis (DEXA T-score -2.8 lumbar — 2023)

Labs:
- Vitamin D: 32 nmol/L (LOW — target >75)
- PTH: 68 pg/mL (HIGH — secondary hyperparathyroidism)
- TSH: 2.1 mIU/L (normal)
- Creatinine: 95 umol/L

Pending:
- Zopiclone taper and discontinuation plan
- Physiotherapy — balance and gait training
- DEXA repeat (last 2023)
- Consider bisphosphonate for osteoporosis
- OT home assessment
- Increase Vitamin D to 2000IU OD
""",
    ),
    # case_15 — intentionally messy note (tests robustness)
    (
        "case_15.txt",
        """quick note - rushed ward round
pt synth-015, ~40yo female, came in yesterday
main issue: rash all over body after starting new antibiotic
dont know which one - family says something for UTI
possibly amoxiclav? or trimethoprim? patient not sure

she has lupus (SLE) - on hydroxychloroquine 200mg daily
also takes something for blood pressure - losartan i think, maybe 50mg
and methotrexate weekly (low dose) for rheumatoid complication

examination: widespread maculopapular rash trunk and arms
no mucosal involvement, no blistering
vitals stable

we stopped the antibiotic (whichever one it was)
antihistamine given - cetirizine 10mg oral

labs: CBC normal, CRP 22 (mildly elevated), eosinophils 0.9 (borderline high)
creatinine ok - 88, LFTs normal

plan:
- keep monitoring rash
- dermatology referral if not improving
- need to clarify WHICH antibiotic caused this (critical for allergy documentation)
- methotrexate hepatotoxicity monitoring (lfts ok today)
- rheumatology aware

note: dont know her full med list - only going on what family said
""",
    ),
]


def main():
    print(f"Writing {len(CASES)} synthetic case files to: {OUTPUT_DIR}\n")
    for filename, content in CASES:
        path = OUTPUT_DIR / filename
        path.write_text(content.strip())
        print(f"  ✓ {filename} ({len(content.strip().splitlines())} lines)")
    print(f"\nDone. Run scripts/evaluate.py after creating gold_summaries/.")


if __name__ == "__main__":
    main()
