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

import base64
import json
import logging
from typing import Annotated, Optional

import httpx
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
    lang: str
    patient_name: str
    patient_age: Optional[int]
    patient_sex: Optional[str]

    # Intermediate results
    image_findings: Optional[ImageFindings]

    # Outputs
    triage_result: Optional[TriageResult]
    fhir_bundle: Optional[dict]

    # Pipeline metadata
    errors: Annotated[list[str], _append_errors]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_patient_data(raw: object) -> PatientData:
    """Coerce a dict (from HTTP/JSON) into a PatientData model."""
    if isinstance(raw, PatientData):
        return raw
    if isinstance(raw, dict):
        return PatientData(**raw)
    raise TypeError(f"Expected PatientData or dict, got {type(raw)}")


def _ensure_triage_result(raw: object) -> Optional[TriageResult]:
    """Coerce a dict (from HTTP/JSON) into a TriageResult model."""
    if raw is None:
        return None
    if isinstance(raw, TriageResult):
        return raw
    if isinstance(raw, dict):
        return TriageResult(**raw)
    raise TypeError(f"Expected TriageResult or dict, got {type(raw)}")


def _ensure_image_bytes(raw: object) -> Optional[bytes]:
    """Coerce base64 string (from HTTP/JSON) into bytes."""
    if raw is None or isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return base64.b64decode(raw)
    raise TypeError(f"Expected bytes or base64 str, got {type(raw)}")


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def run_image_analysis(state: PipelineState) -> dict:
    """Analyze a medical image via MedGemma 4B."""
    image_bytes = _ensure_image_bytes(state.get("image_bytes"))
    if not image_bytes:
        return {}

    mime_type = state.get("image_mime_type", "image/jpeg")
    patient_data = _ensure_patient_data(state["patient_data"])

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
    patient_data = _ensure_patient_data(state["patient_data"])

    lang = state.get("lang", "pt")

    try:
        result = classify_patient(patient_data, lang=lang)
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
    triage_result = _ensure_triage_result(state.get("triage_result"))
    if not triage_result:
        logger.warning("No triage result available, skipping FHIR generation")
        return {"fhir_bundle": None}

    patient_data = _ensure_patient_data(state["patient_data"])

    try:
        bundle = generate_fhir_bundle(
            patient_data=patient_data,
            triage_result=triage_result,
            patient_name=state.get("patient_name", "Paciente"),
            patient_age=state.get("patient_age"),
            patient_sex=state.get("patient_sex"),
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


_STUDIO_URL = "http://127.0.0.1:2024"
_GRAPH_ID = "triage_pipeline"


def _build_initial_state(
    patient_data: PatientData,
    image_bytes: Optional[bytes],
    image_mime_type: str,
    lang: str,
    patient_name: str,
    patient_age: Optional[int],
    patient_sex: Optional[str],
) -> dict:
    """Build the initial state dict for the pipeline."""
    return {
        "patient_data": patient_data.model_dump(),
        "image_bytes": (
            base64.b64encode(image_bytes).decode() if image_bytes else None
        ),
        "image_mime_type": image_mime_type,
        "lang": lang,
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_sex": patient_sex,
        "errors": [],
    }


def _parse_studio_result(raw: dict) -> PipelineState:
    """Convert the JSON response from Studio back into typed objects."""
    result: PipelineState = {
        "errors": raw.get("errors", []),
        "fhir_bundle": raw.get("fhir_bundle"),
    }

    tr = raw.get("triage_result")
    if tr and isinstance(tr, dict):
        result["triage_result"] = TriageResult(**tr)

    img = raw.get("image_findings")
    if img and isinstance(img, dict):
        result["image_findings"] = ImageFindings(**img)

    return result


def _run_via_studio(initial_state: dict) -> PipelineState:
    """Invoke the graph through the LangGraph dev server streaming API.

    Uses ``/runs/stream`` so that LangGraph Studio can visualise each
    node executing in real-time.  The final ``values`` event contains
    the completed state.
    """
    with httpx.Client(base_url=_STUDIO_URL, timeout=120) as client:
        # 1. Find the assistant for our graph
        assistants = client.post(
            "/assistants/search",
            json={"graph_id": _GRAPH_ID},
        ).json()
        if not assistants:
            raise RuntimeError(
                f"No assistant found for graph '{_GRAPH_ID}' "
                f"on {_STUDIO_URL}. Is `langgraph dev` running?"
            )
        assistant_id = assistants[0]["assistant_id"]

        # 2. Create a thread
        thread = client.post("/threads", json={}).json()
        thread_id = thread["thread_id"]

        # 3. Stream the run — Studio shows nodes lighting up in real-time
        final_state: dict = {}
        with client.stream(
            "POST",
            f"/threads/{thread_id}/runs/stream",
            json={
                "assistant_id": assistant_id,
                "input": initial_state,
                "stream_mode": "values",
            },
        ) as sse:
            for line in sse.iter_lines():
                # SSE format: "event: <type>\ndata: <json>\n\n"
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if isinstance(data, dict):
                            final_state = data
                    except json.JSONDecodeError:
                        continue

        return _parse_studio_result(final_state)


def run_pipeline(
    patient_data: PatientData,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/jpeg",
    lang: str = "pt",
    patient_name: str = "Paciente",
    patient_age: Optional[int] = None,
    patient_sex: Optional[str] = None,
    use_langgraph_studio: bool = False,
) -> PipelineState:
    """Run the full triage pipeline.

    Args:
        patient_data: Structured patient data (from intake or form).
        image_bytes: Optional raw image bytes for analysis.
        image_mime_type: MIME type of the image.
        lang: Language code (``"pt"`` or ``"en"``).
        patient_name: Display name for FHIR output.
        patient_age: Age in years for FHIR output.
        patient_sex: ``"M"`` or ``"F"`` for FHIR output.
        use_langgraph_studio: When True, invoke the graph via the
            LangGraph dev server HTTP API so the run is visible in
            LangGraph Studio. Requires ``langgraph dev`` to be running.

    Returns:
        PipelineState with triage_result, image_findings (if any),
        fhir_bundle, and any errors.
    """
    logger.info(
        "Starting triage pipeline (image=%s, studio=%s)",
        "yes" if image_bytes else "no",
        "yes" if use_langgraph_studio else "no",
    )

    if use_langgraph_studio:
        state = _build_initial_state(
            patient_data,
            image_bytes,
            image_mime_type,
            lang,
            patient_name,
            patient_age,
            patient_sex,
        )
        try:
            result = _run_via_studio(state)
        except Exception as exc:
            logger.exception("Studio invocation failed, falling back to local")
            result = {"errors": [f"Studio invocation failed: {exc}"]}
    else:
        initial_state: PipelineState = {
            "patient_data": patient_data,
            "image_bytes": image_bytes,
            "image_mime_type": image_mime_type,
            "lang": lang,
            "patient_name": patient_name,
            "patient_age": patient_age,
            "patient_sex": patient_sex,
            "errors": [],
        }
        result = _compiled_graph.invoke(initial_state)

    logger.info(
        "Pipeline complete. Errors: %d",
        len(result.get("errors", [])),
    )
    return result
