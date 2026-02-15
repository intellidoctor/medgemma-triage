# Multi-Person, Multi-Agent Team Coordination

## Two-Layer Architecture

```
OUTER LOOP — GitHub Projects (team coordination)
│
│  Humans assign Issues, track progress on kanban board
│  Agents read/update the board via GitHub MCP Server
│  PRs are the integration point
│
└── INNER LOOP — Each person's local agent orchestration
    │
    │  Git worktrees for isolation
    │  Claude Code / Codex / Copilot — whatever each person prefers
    │  Agent Teams or Vibe Kanban for within-person parallelism
```

---

## Practice Project: MedGemma Impact Challenge (Agentic Workflow Prize)

Use the multi-agent team workflow to compete in a real Kaggle hackathon with $100K in prizes. The **Agentic Workflow Prize ($10,000)** maps directly to the skills this project is about.

### Competition Overview

| Detail                     | Value                                                                                                                |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Host**                   | Google Research on Kaggle                                                                                            |
| **Prize pool**             | $100,000 total                                                                                                       |
| **Agentic Workflow Prize** | $10,000                                                                                                              |
| **Deadline**               | February 24, 2026                                                                                                    |
| **Results**                | March 17–24, 2026                                                                                                    |
| **Teams**                  | ~1,700 active                                                                                                        |
| **URL**                    | [kaggle.com/competitions/med-gemma-impact-challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge) |

### What You Submit

1. **A working demo application** using at least one HAI-DEF model
2. **A writeup** following their template (problem, solution, technical details)
3. **Reproducible code** (public repo)
4. **A video** (3 minutes or less)

### Evaluation Criteria

1. Effective use of HAI-DEF models
2. Importance of the problem
3. Potential real-world impact
4. Technical feasibility
5. Execution and communication quality

### Project Idea: Agentic Clinical Intake & Triage Assistant

**Target:** Agentic Workflow Prize ($10,000)

**Who this is for:** The **triage nurse** — the first clinical contact when a patient arrives at the ER. The tool does not replace the nurse. It runs alongside them as an AI-powered assistant, while the nurse retains full authority to approve, override, or adjust every decision.

**Problem:** In Brazilian public health (SUS), patients wait hours in emergency rooms. Triage nurses are overwhelmed — they must simultaneously:

1. Interview the patient (complaint, symptoms, history)
2. Check vitals
3. Review any available images (X-ray, skin lesion)
4. Classify urgency using the Manchester Protocol (Red/Orange/Yellow/Green/Blue)
5. Document everything manually
6. Hand off to the physician

**Solution:** An agentic workflow where MedGemma orchestrates the clinical intake process, giving the triage nurse a pre-filled assessment to review instead of building one from scratch.

```
Patient arrives at ER
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Agent 1: INTAKE INTERVIEWER (MedGemma 27B Text)    │
│  - Structured patient interview via voice/text      │
│  - Extracts chief complaint, symptoms, duration     │
│  - Medical history, allergies, medications          │
│  - Outputs structured FHIR-compatible record        │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Agent 2:     │ │ Agent 3:     │ │ Agent 4:         │
│ IMAGE READER │ │ TRIAGE       │ │ DOCUMENTATION    │
│ MedGemma 4B  │ │ CLASSIFIER   │ │ GENERATOR        │
│ multimodal   │ │ MedGemma 27B │ │ MedGemma 27B     │
│              │ │ text         │ │ text             │
│ If patient   │ │              │ │                  │
│ has images → │ │ Manchester   │ │ Generates:       │
│ analyze &    │ │ Protocol     │ │ - FHIR bundle    │
│ report       │ │ color        │ │ - Handoff note   │
└──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       └────────────────┼──────────────────┘
                        ▼
              ┌──────────────────┐
              │ TRIAGE DASHBOARD │
              │ Nurse reviews,   │
              │ approves or      │
              │ overrides        │
              └──────────────────┘
```

---

## Task Guide for Team Members

