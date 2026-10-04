# CRT Local Math Authority Resolution V1

**Task class:** OBSERVATION_ONLY  
**Implementation authorized:** **NO**  
**Migration authorized:** **NO**  
**Architecture:** Decision **C** preserved  

Machine authority: `CRT_LOCAL_MATH_AUTHORITY_RESOLUTION_V1.json`  
Probe: `CRT_LOCAL_MATH_AUTHORITY_PROBE_V1.json`

---

## Owner gate context (confirmed)

| Stamp | Value |
|-------|--------|
| G-SHADOW-01 | ACCEPTED_AS_PASSED (declared XAUUSD population only) |
| G-PARITY-01 (prior) | ACCEPTED_AS_NOT_PASSED |
| G-MIG-01 | CLOSED |
| MSIP shadow authority | OBSERVATIONAL_ONLY |
| CRT lifecycle | UNCHANGED |
| Production cutover / CRT input migration / thresholds / concurrency | **NO** |

**Caution held:** G-PARITY-01 is **not** a prerequisite for the shadow layer. It only gates claims about replacing/deprecating CRT-local market math or migrating CRT inputs.

---

## Classification summary

| Quantity | Classification |
|----------|----------------|
| **body_ratio** | **EXACT_CANONICAL_IDENTITY** (FM-010 / `candle_math.body_ratio`) |
| **wick_size** | **EXACT_CANONICAL_IDENTITY** (FM-002 / `candle_range`; name is historical debt) |
| **atr** | **GOVERNED_TRANSFORM_OF_CANONICAL_QUANTITY** (+ **LEGITIMATE_CRT_PRIVATE** absolute runtime form for thresholds) |
| **ema_fast** | **DISTINCT_GOVERNED_MARKET_QUANTITY** (CRT period **2** vs pipeline FM-043 span **9**) |
| **ema_slow** | **DISTINCT_GOVERNED_MARKET_QUANTITY** (CRT period **5** vs pipeline FM-044 span **21**) |

---

## Per-quantity reasoning

### body_ratio — EXACT_CANONICAL_IDENTITY

- CRT `Candle.body_ratio` is already registry-bound to **FM-010**.
- Pipeline uses the same body/range definition.
- Probe: max abs err **0.0** on 2000 Phase-1 bars.
- Not a discovery problem; residual is optional call-path hygiene only.

### wick_size — EXACT_CANONICAL_IDENTITY

- CRT `Candle.wick_size` → **FM-002** = `high - low` (full range).
- Pipeline identical.
- Probe: max abs err **0.0**.
- Naming debt only: token is not “sum of wicks” (that is FM-005).

### atr — GOVERNED_TRANSFORM (+ private absolute form)

Do **not** treat CRT `state.atr` and feature `atr` (FM-041) as the same number.

| Layer | Meaning |
|-------|---------|
| True range | Shared |
| Absolute SMA(14) TR | Pipeline `atr_14_raw`; CRT formula same on full series → probe max err **0.0** |
| FM-041 `atr` | **Close-relative** = `atr_14_raw / close` |
| CRT `state.atr` | **Absolute** price units; buffer-local; thresholds (`* atr`) assume absolute |

**Transform (full-series):**  
`relative ≈ absolute / close` and `absolute ≈ relative * close`  
(probe max relative err ~1e-10; absolute ~3e-7 float noise).

**Why not register a transform “to pass G-PARITY-01”:**  
Silent replacement of CRT absolute atr by relative FM-041 would retune every absolute ATR multiplier. Architectural desirability fails even though math is valid. Transform registration is only justified under a future BEHAVIOR_CHANGE_AUTHORIZED plan (bind to `atr_14_raw` with buffer-parity, or migrate thresholds to relative units).

### ema_fast / ema_slow — DISTINCT_GOVERNED_MARKET_QUANTITY

| Surface | Periods |
|---------|---------|
| CRT soft-confirm | **2 / 5** (`CRTConfig.ema_fast/slow`) |
| Pipeline FM-043/044 | **9 / 21** `ewm(adjust=False)` |

Probe: pipeline matches 9/21 (float32 noise); vs CRT 2/5 max abs err **~13.7 / ~16.9** — not a failed equality of one quantity.  
**Do not invent EMA-2↔EMA-9 transforms.** They are different instruments.

---

## Gate outcome

```text
G-PARITY-01 = PARTIAL

body_ratio = EXACT_CANONICAL_IDENTITY
wick_size  = EXACT_CANONICAL_IDENTITY
atr        = GOVERNED_TRANSFORM_OF_CANONICAL_QUANTITY
             (+ LEGITIMATE_CRT_PRIVATE absolute runtime form)
ema_fast   = DISTINCT_GOVERNED_MARKET_QUANTITY
ema_slow   = DISTINCT_GOVERNED_MARKET_QUANTITY

CRT_LOCAL_DEPRECATION_CANDIDATES = [body_ratio hygiene, wick_size hygiene]
NEW_GOVERNED_QUANTITIES_REQUIRED = [optional crt_ema_2, crt_ema_5, atr_absolute_sma14]
MIGRATION_CANDIDATES = []
MIGRATION_AUTHORIZED = NO
```

**PARTIAL** means: authority identity is resolved; **migration/deprecation of CRT math is still not authorized**. Equality-based “make ATR/EMA match” is the wrong bar for EMA and an incomplete bar for ATR.

---

## Explicit non-actions

- No ATR/EMA transform registry created
- No CRT code change
- No production cutover
- No G-MIG-01 open
- Shadow layer preserved as-is (G-SHADOW-01 independent)

---

## Project posture

Remain on **Decision C**. Keep the working MSIP shadow layer. Resolve only further CRT math **if** owner opens a new boundary (hygiene, new FM ids, or BEHAVIOR_CHANGE_AUTHORIZED migration). This artifact grants **no** implementation authority.
