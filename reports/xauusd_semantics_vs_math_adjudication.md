# Semantics vs math adjudication — Path A geometry + Path B DecisionEngine

**Generated:** 2026-08-08  
**Question:** After force-session, blockers look like “semantics.” Are they **correct meaning**, **wrong meaning**, or **wrong math/wiring**?  
**Method:** pure arithmetic + source contracts + fresh DecisionEngine re-eval (no production edits)  
**Verdict vocabulary:**

| Label | Meaning |
|---|---|
| **MATH_OK** | Formula implemented correctly; numbers match closed form |
| **MATH_WRONG** | Formula or arithmetic does not match stated contract |
| **SEMANTICS_OK** | Rule means what the market situation requires under stated CRT/DE doctrine |
| **SEMANTICS_CONTESTED** | Rule is self-consistent but may encode the wrong *product* meaning |
| **WIRING_WRONG** | Correct subsystem truth is computed, then **lost/remapped** before the consumer |
| **SEMANTIC_FORK** | Two paths define the same concept differently (not a single arithmetic error) |

---

## Executive verdict (one screen)

| Blocker | Math | Meaning | Classification |
|---|---|---|---|
| Path A inverted SL (both bars) | **MATH_OK** | Displacement-SL doctrine applied correctly; entries are past structural stops | **SEMANTICS_OK + MATH_OK** (honest reject) |
| Path A vs Path B SL anchors | both MATH_OK locally | Different anchors | **SEMANTIC_FORK** (not “one wrong formula”) |
| Path B `zone_gate_invalid` | Zone **score math OK** (passed=true) | “Zone valid opportunity” **should be true** | **WIRING_WRONG** (field path) |
| Path B `weak_setup` (SHORT) | **MATH_OK** for `weak=1−final` | Mostly a **second score floor** (final≥0.6), not independent “weak engine” | **MATH_OK + SEMANTICS_CONTESTED** |
| Path B `low_score` (LONG) | **MATH_OK** | Opportunity score below cold threshold 0.55 | **SEMANTICS_OK + MATH_OK** |

**Bottom line:**  
- Geometry rejects are **not math bugs** — they are **doctrine working**.  
- The first Path B reject is **not wrong zone math** — it is **wiring**: zone passed in `meta`, DecisionEngine reads missing top-level `passed`.  
- Secondary Path B rejects (after zone truth restored) are **mostly score math doing what the formula says**; whether `weak=1−final` is the *right* semantic is a design question, not an arithmetic error.

---

## 1. Path A — inverted SL

### 1.1 Stated contract (source)

```text
entry = retest_candle.close

LONG:  SL = displacement.low  − sl_atr_buffer × ATR
SHORT: SL = displacement.high + sl_atr_buffer × ATR

Reject LONG  if SL ≥ entry
Reject SHORT if SL ≤ entry
```

(`crt_engine_v2.build_trade`, doctrine comment: SL beyond displacement extreme.)

### 1.2 Closed-form check (measured bars)

**SHORT (soft-conf ATR≈9.562, buf=0.2)**

```text
entry     = 4154.55
disp.high = 4146.75
SL        = 4146.75 + 0.2×9.562 = 4148.6624
SL ≤ entry?  YES  (gap entry−SL = 5.8876)
inverted?    YES
```

**LONG (ATR≈6.571)**

```text
entry    = 4044.31
disp.low = 4046.38
SL       = 4046.38 − 0.2×6.571 = 4045.0657
SL ≥ entry?  YES  (gap SL−entry = 0.7557)
inverted?    YES
```

→ **MATH_OK.** Engine logs match hand calculation.

### 1.3 Is the *meaning* wrong?

| Claim | Assessment |
|---|---|
| “SL beyond displacement = structural invalid if broken” | **SEMANTICS_OK** under stated CRT doctrine in code |
| Direction from sweep (high→SHORT, low→LONG) | **SEMANTICS_OK** as *reversal* thesis |
| Displacement body opposed to direction (bullish disp + SHORT; bearish disp + LONG) | **SEMANTICS_OK** as *descriptive* of continuation against thesis |
| Entry past displacement extreme | Structural stop is already violated → inverted reject is **the doctrine working** |

This is **not** “math inverted the inequality.”  
For SHORT, legal SL must be **above** entry; computed SL is **below** → reject.  
For LONG, legal SL must be **below** entry; computed SL is **above** → reject.

### 1.4 SEMANTIC_FORK — Path B would use a different SL

`compute_crt_levels` (live planner path) uses **current bar high/low**, not displacement:

```text
SHORT SL = bar.high + buf×ATR
LONG  SL = bar.low  − buf×ATR
```

