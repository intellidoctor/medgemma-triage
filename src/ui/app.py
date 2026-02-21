"""Streamlit triage dashboard for Brazilian SUS emergency rooms.

Usage:
    streamlit run src/ui/app.py
"""

import json
import logging
from typing import Optional

import streamlit as st

# --- SWAP POINT: change these imports to use real agents -----------------
from src.agents.image_reader import analyze as analyze_image_agent
from src.agents.triage import (
    TRIAGE_LEVELS,
    PatientData,
    TriageColor,
    TriageResult,
    VitalSigns,
)
from src.fhir.builder import build_fhir_bundle as build_mock_fhir_bundle
from src.ui.mock_services import SAMPLE_CASES
from src.ui.mock_services import mock_classify as classify_patient

# -------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color display config
# ---------------------------------------------------------------------------

_COLOR_MAP: dict[TriageColor, dict[str, str]] = {
    TriageColor.RED: {"bg": "#DC2626", "fg": "#FFFFFF", "emoji": "\U0001f534"},
    TriageColor.ORANGE: {"bg": "#EA580C", "fg": "#FFFFFF", "emoji": "\U0001f7e0"},
    TriageColor.YELLOW: {"bg": "#CA8A04", "fg": "#000000", "emoji": "\U0001f7e1"},
    TriageColor.GREEN: {"bg": "#16A34A", "fg": "#FFFFFF", "emoji": "\U0001f7e2"},
    TriageColor.BLUE: {"bg": "#2563EB", "fg": "#FFFFFF", "emoji": "\U0001f535"},
}


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Intellidoctor — Triagem SUS",
    page_icon="\U0001f3e5",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS to match Intellidoctor brand palette
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #27273F;
    }
    [data-testid="stSidebar"] * {
        color: #E8E5F0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stButton button {
        color: #E8E5F0 !important;
    }
    /* Sidebar dropdown — dark background with visible text */
    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div > div,
    [data-testid="stSidebar"] [data-baseweb="select"] input {
        background-color: #3A3A55 !important;
        color: #E8E5F0 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #E8E5F0 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #E8E5F0 !important;
    }
    /* Sidebar button — outlined style with visible text */
    [data-testid="stSidebar"] .stButton > button {
        background-color: transparent;
        border: 1px solid #8776F6;
        color: #E8E5F0 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #8776F6;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #4A4660;
    }

    /* Primary button (Classificar Paciente) */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button {
        background-color: #8776F6;
        border-color: #8776F6;
        color: #FFFFFF !important;
    }
    .stFormSubmitButton > button:hover {
        background-color: #7565E0;
        border-color: #7565E0;
    }

    /* Expander headers */
    .streamlit-expanderHeader {
        color: #2D2B3D;
    }

    /* Progress bar */
    .stProgress > div > div > div > div {
        background-color: #8776F6;
    }

    /* Subheader accent */
    h2, h3 {
        color: #2D2B3D !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------


def _init_session_state() -> None:
    defaults: dict[str, object] = {
        "triage_result": None,
        "fhir_bundle": None,
        "image_findings": None,
        "selected_case": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<h3 style="color: #B8B0D8 !important;">Protocolo Manchester</h3>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.header("Casos de exemplo")
        case_names = ["(selecione)"] + [c["name"] for c in SAMPLE_CASES]
        selected = st.selectbox(
            "Carregar caso sintético",
            case_names,
            key="case_selector",
        )

        if selected != "(selecione)":
            for case in SAMPLE_CASES:
                if case["name"] == selected:
                    st.session_state["selected_case"] = case
                    break
        else:
            st.session_state["selected_case"] = None

        if st.button("Limpar formulário"):
            st.session_state["selected_case"] = None
            st.session_state["triage_result"] = None
            st.session_state["fhir_bundle"] = None
            st.session_state["image_findings"] = None
            st.rerun()

        st.divider()
        st.caption(
            "Este sistema auxilia enfermeiros de triagem — "
            "**nunca substitui** o julgamento clínico profissional."
        )
        st.caption("Dados 100% sintéticos. Nenhum dado real de paciente.")


# ---------------------------------------------------------------------------
# Helper to get case default
# ---------------------------------------------------------------------------


def _case_val(field: str, default: object = "") -> object:
    """Return field value from selected sample case, or default."""
    case = st.session_state.get("selected_case")
    if case is not None and field in case:
        return case[field]
    return default


# ---------------------------------------------------------------------------
# Intake form
# ---------------------------------------------------------------------------


def _render_intake_form() -> Optional[dict]:
    """Render the patient intake form. Returns form data dict on submit."""
    st.subheader("Dados do paciente")

    with st.form("intake_form"):
        col_name, col_age, col_sex = st.columns([3, 1, 1])
        with col_name:
            name = st.text_input("Nome do paciente", value=_case_val("name"))
        with col_age:
            age = st.number_input(
                "Idade",
                min_value=0,
                max_value=120,
                value=int(_case_val("age", 0)),
                step=1,
            )
        with col_sex:
            sex_options = ["M", "F"]
            sex_default = _case_val("sex", "M")
            sex_idx = (
                sex_options.index(sex_default) if sex_default in sex_options else 0
            )
            sex = st.selectbox("Sexo", sex_options, index=sex_idx)

        chief_complaint = st.text_area(
            "Queixa principal *",
            value=_case_val("chief_complaint"),
            height=68,
        )

        symptoms_str = st.text_input(
            "Sintomas (separados por vírgula)",
            value=_case_val("symptoms"),
        )

        col_onset, col_pain = st.columns(2)
        with col_onset:
            onset = st.text_input(
                "Início dos sintomas",
                value=_case_val("onset"),
            )
        with col_pain:
            pain_scale = st.slider(
                "Escala de dor (0-10)",
                min_value=0,
                max_value=10,
                value=int(_case_val("pain_scale", 0)),
            )

        with st.expander("Sinais vitais"):
            vs_c1, vs_c2, vs_c3 = st.columns(3)
            with vs_c1:
                heart_rate = st.number_input(
                    "Freq. cardíaca (bpm)",
                    min_value=0,
                    max_value=300,
                    value=int(_case_val("heart_rate", 0)),
                    step=1,
                )
                blood_pressure = st.text_input(
                    "Pressão arterial (ex: 120/80)",
                    value=_case_val("blood_pressure"),
                )
            with vs_c2:
                respiratory_rate = st.number_input(
                    "Freq. respiratória (/min)",
                    min_value=0,
                    max_value=60,
                    value=int(_case_val("respiratory_rate", 0)),
                    step=1,
                )
                temperature = st.number_input(
                    "Temperatura (°C)",
                    min_value=0.0,
                    max_value=45.0,
                    value=float(_case_val("temperature", 0.0)),
                    step=0.1,
                    format="%.1f",
                )
            with vs_c3:
                spo2 = st.number_input(
                    "SpO2 (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(_case_val("spo2", 0.0)),
                    step=0.1,
                    format="%.1f",
                )
                glucose = st.number_input(
                    "Glicemia (mg/dL)",
                    min_value=0.0,
                    max_value=600.0,
                    value=float(_case_val("glucose", 0.0)),
                    step=1.0,
                    format="%.0f",
                )

        with st.expander("Histórico"):
            history_str = st.text_input(
                "Histórico médico (separado por vírgula)",
                value=_case_val("history"),
            )
            medications_str = st.text_input(
                "Medicamentos em uso (separado por vírgula)",
                value=_case_val("medications"),
            )
            allergies_str = st.text_input(
                "Alergias (separado por vírgula)",
                value=_case_val("allergies"),
            )
            notes = st.text_area(
                "Notas adicionais",
                value=_case_val("notes"),
                height=68,
            )

        submitted = st.form_submit_button(
            "Classificar Paciente",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            return {
                "name": name,
                "age": age,
                "sex": sex,
                "chief_complaint": chief_complaint,
                "symptoms_str": symptoms_str,
                "onset": onset,
                "pain_scale": pain_scale,
                "heart_rate": heart_rate,
                "blood_pressure": blood_pressure,
                "respiratory_rate": respiratory_rate,
                "temperature": temperature,
                "spo2": spo2,
                "glucose": glucose,
                "history_str": history_str,
                "medications_str": medications_str,
                "allergies_str": allergies_str,
                "notes": notes,
            }

    return None


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


def _render_image_upload() -> None:
    st.subheader("Imagem médica (opcional)")
    uploaded = st.file_uploader(
        "Upload de imagem médica",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)
        image_bytes = uploaded.getvalue()
        mime_type = uploaded.type or "image/jpeg"
        try:
            findings = analyze_image_agent(image_bytes, mime_type)
            st.session_state["image_findings"] = findings.to_triage_summary()
            severity_display = findings.severity.value
            st.info(
                f"**Severidade:** {severity_display}\n\n"
                f"**Achados:** {findings.description}"
            )
        except Exception:
            logger.exception("Erro ao analisar imagem")
            st.error(
                "Ocorreu um erro ao analisar a imagem. "
                "Tente novamente ou contacte o suporte técnico."
            )
    else:
        st.session_state["image_findings"] = None


# ---------------------------------------------------------------------------
# Build PatientData from form
# ---------------------------------------------------------------------------


def _split_csv(text: str) -> Optional[list[str]]:
    """Split comma-separated string into list, or None if empty."""
    items = [s.strip() for s in text.split(",") if s.strip()]
    return items if items else None


def _build_patient_data(form: dict) -> PatientData:
    """Convert form dict into PatientData model."""
    vital_signs = VitalSigns(
        heart_rate=form["heart_rate"] if form["heart_rate"] > 0 else None,
        blood_pressure=form["blood_pressure"] if form["blood_pressure"] else None,
        respiratory_rate=(
            form["respiratory_rate"] if form["respiratory_rate"] > 0 else None
        ),
        temperature=form["temperature"] if form["temperature"] > 0.0 else None,
        spo2=form["spo2"] if form["spo2"] > 0.0 else None,
        glucose=form["glucose"] if form["glucose"] > 0.0 else None,
    )

    # Only include vital_signs if at least one field is set
    has_vitals = any(v is not None for v in vital_signs.model_dump().values())

    return PatientData(
        chief_complaint=form["chief_complaint"],
        symptoms=_split_csv(form["symptoms_str"]),
        onset=form["onset"] if form["onset"] else None,
        pain_scale=form["pain_scale"] if form["pain_scale"] > 0 else None,
        vital_signs=vital_signs if has_vitals else None,
        history=_split_csv(form["history_str"]),
        medications=_split_csv(form["medications_str"]),
        allergies=_split_csv(form["allergies_str"]),
        age=form["age"] if form["age"] > 0 else None,
        sex=form["sex"],
        image_findings=st.session_state.get("image_findings"),
        notes=form["notes"] if form["notes"] else None,
    )


# ---------------------------------------------------------------------------
# Triage result display
# ---------------------------------------------------------------------------


def _render_triage_result(result: TriageResult) -> None:
    """Render the color-coded Manchester triage classification."""
    colors = _COLOR_MAP[result.triage_color]
    level_name, max_wait = TRIAGE_LEVELS[result.triage_color]

    # Color banner
    st.markdown(
        f"""
        <div style="
            background-color: {colors['bg']};
            color: {colors['fg']};
            padding: 1.5rem;
            border-radius: 0.75rem;
            text-align: center;
            margin-bottom: 1rem;
        ">
            <h1 style="margin: 0; color: {colors['fg']};">
                {colors['emoji']} {level_name.upper()}
            </h1>
            <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem;">
                Tempo máximo de espera: <strong>{max_wait} min</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.parse_failed:
        st.warning(
            "A resposta do modelo não pôde ser interpretada completamente. "
            "Classificação padrão aplicada — revise manualmente."
        )

    # Confidence
    st.markdown("**Confiança do modelo**")
    st.progress(result.confidence, text=f"{result.confidence:.0%}")

    # Reasoning
    st.markdown("**Raciocínio clínico**")
    st.info(result.reasoning)

    # Key discriminators
    if result.key_discriminators:
        st.markdown("**Discriminadores-chave**")
        for disc in result.key_discriminators:
            st.markdown(f"- {disc}")


def _render_fhir_output(fhir_bundle: dict) -> None:
    """Render the FHIR JSON output with download button."""
    with st.expander("FHIR Bundle (JSON)"):
        st.json(fhir_bundle)
        fhir_json = json.dumps(fhir_bundle, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download FHIR JSON",
            data=fhir_json,
            file_name="triage_fhir_bundle.json",
            mime="application/json",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the Streamlit dashboard."""
    st.image("public/logo_horizontal.png", width=280)
    st.markdown(
        '<p style="color: #6B6880; margin-top: -0.5rem; margin-bottom: 1.5rem;">'
        "Sistema de apoio à triagem para enfermeiros do SUS. "
        "Auxilia na classificação de risco — nunca substitui o profissional."
        "</p>",
        unsafe_allow_html=True,
    )

    if "mock" in classify_patient.__module__:
        st.warning(
            "Modo demonstração — usando dados sintéticos e classificação simulada. "
            "Não utilizar para decisões clínicas reais."
        )

    _render_sidebar()

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        form_data = _render_intake_form()
        _render_image_upload()

        # Handle form submission
        if form_data is not None:
            if not form_data["chief_complaint"].strip():
                st.error("Queixa principal é obrigatória.")
            else:
                try:
                    patient_data = _build_patient_data(form_data)
                    result = classify_patient(patient_data)
                    fhir_bundle = build_mock_fhir_bundle(
                        patient_name=form_data["name"] or "Paciente",
                        patient_age=(
                            form_data["age"] if form_data["age"] > 0 else None
                        ),
                        patient_sex=form_data["sex"],
                        patient_data=patient_data,
                        triage_result=result,
                    )
                    st.session_state["triage_result"] = result
                    st.session_state["fhir_bundle"] = fhir_bundle
                except Exception:
                    logger.exception("Erro ao classificar paciente")
                    st.error(
                        "Ocorreu um erro ao processar a classificação. "
                        "Tente novamente ou contacte o suporte técnico."
                    )

    with col_right:
        st.subheader("Resultado da triagem")
        result = st.session_state.get("triage_result")
        fhir_bundle = st.session_state.get("fhir_bundle")

        if result is not None:
            _render_triage_result(result)
            if fhir_bundle is not None:
                _render_fhir_output(fhir_bundle)
        else:
            st.info(
                "Preencha o formulário e clique em "
                '"Classificar Paciente" para ver o resultado.'
            )


if __name__ == "__main__":
    main()
