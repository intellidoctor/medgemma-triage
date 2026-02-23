"""Streamlit triage dashboard for Brazilian SUS emergency rooms.

Usage:
    streamlit run src/ui/app.py
"""

import json
import logging
import time
from pathlib import Path
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
from src.agents.triage import classify as real_classify
from src.fhir.builder import build_fhir_bundle as build_mock_fhir_bundle
from src.ui.mock_services import mock_classify as classify_patient
from src.ui.strings import get_strings

# -------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# Show INFO-level logs in the terminal running streamlit
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Test case loader (data/sample_cases/*.json → flat form dict)
# ---------------------------------------------------------------------------

_CASES_DIR = Path("data/sample_cases")


def _load_test_cases(lang: str = "pt") -> list[dict]:
    """Load JSON test cases filtered by language."""
    cases: list[dict] = []
    for path in sorted(_CASES_DIR.glob("case_*.json")):
        try:
            with open(path) as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to load test case %s, skipping", path, exc_info=True)
            continue
        if raw.get("lang", "en") != lang:
            continue
        p = raw["patient"]
        vs = p.get("vital_signs", {})
        flat = {
            "name": p.get("name", ""),
            "age": p.get("age", 0),
            "sex": p.get("sex", "M"),
            "chief_complaint": p.get("chief_complaint", ""),
            "symptoms": ", ".join(p.get("symptoms", [])),
            "onset": p.get("onset", ""),
            "pain_scale": p.get("pain_scale", 0),
            "heart_rate": vs.get("heart_rate", 0),
            "blood_pressure": vs.get("blood_pressure", ""),
            "respiratory_rate": vs.get("respiratory_rate", 0),
            "temperature": vs.get("temperature", 0.0),
            "spo2": vs.get("spo2", 0.0),
            "glucose": vs.get("glucose", 0.0),
            "history": ", ".join(p.get("history", [])),
            "medications": ", ".join(p.get("medications", [])),
            "allergies": ", ".join(p.get("allergies", [])),
            "notes": p.get("notes", ""),
            "_test_case_id": raw.get("id", ""),
            "_test_case_title": raw.get("title", ""),
        }
        cases.append(flat)
    return cases


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

_LEVEL_KEYS: dict[TriageColor, str] = {
    TriageColor.RED: "level_red",
    TriageColor.ORANGE: "level_orange",
    TriageColor.YELLOW: "level_yellow",
    TriageColor.GREEN: "level_green",
    TriageColor.BLUE: "level_blue",
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
        "use_real_model": False,
        "lang": "pt",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar(s: dict[str, str], lang: str) -> None:
    with st.sidebar:
        # Language selector — always first
        lang_options = ["Português", "English"]
        lang_index = 0 if lang == "pt" else 1
        selected_lang = st.selectbox(
            s["language_label"],
            lang_options,
            index=lang_index,
            key="lang_selector",
        )
        new_lang = "pt" if selected_lang == "Português" else "en"
        if new_lang != st.session_state["lang"]:
            st.session_state["lang"] = new_lang
            st.session_state["selected_case"] = None
            st.rerun()

        st.divider()

        st.markdown(
            f'<h3 style="color: #B8B0D8 !important;">{s["sidebar_header"]}</h3>',
            unsafe_allow_html=True,
        )
        # --- Sample cases (mock) — hidden for now ---
        # st.divider()
        # st.header(s["sidebar_sample_cases"])
        # cases = get_sample_cases(lang)
        # case_names = [s["sidebar_select_placeholder"]] + [
        #     c["name"] for c in cases
        # ]
        # selected = st.selectbox(
        #     s["sidebar_load_case"],
        #     case_names,
        #     key="case_selector",
        # )
        # if selected != s["sidebar_select_placeholder"]:
        #     for case in cases:
        #         if case["name"] == selected:
        #             st.session_state["selected_case"] = case
        #             st.session_state["use_real_model"] = False
        #             break
        # else:
        #     if not st.session_state.get("use_real_model"):
        #         st.session_state["selected_case"] = None

        # Handle pending resets before widgets are instantiated
        if st.session_state.get("_pending_clear"):
            st.session_state["test_case_selector"] = s["sidebar_select_placeholder"]
            st.session_state["_pending_clear"] = False

        # Test cases (real MedGemma)
        st.divider()
        st.header(s["sidebar_test_cases"])
        test_cases = _load_test_cases(lang)
        test_names = [s["sidebar_select_placeholder"]] + [
            f"{tc['_test_case_id']}: {tc['name']}" for tc in test_cases
        ]

        test_selected = st.selectbox(
            s["sidebar_load_test_case"],
            test_names,
            key="test_case_selector",
        )

        if test_selected != s["sidebar_select_placeholder"]:
            for tc in test_cases:
                label = f"{tc['_test_case_id']}: {tc['name']}"
                if label == test_selected:
                    st.session_state["selected_case"] = tc
                    st.session_state["use_real_model"] = True
                    break
        else:
            st.session_state["selected_case"] = None
            st.session_state["use_real_model"] = False

        st.divider()
        if st.button(s["sidebar_clear"]):
            st.session_state["selected_case"] = None
            st.session_state["use_real_model"] = False
            st.session_state["triage_result"] = None
            st.session_state["fhir_bundle"] = None
            st.session_state["image_findings"] = None
            st.session_state["_pending_clear"] = True
            st.rerun()

        st.divider()
        st.caption(s["sidebar_disclaimer"])
        st.caption(s["sidebar_synthetic"])


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


def _render_intake_form(s: dict[str, str]) -> Optional[dict]:
    """Render the patient intake form. Returns form data dict on submit."""
    st.subheader(s["patient_data"])

    with st.form("intake_form"):
        col_name, col_age, col_sex = st.columns([3, 1, 1])
        with col_name:
            name = st.text_input(s["patient_name"], value=_case_val("name"))
        with col_age:
            age = st.number_input(
                s["age"],
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
            sex = st.selectbox(s["sex"], sex_options, index=sex_idx)

        chief_complaint = st.text_area(
            s["chief_complaint"],
            value=_case_val("chief_complaint"),
            height=68,
        )

        symptoms_str = st.text_input(
            s["symptoms"],
            value=_case_val("symptoms"),
        )

        col_onset, col_pain = st.columns(2)
        with col_onset:
            onset = st.text_input(
                s["onset"],
                value=_case_val("onset"),
            )
        with col_pain:
            pain_scale = st.slider(
                s["pain_scale"],
                min_value=0,
                max_value=10,
                value=int(_case_val("pain_scale", 0)),
            )

        with st.expander(s["vital_signs"]):
            vs_c1, vs_c2, vs_c3 = st.columns(3)
            with vs_c1:
                heart_rate = st.number_input(
                    s["heart_rate"],
                    min_value=0,
                    max_value=300,
                    value=int(_case_val("heart_rate", 0)),
                    step=1,
                )
                blood_pressure = st.text_input(
                    s["blood_pressure"],
                    value=_case_val("blood_pressure"),
                )
            with vs_c2:
                respiratory_rate = st.number_input(
                    s["respiratory_rate"],
                    min_value=0,
                    max_value=60,
                    value=int(_case_val("respiratory_rate", 0)),
                    step=1,
                )
                temperature = st.number_input(
                    s["temperature"],
                    min_value=0.0,
                    max_value=45.0,
                    value=float(_case_val("temperature", 0.0)),
                    step=0.1,
                    format="%.1f",
                )
            with vs_c3:
                spo2 = st.number_input(
                    s["spo2"],
                    min_value=0.0,
                    max_value=100.0,
                    value=float(_case_val("spo2", 0.0)),
                    step=0.1,
                    format="%.1f",
                )
                glucose = st.number_input(
                    s["glucose"],
                    min_value=0.0,
                    max_value=600.0,
                    value=float(_case_val("glucose", 0.0)),
                    step=1.0,
                    format="%.0f",
                )

        with st.expander(s["history_section"]):
            history_str = st.text_input(
                s["history"],
                value=_case_val("history"),
            )
            medications_str = st.text_input(
                s["medications"],
                value=_case_val("medications"),
            )
            allergies_str = st.text_input(
                s["allergies"],
                value=_case_val("allergies"),
            )
            notes = st.text_area(
                s["notes"],
                value=_case_val("notes"),
                height=68,
            )

        submitted = st.form_submit_button(
            s["classify_button"],
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


def _render_image_upload(s: dict[str, str]) -> None:
    st.subheader(s["image_upload_header"])
    uploaded = st.file_uploader(
        s["image_upload_label"],
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
                f"**{s['image_severity']}:** {severity_display}\n\n"
                f"**{s['image_findings']}:** {findings.description}"
            )
        except Exception:
            logger.exception("Error analysing image")
            st.error(s["image_error"])
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


def _render_triage_result(result: TriageResult, s: dict[str, str]) -> None:
    """Render the color-coded Manchester triage classification."""
    colors = _COLOR_MAP[result.triage_color]
    level_name = s[_LEVEL_KEYS[result.triage_color]]
    _, max_wait = TRIAGE_LEVELS[result.triage_color]

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
                {s['max_wait']}: <strong>{max_wait} min</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.parse_failed:
        st.warning(s["parse_warning"])

    # Confidence
    st.markdown(f"**{s['model_confidence']}**")
    st.progress(result.confidence, text=f"{result.confidence:.0%}")

    # Reasoning
    st.markdown(f"**{s['clinical_reasoning']}**")
    st.info(result.reasoning)

    # Key discriminators
    if result.key_discriminators:
        st.markdown(f"**{s['key_discriminators']}**")
        for disc in result.key_discriminators:
            st.markdown(f"- {disc}")


def _render_fhir_output(fhir_bundle: dict, s: dict[str, str]) -> None:
    """Render the FHIR JSON output with download button."""
    with st.expander(s["fhir_bundle"]):
        st.json(fhir_bundle)
        fhir_json = json.dumps(fhir_bundle, indent=2, ensure_ascii=False)
        st.download_button(
            label=s["download_fhir"],
            data=fhir_json,
            file_name="triage_fhir_bundle.json",
            mime="application/json",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the Streamlit dashboard."""
    lang: str = st.session_state.get("lang", "pt")
    s = get_strings(lang)

    st.image("public/logo_horizontal.png", width=280)
    st.markdown(
        f'<p style="color: #6B6880; margin-top: -0.5rem; margin-bottom: 1.5rem;">'
        f"{s['main_subtitle']}"
        f"</p>",
        unsafe_allow_html=True,
    )

    use_real = st.session_state.get("use_real_model", False)

    _render_sidebar(s, lang)

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        form_data = _render_intake_form(s)
        _render_image_upload(s)

        # Handle form submission
        if form_data is not None:
            if not form_data["chief_complaint"].strip():
                st.error(s["chief_complaint_required"])
            else:
                try:
                    patient_data = _build_patient_data(form_data)
                    if use_real:
                        logger.info(
                            "\033[1;34m\U0001f3e5 Starting real MedGemma "
                            "triage classification...\033[0m"
                        )
                        t0 = time.time()
                        result = real_classify(patient_data, lang=lang)
                        elapsed = time.time() - t0
                        logger.info(
                            "\033[1;32m\U0001f3c1 MedGemma result: %s "
                            "in %.1fs\033[0m",
                            result.triage_color.value,
                            elapsed,
                        )
                    else:
                        result = classify_patient(patient_data, lang=lang)
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
                    logger.exception(
                        "\033[1;31m\U0000274c Error classifying patient\033[0m"
                    )
                    st.error(s["classification_error"])

    with col_right:
        st.subheader(s["triage_result_header"])
        result = st.session_state.get("triage_result")
        fhir_bundle = st.session_state.get("fhir_bundle")

        if result is not None:
            _render_triage_result(result, s)
            if fhir_bundle is not None:
                _render_fhir_output(fhir_bundle, s)
        else:
            st.info(s["result_placeholder"])


if __name__ == "__main__":
    main()
