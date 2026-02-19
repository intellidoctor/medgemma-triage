"""Tests for the medical image analysis agent."""

import json
from unittest.mock import patch

import pytest

from src.agents.image_reader import (
    ImageFindings,
    ImageSeverity,
    _build_image_prompt,
    _parse_image_response,
    analyze,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_json_response() -> str:
    return json.dumps(
        {
            "modality": "X-ray",
            "description": "Chest X-ray showing bilateral infiltrates",
            "suspected_conditions": ["pneumonia", "pulmonary edema"],
            "severity": "SEVERE",
            "key_observations": [
                "bilateral opacities",
                "air bronchograms",
            ],
            "confidence": 0.85,
            "requires_specialist": True,
        }
    )


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Minimal valid JPEG header for testing (not a real image)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Unit tests: data models
# ---------------------------------------------------------------------------


class TestImageSeverity:
    def test_all_levels(self) -> None:
        assert len(ImageSeverity) == 5
        for level in ["CRITICAL", "SEVERE", "MODERATE", "MILD", "NORMAL"]:
            assert ImageSeverity(level).value == level


class TestImageFindings:
    def test_minimal_construction(self) -> None:
        findings = ImageFindings(
            severity=ImageSeverity.MODERATE,
            raw_model_response="test",
        )
        assert findings.severity == ImageSeverity.MODERATE
        assert findings.modality == "unknown"
        assert findings.description == ""
        assert findings.suspected_conditions == []
        assert findings.key_observations == []
        assert findings.requires_specialist is False

    def test_full_construction(self) -> None:
        findings = ImageFindings(
            modality="X-ray",
            description="Fracture of the distal radius",
            suspected_conditions=["Colles fracture"],
            severity=ImageSeverity.SEVERE,
            key_observations=["cortical disruption", "dorsal angulation"],
            confidence=0.9,
            requires_specialist=True,
            raw_model_response="raw",
            parse_failed=False,
        )
        assert findings.modality == "X-ray"
        assert findings.confidence == 0.9
        assert findings.requires_specialist is True
        assert len(findings.key_observations) == 2

    def test_to_triage_summary_full(self) -> None:
        findings = ImageFindings(
            modality="photo",
            description="Deep laceration on forearm",
            suspected_conditions=["laceration", "tendon injury"],
            severity=ImageSeverity.SEVERE,
            key_observations=["exposed tissue", "active bleeding"],
            confidence=0.8,
            requires_specialist=True,
            raw_model_response="raw",
        )
        summary = findings.to_triage_summary()
        assert "[photo]" in summary
        assert "Deep laceration" in summary
        assert "laceration" in summary
        assert "Severity: SEVERE" in summary
        assert "exposed tissue" in summary
        assert "Specialist referral recommended" in summary

    def test_to_triage_summary_minimal(self) -> None:
        findings = ImageFindings(
            modality="unknown",
            description="No findings",
            severity=ImageSeverity.NORMAL,
            raw_model_response="raw",
        )
        summary = findings.to_triage_summary()
        assert "Severity: NORMAL" in summary
        assert "Specialist" not in summary


# ---------------------------------------------------------------------------
# Unit tests: prompt construction
# ---------------------------------------------------------------------------


class TestBuildImagePrompt:
    def test_without_context(self) -> None:
        prompt = _build_image_prompt()
        assert "Analyze" in prompt
        assert "Clinical context" not in prompt

    def test_with_context(self) -> None:
        prompt = _build_image_prompt("Patient reports fall from height")
        assert "Clinical context" in prompt
        assert "fall from height" in prompt


# ---------------------------------------------------------------------------
# Unit tests: response parsing
# ---------------------------------------------------------------------------


class TestParseImageResponse:
    def test_valid_json(self, valid_json_response: str) -> None:
        result = _parse_image_response(valid_json_response)
        assert result["severity"] == "SEVERE"
        assert result["modality"] == "X-ray"
        assert result["confidence"] == 0.85
        assert result["requires_specialist"] is True
        assert len(result["suspected_conditions"]) == 2
        assert result["parse_failed"] is False

    def test_json_with_markdown_fences(self) -> None:
        inner = json.dumps(
            {
                "modality": "photo",
                "description": "Wound on left arm",
                "suspected_conditions": ["laceration"],
                "severity": "MODERATE",
                "key_observations": ["clean edges"],
                "confidence": 0.75,
                "requires_specialist": False,
            }
        )
        raw = f"```json\n{inner}\n```"
        result = _parse_image_response(raw)
        assert result["severity"] == "MODERATE"
        assert result["parse_failed"] is False

    def test_json_with_surrounding_text(self) -> None:
        inner = json.dumps(
            {
                "modality": "X-ray",
                "description": "Normal chest",
                "suspected_conditions": [],
                "severity": "NORMAL",
                "key_observations": [],
                "confidence": 0.9,
                "requires_specialist": False,
            }
        )
        raw = f"Here is my analysis:\n{inner}\nEnd of analysis."
        result = _parse_image_response(raw)
        assert result["severity"] == "NORMAL"
        assert result["parse_failed"] is False

    def test_regex_fallback(self) -> None:
        raw = "The image shows a SEVERE wound requiring immediate attention."
        result = _parse_image_response(raw)
        assert result["severity"] == "SEVERE"
        assert result["confidence"] == 0.5
        assert result["parse_failed"] is False
        assert result["modality"] == "unknown"

    def test_regex_fallback_lowercase(self) -> None:
        raw = "This appears to be a mild bruise with no complications."
        result = _parse_image_response(raw)
        assert result["severity"] == "MILD"

    def test_parse_failure_defaults_moderate(self) -> None:
        raw = "Unable to analyze the provided image."
        result = _parse_image_response(raw)
        assert result["severity"] == "MODERATE"
        assert result["parse_failed"] is True
        assert result["confidence"] == 0.3

    def test_invalid_severity_in_json(self) -> None:
        raw = json.dumps({"severity": "EXTREME", "description": "test"})
        result = _parse_image_response(raw)
        # "EXTREME" not valid, falls through to tier 3
        assert result["parse_failed"] is True

    def test_confidence_clamped_above_one(self) -> None:
        raw = json.dumps(
            {
                "modality": "photo",
                "description": "Test",
                "severity": "MILD",
                "confidence": 1.5,
            }
        )
        result = _parse_image_response(raw)
        assert result["confidence"] == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        raw = json.dumps(
            {
                "modality": "photo",
                "description": "Test",
                "severity": "MILD",
                "confidence": -0.3,
            }
        )
        result = _parse_image_response(raw)
        assert result["confidence"] == 0.0

    def test_missing_confidence_uses_default(self) -> None:
        raw = json.dumps(
            {
                "modality": "photo",
                "description": "Test",
                "severity": "NORMAL",
            }
        )
        result = _parse_image_response(raw)
        assert result["confidence"] == 0.7


# ---------------------------------------------------------------------------
# Unit tests: analyze (mocked model)
# ---------------------------------------------------------------------------


class TestAnalyze:
    @patch("src.agents.image_reader._model_analyze_image")
    def test_valid_analysis(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
        valid_json_response: str,
    ) -> None:
        mock_model.return_value = valid_json_response  # type: ignore[attr-defined]

        result = analyze(sample_image_bytes)

        assert isinstance(result, ImageFindings)
        assert result.severity == ImageSeverity.SEVERE
        assert result.modality == "X-ray"
        assert result.parse_failed is False
        assert result.raw_model_response == valid_json_response

    @patch("src.agents.image_reader._model_analyze_image")
    def test_with_clinical_context(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
        valid_json_response: str,
    ) -> None:
        mock_model.return_value = valid_json_response  # type: ignore[attr-defined]

        analyze(sample_image_bytes, clinical_context="Patient fell from ladder")

        call_kwargs = mock_model.call_args  # type: ignore[attr-defined]
        assert "fell from ladder" in call_kwargs.kwargs["prompt"]

    @patch("src.agents.image_reader._model_analyze_image")
    def test_without_clinical_context(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
        valid_json_response: str,
    ) -> None:
        mock_model.return_value = valid_json_response  # type: ignore[attr-defined]

        analyze(sample_image_bytes)

        call_kwargs = mock_model.call_args  # type: ignore[attr-defined]
        assert "Clinical context" not in call_kwargs.kwargs["prompt"]

    @patch("src.agents.image_reader._model_analyze_image")
    def test_model_call_parameters(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
        valid_json_response: str,
    ) -> None:
        mock_model.return_value = valid_json_response  # type: ignore[attr-defined]

        analyze(sample_image_bytes, mime_type="image/png")

        mock_model.assert_called_once()  # type: ignore[attr-defined]
        call_kwargs = mock_model.call_args  # type: ignore[attr-defined]
        assert call_kwargs.kwargs["max_tokens"] == 1024
        assert call_kwargs.kwargs["temperature"] == 0.1
        assert call_kwargs.kwargs["mime_type"] == "image/png"
        assert call_kwargs.kwargs["image"] == sample_image_bytes

    @patch("src.agents.image_reader._model_analyze_image")
    def test_api_error_propagates(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
    ) -> None:
        mock_model.side_effect = RuntimeError("API connection failed")  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="API connection failed"):
            analyze(sample_image_bytes)

    @patch("src.agents.image_reader._model_analyze_image")
    def test_parse_failure_returns_moderate(
        self,
        mock_model: object,
        sample_image_bytes: bytes,
    ) -> None:
        mock_model.return_value = "Unable to process."  # type: ignore[attr-defined]

        result = analyze(sample_image_bytes)

        assert result.severity == ImageSeverity.MODERATE
        assert result.parse_failed is True
