"""Tests for the LangGraph triage pipeline orchestrator."""

from unittest.mock import patch

import pytest

from src.agents.image_reader import ImageFindings, ImageSeverity
from src.agents.triage import (
    PatientData,
    TriageColor,
    TriageResult,
    VitalSigns,
)
from src.pipeline.orchestrator import (
    PipelineState,
    _should_analyze_image,
    build_graph,
    run_documentation,
    run_image_analysis,
    run_pipeline,
    run_triage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_patient() -> PatientData:
    return PatientData(
        chief_complaint="Dor no peito irradiando para o braço esquerdo",
        symptoms=["sudorese", "náusea"],
        onset="30 minutos atrás",
        pain_scale=8,
        vital_signs=VitalSigns(heart_rate=110, blood_pressure="180/100"),
        age=55,
        sex="M",
        history=["hipertensão", "diabetes tipo 2"],
    )


@pytest.fixture
def minimal_patient() -> PatientData:
    return PatientData(chief_complaint="Dor de cabeça")


@pytest.fixture
def mock_triage_result() -> TriageResult:
    return TriageResult(
        triage_color=TriageColor.ORANGE,
        triage_level="Muito urgente",
        max_wait_minutes=10,
        reasoning="Dor torácica com fatores de risco cardíaco",
        key_discriminators=["dor intensa", "risco cardíaco"],
        confidence=0.85,
        raw_model_response="{}",
    )


@pytest.fixture
def mock_image_findings() -> ImageFindings:
    return ImageFindings(
        modality="radiografia",
        description="Cardiomegalia leve",
        suspected_conditions=["cardiomegalia"],
        severity=ImageSeverity.MODERATE,
        key_observations=["silhueta cardíaca aumentada"],
        confidence=0.75,
        requires_specialist=True,
        raw_model_response="{}",
    )


# ---------------------------------------------------------------------------
# Unit tests: conditional routing
# ---------------------------------------------------------------------------


class TestConditionalRouting:
    def test_routes_to_image_when_bytes_present(
        self, sample_patient: PatientData
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": b"fake-image",
            "errors": [],
        }
        assert _should_analyze_image(state) == "run_image_analysis"

    def test_routes_to_triage_when_no_image(self, sample_patient: PatientData) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": None,
            "errors": [],
        }
        assert _should_analyze_image(state) == "run_triage"

    def test_routes_to_triage_when_image_key_missing(
        self, sample_patient: PatientData
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "errors": [],
        }
        assert _should_analyze_image(state) == "run_triage"

    def test_routes_to_triage_when_empty_bytes(
        self, sample_patient: PatientData
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": b"",
            "errors": [],
        }
        assert _should_analyze_image(state) == "run_triage"


# ---------------------------------------------------------------------------
# Unit tests: individual node functions
# ---------------------------------------------------------------------------


class TestRunImageAnalysis:
    def test_calls_analyze_and_returns_findings(
        self,
        sample_patient: PatientData,
        mock_image_findings: ImageFindings,
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": b"fake-image",
            "image_mime_type": "image/png",
            "errors": [],
        }
        with patch(
            "src.pipeline.orchestrator.analyze_image",
            return_value=mock_image_findings,
        ):
            result = run_image_analysis(state)

        assert result["image_findings"] is mock_image_findings
        assert result["patient_data"].image_findings is not None
        assert "cardiomegalia" in result["patient_data"].image_findings.lower()

    def test_returns_empty_when_no_image_bytes(
        self, sample_patient: PatientData
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": None,
            "errors": [],
        }
        result = run_image_analysis(state)
        assert result == {}

    def test_appends_error_on_failure(self, sample_patient: PatientData) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": b"bad-data",
            "errors": [],
        }
        with patch(
            "src.pipeline.orchestrator.analyze_image",
            side_effect=RuntimeError("API down"),
        ):
            result = run_image_analysis(state)

        assert len(result["errors"]) == 1
        assert "Image analysis failed" in result["errors"][0]
        assert "image_findings" not in result

    def test_uses_chief_complaint_as_context(
        self,
        sample_patient: PatientData,
        mock_image_findings: ImageFindings,
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "image_bytes": b"img",
            "errors": [],
        }
        with patch(
            "src.pipeline.orchestrator.analyze_image",
            return_value=mock_image_findings,
        ) as mock_call:
            run_image_analysis(state)

        mock_call.assert_called_once_with(
            image_bytes=b"img",
            mime_type="image/jpeg",
            clinical_context=sample_patient.chief_complaint,
        )


