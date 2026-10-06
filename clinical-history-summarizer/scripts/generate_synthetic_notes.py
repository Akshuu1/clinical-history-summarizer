#!/usr/bin/env python3
"""
Generates 15 synthetic patient case files into data/synthetic_notes/.

Cases are grouped by realism tier:
  cases  1-5  : clear, well-organised notes
  cases  6-10 : moderately messy (abbreviations, mixed order, inconsistent formatting)
  cases 11-15 : deliberately ambiguous in at least one field (tests confidence-flagging)

Run from the project root:
  python scripts/generate_synthetic_notes.py
"""

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic_notes"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# CASES 1–5: Clear, well-organised notes
# ---------------------------------------------------------------------------

CASE_1 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient ID: A1
Date: 12 September 2024
Clinician: Dr. R. Patel (Internal Medicine)

CHIEF COMPLAINT:
Patient A1 presents with a 3-day history of worsening shortness of breath
and bilateral ankle swelling.

ACTIVE PROBLEMS:
1. Decompensated congestive heart failure (known EF 30%)
2. Type 2 diabetes mellitus, poorly controlled
3. Stage 3 chronic kidney disease (baseline creatinine 145 umol/L)

CURRENT MEDICATIONS:
- Furosemide 40 mg oral once daily
- Carvedilol 6.25 mg oral twice daily
- Metformin 500 mg oral twice daily (held today pending contrast)
- Insulin glargine 18 units subcutaneous at bedtime

ALLERGIES:
Penicillin — causes hives and facial swelling (documented 2019)
Contrast dye — anaphylactoid reaction (documented 2022)

RECENT INVESTIGATIONS:
BNP: 1,240 pg/mL (HIGH) — collected today
Creatinine: 198 umol/L (HIGH, above baseline) — collected today

PENDING:
Echo requested to reassess ejection fraction.
Cardiology review booked for next Tuesday.
"""

CASE_2 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient ID: A2
Date of Admission: 04 October 2024
Ward: Respiratory

CHIEF COMPLAINT:
Worsening breathlessness on exertion over the past 3 weeks.
Also reports a dry cough and reduced exercise tolerance.

ACTIVE PROBLEMS:
1. Bronchial asthma — known since childhood, partially controlled
2. Hypothyroidism — diagnosed 2018

CURRENT MEDICATIONS:
Salbutamol inhaler — 2 puffs as needed
Budesonide/formoterol combination inhaler — 1 puff twice daily
Levothyroxine 75 mcg oral once daily (morning, fasting)

ALLERGIES:
No known drug allergies.

RECENT INVESTIGATIONS:
TSH: 9.1 mIU/L (HIGH, target 0.4–4.0) — collected 01 October 2024
Peak flow: 195 L/min (50% of predicted for age and sex)

PENDING:
Spirometry to be arranged as outpatient.
Endocrinology referral for thyroid optimisation.
"""

CASE_3 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient: B7
Admission date: 22 September 2024
Admitting team: General Surgery

CHIEF COMPLAINT:
Right iliac fossa pain for 18 hours, worse on movement,
associated with nausea and one episode of vomiting.
Temperature 38.1 degrees Celsius on arrival.

ACTIVE PROBLEMS:
1. Probable acute appendicitis (pending confirmation)
2. No significant past medical history

CURRENT MEDICATIONS:
None regular.

ALLERGIES:
Latex — contact dermatitis (gloves). Latex-free protocol requested.

RECENT INVESTIGATIONS:
WBC: 15.4 x10^9/L (HIGH, neutrophilia) — today
CRP: 112 mg/L (HIGH) — today

