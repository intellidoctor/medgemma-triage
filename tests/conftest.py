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
            "triage_color": "ORANGE",
            "reasoning": "Acute chest pain requires urgent evaluation.",
            "key_discriminators": ["chest pain", "cardiac risk"],
            "confidence": 0.85,
        }
    ),
    "dor tor": json.dumps(
        {
            "triage_color": "ORANGE",
            "reasoning": "Dor torácica aguda requer avaliação urgente.",
            "key_discriminators": ["dor torácica", "risco cardíaco"],
            "confidence": 0.85,
        }
    ),
    "choking": json.dumps(
        {
            "triage_color": "RED",
            "reasoning": "Airway obstruction is an immediate threat to life.",
            "key_discriminators": ["airway compromise"],
            "confidence": 0.90,
        }
    ),
    "headache": json.dumps(
        {
            "triage_color": "YELLOW",
            "reasoning": "Headache without red flags is standard urgency.",
            "key_discriminators": ["headache"],
            "confidence": 0.75,
        }
    ),
    "fever": json.dumps(
        {
            "triage_color": "YELLOW",
            "reasoning": "High fever with respiratory symptoms warrants urgent evaluation.",
            "key_discriminators": ["fever", "respiratory distress"],
            "confidence": 0.80,
        }
    ),
    "febre": json.dumps(
        {
            "triage_color": "YELLOW",
            "reasoning": "Febre alta com sintomas respiratórios requer avaliação urgente.",
            "key_discriminators": ["febre", "dificuldade respiratória"],
            "confidence": 0.80,
        }
    ),
    "sprained ankle": json.dumps(
        {
            "triage_color": "GREEN",
            "reasoning": "Minor musculoskeletal injury, non-urgent.",
            "key_discriminators": ["limb problem"],
            "confidence": 0.80,
        }
    ),
    "ankle": json.dumps(
        {
            "triage_color": "GREEN",
            "reasoning": "Minor musculoskeletal injury, non-urgent.",
            "key_discriminators": ["limb problem"],
            "confidence": 0.80,
        }
    ),
    "tornozelo": json.dumps(
        {
            "triage_color": "GREEN",
            "reasoning": "Lesão musculoesquelética menor, não urgente.",
            "key_discriminators": ["problema em membro"],
            "confidence": 0.80,
        }
    ),
    "torceu": json.dumps(
        {
            "triage_color": "GREEN",
            "reasoning": "Lesão musculoesquelética menor, não urgente.",
            "key_discriminators": ["problema em membro"],
            "confidence": 0.80,
        }
    ),
    "medication refill": json.dumps(
        {
            "triage_color": "BLUE",
            "reasoning": "Non-clinical request, lowest priority.",
            "key_discriminators": ["administrative"],
            "confidence": 0.90,
        }
    ),
}

_DEFAULT_TEXT_RESPONSE = json.dumps(
    {
        "triage_color": "YELLOW",
        "reasoning": "Patient requires evaluation. Vitals and history suggest further workup.",
        "key_discriminators": ["unspecified complaint"],
        "confidence": 0.60,
    }
)

_IMAGE_RESPONSES: dict[str, str] = {
    "wound": json.dumps(
        {
            "modality": "photo",
            "description": "Deep laceration on forearm with active bleeding",
            "suspected_conditions": ["laceration", "tendon injury"],
            "severity": "SEVERE",
            "key_observations": ["exposed tissue", "active bleeding"],
            "confidence": 0.85,
            "requires_specialist": True,
        }
    ),
    "rash": json.dumps(
        {
            "modality": "photo",
            "description": "Erythematous maculopapular rash on trunk",
            "suspected_conditions": ["allergic reaction", "viral exanthem"],
            "severity": "MODERATE",
            "key_observations": ["widespread distribution", "no vesicles"],
            "confidence": 0.7,
            "requires_specialist": False,
        }
    ),
    "fracture": json.dumps(
        {
            "modality": "X-ray",
            "description": "Displaced fracture of the distal radius",
            "suspected_conditions": ["Colles fracture"],
            "severity": "SEVERE",
            "key_observations": ["cortical disruption", "dorsal angulation"],
            "confidence": 0.9,
            "requires_specialist": True,
        }
    ),
}

_DEFAULT_IMAGE_RESPONSE = json.dumps(
    {
        "modality": "unknown",
        "description": "No acute abnormalities identified",
        "suspected_conditions": [],
        "severity": "NORMAL",
        "key_observations": [],
        "confidence": 0.7,
        "requires_specialist": False,
    }
)


def _mock_generate_text(prompt: str, **kwargs: object) -> str:
    """Return a canned response matched by keyword in the prompt."""
    prompt_lower = prompt.lower()
    for keyword, response in _TRIAGE_RESPONSES.items():
        if keyword in prompt_lower:
            return response
    return _DEFAULT_TEXT_RESPONSE


def _mock_analyze_image(
    image: bytes = b"",
    prompt: str = "",
    **kwargs: object,
) -> str:
    """Return a keyword-matched JSON image analysis response."""
    prompt_lower = prompt.lower()
    for keyword, response in _IMAGE_RESPONSES.items():
        if keyword in prompt_lower:
            return response
    return _DEFAULT_IMAGE_RESPONSE


# ---------------------------------------------------------------------------
# Auto-use fixture: patches model calls at BOTH definition and usage sites
# ---------------------------------------------------------------------------

# Agents use ``from src.models.medgemma import generate_text`` which creates
# a local binding.  Patching only the definition site does NOT affect the
# already-imported references, so we must also patch the usage sites.

_GENERATE_TEXT_TARGETS = [
    "src.models.medgemma.generate_text",
    "src.agents.triage.generate_text",
    "src.agents.intake.generate_text",
]

_ANALYZE_IMAGE_TARGETS = [
    "src.models.medgemma.analyze_image",
    "src.agents.image_reader._model_analyze_image",
]


@pytest.fixture(autouse=True)
def _mock_medgemma(request: pytest.FixtureRequest) -> object:
    """Patch MedGemma model calls unless the test is marked integration."""
    if "integration" in {m.name for m in request.node.iter_markers()}:
        yield
        return

    patches = [
        patch(target, side_effect=_mock_generate_text)
        for target in _GENERATE_TEXT_TARGETS
    ] + [
        patch(target, side_effect=_mock_analyze_image)
        for target in _ANALYZE_IMAGE_TARGETS
    ]

    for p in patches:
        p.start()
    yield
    for p in reversed(patches):
        p.stop()
