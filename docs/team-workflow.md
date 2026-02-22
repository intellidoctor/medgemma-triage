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

## Step 1: Shared Foundation

Every team member needs these three things aligned:

**a) A shared Git repo** — the persistent memory across all agents and humans. No exceptions.

**b) A well-maintained `CLAUDE.md`** — institutional knowledge. Keep it small (~2.5k tokens). Every team member's agents read it. Contents:

- Project architecture overview
- Coding conventions
- What NOT to do (add rules as mistakes happen)

**c) Branch discipline** — each person (and each agent) works on its own branch. Never two agents on the same branch.

---

## Step 2: GitHub Projects as the Outer Loop

GitHub Projects V2 is the team coordination layer. Free, built into GitHub, and — critically — **accessible to agents via MCP**.

### Board Setup

| Column          | Purpose                                   |
| --------------- | ----------------------------------------- |
| **Backlog**     | Ideas and future work                     |
| **To Do**       | Ready for this sprint/iteration           |
| **In Progress** | Someone (or their agent) is working on it |
| **In Review**   | PR opened, awaiting review                |
| **Done**        | Merged                                    |

### Custom Fields

| Field     | Type                     | Purpose                          |
| --------- | ------------------------ | -------------------------------- |
| Priority  | Single select (P0/P1/P2) | What to work on first            |
| Assignee  | Person                   | Who owns this (human, not agent) |
| Iteration | Iteration field          | Sprint/week grouping             |
| Estimate  | Number                   | Story points or T-shirt size     |

### Built-in Automations (Zero Config)

| Trigger                    | Action                       |
| -------------------------- | ---------------------------- |
| Issue added to project     | Moves to "Backlog"           |
| PR opened linking an issue | Moves issue to "In Progress" |
| PR merged                  | Moves issue to "Done"        |
| Issue closed               | Moves to "Done"              |
| Issue reopened             | Moves to "To Do"             |

---

## Step 3: GitHub MCP Server — The Bridge Between Board and Agents

The official GitHub MCP server (`github/github-mcp-server`) gives agents direct read/write access to GitHub Projects. This is the key integration that makes the outer loop work with agents.

### What Agents Can Do via MCP

| Action                    | Description                                                    |
| ------------------------- | -------------------------------------------------------------- |
| List & retrieve projects  | Agent sees the kanban board                                    |
| List items in a project   | Agent reads all cards, status, assignee, priority              |
| List fields               | Agent knows the custom fields                                  |
| Update fields on items    | Agent moves cards between columns (To Do → In Progress → Done) |
| Add issues/PRs to project | Agent puts new work on the board                               |
| Remove items from project | Agent cleans up completed work                                 |
| Create/update issues      | Agent manages work items                                       |
| Create pull requests      | Agent submits code for review                                  |

### MCP Server Configuration

The `projects` toolset is **not enabled by default**. Enable it explicitly:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>",
        "GITHUB_TOOLSETS": "repos,issues,pull_requests,projects"
      }
    }
  }
}
```

Or with the binary:

```bash
github-mcp-server --toolsets repos,issues,pull_requests,projects
```

### The Full Agent-Board Loop

```
GitHub Projects board (team kanban)
    │
    │  Issue #12: "Build auth" → assigned to Person A → status: To Do
    │
    ▼
Person A's agent (Claude Code + GitHub MCP Server)
    │
    │  1. Agent reads board via MCP → sees Issue #12 assigned to them
    │  2. Agent updates #12 status → "In Progress"
    │  3. Agent works on code in git worktree
    │  4. Agent creates PR → "Closes #12"
    │  5. Agent adds PR to the project board
    │  6. Agent updates #12 status → "In Review"
    │
    ▼
Person B reviews PR on GitHub
    │
    │  Merges → GitHub automation moves #12 → "Done"
```

### Claude Code GitHub Action (Async Agent Trigger)

For fully asynchronous work, the `claude-code-action` triggers Claude when someone writes `@claude` in an Issue or PR comment:

```yaml
on:
  issues:
    types: [opened, assigned]
  issue_comment:
    types: [created]

