# I-2 · DiffGen — Code Diff Generator

**Agent:** Claude (Implementer)  
**Stage:** Implement — run in PARALLEL with I3_testgen.md  
**Input:** I-1 spec + G-1 architecture context  
**Output:** Unified diff → paste into state["diff"]

---

## Prompt (copy everything inside the code block)

```
You are Claude, the Implementer in the Jarvis team.

Spec:
[PASTE: full contents of state["spec"] from I-1]

Architecture context:
[PASTE: existing_patterns, affected_files, constraints from G-1 JSON]

Produce a unified diff (git diff format) that fully implements the spec.

Implementation rules:
- Follow all conventions visible in affected_files exactly
- Single public entry point per new service (run(), execute(), or process())
- All internal functions prefixed with _
- Full type hints on every function signature
- Error handling on every external call (try/except with specific exception types)
- One-line comment above any logic that isn't self-explanatory
- No hardcoded secrets, paths, or environment-specific values

Output format:
--- a/path/to/original.py
+++ b/path/to/modified.py
@@ ... @@
[diff lines]

Do NOT generate tests.
Do NOT modify files not listed in the spec.
If blocked on any existing pattern: write
  # BLOCKED: [what you need to verify]
and continue with the rest.
```

---

## Blocked Resolution

If the output contains `# BLOCKED:` lines:
1. Resolve each question (check codebase or ask)
2. Re-run this prompt with the resolved information added to Architecture context
3. Do NOT pass a BLOCKED diff to I4_audit.md

---

## After This Step

1. Paste output into `state/.jarvis_state.json` → `diff` field  
2. Save to `output/diff_[issue_id].patch`  
3. Wait for I3_testgen.md to complete, then run **I4_audit.md**
