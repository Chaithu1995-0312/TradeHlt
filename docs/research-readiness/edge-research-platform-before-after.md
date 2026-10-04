# Edge Research Platform — Before vs After Full Design Implementation

> **Purpose:** One clear picture of **what changes** when the entire phased plan (P0–P7) is done.  
> **Baseline (“Before”):** repository + program state as of design freeze 2026-07-14.  
> **After:** intended end-state if P0–P7 complete successfully — **not a claim that edge exists**.  
> **Plan:** [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md)

---

## One-sentence contrast

| | |
|---|---|
| **Before** | A rich trading **codebase** with engines, governance, and many null research results — but weak guarantees that numbers are trustworthy, opportunities are honest, multi-LLM work is non-echoing, or capital is gated by survivors. Easy to **falsely** promise wealth; hard to **earn** one. |
| **After** | A **closed-loop research organization** that both (1) refuses false promises and (2) **moves toward an earned wealth promise**: integrity → search new info → PL-3 candidates → shadow (PL-4) → micro capital (PL-5) → scale only if live holds. Null is allowed; **lab-forever without search pressure is not the goal**. |

---

## 1. What the project *is*

| Dimension | **Before** | **After (full design implemented)** |
|---|---|---|
| Identity | “Sophisticated multi-engine trading system” (easy to oversell) | Research platform **aiming to earn** a conditional wealth promise (D-01 + Promise Ladder) |
| Success definition | Better backtests / more modules | Raise **P(durable wealth)** via earned PL rungs; clean null only after real search (D-02) |
| Authority | Often confused with “model exists / tests green” | Only **surviving evidence** after gates (D-03); PL-5 for micro capital speech |
| Trader pitch | Risk of “it will make money” | “No promise until PL-3+; path designed **toward** promise, not away from it” |

---

## 2. Trust in numbers and tools

| Dimension | **Before** | **After** |
|---|---|---|
| Backtest / PF / E / WR | Often treated as truth when a run “looked right” | Default **`UNTRUSTED_RAW`** until validation flow reviewed vs intent (D-04) |
| LLM statements | Easy to treat as evidence | **NON_EVIDENCE** until artifact + quote-check (D-05) |
| Failure modes | Informal | Named **H1 invent / H2 misread / H3 wrong path** with tests |
| Run identity | Command may be forgotten | Every serious run has **`run_manifest`** (path, flags, ACTIVE_VERSION, lens, costs, labels) |
| Lens | Easy to mix CRT-only research with “full fusion” claims | Every claim **names lens** (gate-OFF vs gate-ON) (D-10) |

---

## 3. Research spine (candle → decision → learning)

| Step | **Before** | **After** |
|---|---|---|
| Data | CSV / fetchers exist; L3 integrity uneven | Still file-backed; **network/MT5 checks** optional but defined (L3/L4) |
| Features | Ontology / certification in progress | Same WHAT layer; pack and factory use **declared** features |
| Events / opportunities | CRT + opportunity streams; **F-022** contamination risk | **Outcome factory**: neutral seeds + **forward_walk** honest labels |
| Multi-engine scores | Engines exist; research often CRT-only; some inert (BitNet/TradeNet) | Same opportunity → **evidence channels**; zero-Δ **demoted**; inert stay off until Δ |
| Store disagreement | Partial logs / fusion meta | Structured opportunity + engine score table + disagreement retained |
| Predict vs outcome | Qualification exists but label hygiene uneven | Systematic **intended vs produced** + M4-style economic gates |
| Demotion | Ad hoc / findings prose | **Demotion ledger** (describe vs decide) from measured Δ |
| Decision policy | Full stack in code; live structural issues (F-048 class) | Policy only from **survivors**; non-survivors cannot buy authority |
| OOS / costs / regimes | Used in many programs; not one factory standard | Standard factory + costs + dual-lens discipline |
| Shadow / capital | Live path incomplete / PnL unverified (F-010) | **Dry shadow** path proven; capital only P7 + dual-ack |
| Monitor edge decay | Weak closed loop | Continuous monitor only after capital path exists |

### Visual

```text
BEFORE (typical path risk)
  data → features → CRT/entries → pretty backtest → hope
  (labels?, lens?, LLM summary?, model “exists”?)

AFTER (designed path)
  data → verified features → events → opportunity population
       → engines evidence (stored)
       → honest outcomes (factory)
       → incremental value / demote
       → survivors only → policy
       → OOS/costs → shadow → small capital → monitor
       (every step: manifest + trust token)
```

---

## 4. Synthetic fixture (story you locked)

| Dimension | **Before design work** | **After full design** |
|---|---|---|
| Intentional 4h geometry | Did not exist as golden | Exists: sweep 98.5 → … → TP_HIT R=2, entry idx 41 |
| Engine scores on pack | N/A or invented | **Real callables**, intended = produced (CRT/G/Z/RR) |
| Story edit | N/A | Still **CODE** in generator unless later externalized (D-23) |
| CI | No synth golden | **P1:** pytest golden CRITICAL_PASS |

---

## 5. Multi-LLM / research organization