PENDING:
Surgical review in progress.
Nil by mouth — theatre being arranged.
IV antibiotics commenced (co-amoxiclav, noting no penicillin allergy).
"""

CASE_4 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient ID: C3
Date: 30 September 2024
Setting: Outpatient Clinic — Haematology

CHIEF COMPLAINT:
Increasing fatigue and pallor over six weeks.
Patient reports feeling breathless climbing one flight of stairs.

ACTIVE PROBLEMS:
1. Iron-deficiency anaemia (new diagnosis today)
2. Uterine fibroids (known, managed conservatively)
3. Osteoporosis (on treatment)

CURRENT MEDICATIONS:
Tranexamic acid 1 g oral three times daily (during menstruation only)
Alendronate 70 mg oral once weekly (taken on empty stomach)
Calcium carbonate 500 mg with vitamin D3 800 IU oral once daily

ALLERGIES:
No known allergies.

RECENT INVESTIGATIONS:
Haemoglobin: 7.8 g/dL (LOW) — 28 September 2024
Serum ferritin: 4 ng/mL (LOW, depleted stores) — 28 September 2024

PENDING:
Upper and lower GI endoscopy to exclude occult bleeding source.
IV iron infusion planned for next week if no contraindication found.
"""

CASE_5 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient: D12
Date: 15 October 2024
Specialty: Neurology Outpatient

CHIEF COMPLAINT:
New onset right-sided weakness and slurred speech lasting approximately
20 minutes, fully resolved before arrival. No residual deficit on examination.

ACTIVE PROBLEMS:
1. Probable TIA (transient ischaemic attack) — to be confirmed with imaging
2. Hypertension — known, on treatment
3. Hypercholesterolaemia — on statin therapy

CURRENT MEDICATIONS:
Amlodipine 5 mg oral once daily
Atorvastatin 40 mg oral at night
Aspirin 75 mg oral once daily (started in ED today, loading dose given)

ALLERGIES:
Codeine — caused excessive sedation and confusion (documented 2021).
No other known drug allergies.

RECENT INVESTIGATIONS:
CT brain (non-contrast): No acute infarct or haemorrhage — today
LDL cholesterol: 4.2 mmol/L (HIGH) — 10 October 2024

PENDING:
MRI brain with DWI sequences — scheduled tomorrow.
Carotid Doppler ultrasound — arranged.
Cardiology review to exclude cardioembolic source.
"""

# ---------------------------------------------------------------------------
# CASES 6–10: Moderately messy notes
# ---------------------------------------------------------------------------

CASE_6 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Pt: E9 / DOB ~1958 / seen 8/10/24

CC - chest pain, onset last night around 10pm. Described as pressure,
7/10, radiates L arm. Had similar episode 6mo ago that "went away on its own".
Diaphoresis present. No syncope.

Pmhx: T2DM (on meds), HTN, ex-smoker (quit ~10yrs ago)

Meds (from patient — not verified against GP records):
metformin - not sure of dose, says "the small ones twice a day"
ramipril 5mg od
amlodipine - patient says 5 or 10mg, not certain

Allergies: says he had a bad reaction to "an antibiotic" years ago
but cannot recall which one or what happened. Nothing in the notes
brought today.

Ix:
Trop I: 0.06 (lab ref <0.04) — HIGH — taken at 03:15
ECG: ST depression V3-V5 (done on arrival)

Plan:
- ACS protocol started
- repeat trop at 0h+3 pending
- cardiology to review
"""

CASE_7 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

F11 | female | ~40yo | walk-in 09/10/24

presenting c/o: headache x 4 days, throbbing, unilateral (L side),
photophobia + nausea, no vomiting. similar to previous migraines but
"worse than usual". taking OTC ibuprofen with partial relief.

problems: migraine (dx 2016), anxiety disorder (on meds)

