"""Tests for the patient intake interviewer agent."""

import json
from unittest.mock import patch

import pytest

from src.agents.intake import (
    MAX_TURNS,
    ConversationTurn,
    IntakeState,
    IntakeStatus,
    _build_intake_prompt,
    _is_data_sufficient,
    _merge_extracted_data,
    _next_fallback_question,
    _parse_intake_response,
    get_patient_data,
    process_answer,
    start_interview,
)
from src.agents.triage import PatientData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_model_response() -> str:
    return json.dumps(
        {
            "next_question": "Quando começou a dor?",
            "extracted_data": {
                "chief_complaint": "Dor no peito",
                "symptoms": ["dor torácica"],
            },
            "is_complete": False,
            "clinical_notes": "Patient reports chest pain",
        }
    )


@pytest.fixture
def complete_model_response() -> str:
    return json.dumps(
        {
            "next_question": None,
            "extracted_data": {
                "chief_complaint": "Dor no peito",
                "symptoms": ["dor torácica", "falta de ar"],
                "onset": "30 minutos atrás",
                "pain_scale": 8,
                "history": ["hipertensão"],
                "medications": ["losartana"],
                "allergies": ["penicilina"],
            },
            "is_complete": True,
            "clinical_notes": "Red flag: chest pain with radiation",
        }
    )


@pytest.fixture
def started_state() -> IntakeState:
    return start_interview()


@pytest.fixture
def mid_interview_state() -> IntakeState:
    return IntakeState(
        status=IntakeStatus.IN_PROGRESS,
        conversation=[
            ConversationTurn(role="agent", content="Qual é o motivo da sua visita?"),
            ConversationTurn(role="patient", content="Dor no peito"),
            ConversationTurn(role="agent", content="Quando começou a dor?"),
        ],
        extracted={"chief_complaint": "Dor no peito"},
        pending_question="Quando começou a dor?",
        turn_count=1,
    )


@pytest.fixture
def sufficient_extracted_data() -> dict:
    return {
        "chief_complaint": "Dor no peito",
        "symptoms": ["dor torácica"],
        "onset": "30 minutos",
        "pain_scale": 8,
        "history": ["hipertensão"],
    }


# ---------------------------------------------------------------------------
# Unit tests: data models
# ---------------------------------------------------------------------------


class TestIntakeState:
    def test_default_values(self) -> None:
        state = IntakeState()
        assert state.status == IntakeStatus.IN_PROGRESS
        assert state.conversation == []
        assert state.extracted == {}
        assert state.pending_question is None
        assert state.turn_count == 0
        assert state.raw_extraction_response is None

    def test_status_lifecycle(self) -> None:
        state = IntakeState(status=IntakeStatus.IN_PROGRESS)
        assert state.status == IntakeStatus.IN_PROGRESS

        state = IntakeState(status=IntakeStatus.COMPLETE)
        assert state.status == IntakeStatus.COMPLETE

        state = IntakeState(status=IntakeStatus.ABORTED)
        assert state.status == IntakeStatus.ABORTED

    def test_conversation_turn(self) -> None:
        turn = ConversationTurn(role="agent", content="Hello")
        assert turn.role == "agent"
        assert turn.content == "Hello"


class TestIntakeStatus:
    def test_all_statuses(self) -> None:
        assert len(IntakeStatus) == 3
        for status in ["IN_PROGRESS", "COMPLETE", "ABORTED"]:
            assert IntakeStatus(status).value == status


# ---------------------------------------------------------------------------
# Unit tests: prompt construction
# ---------------------------------------------------------------------------


