# Semantic layer trace — Path A SL geometry + Path B DecisionEngine

**Generated:** 2026-08-08  
**ACTIVE_VERSION:** `v2_multi_2026_04`  
**Corpus:** `data/XAUUSD_M15_20260807_203705.xlsx` (HTF=4)  
**Scope:** observe-only semantic reconstruction of why force-session still fails  
**Authority:** source code + measured probe; **not** a behavior-change or session-policy proposal  

Related artifacts:
- `reports/xauusd_retest_pathb_counterfactual.json`
- `reports/xauusd_semantic_analysis_20260807_203705.md` (HTF correction)

---

## 0. Two spines, two semantic questions

| Spine | Semantic question | Failure mode on these bars (force-session) |
|---|---|---|
| **Path A — CRT state machine** | “Is this a structurally valid CRT trade geometry?” | Soft-conf + zone PASS → **EXECUTION** → `build_trade` **inverted SL** → no `TRADE_OPENED` |
| **Path B — Decision spine** | “Is this a valid market *opportunity* (semantic), independent of SL/TP economics?” | EngineRunner → DecisionEngine **`zone_gate_invalid`** (then, if zone forced valid: `weak_setup` / `low_score`) → planner never runs |

They are **not** the same layer. Path A owns **structural geometry**. Path B owns **semantic opportunity approval** (score / zone / weak component). Economics (RR floor, size) are Ultron — never reached here.

```text
PATH A (CRT)
  RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST
       → soft-conf S → zone mid → session → EXECUTION
       → build_trade(entry, SL@disp, TP)
       → TRADE_OPENED | inverted-SL reject

PATH B (live / gate-ON backtest post-candidate)
  features → TrapValidator → engines → Fusion
       → DecisionEngine (semantic only)
       → ExecutionPlanner (entry intent)
       → compute_crt_levels (SL/TP mirror)
       → UltronRiskGate (capital / RR)
```

---

## 1. Path A — CRT SL geometry semantic

### 1.1 What each symbol means (doctrine in code)

| Symbol | Owner | Meaning |
|---|---|---|
| **Direction** | Sweep detector | Reversal thesis from range-boundary sweep |
| **Displacement candle** | State machine | Structural impulse that “created” the move; SL anchor |
| **Retest candle** | State machine | Entry price source (`close`) |
| **Inverted SL guard** | `build_trade` | Hard reject if SL is on wrong side of entry |

**Direction rule** (`crt_engine_v2.py` ~891–898):

```text
swept_high (wick above range high, close back inside) → Direction.SHORT
swept_low  (wick below range low,  close back inside) → Direction.LONG
```

This is a **liquidity-grab → reverse** premise, not “trade with the displacement body.”

**SL rule** (`build_trade` ~2204–2222):

```text
entry = retest_candle.close

LONG:  SL = displacement.low  - sl_atr_buffer * ATR
SHORT: SL = displacement.high + sl_atr_buffer * ATR
```

Doctrine comment in source: *“SL beyond the displacement candle = trade is structurally invalid.”*

**Inverted guard** (~2227–2241):

```text
LONG  illegal if SL >= entry   (stop above/at entry)
SHORT illegal if SL <= entry   (stop below/at entry)
```

### 1.2 Ordered semantic stack (Path A post-RETEST)

```text
1. Soft confirmation approved     (score manifold S)
2. Zone filter (discount/premium mid-range)
3. Session filter (allowed_sessions)     ← historical kill; force-passed in probe
4. try_retest_to_execution()             ← state → EXECUTION  (even if trade later fails)
5. build_trade()
      a. compute entry / SL / TP
      b. inverted-SL guard               ← force-session kill on both bars
      c. emit TRADE_OPENED iff Trade built
```

**Critical semantic split:**  
`EXECUTION` state ≠ `TRADE_OPENED`.  
`try_retest_to_execution` only transitions the state machine (“risk approved → entering execution”). Geometry can still refuse the trade.

