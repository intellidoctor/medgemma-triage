# MedGemma Triage Assistant

Agentic clinical intake & triage assistant for Brazilian SUS emergency rooms. Built for the MedGemma Impact Challenge (Kaggle). An AI assistant for triage nurses — it runs alongside them, never replaces them.

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.11 |
| Package manager | pip + venv |
| Agent orchestration | LangGraph |
| Models | MedGemma 4B (images) + MedGemma 27B Text (reasoning) via Vertex AI |
| FHIR output | `fhir.resources` |
| UI | Streamlit |
| Linting | ruff |
| Formatting | black |
| Tests | pytest |

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
    └── app.py             # Streamlit triage dashboard
tests/
├── test_agents/
├── test_pipeline/
└── test_fhir/
data/
└── sample_cases/          # Test medical cases (synthetic only)
```

## Coding Conventions

- Python 3.11, type hints on all function signatures
- Format with `black`, lint with `ruff`
- One agent per file in `src/agents/`
- All model calls go through `src/models/medgemma.py` — never call models directly from agents
- Use `logging` module, not `print()` — except in Streamlit UI
- Docstrings on public functions only (Google style)

## Branch Discipline

- Never push directly to `main`
- One branch per issue: `feat/issue-number-short-description`
- All changes via PR, at least 1 review before merge
- Each agent session works on its own branch

## Environment Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# UI
streamlit run src/ui/app.py

# Tests
pytest tests/

# Lint + format
ruff check src/
black src/
```

## Rules

- No patient data in the repo — only synthetic test cases
- No API keys or credentials in code — use environment variables
- Keep this file under 2500 tokens — prune session notes, keep rules
- When an agent makes a mistake, add a rule here
