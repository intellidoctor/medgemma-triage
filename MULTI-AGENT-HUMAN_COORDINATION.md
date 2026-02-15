# Multi-Agent & Human Coordination in Agentic Coding (Feb 2026)

> Session report — Research on how Anthropic and the broader community coordinate multi-human, multi-agent workflows using Claude Code, Agent Teams, and related tooling.

---

## 1. The State of Agentic Coding

### Headline Accomplishments (Verified)

| Project | What Happened | Scale |
|---------|--------------|-------|
| **Anthropic C Compiler** | 16 parallel Claude Opus 4.6 agents built a Rust-based C compiler from scratch — compiles Linux kernel, PostgreSQL, FFmpeg, SQLite, QEMU, Redis | ~100,000 lines of Rust, $20K API cost, ~2 weeks, ~2,000 sessions |
| **Rakuten** | 50 engineers across 6 repos using Claude Code in production; Claude implemented activation vector extraction in vLLM (12.5M line codebase) autonomously | 7+ hours autonomous operation |
| **Augment Code customer** | A project estimated at 4-8 months by CTO completed in 2 weeks | Single enterprise customer |
| **Every/Cora (Kieran Klaassen)** | 100% of PRs opened by Claude Code for months; 2-person team shipping like a team of 5 | 4-5 parallel Claude instances daily |
| **Zapier** | 89% AI adoption across entire organization, 800+ AI agents deployed internally | Company-wide |

### Industry Metrics

- **4% of GitHub public commits** are authored by Claude Code (SemiAnalysis, Feb 2026)
- Projected to reach **20%+ of all daily commits** by end of 2026
- VS Code v1.109 (Feb 4, 2026) supports Claude, Codex, and Copilot running side-by-side

---

## 2. How They're Actually Doing It

The extraordinary results do **not** come from using Claude Code as a single standalone session. The architecture has shifted fundamentally to **isolation + parallelism**.

### 2.1 Parallel Git Worktrees

Each Claude instance works in its own git worktree (an isolated copy of the repo). No file conflicts between agents. Merge results when done, discard if bad. Original code stays untouched.

```bash
git worktree add ~/.claude/worktrees/feature-auth origin/main
git worktree add ~/.claude/worktrees/fix-bug-42 origin/main
git worktree add ~/.claude/worktrees/write-tests origin/main
```

Shell aliases (`za`, `zb`, `zc`) let engineers hop between worktrees in one keystroke.

### 2.2 Agent Teams (Research Preview, Feb 2026)

One session acts as "team lead," spawning teammate instances. Each teammate gets its own context window (solving the context rot problem). Teammates communicate via shared mailbox and task list. Best for read-heavy parallel work (code review, codebase analysis, competing hypotheses).

**Architecture:**

| Component | Role |
|-----------|------|
| Team Lead | Main Claude Code session — creates team, spawns teammates, synthesizes results |
| Teammates | Separate Claude Code instances with independent context windows |
| Task List | Shared work items at `~/.claude/tasks/{team-name}/` |
| Mailbox | Messaging system for inter-agent communication |
| Config | Team membership at `~/.claude/teams/{team-name}/config.json` |

### 2.3 Subagents (Different from Teams)

Heavy tasks run in isolated context windows. Return condensed results to the main session. Main conversation stays lean — directly addresses context rot.

| | Subagents | Agent Teams |
|---|-----------|-------------|
| Context | Own window; results return to caller | Own window; fully independent |
| Communication | Report back to main agent only | Teammates message each other directly |
| Coordination | Main agent manages all work | Shared task list with self-coordination |
| Best for | Focused tasks where only result matters | Complex work requiring discussion |
| Token cost | Lower (results summarized) | Higher (each teammate = full instance) |

### 2.4 The Compound Engineering Pattern

1. Human defines intent and spec (`CLAUDE.md`, plan mode)
2. Claude plans the approach
3. Human approves the plan
4. Claude executes in parallel branches
5. Human reviews diffs before merge
6. Another Claude instance reviews the PR (or Claude Agent SDK on CI)

### 2.5 Boris Cherny's Workflow (Creator of Claude Code)

- Runs 5-10 parallel Claude Code sessions simultaneously
- Produces 50-100 PRs per week
- Round-robins: "as soon as a tab is free I restart Claude and start a new task"
- Each session works on unrelated tasks in the same repo, different checkouts
- Uses Claude Agent SDK on CI for automated code review
- Does NOT micromanage context: "just let Claude compact when it decides to"
- CLAUDE.md is kept small (~2.5k tokens), pruned regularly — "delete your CLAUDE.md, add it back one instruction at a time as you see mistakes"

---

## 3. The Four-Layer Architecture

### Layer 1: Human Coordination

Engineers coordinate via GitHub PRs, Slack, and Linear/Jira. Claude is sometimes tagged directly in Slack bug channels. Shared artifacts:

