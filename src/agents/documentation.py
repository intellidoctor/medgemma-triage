"""Documentation agent — generates FHIR R4 output from triage results.

Wraps the FHIR builder for use in the LangGraph pipeline. Takes patient
data and triage results, returns a serialized FHIR R4 Bundle.
"""

import logging
from typing import Optional

from src.agents.triage import PatientData, TriageResult
from src.fhir.builder import build_fhir_bundle

logger = logging.getLogger(__name__)


def generate_fhir_bundle(
    patient_data: PatientData,
    triage_result: TriageResult,
    patient_name: str = "Paciente",
    patient_age: Optional[int] = None,
    patient_sex: Optional[str] = None,
) -> dict:
    """Generate a FHIR R4 Bundle from triage pipeline results.

    Args:
        patient_data: Structured patient data from intake.
        triage_result: Classification from the triage agent.
        patient_name: Display name (defaults to "Paciente").
        patient_age: Age in years (falls back to patient_data.age).
        patient_sex: "M" or "F" (falls back to patient_data.sex).

    Returns:
        FHIR R4 Bundle as a JSON-serializable dict.
    """
    age = patient_age if patient_age is not None else patient_data.age
    sex = patient_sex or patient_data.sex

    logger.info("Generating FHIR R4 Bundle for patient '%s'", patient_name)
    bundle = build_fhir_bundle(
        patient_name=patient_name,
        patient_age=age,
        patient_sex=sex,
        patient_data=patient_data,
        triage_result=triage_result,
    )
    logger.info("FHIR Bundle generated: %d entries", len(bundle.get("entry", [])))
    return bundle