class TestBuildIntakePrompt:
    def test_minimal_prompt(self) -> None:
        state = IntakeState()
        prompt = _build_intake_prompt(state, "Dor de cabeça")
        assert "Dor de cabeça" in prompt
        assert "Paciente:" in prompt
        assert "JSON" in prompt

    def test_with_history(self, mid_interview_state: IntakeState) -> None:
        prompt = _build_intake_prompt(mid_interview_state, "Há 2 horas")
        assert "Conversation so far" in prompt
        assert "Dor no peito" in prompt
        assert "Há 2 horas" in prompt
        assert "Enfermeiro(a)" in prompt
        assert "Paciente" in prompt

    def test_with_extracted_data(self, mid_interview_state: IntakeState) -> None:
        prompt = _build_intake_prompt(mid_interview_state, "Muito forte")
        assert "Data collected so far" in prompt
        assert "chief_complaint" in prompt

    def test_no_history_section_for_empty_conversation(self) -> None:
        state = IntakeState()
        prompt = _build_intake_prompt(state, "Test")
        assert "Conversation so far" not in prompt


# ---------------------------------------------------------------------------
# Unit tests: response parsing
# ---------------------------------------------------------------------------


class TestParseIntakeResponse:
    def test_valid_json(self, valid_model_response: str) -> None:
        result = _parse_intake_response(valid_model_response)
        assert result["next_question"] == "Quando começou a dor?"
        assert result["extracted_data"]["chief_complaint"] == "Dor no peito"
        assert result["is_complete"] is False
        assert result["clinical_notes"] == "Patient reports chest pain"

    def test_json_with_markdown_fences(self) -> None:
        inner = json.dumps(
            {
                "next_question": "Tem dor?",
                "extracted_data": {"chief_complaint": "Febre"},
                "is_complete": False,
                "clinical_notes": None,
            }
        )
        raw = f"```json\n{inner}\n```"
        result = _parse_intake_response(raw)
        assert result["next_question"] == "Tem dor?"
        assert result["extracted_data"]["chief_complaint"] == "Febre"

    def test_json_with_surrounding_text(self) -> None:
        inner = json.dumps(
            {
                "next_question": "Qual a dor?",
                "extracted_data": {},
                "is_complete": False,
                "clinical_notes": None,
            }
        )
        raw = f"Here is my response:\n{inner}\nDone."
        result = _parse_intake_response(raw)
        assert result["next_question"] == "Qual a dor?"

    def test_text_fallback_with_question_mark(self) -> None:
        raw = "Entendo, e quando começou essa dor?"
        result = _parse_intake_response(raw)
        assert "?" in result["next_question"]
        assert result["extracted_data"] == {}
        assert result["is_complete"] is False

    def test_total_failure(self) -> None:
        raw = "I cannot understand the request."
        result = _parse_intake_response(raw)
        assert result["next_question"] is None
        assert result["extracted_data"] == {}
        assert result["is_complete"] is False

    def test_nested_json(self) -> None:
        raw = json.dumps(
            {
                "next_question": "Pressão?",
                "extracted_data": {
                    "chief_complaint": "Tontura",
                    "vital_signs": {"heart_rate": 100, "blood_pressure": "140/90"},
                },
                "is_complete": False,
                "clinical_notes": None,
            }
        )
        result = _parse_intake_response(raw)
        assert result["extracted_data"]["vital_signs"]["heart_rate"] == 100

    def test_missing_fields_use_defaults(self) -> None:
        raw = json.dumps({"next_question": "Olá?"})
        result = _parse_intake_response(raw)
        assert result["next_question"] == "Olá?"
        assert result["extracted_data"] == {}
        assert result["is_complete"] is False
        assert result["clinical_notes"] is None


# ---------------------------------------------------------------------------
# Unit tests: data merging
# ---------------------------------------------------------------------------