- **CLAUDE.md** — institutional rules, read perfectly by every Claude session
- **Git repo** — the single source of truth across all sessions

### Layer 2: Individual Engineer Workspace

Each engineer runs 3-5 git worktrees in tmux/Ghostty, each pane a separate Claude session on a different task. Key patterns:

- **Round-robin** — when one tab finishes, restart Claude with a new task
- **Plan Mode** — obsess over the plan, then one-shot the build
- **Two-Claude Review** — Claude #1 writes plan, Claude #2 reviews as staff engineer
- **Subagents** — delegate heavy search/explore tasks without polluting main context
- **Voice dictation** — fn+fn on macOS, 3x faster than typing

### Layer 3: Agent Teams (Complex Tasks)

One session is Team Lead, spawns teammates (Frontend, Backend, Test agents). Each gets its own fresh context window. They share a task list and mailbox. Peer-to-peer messaging, not just through the lead. Each agent = fresh context, no rot.

### Layer 4: CI/CD & Persistence

- **Git** is the real persistent memory across all sessions
- **CI Pipeline** runs Claude Agent SDK for automated code review
- **CLAUDE.md** is a living document — every mistake becomes a rule
- **Skills & Hooks** — reusable workflows, lazy-loaded on demand
- By the time a human reviews, the code has already been AI-reviewed

**Feedback Loop:** Git commit → CI review (Claude) → Human final review → Merge → CLAUDE.md updated

---

## 4. OpenClaw — The Buzz and the Backlash

**What it was:** An open-source personal AI agent (formerly Clawdbot/Moltbot) running as a persistent daemon connected to 12+ messaging platforms (WhatsApp, Telegram, Discord, iMessage). Heartbeat scheduler, cross-session memory, could trigger Claude Code sessions, commit code, open PRs, call your phone, manage email/calendars — all 24/7.

**The viral explosion:** 160,000+ GitHub stars. People buying Mac Minis specifically to run it.

**The security disaster:**

- 35,000 emails and 1.5M API keys exposed
- Top-downloaded community skill was malware
- Security model was prompt instructions ("don't access sensitive files") — no architectural boundaries
- Any prompt injection could override all safety

**Status:** Effectively dead. Community recommends building secure agents using Claude Opus 4.6 + n8n with hard architectural guardrails (Docker sandboxing, Cloudflare tunnels, explicit tool approval policies).

---

## 5. VS Code as Multi-Agent Command Center

VS Code v1.109 (Feb 4, 2026) supports running Copilot, Claude, and Codex side by side. Developers delegate tasks to different agents based on strengths from a single IDE.

**myclaude** (2.2k GitHub stars) — multi-agent orchestration workflow coordinating Claude Code, Codex, Gemini, and OpenCode together.

**Augment Code's "Intent"** — a workspace designed for orchestrating agents. Define the spec, approve the plan, let agents work in parallel.

---

## 6. Context Window — The Real Constraint

### The Raw Numbers

- Opus 4.6: 1M token context window (beta)
- Usable portion in Claude Code session: ~133k tokens (system prompt + tools + CLAUDE.md eat ~45k)
- Opus 4.6 MRCR v2 score: 76% (vs Sonnet 4.5's 18.5%) — massive improvement, not infinite

### What Power Users Do

| Practice | Why |
|----------|-----|
| `/compact` manually at ~50% context usage | Don't wait for auto-compact |
| Start fresh sessions aggressively | Correct practice, not a limitation |
| Use subagents for heavy tasks | Main context stays lean |
| Keep subtasks small (<50% context each) | Complete within safe window |
| Commit after every completed task | Git = persistent memory |
| CLAUDE.md as persistent memory | Not the conversation |
| Use native Tasks (persist across compaction) | Survive context resets |

### Key Insight

> The era isn't "Claude is smarter now." It's "run 5 Claudes in parallel, each with a fresh context and a narrow task."
>
> Git = persistent memory | CLAUDE.md = institutional knowledge | Parallel sessions = no context rot | CI = automated quality gate

---

## 7. Using Agent Teams (Practical Guide)

### Prerequisites

- Claude Code v2.1.41+
- Environment variable: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

### Starting a Team

Prompt Claude Code in natural language:

```
Create an agent team to review this codebase. One teammate on security,
one on performance, one on test coverage.
```

### Key Controls

| Action | How |
|--------|-----|
| Switch between teammates | `Shift+Up` / `Shift+Down` |
| Talk to a specific teammate | "Tell the researcher to focus on auth" |
| Require plan approval | "Spawn an architect. Require plan approval before changes." |
| Shut down a teammate | "Ask the researcher to shut down" |
| Clean up the whole team | "Clean up the team" |
| Use Sonnet for teammates | "Create a team with 3 teammates. Use Sonnet for each." |

### Cost Considerations

- Opus is ~5x the cost of Sonnet per token
- A 3-teammate team all running Opus burns credits fast
- For straightforward tasks (review, search, tests), use Sonnet teammates
- Reserve Opus for team lead or deep reasoning tasks

---

## 8. Model Comparison (Feb 2026)

| Metric | Claude Opus 4.6 | GPT-5.3 Codex |
|--------|-----------------|---------------|
| Context Window | 1,000,000 tokens (beta) | 512,000 tokens |
| Generation Speed | ~85-100 tokens/sec | ~240-260 tokens/sec |
| Logic Consistency | 94.5% | 88.2% |
| Best Use Case | Deep architecture & debugging | Rapid feature builds & CI/CD |
| Legacy Refactoring | Exceptional | Good |
| Prototyping Speed | Moderate | Exceptional |

---

## 9. Honest Assessment

### What's Real

- Multi-agent parallel workflows produce dramatically more output
- The compiler project is genuinely impressive (independently verified)
- Anthropic's own team uses these patterns daily (Boris Cherny's workflow is well-documented)
- 4% of all GitHub public commits are already from Claude Code

