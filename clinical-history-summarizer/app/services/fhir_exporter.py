"""
FHIR R4 Exporter Service
========================
Converts ClinicalSummary models into standard HL7 FHIR Release 4 JSON Bundles.
Enables direct interoperability with Hospital EHR systems (Epic, Cerner, NHS Spine).

Supported FHIR R4 Resources:
  - Bundle (type: collection)
  - Patient
  - Condition
  - MedicationStatement
  - AllergyIntolerance
  - Observation (Labs & Vitals)
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.models.summary import ClinicalSummary


def export_summary_to_fhir_r4(summary: ClinicalSummary) -> Dict[str, Any]:
    """
    Transforms a ClinicalSummary into an official HL7 FHIR R4 Bundle.
    Returns a dictionary conforming to the FHIR R4 JSON schema.
    """
    bundle_id = str(uuid.uuid4())
    patient_ref = f"urn:uuid:{uuid.uuid4()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    entries: list[Dict[str, Any]] = []

    # 1. FHIR Patient Resource
    patient_resource = {
        "resourceType": "Patient",
        "id": summary.patient_id or "patient-unknown",
        "identifier": [
            {
                "system": "urn:ietf:rfc:3986",
                "value": summary.patient_id or "UNKNOWN",
            }
        ],
        "active": True,
    }
    entries.append({
        "fullUrl": patient_ref,
        "resource": patient_resource,
    })

    # 2. FHIR Condition Resources (Documented Conditions)
    for idx, cond in enumerate(summary.documented_conditions):
        cond_id = f"condition-{idx + 1}"
        condition_resource = {
            "resourceType": "Condition",
            "id": cond_id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "problem-list-item",
                            "display": "Problem List Item",
                        }
                    ]
                }
            ],
            "code": {
                "text": cond,
            },
            "subject": {
                "reference": patient_ref,
            },
            "recordedDate": now_iso,
        }
        entries.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": condition_resource,
        })

    # 3. FHIR MedicationStatement Resources
    for idx, med in enumerate(summary.current_medications):
        med_id = f"medication-{idx + 1}"
        med_status = "active"
        if med.status and med.status.lower() in ("stopped", "held", "historical"):
            med_status = "stopped"

        med_resource = {
            "resourceType": "MedicationStatement",
            "id": med_id,
            "status": med_status,
            "medicationCodeableConcept": {
                "text": med.drug,
            },
            "subject": {
                "reference": patient_ref,
            },
            "effectiveDateTime": now_iso,
            "dosage": [
                {
                    "text": f"{med.dose or ''} {med.frequency or ''} via {med.route or 'oral'}".strip(),
                    "route": {
                        "text": med.route or "Oral",
                    },
                }
            ],
        }
        if med.uncertainty:
            med_resource["note"] = [{"text": f"Uncertainty: {med.uncertainty}"}]

        entries.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": med_resource,
        })

    # 4. FHIR AllergyIntolerance Resources
    for idx, allergy in enumerate(summary.allergies):
        alg_id = f"allergy-{idx + 1}"
        allergy_resource = {
            "resourceType": "AllergyIntolerance",
            "id": alg_id,
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        "code": "active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        "code": "confirmed",
                    }
                ]
            },
            "code": {
                "text": allergy.allergen,
            },
            "patient": {
                "reference": patient_ref,
            },
            "recordedDate": now_iso,
        }
        if allergy.reaction:
            allergy_resource["reaction"] = [
                {
                    "manifestation": [
                        {
                            "text": allergy.reaction,
                        }
                    ]
                }
            ]

        entries.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": allergy_resource,
        })

    # 5. FHIR Observation Resources (Recent Labs & Investigations)
    for idx, lab in enumerate(summary.recent_labs):
        obs_id = f"observation-lab-{idx + 1}"
        obs_resource: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory",
                        }
                    ]
                }
            ],
            "code": {
                "text": lab.test_name,
            },
            "subject": {
                "reference": patient_ref,
            },
            "effectiveDateTime": lab.date or now_iso,
        }

        # Value representation
        if lab.value:
            obs_resource["valueString"] = f"{lab.value} {lab.unit or ''}".strip()

        if lab.abnormality:
            obs_resource["interpretation"] = [
                {
                    "text": lab.abnormality,
                }
            ]

        if lab.reference_range:
            obs_resource["referenceRange"] = [
                {
                    "text": lab.reference_range,
                }
            ]

        entries.append({
            "fullUrl": f"urn:uuid:{uuid.uuid4()}",
            "resource": obs_resource,
        })

    # Assemble FHIR Bundle
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": now_iso,
        "total": len(entries),
        "entry": entries,
    }
