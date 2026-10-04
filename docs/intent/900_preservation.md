# Domain Contract: Preservation (Truth Maintenance)

## Purpose
Prevent silent truth divergence between code, docs, tests, findings, and runtime. Detect and resolve conflicts before they propagate to other readers.

## Why does this exist?
The user thought: *"Most 'bugs' in this repo are documentation entropy — uncontrolled truth duplication."* The F-007→F-016 correction (branch-scoped v4→v2) is a worked example of this failure mode.

**Evidence:** CLAUDE.md §6.2; F-016 — Confidence: Certain

## Authority
- **Owns:** The 4 authority tiers (runtime > code schema > promotion_log > session memory).
- **Decides:** When a conflict is DOC_DRIFT (code wins → fix the doc) vs. CODE_DRIFT (doc wins → fix the code).
- **Must NOT:** Silently resolve a TruthConflict — always surface it with evidence and recommendation.
- **Must NOT:** Delete history — mark SUPERSEDED/RETIRED.

## Must (Required Behaviors)
1. Tiers 0–4 precedence must be respected at all times: runtime > schema > promotion_log > memory.
2. Every code change must check corresponding docs, tests, findings, and topic files.
3. Every doc change must check corresponding code and tests.
4. Every finding change must check indexes and citations.
5. test_current_findings, test_doc_citations, test_topic_docs must remain synchronized.

## Must Never (Forbidden Behaviors)
1. Must NEVER silently resolve a conflict between authorities (surface TruthConflict).
2. Must NEVER delete a finding — mark SUPERSEDED or RETIRED.
3. Must NEVER allow a stale finding to be cited as active (flip Status immediately upon overturning).
4. Must NEVER assume branch-global truth — state branch when applicable.

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| ACTIVE_VERSION suffix mismatch (deepdeektry) | config_integrity (ORPHANED) | HIGH (happened) |
| Doc path:line citation stale | test_doc_citations | MEDIUM |
| Topic doc stale | test_topic_docs | MEDIUM |
| Finding index ↔ findings mismatch | test_current_findings | MEDIUM |
| Finding not filed in same turn | No automated detection | MEDIUM |

## Economic Meaning
Documentation drift costs compound exponentially. Each reader who trusts stale docs and makes a wrong decision creates a cost that grows with the number of readers. The enforcement tests are cheap insurance against this. The F-007→F-016 correction proves both the failure mode and the cure.

**Evidence:** CLAUDE.md §6.2 — Confidence: Certain

## Evidence
- CLAUDE.md §4.0 (Active Version Resolution) — Confidence: Certain
- CLAUDE.md §6.2 (Truth Maintenance Doctrine) — Confidence: Certain
- test_current_findings.py (synchronization) — Confidence: Certain
- test_doc_citations.py (citation validity) — Confidence: Certain
- test_topic_docs.py (topic drift) — Confidence: Certain