### What Requires Nuance

- Extraordinary results come from **orchestration infrastructure** (git worktrees, tmux, agent teams, subagents), not from a single chat session
- Cost is substantial — compiler cost $20K; power users report $2K+/month
- Security review is still a human job — agents handle rule-based vulnerabilities (SQLi, XSS) but miss authorization, business logic, SSRF
- Agent teams are in research preview — write-heavy tasks still cause conflicts
- Boris Cherny has unlimited tokens as an Anthropic employee — his workflow is not directly reproducible for average users at the same scale

### Actionable Takeaways

1. The context management instinct (starting fresh sessions) is correct practice
2. The gap between standalone use and the buzz is **parallelism + isolation**, not "better prompting"
3. Start experimenting with subagents (Task tool) and git worktrees
4. Use Agent Teams for read-heavy parallel work (enable with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
5. Treat each Claude session as a focused worker with a single task, not a long-lived conversation partner
6. Invest in CLAUDE.md — keep it small, prune regularly, let mistakes drive the rules

---

## Sources

- [Anthropic — Introducing Claude Opus 4.6](https://www.anthropic.com/news/claude-opus-4-6)
- [Anthropic — 2026 Agentic Coding Trends Report (PDF)](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [Anthropic — Agent Teams Documentation](https://docs.anthropic.com/en/docs/claude-code/agent-teams)
- [SemiAnalysis — Claude Code is the Inflection Point](https://newsletter.semianalysis.com/p/claude-code-is-the-inflection-point)
- [TLDR Dev — Building a C Compiler with Parallel Claudes](https://tldr.tech/dev/2026-02-06)
- [Analytics Vidhya — Claude Agents Built a C Compiler](https://www.analyticsvidhya.com/blog/2026/02/claude-agents-built-c-compiler/)
- [The New Stack — VS Code Multi-Agent Command Center](https://thenewstack.io/vs-code-becomes-multi-agent-command-center-for-developers/)
- [AI Enabled PM — 10 Claude Code Secrets from the Team](https://www.aienabledpm.com/p/10-claude-code-secrets-from-the-team)
- [Dev Genius — The Claude Code Team Revealed Their Setup](https://blog.devgenius.io/the-claude-code-team-just-revealed-their-setup-pay-attention-4e5d90208813)
- [LinkedIn — State of AI Agents 2026](https://www.linkedin.com/pulse/state-ai-agents-2026-autonomy-here-nishikant-dhanuka-pssge)
- [TrekKnowledge — AI This Week: Multi-Agent Orchestration](https://trewknowledge.com/2026/02/06/ai-this-week-multi-agent-orchestration-becomes-reality/)
- [Vertu — Claude Opus 4.6 vs GPT-5.3 Codex](https://vertu.com/ai-tools/claude-opus-4-6-vs-gpt-5-3-codex-results-from-a-48-hour-deep-dive-testing/)
- [myclaude — Multi-Agent Orchestration Workflow](https://github.com/cexll/myclaude)
- [IndyDevDan — Claude Code Multi-Agent Orchestration (Video)](https://www.youtube.com/watch?v=RpUTF_U4kiw)
- [Boris Cherny workflow analysis (HN)](https://gist.github.com/notjulian/3a623d7889e5971d4b9fd1aac949b74e)

---

## Diagram

Architecture diagram saved at:
- **PNG**: `~/Downloads/Excalidraw/anthropic-multi-human-multi-agent-coordination-architecture.png`
- **SVG**: `~/Downloads/Excalidraw/anthropic-multi-human-multi-agent-coordination-architecture.svg`

---

*Report generated: Feb 13, 2026*
