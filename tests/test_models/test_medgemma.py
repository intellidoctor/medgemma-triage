"""Integration tests for MedGemma model interface.

These tests hit real Vertex AI endpoints. They require:
    - GOOGLE_APPLICATION_CREDENTIALS_BASE64 set in .env
    - MEDGEMMA_27B_BASE_URL set in .env
    - MEDGEMMA_4B_BASE_URL set in .env
    - Both endpoints deployed and running
"""

import io

import pytest

pytestmark = pytest.mark.integration

from PIL import Image

from src.models.medgemma import _get_token, analyze_image, generate_text


class TestCredentials:
    def test_credentials_available(self):
        """Can we obtain a GCP bearer token from the service account?"""
        token = _get_token()
        assert isinstance(token, str)
        assert len(token) > 50  # bearer tokens are long


class TestGenerateText:
    def test_medical_question(self):
        """27B responds to a Manchester Protocol question."""
        response = generate_text(
            prompt="In the Manchester Triage System, what color is assigned to a patient with chest pain?",
            system_prompt="You are a triage nurse expert in the Manchester Protocol.",
            max_tokens=256,
        )
        assert isinstance(response, str)
        assert len(response) > 20
        # Should mention a triage color or severity level
        response_lower = response.lower()
        assert any(
            term in response_lower
            for term in [
                "red",
                "orange",
                "yellow",
                "green",
                "blue",
                "amber",
                "immediate",
                "urgent",
                "emergency",
            ]
        )

    def test_no_system_prompt(self):
        """27B works without a system prompt."""
        response = generate_text(
            prompt="Define tachycardia in one sentence.",
            max_tokens=100,
        )
        assert isinstance(response, str)
        assert len(response) > 10


class TestAnalyzeImage:
    def test_synthetic_image(self):
        """4B responds to a synthetic image (solid red square)."""
        img = Image.new("RGB", (64, 64), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        response = analyze_image(
            image=img_bytes,
            prompt="Describe this image briefly.",
            max_tokens=100,
        )
        assert isinstance(response, str)
        assert len(response) > 5