### 1.3 Measured geometry — Setup 1 SHORT

| Field | Value |
|---|---|
| RETEST bar | 2026-07-22 19:00 broker |
| Soft-conf / EXECUTION | 2026-07-22 19:15 |
| Direction | **SHORT** (sweep high ≈ 4156.69) |
| Displacement | O 4132.02 **H 4146.75** L 4132.02 C 4142.79 — **bullish body** |
| Body vs thesis | **OPPOSED_to_SHORT** (bullish impulse, short thesis) |
| Entry | retest close **4154.55** |
| SL would-be | 4146.75 + 0.2·ATR ≈ **4148.66** |
| Relation | entry is **+7.8 above** disp.high → SL sits **below** entry → **inverted SHORT** |

```text
 price
  4156.69  ── sweep high (thesis: reverse SHORT)
  4154.55  ── ENTRY (retest close)  ← still above structural stop
  4148.66  ── SL would-be (disp.high + buffer)  ← WRONG SIDE for SHORT
  4146.75  ── displacement high
  4142.79  ── displacement close (bullish)
  4132.02  ── displacement open/low
```

**Semantic reading:** market continued **through** the displacement high after a high-sweep short thesis. Retest entry is no longer “protected by” the displacement extreme — the structural stop is below the entry, so the guard correctly refuses.

### 1.4 Measured geometry — Setup 2 LONG

| Field | Value |
|---|---|
| RETEST bar | 2026-07-28 05:30 broker |
| Soft-conf / EXECUTION | 2026-07-28 05:45 |
| Direction | **LONG** (sweep low ≈ 4042.53) |
| Displacement | O 4058.08 H 4059.19 **L 4046.38** C 4047.41 — **bearish body** |
| Body vs thesis | **OPPOSED_to_LONG** |
| Entry | retest close **4044.31** |
| SL would-be | 4046.38 − 0.2·ATR ≈ **4045.07** |
| Relation | entry is **−2.07 below** disp.low → SL sits **above** entry → **inverted LONG** |

```text
 price
  4059.19  ── displacement high
  4058.08  ── displacement open
  4047.41  ── displacement close (bearish)
  4046.38  ── displacement low
  4045.07  ── SL would-be (disp.low − buffer)  ← WRONG SIDE for LONG
  4044.31  ── ENTRY (retest close)  ← already past structural stop
  4042.53  ── sweep low (thesis: reverse LONG)
```

**Semantic reading:** after a low sweep, displacement printed **down**, and the retest closed **through** the displacement low. Entry is beyond the structural SL anchor — guard correctly refuses (near-zero / inverted risk).

### 1.5 Path A semantic conclusion

| Layer | Result |
|---|---|
| Market narrative (CRT) | Reversal after sweep |
| Soft-conf / zone | Treat setup as scorable and in zone |
| Geometry | Entry and SL are **incompatible with direction** |
| Outcome | **EXECUTION without TRADE_OPENED** |

This is not “session did everything.” Under force-session, **geometry is the binding Path A semantic reject.** Both cases share a pattern: **displacement body opposed to sweep direction + retest entry past the displacement extreme.**

---

## 2. Path B — DecisionEngine semantic layer

### 2.1 Ownership (F-048)

`decision_engine.py` header:

> DecisionEngine answers ONE question: **“is this a valid market opportunity?”** — SEMANTIC  
> Not economics, not SL/TP, not portfolio.

Ordered gates in `DecisionEngine.evaluate` (~138–173):

```text
1. zone_gate.valid  (unless fusion.zone_gate_dead)  → reject zone_gate_invalid
2. effective_score < dynamic_threshold              → reject low_score
3. p_win < p_win_threshold (0.4)                    → reject low_probability
4. weak_component > weak_component_threshold (0.4)  → reject weak_setup
5. else                                             → execute
```

Config (`v2_multi_2026_04` `decision_engine`):

