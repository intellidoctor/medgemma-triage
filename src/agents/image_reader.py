"""Medical image analysis agent.

Takes uploaded medical images (wounds, rashes, X-rays), sends them to
MedGemma 4B, and returns structured findings (description, suspected
conditions, severity). These findings feed into the triage classifier
via PatientData.image_findings.

Usage:
    from src.agents.image_reader import analyze, ImageFindings

    findings = analyze(image_bytes, mime_type="image/jpeg")
    print(findings.severity, findings.description)
    summary = findings.to_triage_summary()
"""

import json
import logging
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.medgemma import analyze_image as _model_analyze_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ImageSeverity(str, Enum):
    """Severity levels for medical image findings."""

    CRITICAL = "CRITICAL"
    SEVERE = "SEVERE"
    MODERATE = "MODERATE"
    MILD = "MILD"
    NORMAL = "NORMAL"


class ImageFindings(BaseModel):
    """Structured output from the image analysis agent."""

    modality: str = Field(
        default="unknown", description="Image modality (X-ray, photo, etc.)"
    )
    description: str = Field(default="", description="Clinical description of findings")
    suspected_conditions: list[str] = Field(
        default_factory=list, description="Possible diagnoses"
    )
    severity: ImageSeverity = Field(default=ImageSeverity.MODERATE)
    key_observations: list[str] = Field(
        default_factory=list, description="Notable visual findings"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    requires_specialist: bool = Field(
        default=False, description="Whether specialist referral is recommended"
    )
    raw_model_response: str = Field(default="")
    parse_failed: bool = False

    def to_triage_summary(self) -> str:
        """Format findings as a single string for PatientData.image_findings."""
        parts: list[str] = []
        parts.append(f"[{self.modality}] {self.description}")
        if self.suspected_conditions:
            parts.append(f"Suspected: {', '.join(self.suspected_conditions)}")
        parts.append(f"Severity: {self.severity.value}")
        if self.key_observations:
            parts.append(f"Observations: {'; '.join(self.key_observations)}")
        if self.requires_specialist:
            parts.append("Specialist referral recommended")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_IMAGE_SYSTEM_PROMPT = """\
You are a medical image analysis assistant for a Brazilian SUS emergency room. \
You assist triage nurses — you never replace them.

## Your Task
Analyze the provided medical image and return structured findings.

## Severity Levels

- CRITICAL: Immediate life threat. Tension pneumothorax, \
open fracture with vascular compromise, large hemorrhage.
- SEVERE: Urgent, needs prompt intervention. Displaced \
fracture, deep wound, extensive burn, significant effusion.
- MODERATE: Notable finding needing evaluation. Simple \
fracture, moderate wound, rash with systemic signs.
- MILD: Minor, low urgency. Superficial wound, localized \
rash, minor bruising, small abrasion.
- NORMAL: No significant abnormality. Normal anatomy.

## Clinical Red Flags (escalate severity)
- Signs of infection (erythema, warmth, purulent discharge)
- Neurovascular compromise (pallor, pulselessness, paresthesia)
- Compartment syndrome signs
- Open fractures or dislocations
- Burns involving face, hands, genitalia, or circumferential
- Signs of abuse (patterned injuries, multiple healing stages)

## Conservative Bias
When uncertain, err on the side of higher severity. It is safer to \
over-triage than to under-triage.

## Response Format
Respond ONLY with valid JSON (no markdown, no backticks):
{
    "modality": "X-ray|photo|CT|MRI|ultrasound|other",
    "description": "Brief clinical description of what the image shows",
    "suspected_conditions": ["condition1", "condition2"],
    "severity": "CRITICAL|SEVERE|MODERATE|MILD|NORMAL",
    "key_observations": ["observation1", "observation2"],
    "confidence": 0.0-1.0,
    "requires_specialist": true/false
}
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_image_prompt(clinical_context: Optional[str] = None) -> str:
    """Build the user prompt for image analysis."""
    prompt = "Analyze this medical image and provide structured findings."
    if clinical_context:
        prompt += f"\n\nClinical context: {clinical_context}"
    return prompt


def _parse_image_response(raw: str) -> dict:
    """Parse model response into an image findings dict using three-tier strategy.

    Tier 1: Extract JSON object from response.
    Tier 2: Regex fallback — extract severity word from text.
    Tier 3: Default to MODERATE with parse_failed flag.
    """
    # Tier 1: Try to find and parse a JSON object (brace-counting for nested JSON)
    start = raw.find("{")
    if start != -1:
        depth = 0
        json_str = None
        for i, ch in enumerate(raw[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0:
                json_str = raw[start : i + 1]
                break
        if json_str:
            try:
                parsed = json.loads(json_str)
                severity_str = str(parsed.get("severity", "")).upper().strip()
                valid_severities = {s.value for s in ImageSeverity}
                if severity_str in valid_severities:
                    return {
                        "modality": str(parsed.get("modality", "unknown")),
                        "description": str(parsed.get("description", "")),
                        "suspected_conditions": parsed.get("suspected_conditions", []),
                        "severity": severity_str,
                        "key_observations": parsed.get("key_observations", []),
                        "confidence": max(
                            0.0, min(1.0, float(parsed.get("confidence", 0.7)))
                        ),
                        "requires_specialist": bool(
                            parsed.get("requires_specialist", False)
                        ),
                        "parse_failed": False,
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                logger.warning("JSON parsing failed, trying regex fallback")

    # Tier 2: Regex fallback — look for severity mention
    severity_pattern = r"\b(CRITICAL|SEVERE|MODERATE|MILD|NORMAL)\b"
    severity_match = re.search(severity_pattern, raw.upper())
    if severity_match:
        severity_str = severity_match.group(1)
        logger.warning(
            "Used regex fallback to extract image severity: %s", severity_str
        )
        return {
            "modality": "unknown",
            "description": raw[:500],
            "suspected_conditions": [],
            "severity": severity_str,
            "key_observations": [],
            "confidence": 0.5,
            "requires_specialist": False,
            "parse_failed": False,
        }

    # Tier 3: Default to MODERATE (conservative middle ground)
    logger.error("Could not parse severity from model response")
    return {
        "modality": "unknown",
        "description": raw[:500],
        "suspected_conditions": [],
        "severity": "MODERATE",
        "key_observations": [],
        "confidence": 0.3,
        "requires_specialist": False,
        "parse_failed": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    clinical_context: str | None = None,
) -> ImageFindings:
    """Analyze a medical image and return structured findings.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.).
        mime_type: MIME type of the image.
        clinical_context: Optional patient context to guide analysis.

    Returns:
        ImageFindings with severity, description, and observations.

    Raises:
        openai.APIError: If the model call fails (not caught here).
        EnvironmentError: If model configuration is missing.
    """
    user_prompt = _build_image_prompt(clinical_context)

    logger.info("Calling MedGemma 4B for image analysis")
    raw_response = _model_analyze_image(
        image=image_bytes,
        prompt=user_prompt,
        system_prompt=_IMAGE_SYSTEM_PROMPT,
        mime_type=mime_type,
        max_tokens=1024,
        temperature=0.1,
    )
    logger.info("Model response received (%d chars)", len(raw_response))

    parsed = _parse_image_response(raw_response)

    return ImageFindings(
        modality=parsed["modality"],
        description=parsed["description"],
        suspected_conditions=parsed["suspected_conditions"],
        severity=ImageSeverity(parsed["severity"]),
        key_observations=parsed["key_observations"],
        confidence=parsed["confidence"],
        requires_specialist=parsed["requires_specialist"],
        raw_model_response=raw_response,
        parse_failed=parsed["parse_failed"],
    )
