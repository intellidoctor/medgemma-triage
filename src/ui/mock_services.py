"""Mock service layer for the Streamlit UI.

Provides synthetic triage classification and image analysis
so the dashboard works end-to-end without Vertex AI credentials.

To swap to real agents, change the import in app.py:
    from src.agents.triage import classify
    from src.models.medgemma import analyze_image
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from src.agents.triage import (
    TRIAGE_LEVELS,
    PatientData,
    TriageColor,
    TriageResult,
    VitalSigns,
)

# ---------------------------------------------------------------------------
# Keyword-to-color mapping for mock classification
# ---------------------------------------------------------------------------

_HIGH_ACUITY_KEYWORDS: list[str] = [
    "unresponsive",
    "airway",
    "choking",
    "hemorrhage",
    "seizure",
    "convulsão",
    "parada",
    "inconsciente",
]

_ORANGE_KEYWORDS: list[str] = [
    "chest pain",
    "dor no peito",
    "peito",
    "stroke",
    "avc",
    "altered consciousness",
    "severe pain",
    "dor intensa",
]

_YELLOW_KEYWORDS: list[str] = [
    "febre",
    "fever",
    "vomit",
    "vômito",
    "abdomen",
    "abdômen",
    "falta de ar",
    "dyspnea",
    "dispneia",
    "asma",
    "wheezing",
]

_GREEN_KEYWORDS: list[str] = [
    "torci",
    "sprain",
    "minor",
    "leve",
    "cut",
    "corte",
    "pequeno",
    "dor leve",
]

_BLUE_KEYWORDS: list[str] = [
    "receita",
    "refill",
    "prescription",
    "renovar",
    "atestado",
    "certificate",
    "consulta de rotina",
]

# ---------------------------------------------------------------------------
# Reasoning templates (Portuguese)
# ---------------------------------------------------------------------------

_REASONING: dict[TriageColor, str] = {
    TriageColor.RED: (
        "Paciente apresenta sinais de ameaça imediata à vida. "
        "Necessita atendimento imediato conforme Protocolo de Manchester."
    ),
    TriageColor.ORANGE: (
        "Quadro clínico sugere condição muito urgente com risco potencial. "
        "Discriminadores-chave indicam necessidade de avaliação em até 10 minutos."
    ),
    TriageColor.YELLOW: (
        "Paciente apresenta sinais de urgência moderada. "
        "Sinais vitais e quadro clínico indicam necessidade de avaliação "
        "em até 60 minutos."
    ),
    TriageColor.GREEN: (
        "Quadro clínico estável, sem sinais de urgência. "
        "Paciente pode aguardar atendimento em até 120 minutos."
    ),
    TriageColor.BLUE: (
        "Demanda não urgente, sem achados clínicos agudos. "
        "Paciente pode ser atendido em até 240 minutos ou encaminhado "
        "para unidade básica de saúde."
    ),
}

_DISCRIMINATORS: dict[TriageColor, list[str]] = {
    TriageColor.RED: [
        "Comprometimento de via aérea",
        "Nível de consciência alterado",
        "Hemorragia ativa",
    ],
    TriageColor.ORANGE: [
        "Dor severa (8-10)",
        "Risco cardíaco",
        "Desconforto respiratório grave",
    ],
    TriageColor.YELLOW: [
        "Dor moderada (4-7)",
        "Sinais vitais alterados",
        "Febre significativa",
    ],
    TriageColor.GREEN: [
        "Dor leve (1-3)",
        "Sinais vitais estáveis",
        "Lesão menor",
    ],
    TriageColor.BLUE: [
        "Sem achados agudos",
        "Demanda administrativa",
        "Queixa crônica estável",
    ],
}

_CONFIDENCE: dict[TriageColor, float] = {
    TriageColor.RED: 0.95,
    TriageColor.ORANGE: 0.90,
    TriageColor.YELLOW: 0.85,
    TriageColor.GREEN: 0.88,
    TriageColor.BLUE: 0.92,
}


# ---------------------------------------------------------------------------
# Mock classify
# ---------------------------------------------------------------------------


def _keyword_color(text: str) -> TriageColor:
    """Match chief complaint text against keyword lists."""
    lower = text.lower()

    for kw in _HIGH_ACUITY_KEYWORDS:
        if kw in lower:
            return TriageColor.RED

    for kw in _BLUE_KEYWORDS:
        if kw in lower:
            return TriageColor.BLUE

    for kw in _ORANGE_KEYWORDS:
        if kw in lower:
            return TriageColor.ORANGE

    for kw in _YELLOW_KEYWORDS:
        if kw in lower:
            return TriageColor.YELLOW

    for kw in _GREEN_KEYWORDS:
        if kw in lower:
            return TriageColor.GREEN

    return TriageColor.YELLOW  # safe default


def _check_vital_red_flags(
    vital_signs: Optional[VitalSigns],
) -> Optional[TriageColor]:
    """Upgrade acuity if vital signs show red flags."""
    if vital_signs is None:
        return None

    vs = vital_signs

    # SpO2 < 92% -> at least ORANGE
    if vs.spo2 is not None and vs.spo2 < 92.0:
        return TriageColor.ORANGE

    # Systolic BP < 90 or > 200 -> ORANGE
    if vs.blood_pressure:
        try:
            systolic = int(vs.blood_pressure.split("/")[0])
            if systolic < 90 or systolic > 200:
                return TriageColor.ORANGE
        except (ValueError, IndexError):
            pass

    # HR > 120 or < 50 -> at least YELLOW
    if vs.heart_rate is not None and (vs.heart_rate > 120 or vs.heart_rate < 50):
        return TriageColor.YELLOW

    # RR > 30 or < 10 -> at least YELLOW
    if vs.respiratory_rate is not None and (
        vs.respiratory_rate > 30 or vs.respiratory_rate < 10
    ):
        return TriageColor.YELLOW

    # Temp > 40 or < 35 -> at least YELLOW
    if vs.temperature is not None and (vs.temperature > 40.0 or vs.temperature < 35.0):
        return TriageColor.YELLOW

    # Glucose < 60 or > 400 -> at least YELLOW
    if vs.glucose is not None and (vs.glucose < 60.0 or vs.glucose > 400.0):
        return TriageColor.YELLOW

    return None


_COLOR_PRIORITY = {
    TriageColor.RED: 0,
    TriageColor.ORANGE: 1,
    TriageColor.YELLOW: 2,
    TriageColor.GREEN: 3,
    TriageColor.BLUE: 4,
}


def _more_urgent(a: TriageColor, b: TriageColor) -> TriageColor:
    """Return the more urgent of two colors."""
    return a if _COLOR_PRIORITY[a] <= _COLOR_PRIORITY[b] else b


def mock_classify(patient: PatientData) -> TriageResult:
    """Classify a patient using keyword heuristics (no model call).

    Args:
        patient: Structured patient data.

    Returns:
        A realistic TriageResult based on keyword matching and vital signs.
    """
    color = _keyword_color(patient.chief_complaint)

    # Pain scale override
    if patient.pain_scale is not None:
        if patient.pain_scale >= 8:
            color = _more_urgent(TriageColor.ORANGE, color)
        elif patient.pain_scale >= 4:
            color = _more_urgent(TriageColor.YELLOW, color)

    # Vital sign red-flag upgrade
    vital_upgrade = _check_vital_red_flags(patient.vital_signs)
    if vital_upgrade is not None:
        color = _more_urgent(vital_upgrade, color)

    level_name, max_wait = TRIAGE_LEVELS[color]

    return TriageResult(
        triage_color=color,
        triage_level=level_name,
        max_wait_minutes=max_wait,
        reasoning=_REASONING[color],
        key_discriminators=_DISCRIMINATORS[color],
        confidence=_CONFIDENCE[color],
        raw_model_response="[mock response — nenhuma chamada ao modelo realizada]",
        parse_failed=False,
    )


# ---------------------------------------------------------------------------
# Mock image analysis
# ---------------------------------------------------------------------------

_IMAGE_FINDINGS: dict[str, str] = {
    "image/jpeg": (
        "Radiografia de tórax: campos pulmonares limpos, sem consolidações "
        "ou derrames. Silhueta cardíaca dentro dos limites da normalidade. "
        "Sem achados agudos."
    ),
    "image/png": (
        "Imagem analisada: lesão cutânea superficial observada. "
        "Bordas regulares, sem sinais de infecção. "
        "Recomendada avaliação presencial para confirmação."
    ),
}

_DEFAULT_FINDING = (
    "Imagem recebida e analisada. Sem achados críticos identificados "
    "na avaliação preliminar. Avaliação clínica presencial recomendada."
)


def mock_analyze_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> str:
    """Return a synthetic image analysis finding.

    Args:
        image_bytes: Raw image bytes (not used in mock).
        mime_type: MIME type of the image.

    Returns:
        A Portuguese radiology-style finding string.
    """
    return _IMAGE_FINDINGS.get(mime_type, _DEFAULT_FINDING)


# ---------------------------------------------------------------------------
# Mock FHIR bundle
# ---------------------------------------------------------------------------


def build_mock_fhir_bundle(
    patient_name: str,
    patient_age: Optional[int],
    patient_sex: Optional[str],
    patient_data: PatientData,
    triage_result: TriageResult,
) -> dict:
    """Build a realistic FHIR R4 Bundle with mock resources.

    Args:
        patient_name: Display name for the patient resource.
        patient_age: Patient age in years.
        patient_sex: "M" or "F".
        patient_data: Structured patient data.
        triage_result: Triage classification result.

    Returns:
        A dict matching FHIR R4 Bundle structure.
    """
    now = datetime.now(timezone.utc).isoformat()
    patient_id = str(uuid.uuid4())
    encounter_id = str(uuid.uuid4())
    observation_id = str(uuid.uuid4())
    condition_id = str(uuid.uuid4())

    gender = "unknown"
    if patient_sex:
        gender = "male" if patient_sex.upper() == "M" else "female"

    birth_year = ""
    if patient_age is not None:
        birth_year = str(datetime.now(timezone.utc).year - patient_age)

    level_name, max_wait = TRIAGE_LEVELS[triage_result.triage_color]

    # Vital sign observations
    vital_observations: list[dict] = []
    if patient_data.vital_signs:
        vs = patient_data.vital_signs
        if vs.heart_rate is not None:
            vital_observations.append(
                {
                    "code": {"text": "Heart rate"},
                    "valueQuantity": {
                        "value": vs.heart_rate,
                        "unit": "bpm",
                    },
                }
            )
        if vs.blood_pressure:
            vital_observations.append(
                {
                    "code": {"text": "Blood pressure"},
                    "valueString": f"{vs.blood_pressure} mmHg",
                }
            )
        if vs.spo2 is not None:
            vital_observations.append(
                {
                    "code": {"text": "SpO2"},
                    "valueQuantity": {"value": vs.spo2, "unit": "%"},
                }
            )
        if vs.temperature is not None:
            vital_observations.append(
                {
                    "code": {"text": "Temperature"},
                    "valueQuantity": {"value": vs.temperature, "unit": "°C"},
                }
            )

    return {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "timestamp": now,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "name": [{"use": "official", "text": patient_name}],
                    "gender": gender,
                    "birthDate": birth_year,
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": encounter_id,
                    "status": "in-progress",
                    "class": {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "EMER",
                        "display": "emergency",
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "priority": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/v3/ActPriority",
                                "code": triage_result.triage_color.value,
                                "display": level_name,
                            }
                        ]
                    },
                    "reasonCode": [{"text": patient_data.chief_complaint}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": observation_id,
                    "status": "final",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "56838-1",
                                "display": "Manchester Triage Category",
                            }
                        ],
                        "text": "Classificação de Risco Manchester",
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{encounter_id}"},
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "code": triage_result.triage_color.value,
                                "display": level_name,
                            }
                        ],
                        "text": (
                            f"{triage_result.triage_color.value} — {level_name} "
                            f"(máx {max_wait} min)"
                        ),
                    },
                    "component": [
                        {
                            "code": {"text": "Confidence"},
                            "valueQuantity": {
                                "value": triage_result.confidence,
                                "unit": "ratio",
                            },
                        },
                        {
                            "code": {"text": "Reasoning"},
                            "valueString": triage_result.reasoning,
                        },
                        *vital_observations,
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": condition_id,
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": (
                                    "http://terminology.hl7.org/CodeSystem"
                                    "/condition-clinical"
                                ),
                                "code": "active",
                            }
                        ]
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{encounter_id}"},
                    "code": {"text": patient_data.chief_complaint},
                }
            },
        ],
    }


# ---------------------------------------------------------------------------
# Sample synthetic cases for the demo sidebar
# ---------------------------------------------------------------------------

SAMPLE_CASES: list[dict] = [
    {
        "name": "Maria Silva",
        "age": 55,
        "sex": "F",
        "chief_complaint": "Dor no peito irradiando para braço esquerdo",
        "symptoms": "diaphorese, náusea, falta de ar",
        "onset": "30 minutos atrás",
        "pain_scale": 9,
        "heart_rate": 110,
        "blood_pressure": "180/100",
        "respiratory_rate": 22,
        "temperature": 0.0,
        "spo2": 94.0,
        "glucose": 0.0,
        "history": "hipertensão, diabetes tipo 2",
        "medications": "losartana, metformina",
        "allergies": "",
        "notes": "",
    },
    {
        "name": "João Santos",
        "age": 8,
        "sex": "M",
        "chief_complaint": "Febre alta e vômitos há 2 dias",
        "symptoms": "febre, vômito, letargia",
        "onset": "2 dias atrás",
        "pain_scale": 4,
        "heart_rate": 130,
        "blood_pressure": "",
        "respiratory_rate": 28,
        "temperature": 39.2,
        "spo2": 0.0,
        "glucose": 0.0,
        "history": "",
        "medications": "",
        "allergies": "",
        "notes": "",
    },
    {
        "name": "Ana Oliveira",
        "age": 30,
        "sex": "F",
        "chief_complaint": "Torci o tornozelo jogando futebol",
        "symptoms": "inchaço no tornozelo, dor leve",
        "onset": "1 hora atrás",
        "pain_scale": 3,
        "heart_rate": 78,
        "blood_pressure": "120/80",
        "respiratory_rate": 0,
        "temperature": 36.5,
        "spo2": 0.0,
        "glucose": 0.0,
        "history": "",
        "medications": "",
        "allergies": "",
        "notes": "",
    },
    {
        "name": "Carlos Ferreira",
        "age": 72,
        "sex": "M",
        "chief_complaint": "Preciso renovar receita de losartana",
        "symptoms": "",
        "onset": "",
        "pain_scale": 0,
        "heart_rate": 72,
        "blood_pressure": "130/85",
        "respiratory_rate": 0,
        "temperature": 0.0,
        "spo2": 0.0,
        "glucose": 0.0,
        "history": "hipertensão",
        "medications": "losartana",
        "allergies": "",
        "notes": "",
    },
    {
        "name": "Lúcia Pereira",
        "age": 45,
        "sex": "F",
        "chief_complaint": "Falta de ar súbita, chiado no peito",
        "symptoms": "chiado, dispneia, aperto no peito",
        "onset": "20 minutos atrás",
        "pain_scale": 6,
        "heart_rate": 105,
        "blood_pressure": "140/90",
        "respiratory_rate": 32,
        "temperature": 0.0,
        "spo2": 88.0,
        "glucose": 0.0,
        "history": "asma",
        "medications": "salbutamol",
        "allergies": "",
        "notes": "",
    },
]