| Key | Value | Role |
|---|---|---|
| `threshold_min` / `max` | 0.45 / 0.65 | Dynamic threshold clamp |
| empty history midpoint | **0.55** | Cold DynamicThreshold.compute() |
| `p_win_threshold` | 0.4 | Probability floor |
| `weak_component_threshold` | 0.4 | Weak-link of fused score |

`effective_score = fusion["normalized_score"]` if present, else raw `score`.

`weak_component` is **injected by EngineRunner**, not by Fusion output:

```text
weak_component = max(0, 1 - fusion_result.final_score)   # engine_runner.py ~1038-1042
```

So “weak setup” ≈ “final fusion score too far below 1.0” (threshold 0.4 ⇒ needs final_score > 0.6 to clear this gate when that formula is used).

### 2.2 How EngineRunner builds DecisionEngine inputs

**Zone context** (`engine_runner.py` ~712–717, 1019–1022):

```text
zone_result = {
  engine: "zone_gate",
  score:  <float>,
  direction: 1 if zone_raw.passed else 0,
  meta: zone_raw,          # ← passed / valid / score live HERE
}

zone_gate_ctx = {
  valid: bool(zone_result.get("passed", False)),  # ← reads TOP LEVEL, not meta
  score: zone_result.score,
}
```

On both measured bars, collector showed:

```text
zone_gate.meta.passed = true
zone_gate.meta.valid  = true
```

but `zone_result.get("passed")` is **absent** → `valid=False` → **primary reject `zone_gate_invalid`.**

**Fusion context** (`engine_runner.py` ~1038–1043):

```text
fusion_ctx = {
  candle_polarity: <rr polarity>,   # audit only
  weak_component: 1 - final_score,
  # NOT passed: normalized_score, zone_gate_dead  (even though fusion_result has them)
}
```

So DecisionEngine does **not** see Fusion’s `normalized_score` or `zone_gate_dead` on this path.  
FIX 3 (“bypass zone_gate_invalid when zone engine dead”) cannot fire from this `fusion_ctx`.  
`effective_score` falls back to raw `final_score`.

### 2.3 Ordered DecisionEngine trace — measured bars

#### SHORT soft-conf 2026-07-22 19:15

| Step | Input | Threshold / rule | Result |
|---|---|---|---|
| Engines | crt 0.347 · gaussian 0.883 · zone 0.782 · rr 0.823 | — | ok |
| Fusion | final_score **0.567**, normalized 0.5 (in fusion_result; **not** in fusion_ctx) | — | fusion accepted path logged |
| Gate 1 zone | `valid=False` (wiring) despite meta.passed=true | must be true | **`zone_gate_invalid`** ← primary |
| Gate 2 score *(observe reval)* | effective 0.567 | cold thresh **0.55** | PASS |
| Gate 3 p_win *(reval)* | ~0.567 or gauss 0.88 | 0.4 | PASS |
| Gate 4 weak *(reval)* | weak=1−0.567=**0.433** | 0.4 | **`weak_setup`** ← next |

#### LONG soft-conf 2026-07-28 05:45

| Step | Input | Threshold / rule | Result |
|---|---|---|---|
| Engines | crt 0.172 · gaussian 0.882 · zone 0.610 · rr 0.726 | — | ok |
| Fusion | final_score **0.4602**, normalized 0.0 | — | weak fusion |
| Gate 1 zone | `valid=False` (wiring) | — | **`zone_gate_invalid`** ← primary |
| Gate 2 score *(reval)* | 0.4602 | **0.55** | **`low_score`** ← next |

Planner / `compute_crt_levels` / Ultron: **never invoked** on either bar.

### 2.4 Path B semantic conclusion

| Layer | Meaning | These bars |
|---|---|---|
| Zone cluster score | Geometric zone affinity | **passed=true** in meta |
| Decision zone flag | Boolean opportunity hygiene | **false** via top-level `passed` miss → `zone_gate_invalid` |
| Fused score quality | Opportunity strength | SHORT marginal (weak_setup if zone ok); LONG below dynamic floor (low_score) |
| Planner / Ultron | Intent + capital | Unreached |

