# MedGemma Team Playbook

How we work with Claude Code. Read this before your first session.

---

## Core Principle

> Run focused Claudes in parallel, each with a fresh context and a narrow task. Git is memory. CLAUDE.md is institutional knowledge.

We do **not** use Claude as a long-lived conversation partner. Every session is a short-lived worker with one job.

---

## 1. Before You Start

### Claim your work

GitHub Projects is the single source of truth. Before starting:

1. Check the board for unassigned issues
2. Assign yourself
3. Use `/start-issue` — it creates the branch, sets up the worktree, and shows you the task

### Know the skills available

| Command | What it does |
|---------|-------------|
| `/start-issue` | Claim an issue, create branch, optional worktree |
| `/submit-work` | Lint, test, commit, push, create PR |
| `/write_tests` | Generate pytest tests following project conventions |
| `/commit` | Create a well-structured commit |

---

## 2. One Task, One Session, One Branch

Every Claude Code session gets **one focused task**. Not two. Not "and also fix that other thing."

```
Issue #5: Build intake agent
  → Branch: feat/5-intake-agent
  → One Claude session
  → Commit after each sub-task
  → When done: /submit-work
  → Start a NEW session for the next task
```

**Why:** Claude's context window degrades over long sessions (context rot). Fresh sessions = sharp Claude.

### When to start fresh

- After completing a task (always)
- When Claude starts repeating itself or forgetting earlier decisions
- When context usage hits ~50% (run `/compact` or just start over)
- After any major plan change

---

## 3. Parallel Git Worktrees

When working on multiple tasks simultaneously, use worktrees — not branches in the same directory.

```bash
# Set up parallel work
git worktree add ../worktree-issue-5 origin/main
git worktree add ../worktree-issue-6 origin/main

# Each worktree gets its own Claude session
# Terminal 1: cd ../worktree-issue-5 && claude
# Terminal 2: cd ../worktree-issue-6 && claude
```

Each worktree is a full isolated copy of the repo. No file conflicts between sessions. Merge via PR when done.

### Cleanup

```bash
# After PR is merged
git worktree remove ../worktree-issue-5
```

Or use `/clean_gone` to clean up all branches whose remotes have been deleted.

---

## 4. Plan Mode

For any non-trivial task, **plan before building**.

### The pattern

1. Start Claude in the worktree
2. Describe the task (or let `/start-issue` load it)
3. Claude enters plan mode — it reads code, explores the codebase, designs the approach
4. **You review the plan** — this is your highest-leverage moment
5. Approve or adjust
6. Claude executes

### Why this matters

Bad plans produce bad code that wastes review cycles. A 5-minute plan review saves hours of rework. Challenge the plan:

- "Why not use X instead?"
- "What about the edge case where...?"
- "This touches too many files — can we scope it down?"

---

## 5. Subagents for Heavy Tasks

When Claude needs to search the codebase, explore multiple files, or do deep research, it should delegate to a **subagent** instead of doing it in the main context.

### What subagents do

| Task | Use subagent? |
|------|--------------|
| "Find where FHIR resources are constructed" | Yes — Explore agent |
| "Research how LangGraph handles state" | Yes — general-purpose agent |
| "Add a field to this function" | No — do it directly |
| "Review this PR for security issues" | Yes — code-reviewer agent |

### Why

The main session's context stays lean. Subagents get their own context window, do the heavy lifting, and return a condensed result. The main session never gets polluted with hundreds of lines of search results.

You don't need to do anything — Claude uses subagents automatically when configured. Just be aware that when you see "Task" tool calls, that's delegation happening.

---

## 6. The Compound Engineering Pattern

This is how a complete feature flows:

```
1. Human picks issue from board           ← /start-issue
2. Claude plans the approach              ← Plan mode
3. Human reviews and approves the plan    ← Your judgment
4. Claude executes on its branch          ← Isolated worktree
5. Claude commits after each sub-task     ← Git = memory
6. Human runs /submit-work               ← Creates PR
7. Another human reviews the PR           ← Final judgment
8. Merge to main                          ← Protected branch
9. If Claude made a mistake → add rule    ← CLAUDE.md updated
```

Steps 3 and 7 are where humans add the most value. Everything else is execution.

---

## 7. The Feedback Loop

Every mistake Claude makes should become a rule.

```
Claude generates print() statements instead of logging
  → Add to CLAUDE.md: "Use logging module, not print()"

Claude calls Vertex AI directly from an agent
  → Add to CLAUDE.md: "All model calls go through src/models/medgemma.py"

Claude creates a 500-line function
  → Add to CLAUDE.md: "Keep functions under 50 lines"
```

**CLAUDE.md is a living document.** The team contributes to it. Keep it under 2500 tokens — prune old rules that are no longer relevant.

---

## 8. Commit Discipline

Git is the persistent memory across all sessions. Claude's context disappears. Git stays.

### Rules

- **Commit after every completed sub-task** — not at the end of a session
- **Never push directly to main** — all changes via PR
- **One branch per issue** — `feat/N-short-description`
- **Use `/commit`** — it generates a proper commit message from the diff

### What a good commit flow looks like

```
feat/5-intake-agent
  ├── "Add intake agent skeleton with state schema"
  ├── "Implement patient interview loop"
  ├── "Add input validation for vital signs"
  ├── "Add tests for intake agent"
  └── PR → review → merge
```

Not:

```
feat/5-intake-agent
  └── "Add intake agent"  ← one giant commit with everything
```

---

## 9. Context Management

### The numbers

- Opus 4.6: ~133k usable tokens per session (system prompt eats the rest)
- CLAUDE.md + skills metadata is loaded every session
- Keep CLAUDE.md lean — every token there is a token less for your task

### Practical rules

| Situation | Action |
|-----------|--------|
| Context at ~50% | Run `/compact` or start fresh |
| Task is done | Start a new session (always) |
| Need to search many files | Let Claude use subagents |
| Long debugging session going nowhere | Start fresh with a clearer prompt |
| Need to remember something across sessions | Put it in a commit message or CLAUDE.md |

---

## 10. Agent Teams (Advanced)

For complex tasks that benefit from parallel AI work (e.g., "review this codebase for security, performance, and test coverage simultaneously"), use Agent Teams.

### Prerequisites

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### When to use

- Read-heavy parallel analysis (code review from multiple angles)
- Competing hypotheses (try two approaches, compare)
- Large codebase exploration

### When NOT to use

- Write-heavy tasks (agents will conflict on files)
- Simple single-file changes
- Tasks that must be sequential

### Cost awareness

- Each teammate is a full Claude instance
- A 3-teammate Opus team burns credits fast
- Use Sonnet for teammates doing straightforward work (search, review)
- Reserve Opus for the team lead or deep reasoning

---

## Quick Reference

```
Start work:        /start-issue
Plan first:        Claude enters plan mode automatically for non-trivial tasks
Commit often:      /commit
Write tests:       /write_tests <module>
Submit PR:         /submit-work
Clean branches:    /clean_gone
```

### Session checklist

- [ ] Claimed an issue on the board
- [ ] Working in a dedicated branch (or worktree)
- [ ] Plan reviewed before execution
- [ ] Committing after each sub-task
- [ ] Context not bloated (start fresh if needed)
- [ ] PR created with `/submit-work` when done

---

*Keep this playbook updated. When something doesn't work, fix the process here.*