class TestMergeExtractedData:
    def test_new_overrides_existing(self) -> None:
        previous = {"chief_complaint": "Dor"}
        new_data = {"chief_complaint": "Dor forte no peito"}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["chief_complaint"] == "Dor forte no peito"

    def test_null_values_preserved_from_previous(self) -> None:
        previous = {"chief_complaint": "Dor", "onset": "2 horas"}
        new_data = {"chief_complaint": "Dor", "onset": None}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["onset"] == "2 horas"

    def test_empty_list_does_not_overwrite_populated(self) -> None:
        previous = {"symptoms": ["febre", "tosse"]}
        new_data = {"symptoms": []}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["symptoms"] == ["febre", "tosse"]

    def test_empty_list_overwrites_empty(self) -> None:
        previous = {"symptoms": []}
        new_data = {"symptoms": []}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["symptoms"] == []

    def test_new_fields_added(self) -> None:
        previous = {"chief_complaint": "Dor"}
        new_data = {"onset": "1 hora"}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["chief_complaint"] == "Dor"
        assert merged["onset"] == "1 hora"

    def test_nested_dict_merge(self) -> None:
        previous = {"vital_signs": {"heart_rate": 80}}
        new_data = {"vital_signs": {"blood_pressure": "120/80"}}
        merged = _merge_extracted_data(previous, new_data)
        assert merged["vital_signs"]["heart_rate"] == 80
        assert merged["vital_signs"]["blood_pressure"] == "120/80"

    def test_all_null_dict_not_set(self) -> None:
        previous = {}
        new_data = {"vital_signs": {"heart_rate": None, "blood_pressure": None}}
        merged = _merge_extracted_data(previous, new_data)
        assert "vital_signs" not in merged

    def test_empty_previous(self) -> None:
        merged = _merge_extracted_data({}, {"chief_complaint": "Febre"})
        assert merged["chief_complaint"] == "Febre"


# ---------------------------------------------------------------------------
# Unit tests: data sufficiency
# ---------------------------------------------------------------------------


class TestIsDataSufficient:
    def test_sufficient_data(self, sufficient_extracted_data: dict) -> None:
        assert _is_data_sufficient(sufficient_extracted_data) is True

    def test_no_chief_complaint(self) -> None:
        data = {
            "symptoms": ["febre"],
            "onset": "1h",
            "pain_scale": 5,
            "history": ["dm"],
        }
        assert _is_data_sufficient(data) is False

    def test_chief_complaint_only(self) -> None:
        data = {"chief_complaint": "Dor"}
        assert _is_data_sufficient(data) is False

    def test_chief_complaint_plus_two_fields(self) -> None:
        data = {"chief_complaint": "Dor", "symptoms": ["febre"], "onset": "1h"}
        assert _is_data_sufficient(data) is False

    def test_chief_complaint_plus_three_fields(self) -> None:
        data = {
            "chief_complaint": "Dor",
            "symptoms": ["febre"],
            "onset": "1h",
            "pain_scale": 5,
        }
        assert _is_data_sufficient(data) is True

    def test_empty_lists_not_counted(self) -> None:
        data = {
            "chief_complaint": "Dor",
            "symptoms": [],
            "history": [],
            "medications": [],
            "onset": "1h",
        }
        assert _is_data_sufficient(data) is False

    def test_empty_dict(self) -> None:
        assert _is_data_sufficient({}) is False

    def test_chief_complaint_empty_string(self) -> None:
        data = {"chief_complaint": ""}
        assert _is_data_sufficient(data) is False


# ---------------------------------------------------------------------------
# Unit tests: fallback questions
# ---------------------------------------------------------------------------


class TestNextFallbackQuestion:
    def test_first_question_is_chief_complaint(self) -> None:
        question = _next_fallback_question({})
        assert "motivo" in question.lower() or "visita" in question.lower()

    def test_skips_filled_fields(self) -> None:
        data = {"chief_complaint": "Dor"}
        question = _next_fallback_question(data)
        assert "motivo" not in question.lower()

    def test_all_fields_filled(self) -> None:
        data = {
            "chief_complaint": "Dor",
            "symptoms": ["febre"],
            "onset": "1h",
            "pain_scale": 5,
            "history": ["dm"],
            "medications": ["metformina"],
            "allergies": ["penicilina"],
        }
        question = _next_fallback_question(data)
        assert "algo mais" in question.lower()


# ---------------------------------------------------------------------------
# Unit tests: start_interview
# ---------------------------------------------------------------------------


