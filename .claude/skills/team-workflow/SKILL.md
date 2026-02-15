---
name: team-workflow
description: "Enforce team workflow patterns: plan before building, use subagents for heavy search, commit after each sub-task, one task per session. Auto-applied — Claude should follow these patterns without being asked."
---

# Team Workflow Enforcement

## Session Start

When starting a session:
1. Check if working on a specific issue — if so, read the issue first
2. Confirm you are on a feature branch, not `main`
3. If the task is non-trivial (touches >2 files or requires design decisions), enter plan mode before writing code

## During Work

### Plan first
- For any task that is not a trivial fix, plan the approach and present it before executing
- The plan should list which files will be created/modified and why
- Wait for human approval before proceeding

### Use subagents
- When searching across many files, use the Explore subagent — do not dump search results into main context
- When reviewing code for quality, delegate to a code-reviewer subagent
- Keep the main session context lean and focused on the current task

### Commit often
- After completing each logical sub-task, create a commit
- Do not batch all changes into one commit at the end
- Each commit should be a meaningful unit: "Add intake agent skeleton", not "WIP"

### Stay focused
- Work on the single task assigned — do not fix unrelated issues, refactor surrounding code, or add features not in the issue
- If you notice something that needs fixing, mention it to the human — do not fix it silently

## Before Submitting

1. Run `ruff check src/` and `black --check src/` — fix any issues
2. Run `pytest tests/` — all tests must pass
3. Verify all changes are committed
4. Use `/submit-work` to create the PR

## CLAUDE.md Updates

If you make a mistake that a rule could prevent:
- Suggest adding the rule to CLAUDE.md
- Keep the suggestion specific and concise
- The human decides whether to add it

## Context Management

- If you notice your context is getting large (long conversation, many file reads), proactively suggest starting a fresh session
- Use `/compact` if the conversation is productive but getting long
- Never try to "remember" things across sessions — put important decisions in commit messages or CLAUDE.md
