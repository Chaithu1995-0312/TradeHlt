---
name: verify-claims
description: Verify every factual claim in a doc/spec against repo source before acting on it
---

For the document or claim set I point you at:

1. Extract every checkable assertion into a numbered table (claim | where it would live | how to check).
2. Verify EACH one with grep/read against primary source. Do not infer from other docs or prior findings.
3. Mark each: CONFIRMED (with file:line), REFUTED (with counter-evidence), or UNVERIFIABLE.
4. Explicitly flag any claim that rests on a stale summary/status doc.
5. Report the table FIRST. Do not write any code, docs, or plans until I approve.

## Repo-specific

- **Default-STALE sources** (AGENTS.md §1.1): a session-log summary, a usage/insights report, a
  generated status doc, or another model's analysis is an input to verification, never evidence.
  Findings `Evidence:` blocks may themselves be bug-contaminated — check the source they cite, not
  the citation.
- **Repo nouns, relationships, symbols, findings, and JSONL claims have a grounding tool** — use it
  instead of asserting (AGENTS.md §6.7):
  `python scripts/governance/query_semantic_os.py --ground --kind NOUN|RELATIONSHIP|IMPLEMENTATION|EVIDENCE|JSONL|CONCEPT|REPRESENTATION --token <id>`
  Anything other than `GROUNDED` means do not introduce the claim; report the status verbatim.
  Claims about what a trading concept or code field MEANS use `--kind CONCEPT` / `REPRESENTATION`
  (Semantic OS v2, `docs/memory/semantic-os-memory.md`); `NOUN` never finds v2 concepts.
- **Runtime/config claims resolve through §4.0 `ORIENT_RUNTIME`**, not memory: read
  `configs/production/ACTIVE_VERSION` first.
- A claim about what a test enforces is verified by **running** it, not by reading its name.
- When two authorities disagree and the winner is unclear, surface a §6.2 rule-3 `TruthConflict`
  (source A, source B, evidence, impact, recommendation) — do not pick a winner silently.
