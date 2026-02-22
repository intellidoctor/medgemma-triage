"""Manchester Protocol triage classifier agent.

Takes structured patient data, sends it to MedGemma 27B for clinical
reasoning, and returns a structured triage classification with color,
reasoning, and key discriminators.

Usage:
    from src.agents.triage import classify, PatientData, VitalSigns

    patient = PatientData(
        chief_complaint="Chest pain radiating to left arm",
        vital_signs=VitalSigns(heart_rate=110, blood_pressure="180/100"),
    )
    result = classify(patient)
    print(result.triage_color, result.reasoning)
"""

import json
import logging
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.medgemma import generate_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TriageColor(str, Enum):
    """Manchester Triage System color categories."""

    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"


TRIAGE_LEVELS: dict[TriageColor, tuple[str, int]] = {
    TriageColor.RED: ("Emergência", 0),
    TriageColor.ORANGE: ("Muito urgente", 10),
    TriageColor.YELLOW: ("Urgente", 60),
    TriageColor.GREEN: ("Pouco urgente", 120),
    TriageColor.BLUE: ("Não urgente", 240),
}


class VitalSigns(BaseModel):
    """Patient vital signs — all fields optional."""

    heart_rate: Optional[int] = Field(None, description="Beats per minute")
    blood_pressure: Optional[str] = Field(
        None, description="Systolic/diastolic, e.g. '120/80'"
    )
    respiratory_rate: Optional[int] = Field(None, description="Breaths per minute")
    temperature: Optional[float] = Field(None, description="Celsius")
    spo2: Optional[float] = Field(None, description="Oxygen saturation %")
    glucose: Optional[float] = Field(None, description="Blood glucose mg/dL")


class PatientData(BaseModel):
    """Structured patient data for triage classification."""

    chief_complaint: str = Field(..., description="Primary reason for visit")
    symptoms: Optional[list[str]] = Field(None, description="List of symptoms")
    onset: Optional[str] = Field(None, description="When symptoms started")
    duration: Optional[str] = Field(None, description="How long symptoms lasted")
    pain_scale: Optional[int] = Field(None, ge=0, le=10, description="Pain level 0-10")
    vital_signs: Optional[VitalSigns] = None
    history: Optional[list[str]] = Field(None, description="Relevant medical history")
    medications: Optional[list[str]] = Field(None, description="Current medications")
    allergies: Optional[list[str]] = Field(None, description="Known allergies")
    age: Optional[int] = Field(None, description="Patient age in years")
    sex: Optional[str] = Field(None, description="Patient sex (M/F)")
    image_findings: Optional[str] = Field(
        None, description="Findings from medical image analysis"
    )
    notes: Optional[str] = Field(None, description="Additional clinical notes")