On the soft-conf bars (hand calc):

| Setup | Path A (disp extreme) | Path B-style (conf bar H/L) |
|---|---|---|
| SHORT | illegal (4148.66) | **legal** ≈ 4157.52 (risk ≈ 2.97) |
| LONG | illegal (4045.07) | **legal** ≈ 4039.53 (risk ≈ 4.78) |

So:

- Path A math is correct for **its** contract.  
- Path B math is correct for **its** contract.  
- They disagree on **what “SL” means** → **SEMANTIC_FORK**, not “one side miscomputed.”

If product intent is “one CRT SL authority,” that fork is a **design inconsistency** (SEMANTICS_CONTESTED at system level), not a floating-point bug.

---

## 2. Path B — `zone_gate_invalid`

### 2.1 Zone *math* (score pass)

From measured EngineRunner/collector on both bars:

```text
zone score SHORT ≈ 0.782  ·  LONG ≈ 0.610
zone_cluster_threshold (config) = 0.25
zone_mode = hard
meta.passed = true
meta.valid  = true
```

`score ≥ threshold` → pass. **MATH_OK.** Zone subsystem says **opportunity zone is valid**.

### 2.2 Wiring into DecisionEngine

EngineRunner builds:

```text
zone_result = {
  engine, score, direction,   # direction = 1 if zone_raw.passed else 0
  meta: zone_raw              # passed lives HERE
}

zone_gate_ctx.valid = bool(zone_result.get("passed", False))  # top-level — ABSENT
```

Proof:

```text
zone_result.get("passed")           → None  → valid=False
zone_result["meta"].get("passed")   → True
zone_result["direction"]            → 1     (pass proxy that DE does not read)
```

DecisionEngine gate 1:

```text
if not zone_gate_dead and not zone_gate.valid → reject "zone_gate_invalid"
```

`fusion_ctx` also **omits** `zone_gate_dead` and `normalized_score` from `fusion_result`.

### 2.3 Classification

| Layer | Status |
|---|---|
| Zone score math | **MATH_OK** → should pass |
| Decision zone flag | **WIRING_WRONG** → always false when `passed` only in `meta` |
| Semantic meaning of reject | **FALSE REJECT** relative to zone subsystem truth |

This is **not** “semantics say zone is bad.” Semantics of the zone engine say **good**; the consumer **never sees** that bit.

### 2.4 Why backtests can still show few zone vetoes

Active config: `backtest.bypass_zone_invalid = true`.  
Backtest gate path can **ignore** `zone_gate_invalid` when journaling CRT trades.  
Live DecisionEngine path does **not** get that bypass.  
That explains coexistence of “zone looks fine in meta” + “DE says zone_gate_invalid” + “research gate-ON ledgers may not show this reject.”

---

## 3. Path B — after zone truth restored

Fresh `DecisionEngine` per case (cold threshold = midpoint 0.55).

| Case | Inputs | Result |
|---|---|---|
| Wired as production | valid=False, score=0.567 | **`zone_gate_invalid`** |
| valid=True, weak=1−0.567, SHORT | score=0.567, p_win=0.883 | **`weak_setup`** |
| valid=True, weak=0, SHORT | score=0.567, p_win=0.883 | **`execute`** |
| valid=True, LONG | score=0.4602 | **`low_score`** |
| valid=True + normalized_score=0.5 SHORT | effective=0.5 | **`low_score`** |

### 3.1 `low_score` (LONG) — MATH_OK + SEMANTICS_OK

```text
final_score = 0.4602
cold threshold = 0.55
0.4602 < 0.55 → low_score
```

Arithmetic and “score too low to be an opportunity” meaning both hold.

### 3.2 `weak_setup` (SHORT) — MATH_OK + SEMANTICS_CONTESTED

Implemented:

```text
weak_component = max(0, 1 − fusion.final_score)     # EngineRunner
reject if weak_component > 0.4
⇔ reject if final_score < 0.6
```

SHORT: `1 − 0.567 = 0.433 > 0.4` → reject. **MATH_OK.**

But notice the interaction with the score gate:

```text
low_score  rejects if final < 0.55   (cold)
weak_setup rejects if final < 0.6    (via 1−final > 0.4)
```

So on a cold DynamicThreshold, **weak_setup is strictly a higher score floor**, not an independent “one engine is weak” check.  
Min-engine on SHORT is CRT **0.347** — never enters the weak formula.

| Interpretation | Verdict |
|---|---|
| Formula computed as coded | **MATH_OK** |
| Name “weak_component” implies component-level weakness | **SEMANTICS_CONTESTED** — implementation is score-complement, not min(engine) |
| SHORT should fail as “not strong enough opportunity” | Debatable; **not a miscalc of 0.433** |