class TestStartInterview:
    def test_returns_in_progress(self) -> None:
        state = start_interview()
        assert state.status == IntakeStatus.IN_PROGRESS

    def test_has_first_question(self) -> None:
        state = start_interview()
        assert state.pending_question is not None
        assert len(state.pending_question) > 0

    def test_conversation_has_agent_turn(self) -> None:
        state = start_interview()
        assert len(state.conversation) == 1
        assert state.conversation[0].role == "agent"

    def test_turn_count_zero(self) -> None:
        state = start_interview()
        assert state.turn_count == 0

    def test_empty_extracted(self) -> None:
        state = start_interview()
        assert state.extracted == {}


# ---------------------------------------------------------------------------
# Unit tests: process_answer (mocked model)
# ---------------------------------------------------------------------------


class TestProcessAnswer:
    @patch("src.agents.intake.generate_text")
    def test_updates_state(
        self,
        mock_generate: object,
        started_state: IntakeState,
        valid_model_response: str,
    ) -> None:
        mock_generate.return_value = valid_model_response  # type: ignore[attr-defined]

        new_state = process_answer(started_state, "Dor no peito")

        assert new_state.status == IntakeStatus.IN_PROGRESS
        assert new_state.turn_count == 1
        assert new_state.extracted.get("chief_complaint") == "Dor no peito"
        assert new_state.pending_question is not None
        # Patient answer + agent question added
        assert len(new_state.conversation) > len(started_state.conversation)

    @patch("src.agents.intake.generate_text")
    def test_marks_complete_when_sufficient(
        self,
        mock_generate: object,
        mid_interview_state: IntakeState,
        complete_model_response: str,
    ) -> None:
        mock_generate.return_value = complete_model_response  # type: ignore[attr-defined]

        new_state = process_answer(
            mid_interview_state, "Sim, sou alérgico a penicilina"
        )

        assert new_state.status == IntakeStatus.COMPLETE
        assert new_state.pending_question is None

    @patch("src.agents.intake.generate_text")
    def test_does_not_complete_without_sufficient_data(
        self,
        mock_generate: object,
        started_state: IntakeState,
    ) -> None:
        # Model says complete but data is insufficient
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "next_question": None,
                "extracted_data": {"chief_complaint": "Dor"},
                "is_complete": True,
                "clinical_notes": None,
            }
        )

        new_state = process_answer(started_state, "Dor")

        assert new_state.status == IntakeStatus.IN_PROGRESS

    @patch("src.agents.intake.generate_text")
    def test_enforces_max_turns(
        self,
        mock_generate: object,
    ) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "next_question": "Mais alguma coisa?",
                "extracted_data": {"chief_complaint": "Dor"},
                "is_complete": False,
                "clinical_notes": None,
            }
        )

        state = IntakeState(
            status=IntakeStatus.IN_PROGRESS,
            turn_count=MAX_TURNS - 1,
            extracted={"chief_complaint": "Dor"},
            conversation=[ConversationTurn(role="agent", content="Pergunta?")],
        )

        new_state = process_answer(state, "Resposta")

        assert new_state.status == IntakeStatus.COMPLETE
        assert new_state.turn_count == MAX_TURNS

    @patch("src.agents.intake.generate_text")
    def test_rejects_completed_state(
        self,
        mock_generate: object,
    ) -> None:
        state = IntakeState(status=IntakeStatus.COMPLETE)
        with pytest.raises(ValueError, match="COMPLETE"):
            process_answer(state, "More info")

    @patch("src.agents.intake.generate_text")
    def test_rejects_aborted_state(
        self,
        mock_generate: object,
    ) -> None:
        state = IntakeState(status=IntakeStatus.ABORTED)
        with pytest.raises(ValueError, match="ABORTED"):
            process_answer(state, "More info")

    @patch("src.agents.intake.generate_text")
    def test_adds_clinical_notes(
        self,
        mock_generate: object,
        started_state: IntakeState,
    ) -> None:
        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "next_question": "Onde dói?",
                "extracted_data": {"chief_complaint": "Dor no peito"},
                "is_complete": False,
                "clinical_notes": "Red flag: chest pain",
            }
        )

        new_state = process_answer(started_state, "Dor no peito")

        assert "Red flag" in new_state.extracted.get("clinical_notes", "")

    @patch("src.agents.intake.generate_text")
    def test_accumulates_clinical_notes(
        self,
        mock_generate: object,
    ) -> None:
        state = IntakeState(
            status=IntakeStatus.IN_PROGRESS,
            extracted={"chief_complaint": "Dor", "clinical_notes": "First note"},
            conversation=[ConversationTurn(role="agent", content="Pergunta?")],
            turn_count=1,
        )

        mock_generate.return_value = json.dumps(  # type: ignore[attr-defined]
            {
                "next_question": "Mais?",
                "extracted_data": {"chief_complaint": "Dor"},
                "is_complete": False,
                "clinical_notes": "Second note",
            }
        )

        new_state = process_answer(state, "Sim")

        assert "First note" in new_state.extracted["clinical_notes"]
        assert "Second note" in new_state.extracted["clinical_notes"]

    @patch("src.agents.intake.generate_text")
    def test_stores_raw_response(
        self,
        mock_generate: object,
        started_state: IntakeState,
        valid_model_response: str,
    ) -> None:
        mock_generate.return_value = valid_model_response  # type: ignore[attr-defined]

        new_state = process_answer(started_state, "Dor de cabeça")

        assert new_state.raw_extraction_response == valid_model_response

    @patch("src.agents.intake.generate_text")
    def test_api_error_propagates(
        self,
        mock_generate: object,
        started_state: IntakeState,
    ) -> None:
        mock_generate.side_effect = RuntimeError("API connection failed")  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="API connection failed"):
            process_answer(started_state, "Dor")

    @patch("src.agents.intake.generate_text")
    def test_fallback_question_on_parse_failure(
        self,
        mock_generate: object,
        started_state: IntakeState,
    ) -> None:
        mock_generate.return_value = "Cannot process this."  # type: ignore[attr-defined]

        new_state = process_answer(started_state, "Dor")

        # Should still get a fallback question
        assert new_state.status == IntakeStatus.IN_PROGRESS
        assert new_state.pending_question is not None


