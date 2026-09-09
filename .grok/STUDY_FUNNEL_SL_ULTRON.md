# Study: structure completion / inverted SL / Ultron

**Corpus:** NS walk (`MC-CRT-SB-XAUUSD-M15-NS-V1`), 47,275 XAUUSD M15 bars.  
**Source of counts:** `XAUUSD_events.jsonl` + NS run log.  
**Not an edge. Not a production change.**

Two different “Ultrons” exist. This study names both.

| Name | File | Question | Binding on NS? |
|---|---|---|---|
| `UltronRiskEngine` | `crt_engine_v2.py` | Is the setup’s fused score S ≥ 0.30? | **Yes** (3 rejects logged) |
| `UltronRiskGate` | `ultron_risk_gate.py` | May we size this plan? | **No** — summary `rejected_trades=0` |

The walk logs that said `CRT.UltronRisk | REJECTED | S=0.289 < tier_2=0.3` are the **engine**, not the capital gate.

---

# 1. Structure completion

## RECOMMENDATION
KEEP CURRENT ARCHITECTURE for the funnel identity. The NS book dies in the **middle** of the graph, not at session.

## CONFIDENCE
HIGH on transition counts (events file). MEDIUM on RESET “visits vs bar-hours.”

## DOMAIN REASONING
A CRT setup is a sequence, not a score: range is raided, price impulsively leaves, expands, then comes back. Most raids never complete. That is normal market behavior. A “complete” path to a trade is rare by construction.

## CURRENT BEHAVIOR (NS events)

Legal golden-path transitions:

| Step | Count | Keep rate vs previous |
|---|---:|---:|
| RANGE → SWEEP | 1792 | — |
| SWEEP → DISPLACEMENT | 399 | 22% |
| DISPLACEMENT → EXPANSION | 142 | 36% |
| (+ SWEEP → EXPANSION shadow) | 6 | — |
| EXPANSION → RETEST | 24 | ~16% of 148 expansions |
| RETEST → EXECUTION | 23 | 96% |
| TRADE_OPENED | 16 | 70% of EXECUTION |

Bar-hours (summary `state_distribution`): RANGE 22,162 · SWEEP 15,564 · DISPLACEMENT 778 · EXPANSION 8,632 · RETEST 26 · EXECUTION 29 · SHADOW_PENDING 6.

RESET families (not all kill a setup at the same place):

| Family | Count |
|---|---:|
| HTF clock change | 2465 |
| 50% retrace (directional, post F-074-adjacent rule) | 166 |
| 1.618 extension | 109 |
| Post-resolution | 21 |
| Session gap > 120 min | 121 |
| Soft-confirmation timeout | 1 |

HTF resets are the loudest RESET *event* (every 16 M15 bars). EXPANSION is exempt from HTF kill (prior study). The **completion** bind is SWEEP→DISP (78% of sweeps die) and EXP→RETEST (most expansions never get a legal retest).

## INTENDED SEMANTICS
Universal: most liquidity raids are not trades.  
Repo: `VALID_TRANSITIONS` + F-074 directional displacement. Structure ≠ execution.

## CODEBASE EVIDENCE
- Transitions: NS `XAUUSD_events.jsonl` (`STATE_TRANSITION`)
- Graph: `state_identity.py` `VALID_TRANSITIONS`
- Retrace: `ResetLogic` directional 50% (F-074-era)

## CLASSIFICATION
**INTENTIONAL SEMANTIC SEPARATION** — rare completion is the structure contract working, not a missing session.

---

# 2. Inverted SL

## RECOMMENDATION
KEEP CURRENT ARCHITECTURE. Fail-closed when the stop would sit on the wrong side of entry.

## CONFIDENCE
HIGH (7 log lines, source at `crt_engine_v2.py:2371-2386`).

## DOMAIN REASONING
Stop belongs **beyond** the displacement extreme (the candle that left the range). Entry is the retest close. If the retest close is already past that extreme (plus the 0.2 ATR buffer), there is no structural room. Taking that trade would mean “stop is in the profit direction.” That is not a trade.

## CURRENT BEHAVIOR
`ExecutionEngine.build_trade`:

- LONG SL = displacement.low − 0.2×ATR  
- SHORT SL = displacement.high + 0.2×ATR  
- Reject if LONG and sl ≥ entry, or SHORT and sl ≤ entry.

NS log: **7** inverted SL (4 SHORT, 3 LONG). Arithmetic check: 23 risk-approved − 7 inverted = 16 TRADE_OPENED.

Examples (NS): SHORT entry 2329.94 / sl 2327.81 (sl below entry on a short). LONG entry 2640.86 / sl 2644.12 (sl above entry on a long).

No event row is emitted (function returns `None`). Invisible in `events.jsonl` unless you have the execution log.

## INTENDED SEMANTICS
Domain: invalid geometry.  
Repo: comment in `build_trade` — “SL beyond the displacement candle = trade is structurally invalid.”

## WHAT SHOULD NOT YET BE CHANGED
Do not move SL to sweep.price or range boundary to “get more trades.” That is a new geometry thesis and a new MC.

## CLASSIFICATION
**CONFIRMED** fail-closed geometry, not a defect. It is a **throughput bind** (7 of 23 approved executions).

---

# 3. Ultron (two owners)

## RECOMMENDATION
KEEP the two Ultrons separate. Do not unify the names.

## CONFIDENCE
HIGH.

## CURRENT BEHAVIOR

**A. `UltronRiskEngine` (CRT, this walk)**  
S = G^α × C^β. Reject if S < `tier_2_threshold` (0.30 on active config).  
NS log: **3** lines (S = 0.289, 0.258, 0.247), all same wall-clock second.  
That is the **one** soft-conf timeout (`CONFIRMATION_FAILED` 2025-02-24 17:30, 3-candle window).  
Not three extra dead setups. 24 retests → 23 approved + 1 timeout.

**B. `UltronRiskGate` (capital, live/planner path)**  
TTL, min RR 1.5, daily limits, kill switch, exposure, SL distance, size.  
NS summary: `rejected_trades=0`. **Not binding** on this backtest object.

## INTENDED SEMANTICS
MIAR: CRT never owns economic RR; UltronRiskGate owns cost-taxed min RR after the planner (F-048).  
The name collision is historical (`UltronRisk` logger vs `UltronRiskGate`).

## CLASSIFICATION
**INTENTIONAL SEMANTIC SEPARATION** (two questions). On NS, only the CRT score floor bound. Capital Ultron did not.

---

# Combined picture (NS, session already open)

```
1792 sweeps
  → 399 directional displacements (22%)
    → 148 expansions
      → 24 retests (16%)
        → 24 soft-conf starts
          → 23 risk-approved  (1 timeout = 3 CRT-Ultron S<0.3 candle evals)
            → 16 TRADE_OPENED  (7 inverted SL)
```

Session is exhausted (V1 3 → SOFF 12 → NS 16).  
These three are why 16 ≠ 30. The largest structural drop is **before** retest. Inverted SL is the largest *late* drop (7). CRT-Ultron killed **one** setup (3 candle logs). Capital Ultron is zero.

A new MC that only relaxes inverted SL or tier_2 would be a **new geometry/score thesis**, not a session tweak.
