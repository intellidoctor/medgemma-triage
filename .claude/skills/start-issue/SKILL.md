---
name: start-issue
description: "Start work on a GitHub issue. Use when a team member says 'start work on issue #N', 'pick up an issue', 'what should I work on', 'grab an issue', 'next task', or any request to begin working on a task from the board. Handles: check GitHub issues, claim an unassigned issue, create a feature branch, optionally set up a git worktree, update issue status, and read the issue to understand the task."
---

# Start Issue Workflow

## Procedure

1. **If no issue number provided**, list open issues:
   ```
   mcp__github__list_issues(owner: "intellidoctor", repo: "medgemma-triage", state: "open")
   ```
   Present available issues and ask which one to work on.

2. **Read the issue** to understand the full task:
   ```
   mcp__github__get_issue(owner: "intellidoctor", repo: "medgemma-triage", issue_number: N)
   ```
   Display the issue title and body.

3. **Assign the issue** if unassigned:
   ```
   mcp__github__update_issue(owner: "intellidoctor", repo: "medgemma-triage", issue_number: N, assignees: ["username"])
   ```

4. **Create the feature branch** from `main`:
   ```bash
   git fetch origin
   git checkout -b feat/N-short-description origin/main
   ```
   Derive `short-description` from issue title: lowercase, hyphens, max 4 words.
   Example: Issue #3 "Image analysis agent" → `feat/3-image-analysis-agent`

5. **Worktree** — ask if doing parallel work:
   - Yes: `git worktree add ../worktree-issue-N feat/N-short-description`
   - No: continue in current directory

6. **Confirm** — print summary:
   ```
   Ready to work on Issue #N: <title>
   Branch: feat/N-short-description
   ```
   Then begin working on the task.
