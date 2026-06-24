> Created: 2026-06-06 · Updated: 2026-06-06 · Milestone: architecture (pre-autonomy)

# Plan: Autonomy Preconditions Document

## Context

The user wants an autonomous n8n agent eventually, but correctly argues the next bottleneck is **not** automation — it's a **frozen objective function + frozen accept/kill/escalate rules + the two safety blockers (F-006, F-010)**. Building a research engine before freezing what it optimizes = "faster mistakes." So the first deliverable is **not** an autonomy *architecture* doc (`agent_state.json`, decision policy) — it is an **Autonomy Preconditions** doc that freezes the six things that must be true before autonomy is safe or useful.

This doc does not build the agent. It defines the contract the agent will later be held to, citing thresholds that **already exist in code** (so the rubric is real, not invented).

**Deliverable:** `docs/architecture/autonomy-preconditions.md` + discoverability hooks.

---

## The six preconditions (each = a section with a frozen definition + done-criteria checkbox)

### Precondition 0 — Objective function (frozen)
Two layers, stated as constrained optimization:
- **Hard constraints (never traded off):** the 7 invariants from [`goal.md`](docs/architecture/goal.md) §3 + the priority hierarchy *replay correctness > explainability > telemetry continuity > advisory-AI > (structure validity ≠ execution validity)*.
- **Economic objective (what the agent maximizes within constraints):** selection quality + throughput (N), per **F-001** (intelligence is NOT the constraint), **F-002** (edge is in selection, not pattern identity), **F-003** (throughput is the ROI lever). Profit is the downstream result, not the proximate target.
- Frozen statement: *"The agent maximizes risk-adjusted throughput of high-selection-quality trades, subject to the goal.md invariants as hard constraints. It never optimizes activity (experiment count) as a proxy."*

### Precondition 1 — Promotion / acceptance rubric (frozen, cite code)
Reproduce the existing thresholds as the frozen accept gate (all from real code):
| Gate | Threshold | Source |
|---|---|---|
| Min trades/instrument (HARD) | 10 | `config_validator.py:91` |
| Max drawdown/instrument (HARD) | 35% | `config_validator.py:92` |
| Min fitness score (HARD) | 0.15 | `config_validator.py:95` |
| Min win rate (SOFT) | 35% | `config_validator.py:93` |
| Min expectancy (SOFT) | −0.5R | `config_validator.py:94` |
| Max cross-instrument score std_dev (SOFT) | 0.3 | `config_validator.py:96` |
| APPROVE gate | `decision == "APPROVE"` | `promotion_manager.py:151` |
| Shadow sample size | ≥ 30 trades | `shadow_promotion_gate.py:217` |
| Shadow performance | `shadow_pnl > baseline_pnl` | `shadow_promotion_gate.py:228` |

Plus a **research-loop acceptance rubric** (NEW — does not exist today): turn Claude's prose verdicts ("interesting / promising / dead end / noise") into numbers. Proposed: a sweep result is *actionable* only if it beats baseline PF by a margin AND clears a minimum-N significance floor (directly addresses the N=5 noise failure in the Phase-2b memory). Mark this as the one genuinely missing acceptance artifact.

### Precondition 2 — Kill / runtime-risk rubric (frozen, cite code)
| Limit | Threshold | Source |
|---|---|---|
| Max daily loss (kill switch) | 3.0% | `ultron_risk_gate.py:280` |
| Max portfolio risk | 5.0% | `ultron_risk_gate.py:305` |
| Max trades/day | 10 | `ultron_risk_gate.py:275` |
| Min R:R ratio | 1.5 | `ultron_risk_gate.py:243` |
| Max per-trade risk | 1.0% | `ultron_risk_gate.py:301` |

Plus **initiative kill conditions** = the Funding Ledger `Reopen Conditions` (current-findings.md): KILLED = Liquidity V2 / TradeNet V2 / Probability Surface V2; FROZEN = BitNet V2. Rule: the agent may **never** silently revive a KILLED/FROZEN initiative (CLAUDE.md §6.2).