If product intent is “block weak *legs*,” math is the wrong instrument (**SEMANTICS_CONTESTED**).  
If product intent is “require final≥0.6,” naming is misleading but math matches that intent (**SEMANTICS_OK under that reading**).

### 3.3 Missing `normalized_score` in fusion_ctx

Fusion produces both `final_score` and `normalized_score`.  
DecisionEngine prefers `normalized_score` when present.  
EngineRunner **does not pass it** → DE uses raw `final_score`.

| | Effect on these bars |
|---|---|
| SHORT final 0.567 | raw used; with weak=0 would **execute** (G above) |
| If normalized 0.5 were passed | would **low_score** even with valid zone |

Classification: **WIRING/contract gap** (normalized computed then dropped). Whether DE *should* use normalized is **SEMANTICS_CONTESTED**; the drop itself is measurable.

---

## 4. Adjudication matrix (force-session world)

```text
SESSION removed (force-pass)
        │
        ├─ Path A geometry
        │     formula:  MATH_OK
        │     inequality: MATH_OK
        │     meaning:    SEMANTICS_OK (doctrine: no trade past structural SL)
        │     outcome:    CORRECT REJECT (inverted SL)
        │
        └─ Path B DecisionEngine
              zone score:     MATH_OK (passed)
              zone → DE bit:  WIRING_WRONG → FALSE zone_gate_invalid
              then SHORT:     weak_setup  MATH_OK / SEMANTICS_CONTESTED (1−final)
              then LONG:      low_score   MATH_OK / SEMANTICS_OK
```

### What is *not* true

| False claim | Why |
|---|---|
| “Inverted SL is a math bug” | Closed form matches engine; inequality correct |
| “Zone math failed these bars” | meta.passed=true; scores ≫ 0.25 threshold |
| “weak_setup is a random DE glitch” | Deterministic `1−0.567=0.433>0.4` |
| “Semantics and math are the same failure” | Geometry is OK/OK; zone is wiring; weak is formula-design |

### What *is* true

1. **Geometry layer:** meaning and math agree — these entries are past CRT displacement stops.  
2. **Zone opportunity bit:** meaning and zone math agree “pass”; **DecisionEngine never receives that bit** → wiring.  
3. **Score opportunity:** LONG truly weak on fused score; SHORT dies on a **stricter re-expression of score** labeled “weak.”

---

## 5. Dual-spine SL fork (system-level)

```text
Path A TRADE:     SL @ displacement extreme   → both bars ILLEGAL
Path B levels:    SL @ bar high/low           → both bars LEGAL (hand calc)
```

If a future fix only repaired zone wiring and DE executed, **Path B could plan a trade Path A geometry would refuse.**  
That is **SEMANTIC_FORK**, not resolved by “fix the math” on one side alone.

---

## 6. Recommended classification for next work (no authority granted)

| Priority | Item | Class | Nature of work |
|---|---|---|---|
| P0 | `zone_gate_ctx.valid` ← `meta.passed` / `_zone_scored.passed` | **WIRING_WRONG** | Contract fix + regression test; measure Δ decisions |
| P1 | Document dual SL anchors (disp vs bar) | **SEMANTIC_FORK** | Ontology / ownership decision before any code unify |
| P2 | Rename or redefine `weak_component` | **SEMANTICS_CONTESTED** | Design: score floor vs min-engine vs fusion variance |
| P3 | Pass `normalized_score` + `zone_gate_dead` into DE fusion_ctx | **WIRING/contract** | Only after deciding which score DE owns |
| — | Path A inverted SL on these bars | **OK** | No fix; optional research on displacement/body alignment filters |

---

## 7. Direct answer to the question

> “Semantics wrong or math wrong — we need to trace it.”

| Layer | Wrong? |
|---|---|
| Path A SL arithmetic | **No — math right** |
| Path A SL meaning for these bars | **No — semantics right under CRT displacement doctrine** |
| Path B zone *score* math | **No — math right (pass)** |
| Path B zone *flag* to DecisionEngine | **Yes — wiring wrong** (semantics of zone lost) |
| Path B weak/low after zone restored | **Math right**; weak **labeling/meaning contested**; LONG low_score **semantics right** |

**Not** a single blob of “semantics failed.”  
**Three different truths:** correct geometry reject · false zone reject via wiring · real score weakness (LONG) / score-floor named weak (SHORT).

---

*Observe-only. `PRODUCTION_BEHAVIOR_CHANGED=NO`.*
