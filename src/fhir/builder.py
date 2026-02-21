"""FHIR R4 Bundle builder for triage results.

Converts patient data and triage classification into a valid FHIR R4
Bundle containing Patient, Encounter, Condition, and Observation resources.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.codeablereference import CodeableReference
from fhir.resources.coding import Coding
from fhir.resources.condition import Condition
from fhir.resources.encounter import Encounter, EncounterReason
from fhir.resources.humanname import HumanName
from fhir.resources.observation import Observation, ObservationComponent
from fhir.resources.patient import Patient
from fhir.resources.quantity import Quantity
from fhir.resources.reference import Reference

from src.agents.triage import TRIAGE_LEVELS, PatientData, TriageResult

# LOINC codes for vital signs
_VITAL_LOINC = {
    "heart_rate": ("8867-4", "Heart rate", "bpm"),
    "blood_pressure": ("85354-9", "Blood pressure", "mmHg"),
    "respiratory_rate": ("9279-1", "Respiratory rate", "/min"),
    "temperature": ("8310-5", "Body temperature", "Cel"),
    "spo2": ("2708-6", "Oxygen saturation", "%"),
    "glucose": ("2339-0", "Glucose", "mg/dL"),
}


def _make_id() -> str:
    return str(uuid.uuid4())


def _build_patient(
    patient_id: str,
    name: str,
    age: Optional[int],
    sex: Optional[str],
) -> Patient:
    gender = "unknown"
    if sex:
        gender = "male" if sex.upper() == "M" else "female"

    birth_date = None
    if age is not None:
        birth_date = str(datetime.now(timezone.utc).year - age)

    return Patient(
        id=patient_id,
        name=[HumanName(use="official", text=name)],
        gender=gender,
        birthDate=birth_date,
    )


def _build_encounter(
    encounter_id: str,
    patient_id: str,
    triage_result: TriageResult,
    chief_complaint: str,
) -> Encounter:
    level_name, _ = TRIAGE_LEVELS[triage_result.triage_color]

    return Encounter(
        id=encounter_id,
        status="in-progress",
        class_fhir=[
            CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        code="EMER",
                        display="emergency",
                    )
                ]
            )
        ],
        subject=Reference(reference=f"Patient/{patient_id}"),
        priority=CodeableConcept(
            coding=[
                Coding(
                    system="http://hl7.org/fhir/v3/ActPriority",
                    code=triage_result.triage_color.value,
                    display=level_name,
                )
            ]
        ),
        reason=[
            EncounterReason(
                value=[CodeableReference(concept=CodeableConcept(text=chief_complaint))]
            )
        ],
    )


def _build_triage_observation(
    observation_id: str,
    patient_id: str,
    encounter_id: str,
    triage_result: TriageResult,
    patient_data: PatientData,
) -> Observation:
    level_name, max_wait = TRIAGE_LEVELS[triage_result.triage_color]

    components: list[ObservationComponent] = [
        ObservationComponent(
            code=CodeableConcept(text="Confidence"),
            valueQuantity=Quantity(value=triage_result.confidence, unit="ratio"),
        ),
        ObservationComponent(
            code=CodeableConcept(text="Reasoning"),
            valueString=triage_result.reasoning,
        ),
    ]

    # Add vital signs as components
    if patient_data.vital_signs:
        vs = patient_data.vital_signs
        for field, (loinc, display, unit) in _VITAL_LOINC.items():
            value = getattr(vs, field, None)
            if value is None or value == 0 or value == 0.0 or value == "":
                continue
            comp = ObservationComponent(
                code=CodeableConcept(
                    coding=[
                        Coding(system="http://loinc.org", code=loinc, display=display)
                    ]
                ),
            )
            if isinstance(value, str):
                comp.valueString = f"{value} {unit}"
            else:
                comp.valueQuantity = Quantity(value=float(value), unit=unit)
            components.append(comp)

    return Observation(
        id=observation_id,
        status="final",
        code=CodeableConcept(
            coding=[
                Coding(
                    system="http://loinc.org",
                    code="56838-1",
                    display="Manchester Triage Category",
                )
            ],
            text="Classificação de Risco Manchester",
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        encounter=Reference(reference=f"Encounter/{encounter_id}"),
        valueCodeableConcept=CodeableConcept(
            coding=[
                Coding(
                    code=triage_result.triage_color.value,
                    display=level_name,
                )
            ],
            text=(
                f"{triage_result.triage_color.value} — {level_name} "
                f"(máx {max_wait} min)"
            ),
        ),
        component=components,
    )


def _build_condition(
    condition_id: str,
    patient_id: str,
    encounter_id: str,
    chief_complaint: str,
) -> Condition:
    return Condition(
        id=condition_id,
        clinicalStatus=CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                    code="active",
                )
            ]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        encounter=Reference(reference=f"Encounter/{encounter_id}"),
        code=CodeableConcept(text=chief_complaint),
    )


def build_fhir_bundle(
    patient_name: str,
    patient_age: Optional[int],
    patient_sex: Optional[str],
    patient_data: PatientData,
    triage_result: TriageResult,
) -> dict:
    """Build a FHIR R4 Bundle from triage results.

    Args:
        patient_name: Display name for the patient resource.
        patient_age: Patient age in years.
        patient_sex: "M" or "F".
        patient_data: Structured patient data from intake.
        triage_result: Triage classification result.

    Returns:
        FHIR R4 Bundle as a plain dict (JSON-serializable).
    """
    patient_id = _make_id()
    encounter_id = _make_id()
    observation_id = _make_id()
    condition_id = _make_id()

    # FHIR Bundle: a container for a group of related resources.
    # Used to package resources for sending, retrieval, or batch
    # processing. Type "collection" groups the main components of
    # an ER triage episode (Patient, Encounter, Observation, and
    # Condition) into a single, portable package.
    #
    # FHIR BundleEntry: a wrapper for one resource inside the
    # Bundle. Maintains references between resources and supplies
    # additional metadata. Each entry here holds a core clinical
    # resource generated during the triage process.

    bundle = Bundle(
        id=_make_id(),
        type="collection",
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry=[
            BundleEntry(
                resource=_build_patient(
                    patient_id, patient_name, patient_age, patient_sex
                )
            ),
            BundleEntry(
                resource=_build_encounter(
                    encounter_id,
                    patient_id,
                    triage_result,
                    patient_data.chief_complaint,
                )
            ),
            BundleEntry(
                resource=_build_triage_observation(
                    observation_id,
                    patient_id,
                    encounter_id,
                    triage_result,
                    patient_data,
                )
            ),
            BundleEntry(
                resource=_build_condition(
                    condition_id, patient_id, encounter_id, patient_data.chief_complaint
                )
            ),
        ],
    )

    return bundle.model_dump(mode="json", exclude_none=True)