jobs:
  claude-pr:
    if: contains(github.event.comment.body, '@claude')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          trigger_phrase: '@claude'
          use_vertex: 'true' # works with Vertex AI credits
```

This enables:

1. Human creates Issue on GitHub Projects board
2. Writes `@claude implement this` in a comment
3. Claude Code Action fires in CI
4. Claude reads the issue, writes code, opens a Draft PR
5. PR appears on the Projects board in "In Review"

---

## Step 4: Individual Setup (Each Team Member)

Each person picks their AI tool and sets up their workspace:

| Tool                | Setup                                                                     |
| ------------------- | ------------------------------------------------------------------------- |
| **Claude Code**     | Install CLI, set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`                 |
| **Codex (OpenAI)**  | VS Code extension or CLI                                                  |
| **Both**            | VS Code 1.109+ runs them side-by-side                                     |
| **GitHub Agent HQ** | Copilot Pro+ ($39/mo) or Enterprise — runs Claude/Codex in GitHub's cloud |

### Git Worktrees (Essential)

Each agent session gets its own worktree for complete file isolation:

```bash
# Person A working on auth
git worktree add ../worktree-auth origin/main

# Person B working on API
git worktree add ../worktree-api origin/main
```

### Within-Person Parallelism

**Option A — Worktree round-robin (simplest)**

```bash
# Terminal 1: Claude on feature-X
cd ../worktree-feature-x && claude

# Terminal 2: Claude on tests
cd ../worktree-tests && claude

# Terminal 3: Codex on docs
cd ../worktree-docs && codex
```

**Option B — Agent Teams (for complex single tasks)**

```
"Create a team. One teammate reviews security,
 one writes tests, one refactors the API layer."
```

---

## Step 5: CI as the Quality Gate

Once multiple agents are producing PRs in parallel, you need automated checks before a human even looks at the code. This is what makes the parallelism safe.

### Start with tests

Agents are good at writing unit tests — ask them to. Once you have tests in the repo, set up GitHub Actions to run them on every PR:

```yaml
# .github/workflows/ci.yml
on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4  # or setup-python, etc.
      - run: npm ci && npm test
```

### Then add AI code review

The Claude Code GitHub Action (from Step 3) doubles as a CI reviewer. By the time you open a PR, both tests and an AI review have already run. You're reviewing a PR that's already been checked twice.

### The progression

1. Add unit tests to the repo (agents write them as part of each task)
2. Set up GitHub Actions to run tests on every PR
3. Add Claude Code Action for AI review on CI
4. Now when you review a PR, you're the third pair of eyes — not the first

---

## Step 6: Getting Started (Concrete Exercise)

Pick a real task your team needs done. Split it:

| Person   | Task                       | Agent                      |
| -------- | -------------------------- | -------------------------- |
| Person A | Implement feature X        | Claude Code in worktree-A  |
| Person B | Write tests for module Y   | Claude/Codex in worktree-B |
| Person C | Review & refactor module Z | Claude Code in worktree-C  |

Each person works independently. PRs merge the work. Start small — one task per person, one agent each.

---

## Key Rules

1. **Each agent session = one focused task.** Don't reuse long conversations.
2. **Commit after every completed sub-task.** Git is memory, not the chat.
3. **Start fresh sessions aggressively.** Context rot is real.
4. **`CLAUDE.md` is a living doc.** When an agent makes a mistake, add a rule.
5. **Human reviews every PR.** Agents handle 80% of work, humans handle judgment.
6. **GitHub Projects is the single source of truth** for what needs to be done and who's doing it.
7. **Learn CI/CD along the way.** This whole setup naturally pushes you to learn GitHub Actions, automated testing, and deployment pipelines. If you're adding unit tests (and you should — agents are good at writing them), you'll want CI running those tests on every PR. It's one of those skills that pays for itself quickly and fits right into the workflow.

---

## Tool Stack Summary

| Layer                           | Tool                                   | Cost                  |
| ------------------------------- | -------------------------------------- | --------------------- |
| **Team coordination**           | GitHub Projects V2                     | Free                  |
| **Agent ↔ Board bridge**        | GitHub MCP Server (`projects` toolset) | Free (open source)    |
| **Async agent triggers**        | Claude Code GitHub Action              | Free (your API costs) |
| **Human communication**         | Slack.                                 | Free tier             |
| **Agent orchestration (local)** | Claude Code CLI / Agent Teams          | VertexAI Credits      |
| **Code review (AI)**            | Claude Agent SDK on CI / Agent HQ      | VertexAI Credits      |

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

