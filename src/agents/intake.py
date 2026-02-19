"""Patient intake interviewer agent for Brazilian SUS emergency rooms.

Conducts structured clinical interviews in Brazilian Portuguese, collecting
patient data via conversational turns. Each call to process_answer() sends
full conversation history to MedGemma 27B, which returns accumulated
extracted data and the next question as JSON.

The agent exposes turn-by-turn functions (not a blocking loop) so the
UI/orchestrator controls the conversation flow.

Usage:
    from src.agents.intake import start_interview, process_answer, get_patient_data

    state = start_interview()
    state = process_answer(state, "Dor no peito forte")
    state = process_answer(state, "Começou há 30 minutos")
    # ... more turns ...
    patient = get_patient_data(state)  # -> PatientData for triage
"""

import json
import logging
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.agents.triage import PatientData, VitalSigns
from src.models.medgemma import generate_text

logger = logging.getLogger(__name__)

MAX_TURNS = 15

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class IntakeStatus(str, Enum):
    """Status of the intake interview."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


class ConversationTurn(BaseModel):
    """A single turn in the intake conversation."""

    role: str = Field(..., description="'agent' or 'patient'")
    content: str


class IntakeState(BaseModel):
    """Full state of an intake interview session."""

    status: IntakeStatus = IntakeStatus.IN_PROGRESS
    conversation: list[ConversationTurn] = Field(default_factory=list)
    extracted: dict = Field(default_factory=dict)
    pending_question: Optional[str] = None
    turn_count: int = 0
    raw_extraction_response: Optional[str] = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_INTAKE_SYSTEM_PROMPT = """\
You are a clinical intake assistant for a Brazilian SUS emergency room. \
You conduct structured patient interviews in simple Brazilian Portuguese. \
You assist triage nurses — you never replace them.

## Interview Order
Collect information in this order, one question at a time:
1. Chief complaint (queixa principal)
2. Symptoms (sintomas associados)
3. Onset and duration (quando começou, há quanto tempo)
4. Pain scale 0-10 (escala de dor)
5. Medical history (doenças anteriores, cirurgias)
6. Current medications (medicamentos em uso)
7. Allergies (alergias)
8. Demographics — age, sex (idade, sexo)
9. Vital signs if available (sinais vitais)

## Rules
- Ask ONE question at a time in simple Brazilian Portuguese
- Be empathetic but efficient — this is an emergency room
- Map common colloquialisms to clinical terms:
  - "pressão alta" → hypertension
  - "falta de ar" → dyspnea
  - "dor no peito" → chest pain
  - "açúcar no sangue" → diabetes/glucose
  - "coração acelerado" → tachycardia/palpitations
  - "enjoo" → nausea
  - "tontura" → dizziness/vertigo
- If the patient reports RED FLAG symptoms (chest pain with radiation, \
sudden severe headache, difficulty breathing, loss of consciousness, \
heavy bleeding), note urgency in clinical_notes
- When you have enough information for triage, set is_complete to true

## Response Format
Respond ONLY with valid JSON (no markdown, no backticks):
{
    "next_question": "Your next question in Brazilian Portuguese",
    "extracted_data": {
        "chief_complaint": "...",
        "symptoms": ["..."],
        "onset": "...",
        "duration": "...",
        "pain_scale": 0-10,
        "history": ["..."],
        "medications": ["..."],
        "allergies": ["..."],
        "age": null,
        "sex": null,
        "vital_signs": {
            "heart_rate": null,
            "blood_pressure": null,
            "respiratory_rate": null,
            "temperature": null,
            "spo2": null,
            "glucose": null
        }
    },
    "is_complete": false,
    "clinical_notes": "Any clinical observations or red flags"
}