# ---------------------------------------------------------------------------
# Unit tests: model call parameters
# ---------------------------------------------------------------------------


class TestModelCallParameters:
    @patch("src.agents.intake.generate_text")
    def test_temperature_and_max_tokens(
        self,
        mock_generate: object,
        started_state: IntakeState,
        valid_model_response: str,
    ) -> None:
        mock_generate.return_value = valid_model_response  # type: ignore[attr-defined]

        process_answer(started_state, "Dor de cabeça")

        mock_generate.assert_called_once()  # type: ignore[attr-defined]
        call_kwargs = mock_generate.call_args  # type: ignore[attr-defined]
        assert call_kwargs.kwargs["temperature"] == 0.3
        assert call_kwargs.kwargs["max_tokens"] == 1024

    @patch("src.agents.intake.generate_text")
    def test_system_prompt_content(
        self,
        mock_generate: object,
        started_state: IntakeState,
        valid_model_response: str,
    ) -> None:
        mock_generate.return_value = valid_model_response  # type: ignore[attr-defined]

        process_answer(started_state, "Dor de cabeça")

        call_kwargs = mock_generate.call_args  # type: ignore[attr-defined]
        system_prompt = call_kwargs.kwargs["system_prompt"]
        assert "SUS" in system_prompt
        assert (
            "Brazilian Portuguese" in system_prompt
            or "português" in system_prompt.lower()
        )
        assert "JSON" in system_prompt
        assert "next_question" in system_prompt
        assert "extracted_data" in system_prompt


# ---------------------------------------------------------------------------
# Unit tests: get_patient_data
# ---------------------------------------------------------------------------