class TriageResult(BaseModel):
    """Structured output from the triage classifier."""

    triage_color: TriageColor
    triage_level: str
    max_wait_minutes: int
    reasoning: str
    key_discriminators: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    raw_model_response: str
    parse_failed: bool = False


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_MANCHESTER_SYSTEM_PROMPT = """\
You are a Manchester Triage System (MTS) classifier for a Brazilian SUS \
emergency room. You assist triage nurses — you never replace them.

## Manchester Triage Levels

| Color  | Level           | Max Wait | Criteria                                      |
|--------|-----------------|----------|-----------------------------------------------|
| RED    | Emergência      | 0 min    | Immediate life threat, airway compromise,     |
|        |                 |          | unresponsive, active major hemorrhage,         |
|        |                 |          | shock, seizure in progress                     |
| ORANGE | Muito urgente   | 10 min   | Severe pain (8-10), altered consciousness,    |
|        |                 |          | acute neurological deficit, chest pain with   |
|        |                 |          | cardiac risk, severe respiratory distress,     |
|        |                 |          | uncontrolled hemorrhage                        |
| YELLOW | Urgente         | 60 min   | Moderate pain (4-7), fever >38.5°C,           |
|        |                 |          | vomiting/dehydration, acute abdomen,           |
|        |                 |          | moderate injury, abnormal vitals               |
| GREEN  | Pouco urgente   | 120 min  | Minor injury, mild pain (1-3), chronic         |
|        |                 |          | complaint exacerbation, stable vitals          |
| BLUE   | Não urgente     | 240 min  | Administrative, prescription refill,           |
|        |                 |          | minor complaint >7 days, no acute findings     |

## Key Discriminators to Evaluate
- Life threat (airway, breathing, circulation)
- Level of consciousness (AVPU: Alert, Voice, Pain, Unresponsive)
- Hemorrhage severity (major, minor, controlled)
- Pain severity (0-10 scale)
- Temperature (hypothermia <35°C, fever >38.5°C, high fever >40°C)
- Vital sign red flags: HR >120 or <50, RR >30 or <10, SpO2 <92%, \
SBP <90 or >200, glucose <60 or >400

## Vital Sign Red Flags (require at minimum YELLOW, consider ORANGE/RED)
- Heart rate: >120 bpm (tachycardia) or <50 bpm (bradycardia)
- Respiratory rate: >30/min or <10/min
- SpO2: <92%
- Blood pressure: systolic <90 mmHg (hypotension) or >200 mmHg (crisis)
- Temperature: <35°C or >40°C
- Glucose: <60 mg/dL (hypoglycemia) or >400 mg/dL

## Response Format
Respond ONLY with valid JSON (no markdown, no backticks):
{
    "triage_color": "RED|ORANGE|YELLOW|GREEN|BLUE",
    "reasoning": "Brief clinical reasoning for the classification",
    "key_discriminators": ["discriminator1", "discriminator2"],
    "confidence": 0.0-1.0
}
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_user_prompt(patient: PatientData) -> str:
    """Format patient data into a structured prompt for the model."""
    sections: list[str] = []

    sections.append(f"Chief complaint: {patient.chief_complaint}")

    if patient.age is not None or patient.sex:
        demo_parts: list[str] = []
        if patient.age is not None:
            demo_parts.append(f"{patient.age} years old")
        if patient.sex:
            demo_parts.append(patient.sex)
        sections.append(f"Demographics: {', '.join(demo_parts)}")

    if patient.symptoms:
        sections.append(f"Symptoms: {', '.join(patient.symptoms)}")

    if patient.onset:
        sections.append(f"Onset: {patient.onset}")

    if patient.duration:
        sections.append(f"Duration: {patient.duration}")

    if patient.pain_scale is not None:
        sections.append(f"Pain scale: {patient.pain_scale}/10")

    if patient.vital_signs:
        vs = patient.vital_signs
        vs_parts: list[str] = []
        if vs.heart_rate is not None:
            vs_parts.append(f"HR {vs.heart_rate} bpm")
        if vs.blood_pressure:
            vs_parts.append(f"BP {vs.blood_pressure} mmHg")
        if vs.respiratory_rate is not None:
            vs_parts.append(f"RR {vs.respiratory_rate}/min")
        if vs.temperature is not None:
            vs_parts.append(f"Temp {vs.temperature}°C")
        if vs.spo2 is not None:
            vs_parts.append(f"SpO2 {vs.spo2}%")
        if vs.glucose is not None:
            vs_parts.append(f"Glucose {vs.glucose} mg/dL")
        if vs_parts:
            sections.append(f"Vital signs: {', '.join(vs_parts)}")

    if patient.history:
        sections.append(f"Medical history: {', '.join(patient.history)}")

    if patient.medications:
        sections.append(f"Medications: {', '.join(patient.medications)}")

    if patient.allergies:
        sections.append(f"Allergies: {', '.join(patient.allergies)}")

    if patient.image_findings:
        sections.append(f"Image findings: {patient.image_findings}")

    if patient.notes:
        sections.append(f"Notes: {patient.notes}")

    sections.append(
        "\nClassify this patient using the Manchester Triage System. "
        "Respond with JSON only."
    )

    return "\n".join(sections)


def _parse_triage_response(raw: str) -> dict:
    """Parse model response into a triage dict using three-tier strategy.

    Tier 1: Extract JSON object from response.
    Tier 2: Regex fallback — extract color from text.
    Tier 3: Default to YELLOW with parse_failed flag.
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
                color_str = str(parsed.get("triage_color", "")).upper().strip()
                valid_colors = {c.value for c in TriageColor}
                if color_str in valid_colors:
                    return {
                        "triage_color": color_str,
                        "reasoning": str(parsed.get("reasoning", "")),
                        "key_discriminators": parsed.get("key_discriminators", []),
                        "confidence": max(
                            0.0, min(1.0, float(parsed.get("confidence", 0.7)))
                        ),
                        "parse_failed": False,
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                logger.warning(
                    "\033[33m\U000026a0\U0000fe0f  JSON parsing failed, "
                    "trying regex fallback\033[0m"
                )

    # Tier 2: Regex fallback — look for color mention
    color_pattern = r"\b(RED|ORANGE|YELLOW|GREEN|BLUE)\b"
    color_match = re.search(color_pattern, raw.upper())
    if color_match:
        color_str = color_match.group(1)
        logger.warning(
            "\033[33m\U000026a0\U0000fe0f  Regex fallback extracted color: %s\033[0m",
            color_str,
        )
        return {
            "triage_color": color_str,
            "reasoning": raw[:500],
            "key_discriminators": [],
            "confidence": 0.5,
            "parse_failed": False,
        }

    # Tier 3: Default to YELLOW (safe middle ground)
    logger.error(
        "\033[1;31m\U0000274c Could not parse triage color from model response\033[0m"
    )
    return {
        "triage_color": "YELLOW",
        "reasoning": raw[:500],
        "key_discriminators": [],
        "confidence": 0.3,
        "parse_failed": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify(patient: PatientData, lang: str = "pt") -> TriageResult:
    """Classify a patient using the Manchester Triage System.

    Args:
        patient: Structured patient data with at least a chief complaint.
        lang: Language code (``"pt"`` or ``"en"``).

    Returns:
        TriageResult with color, reasoning, and key discriminators.

    Raises:
        openai.APIError: If the model call fails (not caught here).
        EnvironmentError: If model configuration is missing.
    """
    user_prompt = _build_user_prompt(patient)

    if lang == "en":
        lang_instruction = (
            "\n\nThis is for an American medical application. "
            "Your answer must be in English."
        )
    else:
        lang_instruction = (
            "\n\nThis is for a Brazilian medical application. "
            "Your answer must be in Brazilian Portuguese."
        )
    system_prompt = _MANCHESTER_SYSTEM_PROMPT + lang_instruction

    logger.info(
        "\n\033[36m"
        "============================================================\n"
        "\U0001f4e4  SENDING TO MEDGEMMA 27B\n"
        "============================================================\033[0m\n"
        "\033[33m[SYSTEM PROMPT]\033[0m\n%s\n\n"
        "\033[33m[USER PROMPT]\033[0m\n%s\n"
        "\033[36m============================================================\033[0m",
        system_prompt,
        user_prompt,
    )
    try:
        raw_response = generate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=1024,
            temperature=0.1,
        )
    except Exception:
        logger.error("\033[1;31m\u274c MedGemma API call failed\033[0m", exc_info=True)
        return TriageResult(
            triage_color=TriageColor.YELLOW,
            triage_level="Urgente",
            max_wait_minutes=60,
            reasoning="Model API call failed — defaulting to YELLOW for safety.",
            key_discriminators=[],
            confidence=0.0,
            raw_model_response="",
            parse_failed=True,
        )
    logger.info(
        "\n\033[32m"
        "============================================================\n"
        "\U0001f4e5  MEDGEMMA 27B RESPONSE (%d chars)\n"
        "============================================================\033[0m\n"
        "%s\n"
        "\033[32m============================================================\033[0m",
        len(raw_response),
        raw_response,
    )

    parsed = _parse_triage_response(raw_response)

    triage_color = TriageColor(parsed["triage_color"])
    level_name, max_wait = TRIAGE_LEVELS[triage_color]

    return TriageResult(
        triage_color=triage_color,
        triage_level=level_name,
        max_wait_minutes=max_wait,
        reasoning=parsed["reasoning"],
        key_discriminators=parsed["key_discriminators"],
        confidence=parsed["confidence"],
        raw_model_response=raw_response,
        parse_failed=parsed["parse_failed"],
    )
