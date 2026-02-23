# MedGemma Triage Assistant

An agentic clinical intake and triage assistant for Brazilian SUS emergency rooms, built for the [MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge) on Kaggle.

An AI assistant for triage nurses -- it runs alongside them, never replaces them. The nurse retains full authority to approve, override, or adjust every decision.

## The Problem

In Brazilian public health (SUS), patients wait hours in emergency rooms. Triage nurses must simultaneously interview patients, check vitals, review images, classify urgency using the Manchester Protocol, and document everything manually. Every minute spent on paperwork is a minute not spent on the next patient.

## The Solution

An agentic workflow where MedGemma orchestrates the clinical intake process, giving the triage nurse a pre-filled assessment to review instead of building one from scratch.

```
Patient arrives at ER
        |
        v
+-----------------------------------------------+
|  INTAKE INTERVIEWER (MedGemma 27B Text)        |
|  Structured interview: complaint, symptoms,    |
|  history, vitals -> structured patient record   |
+---------------------+-------------------------+
                      |
        +-------------+-------------+
        v             v             v
  IMAGE READER   TRIAGE         DOCUMENTATION
  MedGemma 4B    CLASSIFIER     GENERATOR
  (if images     MedGemma 27B   MedGemma 27B
   provided)     Manchester     FHIR R4 Bundle
                 Protocol       + handoff note
        +-------------+-------------+
                      |
                      v
            TRIAGE DASHBOARD
            Nurse reviews suggested
            urgency, approves or
            overrides
```

## Tech Stack

| Component           | Choice                                                             |
| ------------------- | ------------------------------------------------------------------ |
| Language            | Python 3.12                                                        |
| Agent orchestration | LangGraph                                                          |
| Models              | MedGemma 4B (images) + MedGemma 27B Text (reasoning) via Vertex AI |
| FHIR output         | `fhir.resources` (R4)                                              |
| UI                  | Streamlit                                                          |
| Tests               | pytest (201 unit tests)                                            |

## Project Structure

```
src/
├── agents/
│   ├── intake.py          # Patient interview agent
│   ├── image_reader.py    # Medical image analysis agent
│   ├── triage.py          # Manchester Protocol classifier
│   └── documentation.py   # FHIR + report generator
├── pipeline/
│   └── orchestrator.py    # LangGraph workflow connecting agents
├── models/
│   └── medgemma.py        # Model loading and inference
├── fhir/
│   └── builder.py         # FHIR resource construction
└── ui/
    ├── app.py             # Streamlit triage dashboard
    ├── strings.py         # EN/PT i18n strings
    └── mock_services.py   # Mock classification for demo mode
data/
└── sample_cases/          # Synthetic test cases (EN + PT)
tests/
├── test_agents/
├── test_pipeline/
└── test_fhir/
```

## Setup

### Prerequisites

- Python 3.11+
- Google Cloud credentials with access to Vertex AI MedGemma endpoints

### Installation

```bash
git clone https://github.com/intellidoctor/medgemma-triage.git
cd medgemma-triage

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Copy the environment template and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:
- `GOOGLE_APPLICATION_CREDENTIALS_BASE64` -- Base64-encoded GCP service account key
- `MEDGEMMA_27B_BASE_URL` -- Vertex AI endpoint for MedGemma 27B Text
- `MEDGEMMA_4B_BASE_URL` -- Vertex AI endpoint for MedGemma 4B multimodal

## Running

```bash
# Start the triage dashboard
streamlit run src/ui/app.py

# Run tests (no credentials needed)
pytest tests/ -m "not integration"

# Run integration tests (requires Vertex AI credentials)
pytest tests/ -m integration

# Lint and format
ruff check src/
black src/
```

## Features

- **Bilingual UI** -- Toggle between English and Portuguese (Brasileiro) in the sidebar
- **Manchester Protocol triage** -- AI-assisted classification into Red/Orange/Yellow/Green/Blue urgency levels
- **Real MedGemma integration** -- Test cases trigger actual MedGemma 27B inference via Vertex AI
- **FHIR R4 output** -- Every triage encounter produces a standards-compliant FHIR Bundle (Patient, Encounter, Observations, Condition, RiskAssessment)
- **Synthetic test cases** -- 6 cases (3 EN, 3 PT) covering chest pain, pediatric fever, and ankle sprain
- **Human-in-the-loop** -- Nurse always reviews and can override the AI suggestion

## Test Cases

| Case | Language | Scenario | Expected Severity |
|------|----------|----------|-------------------|
| Chest pain with cardiac risk factors | EN / PT | 62yo male, crushing chest pain, diaphoresis | Red/Orange |
| Pediatric fever with respiratory distress | EN / PT | 4yo female, high fever, tachypnea, SpO2 93% | Orange/Yellow |
| Ankle sprain | EN / PT | 28yo male, twisted ankle, mild swelling | Green |

## Architecture Highlights

- **All model calls go through `src/models/medgemma.py`** -- agents never call models directly
- **LangGraph orchestrator** connects agents with conditional routing (skips image analysis if no image)
- **FHIR builder** uses `fhir.resources` for validated R4 resource construction
- **Mock library in `tests/conftest.py`** patches model calls automatically for unit tests

## Disclaimer

This is a research prototype for a hackathon submission. It uses only synthetic patient data. Not intended for clinical use without proper validation and regulatory approval.

## License

This project was built for the [MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge) by [Intellidoctor](https://github.com/intellidoctor).