class TestGetPatientData:
    def test_converts_to_patient_data(self, sufficient_extracted_data: dict) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted=sufficient_extracted_data,
        )

        patient = get_patient_data(state)

        assert isinstance(patient, PatientData)
        assert patient.chief_complaint == "Dor no peito"
        assert patient.symptoms == ["dor torácica"]
        assert patient.onset == "30 minutos"
        assert patient.pain_scale == 8
        assert patient.history == ["hipertensão"]

    def test_raises_on_missing_chief_complaint(self) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted={"symptoms": ["febre"]},
        )

        with pytest.raises(ValueError, match="chief_complaint"):
            get_patient_data(state)

    def test_raises_on_empty_extracted(self) -> None:
        state = IntakeState(status=IntakeStatus.COMPLETE, extracted={})

        with pytest.raises(ValueError, match="chief_complaint"):
            get_patient_data(state)

    def test_includes_vital_signs(self) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted={
                "chief_complaint": "Tontura",
                "vital_signs": {
                    "heart_rate": 100,
                    "blood_pressure": "140/90",
                    "respiratory_rate": None,
                    "temperature": None,
                    "spo2": None,
                    "glucose": None,
                },
            },
        )

        patient = get_patient_data(state)

        assert patient.vital_signs is not None
        assert patient.vital_signs.heart_rate == 100
        assert patient.vital_signs.blood_pressure == "140/90"
        assert patient.vital_signs.respiratory_rate is None

    def test_no_vital_signs_when_all_null(self) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted={
                "chief_complaint": "Dor",
                "vital_signs": {
                    "heart_rate": None,
                    "blood_pressure": None,
                },
            },
        )

        patient = get_patient_data(state)
        assert patient.vital_signs is None

    def test_includes_clinical_notes(self) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted={
                "chief_complaint": "Dor no peito",
                "clinical_notes": "Red flag: chest pain with radiation",
            },
        )

        patient = get_patient_data(state)
        assert patient.notes == "Red flag: chest pain with radiation"

    def test_works_with_in_progress_state(self) -> None:
        state = IntakeState(
            status=IntakeStatus.IN_PROGRESS,
            extracted={"chief_complaint": "Febre"},
        )

        patient = get_patient_data(state)
        assert patient.chief_complaint == "Febre"

    def test_full_data_conversion(self) -> None:
        state = IntakeState(
            status=IntakeStatus.COMPLETE,
            extracted={
                "chief_complaint": "Dor no peito",
                "symptoms": ["dispneia", "sudorese"],
                "onset": "30 minutos atrás",
                "duration": "contínua",
                "pain_scale": 9,
                "history": ["hipertensão", "diabetes"],
                "medications": ["losartana", "metformina"],
                "allergies": ["penicilina"],
                "age": 55,
                "sex": "M",
                "vital_signs": {
                    "heart_rate": 110,
                    "blood_pressure": "180/100",
                    "spo2": 94.0,
                },
                "clinical_notes": "Cardiac risk profile",
            },
        )

        patient = get_patient_data(state)

        assert patient.chief_complaint == "Dor no peito"
        assert patient.symptoms == ["dispneia", "sudorese"]
        assert patient.onset == "30 minutos atrás"
        assert patient.duration == "contínua"
        assert patient.pain_scale == 9
        assert patient.history == ["hipertensão", "diabetes"]
        assert patient.medications == ["losartana", "metformina"]
        assert patient.allergies == ["penicilina"]
        assert patient.age == 55
        assert patient.sex == "M"
        assert patient.vital_signs is not None
        assert patient.vital_signs.heart_rate == 110
        assert patient.notes == "Cardiac risk profile"


# ---------------------------------------------------------------------------
# Integration test: classify with intake data (requires real model endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestClassifyIntegration:
    def test_intake_to_triage_flow(self) -> None:
        """Run a full intake interview and pass result to triage classifier."""
        from src.agents.triage import classify

        state = start_interview()

        # Simulate multi-turn conversation
        answers = [
            "Dor forte no peito, vai pro braço esquerdo",
            "Começou faz uns 30 minutos",
            "Dor é 9 de 10, muito forte",
            "Tenho pressão alta e diabetes",
            "Tomo losartana e metformina",
            "Alergia a penicilina",
            "Tenho 55 anos, sou homem",
        ]

        for answer in answers:
            if state.status != IntakeStatus.IN_PROGRESS:
                break
            state = process_answer(state, answer)

        patient = get_patient_data(state)
        result = classify(patient)

        assert result.triage_color.value in ("RED", "ORANGE")
        assert len(result.reasoning) > 0
        assert result.parse_failed is False
