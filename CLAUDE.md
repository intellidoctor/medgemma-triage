# Multi-Agent & Human Coordination Research

## Project Purpose

This project is a research workspace for understanding and experimenting with multi-agent orchestration patterns using Claude Code, Agent Teams, subagents, and related tooling.

## Session Context (Feb 13, 2026)

**Original session ID:** `ec11ec1e-9d4f-4694-9a7d-b8cfce8e539c`

A deep research session was conducted covering:

1. **Verified accomplishments** — Anthropic's 16-agent C compiler ($20K, 100K lines of Rust), Rakuten production deployment (50 engineers, 6 repos), Augment Code (4-8 month project done in 2 weeks), Zapier (89% AI adoption, 800+ agents)
2. **How power users orchestrate** — parallel git worktrees, round-robin sessions, Plan Mode, two-Claude review, subagents for context isolation
3. **Agent Teams** (research preview) — team lead spawns teammates, shared task list, peer-to-peer messaging, each agent gets fresh context window
4. **Four-layer architecture** — Human coordination (Slack/PRs) → Individual workspace (worktrees/tmux) → Agent Teams (parallel agents) → CI/CD persistence (Git + Claude Agent SDK)
5. **OpenClaw** — viral growth then security disaster (35K emails, 1.5M API keys exposed), effectively dead
6. **Context window management** — context rot is real, power users start fresh sessions aggressively, use subagents to keep main context lean, treat git as persistent memory
7. **Model comparison** — Opus 4.6 vs GPT-5.3 Codex benchmarks

## Key Findings

- The gap between standalone Claude Code use and extraordinary results is **parallelism + isolation**, not better prompting
- Each Claude session should be a focused worker with a single task, not a long-lived conversation partner
- Git is the real persistent memory; CLAUDE.md is institutional knowledge; parallel sessions eliminate context rot
- Agent Teams enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (already set)
- Boris Cherny (creator of Claude Code) keeps CLAUDE.md small (~2.5k tokens), prunes regularly

## Files

| File                                                        | Contents                                     |
| ----------------------------------------------------------- | -------------------------------------------- |
| `MULTI-AGENT-HUMAN_COORDINATION.md`                         | Full research report with sources            |
| `README.md`                                                  | Practical guide: two-layer architecture, GitHub Projects + MCP, MedGemma project sketch |
| `~/Downloads/Excalidraw/multi-agent-human-coordination.png` | Architecture diagram (4-layer visualization) |

## Current Progress (Feb 14, 2026)

### Session: Team Coordination Workflow + MedGemma Challenge

**Accomplished:**

1. **Two-layer architecture designed** — outer loop (GitHub Projects for human coordination) + inner loop (each person's local agent orchestration via worktrees/Agent Teams)

2. **GitHub Projects as outer loop** — researched board setup, custom fields, built-in automations (PR merged → card moves to Done)

3. **GitHub MCP Server `projects` toolset** — discovered that the official GitHub MCP Server supports read/write access to GitHub Projects V2 boards. Agents can list items, update card status, add issues/PRs to boards. Not enabled by default — requires `GITHUB_TOOLSETS="repos,issues,pull_requests,projects"`

4. **Claude Code GitHub Action** — documented `@claude` trigger in Issues/PRs, works with Vertex AI credits

5. **GitHub Agent HQ research** — Claude + Codex available in public preview on Agent HQ for Copilot Pro+ ($39/mo) and Enterprise ($39/user/mo). Agents produce Draft PRs inside GitHub. Not available on Free tier.

6. **Vibe Kanban research** — evaluated as inner-loop tool. Strong for personal agent orchestration (git worktrees per task, built-in diffs), weak for team coordination. No sync with GitHub Projects/Issues.

7. **MedGemma Impact Challenge** — researched as practice project for 3-person team. $100K prize pool, Agentic Workflow Prize $10K. Deadline Feb 24, 2026. Project: **Agentic Clinical Intake & Triage Assistant** — an AI assistant for **triage nurses** in Brazilian SUS emergency rooms. Uses MedGemma 4B (medical images) + 27B Text (clinical reasoning) in a multi-agent pipeline: intake interview → image analysis → Manchester Protocol triage → FHIR documentation. Nurse reviews and approves/overrides. Task split for 3 people documented.

8. **GitHub plan status** — Enterprise coupon expired, back to Free tier. Confirmed all architecture works on Free (Projects, MCP Server, Actions with 2K min/mo).

9. **HAI-DEF models researched** — full catalog: MedGemma 1.5 4B (multimodal), MedGemma 27B (multimodal + text-only), MedASR (speech-to-text), CXR Foundation (chest X-ray), Derm Foundation (skin), Path Foundation (histopathology), HEAR (health audio). All free for research and commercial use on Hugging Face. MedGemma officially supports "agentic orchestration" — pairing with FHIR generators, web search, Gemini for function calling.

### Files Modified

| File | Change |
|------|--------|
| `README.md` | Complete rewrite — two-layer architecture, GitHub Projects setup, MCP Server config, agent-board loop, Claude Code GitHub Action, MedGemma project sketch with polished problem statement (triage nurse focus), task split, tech stack |
| `CLAUDE.md` | Updated with session progress and HAI-DEF research |

### Pending / Next Steps

- [ ] Set up a GitHub repo for the MedGemma project
- [ ] Create GitHub Projects board with Issues from the task split (11 issues)
- [ ] Configure GitHub MCP Server with `projects` toolset locally
- [ ] Test MedGemma 4B and 27B on Vertex AI
- [ ] Each team member sets up worktrees and Claude Code
- [ ] Begin implementation (deadline Feb 24, 2026)
- [ ] Prepare Kaggle submission: writeup (template), 3-min video, public repo

### Key Config to Remember

```bash
# GitHub MCP Server with Projects support
GITHUB_TOOLSETS="repos,issues,pull_requests,projects"

# Claude Code Agent Teams
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# Vertex AI (existing setup)
CLAUDE_CODE_USE_VERTEX=1
```
