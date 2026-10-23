"""
Drug Intelligence Service — Rule-based safety layer (zero hallucination).
Detects drug-drug interactions, allergy conflicts, contraindications, dose anomalies.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

# ── Drug-Drug Interaction Database ───────────────────────────────────────────
_DDI = [
    ("warfarin","aspirin","HIGH","Warfarin + Aspirin: Major bleeding risk. Both inhibit clotting."),
    ("warfarin","ibuprofen","HIGH","Warfarin + Ibuprofen: NSAIDs displace warfarin → haemorrhage risk."),
    ("warfarin","naproxen","HIGH","Warfarin + Naproxen: Significant bleeding risk."),
    ("warfarin","diclofenac","HIGH","Warfarin + Diclofenac: Elevated INR and bleeding risk."),
    ("amiodarone","simvastatin","HIGH","Amiodarone blocks CYP3A4 → simvastatin ↑ → myopathy/rhabdomyolysis."),
    ("azithromycin","amiodarone","HIGH","Both prolong QT interval → life-threatening arrhythmia risk."),
    ("ciprofloxacin","amiodarone","HIGH","Additive QT prolongation → fatal arrhythmia risk."),
    ("ramipril","spironolactone","HIGH","Severe hyperkalaemia risk — can cause fatal cardiac arrhythmia."),
    ("lisinopril","spironolactone","HIGH","Additive potassium retention → hyperkalaemia."),
    ("enalapril","spironolactone","HIGH","Hyperkalaemia risk."),
    ("ramipril","amiloride","HIGH","Both retain potassium → severe hyperkalaemia."),
    ("sertraline","tramadol","HIGH","Serotonin syndrome risk — agitation, confusion, hyperthermia."),
    ("fluoxetine","tramadol","HIGH","Serotonin syndrome + seizure risk. CYP2D6 inhibition raises tramadol."),
    ("citalopram","tramadol","HIGH","Serotonin syndrome + QT prolongation."),
    ("paroxetine","tamoxifen","HIGH","Reduces tamoxifen→endoxifen conversion; reduces cancer efficacy."),
    ("simvastatin","clarithromycin","HIGH","CYP3A4 inhibition → simvastatin ↑↑ → rhabdomyolysis."),
    ("simvastatin","erythromycin","HIGH","CYP3A4 inhibition → severely elevated simvastatin → rhabdomyolysis."),
    ("digoxin","amiodarone","HIGH","P-gp + CYP3A4 inhibition → digoxin toxicity."),
    ("digoxin","clarithromycin","HIGH","P-gp inhibition → digoxin toxicity (nausea, arrhythmia)."),
    ("tramadol","diazepam","HIGH","CNS + respiratory depression. Dangerous sedation."),
    ("morphine","diazepam","HIGH","Life-threatening respiratory depression."),
    ("codeine","diazepam","HIGH","Combined CNS depression → apnoea risk."),
    ("tramadol","lorazepam","HIGH","Additive CNS/respiratory depression."),
    ("metoprolol","verapamil","HIGH","Both slow conduction → bradycardia, heart block, cardiac arrest."),
    ("atenolol","verapamil","HIGH","Severe bradycardia + AV block risk."),
    ("lithium","ibuprofen","HIGH","NSAIDs ↓ renal lithium clearance → toxicity (tremor, confusion, renal failure)."),
    ("lithium","diclofenac","HIGH","Reduced renal clearance → lithium toxicity."),
    ("rivaroxaban","ibuprofen","HIGH","Serious GI and systemic bleeding risk."),
    ("amiodarone","metformin","MODERATE","CYP2C8 inhibition → metformin ↑ → lactic acidosis risk."),
    ("atorvastatin","clarithromycin","MODERATE","CYP3A4 inhibition → atorvastatin ↑ → muscle pain risk."),
    ("simvastatin","amlodipine","MODERATE","Simvastatin dose should not exceed 20mg with amlodipine."),
    ("metformin","alcohol","MODERATE","Regular alcohol + metformin → lactic acidosis risk."),
    ("aspirin","clopidogrel","MODERATE","Dual antiplatelet — necessary in ACS but increases bleeding."),
    ("metoprolol","diltiazem","MODERATE","Additive AV nodal slowing → bradycardia."),
    ("lithium","ramipril","MODERATE","ACE inhibitors ↓ lithium excretion → toxicity risk."),
    ("lithium","furosemide","MODERATE","Loop diuretics ↓ lithium excretion → toxicity."),
    ("apixaban","aspirin","MODERATE","Increased bleeding risk."),
    ("ciprofloxacin","glibenclamide","MODERATE","Fluoroquinolones potentiate glucose fluctuations."),
    ("metronidazole","amiodarone","MODERATE","CYP2C9 inhibition → amiodarone ↑."),
]

# ── Allergy Cross-Reactivity Database ────────────────────────────────────────
_ALLERGY_CROSS = [
    ("penicillin","amoxicillin","Amoxicillin is a penicillin — direct allergy conflict.","HIGH"),
    ("penicillin","ampicillin","Ampicillin is a penicillin — direct allergy conflict.","HIGH"),
    ("penicillin","flucloxacillin","Flucloxacillin is a penicillin — direct allergy conflict.","HIGH"),
    ("penicillin","co-amoxiclav","Co-amoxiclav contains amoxicillin — direct allergy conflict.","HIGH"),
    ("penicillin","cephalexin","~10% cross-reactivity with penicillin allergy. Use with caution.","MODERATE"),
    ("penicillin","cefuroxime","Possible cross-reactivity (cephalosporin).","MODERATE"),
    ("penicillin","ceftriaxone","Possible cross-reactivity — check anaphylaxis history.","MODERATE"),
    ("sulfa","trimethoprim-sulfamethoxazole","Contains sulphonamide — allergy conflict.","HIGH"),
    ("sulfa","furosemide","Furosemide has sulphonamide structure — possible cross-reactivity.","MODERATE"),
    ("nsaid","ibuprofen","Patient has NSAID allergy — ibuprofen is an NSAID.","HIGH"),
    ("nsaid","diclofenac","Patient has NSAID allergy — diclofenac is an NSAID.","HIGH"),
    ("nsaid","naproxen","Patient has NSAID allergy — naproxen is an NSAID.","HIGH"),
    ("aspirin","ibuprofen","Aspirin-intolerant patients may react to other NSAIDs.","MODERATE"),
    ("codeine","tramadol","Both are opioids — possible broad opioid sensitivity.","MODERATE"),
    ("morphine","tramadol","Both are opioids — assess if allergy is to opioid class.","MODERATE"),
]

# ── Contraindication Table ────────────────────────────────────────────────────
_CI = [
    ("renal","metformin","HIGH","Metformin contraindicated in eGFR<30 — lactic acidosis risk."),
    ("ckd","metformin","HIGH","Metformin contraindicated in CKD stage 4/5."),
    ("renal failure","ibuprofen","HIGH","NSAIDs reduce renal blood flow — contraindicated in renal failure."),
    ("heart failure","ibuprofen","HIGH","NSAIDs cause fluid retention, worsen heart failure."),
    ("heart failure","verapamil","HIGH","Negative inotropic effect — can precipitate decompensated HF."),
    ("asthma","aspirin","HIGH","Aspirin triggers bronchospasm in aspirin-sensitive asthma."),
    ("asthma","ibuprofen","HIGH","NSAIDs can precipitate severe bronchospasm in asthma."),
    ("asthma","propranolol","HIGH","Non-selective beta-blockers cause bronchospasm — strictly contraindicated."),
    ("pregnant","methotrexate","HIGH","Methotrexate is teratogenic — absolutely contraindicated."),
    ("pregnant","warfarin","HIGH","Warfarin is teratogenic in first trimester."),
    ("pregnant","ramipril","HIGH","ACE inhibitors contraindicated — foetal renal agenesis."),
    ("pregnant","lisinopril","HIGH","ACE inhibitors contraindicated in pregnancy."),
    ("pregnant","simvastatin","HIGH","Statins contraindicated in pregnancy."),
    ("pregnant","atorvastatin","HIGH","Statins contraindicated in pregnancy."),
    ("liver failure","metformin","HIGH","Contraindicated in severe hepatic impairment — lactic acidosis risk."),
    ("hyperkalaemia","spironolactone","HIGH","Spironolactone retains potassium — contraindicated with existing hyperkalaemia."),
    ("hyperkalaemia","ramipril","HIGH","ACE inhibitors impair K+ excretion — contraindicated with hyperkalaemia."),
    ("diabetes","corticosteroids","MODERATE","Corticosteroids cause hyperglycaemia — monitor glucose closely."),
    ("liver","statins","MODERATE","Avoid statins in active liver disease — hepatotoxicity risk."),
    ("osteoporosis","corticosteroids","MODERATE","Long-term steroids worsen osteoporosis — consider bisphosphonate."),
    ("heart failure","diltiazem","MODERATE","Negative inotropic effect may worsen reduced-EF heart failure."),
    ("asthma","atenolol","MODERATE","Beta-1 selective blockers still carry bronchospasm risk."),
]

# ── Dose Plausibility Ranges ──────────────────────────────────────────────────
_DOSE_RANGES = {
    "metformin": (500, 2000, "mg/day", "Typical 500–2000 mg/day in divided doses"),
    "ramipril": (1.25, 10, "mg/day", "Hypertension 2.5–10 mg/day"),
    "amlodipine": (2.5, 10, "mg/day", "Standard 5–10 mg once daily"),
    "lisinopril": (2.5, 40, "mg/day", "Hypertension 10–40 mg/day"),
    "atorvastatin": (10, 80, "mg/day", "10–80 mg once daily"),
    "simvastatin": (10, 40, "mg/day", "Standard 10–40 mg; >40 mg exceptional only"),
    "aspirin": (75, 325, "mg/day", "Antiplatelet 75–100 mg; analgesic up to 4000 mg/day"),
    "ibuprofen": (200, 2400, "mg/day", "OTC max 1200 mg; prescription up to 2400 mg/day"),
    "omeprazole": (10, 40, "mg/day", "Standard 20–40 mg once daily"),
    "metoprolol": (25, 200, "mg/day", "25–200 mg/day"),
    "furosemide": (20, 80, "mg/day", "20–80 mg/day; higher under supervision"),
    "spironolactone": (25, 100, "mg/day", "25–100 mg/day for heart failure"),
    "warfarin": (1, 10, "mg/day", "Guided by INR target; highly variable"),
    "paracetamol": (500, 4000, "mg/day", "Max 4000 mg/day; reduce in liver disease"),
    "sertraline": (50, 200, "mg/day", "50 mg start; max 200 mg/day"),
    "amiodarone": (100, 400, "mg/day", "Maintenance 100–400 mg/day after loading"),
    "tramadol": (50, 400, "mg/day", "50–400 mg/day in divided doses"),
    "prednisolone": (5, 60, "mg/day", "Varies by indication; taper slowly"),
    "ciprofloxacin": (250, 1500, "mg/day", "250–750 mg twice daily"),
    "digoxin": (0.0625, 0.25, "mg/day", "62.5–250 mcg/day; guided by serum levels"),
    "bisoprolol": (1.25, 10, "mg/day", "1.25 mg start in HF; up to 10 mg/day"),
    "losartan": (25, 100, "mg/day", "25–100 mg once daily"),
}


@dataclass
class DrugInteractionAlert:
    drug_a: str; drug_b: str; severity: str; explanation: str; action: str = ""
    def __post_init__(self):
        if not self.action:
            self.action = ("Urgent review required — contact prescriber before dispensing."
                          if self.severity == "HIGH" else
                          "Monitor closely. Discuss with prescriber if not already aware.")

@dataclass
class AllergyConflictAlert:
    allergen: str; conflicting_drug: str; explanation: str; severity: str = "HIGH"

@dataclass
class ContraindicationAlert:
    condition: str; drug: str; severity: str; explanation: str

@dataclass
class DosePlausibilityAlert:
    drug: str; prescribed_dose: str; expected_range: str; note: str; is_high: bool

@dataclass
class DrugIntelligenceReport:
    drug_interactions: list = field(default_factory=list)
    allergy_conflicts: list = field(default_factory=list)
    contraindications: list = field(default_factory=list)
    dose_alerts: list = field(default_factory=list)
    high_severity_count: int = 0
    moderate_severity_count: int = 0
    is_safe_profile: bool = True

    def to_dict(self):
        return {
            "drug_interactions": [{"drug_a":a.drug_a,"drug_b":a.drug_b,"severity":a.severity,"explanation":a.explanation,"action":a.action} for a in self.drug_interactions],
            "allergy_conflicts": [{"allergen":a.allergen,"conflicting_drug":a.conflicting_drug,"explanation":a.explanation,"severity":a.severity} for a in self.allergy_conflicts],
            "contraindications": [{"condition":c.condition,"drug":c.drug,"severity":c.severity,"explanation":c.explanation} for c in self.contraindications],
            "dose_alerts": [{"drug":d.drug,"prescribed_dose":d.prescribed_dose,"expected_range":d.expected_range,"note":d.note,"is_high":d.is_high} for d in self.dose_alerts],
            "high_severity_count": self.high_severity_count,
            "moderate_severity_count": self.moderate_severity_count,
            "is_safe_profile": self.is_safe_profile,
        }


def _n(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").lower().strip())

def _match(name: str, kw: str) -> bool:
    kw_c = _n(kw)
    name_c = _n(name)
    if not kw_c or not name_c:
        return False
    pattern = r"\b" + re.escape(kw_c) + r"\b"
    return bool(re.search(pattern, name_c))

def _extract_mg(dose_str: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", dose_str or "", re.IGNORECASE)
    return float(m.group(1)) if m else None


def analyse_drug_safety(medications: list, allergies: list, conditions: list) -> DrugIntelligenceReport:
    report = DrugIntelligenceReport()
    drug_names = [m.get("drug","") for m in medications if m.get("drug")]
    allergen_names = [a.get("allergen","") for a in allergies if a.get("allergen")]

    # 1. Drug-Drug Interactions
    seen = set()
    for da, db, sev, exp in _DDI:
        for d1 in [d for d in drug_names if _match(d, da)]:
            for d2 in [d for d in drug_names if _match(d, db)]:
                if d1.strip().lower() == d2.strip().lower():
                    continue
                key = frozenset({d1.lower(), d2.lower()})
                if key in seen: continue
                seen.add(key)
                report.drug_interactions.append(DrugInteractionAlert(d1, d2, sev, exp))
                if sev == "HIGH": report.high_severity_count += 1; report.is_safe_profile = False
                else: report.moderate_severity_count += 1


    # 2. Allergy Cross-Reactivity
    for alg_kw, drg_kw, exp, sev in _ALLERGY_CROSS:
        for alg in [a for a in allergen_names if _match(a, alg_kw)]:
            for drg in [d for d in drug_names if _match(d, drg_kw)]:
                report.allergy_conflicts.append(AllergyConflictAlert(alg, drg, exp, sev))
                if sev == "HIGH": report.high_severity_count += 1; report.is_safe_profile = False
                else: report.moderate_severity_count += 1

    # 3. Contraindications
    cond_text = " ".join(conditions)
    seen_ci = set()
    for cond_kw, drg_kw, sev, exp in _CI:
        if _n(cond_kw) not in _n(cond_text): continue
        for drg in [d for d in drug_names if _match(d, drg_kw)]:
            key = (cond_kw, drg.lower())
            if key in seen_ci: continue
            seen_ci.add(key)
            report.contraindications.append(ContraindicationAlert(cond_kw, drg, sev, exp))
            if sev == "HIGH": report.high_severity_count += 1; report.is_safe_profile = False
            else: report.moderate_severity_count += 1

    # 4. Dose Plausibility
    for med in medications:
        name = med.get("drug","")
        dose_s = med.get("dose","") or ""
        if not name or not dose_s: continue
        for db_name,(mn,mx,unit,note) in _DOSE_RANGES.items():
            if not _match(name, db_name): continue
            val = _extract_mg(dose_s)
            if val is None: break
            if val > mx*2:
                report.dose_alerts.append(DosePlausibilityAlert(name,dose_s,f"{mn}–{mx} {unit}",note,True))
            elif val < mn*0.5:
                report.dose_alerts.append(DosePlausibilityAlert(name,dose_s,f"{mn}–{mx} {unit}",note,False))
            break

    return report
