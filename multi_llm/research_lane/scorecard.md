# Research Lane — Cycle Scorecard (HOW metrics)

Update after each cycle (or every 30 days).  
**Goal:** measure whether Grok/DeepSeek add Δ (D-19); track path-to-promise pressure.

| Metric | RC-000 | RC-001 | RC-002 | Notes |
|---|---|---|---|---|
| Cycle id | RC-000 | RC-001 | RC-002 | |
| Claim types (H_tool / H_market / process) | process | — | process | RC-002 = semantic/identity, not H_market |
| PROPOSAL count | 1 | 0 | 1 done | Grok DONE (turn 2): 5 ordered candidates, UNKNOWN first |
| CRITIQUE count | 0 | 0 | **2 done** | DeepSeek (turn 1) + Gemini (turn 3, re-scoped mid-cycle) |
| EXECUTION_EVIDENCE count | 0 | 0 | **2** | both are gate/verification checks, NOT granted RUN work |
| DECISION count | 1 | 0 | **2 drafts (v1 SUPERSEDED by v2) + 1 principal open** | v1 without packages -> USER AUTHORIZATION REQUIRED; v2 with packages -> **INSUFFICIENT EVIDENCE**. The verdict CHANGED; the executor predicted it would not |
| Unique H from Grok accepted | 0 | 0 | **pending DECISION** | 3 genuinely new (same-side-through-sweep, independent-impulse, misparented); refused to ratify SweepReversal |
| Critic defects pre-execution | 0 | 0 | **2 CONFIRMED + 1 partial** | DeepSeek #1 circularity + #2 denominator (both verified); Gemini's 89.66% mechanism SUPPORTED-not-complete |
| Spec changes from valid critique | 0 | 0 | **4** | dossier rewrite · market_shapes.yaml correction · Gemini prompt re-scope · corpus target moved to Phase-1 admitted |
| Tokens/time cost (rough) | init | init only | ~73 KB x 4 turns + one 96 KB re-run | the re-run changed the verdict; it was worth it |
| Promise rung at end | PL-0 | PL-0 | PL-0 | unchanged by design |
| Phase grant issued | P1 pending | none | none | |
| Survivors / nulls | n/a | n/a | **Position B = INSUFFICIENT EVIDENCE** (both drafts agree) | verdict INSUFFICIENT EVIDENCE; identity UNKNOWN; F-074 intact and shown operating as documented |

> **RC-001 is a stalled cycle** — `initiate_plan.py` wrote stubs for grok + deepseek on
> 2026-07-14 and neither was ever filled. Recorded, not reused; RC-002 is a fresh cycle id.
>
> **D-19 answered early:** DeepSeek's very first package produced **2 confirmed blocking
> defects** that the executor had missed, one of which killed the executor's own headline
> statistic (p 4e-07 -> 0.574 once the denominator was fixed). The critic seat earned its
> place on turn 1; the keep/drop rule's "0 blocking defects" branch does not apply.
>
> **RC-002 is Lane R, semantic/identity, not an ERP experiment.** It resolves a conflict
> between two recorded user authorizations (F-074 vs Position B), one of whose premises the
> executor retracted. Evidence: `cycles/RC-002/EVIDENCE_DOSSIER.md`.

### RC-003 (authorized 2026-09-04, executed same day)

| Metric | RC-003 | Notes |
|---|---|---|
| Cycle id | RC-003 | new evidence cycle, NOT a continuation of RC-002 |
| Claim types | process | geometric + duration; no economic label anywhere |
| PROPOSAL / CRITIQUE count | 0 / 0 | **no relay** — Principal chose build/freeze/approve/run |
| EXECUTION_EVIDENCE count | **1** | the first real granted run in either lane |
| DECISION count | 1 (principal) | authorization only |
| Corpus | **Phase-1 ADMITTED** (47,275 bars) | retires the non-admitted-export caveat |
| Power | n=553 / 1,100 vs floor 150 | not INSUFFICIENT; n_eff blocks 307 / 366 |
| Result | **first non-null on this population** | primary diff +0.4156, CI excludes zero |
| Defects found post-hoc | **2, declared not repaired** | S1 degenerate control; primary control unmatched on proximity |
| Frozen predictions | **1 wrong, 1 weaker, 1 confirmed** | prediction 1 expected a null and did not get one |
| Promise rung at end | PL-0 | unchanged |

> **Lane R produced its first `EXECUTION_EVIDENCE`.** The keep/drop rule's "if cycles produce no
> EXECUTION_EVIDENCE -> LLM theater -> stop Lane R" branch no longer applies. Note the run was
> executed *without* a relay, on a design the relay produced — the seats earned their keep in RC-002
> and were deliberately not re-spent in RC-003.

## Keep / drop rule

After **10 research cycles** (not counting pure process RC-000 unless you count it):

- If Grok unique accepted H = 0 and no useful counters → consider drop diversity seat  
- If DeepSeek blocking defects = 0 across cycles → consider lighter critic  
- If cycles produce no EXECUTION_EVIDENCE → **LLM theater** → stop Lane R until P1/P2
