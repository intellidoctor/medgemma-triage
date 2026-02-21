"""LangGraph triage pipeline orchestrator.

Connects agents into a coherent pipeline:
    intake data → image analysis (optional) → triage → documentation

The intake conversation is driven by the UI/caller. This orchestrator
receives **completed** patient data and runs the remaining steps.

Usage:
    from src.pipeline.orchestrator import run_pipeline
    from src.agents.triage import PatientData

    patient = PatientData(chief_complaint="Chest pain")
    result = run_pipeline(patient)
    print(result["triage_result"].triage_color)

    # With an image:
    result = run_pipeline(patient, image_bytes=b"...", image_mime_type="image/jpeg")
"""

import logging
from typing import Annotated, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.agents.documentation import generate_fhir_bundle
from src.agents.image_reader import ImageFindings
from src.agents.image_reader import analyze as analyze_image
from src.agents.triage import PatientData, TriageResult
from src.agents.triage import classify as classify_patient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


def _append_errors(existing: list[str], new: list[str]) -> list[str]:
    """Reducer that appends new errors to existing list."""
    return existing + new


class PipelineState(TypedDict, total=False):
    """Data flowing through the triage pipeline."""

    # Inputs
    patient_data: PatientData
    image_bytes: Optional[bytes]
    image_mime_type: str

    # Intermediate results
    image_findings: Optional[ImageFindings]

    # Outputs
    triage_result: Optional[TriageResult]
    fhir_bundle: Optional[dict]

    # Pipeline metadata
    errors: Annotated[list[str], _append_errors]


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def run_image_analysis(state: PipelineState) -> dict:
    """Analyze a medical image via MedGemma 4B."""
    image_bytes = state.get("image_bytes")
    if not image_bytes:
        return {}

    mime_type = state.get("image_mime_type", "image/jpeg")
    patient_data: PatientData = state["patient_data"]

    try:
        findings = analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            clinical_context=patient_data.chief_complaint,
        )
        # Wire image findings into patient data for triage
        updated_patient = patient_data.model_copy(
            update={"image_findings": findings.to_triage_summary()}
        )
        logger.info("Image analysis complete: severity=%s", findings.severity.value)
        return {
            "image_findings": findings,
            "patient_data": updated_patient,
        }
    except Exception as exc:
        logger.exception("Image analysis failed")
        return {"errors": [f"Image analysis failed: {exc}"]}


def run_triage(state: PipelineState) -> dict:
    """Classify patient using Manchester Protocol via MedGemma 27B."""
    patient_data: PatientData = state["patient_data"]

    try:
        result = classify_patient(patient_data)
        logger.info(
            "Triage complete: color=%s, confidence=%.2f",
            result.triage_color.value,
            result.confidence,
        )
        return {"triage_result": result}
    except Exception as exc:
        logger.exception("Triage classification failed")
        return {"errors": [f"Triage classification failed: {exc}"]}


def run_documentation(state: PipelineState) -> dict:
    """Generate FHIR R4 Bundle from triage results."""
    triage_result = state.get("triage_result")
    if not triage_result:
        logger.warning("No triage result available, skipping FHIR generation")
        return {"fhir_bundle": None}

    patient_data: PatientData = state["patient_data"]

    try:
        bundle = generate_fhir_bundle(
            patient_data=patient_data,
            triage_result=triage_result,
        )
        logger.info(
            "FHIR Bundle generated with %d entries", len(bundle.get("entry", []))
        )
        return {"fhir_bundle": bundle}
    except Exception as exc:
        logger.exception("FHIR generation failed")
        return {"errors": [f"FHIR generation failed: {exc}"], "fhir_bundle": None}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def _should_analyze_image(state: PipelineState) -> str:
    """Route to image analysis if image bytes are present."""
    if state.get("image_bytes"):
        return "run_image_analysis"
    return "run_triage"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Build and compile the triage pipeline graph."""
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("run_image_analysis", run_image_analysis)
    graph.add_node("run_triage", run_triage)
    graph.add_node("run_documentation", run_documentation)

    # Entry point: conditionally route to image analysis or triage
    graph.set_conditional_entry_point(
        _should_analyze_image,
        {
            "run_image_analysis": "run_image_analysis",
            "run_triage": "run_triage",
        },
    )

    # Edges
    graph.add_edge("run_image_analysis", "run_triage")
    graph.add_edge("run_triage", "run_documentation")
    graph.add_edge("run_documentation", END)

    return graph


# Module-level compiled graph (reusable)
_compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_pipeline(
    patient_data: PatientData,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/jpeg",
) -> PipelineState:
    """Run the full triage pipeline.

    Args:
        patient_data: Structured patient data (from intake or form).
        image_bytes: Optional raw image bytes for analysis.
        image_mime_type: MIME type of the image.

    Returns:
        PipelineState with triage_result, image_findings (if any),
        fhir_bundle (stub), and any errors.
    """
    initial_state: PipelineState = {
        "patient_data": patient_data,
        "image_bytes": image_bytes,
        "image_mime_type": image_mime_type,
        "errors": [],
    }

    logger.info(
        "Starting triage pipeline (image=%s)",
        "yes" if image_bytes else "no",
    )
    result = _compiled_graph.invoke(initial_state)
    logger.info(
        "Pipeline complete. Errors: %d",
        len(result.get("errors", [])),
    )
    return result
