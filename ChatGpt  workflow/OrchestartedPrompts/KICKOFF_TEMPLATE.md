# KICKOFF TEMPLATE — Start Any Task Here

Copy this file, fill in the bracketed sections, then feed each [[AGENT]] block to the correct model.

---

## Task Information

```json
{
  "task": "[ONE SENTENCE DESCRIPTION]",
  "issue_id": "[JIRA-XXX or local-001]",
  "branch": "[feature/JIRA-XXX-short-description]",
  "existing_architecture_summary": "",
  "spec": "",
  "diff": "",
  "tests": "",
  "audit": "",
  "commit_msg": "",
  "pr_body": "",
  "changelog_entry": ""
}
```

Save this as: `state/.jarvis_state.json` — update after each agent completes.

---

## Step 1 — Clarify & Analyse [[AGENT:Clarifier]]

**Paste into a fresh Claude/ChatGPT chat:**

```
You are the Clarifier in the Jarvis system.

Codebase context:
[PASTE: find . -type f -name "*.py" | sort | head -80]

Task: [SAME AS task FIELD ABOVE]

Output ONLY a JSON object:
{
  "task_description": "atomic restatement",
  "issue_id": "[your issue id]",
  "affected_files": ["path/to/file.py"],
  "existing_patterns": ["pattern: description"],
  "dependencies": ["services touched"],
  "constraints": ["must not break X"],
  "open_questions": []
}
Do not write code. Mark uncertain paths as "(unverified)".
```

**→ Save output to state["existing_architecture_summary"]**  
**→ Resolve any open_questions before Step 2**

---

## Step 2 — Create Branch

```bash
git checkout -b [BRANCH NAME FROM STATE]
```

---

## Step 3 — Write Spec [[AGENT:SpecWriter]]

**Paste into ChatGPT (Architect):**

```
You are the SpecWriter in the Jarvis system.

Task: [state.task_description]
Architecture: [state.existing_architecture_summary]
Constraints: [state.constraints]

Write a spec covering:
1. What must be built (no code)
2. Files: exact paths of every file to create/modify
3. Public interface: signatures + docstrings for new services
4. Acceptance criteria: 3-5 in Given/When/Then format
5. Assumptions and out-of-scope items

Max 400 words. No code blocks.
```

**→ Save output to state["spec"] and output/spec_[issue_id].md**

---

## Step 4 — Generate Diff + Tests (PARALLEL)

Open TWO separate chat windows simultaneously.

**Window A — [[AGENT:DiffGen]] → paste I2_diffgen.md prompt**  
**Window B — [[AGENT:TestGen]] → paste I3_testgen.md prompt**

Both use: `state["spec"]` + `state["existing_architecture_summary"]`

**→ Save diff to state["diff"] and output/diff_[issue_id].patch**  
**→ Save tests to state["tests"] and output/test_[issue_id].py**

---

## Step 5 — Review Point

Apply the diff and run tests locally:

```bash
git apply output/diff_[issue_id].patch
cp output/test_[issue_id].py tests/
pytest tests/test_[service_name].py -v
```

**Only continue if tests pass.**

---

## Step 6 — Audit [[AGENT:Auditor]]

**Paste into DeepSeek:**

```
You are DeepSeek, the Auditor in the Jarvis team.
Spec: [state.spec]
Diff: [state.diff]
Tests: [state.tests]
[use full I4_audit.md prompt]
```

**→ If SIGN-OFF: approved → continue**  
**→ If needs revision → fix and re-run steps 4-6**

---

## Step 7 — Commit

```
You are the CommitWriter.
spec: [state.spec]
diff summary: [2-line summary of changes]
issue_id: [state.issue_id]

Write a conventional commit message:
type(scope): short description

Body: what changed and why (3-4 lines max)
Footer: Refs [issue_id]
```

```bash
git add -p
git commit -m "[commit message from above]"
```

---

## Step 8 — PR Description

```
You are the PRWriter.
branch: [state.branch]
commit_msg: [state.commit_msg]
spec: [state.spec]
issue_id: [state.issue_id]

Write a PR description with sections:
## What changed
## Why
## How to test
## Checklist
- [ ] Tests pass
- [ ] dependencies.dot updated
- [ ] Line explanations added to logs/
```

---

## Step 9 — Changelog Entry

```
You are the ChangelogWriter.
issue_id: [state.issue_id]
spec summary: [2-sentence summary]

Write a CHANGELOG.md entry in Keep a Changelog format:
### Added / Changed / Fixed
- [Description] ([issue_id])
```

---

## Step 10 — Finalize

```bash
git push origin [state.branch]
# Open PR, assign reviewer, close issue
node build_doc.js  # Regenerate prompt reference doc
```