### Prize Tracks

| Track                      | Prize   | Focus                                            |
| -------------------------- | ------- | ------------------------------------------------ |
| **Main Track**             | $75,000 | Best overall projects                            |
| **Agentic Workflow Prize** | $10,000 | Reimagine complex workflows using HAI-DEF models |
| **Novel Task Prize**       | $10,000 | Best fine-tuned model for a useful new task      |
| **Edge AI Prize**          | $5,000  | Solutions running on local/edge devices          |

### Available HAI-DEF Models

| Model                            | Size            | What it does                                                    | Hugging Face                  |
| -------------------------------- | --------------- | --------------------------------------------------------------- | ----------------------------- |
| **MedGemma 1.5 4B** (multimodal) | 4B params       | Medical images + text — CXR, CT, MRI, derm, pathology, EHR      | `google/medgemma-1.5-4b-it`   |
| **MedGemma 27B** (multimodal)    | 27B params      | Same but higher accuracy, needs more compute                    | `google/medgemma-27b-it`      |
| **MedGemma 27B Text**            | 27B params      | Text-only clinical reasoning, no images                         | `google/medgemma-27b-text-it` |
| **MedASR**                       | —               | Medical speech-to-text (dictation, notes)                       | Part of HAI-DEF               |
| **CXR Foundation**               | EfficientNet-L2 | Chest X-ray embeddings — classify findings with very few labels | `google/cxr-foundation`       |
| **Derm Foundation**              | —               | Skin image embeddings for dermatology                           | `google/derm-foundation`      |
| **Path Foundation**              | —               | Histopathology image embeddings                                 | `google/path-foundation`      |
| **HEAR**                         | —               | Health audio embeddings (coughs, breaths)                       | `google/hear`                 |

### MedGemma Key Capabilities

- **Medical image interpretation** — CXR, CT, MRI, dermatology, pathology, ophthalmology
- **Medical text comprehension** — EHR summaries, discharge notes, clinical Q&A
- **Clinical reasoning** — patient triaging, decision support, differential diagnosis
- **EHR understanding** — FHIR-based records, discharge summaries, lab reports
- **Agentic orchestration** — MedGemma as a tool within an agent system, paired with web search, FHIR generators, Gemini for function calling, or local privacy-preserving parsing before sending anonymized requests to cloud models

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

All of this is done manually, which is slow and error-prone. The nurse is the bottleneck: every minute spent on paperwork is a minute not spent on the next patient.

**Solution:** An agentic workflow where MedGemma orchestrates the clinical intake process, giving the triage nurse a pre-filled assessment to review instead of building one from scratch. MedGemma handles the structured interview and documentation, analyzes any images, and suggests a triage color. The nurse reviews, approves or overrides, and moves on to the next patient — faster and with a second opinion on classification.

```
Patient arrives at ER
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Agent 1: INTAKE INTERVIEWER (MedGemma 27B Text)    │
│                                                     │
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
│              │ │ CLASSIFIER   │ │ GENERATOR        │
│ MedGemma 4B  │ │ MedGemma 27B │ │ MedGemma 27B     │
│ multimodal   │ │ text         │ │ text             │
│              │ │              │ │                  │
│ If patient   │ │ Assigns      │ │ Generates:       │
│ has images   │ │ Manchester   │ │ - Triage form    │
│ (X-ray, skin │ │ Protocol     │ │ - FHIR bundle    │
│ photo) →     │ │ color:       │ │ - Handoff note   │
│ analyze &    │ │ Red/Orange/  │ │   for physician  │
│ report       │ │ Yellow/Green │ │ - Patient summary│
└──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       │                │                  │
       └────────────────┼──────────────────┘
                        ▼
              ┌──────────────────┐
              │ TRIAGE DASHBOARD │
              │                  │
              │ Nurse reviews:   │
              │ - Suggested      │
              │   urgency color  │
              │ - Patient summary│
              │ - Key findings   │
              │ - Approves or    │
              │   overrides      │
              └──────────────────┘
```