meds:
- sumatriptan 50mg prn (PRN, says she's been using it daily this week)
- sertraline 100mg od
- OCP (combined) — brand not recalled

NKDa

investigations: nil done today. BP 138/86 on arrival (baseline unclear).

pending: neurology referral if not improving in 2 weeks. GP follow-up
advised. counsel re: medication overuse headache given daily sumatriptan use.
"""

CASE_8 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

===== WARD ROUND NOTE =====
Patient G4 | male | 74yo | Day 3 post-admission

Reason for admission: fall at home, query cause.
Now: mobilising with physio, mild confusion still present (better than day 1)

Active issues:
 * recurrent falls (3rd this year)
 * vascular dementia (mild-moderate, diagnosed 2022)
 * AF - on anticoag
 * HTN

Drug chart (written up by admitting SHO — pharmacy reconciliation pending):
Rivaroxaban 20mg OD with evening meal
Bisoprolol 2.5mg OD
Lercanidipine 10mg OD
Zopiclone 3.75mg ON — prescribed at home, family says he takes it nightly
Donepezil 5mg ON

ALLERGIES: sulfonamides (trimethoprim caused rash in 2020)

Recent bloods (07/10/24):
Na 131 (LOW), K 4.2, Cr 102, eGFR 58
INR not done yet — urgent flagged

Pending:
CT head ordered (waiting for porter)
Falls MDT to be arranged
Review zopiclone — contributing to falls?
"""

CASE_9 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient H2. Seen in MAU 11 Oct. Referred from GP.

hx: 58F, known DM2, referred with 2wk hx polyuria+polydipsia,
blurred vision, 4kg wt loss. HbA1c sent by GP = 11.4% (very high, poorly
controlled). normally managed in primary care, first hospital attendance
in years.

Problems: T2DM (dx 2015), obesity (BMI 38 noted at GP), GORD

Medication list from GP letter:
metformin 1g BD
sitagliptin 100mg OD
omeprazole 20mg OD
(GP letter also mentions "topical treatment for skin condition" —
no further detail given)

Allergies: NKDA per GP letter

bloods today: glucose 22.1 mmol/L (HIGH), HbA1c 11.4% (done at GP 3 days ago),
renal fn normal (Cr 74, eGFR >90)

plan: diabetes review nurse, dietitian referral, consider intensification
of hypoglycaemic therapy vs insulin initiation. ophthalmology referral
for diabetic eye check (overdue by 2 years per GP records).
"""

CASE_10 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

K6 | 32M | ED 13/10/24 02:40

cc: acute severe asthma attack. brought in by ambulance.
SpO2 84% on air on arrival, now 93% on 15L NRB mask.

hx: asthma since age 12. 2 prev ICU admissions (last 2021).
ran out of preventer inhaler ~1wk ago. had URTI 3 days ago.

pmhx: asthma (severe persistent), eczema

meds per ambulance crew:
- salbutamol neb given x2 en route
- home meds: seretide 500 accuhaler 1 puff BD (not taken x1wk as above),
  montelukast 10mg on, cetirizine 10mg on prn

allergy: aspirin — causes bronchoconstriction (NSAID-exacerbated resp disease)
also: eggs (anaphylaxis as child, no epipen currently, says "grown out of it")

bloods/ix:
ABG (on 15L): pH 7.31, pCO2 5.8, pO2 11.2 — not yet improving
CXR: hyperinflation, no consolidation

immediate plan: continue back-to-back salbutamol nebs, IV magnesium
sulphate 2g over 20min, IV hydrocortisone 200mg stat.
HDU/ICU referral made. resp reg called.
pending: repeat ABG in 45 mins, peak flow when patient able.
"""

# ---------------------------------------------------------------------------
# CASES 11–15: Deliberately ambiguous (tests confidence-flagging)
# ---------------------------------------------------------------------------

CASE_11 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Patient: L9
Seen: approx. early October 2024
Setting: GP referral letter (transcribed)

Patient L9 is a gentleman in his mid-sixties referred for investigation
of macrocytic anaemia found incidentally on routine bloods.

He takes a number of medications for his heart. I have not been able
to obtain a complete list as he attends another practice for his
cardiology follow-up, but I believe he is on at least one anticoagulant
and possibly a rate-controlling agent. He also mentioned taking
"something for his stomach" but was unable to recall the name or dose.

He reports a previous adverse reaction to a statin — he stopped it
himself some years ago due to muscle pains, but is not sure if this
was formally documented as an allergy or just a side effect.

Active concerns from my perspective:
- Macrocytic anaemia (B12/folate deficiency vs medication-induced)
- Query alcohol use (units per week unclear, patient vague)
- The cardiac condition (exact diagnosis not provided in referral)

Recent bloods: Hb 9.2 g/dL, MCV 108 fL (both from GP, dated approx
3 weeks ago). B12 and folate pending from today's draw.

Please review and advise on further management.
No specific follow-up arranged at time of writing.
"""

CASE_12 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

pt M3 female 29yo
admitted via ED following deliberate self-harm (superficial lacerations
to forearm, medically managed, wounds dressed). now medically stable,
awaiting psych review.

diabetes — type 1. "usually well controlled" per patient. no recent hba1c
available. patient reports not always taking insulin when feeling unwell.

psych meds: patient mentions she "used to be on something" but stopped
taking it a few months ago. name/dose not known. no current regular
psychiatric medications confirmed.

insulin: novorapid with meals (patient-reported doses: variable).
lantus at night — dose also not stated clearly, says "about 20 units
but it changes".

allergy: patient denies allergies. however, nursing notes from a
previous admission (2022) mention "morphine — nausea", though it is
unclear if this was documented as an allergy or an adverse effect.
previous notes not available for review today.

glucose on admission: 3.1 mmol/L (LOW — corrected with oral glucose).
no other bloods yet.

pending: psychiatric assessment (urgent), endocrine review re: T1DM
management, social work input. safeguarding form completed.
"""

CASE_13 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

N5 | elderly female | exact DOB unclear from notes | ward B 

Patient brought in by son. Found at home after neighbour raised concern.
Son reports she "hasn't been herself" for about a week. No specific
complaint from patient (limited historian).

On examination: confused (AMT 4/10), dry mucous membranes, temp 37.8.

Background: son reports HTN, "a thyroid problem" (on tablets), and
something to do with her kidneys (no further detail). He is not sure
of her medication names — he brought in a carrier bag with blister
packs, most of which are unlabelled or partially labelled. Pharmacy
reconciliation requested but will take time.

Identifiable medications from blister packs:
- A pink tablet, once daily (unidentified)
- Levothyroxine 50mcg (label visible)
- One other tablet (white, round, no markings visible on this pack)

Allergies: son says "she can't have aspirin — something about her
stomach" but cannot say if this is a documented allergy, an intolerance,
or just a personal preference she has mentioned. No medic-alert bracelet.

bloods: Na 147 (HIGH), Cr 156 (HIGH), urea 18.2 (HIGH). WBC 13.1.
lactate 1.8. No prior bloods for comparison available today.

impression: dehydration with possible infection. sepsis screen sent.
urine dip: leucocytes ++ nitrites +

pending: CXR, blood and urine cultures, further medication reconciliation,
family to bring any GP letters or discharge summaries they can find.
"""

CASE_14 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

Outpatient rheum review — patient P2, male, ~50s.
Seen by SpR, supervised by consultant.

reason for attendance: follow up RA, also raised by patient —
new onset swelling right knee, started about 3 weeks ago. Query
flare vs. new pathology.

background: seropositive RA (RF+, anti-CCP+, diagnosed 2017).
Previous trial of methotrexate — stopped due to "liver problem"
(patient says LFTs were raised, does not know by how much;
not sure if this means methotrexate is formally contraindicated
or just needs monitoring). Currently on a biologic but patient
cannot name it — "the injection I do at home every two weeks".

Other problems: T2DM (diet-controlled, no meds), GORD.

Other meds: omeprazole 20mg OD, naproxen 500mg BD PRN
(patient takes this regularly despite GORD — noted, counselled).

Allergies: none stated. Patient unsure — "I just avoid things
that disagree with me." No formal allergy documentation found
in today's clinic letter.

bloods from last month: CRP 34 (HIGH), ESR 51 (HIGH), Hb 11.1 (borderline low).
no bloods today, point-of-care CRP sent — result pending.

plan: aspirate right knee if effusion confirmed. check biologic records
via pharmacy. revisit methotrexate hepatotoxicity question with full
liver screen before any future DMARD change. follow up in 6 weeks.
"""

CASE_15 = """\
# SYNTHETIC DATA — NOT A REAL PATIENT

quick note — Q8, male, 22yo, student. seen urgently in GP clinic.

presenting with rash — widespread, appeared this morning.
started taking a new antibiotic 4 days ago for a chest infection
(says it was prescribed by a walk-in clinic, doesn't have the
packet with him — thinks it "started with an A" — amoxicillin?
azithromycin? not confirmed).

rash: maculopapular, trunk and arms, no mucosal involvement,
mild itching. no blistering. no fever. no lymphadenopathy.
vitals normal.

past medical: nil significant. no regular meds.

the antibiotic has been stopped pending this review.
no epipen given today as reaction does not appear anaphylactic.

allergy documentation: cannot complete formal allergy entry as
the causative drug is unconfirmed. will need to clarify with
walk-in clinic records before documenting anything.

bloods: not done (clinical decision).

impression: probable drug reaction to recent antibiotic.
which antibiotic unclear — THIS MUST BE CLARIFIED before any
future prescribing of penicillins or macrolides.

plan: cetirizine 10mg OD for symptom relief. safety-net advice given.
follow-up in 3 days. request records from walk-in clinic.
"""

# ---------------------------------------------------------------------------

CASES = [
    ("case_1.txt",  CASE_1),
    ("case_2.txt",  CASE_2),
    ("case_3.txt",  CASE_3),
    ("case_4.txt",  CASE_4),
    ("case_5.txt",  CASE_5),
    ("case_6.txt",  CASE_6),
    ("case_7.txt",  CASE_7),
    ("case_8.txt",  CASE_8),
    ("case_9.txt",  CASE_9),
    ("case_10.txt", CASE_10),
    ("case_11.txt", CASE_11),
    ("case_12.txt", CASE_12),
    ("case_13.txt", CASE_13),
    ("case_14.txt", CASE_14),
    ("case_15.txt", CASE_15),
]


def main():
    print(f"Writing {len(CASES)} synthetic case files to: {OUTPUT_DIR}\n")
    print("Tier 1 — clear, well-organised (cases 1–5):")
    for i, (filename, content) in enumerate(CASES):
        path = OUTPUT_DIR / filename
        path.write_text(content.lstrip())
        lines = content.strip().count("\n") + 1
        tier = (
            "CLEAR     " if i < 5
            else "MESSY     " if i < 10
            else "AMBIGUOUS "
        )
        print(f"  [{tier}] {filename} ({lines} lines)")
        if i == 4:
            print("\nTier 2 — moderately messy (cases 6–10):")
        if i == 9:
            print("\nTier 3 — deliberately ambiguous (cases 11–15):")

    print(f"\nDone. Files saved to: {OUTPUT_DIR}")
    print("\nAmbiguous fields by design:")
    print("  case_6  : medication dose unknown (metformin), unknown antibiotic allergy")
    print("  case_11 : incomplete medication list, allergy vs. side-effect unclear")
    print("  case_12 : insulin dose vague, morphine allergy vs. adverse effect unclear")
    print("  case_13 : most medications unidentified, aspirin 'allergy' ambiguous")
    print("  case_14 : biologic name unknown, allergy section blank/uncertain")
    print("  case_15 : causative drug unconfirmed — allergy cannot be documented")
    print("\nNo-allergy-info cases (simulating real gaps):")
    print("  case_4  : 'No known allergies'")
    print("  case_7  : 'NKDA'")
    print("  case_9  : 'NKDA per GP letter'")


if __name__ == "__main__":
    main()
