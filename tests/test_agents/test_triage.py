"""Tests for the Manchester Protocol triage classifier agent."""

import json
from unittest.mock import patch

import pytest

from src.agents.triage import (
    PatientData,
    TriageColor,
    TriageResult,
    VitalSigns,
    _build_user_prompt,
    _parse_triage_response,
    classify,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chest_pain_patient() -> PatientData:
    return PatientData(
        chief_complaint="Chest pain radiating to left arm",
        symptoms=["diaphoresis", "nausea", "shortness of breath"],
        onset="30 minutes ago",
        pain_scale=9,
        vital_signs=VitalSigns(
            heart_rate=110,
            blood_pressure="180/100",
            respiratory_rate=22,
            spo2=94.0,
        ),
        age=55,
        sex="M",
        history=["hypertension", "diabetes type 2"],
        medications=["losartan", "metformin"],
    )


@pytest.fixture
def minimal_patient() -> PatientData:
    return PatientData(chief_complaint="Headache")


@pytest.fixture
def valid_json_response() -> str:
    return json.dumps(
        {
            "triage_color": "ORANGE",
            "reasoning": "Chest pain with cardiac risk factors "
            "requires urgent evaluation.",
            "key_discriminators": ["severe pain", "cardiac risk", "diaphoresis"],
            "confidence": 0.9,
        }
    )


# ---------------------------------------------------------------------------
# Unit tests: data models
# ---------------------------------------------------------------------------


class TestPatientData:
    def test_minimal_patient(self) -> None:
        patient = PatientData(chief_complaint="Headache")
        assert patient.chief_complaint == "Headache"
        assert patient.symptoms is None
        assert patient.vital_signs is None

    def test_pain_scale_valid_range(self) -> None:
        patient = PatientData(chief_complaint="Pain", pain_scale=5)
        assert patient.pain_scale == 5

    def test_pain_scale_min(self) -> None:
        patient = PatientData(chief_complaint="Pain", pain_scale=0)
        assert patient.pain_scale == 0

    def test_pain_scale_max(self) -> None:
        patient = PatientData(chief_complaint="Pain", pain_scale=10)
        assert patient.pain_scale == 10

    def test_pain_scale_too_high(self) -> None:
        with pytest.raises(ValueError):
            PatientData(chief_complaint="Pain", pain_scale=11)

    def test_pain_scale_too_low(self) -> None:
        with pytest.raises(ValueError):
            PatientData(chief_complaint="Pain", pain_scale=-1)

    def test_full_patient(self, chest_pain_patient: PatientData) -> None:
        assert chest_pain_patient.age == 55
        assert chest_pain_patient.vital_signs is not None
        assert chest_pain_patient.vital_signs.heart_rate == 110


class TestVitalSigns:
    def test_all_optional(self) -> None:
        vs = VitalSigns()
        assert vs.heart_rate is None
        assert vs.blood_pressure is None

    def test_partial_vitals(self) -> None:
        vs = VitalSigns(heart_rate=80, temperature=37.2)
        assert vs.heart_rate == 80
        assert vs.temperature == 37.2
        assert vs.spo2 is None


class TestTriageColor:
    def test_all_colors(self) -> None:
        assert len(TriageColor) == 5
        for color in ["RED", "ORANGE", "YELLOW", "GREEN", "BLUE"]:
            assert TriageColor(color).value == color


# ---------------------------------------------------------------------------
# Unit tests: prompt construction
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    def test_minimal_prompt(self, minimal_patient: PatientData) -> None:
        prompt = _build_user_prompt(minimal_patient)
        assert "Headache" in prompt
        assert "JSON" in prompt

    def test_includes_vitals(self, chest_pain_patient: PatientData) -> None:
        prompt = _build_user_prompt(chest_pain_patient)
        assert "HR 110 bpm" in prompt
        assert "BP 180/100 mmHg" in prompt
        assert "SpO2 94.0%" in prompt

    def test_includes_demographics(self, chest_pain_patient: PatientData) -> None:
        prompt = _build_user_prompt(chest_pain_patient)
        assert "55 years old" in prompt
        assert "M" in prompt

    def test_includes_pain_scale(self, chest_pain_patient: PatientData) -> None:
        prompt = _build_user_prompt(chest_pain_patient)
        assert "9/10" in prompt

    def test_includes_history(self, chest_pain_patient: PatientData) -> None:
        prompt = _build_user_prompt(chest_pain_patient)
        assert "hypertension" in prompt
        assert "diabetes type 2" in prompt

    def test_includes_medications(self, chest_pain_patient: PatientData) -> None:
        prompt = _build_user_prompt(chest_pain_patient)
        assert "losartan" in prompt

    def test_includes_image_findings(self) -> None:
        patient = PatientData(
            chief_complaint="Cough",
            image_findings="Bilateral infiltrates on chest X-ray",
        )
        prompt = _build_user_prompt(patient)
        assert "Bilateral infiltrates" in prompt

    def test_includes_notes(self) -> None:
        patient = PatientData(chief_complaint="Fever", notes="Patient appears toxic")
        prompt = _build_user_prompt(patient)
        assert "Patient appears toxic" in prompt


# ---------------------------------------------------------------------------
# Unit tests: response parsing
# ---------------------------------------------------------------------------


class TestParseTriageResponse:
    def test_valid_json(self, valid_json_response: str) -> None:
        result = _parse_triage_response(valid_json_response)
        assert result["triage_color"] == "ORANGE"
        assert result["confidence"] == 0.9
        assert "cardiac" in result["reasoning"]
        assert len(result["key_discriminators"]) == 3
        assert result["parse_failed"] is False

    def test_json_with_surrounding_text(self) -> None:
        inner = json.dumps(
            {
                "triage_color": "RED",
                "reasoning": "Life threat",
                "key_discriminators": ["airway"],
                "confidence": 0.95,
            }
        )
        raw = f"Here is my assessment:\n{inner}\nEnd."
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "RED"
        assert result["parse_failed"] is False

    def test_json_missing_confidence_uses_default(self) -> None:
        raw = json.dumps(
            {
                "triage_color": "GREEN",
                "reasoning": "Minor complaint",
                "key_discriminators": [],
            }
        )
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "GREEN"
        assert result["confidence"] == 0.7

    def test_regex_fallback(self) -> None:
        raw = "Based on the symptoms, I would classify this as ORANGE urgency."
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "ORANGE"
        assert result["confidence"] == 0.5
        assert result["parse_failed"] is False

    def test_regex_fallback_lowercase(self) -> None:
        raw = "The patient should be classified as red priority."
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "RED"

    def test_parse_failure_defaults_yellow(self) -> None:
        raw = "I cannot determine the appropriate classification."
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "YELLOW"
        assert result["parse_failed"] is True
        assert result["confidence"] == 0.3

    def test_invalid_color_in_json_falls_to_regex(self) -> None:
        raw = json.dumps({"triage_color": "PURPLE", "reasoning": "test"})
        result = _parse_triage_response(raw)
        # "PURPLE" isn't valid, JSON tier fails, no color word in text either
        # Actually the JSON itself contains no valid color word
        assert result["parse_failed"] is True

    def test_nested_json(self) -> None:
        raw = json.dumps(
            {
                "triage_color": "ORANGE",
                "reasoning": "Severe pain with cardiac risk",
                "key_discriminators": [
                    {"name": "chest pain", "severity": "high"},
                    {"name": "diaphoresis", "severity": "moderate"},
                ],
                "confidence": 0.85,
            }
        )
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "ORANGE"
        assert result["parse_failed"] is False

    def test_confidence_clamped_above_one(self) -> None:
        raw = json.dumps(
            {
                "triage_color": "GREEN",
                "reasoning": "Minor",
                "key_discriminators": [],
                "confidence": 1.5,
            }
        )
        result = _parse_triage_response(raw)
        assert result["confidence"] == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        raw = json.dumps(
            {
                "triage_color": "GREEN",
                "reasoning": "Minor",
                "key_discriminators": [],
                "confidence": -0.3,
            }
        )
        result = _parse_triage_response(raw)
        assert result["confidence"] == 0.0

    def test_json_with_markdown_fences(self) -> None:
        inner = json.dumps(
            {
                "triage_color": "YELLOW",
                "reasoning": "Moderate urgency",
                "key_discriminators": ["fever"],
                "confidence": 0.8,
            }
        )
        raw = f"```json\n{inner}\n```"
        result = _parse_triage_response(raw)
        assert result["triage_color"] == "YELLOW"
        assert result["parse_failed"] is False


# ---------------------------------------------------------------------------
# Unit tests: classify (mocked model)
# ---------------------------------------------------------------------------


class TestClassify:
    @patch("src.agents.triage.generate_text")
    def test_valid_classification(
        self,
        mock_generate: object,
        chest_pain_patient: PatientData,
        valid_json_response: str,
    ) -> None:
        mock_generate.return_value = valid_json_response  # type: ignore[attr-defined]

        result = classify(chest_pain_patient)

        assert isinstance(result, TriageResult)
        assert result.triage_color == TriageColor.ORANGE
        assert result.triage_level == "Muito urgente"
        assert result.max_wait_minutes == 10
        assert result.parse_failed is False
        assert result.raw_model_response == valid_json_response

    @patch("src.agents.triage.generate_text")
    def test_red_classification(self, mock_generate: object) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "triage_color": "RED",
                "reasoning": "Airway compromise",
                "key_discriminators": ["airway obstruction"],
                "confidence": 0.95,
            }
        )
        patient = PatientData(chief_complaint="Choking, cannot breathe")
        result = classify(patient)

        assert result.triage_color == TriageColor.RED
        assert result.triage_level == "Emergência"
        assert result.max_wait_minutes == 0

    @patch("src.agents.triage.generate_text")
    def test_green_classification(self, mock_generate: object) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "triage_color": "GREEN",
                "reasoning": "Minor complaint, stable vitals",
                "key_discriminators": ["mild pain"],
                "confidence": 0.85,
            }
        )
        patient = PatientData(chief_complaint="Paper cut on finger", pain_scale=1)
        result = classify(patient)

        assert result.triage_color == TriageColor.GREEN
        assert result.triage_level == "Pouco urgente"
        assert result.max_wait_minutes == 120

    @patch("src.agents.triage.generate_text")
    def test_blue_classification(self, mock_generate: object) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "triage_color": "BLUE",
                "reasoning": "Prescription refill, no acute complaint",
                "key_discriminators": [],
                "confidence": 0.9,
            }
        )
        patient = PatientData(chief_complaint="Need prescription refill")
        result = classify(patient)

        assert result.triage_color == TriageColor.BLUE
        assert result.triage_level == "Não urgente"
        assert result.max_wait_minutes == 240

    @patch("src.agents.triage.generate_text")
    def test_fallback_parsing(self, mock_generate: object) -> None:
        mock_generate.return_value = "I think this is ORANGE priority."  # type: ignore[attr-defined]
        patient = PatientData(chief_complaint="Severe headache")
        result = classify(patient)

        assert result.triage_color == TriageColor.ORANGE
        assert result.parse_failed is False

    @patch("src.agents.triage.generate_text")
    def test_parse_failure_defaults_yellow(self, mock_generate: object) -> None:
        mock_generate.return_value = "Unable to assess."  # type: ignore[attr-defined]
        patient = PatientData(chief_complaint="Vague symptoms")
        result = classify(patient)

        assert result.triage_color == TriageColor.YELLOW
        assert result.parse_failed is True
        assert result.max_wait_minutes == 60

    @patch("src.agents.triage.generate_text")
    def test_model_call_parameters(
        self, mock_generate: object, minimal_patient: PatientData
    ) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "triage_color": "GREEN",
                "reasoning": "Minor",
                "key_discriminators": [],
                "confidence": 0.8,
            }
        )
        classify(minimal_patient)

        mock_generate.assert_called_once()  # type: ignore[attr-defined]
        call_kwargs = mock_generate.call_args  # type: ignore[attr-defined]
        assert call_kwargs.kwargs["max_tokens"] == 1024
        assert call_kwargs.kwargs["temperature"] == 0.1
        assert "Manchester" in call_kwargs.kwargs["system_prompt"]
        assert "Headache" in call_kwargs.kwargs["prompt"]

    @patch("src.agents.triage.generate_text")
    def test_api_error_propagates(self, mock_generate: object) -> None:
        mock_generate.side_effect = RuntimeError("API connection failed")  # type: ignore[attr-defined]
        patient = PatientData(chief_complaint="Fever")

        with pytest.raises(RuntimeError, match="API connection failed"):
            classify(patient)


# ---------------------------------------------------------------------------
# Integration test (requires real model endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestClassifyIntegration:
    def test_chest_pain_high_acuity(self, chest_pain_patient: PatientData) -> None:
        """Chest pain + cardiac risk factors should be RED or ORANGE."""
        result = classify(chest_pain_patient)

        assert result.triage_color in (TriageColor.RED, TriageColor.ORANGE)
        assert result.max_wait_minutes <= 10
        assert len(result.reasoning) > 0
        assert result.parse_failed is False