**Why this wins the Agentic Workflow Prize:**

- Uses multiple HAI-DEF models in a coordinated pipeline (not just one model)
- Reimagines a real, broken clinical workflow (ER triage)
- Human-in-the-loop — nurse always has final say
- Privacy-first — MedGemma runs locally, patient data never leaves the facility
- FHIR output — integrates with existing hospital systems
- Addresses underserved populations (SUS serves 150M+ Brazilians)

### Task Split for 3 People

| Person       | Domain                | What they build                                                                                                                |
| ------------ | --------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Person A** | MedGemma integration  | Model loading, inference pipeline, prompt engineering for each agent role. Test with sample medical cases.                     |
| **Person B** | Agentic orchestration | The multi-agent workflow — intake → image analysis → triage → documentation. FHIR output generation. Agent coordination logic. |
| **Person C** | UI + writeup + video  | Triage dashboard (web UI), patient intake form, nurse review screen. Kaggle writeup. Record 3-min demo video.                  |

### GitHub Projects Board (4-day plan)

With each person running multiple agents in parallel, this compresses to 4 days — that's the whole point of this workflow.

![MedGemma 4-Day Plan](medgemma-project-4-day-plan.png)

```
#1 MedGemma setup     (day 1)       ← foundation, no deps
#2 Intake agent       (day 1-2)     ← depends on #1
#3 Image agent        (day 2-3)     ← depends on #1
#4 Triage logic       (day 1-2)     ← depends on #1 (uses MedGemma 27B)
#5 FHIR output        (day 2-3)     ← depends on #4
#6 Agent pipeline     (day 2-3)     ← depends on #2, #3, #4, #5 (start with stubs day 2)
#7 Dashboard UI       (day 1-3)     ← no deps (mock data)
#10 Integration       (day 3)       ← depends on #6, #7
#8 Writeup            (day 3-4)     ← depends on #10
#9 Video              (day 4)       ← depends on #10
#11 Final polish      (day 4)       ← depends on #10
```

### Task Guide for Team Members