| Dimension | **Before** | **After** |
|---|---|---|
| Multi-model use | You copy-paste; risk of **echo chamber** | Asymmetric roles + **no voting** (D-08) |
| Output types | Free chat + SESSION LOG + turn_ledger | Only **PROPOSAL / CRITIQUE / EXECUTION_EVIDENCE / DECISION** |
| Implementation lane | `multi_llm/` (DeepSeek plan → … → Claude) | **Kept** (dual-lane) unless AMB-01 supersedes |
| Research lane | Informal | Architect / diversity / critic / Claude executor + You capital |
| Model value | Assumed useful | **Measured** over 10 cycles; drop Grok/DeepSeek if zero Δ (D-19) |
| Bridge cost | High manual paste | Packages on disk; You still own capital |

---

## 6. Workstreams & phases (what “implemented” means)

| Phase | Before | After complete |
|---|---|---|
| **P0** | AMB open, plan draft | Defaults frozen; grant path clear |
| **P1** | Testing **design** only; synth manual | Markers, manifests, AH/VP tests, synth **CI golden** |
| **P2** | `forward_walk` exists; no program factory | Versioned opportunity+outcome factory + floors |
| **P3** | Engines run; demotion informal | Ablation Δ table + demotion ledger |
| **P4** | OI deferred; OHLCV nulls many | At least one **new-info** prereg closed (null OK) |
| **P5** | dry_run pieces / live_smoke exist | End-to-end **shadow dry** + manifest |
| **P6** | multi_llm for code delivery | Research cycle ledger + scorecard + keep/drop |
| **P7** | No governed micro-capital ritual | Dual-ack capital path **or** explicitly never opened |

---

## 7. Artifacts: before vs after

| Kind | **Before** | **After** |
|---|---|---|
| Program docs | Scattered session insight | Decision board + phased plan + I/O + testing + multi-LLM design |
| Run truth | Chat + ad hoc results folders | `run_manifest` + assertions + hash |
| Synth | — | `data/synthetic/erp_4h_m15/*` + generator |
| Factory | Opportunities / mixed labels | Clean population + re-derived outcomes |
| Findings | Living `current-findings.md` | Same **plus** DECISION co-sign before Validated flips |
| Research cycles | Chat threads | `research_cycle_ledger.jsonl` (4 kinds) |
| Capital | Informal / blocked | Checklist + env dual-ack only |

---

## 8. What does **not** automatically change (even after full implement)

These stay true unless **evidence** overturns them:

| Item | Note |
|---|---|
| **No guaranteed profit** | Design never promises edge (D-01) |
| Prior nulls (F-019 family, carry, etc.) | Still valid under their scopes until reopened with new ontology/data |
| BitNet/TradeNet | Stay off until ΔG001 |
| RR polarity ≠ true RR | Naming honesty remains (D-11) |
| You as capital owner | Never automated away (D-20) |
| File-backed, no DB | Unchanged stack choice |
| WHAT/WHO/HOW live spine | Still the production authority model; synth story is separate CODE until externalized |

**After implementation success can look like either:**

```text
A) One or more small, cost-surviving, replicated edges → shadow → micro capital
B) Honest multi-axis nulls + demoted dead models + faster kill of bad ideas
```

Both are **wins**. Only (A) allows P7.

---

## 9. Operator experience: before vs after

### Before

```text
Idea → ask LLM → run a script → read summary → maybe promote hope
You paste between Grok / ChatGPT / Claude / DeepSeek
Hard to know: wrong lens? bad labels? invented metric?
```

### After

```text
PROPOSAL (frozen H_tool or H_market)
  → CRITIQUE
  → freeze prereg
  → Claude EXECUTION_EVIDENCE (manifest + compare)
  → DECISION (retire / repair / replicate / next gate)
  → You authorize only expensive / capital steps
```

---

## 10. Risk profile

| Risk | **Before** | **After** |
|---|---|---|
| Self-deception via backtests | High | Lower (trust gate + factory) |
| LLM echo chamber | High | Lower if RCP used + measured |
| Years of infra without alpha | High | Still real — mitigated by demotion + new-info phase + stop rules |
| Premature capital | Possible | Structurally blocked until P7 gates |
| LLM theater (tokens without falsification rate) | High | Measured in P6 scorecard |

---

## 11. Checklist: “entire design implemented”

Tick only when true:

- [ ] P0 frozen (AMB defaults written)  
- [ ] P1 CI: AH/VP + synth golden green  
- [ ] P2 factory artifact + floors + contamination report  
- [ ] P3 demotion ledger from measured Δ  
- [ ] P4 at least one new-info prereg closed  
- [ ] P5 dry shadow path with manifest  
- [ ] P6 ten cycles + model keep/drop recorded  
- [ ] P7 either dual-ack micro run **or** explicit “not opened” DECISION  
- [ ] No production authority granted without Stage-3-class survivor  
- [ ] Decision board still matches reality (update if reversed)

---

## 12. Where to read next

| Doc | Role |
|---|---|
| This file | Before / after narrative |
| [Phased plan](edge-research-platform-phased-plan.md) | How to get from before → after |
| [Decision board](erp-decision-board-and-story-authority.md) | Locked D-* |
| [Program](edge-research-platform-program.md) | Living status |

---

*Before = capable lab with weak epistemic clamps.  
After = same lab with clamps, factory, demotion, and capital only for survivors — still no promise of wealth.*
