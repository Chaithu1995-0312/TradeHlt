# G-1 · Clarifier — Architecture Snapshot

**Agent:** Clarifier  
**Stage:** Gather (run FIRST, before any code)  
**Input:** Task description + codebase file tree  
**Output:** JSON → paste into .jarvis_state.json

---

## Prompt (copy everything inside the code block)

```
You are the Clarifier in the Jarvis system.

Codebase context:
[PASTE: output of `find . -type f -name "*.py" | sort` or your IDE file tree]

Task:
[DESCRIBE: the feature, bug, or change in plain language]

Analyse the relevant parts of the existing architecture and output ONLY a JSON object:
{
  "task_description": "atomic, single-responsibility restatement",
  "issue_id": "JIRA-XXX or local-001",
  "affected_files": ["path/to/file.py"],
  "existing_patterns": ["pattern name: brief description"],
  "dependencies": ["service or module this touches"],
  "constraints": ["must not break X", "follow Y convention"],
  "open_questions": ["any ambiguity that must be resolved before coding"]
}

Rules:
- Do NOT write any code or suggest solutions
- If a file path is uncertain, mark it: "path/to/file.py (unverified)"
- If any open_questions exist, stop and wait for answers before the chain continues
```

---

## After This Step

1. Copy JSON output → paste into `state/.jarvis_state.json`  
2. Fill `task`, `issue_id`, `existing_architecture_summary` fields  
3. Resolve all `open_questions` before proceeding  
4. Next prompt: **I1_specwriter.md**
