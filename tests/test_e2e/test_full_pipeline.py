"""End-to-end tests for the full triage pipeline.

Loads real sample case JSON files from data/sample_cases/ and runs them
through the complete pipeline (image analysis → triage → FHIR generation)
using the conftest auto-patching of generate_text/analyze_image.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agents.image_reader import ImageFindings, ImageSeverity
from src.agents.triage import PatientData, TriageColor, VitalSigns
from src.pipeline.orchestrator import run_pipeline

SAMPLE_CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "sample_cases"

ALL_CASE_FILES = sorted(SAMPLE_CASES_DIR.glob("case_*.json"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_case(filename: str) -> dict:
    """Load a sample case JSON from data/sample_cases/."""
    path = SAMPLE_CASES_DIR / filename
    with open(path) as f:
        return json.load(f)


def case_to_patient_data(case: dict) -> PatientData:
    """Convert a case JSON patient dict to PatientData with VitalSigns."""
    p = case["patient"]

    vital_signs = None
    if "vital_signs" in p and p["vital_signs"]:
        vital_signs = VitalSigns(**p["vital_signs"])

    return PatientData(
        chief_complaint=p["chief_complaint"],
        symptoms=p.get("symptoms"),
        onset=p.get("onset"),
        pain_scale=p.get("pain_scale"),
        vital_signs=vital_signs,
        age=p.get("age"),
        sex=p.get("sex"),
        history=p.get("history"),
        medications=p.get("medications"),
        allergies=p.get("allergies"),
        notes=p.get("notes"),
    )


# ---------------------------------------------------------------------------
# Individual case tests
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    def test_chest_pain_case_en(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["triage_result"].reasoning
        assert result["fhir_bundle"] is not None
        assert result["fhir_bundle"]["resourceType"] == "Bundle"
        assert len(result["fhir_bundle"]["entry"]) == 4
        assert result["errors"] == []

    def test_pediatric_fever_case_en(self) -> None:
        case = load_case("case_02_pediatric_fever.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []

    def test_ankle_sprain_case_en(self) -> None:
        case = load_case("case_03_ankle_sprain.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []

    def test_chest_pain_case_pt(self) -> None:
        case = load_case("case_04_dor_toracica.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []

    def test_pediatric_fever_case_pt(self) -> None:
        case = load_case("case_05_febre_pediatrica.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []

    def test_ankle_sprain_case_pt(self) -> None:
        case = load_case("case_06_entorse_tornozelo.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []


# ---------------------------------------------------------------------------
# Parametrized test across all cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_file",
    ALL_CASE_FILES,
    ids=[f.stem for f in ALL_CASE_FILES],
)
def test_all_cases_produce_valid_output(case_file: Path) -> None:
    with open(case_file) as f:
        case = json.load(f)

    patient = case_to_patient_data(case)
    result = run_pipeline(patient)

    # Triage result should exist with valid fields
    triage = result["triage_result"]
    assert triage is not None
    assert triage.triage_color in TriageColor
    assert triage.triage_level
    assert triage.max_wait_minutes >= 0
    assert triage.reasoning
    assert 0.0 <= triage.confidence <= 1.0

    # FHIR bundle should exist with 4 entries
    bundle = result["fhir_bundle"]
    assert bundle is not None
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 4

    # No errors
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# Image path tests
# ---------------------------------------------------------------------------


class TestPipelineWithImages:
    def test_pipeline_with_image_bytes(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)

        # Patch at the orchestrator level — the conftest patches the
        # definition site (src.models.medgemma.analyze_image) but
        # image_reader.py imports the function at load time, so the
        # patch doesn't propagate through the from-import chain.
        with patch(
            "src.pipeline.orchestrator.analyze_image",
        ) as mock_analyze:
            mock_analyze.return_value = ImageFindings(
                modality="X-ray",
                description="No acute abnormalities identified",
                suspected_conditions=[],
                severity=ImageSeverity.NORMAL,
                key_observations=[],
                confidence=0.7,
                requires_specialist=False,
                raw_model_response="{}",
            )
            result = run_pipeline(
                patient,
                image_bytes=b"fake-xray-image-bytes",
                image_mime_type="image/png",
            )

        assert result["triage_result"] is not None
        assert result["image_findings"] is not None
        assert result["image_findings"].description
        assert result["patient_data"].image_findings is not None
        assert result["fhir_bundle"] is not None
        assert result["errors"] == []


# ---------------------------------------------------------------------------
# FHIR bundle structure tests
# ---------------------------------------------------------------------------


class TestPipelineFhirOutput:
    def test_pipeline_fhir_bundle_structure(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        bundle = result["fhir_bundle"]
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"

        entries = bundle["entry"]
        assert len(entries) == 4

        resource_types = [e["resource"]["resourceType"] for e in entries]
        assert "Patient" in resource_types
        assert "Encounter" in resource_types
        assert "Observation" in resource_types
        assert "Condition" in resource_types

    def test_pipeline_fhir_has_vitals(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)
        result = run_pipeline(patient)

        bundle = result["fhir_bundle"]
        # Find the Observation entry (vital signs)
        observation = None
        for entry in bundle["entry"]:
            if entry["resource"]["resourceType"] == "Observation":
                observation = entry["resource"]
                break

        assert observation is not None
        # Observation should have components for vital signs
        assert "component" in observation
        components = observation["component"]
        assert len(components) > 0

        # Filter to vital sign components (those with LOINC coding);
        # the first two components are Confidence/Reasoning with text-only codes.
        vital_displays = [
            c["code"]["coding"][0]["display"]
            for c in components
            if "coding" in c["code"]
        ]
        assert "Heart rate" in vital_displays
        assert "Blood pressure" in vital_displays


# ---------------------------------------------------------------------------
# Error resilience tests
# ---------------------------------------------------------------------------


class TestPipelineErrorResilience:
    def test_pipeline_error_resilience(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)

        with patch(
            "src.pipeline.orchestrator.classify_patient",
            side_effect=RuntimeError("Model endpoint unreachable"),
        ):
            result = run_pipeline(patient)

        # Pipeline should not crash
        assert result.get("triage_result") is None
        assert any("Triage classification failed" in e for e in result["errors"])
        # FHIR should be None since triage failed
        assert result["fhir_bundle"] is None

    def test_pipeline_image_failure_continues(self) -> None:
        case = load_case("case_01_chest_pain.json")
        patient = case_to_patient_data(case)

        with patch(
            "src.pipeline.orchestrator.analyze_image",
            side_effect=RuntimeError("GPU OOM"),
        ):
            result = run_pipeline(
                patient,
                image_bytes=b"some-image",
            )

        # Triage should still succeed despite image failure
        assert result["triage_result"] is not None
        assert result["triage_result"].triage_color in TriageColor
        assert result["fhir_bundle"] is not None
        assert len(result["errors"]) == 1
        assert "Image analysis failed" in result["errors"][0]
