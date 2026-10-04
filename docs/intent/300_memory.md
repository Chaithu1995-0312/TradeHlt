# Domain Contract: Memory

## Purpose
Preserve every decision, finding, belief update, and experiment outcome so that future sessions (human or LLM) can build on accumulated knowledge without re-deriving it.

## Why does this exist?
The user thought: *"Experiments should not be forgotten."* The repository is not just code — it is a knowledge substrate that compounds intelligence over time. A finding discovered and lost is worse than never discovering it.

**Evidence:** intelligence-compounding.md:127; CLAUDE.md §6.1 — Confidence: Certain

## Authority
- **Owns:** Living repository truths (current-findings.md), SESSION LOG (assistant_project.md), intelligence doctrine.
- **Decides:** Which conclusions are repository truths (VALIDATED/OPEN/DURABLE/SUPERSEDED).
- **Must NOT:** Let any actionable finding exist only in a session log without being captured in current-findings.md.
- **Must NOT:** Delete or truncate history — superseded findings stay as rows.

## Must (Required Behaviors)
1. Every response must append a SESSION LOG entry to assistant_project.md (CLAUDE.md §6).
2. Every validated or overturned conclusion must be added/flipped in current-findings.md in the same turn.
3. current-findings.md must maintain a schema with: Type, Status, Confidence, Validated, Revalidate-by, Evidence, Reversal.
4. test_current_findings.py must enforce synchronization between Truths Index and current-findings.md.
5. Superseded/retired findings must remain as rows (never deleted).

## Must Never (Forbidden Behaviors)
1. Must NEVER let a research finding exist only in a session log without being formalized in current-findings.md.
2. Must NEVER delete a finding — mark SUPERSEDED or RETIRED.
3. Must NEVER allow CLAUDE.md's Truths Index to diverge from current-findings.md (test-enforced).
4. Must NEVER silently revive a KILLED/FROZEN initiative without meeting its Reopen Conditions.

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| Finding not captured (exists only in session memory) | No automated detection | HIGH |
| Finding overturned without flipping status | Manual review | HIGH |
| KILLED initiative revived without reopen conditions | Manual review | MEDIUM |
| Revalidate-by deadline passed | CI failure (test_current_findings) | MEDIUM |

## Economic Meaning
The compounded intelligence system is the repository's #1 asset. A single preserved null finding (e.g., "EMA gate non-binding") prevents months of wasted exploration. The cost of fragmented meaning (knowledge exists but is scattered) is the primary intelligence loss vector — not missing data.

**Evidence:** CLAUDE.md §6.1; intelligence-compounding.md — Confidence: Certain

## Unknowns
- Whether the SESSION LOG mandate is sufficient for human readers (it's designed for LLM consumption).
- Whether the Revalidate-by deadlines are realistic (90d for non-durable findings).

## Evidence
- CLAUDE.md §6 (Persistent Logging Mandate) — Confidence: Certain
- CLAUDE.md §6.1 (Intelligence Compounding Doctrine) — Confidence: Certain
- CLAUDE.md §6.2 (Truth Maintenance Doctrine) — Confidence: Certain
- test_current_findings.py (enforcement) — Confidence: Certain