"""Internationalisation strings for the Streamlit UI.

Provides Portuguese (pt) and English (en) translations for all
user-facing labels, messages, and mock-data templates.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Portuguese strings
# ---------------------------------------------------------------------------

_STRINGS_PT: Dict[str, str] = {
    # Page config
    "page_title": "Intellidoctor — Triagem SUS",
    # Sidebar
    "sidebar_header": "Protocolo Manchester",
    "sidebar_sample_cases": "Casos de exemplo",
    "sidebar_load_case": "Carregar caso sintético",
    "sidebar_select_placeholder": "(selecione)",
    "sidebar_test_cases": "Casos de teste",
    "sidebar_load_test_case": "Carregar caso de teste (MedGemma)",
    "sidebar_clear": "Limpar formulário",
    "sidebar_disclaimer": (
        "Este sistema auxilia enfermeiros de triagem — "
        "**nunca substitui** o julgamento clínico profissional."
    ),
    "sidebar_synthetic": "Dados 100% sintéticos. Nenhum dado real de paciente.",
    # Main header
    "main_subtitle": (
        "Sistema de apoio à triagem para enfermeiros do SUS. "
        "Auxilia na classificação de risco — nunca substitui o profissional."
    ),
    "demo_warning": (
        "Modo demonstração — usando dados sintéticos e classificação simulada. "
        "Não utilizar para decisões clínicas reais."
    ),
    # Patient form
    "patient_data": "Dados do paciente",
    "patient_name": "Nome do paciente",
    "age": "Idade",
    "sex": "Sexo",
    "chief_complaint": "Queixa principal *",
    "symptoms": "Sintomas (separados por vírgula)",
    "onset": "Início dos sintomas",
    "pain_scale": "Escala de dor (0-10)",
    # Vital signs
    "vital_signs": "Sinais vitais",
    "heart_rate": "Freq. cardíaca (bpm)",
    "blood_pressure": "Pressão arterial (ex: 120/80)",
    "respiratory_rate": "Freq. respiratória (/min)",
    "temperature": "Temperatura (°C)",
    "spo2": "SpO2 (%)",
    "glucose": "Glicemia (mg/dL)",
    # History
    "history_section": "Histórico",
    "history": "Histórico médico (separado por vírgula)",
    "medications": "Medicamentos em uso (separado por vírgula)",
    "allergies": "Alergias (separado por vírgula)",
    "notes": "Notas adicionais",
    # Submit
    "classify_button": "Classificar Paciente",
    "chief_complaint_required": "Queixa principal é obrigatória.",
    "classification_error": (
        "Ocorreu um erro ao processar a classificação. "
        "Tente novamente ou contacte o suporte técnico."
    ),
    # Image upload
    "image_upload_header": "Imagem médica (opcional)",
    "image_upload_label": "Upload de imagem médica",
    "image_severity": "Severidade",
    "image_findings": "Achados",
    "image_error": (
        "Ocorreu um erro ao analisar a imagem. "
        "Tente novamente ou contacte o suporte técnico."
    ),
    # Triage result
    "triage_result_header": "Resultado da triagem",
    "max_wait": "Tempo máximo de espera",
    "parse_warning": (
        "A resposta do modelo não pôde ser interpretada completamente. "
        "Classificação padrão aplicada — revise manualmente."
    ),
    "model_confidence": "Confiança do modelo",
    "clinical_reasoning": "Raciocínio clínico",
    "key_discriminators": "Discriminadores-chave",
    "result_placeholder": (
        "Preencha o formulário e clique em "
        '"Classificar Paciente" para ver o resultado.'
    ),
    # FHIR
    "fhir_bundle": "FHIR Bundle (JSON)",
    "download_fhir": "Download FHIR JSON",
    # Language selector
    "language_label": "Idioma / Language",
    # Triage level names
    "level_red": "Emergência",
    "level_orange": "Muito urgente",
    "level_yellow": "Urgente",
    "level_green": "Pouco urgente",
    "level_blue": "Não urgente",
    # Mock reasoning
    "reasoning_red": (
        "Paciente apresenta sinais de ameaça imediata à vida. "
        "Necessita atendimento imediato conforme Protocolo de Manchester."
    ),
    "reasoning_orange": (
        "Quadro clínico sugere condição muito urgente com risco potencial. "
        "Discriminadores-chave indicam necessidade de avaliação em até 10 minutos."
    ),
    "reasoning_yellow": (
        "Paciente apresenta sinais de urgência moderada. "
        "Sinais vitais e quadro clínico indicam necessidade de avaliação "
        "em até 60 minutos."
    ),
    "reasoning_green": (
        "Quadro clínico estável, sem sinais de urgência. "
        "Paciente pode aguardar atendimento em até 120 minutos."
    ),
    "reasoning_blue": (
        "Demanda não urgente, sem achados clínicos agudos. "
        "Paciente pode ser atendido em até 240 minutos ou encaminhado "
        "para unidade básica de saúde."
    ),
    # Mock discriminators
    "disc_red_1": "Comprometimento de via aérea",
    "disc_red_2": "Nível de consciência alterado",
    "disc_red_3": "Hemorragia ativa",
    "disc_orange_1": "Dor severa (8-10)",
    "disc_orange_2": "Risco cardíaco",
    "disc_orange_3": "Desconforto respiratório grave",
    "disc_yellow_1": "Dor moderada (4-7)",
    "disc_yellow_2": "Sinais vitais alterados",
    "disc_yellow_3": "Febre significativa",
    "disc_green_1": "Dor leve (1-3)",
    "disc_green_2": "Sinais vitais estáveis",
    "disc_green_3": "Lesão menor",
    "disc_blue_1": "Sem achados agudos",
    "disc_blue_2": "Demanda administrativa",
    "disc_blue_3": "Queixa crônica estável",
    # Mock raw response
    "mock_raw_response": "[mock response — nenhuma chamada ao modelo realizada]",
}

# ---------------------------------------------------------------------------
# English strings
# ---------------------------------------------------------------------------

_STRINGS_EN: Dict[str, str] = {
    # Page config
    "page_title": "Intellidoctor — SUS Triage",
    # Sidebar
    "sidebar_header": "Manchester Protocol",
    "sidebar_sample_cases": "Sample cases",
    "sidebar_load_case": "Load synthetic case",
    "sidebar_select_placeholder": "(select)",
    "sidebar_test_cases": "Test cases",
    "sidebar_load_test_case": "Load test case (MedGemma)",
    "sidebar_clear": "Clear form",
    "sidebar_disclaimer": (
        "This system assists triage nurses — "
        "it **never replaces** professional clinical judgment."
    ),
    "sidebar_synthetic": "100% synthetic data. No real patient data.",
    # Main header
    "main_subtitle": (
        "Triage support system for SUS nurses. "
        "Assists with risk classification — never replaces the professional."
    ),
    "demo_warning": (
        "Demo mode — using synthetic data and simulated classification. "
        "Do not use for real clinical decisions."
    ),
    # Patient form
    "patient_data": "Patient data",
    "patient_name": "Patient name",
    "age": "Age",
    "sex": "Sex",
    "chief_complaint": "Chief complaint *",
    "symptoms": "Symptoms (comma-separated)",
    "onset": "Symptom onset",
    "pain_scale": "Pain scale (0-10)",
    # Vital signs
    "vital_signs": "Vital signs",
    "heart_rate": "Heart rate (bpm)",
    "blood_pressure": "Blood pressure (e.g. 120/80)",
    "respiratory_rate": "Respiratory rate (/min)",
    "temperature": "Temperature (°C)",
    "spo2": "SpO2 (%)",
    "glucose": "Blood glucose (mg/dL)",
    # History
    "history_section": "History",
    "history": "Medical history (comma-separated)",
    "medications": "Current medications (comma-separated)",
    "allergies": "Allergies (comma-separated)",
    "notes": "Additional notes",
    # Submit
    "classify_button": "Classify Patient",
    "chief_complaint_required": "Chief complaint is required.",
    "classification_error": (
        "An error occurred while processing the classification. "
        "Please try again or contact technical support."
    ),
    # Image upload
    "image_upload_header": "Medical image (optional)",
    "image_upload_label": "Upload medical image",
    "image_severity": "Severity",
    "image_findings": "Findings",
    "image_error": (
        "An error occurred while analysing the image. "
        "Please try again or contact technical support."
    ),
    # Triage result
    "triage_result_header": "Triage result",
    "max_wait": "Maximum wait time",
    "parse_warning": (
        "The model response could not be fully parsed. "
        "Default classification applied — please review manually."
    ),
    "model_confidence": "Model confidence",
    "clinical_reasoning": "Clinical reasoning",
    "key_discriminators": "Key discriminators",
    "result_placeholder": (
        "Fill out the form and click " '"Classify Patient" to see the result.'
    ),
    # FHIR
    "fhir_bundle": "FHIR Bundle (JSON)",
    "download_fhir": "Download FHIR JSON",
    # Language selector
    "language_label": "Idioma / Language",
    # Triage level names
    "level_red": "Emergency",
    "level_orange": "Very urgent",
    "level_yellow": "Urgent",
    "level_green": "Standard",
    "level_blue": "Non-urgent",
    # Mock reasoning
    "reasoning_red": (
        "Patient presents signs of immediate life threat. "
        "Requires immediate care per Manchester Protocol."
    ),
    "reasoning_orange": (
        "Clinical picture suggests very urgent condition with potential risk. "
        "Key discriminators indicate need for evaluation within 10 minutes."
    ),
    "reasoning_yellow": (
        "Patient presents signs of moderate urgency. "
        "Vital signs and clinical picture indicate need for evaluation "
        "within 60 minutes."
    ),
    "reasoning_green": (
        "Stable clinical picture, no signs of urgency. "
        "Patient may wait for care up to 120 minutes."
    ),
    "reasoning_blue": (
        "Non-urgent demand, no acute clinical findings. "
        "Patient may be seen within 240 minutes or referred "
        "to a primary care unit."
    ),
    # Mock discriminators
    "disc_red_1": "Airway compromise",
    "disc_red_2": "Altered level of consciousness",
    "disc_red_3": "Active haemorrhage",
    "disc_orange_1": "Severe pain (8-10)",
    "disc_orange_2": "Cardiac risk",
    "disc_orange_3": "Severe respiratory distress",
    "disc_yellow_1": "Moderate pain (4-7)",
    "disc_yellow_2": "Altered vital signs",
    "disc_yellow_3": "Significant fever",
    "disc_green_1": "Mild pain (1-3)",
    "disc_green_2": "Stable vital signs",
    "disc_green_3": "Minor injury",
    "disc_blue_1": "No acute findings",
    "disc_blue_2": "Administrative demand",
    "disc_blue_3": "Stable chronic complaint",
    # Mock raw response
    "mock_raw_response": "[mock response — no model call made]",
}


def get_strings(lang: str) -> Dict[str, str]:
    """Return the string dictionary for the given language code.

    Args:
        lang: Language code, either ``"pt"`` or ``"en"``.

    Returns:
        Dictionary mapping string keys to localised text.
    """
    if lang == "en":
        return _STRINGS_EN
    return _STRINGS_PT