IMPORTANT: extracted_data must contain ALL data collected so far across \
all turns, not just data from this turn. Accumulate everything.
"""

# Static fallback questions when model fails to generate one
_FALLBACK_QUESTIONS = [
    ("chief_complaint", "Qual é o motivo da sua visita hoje?"),
    ("symptoms", "Você tem outros sintomas além da queixa principal?"),
    ("onset", "Quando esses sintomas começaram?"),
    ("pain_scale", "De 0 a 10, qual é o nível da sua dor?"),
    ("history", "Você tem alguma doença ou já fez alguma cirurgia?"),
    ("medications", "Está tomando algum medicamento?"),
    ("allergies", "Tem alergia a algum medicamento ou substância?"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_intake_prompt(state: IntakeState, answer: str) -> str:
    """Format conversation history + new answer into a user prompt."""
    sections: list[str] = []

    # Conversation history
    if state.conversation:
        sections.append("## Conversation so far")
        for turn in state.conversation:
            label = "Enfermeiro(a)" if turn.role == "agent" else "Paciente"
            sections.append(f"{label}: {turn.content}")

    # New answer
    sections.append(f"\nPaciente: {answer}")

    # Current extracted data
    if state.extracted:
        collected = json.dumps(state.extracted, ensure_ascii=False)
        sections.append(f"\n## Data collected so far\n{collected}")

    sections.append(
        "\nUpdate extracted_data with ALL information collected so far "
        "(accumulate, do not discard previous data). "
        "Ask the next question or set is_complete=true if enough data is collected. "
        "Respond with JSON only."
    )

    return "\n".join(sections)


def _parse_intake_response(raw: str) -> dict:
    """Parse model response into intake dict using three-tier strategy.

    Tier 1: Extract JSON object via brace-counting.
    Tier 2: Scan for a question-mark sentence as next_question.
    Tier 3: Static fallback.
    """
    # Tier 1: Brace-counting JSON extraction (handles nested objects)
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
                return {
                    "next_question": parsed.get("next_question"),
                    "extracted_data": parsed.get("extracted_data", {}),
                    "is_complete": bool(parsed.get("is_complete", False)),
                    "clinical_notes": parsed.get("clinical_notes"),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                logger.warning("JSON parsing failed, trying text fallback")

    # Tier 2: Look for a question-mark sentence
    question_match = re.search(r"[^.!?\n]*\?", raw)
    if question_match:
        question = question_match.group(0).strip()
        logger.warning("Used text fallback to extract question: %s", question)
        return {
            "next_question": question,
            "extracted_data": {},
            "is_complete": False,
            "clinical_notes": None,
        }

    # Tier 3: Static fallback
    logger.error("Could not parse intake response from model")
    return {
        "next_question": None,
        "extracted_data": {},
        "is_complete": False,
        "clinical_notes": None,
    }


def _merge_extracted_data(previous: dict, new_data: dict) -> dict:
    """Merge new extraction into previous, keeping previous values when new is null."""
    merged = dict(previous)
    for key, value in new_data.items():
        if value is None:
            continue
        if isinstance(value, list) and len(value) == 0:
            # Don't overwrite a populated list with an empty one
            if key in merged and isinstance(merged[key], list) and len(merged[key]) > 0:
                continue
        if isinstance(value, dict):
            # Recursive merge for nested dicts (e.g., vital_signs)
            if key in merged and isinstance(merged[key], dict):
                merged[key] = _merge_extracted_data(merged[key], value)
            else:
                # Only set if dict has at least one non-null value
                if any(v is not None for v in value.values()):
                    merged[key] = value
        else:
            merged[key] = value
    return merged


def _next_fallback_question(data: dict) -> str:
    """Return the next question from the static list based on missing fields."""
    for field, question in _FALLBACK_QUESTIONS:
        if field not in data or data[field] is None:
            return question
    return "Há algo mais que gostaria de informar?"


def _is_data_sufficient(data: dict) -> bool:
    """Check if enough data has been collected for triage.

    Requires chief_complaint plus at least 3 of 6 desired fields.
    """
    if not data.get("chief_complaint"):
        return False

    desired_fields = [
        "symptoms",
        "onset",
        "pain_scale",
        "history",
        "medications",
        "allergies",
    ]
    filled = 0
    for field in desired_fields:
        value = data.get(field)
        if value is not None:
            if isinstance(value, list) and len(value) == 0:
                continue
            filled += 1

    return filled >= 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_interview() -> IntakeState:
    """Start a new intake interview.

    Returns:
        IntakeState with IN_PROGRESS status and the first question
        (asking for chief complaint).
    """
    first_question = (
        "Olá, eu sou o assistente de triagem. Qual é o motivo da sua visita hoje?"
    )

    state = IntakeState(
        status=IntakeStatus.IN_PROGRESS,
        conversation=[ConversationTurn(role="agent", content=first_question)],
        pending_question=first_question,
        turn_count=0,
    )

    logger.info("Intake interview started")
    return state


def process_answer(state: IntakeState, answer: str) -> IntakeState:
    """Process a patient answer, extract data, and generate the next question.

    Args:
        state: Current intake state.
        answer: Patient's answer text.

    Returns:
        Updated IntakeState with new conversation turns, extracted data,
        and next question (or COMPLETE status).

    Raises:
        ValueError: If the interview is already complete or aborted.
    """
    if state.status != IntakeStatus.IN_PROGRESS:
        raise ValueError(
            f"Cannot process answer: interview status is {state.status.value}"
        )

    # Add patient answer to conversation
    conversation = list(state.conversation)
    conversation.append(ConversationTurn(role="patient", content=answer))

    turn_count = state.turn_count + 1

    # Build prompt and call model
    prompt = _build_intake_prompt(state, answer)

    logger.info("Calling MedGemma 27B for intake turn %d", turn_count)
    raw_response = generate_text(
        prompt=prompt,
        system_prompt=_INTAKE_SYSTEM_PROMPT,
        max_tokens=1024,
        temperature=0.3,
    )
    logger.info("Model response received (%d chars)", len(raw_response))

    # Parse response
    parsed = _parse_intake_response(raw_response)

    # Merge extracted data
    extracted = _merge_extracted_data(state.extracted, parsed.get("extracted_data", {}))

    # Determine next question
    next_question = parsed.get("next_question")
    if not next_question:
        next_question = _next_fallback_question(extracted)

    # Determine status
    model_says_complete = parsed.get("is_complete", False)
    data_sufficient = _is_data_sufficient(extracted)

    if (model_says_complete and data_sufficient) or turn_count >= MAX_TURNS:
        status = IntakeStatus.COMPLETE
        if turn_count >= MAX_TURNS:
            logger.warning(
                "Intake reached max turns (%d), forcing completion", MAX_TURNS
            )
    else:
        status = IntakeStatus.IN_PROGRESS
        # Add agent question to conversation
        conversation.append(ConversationTurn(role="agent", content=next_question))

    # Append clinical notes if present
    if parsed.get("clinical_notes"):
        notes = extracted.get("clinical_notes", "")
        if notes:
            extracted["clinical_notes"] = f"{notes}; {parsed['clinical_notes']}"
        else:
            extracted["clinical_notes"] = parsed["clinical_notes"]

    return IntakeState(
        status=status,
        conversation=conversation,
        extracted=extracted,
        pending_question=next_question if status == IntakeStatus.IN_PROGRESS else None,
        turn_count=turn_count,
        raw_extraction_response=raw_response,
    )


def get_patient_data(state: IntakeState) -> PatientData:
    """Convert extracted intake data to PatientData for triage classification.

    Args:
        state: Completed (or in-progress) intake state.

    Returns:
        PatientData suitable for triage.classify().

    Raises:
        ValueError: If chief_complaint has not been extracted.
    """
    data = state.extracted

    chief_complaint = data.get("chief_complaint")
    if not chief_complaint:
        raise ValueError("Cannot create PatientData: chief_complaint not extracted")

    # Build VitalSigns if any vital data exists
    vital_signs = None
    vs_data = data.get("vital_signs")
    if isinstance(vs_data, dict) and any(v is not None for v in vs_data.values()):
        vital_signs = VitalSigns(
            heart_rate=vs_data.get("heart_rate"),
            blood_pressure=vs_data.get("blood_pressure"),
            respiratory_rate=vs_data.get("respiratory_rate"),
            temperature=vs_data.get("temperature"),
            spo2=vs_data.get("spo2"),
            glucose=vs_data.get("glucose"),
        )

    return PatientData(
        chief_complaint=chief_complaint,
        symptoms=data.get("symptoms"),
        onset=data.get("onset"),
        duration=data.get("duration"),
        pain_scale=data.get("pain_scale"),
        vital_signs=vital_signs,
        history=data.get("history"),
        medications=data.get("medications"),
        allergies=data.get("allergies"),
        age=data.get("age"),
        sex=data.get("sex"),
        notes=data.get("clinical_notes"),
    )
