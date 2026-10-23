"""
Clinical Decision Support (CDS) Service
========================================
Rule-based urgency scoring and clinical intelligence layer.
Zero hallucination — all logic is deterministic.

Features:
  1. Urgency scoring (1-5 scale, CTAS-inspired)
  2. Missing critical info detection (per complaint type)
  3. Red flag pattern matching
  4. Clinical context enrichment (what this complaint typically means)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

# ── Urgency scoring keywords ──────────────────────────────────────────────────
# (keyword_in_complaint_or_symptoms, urgency_level_contribution, reason)
_URGENCY_SIGNALS = [
    # Cardiac / vascular emergencies → Level 5 (Resuscitation)
    ("cardiac arrest", 5, "Cardiac arrest — immediate resuscitation"),
    ("ventricular fibrillation", 5, "VF — life-threatening arrhythmia"),
    ("st elevation", 5, "STEMI — emergent reperfusion required"),
    ("stemi", 5, "STEMI — immediate cath lab activation"),
    ("nstemi", 4, "NSTEMI — urgent cardiology review"),
    ("aortic dissection", 5, "Aortic dissection — surgical emergency"),
    ("pulmonary embolism", 4, "PE — oxygen, anticoagulation, urgent imaging"),
    ("anaphylaxis", 5, "Anaphylaxis — adrenaline + airway management"),

    # Neuro emergencies → Level 4-5
    ("stroke", 5, "Stroke — time-critical thrombolysis window"),
    ("tia", 4, "TIA — high early stroke risk, urgent neurology"),
    ("seizure", 4, "Active seizure or post-ictal — airway priority"),
    ("altered consciousness", 4, "Altered GCS — urgent neurological assessment"),
    ("meningitis", 5, "Meningitis — immediate antibiotics + CT/LP"),

    # Chest pain signals → Level 3-4
    ("chest pain", 4, "Chest pain — must exclude ACS, PE, aortic dissection"),
    ("chest pressure", 4, "Chest pressure — high ACS suspicion"),
    ("chest tightness", 3, "Chest tightness — exclude cardiac cause"),
    ("diaphoresis", 4, "Diaphoresis with pain — high ACS/PE suspicion"),
    ("radiates", 3, "Radiating pain — classic cardiac/referred pain pattern"),
    ("left arm", 4, "Left arm radiation — classic ACS symptom"),

    # Respiratory
    ("shortness of breath", 3, "Dyspnoea — requires SpO2, clinical assessment"),
    ("sob", 3, "Dyspnoea — requires SpO2 and auscultation"),
    ("respiratory distress", 4, "Respiratory distress — urgent airway management"),
    ("oxygen saturation", 3, "SpO2 documented — assess adequacy"),
    ("haemoptysis", 4, "Blood in sputum — exclude PE, TB, malignancy"),

    # GI emergencies
    ("haematemesis", 5, "Haematemesis — GI bleed, urgent endoscopy"),
    ("melena", 4, "Melaena — GI bleed, haemodynamic monitoring"),
    ("peritonitis", 5, "Peritonitis — surgical emergency"),
    ("bowel obstruction", 4, "Bowel obstruction — urgent surgical review"),

    # Metabolic
    ("hypoglycaemia", 4, "Hypoglycaemia — immediate glucose correction"),
    ("dka", 5, "DKA — immediate fluid/insulin protocol"),
    ("diabetic ketoacidosis", 5, "DKA — immediate protocol required"),
    ("hyperkalemia", 4, "Hyperkalaemia — cardiac monitoring + treatment"),
    ("hyperkalaemia", 4, "Hyperkalaemia — cardiac monitoring required"),
    ("sepsis", 5, "Sepsis — 1-hour bundle (blood cultures, antibiotics, IV fluids)"),

    # Troponin abnormality
    ("troponin", 4, "Troponin result present — serial testing and cardiac monitoring"),
    ("high", 3, "Abnormal value flagged"),

    # General urgency modifiers (lower weight)
    ("syncope", 3, "Syncope — rule out arrhythmia, orthostatic, cardiac cause"),
    ("palpitations", 2, "Palpitations — ECG, Holter if recurrent"),
    ("fever", 2, "Fever — assess for source; consider sepsis screen"),
    ("vomiting", 2, "Vomiting — assess hydration, exclude surgical cause"),
    ("pain", 1, "Pain documented"),
    ("fatigue", 1, "Fatigue — non-specific, investigate if persistent"),
]

# ── Missing critical info rules ───────────────────────────────────────────────
# (trigger_keyword, field_to_check, friendly_label_if_missing)
_CRITICAL_INFO_RULES = [
    # Chest pain workup
    ("chest pain", "recent_labs.troponin", "Troponin-I / Troponin-T result"),
    ("chest pain", "recent_labs.ecg", "ECG / electrocardiogram"),
    ("chest pain", "clinical_findings.bp", "Blood pressure measurement"),
    ("chest pain", "clinical_findings.heart_rate", "Heart rate / pulse"),
    ("chest pain", "clinical_findings.spo2", "Oxygen saturation (SpO2)"),

    # Diabetic management
    ("diabetes", "recent_labs.hba1c", "HbA1c (blood sugar control over 3 months)"),
    ("t2dm", "recent_labs.hba1c", "HbA1c"),
    ("diabetes", "recent_labs.egfr", "eGFR (kidney function)"),
    ("metformin", "recent_labs.egfr", "eGFR (required before/during metformin)"),

    # Hypertension
    ("hypertension", "clinical_findings.bp", "Blood pressure reading"),
    ("htn", "clinical_findings.bp", "Blood pressure reading"),
    ("ramipril", "recent_labs.urea", "Renal function (U&E) — mandatory with ACE inhibitor"),
    ("lisinopril", "recent_labs.urea", "Renal function (U&E) — mandatory with ACE inhibitor"),
    ("ramipril", "recent_labs.potassium", "Serum potassium — ACE inhibitors risk hyperkalaemia"),

    # Heart failure
    ("heart failure", "recent_labs.bnp", "BNP or NT-proBNP (heart failure marker)"),
    ("heart failure", "clinical_findings.weight", "Body weight (fluid monitoring in HF)"),
    ("heart failure", "clinical_findings.oedema", "Oedema assessment"),

    # Anticoagulation
    ("warfarin", "recent_labs.inr", "INR (warfarin monitoring)"),
    ("warfarin", "recent_labs.pt", "Prothrombin time (PT)"),

    # Infection / fever
    ("fever", "recent_labs.wbc", "White blood cell count (infection marker)"),
    ("sepsis", "recent_labs.lactate", "Serum lactate (sepsis severity marker)"),
    ("sepsis", "recent_labs.blood_culture", "Blood cultures before antibiotics"),

    # Respiratory
    ("shortness of breath", "clinical_findings.spo2", "Oxygen saturation (SpO2)"),
    ("sob", "clinical_findings.spo2", "Oxygen saturation (SpO2)"),
    ("asthma", "clinical_findings.peak_flow", "Peak flow measurement"),

    # Stroke / neuro
    ("stroke", "clinical_findings.gcs", "GCS (Glasgow Coma Scale)"),
    ("stroke", "clinical_findings.nihss", "NIHSS stroke score"),

    # Allergy documentation
    ("penicillin", "allergies", "Allergy status documented — good practice"),
]

# ── Contextual clinical intelligence ────────────────────────────────────────
_CLINICAL_CONTEXT = {
    "chest pain": "Chest pain requires immediate ECG + serial troponins. Key differentials: ACS (Acute Coronary Syndrome), PE (Pulmonary Embolism), aortic dissection, pericarditis. Any troponin rise needs cardiology input.",
    "diabetes": "Diabetes management: target HbA1c <53 mmol/mol (7%). Screen annually for retinopathy, nephropathy (eGFR + ACR), neuropathy, foot care.",
    "hypertension": "Blood pressure target <140/90 mmHg (or <130/80 in CKD/diabetes). Lifestyle: reduce salt, weight loss, exercise. First-line medications: ACE inhibitor, ARB, or CCB.",
    "heart failure": "Heart failure management: weigh daily (alert if >2kg rise in 3 days), restrict fluid to 1.5L/day, low-sodium diet. Pillar medications: ACE inhibitor + beta-blocker + spironolactone.",
    "shortness of breath": "Dyspnoea workup: SpO2, CXR, ECG, BNP, spirometry. Differentials: heart failure, COPD/asthma, PE, pneumonia, anaemia.",
    "stroke": "Stroke: FAST assessment (Face, Arms, Speech, Time). Thrombolysis window ≤4.5h from onset if CT excludes bleed. BP management critical. Start antiplatelet/anticoagulation per aetiology.",
}


@dataclass
class UrgencyScore:
    level: int  # 1-5 (1=non-urgent, 5=immediate)
    label: str  # "Routine" | "Semi-urgent" | "Urgent" | "Emergent" | "Resuscitation"
    color: str  # hex color for UI
    reasons: list = field(default_factory=list)
    clinical_context: str = ""


@dataclass
class MissingCriticalInfo:
    trigger: str
    missing_item: str
    why_important: str


@dataclass
class CDSReport:
    urgency: UrgencyScore
    missing_info: list = field(default_factory=list)
    clinical_pearls: list = field(default_factory=list)

    def to_dict(self):
        return {
            "urgency": {
                "level": self.urgency.level,
                "label": self.urgency.label,
                "color": self.urgency.color,
                "reasons": self.urgency.reasons,
                "clinical_context": self.urgency.clinical_context,
            },
            "missing_info": [
                {"trigger": m.trigger, "missing_item": m.missing_item, "why_important": m.why_important}
                for m in self.missing_info
            ],
            "clinical_pearls": self.clinical_pearls,
        }


def _n(t: Any) -> str:
    return re.sub(r"\s+", " ", str(t or "").lower().strip())

def _any_match(text: str, kw: str) -> bool:
    return _n(kw) in _n(text)


def _compute_urgency(all_text: str, red_flags: list) -> UrgencyScore:
    max_level = 1
    reasons = []

    for kw, level, reason in _URGENCY_SIGNALS:
        if _any_match(all_text, kw):
            if level > max_level:
                max_level = level
            if level >= 3 and reason not in reasons:
                reasons.append(reason)

    # Red flags always push to at least 3
    if red_flags and max_level < 3:
        max_level = 3
        reasons.append(f"{len(red_flags)} clinical red flag(s) identified")

    labels = {
        1: ("Routine", "#22c55e"),
        2: ("Semi-Urgent", "#84cc16"),
        3: ("Urgent", "#f59e0b"),
        4: ("Emergent", "#f97316"),
        5: ("Resuscitation", "#ef4444"),
    }
    label, color = labels[max_level]

    # Clinical context
    context = ""
    for trigger, ctx in _CLINICAL_CONTEXT.items():
        if _any_match(all_text, trigger):
            context = ctx
            break

    return UrgencyScore(max_level, label, color, reasons[:5], context)


def _find_missing_info(
    all_text: str,
    recent_labs: list,
    clinical_findings: list,
    allergies: list,
) -> list:
    missing = []
    seen = set()

    lab_text = " ".join(str(l) for l in recent_labs).lower()
    findings_text = " ".join(str(f) for f in clinical_findings).lower()
    allergy_text = " ".join(str(a) for a in allergies).lower()

    for trigger_kw, field_check, label in _CRITICAL_INFO_RULES:
        if not _any_match(all_text, trigger_kw):
            continue

        category, sub = field_check.split(".", 1) if "." in field_check else (field_check, "")
        is_present = False

        if category == "recent_labs":
            is_present = sub in lab_text or any(sub in str(l).lower() for l in recent_labs)
        elif category == "clinical_findings":
            is_present = sub in findings_text
        elif category == "allergies":
            is_present = bool(allergies)

        if not is_present and label not in seen:
            seen.add(label)
            missing.append(MissingCriticalInfo(
                trigger=trigger_kw,
                missing_item=label,
                why_important=f"Not documented in notes — important for {trigger_kw} management.",
            ))

    return missing[:8]  # cap at 8 most important


def run_clinical_decision_support(
    chief_complaint: str,
    symptoms: list,
    documented_conditions: list,
    red_flags: list,
    recent_labs: list,
    clinical_findings: list,
    allergies: list,
    risk_factors: list,
) -> CDSReport:
    """
    Run clinical decision support analysis.
    All inputs are strings or lists-of-strings extracted from ClinicalSummary.
    Returns a CDSReport with urgency score, missing info, and clinical pearls.
    """
    # Helper to stringify anything safely
    def _to_str(item):
        if hasattr(item, "finding"):
            val_part = f" {item.value}" if getattr(item, "value", None) else ""
            unit_part = f" {item.unit}" if getattr(item, "unit", None) else ""
            return f"{item.finding}{val_part}{unit_part}".strip()
        elif hasattr(item, "test_name"):
            val_part = f" {item.value}" if getattr(item, "value", None) else ""
            unit_part = f" {item.unit}" if getattr(item, "unit", None) else ""
            return f"{item.test_name}{val_part}{unit_part}".strip()
        elif isinstance(item, dict):
            if "finding" in item:
                val_part = f" {item['value']}" if item.get("value") else ""
                unit_part = f" {item['unit']}" if item.get("unit") else ""
                return f"{item['finding']}{val_part}{unit_part}".strip()
            if "test_name" in item:
                val_part = f" {item['value']}" if item.get("value") else ""
                unit_part = f" {item['unit']}" if item.get("unit") else ""
                return f"{item['test_name']}{val_part}{unit_part}".strip()
            return " ".join(f"{k} {v}" for k, v in item.items() if v).strip()
        return str(item or "")

    # Combine all text for keyword matching
    all_parts = [
        str(chief_complaint or ""),
        *[str(s) for s in (symptoms or [])],
        *[str(d) for d in (documented_conditions or [])],
        *[_to_str(r) for r in (red_flags or [])],
        *[str(rf) for rf in (risk_factors or [])],
        *[_to_str(l) for l in (recent_labs or [])],
        *[_to_str(f) for f in (clinical_findings or [])],
    ]
    all_text = " ".join(p for p in all_parts if p)

    urgency = _compute_urgency(all_text, red_flags or [])
    missing = _find_missing_info(all_text, recent_labs or [], clinical_findings or [], allergies or [])

    # Clinical pearls
    pearls = []
    if any("troponin" in _n(str(l)) for l in (recent_labs or [])):
        pearls.append("📌 Troponin result present — serial measurements (0h + 3h) recommended to trend for ACS rule-in/rule-out.")
    if any("ecg" in _n(str(f)) or "st " in _n(str(f)) for f in (clinical_findings or []) + list(recent_labs or [])):
        pearls.append("📌 ECG findings noted — correlate with troponin and clinical history for ACS risk stratification.")
    if any("metformin" in _n(str(m)) for m in list(documented_conditions or []) + all_parts):
        pearls.append("📌 Metformin requires eGFR monitoring ≥ every 6 months — hold if eGFR <30 mL/min.")
    if any("ramipril" in _n(p) or "lisinopril" in _n(p) or "enalapril" in _n(p) for p in all_parts):
        pearls.append("📌 ACE inhibitor prescribed — check U&E and serum potassium within 1–2 weeks of starting or dose change.")
    if any("warfarin" in _n(p) for p in all_parts):
        pearls.append("📌 Warfarin requires INR monitoring — check drug interactions and dietary vitamin K intake.")

    return CDSReport(urgency=urgency, missing_info=missing, clinical_pearls=pearls)