> **Board:** [github.com/orgs/intellidoctor/projects/7](https://github.com/orgs/intellidoctor/projects/7)
> **Repo:** [github.com/intellidoctor/medgemma-triage](https://github.com/intellidoctor/medgemma-triage)
> **Slack:** `#medgemma-triage`

Each task below maps to a GitHub Issue. Pick your assigned issue, create a branch (`feat/<issue-number>-short-name`), and submit a PR when done. Full acceptance criteria are in each issue — this guide gives you the big picture.

---

#### #1 — MedGemma Model Setup on Vertex AI `[Roberto]` `P0` `Day 1`

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
- Keep the interface simple — other team members will build on top of this. Return strings/dicts, not framework-specific objects

---

#### #2 — Triage Classifier Agent (Manchester Protocol) `[Thiago]` `P0` `Day 1`

**What:** Create `src/agents/triage.py` — classifies a patient into a Manchester Protocol urgency level based on structured clinical data.

**Goal:** Given patient symptoms, vitals, and chief complaint, output one of: Red (Immediate), Orange (Very Urgent), Yellow (Urgent), Green (Standard), Blue (Non-Urgent) — with clinical reasoning.

**What to deliver:**
- Takes structured patient data (complaint, vitals, symptoms, duration)
- Returns triage color + confidence + reasoning explanation
- Uses Manchester Protocol decision trees (flowcharts by discriminator)
- Prompt engineering to make MedGemma follow the protocol accurately

**Suggestions:**
- Start with a stub that returns mock classifications — don't block on #1
- The Manchester Protocol has ~52 flowcharts organized by chief complaint (chest pain, abdominal pain, breathing difficulty, etc.). Focus on the top 10 most common ER presentations
- Include a few discriminators: life threat → pain severity → acuity → time of onset
- Test with synthetic cases covering each color level

---

#### #3 — Dashboard UI with Mock Data (Streamlit) `[Roberta]` `P0` `Day 1`

**What:** Create `src/ui/app.py` — a Streamlit dashboard that demonstrates the full triage workflow.

**Goal:** A nurse opens the dashboard, enters patient info (or it arrives automatically), sees the AI's triage suggestion, and can approve/override. Demo-ready from day 1 with mock data.

**What to deliver:**
- Patient intake form: name, age, gender, chief complaint, vitals (HR, BP, SpO2, temp), symptom duration
- Image upload area (for skin photos, X-rays — even if analysis is mocked initially)
- Triage result display: color-coded badge (Red/Orange/Yellow/Green/Blue) with reasoning
- Patient queue view: list of triaged patients sorted by urgency
- FHIR output viewer: collapsible JSON section showing the structured output
- Clean, professional design — this is what judges see in the demo video

**Suggestions:**
- Use `st.columns()` for layout, `st.status()` for agent progress feedback
- Color-code everything: Red = `#E74C3C`, Orange = `#E67E22`, Yellow = `#F1C40F`, Green = `#27AE60`, Blue = `#3498DB`
- Mock data should include 3-5 realistic cases (chest pain, fracture, mild fever, etc.)
- Design the UI so it's easy to swap mock data for real agent calls later (use function calls, not inline data)

---

#### #4 — Intake Interviewer Agent `[Thiago]` `P0` `Day 1-2`

**What:** Create `src/agents/intake.py` — conducts a structured clinical interview and outputs a standardized patient record.

**Goal:** Simulate what a triage nurse does in the first 2 minutes: gather chief complaint, symptom details, history, allergies, and medications — then produce a structured record that downstream agents can consume.

**What to deliver:**
- Conversational agent that asks clinically relevant follow-up questions
- Extracts: chief complaint, onset/duration, severity (0-10), associated symptoms, PMH, allergies, medications, recent travel/contacts
- Outputs structured dict/JSON compatible with FHIR Patient + Encounter resources
- Handles both text input and (future) voice transcription

**Suggestions:**
- Depends on #1 for real model calls, but can develop with mock responses
- Use a system prompt that establishes the agent as a triage nurse assistant
- Follow clinical interview structure: CC → HPI → ROS → PMH → Medications → Allergies → Social History
- Keep the output schema consistent — downstream agents (#2 triage, #6 FHIR) will parse it

---

#### #5 — Medical Image Analysis Agent `[Roberto]` `P1` `Day 1-2`

**What:** Create `src/agents/image_reader.py` — analyzes medical images using MedGemma 4B multimodal.

**Goal:** When a patient brings an X-ray, skin photo, or other medical image, this agent provides a structured analysis that feeds into the triage decision.

**What to deliver:**
- Accepts image file (JPEG/PNG) + optional clinical context
- Returns structured findings: modality detected, key observations, abnormalities, suggested relevance to chief complaint
- Handles common medical image types: chest X-ray, skin lesion photos, wound photos, extremity X-rays
- Includes appropriate disclaimers ("AI-assisted analysis, requires clinical validation")

**Suggestions:**
- Use MedGemma 4B (the multimodal model) via the interface from #1
- For demo, include 2-3 sample images (synthetic or from public medical datasets like NIH ChestX-ray14 or ISIC skin lesion dataset)
- Output should be structured enough for the triage agent to incorporate
- Consider CXR Foundation model as an alternative/complement for chest X-rays

---

#### #6 — FHIR Output Generation `[Thiago]` `P1` `Day 2`

**What:** Create `src/fhir/builder.py` — converts the triage pipeline output into valid FHIR R4 resources.

**Goal:** Every triage encounter produces a standards-compliant FHIR Bundle that could be sent to a hospital EHR system. This demonstrates real-world interoperability.

**What to deliver:**
- Generate FHIR R4 resources: Patient, Encounter, Observation (vitals), Condition (chief complaint), DiagnosticReport (triage result)
- Bundle everything into a FHIR Bundle (type: document or transaction)
- Validate output using `fhir.resources` library
- Include triage classification as a coded Observation (Manchester Protocol codes)

**Suggestions:**
- Use `fhir.resources` Python library (already in tech stack)
- FHIR resources are just structured JSON — don't overthink it
- Key references: [FHIR R4 Patient](https://www.hl7.org/fhir/patient.html), [FHIR Encounter](https://www.hl7.org/fhir/encounter.html)
- The triage color maps to a FHIR Observation with a coding from the Manchester Triage System

---

#### #7 — LangGraph Agent Pipeline (Orchestrator) `[Roberta]` `P0` `Day 2`

**What:** Create `src/pipeline/orchestrator.py` — the LangGraph workflow that connects all agents into a single pipeline.

**Goal:** One function call that takes raw patient input and produces a complete triage result with FHIR output. This is the "agentic workflow" the judges evaluate.

**What to deliver:**
- LangGraph StateGraph with nodes for each agent: intake → image_reader → triage → documentation
- State schema defining data that flows between agents
- Conditional routing: skip image analysis if no image provided
- Error handling: if one agent fails, the pipeline degrades gracefully
- Clear logging showing the agent orchestration flow

**Suggestions:**
- Use LangGraph's `StateGraph` with typed state (TypedDict)
- Start with stubs for agents that aren't ready yet — the pipeline structure is what matters first
- Key pattern: each node takes the full state, does its work, and returns updates to the state
- Check [LangGraph docs](https://langchain-ai.github.io/langgraph/) for conditional edges and parallel execution

---

#### #8 — Kaggle Writeup `[Roberto]` `P0` `Day 3-4`

**What:** Write the Kaggle competition submission document following their template.

**Goal:** A compelling writeup that explains the problem, solution, and technical approach. This is 50%+ of the judging score.

**What to cover:**
- Problem statement: ER triage bottleneck in Brazilian SUS (150M+ users)
- Solution: agentic workflow with MedGemma at each stage
- Technical architecture: the 4-agent pipeline diagram
- How each HAI-DEF model is used (MedGemma 4B, 27B Text, optionally CXR Foundation)
- Human-in-the-loop design: nurse always has final authority
- FHIR interoperability: output integrates with existing hospital systems
- Privacy: MedGemma runs locally, no patient data leaves the facility
- Impact potential: faster triage → fewer deaths from delayed care

---

#### #9 — Demo Video (3 min) `[Roberto]` `P0` `Day 3-4`

**What:** Record a 3-minute video demonstrating the application.

**Goal:** Show judges a complete triage workflow from patient arrival to nurse decision.

**Suggested flow:**
1. (0:00-0:30) Problem intro — ER waiting room, overwhelmed nurses
2. (0:30-1:30) Live demo — patient enters data, agent pipeline runs, triage result appears
3. (1:30-2:15) Technical walkthrough — show agent orchestration, FHIR output
4. (2:15-2:45) Image analysis demo — upload an X-ray, see findings
5. (2:45-3:00) Impact statement — faster triage for 150M Brazilians

---

#### #10 — End-to-End Integration `[Thiago]` `P0` `Day 3`

**What:** Connect the real agents (#4, #5, #2) through the pipeline (#7) to the UI (#3). Replace all mocks with real model calls.

**Goal:** A working demo where you can enter patient data in the UI, the agents process it through MedGemma, and you see real triage results.

**What to deliver:**
- UI calls the orchestrator pipeline with real patient data
- All agents use MedGemma via the `src/models/medgemma.py` interface
- FHIR output is generated and displayed in the UI
- At least 3 synthetic test cases work end-to-end
- Error handling for model timeouts or failures

---

#### #11 — Final Polish and Testing `[All]` `P1` `Day 3-4`

**What:** Bug fixes, edge cases, and demo polish. All team members contribute.

**What to check:**
- All synthetic test cases pass end-to-end
- UI handles errors gracefully (model timeout, invalid input)
- Code passes `ruff check` and `black` formatting
- README has clear setup instructions
- No credentials, API keys, or real patient data in the repo
- Demo flow is smooth for the video recording

---

### Team Quick Reference

| Person | Slack | GitHub | Issues | Focus |
|--------|-------|--------|--------|-------|
| **Roberto** | @rshimizubr | @robertoshimizu | #1, #5, #8, #9 | Models + submission |
| **Thiago** | @thiagoreisporto | @Thiago-Reis-Porto | #2, #4, #6, #10 | Agents + integration |
| **Roberta** | @robdallagogar | @rferrazd | #3, #7 | UI + pipeline |

### Workflow Reminders

1. **Branch naming:** `feat/<issue-number>-short-name` (e.g., `feat/1-medgemma-setup`)
2. **One PR per issue.** Link the issue in the PR description: `Closes #1`
3. **Commit often.** Git is your memory, not the chat.
4. **Ask in Slack** if blocked. Don't spin for hours.
5. **Use worktrees** for parallel work: `git worktree add ../worktree-issue-1 origin/main`

---

### Testing & CI

#### Running Tests Locally

```bash
source .venv/bin/activate

# Unit tests (no credentials needed)
pytest tests/ -m "not integration" -v

# Integration tests (requires Vertex AI credentials in .env)
pytest tests/ -m integration -v

# Lint + format
ruff check src/
black --check src/ tests/
```

#### How the Mock Library Works

A project-wide mock in `tests/conftest.py` automatically patches `generate_text` and `analyze_image` from `src.models.medgemma` for all non-integration tests. You don't need `@patch` decorators in your test files — just write tests that call agent code normally, and the mock intercepts model calls.

The mock returns keyword-matched canned responses based on the prompt content:

| Keyword in prompt | Mock returns |
|---|---|
| "chest pain" | Triage JSON: ORANGE, priority 2 |
| "choking" | Triage JSON: RED, priority 1 |
| "headache" | Triage JSON: YELLOW, priority 3 |
| "sprained ankle" | Triage JSON: GREEN, priority 4 |
| "medication refill" | Triage JSON: BLUE, priority 5 |
| anything else | Generic medical text (plain string) |

`analyze_image` always returns a static finding string.

**To add new canned responses:** edit the `_TRIAGE_RESPONSES` dict in `tests/conftest.py`.

**To write tests that hit real endpoints:** mark them with `@pytest.mark.integration`. The conftest mock skips those tests automatically.

#### CI Pipeline (GitHub Actions)

Every PR to `main` and every push to `main` triggers `.github/workflows/ci.yml`:

1. **Lint** — `ruff check src/`
2. **Format check** — `black --check src/ tests/`
3. **Unit tests** — `pytest tests/ -m "not integration" -v`

No credentials or secrets are configured in CI. If any step fails, the PR gets a red check. Fix failures before requesting review.

---

### Agent Setup: GitHub & Slack MCP Servers

For your Claude Code agent to read/update GitHub issues, move cards on the project board, and post to `#medgemma-triage` on Slack, you need two MCP servers configured. This is a **one-time setup per machine**.

#### Credential Ownership

| Credential | Who creates it | Shared or personal |
|-----------|---------------|-------------------|
| `GOOGLE_APPLICATION_CREDENTIALS_BASE64` | Roberto (shared via Slack DM) | Shared — same for everyone |
| `MEDGEMMA_27B_BASE_URL` | Already in `.env.example` | Shared — same for everyone |
| `MEDGEMMA_4B_BASE_URL` | Already in `.env.example` | Shared — same for everyone |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | **Each person** creates their own | Personal — never share |
| `SLACK_BOT_TOKEN` | Roberto (shared via Slack DM) | Shared — same for everyone |
| `SLACK_TEAM_ID` | Already in `.env.example` | Shared — same for everyone |

> **Quick start:** Copy `.env.example` to `.env`, fill in your own GitHub PAT, and ask Roberto for the GCP credentials and Slack bot token.

#### Prerequisites

1. **Node.js 18+** — needed to run the MCP servers via `npx`
2. **GitHub Personal Access Token** — each person creates their own
   - Create at: https://github.com/settings/tokens
   - Classic token with scopes: `repo`, `read:org`, `project`
3. **Slack Bot Token** — shared team token (ask Roberto via Slack DM)
   - The bot needs scopes: `channels:history`, `channels:read`, `chat:write`, `users:read`
4. **Slack Team ID** — already in `.env.example` (`T0AF4E6QX6W`)

#### Step 1: Set environment variables

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
export SLACK_TEAM_ID="T0AF4E6QX6W"
```

Then `source ~/.zshrc` (or restart your terminal).

#### Step 2: Create `.mcp.json` in the project root

This file tells Claude Code which MCP servers to start. Create it at the repo root (`medgemma-triage/.mcp.json`):

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}",
        "GITHUB_TOOLSETS": "repos,issues,pull_requests,projects"
      }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
        "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"
      }
    }
  }
}
```

> **Note:** `${VAR}` syntax references your shell environment variables — don't paste the actual tokens into this file (it's committed to the repo).

#### Step 3: Verify it works

Start Claude Code in the project directory and test:

```
# GitHub — should list all 11 issues
> List open issues on intellidoctor/medgemma-triage

# Slack — should show recent messages
> Read the last 5 messages from #medgemma-triage

# Post a test message
> Post "Testing MCP setup ✓" to #medgemma-triage
```

If GitHub tools fail with `INSUFFICIENT_SCOPES`, run:
```bash
gh auth refresh -s project
```

#### Slack Channel IDs (for reference)

| Channel | ID | Purpose |
|---------|-----|---------|
| `#medgemma-triage` | `C0AF11QBXHT` | Project coordination |
| `#all-intellidoctor` | `C0AF82JC3KN` | General announcements |
| `#social` | `C0AEY2NRZEX` | Off-topic |

#### What your agent can do once set up

| Capability | Example |
|-----------|---------|
| Read assigned issues | "What issues are assigned to me?" |
| Update issue status | "Move issue #1 to In Progress" |
| Create PRs | "Create a PR for my changes on feat/1-medgemma-setup" |
| Post to Slack | "Tell the team in #medgemma-triage that #1 is ready for review" |
| Read Slack threads | "What did Thiago say in the latest thread?" |

---

### Tech Stack

| Component     | Tool                                                               |
| ------------- | ------------------------------------------------------------------ |
| Models        | MedGemma 4B (images) + MedGemma 27B Text (reasoning) via Vertex AI |
| Orchestration | Python — LangGraph or simple agent loop                            |
| FHIR output   | `fhir.resources` Python library                                    |
| UI            | Streamlit or Gradio (fast to build)                                |
| Hosting       | Vertex AI endpoints for models, local for demo                     |
| Code          | Public GitHub repo                                                 |

### References

- [MedGemma docs](https://developers.google.com/health-ai-developer-foundations/medgemma)
- [MedGemma model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)
- [HAI-DEF on Hugging Face](https://huggingface.co/collections/google/health-ai-developer-foundations-hai-def)
- [MedGemma agentic orchestration](https://developers.google.com/health-ai-developer-foundations/medgemma) — official docs mention pairing with FHIR, Gemini, web search
- [How to Build Agentic Workflows with MedGemma 1.5 (YouTube)](https://www.youtube.com/watch?v=1FR2wOuRpY4)
- [MedGemma Kaggle submission example (YouTube)](https://www.youtube.com/watch?v=N5RVNnSQGSo)

---

## References

### Why Multi-Agent Coordination

- [SemiAnalysis — Claude Code is the Inflection Point](https://newsletter.semianalysis.com/p/claude-code-is-the-inflection-point) — 4% of GitHub public commits from Claude Code, projected 20%+ by end of 2026
- [TLDR Dev — Building a C Compiler with Parallel Claudes](https://tldr.tech/dev/2026-02-06) — 16 agents, 100K lines of Rust, $20K, compiles the Linux kernel
- [10 Claude Code Secrets from the Team](https://www.aienabledpm.com/p/10-claude-code-secrets-from-the-team) — Boris Cherny's workflow: 5-10 parallel sessions, 50-100 PRs/week
- [Anthropic — 2026 Agentic Coding Trends Report (PDF)](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)

### Tooling

- [GitHub MCP Server](https://github.com/github/github-mcp-server) — includes `projects` toolset for agent ↔ board integration
- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams) — team lead + teammates, shared task list, peer messaging
- [Claude Code GitHub Action](https://code.claude.com/docs/en/github-actions) — `@claude` trigger in Issues/PRs, works with Vertex AI
- [Claude Code Multi-Agent Orchestration (IndyDevDan)](https://www.youtube.com/watch?v=RpUTF_U4kiw)