### Precondition 3 — Escalation rubric (frozen, NEW)
Hard machine rules for when the agent must stop and hand to the human (today this is Claude's judgment). Escalate when: a goal.md invariant would be violated; a KILLED/FROZEN reopen condition triggers; UltronRiskGate kill switch fires; a result is statistically ambiguous (fails the Precondition-1 significance floor); or a promotion would proceed on backtest-only evidence while **F-010 is OPEN**.

### Precondition 4 — F-006 enforced (safety blocker)
Done-criteria: `config_integrity.py` (`validation_summary_is_fresh` / `active_version_is_governed`) is called on a **runtime path** (backtest_v2 / live_engine_hook / promotion_manager), not just the cutover CLI. Today its only caller is the one-off cutover script — an autonomous agent through an unwired gate is the single highest-risk failure. This precondition *names* the work; the wiring is a downstream code task, not part of this doc.

### Precondition 5 — F-010 resolved (safety blocker)
Done-criteria: live (or live-equivalent) PnL verified through ExecutionPlannerV1_2 + UltronRiskGate, which are live-only and absent from the backtest spine that produced the headline ROI. Until closed, the agent is **forbidden from autonomous promotion** (enforced via Precondition 3 escalation).

---

## Doc structure

`docs/architecture/autonomy-preconditions.md`:
1. **Context / thesis** — autonomy is not the next bottleneck; the objective function + rules are. (1 para, cite the user's "faster mistakes" framing.)
2. **The preconditions checklist** — six `[ ]` items up top for at-a-glance status.
3. **One section per precondition** (0–5) with frozen definition + done-criteria + code citations (`path:line · Symbol` per CLAUDE.md §6.3).
4. **Sequencing** — Tier 0 (F-006, F-010) → Tier 1 (objective + decision policy) → Tier 2 (acceptance rubric) → Tier 3 (run ledger). State: only after all six are `[x]` does autonomy-layer design begin.
5. **What this doc is NOT** — not the autonomy architecture; agent_state.json / decision_policy.json / run_ledger.jsonl come *after*.

---

## Discoverability hooks (consistent with the prior catalog lesson)

- `README.md` Tier 3 table — add a row for `autonomy-preconditions.md`.
- `CLAUDE.md` §2 companion-docs table — add a row.
- `docs/architecture/roadmap.md` — add a note that autonomy is gated behind this checklist (read-only confirm it fits a track; if a clean row exists, add it).

---

## Files Modified

| File | Change |
|---|---|
| `docs/architecture/autonomy-preconditions.md` | **NEW** — the frozen six-precondition doc |
| `README.md` | +1 Tier 3 row |
| `CLAUDE.md` | +1 companion-docs row |
| `docs/architecture/roadmap.md` | +1 note/row gating autonomy behind the checklist |

No code changes. F-006/F-010 wiring and the autonomy layer itself are explicitly out of scope — this doc defines the contract they must satisfy.

---

## Verification

1. Read `autonomy-preconditions.md` — confirm all six sections present, each with a done-criteria checkbox, and that every cited threshold matches the code (`config_validator.py:91/92/95`, `ultron_risk_gate.py:280/305/275/243/301`, `shadow_promotion_gate.py:217/228`, `promotion_manager.py:151`).
2. Confirm the objective-function section states BOTH the goal.md invariant hierarchy (hard constraint) AND the selection+throughput economic objective (F-001/F-002/F-003).
3. Confirm F-006 and F-010 are framed as Tier-0 blockers with explicit done-criteria, and that autonomous promotion is forbidden while F-010 is OPEN.
4. Confirm README + CLAUDE.md + roadmap point to the new doc.
5. Doc-only — run `pytest tests/test_doc_citations.py` to confirm the new `path:line · Symbol` citations resolve.
