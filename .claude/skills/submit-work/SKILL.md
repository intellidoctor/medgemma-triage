---
name: submit-work
description: "Submit completed work as a pull request. Use when a team member says 'submit my work', 'create a PR', 'I am done with this issue', 'open a pull request', 'send for review', or any request to finalize and submit work on the current branch. Handles: lint, format, test, commit, push, create PR linking the issue, and update issue status."
---

# Submit Work Workflow

## Procedure

1. **Identify the current issue** from the branch name:
   ```bash
   git branch --show-current
   ```
   Extract issue number N from `feat/N-short-description`.

2. **Lint and format**:
   ```bash
   ruff check src/ --fix
   black src/
   ```
   Fix issues automatically. If unfixable errors remain, report them and stop.

3. **Run tests**:
   ```bash
   pytest tests/
   ```
   If tests fail, report failures and stop. Do not submit broken code.

4. **Stage and commit**:
   ```bash
   git add -A
   git commit -m "<meaningful message describing what was done>"
   ```
   Commit message should reference the issue: `feat(#N): <what changed>`.

5. **Push the branch**:
   ```bash
   git push -u origin feat/N-short-description
   ```

6. **Create the pull request**:
   ```
   mcp__github__create_pull_request(
     owner: "intellidoctor",
     repo: "medgemma-triage",
     title: "<concise title>",
     head: "feat/N-short-description",
     base: "main",
     body: "Closes #N\n\n## Summary\n<bullet points>\n\n## Test plan\n<how it was tested>"
   )
   ```
   Always include `Closes #N` to auto-link the issue.

7. **Confirm** — print summary with the PR URL.