Even under a pure “zone valid=true” counterfactual, **neither bar is an `execute` opportunity** on cold DynamicThreshold + current fusion scores.

---

## 3. Unified semantic map (both failures)

```text
                    MARKET (XAUUSD window)
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
   CRT narrative                      Feature vector
   (sweep→disp→retest)                (39-dim + OHLCV)
         │                                   │
         ▼                                   ▼
   Soft-conf + zone mid                 EngineRunner
         │                                   │
   session (hist kill)                  Fusion scores
         │                                   │
   EXECUTION (state)                    DecisionEngine
         │                                   │
   build_trade geometry                 zone_gate_invalid
         │                               (then weak/low score)
   inverted SL ──X TRADE_OPENED              │
                                      planner / Ultron ──X never
```

**Shared economic story:** both ladders are **continuation / wrong-side entries** relative to a reversal CRT thesis. Path A detects that as **illegal SL geometry**. Path B (even after session force-pass) never fully clears **semantic opportunity** gates; scores stay mediocre and zone flag wiring rejects first.

---

## 4. Semantic defects / seams (descriptive only)

| ID | Seam | Evidence | Type |
|---|---|---|---|
| S1 | `EXECUTION` without `TRADE_OPENED` | state_after=EXECUTION, action=NONE, inverted SL log | Intended geometry guard + state split |
| S2 | Sweep direction vs displacement body | SHORT+bullish disp; LONG+bearish disp | CRT reversal premise vs continuation market |
| S3 | `zone_gate_ctx.valid` reads `zone_result["passed"]` but `passed` lives under `meta` | meta.passed=true → still zone_gate_invalid | **Wiring / contract mismatch** (candidate CODE_DRIFT; not fixed this turn) |
| S4 | `fusion_ctx` omits `normalized_score` and `zone_gate_dead` | fusion_result has both; DecisionEngine never sees them | Contract gap between Fusion and Decision |
| S5 | `weak_component = 1 - final_score` | SHORT 0.433 > 0.4 | Semantic “weak” = score far from 1.0, not a separate weak-engine metric |

**No authority** to “fix” S3/S4 without a governed behavior-change task + parity proof. S3 is especially load-bearing: if live always injects `valid=False`, DecisionEngine would always reject `zone_gate_invalid` unless another path differs — worth a dedicated audit against production trade paths.

---

## 5. One-page answer

1. **Path A fails CRT SL geometry** because entry is taken from the **retest close** while SL is anchored to the **displacement extreme**; on both setups the retest has already traded **through** that extreme relative to the sweep direction, so the inverted-SL guard fires. Soft-conf approval does not certify geometry.

2. **Path B fails DecisionEngine** because (a) primary: `zone_gate_invalid` from **valid-flag wiring** (`passed` not on `zone_result` top-level), and (b) even with valid forced: SHORT **`weak_setup`**, LONG **`low_score`**. Planner and Ultron never receive a candidate.

3. **Session was the first historical block; it is not the only semantic layer.** Force-session exposes the deeper CRT-geometry + DecisionEngine opportunity layers.

---

## 6. Suggested next governed probes (not executed)

1. **S3 audit:** unit/integration — assert `zone_gate_ctx["valid"] == zone_raw["passed"]` on a known-pass zone bar; compare to live `TRADE_OPENED` path if any.  
2. **S4 audit:** whether DecisionEngine is intended to use `normalized_score` and `zone_gate_dead` from `fusion_result`.  
3. **Geometry census:** rate of inverted-SL among RETEST→soft-conf approvals on full XAUUSD (HTF=4), by direction and disp-body alignment.

---

*Observe-only. `PRODUCTION_BEHAVIOR_CHANGED=NO`.*
