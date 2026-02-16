"""Project-wide test fixtures.

Auto-patches src.models.medgemma.generate_text and analyze_image for all
non-integration tests so the full test suite runs without Vertex AI
credentials or API credits.
"""

import json
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Keyword → canned response map for generate_text
# ---------------------------------------------------------------------------

_TRIAGE_RESPONSES: dict[str, str] = {
    "chest pain": json.dumps(
        {
            "discriminator": "Chest pain",
            "color": "ORANGE",
            "priority": 2,
            "reasoning": "Acute chest pain requires urgent evaluation.",
        }
    ),
    "choking": json.dumps(
        {
            "discriminator": "Airway compromise",
            "color": "RED",
            "priority": 1,
            "reasoning": "Airway obstruction is an immediate threat to life.",
        }
    ),
    "headache": json.dumps(
        {
            "discriminator": "Headache",
            "color": "YELLOW",
            "priority": 3,
            "reasoning": "Headache without red flags is standard urgency.",
        }
    ),
    "sprained ankle": json.dumps(
        {
            "discriminator": "Limb problem",
            "color": "GREEN",
            "priority": 4,
            "reasoning": "Minor musculoskeletal injury, non-urgent.",
        }
    ),
    "medication refill": json.dumps(
        {
            "discriminator": "Administrative",
            "color": "BLUE",
            "priority": 5,
            "reasoning": "Non-clinical request, lowest priority.",
        }
    ),
}

_DEFAULT_TEXT_RESPONSE = (
    "Based on the clinical information provided, the patient should be "
    "evaluated promptly. Vital signs and history suggest further workup "
    "is warranted."
)

_DEFAULT_IMAGE_RESPONSE = (
    "The image shows no acute abnormalities. Recommend clinical correlation."
)


def _mock_generate_text(prompt: str, **kwargs: object) -> str:
    """Return a canned response matched by keyword in the prompt."""
    prompt_lower = prompt.lower()
    for keyword, response in _TRIAGE_RESPONSES.items():
        if keyword in prompt_lower:
            return response
    return _DEFAULT_TEXT_RESPONSE


def _mock_analyze_image(**kwargs: object) -> str:
    """Return a static image analysis response."""
    return _DEFAULT_IMAGE_RESPONSE


# ---------------------------------------------------------------------------
# Auto-use fixture: patches the definition site so all importers get the mock
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_medgemma(request: pytest.FixtureRequest) -> object:
    """Patch MedGemma model calls unless the test is marked integration."""
    if "integration" in {m.name for m in request.node.iter_markers()}:
        yield
        return

    with (
        patch(
            "src.models.medgemma.generate_text",
            side_effect=_mock_generate_text,
        ),
        patch(
            "src.models.medgemma.analyze_image",
            side_effect=_mock_analyze_image,
        ),
    ):
        yield