class TestRunTriage:
    def test_returns_triage_result(
        self,
        sample_patient: PatientData,
        mock_triage_result: TriageResult,
    ) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "errors": [],
        }
        with patch(
            "src.pipeline.orchestrator.classify_patient",
            return_value=mock_triage_result,
        ):
            result = run_triage(state)

        assert result["triage_result"] is mock_triage_result

    def test_appends_error_on_failure(self, sample_patient: PatientData) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "errors": [],
        }
        with patch(
            "src.pipeline.orchestrator.classify_patient",
            side_effect=RuntimeError("Model timeout"),
        ):
            result = run_triage(state)

        assert len(result["errors"]) == 1
        assert "Triage classification failed" in result["errors"][0]


class TestRunDocumentation:
    def test_returns_none_stub(self, sample_patient: PatientData) -> None:
        state: PipelineState = {
            "patient_data": sample_patient,
            "errors": [],
        }
        result = run_documentation(state)
        assert result["fhir_bundle"] is None


# ---------------------------------------------------------------------------
# Unit tests: graph construction
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_graph_compiles(self) -> None:
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self) -> None:
        graph = build_graph()
        compiled = graph.compile()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "run_image_analysis" in node_names
        assert "run_triage" in node_names
        assert "run_documentation" in node_names


# ---------------------------------------------------------------------------
# Integration-style tests: full pipeline (agents mocked)
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def test_pipeline_without_image(
        self,
        sample_patient: PatientData,
        mock_triage_result: TriageResult,
    ) -> None:
        with patch(
            "src.pipeline.orchestrator.classify_patient",
            return_value=mock_triage_result,
        ):
            result = run_pipeline(sample_patient)

        assert result["triage_result"].triage_color == TriageColor.ORANGE
        assert result.get("image_findings") is None
        assert result["fhir_bundle"] is None
        assert result["errors"] == []

    def test_pipeline_with_image(
        self,
        sample_patient: PatientData,
        mock_triage_result: TriageResult,
        mock_image_findings: ImageFindings,
    ) -> None:
        with (
            patch(
                "src.pipeline.orchestrator.classify_patient",
                return_value=mock_triage_result,
            ),
            patch(
                "src.pipeline.orchestrator.analyze_image",
                return_value=mock_image_findings,
            ),
        ):
            result = run_pipeline(
                sample_patient,
                image_bytes=b"fake-xray",
                image_mime_type="image/png",
            )

        assert result["triage_result"].triage_color == TriageColor.ORANGE
        assert result["image_findings"].severity == ImageSeverity.MODERATE
        # Image findings should be wired into patient_data
        assert result["patient_data"].image_findings is not None
        assert result["errors"] == []

    def test_pipeline_continues_after_image_failure(
        self,
        sample_patient: PatientData,
        mock_triage_result: TriageResult,
    ) -> None:
        with (
            patch(
                "src.pipeline.orchestrator.classify_patient",
                return_value=mock_triage_result,
            ),
            patch(
                "src.pipeline.orchestrator.analyze_image",
                side_effect=RuntimeError("GPU OOM"),
            ),
        ):
            result = run_pipeline(sample_patient, image_bytes=b"some-image")

        # Triage should still succeed despite image failure
        assert result["triage_result"].triage_color == TriageColor.ORANGE
        assert len(result["errors"]) == 1
        assert "Image analysis failed" in result["errors"][0]

    def test_pipeline_with_minimal_patient(
        self,
        minimal_patient: PatientData,
        mock_triage_result: TriageResult,
    ) -> None:
        with patch(
            "src.pipeline.orchestrator.classify_patient",
            return_value=mock_triage_result,
        ):
            result = run_pipeline(minimal_patient)

        assert result["triage_result"] is not None
        assert result["errors"] == []

    def test_pipeline_triage_failure_records_error(
        self, sample_patient: PatientData
    ) -> None:
        with patch(
            "src.pipeline.orchestrator.classify_patient",
            side_effect=RuntimeError("Endpoint unreachable"),
        ):
            result = run_pipeline(sample_patient)

        assert result.get("triage_result") is None
        assert any("Triage classification failed" in e for e in result["errors"])

    def test_pipeline_errors_accumulate(
        self,
        sample_patient: PatientData,
    ) -> None:
        with (
            patch(
                "src.pipeline.orchestrator.analyze_image",
                side_effect=RuntimeError("Image error"),
            ),
            patch(
                "src.pipeline.orchestrator.classify_patient",
                side_effect=RuntimeError("Triage error"),
            ),
        ):
            result = run_pipeline(sample_patient, image_bytes=b"img")

        assert len(result["errors"]) == 2
        assert any("Image" in e for e in result["errors"])
        assert any("Triage" in e for e in result["errors"])