> **Board:** [github.com/orgs/intellidoctor/projects/7](https://github.com/orgs/intellidoctor/projects/7)
> **Repo:** [github.com/intellidoctor/medgemma-triage](https://github.com/intellidoctor/medgemma-triage)
> **Slack:** `#medgemma-triage`

Each task below maps to a GitHub Issue. Pick your assigned issue, create a branch (`feat/<issue-number>-short-name`), and submit a PR when done. Full acceptance criteria are in each issue — this guide gives you the big picture.

### Team Quick Reference

| Person | Slack | GitHub | Issues | Focus |
|--------|-------|--------|--------|-------|
| **Roberto** | @rshimizubr | @robertoshimizu | #1, #5, #8, #9 | Models + submission |
| **Thiago** | @thiagoreisporto | @Thiago-Reis-Porto | #2, #4, #6, #10 | Agents + integration |
| **Roberta** | @robdallagogar | @rferrazd | #3, #7 | UI + pipeline |

### Dependency Graph (4 days)

```
Day 1 (Feb 15):
  #1 MedGemma setup       [Roberto]     ← foundation, no deps
  #2 Triage classifier    [Thiago]      ← start with stubs, no deps
  #3 Dashboard UI         [Roberta]     ← mock data, no deps

Day 1-2 (Feb 15-16):
  #4 Intake agent          [Thiago]      ← depends on #1
  #5 Image agent           [Roberto]     ← depends on #1
  #6 FHIR output           [Thiago]      ← depends on #2

Day 2 (Feb 16):
  #7 Agent pipeline        [Roberta]     ← depends on #4, #5, #2, #6

Day 3 (Feb 17):
  #10 Integration          [Thiago]      ← depends on #7, #3
  #11 Polish               [All]         ← depends on #10
  #8 Writeup               [Roberto]     ← depends on #10

Day 4 (Feb 18):
  #9 Video                 [Roberto]     ← depends on #10
  Final submission
```

---

### #1 — MedGemma Model Setup on Vertex AI `[Roberto]` `P0` `Day 1`

**What:** Create `src/models/medgemma.py` — the single entry point for all model inference. No agent should call models directly.

**Goal:** Team members can `from src.models.medgemma import ...` and get predictions without worrying about Vertex AI auth, model selection, or prompt formatting.

**What to deliver:**
- Load MedGemma 4B (multimodal) and MedGemma 27B Text via Vertex AI
- Provide clean functions: `analyze_image(image, prompt)` and `generate_text(prompt, system_prompt)`
- Handle auth via `GOOGLE_APPLICATION_CREDENTIALS` or Application Default Credentials
- Include a test script that proves both models respond correctly

**Suggestions:**
- Use the Vertex AI Python SDK (`google-cloud-aiplatform`) or Gemini API with the MedGemma endpoint
- Check [MedGemma on Vertex AI docs](https://developers.google.com/health-ai-developer-foundations/medgemma) for endpoint setup
- Keep the interface simple — other team members will build on top of this

---

### #2 — Triage Classifier Agent (Manchester Protocol) `[Thiago]` `P0` `Day 1`

**What:** Create `src/agents/triage.py` — classifies a patient into a Manchester Protocol urgency level based on structured clinical data.

**Goal:** Given patient symptoms, vitals, and chief complaint, output one of: Red (Immediate), Orange (Very Urgent), Yellow (Urgent), Green (Standard), Blue (Non-Urgent) — with clinical reasoning.

**What to deliver:**
- Takes structured patient data (complaint, vitals, symptoms, duration)
- Returns triage color + confidence + reasoning explanation
- Uses Manchester Protocol decision trees (flowcharts by discriminator)
- Prompt engineering to make MedGemma follow the protocol accurately

**Suggestions:**
- Start with a stub that returns mock classifications — don't block on #1
- The Manchester Protocol has ~52 flowcharts organized by chief complaint. Focus on the top 10 most common ER presentations
- Include discriminators: life threat → pain severity → acuity → time of onset
- Test with synthetic cases covering each color level

---

### #3 — Dashboard UI with Mock Data (Streamlit) `[Roberta]` `P0` `Day 1`

**What:** Create `src/ui/app.py` — a Streamlit dashboard that demonstrates the full triage workflow.

**Goal:** A nurse opens the dashboard, enters patient info, sees the AI's triage suggestion, and can approve/override. Demo-ready from day 1 with mock data.

**What to deliver:**
- Patient intake form: name, age, gender, chief complaint, vitals (HR, BP, SpO2, temp), symptom duration
- Image upload area (for skin photos, X-rays — even if analysis is mocked initially)
- Triage result display: color-coded badge (Red/Orange/Yellow/Green/Blue) with reasoning
- Patient queue view: list of triaged patients sorted by urgency
- FHIR output viewer: collapsible JSON section showing the structured output

**Suggestions:**
- Use `st.columns()` for layout, `st.status()` for agent progress feedback
- Color-code: Red = `#E74C3C`, Orange = `#E67E22`, Yellow = `#F1C40F`, Green = `#27AE60`, Blue = `#3498DB`
- Mock data: 3-5 realistic cases (chest pain, fracture, mild fever, etc.)
- Design the UI so it's easy to swap mock data for real agent calls later

---

### #4 — Intake Interviewer Agent `[Thiago]` `P0` `Day 1-2`

**What:** Create `src/agents/intake.py` — conducts a structured clinical interview and outputs a standardized patient record.

**Goal:** Simulate what a triage nurse does in the first 2 minutes: gather chief complaint, symptom details, history, allergies, and medications — then produce a structured record that downstream agents can consume.

**What to deliver:**
- Conversational agent that asks clinically relevant follow-up questions
- Extracts: chief complaint, onset/duration, severity (0-10), associated symptoms, PMH, allergies, medications
- Outputs structured dict/JSON compatible with FHIR Patient + Encounter resources

**Suggestions:**
- Depends on #1 for real model calls, but can develop with mock responses
- Follow clinical interview structure: CC → HPI → ROS → PMH → Medications → Allergies → Social History
- Keep the output schema consistent — downstream agents (#2 triage, #6 FHIR) will parse it

---

### #5 — Medical Image Analysis Agent `[Roberto]` `P1` `Day 1-2`

**What:** Create `src/agents/image_reader.py` — analyzes medical images using MedGemma 4B multimodal.

**Goal:** When a patient brings an X-ray, skin photo, or other medical image, this agent provides a structured analysis that feeds into the triage decision.

**What to deliver:**
- Accepts image file (JPEG/PNG) + optional clinical context
- Returns structured findings: modality detected, key observations, abnormalities
- Handles common types: chest X-ray, skin lesion photos, wound photos, extremity X-rays
- Includes appropriate disclaimers ("AI-assisted analysis, requires clinical validation")

**Suggestions:**
- Use MedGemma 4B (multimodal) via the interface from #1
- For demo, include 2-3 sample images from public datasets (NIH ChestX-ray14, ISIC skin lesion)
- Consider CXR Foundation model as a complement for chest X-rays

---

### #6 — FHIR Output Generation `[Thiago]` `P1` `Day 2`

**What:** Create `src/fhir/builder.py` — converts the triage pipeline output into valid FHIR R4 resources.

**Goal:** Every triage encounter produces a standards-compliant FHIR Bundle that could be sent to a hospital EHR system.

**What to deliver:**
- Generate FHIR R4 resources: Patient, Encounter, Observation (vitals), Condition (chief complaint), DiagnosticReport (triage result)
- Bundle into a FHIR Bundle (type: document or transaction)
- Validate using `fhir.resources` library
- Include triage classification as a coded Observation

**Suggestions:**
- Use `fhir.resources` Python library (already in tech stack)
- FHIR resources are just structured JSON — don't overthink it
- Key references: [FHIR R4 Patient](https://www.hl7.org/fhir/patient.html), [FHIR Encounter](https://www.hl7.org/fhir/encounter.html)

---

### #7 — LangGraph Agent Pipeline (Orchestrator) `[Roberta]` `P0` `Day 2`

**What:** Create `src/pipeline/orchestrator.py` — the LangGraph workflow that connects all agents into a single pipeline.

**Goal:** One function call that takes raw patient input and produces a complete triage result with FHIR output. This is the "agentic workflow" the judges evaluate.

**What to deliver:**
- LangGraph StateGraph with nodes: intake → image_reader → triage → documentation
- State schema defining data that flows between agents
- Conditional routing: skip image analysis if no image provided
- Error handling: if one agent fails, the pipeline degrades gracefully

**Suggestions:**
- Use LangGraph's `StateGraph` with typed state (TypedDict)
- Start with stubs for agents that aren't ready yet
- Check [LangGraph docs](https://langchain-ai.github.io/langgraph/) for conditional edges and parallel execution

---

### #8 — Kaggle Writeup `[Roberto]` `P0` `Day 3-4`

**What:** Write the Kaggle competition submission document following their template.

**Goal:** A compelling writeup that explains the problem, solution, and technical approach. This is 50%+ of the judging score.

**What to cover:**
- Problem statement: ER triage bottleneck in Brazilian SUS (150M+ users)
- Solution: agentic workflow with MedGemma at each stage
- Technical architecture: the 4-agent pipeline diagram
- Human-in-the-loop design: nurse always has final authority
- FHIR interoperability: output integrates with existing hospital systems
- Privacy: MedGemma runs locally, no patient data leaves the facility

---

### #9 — Demo Video (3 min) `[Roberto]` `P0` `Day 3-4`

**What:** Record a 3-minute video demonstrating the application.

**Suggested flow:**
1. (0:00-0:30) Problem intro — ER waiting room, overwhelmed nurses
2. (0:30-1:30) Live demo — patient enters data, agent pipeline runs, triage result appears
3. (1:30-2:15) Technical walkthrough — agent orchestration, FHIR output
4. (2:15-2:45) Image analysis demo — upload an X-ray, see findings
5. (2:45-3:00) Impact statement — faster triage for 150M Brazilians

---

### #10 — End-to-End Integration `[Thiago]` `P0` `Day 3`

**What:** Connect the real agents (#4, #5, #2) through the pipeline (#7) to the UI (#3). Replace all mocks with real model calls.

**Goal:** A working demo where you enter patient data in the UI, agents process it through MedGemma, and you see real triage results.

**What to deliver:**
- UI calls the orchestrator pipeline with real patient data
- All agents use MedGemma via `src/models/medgemma.py`
- FHIR output generated and displayed in the UI
- At least 3 synthetic test cases work end-to-end
- Error handling for model timeouts or failures

---

### #11 — Final Polish and Testing `[All]` `P1` `Day 3-4`

**What:** Bug fixes, edge cases, and demo polish. All team members contribute.

**What to check:**
- All synthetic test cases pass end-to-end
- UI handles errors gracefully (model timeout, invalid input)
- Code passes `ruff check` and `black` formatting
- README has clear setup instructions
- No credentials, API keys, or real patient data in the repo
- Demo flow is smooth for the video recording

---

## Workflow Reminders

1. **Branch naming:** `feat/<issue-number>-short-name` (e.g., `feat/1-medgemma-setup`)
2. **One PR per issue.** Link the issue in the PR description: `Closes #1`
3. **Commit often.** Git is your memory, not the chat.
4. **Ask in Slack** if blocked. Don't spin for hours.
5. **Use worktrees** for parallel work: `git worktree add ../worktree-issue-1 origin/main`

---

## Tech Stack

| Component     | Tool                                                               |
| ------------- | ------------------------------------------------------------------ |
| Language      | Python 3.12                                                        |
| Models        | MedGemma 4B (images) + MedGemma 27B Text (reasoning) via Vertex AI |
| Orchestration | LangGraph                                                          |
| FHIR output   | `fhir.resources` Python library                                    |
| UI            | Streamlit                                                          |
| Linting       | ruff                                                               |
| Formatting    | black                                                              |
| Tests         | pytest                                                             |

## Project Structure

```
src/
├── agents/
│   ├── intake.py          # Patient interview agent (#4)
│   ├── image_reader.py    # Medical image analysis agent (#5)
│   ├── triage.py          # Manchester Protocol classifier (#2)
│   └── documentation.py   # Report generator (#6)
├── pipeline/
│   └── orchestrator.py    # LangGraph workflow (#7)
├── models/
│   └── medgemma.py        # Model loading and inference (#1)
├── fhir/
│   └── builder.py         # FHIR resource construction (#6)
└── ui/
    └── app.py             # Streamlit triage dashboard (#3)
tests/
├── test_agents/
├── test_pipeline/
└── test_fhir/
data/
└── sample_cases/          # Test medical cases (synthetic only)
```

## Environment Setup

```bash
python3.12 -m venv .venv
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

## References

- [MedGemma docs](https://developers.google.com/health-ai-developer-foundations/medgemma)
- [MedGemma model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)
- [HAI-DEF on Hugging Face](https://huggingface.co/collections/google/health-ai-developer-foundations-hai-def)
- [LangGraph docs](https://langchain-ai.github.io/langgraph/)
- [How to Build Agentic Workflows with MedGemma 1.5 (YouTube)](https://www.youtube.com/watch?v=1FR2wOuRpY4)
- [Kaggle competition page](https://www.kaggle.com/competitions/med-gemma-impact-challenge)
