# CONTEXT PACKET — CRT State Machine Rules · Feature Formation · INFRA Charts

| Field | Value |
|---|---|
| **Packet ID** | `CP-CRT-SM-INFRA-2026-08-06` |
| **Revision** | **r3** — DeepSeek audit remediation (thresholds complete, looser/stricter fix, 39-dim map, loader verify, three-way F-057) |
| **Purpose** | Transferable multi-agent LLM context (self-contained) |
| **Audience** | DeepSeek / Gemini / ChatGPT / Claude / Grok / human bridge |
| **Authority** | Code + production JSON + design freezes; this packet is **descriptive only** |
| **Canonical path** | `docs/handover/CRT_SM_INFRA_CONTEXT_PACKET.md` |
| **Convenience copy** | Repo-root `CRT_SM_INFRA_CONTEXT_PACKET.md` **may lag** — prefer canonical |
| **Runtime pin** | `ACTIVE_VERSION` = **`v2_multi_2026_04`** (observed at r3 freeze) |
| **Build status** | INFRA charts/paper = **DESIGN_FROZEN**. VA = **implemented**. ZONE-X geometry = **halted path (a)** |

---

## 0. Multi-agent safety (read first)

### 0.1 Runtime authority hierarchy

```text
Production JSON (ACTIVE_VERSION → configs/production/<version>.json)
        ↓  when loaded via load_prod_config_from_registry / equivalent merge
CRTConfig runtime instance (frozen)
        ↓
Engine decisions (crt_engine_v2.process_candle)
        ↓
Documentation / this packet / chat   ← DESCRIPTIVE ONLY
```

**Docs never set thresholds.** On conflict: **constructed CRTConfig + code** win.

### 0.2 Boxed rule — never infer from defaults

> **Never infer live thresholds from `CRTConfig` constructor defaults alone.**  
> **Never assume `ConfigBuilder.build(instrument)` equals production.**  
> For production-equivalent analysis: use `load_prod_config_from_registry(ACTIVE_VERSION, instrument)` (or prove the same merge).  
> If loader path is unknown → mark **`UNKNOWN_LOADER`** and do not invent numbers.

### 0.3 Three construction sources (F-057)

| Source | How obtained | Use |
|---|---|---|
| **SCHEMA** | `CRTConfig()` field defaults | Fallback only |
| **ROUTER_BASE** | `ConfigBuilder.build(instrument)` → `market_router.classes[FOREX\|CRYPTO]` | Class profile — **not** full prod |
| **PRODUCTION_MERGED** | `load_prod_config_from_registry(version, instrument)` = crt_engine ∪ params (params win) ∪ instrument_overrides | **Live operating surface** |

**XAUUSD is FOREX** in `market_router.symbol_map`.

---

## 1. Source map

| Concern | Path |
|---|---|
| Legal graph / CRTConfig schema | `src/config_layer/state_identity.py` |
| Guards / process_candle | `src/config_layer/crt_engine_v2.py` |
| Builder | `src/config_layer/config_builder.py` |
| Prod merge | `src/config_layer/production_config.py` → `load_prod_config_from_registry` |
| Router profiles | `configs/production/<ver>.json` → `market_router` |
| Vector names | `src/features/feature_schema.py` → `CANONICAL_FEATURES` |
| FM identities | `configs/formulas/market_ontology.yaml` |
| Pipeline | `src/features/feature_pipeline.py` |
| Story layers | `configs/research/market_story_ontology.yaml` |
| VA | `docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md` · `src/validation_access/` |
| INFRA design | `docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md` |
| ZONE-X | `ZONE-X-DECISION-2026-08-06.md` (path a Stop) |

---

## 2. Thresholds — H1 / H3 complete (r3)

### 2.1 Merge rule (production)

```text
merged = {**crt_engine_coerced, **params}   # params WIN over crt_engine
then instrument_overrides last
→ ConfigBuilder.build(instrument, overrides=merged)
```

### 2.2 Master table (XAUUSD / FOREX · `v2_multi_2026_04`)

**Gate direction key:** for a **minimum** threshold, **higher = stricter**; for a **maximum** ceiling, **lower = stricter**.

| Key | SCHEMA default | ROUTER FOREX (bare build) | PROD effective (merged) | vs SCHEMA | Notes |
|---|---:|---:|---:|---|---|
| `body_ratio_min` | 0.70 | **0.60** | **0.65** | **looser** than schema | Smaller min → easier body gate |
| `atr_multiplier_min` | 1.50 | **1.50** | **1.0** | **looser** | Wick/range vs ATR |
| `atr_min_displacement` | 1.2 | (schema via unset) | **1.2** | same | Body move vs ATR |
| `expansion_atr_min_distance` | 0.20 | **0.08** | **0.30** | **stricter** | Extension beyond disp |
| `retest_depth_max` | 0.25 | **0.35** | **0.15** | **stricter** | Static retest ceiling × range.size |
| `retest_atr_depth_fraction` | 0.50 | **0.50** | **0.30** | **stricter** | ATR retest ceiling |
| `retest_min_depth_atr_fraction` | 0.10 | 0.10 | **0.10** | same | Floor (crt_engine / schema) |
| `max_displacement_strength` | 2.0 | 2.0 | **2.0** | same | FM-028 ceiling |
| `max_sweep_age_candles` | 20 | 20 | **20** | same | |
| `atr_period` | 14 | 14 | **14** | same | Absolute ATR window |
| `atr_buffer_multiplier` | 3 | 3 | **3** | same | Buffer cap = 14×3 = **42** candles |
| `ema_fast` / `ema_slow` (CRT) | 2 / 5 | 2 / 5 | **2 / 5** | same | Soft-conf only |
| `tier_1_threshold` | 0.75 | 0.75 | **0.75** | same | Soft-conf tiers |
| `tier_2_threshold` | 0.30 | 0.30 | **0.30** | same | EXECUTION floor (S_eff) |
| `max_expansion_age_candles` | 495 | 495 | **495** | same | ~5.2 days M15 |
| `max_expansion_age_hours` | 124 | 124 | **124** | same | |
| `shadow_age_penalty_lambda` | 0.0 | 0.0 | **0.0** | same | **Decay OFF** when λ=0 |
| `shadow_age_norm_candles` | 0 | 0 | **0** | same | |
| `conf_alpha` / `conf_beta` | 0.7 / 0.3 | same | **0.7 / 0.3** | same | Soft-conf fusion exponents |
| `conf_floor` | 0.2 | 0.2 | **0.2** | same | |
| Pipeline `ema_fast_span` / `ema_slow_span` | n/a | n/a | **9 / 21** | — | FM-043/044 |

**Do not say “prod is tighter overall.”**  
Pre-expansion gates: **looser** body/wick mins vs schema. Expansion + retest ceilings: **stricter** vs schema. Router FOREX alone is a **third** wrong surface (e.g. expansion **0.08**).

### 2.3 market_router class profiles (snippet)

From `v2_multi_2026_04.json` `market_router.classes`:

```json
"CRYPTO": {
  "retest_depth_max": 0.25,
  "retest_atr_depth_fraction": 0.3,
  "body_ratio_min": 0.5,
  "atr_multiplier_min": 1.0,
  "expansion_atr_min_distance": 0.15
},
"FOREX": {
  "retest_depth_max": 0.35,
  "retest_atr_depth_fraction": 0.5,
  "body_ratio_min": 0.6,
  "atr_multiplier_min": 1.5,
  "expansion_atr_min_distance": 0.08
}
```

`symbol_map` sample: `XAUUSD → FOREX`, `BTCUSDT → CRYPTO`, …

### 2.4 Production JSON snippet (params + crt_engine keys that matter)

```json
"params": {
  "body_ratio_min": 0.65,
  "atr_multiplier_min": 1.0,
  "expansion_atr_min_distance": 0.3,
  "retest_depth_max": 0.15,
  "retest_atr_depth_fraction": 0.3
},
"crt_engine": {
  "atr_min_displacement": 1.2,
  "ema_fast": 2,
  "ema_slow": 5,
  "max_sweep_age_candles": 20,
  "max_displacement_strength": 2.0,
  "max_expansion_age_candles": 495,
  "max_expansion_age_hours": 124,
  "tier_2_threshold": 0.3,
  "shadow_age_penalty_lambda": 0.0,
  "atr_buffer_multiplier": 3,
  "session_windows": {
    "LONDON": ["07:00", "10:00"],
    "NEWYORK": ["13:00", "16:00"],
    "ASIA": ["00:00", "03:00"]
  }
}
```

(Actual file has more keys; these are the ones agents need for SM modeling.)

### 2.5 Loader path verification (no fake `_source` attribute)

CRTConfig has **no** `_source` field. Detect path by **fingerprint compare**:

```python
# PYTHONPATH=src
from config_layer.production_config import get_active_version, load_prod_config_from_registry
from config_layer.config_builder import ConfigBuilder
from config_layer.state_identity import CRTConfig

instrument = "XAUUSD"
version = get_active_version()  # must match ACTIVE_VERSION file

prod = load_prod_config_from_registry(version, instrument)  # PRODUCTION_MERGED
bare = ConfigBuilder.build(instrument)                      # ROUTER_BASE
schema = CRTConfig()                                        # SCHEMA

def fp(cfg):
    return (
        cfg.body_ratio_min,
        cfg.atr_multiplier_min,
        cfg.expansion_atr_min_distance,
        cfg.retest_depth_max,
        cfg.retest_atr_depth_fraction,
    )

print("ACTIVE_VERSION", version)
print("PROD   ", fp(prod))
print("ROUTER ", fp(bare))
print("SCHEMA ", fp(schema))

if fp(prod) == fp(bare):
    print("WARNING: router matches prod fingerprint — unusual; still tag source explicitly")
else:
    print("OK fingerprint: ROUTER_BASE ≠ PRODUCTION_MERGED (F-057 class visible)")

# For production-equivalent work, ONLY use `prod` (or an EXPLICIT injected CRTConfig).
# If you cannot run this check → UNKNOWN_LOADER
```

**BacktestRunner note:** when `crt_config is None` and instrument is set, runner uses `load_prod_config_from_registry` (partial F-057 fix). Other callers of bare `ConfigBuilder.build` still diverge.

### 2.6 F-057 summary (quantified)

| Risk | Example |
|---|---|
| SCHEMA vs PROD expansion | 0.20 vs **0.30** |
| ROUTER FOREX vs PROD expansion | **0.08** vs **0.30** (huge) |
| SCHEMA vs PROD body_ratio_min | 0.70 vs **0.65** (prod **looser**) |
| ROUTER FOREX body | **0.60** vs prod **0.65** |

---

## 3. Layer stack

```
GOAL / ACTIVE_VERSION
  → OHLC (MT5/CSV)
  → market_ontology FM-* + feature_pipeline (39-dim)
  → crt_engine_v2 SM (CRTConfig runtime)
  → EngineRunner scores → Fusion → Decision → Planner → Risk
PARALLEL: story ontology · VA S→I→F→E · ZONE-X (ref only)
```

---

## 4. CRT states (design meanings — not trained)

| State | Meaning |
|---|---|
| RANGE | Building; hold range; watch sweep |
| SHADOW_PENDING | Cross-window disp memory; confirming sweep |
| SWEEP | Range breach + close back inside |
| DISPLACEMENT | Impulse after 4-gates (normal path) |
| EXPANSION | Extended beyond disp **or** shadow resume |
| RETEST | Adaptive depth band; soft-conf flag ON |
| EXECUTION | Soft-conf + filters approved |
| RESOLUTION | Trade finished |
| EXPIRED | Expansion TTL |

---

## 5. Legal graph

```text
RANGE          → SWEEP | SHADOW_PENDING
SHADOW_PENDING → SWEEP | RANGE
SWEEP          → DISPLACEMENT | EXPANSION | RANGE
DISPLACEMENT   → EXPANSION | RANGE
EXPANSION      → RETEST | EXPIRED | RANGE
EXPIRED        → RANGE
RETEST         → EXECUTION | RANGE
EXECUTION      → RESOLUTION
RESOLUTION     → RANGE
```

Golden path: `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION → RANGE`  
Many resets → RANGE without RESOLUTION.

---

## 6. Rule trace

### 6.1 Every bar (`process_candle`)

1. Index++; buffer cap = `atr_period × atr_buffer_multiplier` (**14 × 3 = 42**).
2. `atr_abs = SMA(true_range, atr_period)` — **absolute**, not FM-041.
3. CRT EMAs update (2/5).
4. Optional HTF reset → RANGE + fall-through.
5. Branch on **state** and soft-conf **flag**.

### 6.2 RANGE geometry

`h_ref = max(high)`, `l_ref = min(low)`; `size = h_ref - l_ref`.

### 6.3 RANGE → SWEEP

| Side | Predicate | Direction |
|---|---|---|
| High | high > h_ref AND close < h_ref | SHORT |
| Low | low < l_ref AND close > l_ref | LONG |

Both true → **SHORT** preferred. **≠ FM-058**.

### 6.4 Shadow path (H2 — critical)

```text
RANGE + confirming sweep matching pending dir
  → SHADOW_PENDING
  → try_shadow_pending_to_expansion:
       SHADOW_PENDING → SWEEP → EXPANSION  (same resume)
```

| Fact | |
|---|---|
| DISPLACEMENT dwell | **Skipped** |
| 4-gates | **Bypassed** |
| Legal edge | SWEEP → EXPANSION |
| Agent rule | Tag shadow episodes; never claim universal 4-gate EXPANSION |
| Soft-conf shadow decay | `S_eff = S × exp(−λ · age…)` but prod **λ = 0** → **no decay** until config changes |

### 6.5 SWEEP → DISPLACEMENT (normal, all gates)

| Gate | Predicate | Prod key |
|---|---|---|
| Move | \|close−open\| ≥ atr_min_displacement × atr_abs | 1.2 |
| Age | age ≤ max_sweep_age_candles | 20 |
| Body | body_ratio ≥ body_ratio_min | **0.65** |
| Wick | wick_size ≥ atr_multiplier_min × atr_abs | **1.0** |

Fail move/body/wick → **stay SWEEP**. Age fail → **RANGE**.

### 6.6 DISPLACEMENT → EXPANSION

Directional bar + close beyond disp.close +  
`|close−disp.close| ≥ expansion_atr_min_distance × atr_abs` (**0.30** prod).

### 6.7 EXPANSION → RETEST

```text
depth LONG = close − l_ref; SHORT = h_ref − close
ceiling = max(retest_depth_max×size, retest_atr_depth_fraction×atr)
  = max(0.15×size, 0.30×atr) under prod
min_depth = 0.10 × atr
+ FM-028(disp) ≤ max_displacement_strength (2.0)
```

Pass → cache FM-027/028 + body_ratio; **`evaluating_soft_conf = True`**.

### 6.8 Soft-conf (flag-driven, M1)

Not only `state == RETEST`. Branch: `elif evaluating_soft_conf`.

- Score S via soft-conf manifold; tier_2 = **0.30**.
- Shadow decay only if λ > 0 (prod λ=**0**).
- Zone: LONG ≤ mid (discount); SHORT ≥ mid (premium); else RANGE.
- Pass → EXECUTION.

### 6.9 EXPIRED

age_candles > **495** OR age_hours > **124** (if retest did not win).

### 6.10 EXECUTION → RESOLUTION → RANGE

Trade close / executor.

### 6.11 Tree

```text
RANGE ─sweep?─ no ─ stay
            ├ shadow-confirm ─ SHADOW ─ SWEEP ─ EXPANSION (no 4-gate)
            └ normal ─ SWEEP ─ 4-gate? ─ no ─ stay SWEEP / age→RANGE
                                 └ yes ─ DISPLACEMENT ─ ext? ─ EXPANSION
                                    ├ retest ─ RETEST ─ soft_conf flag ─ EXECUTION ─ RESOLUTION ─ RANGE
                                    │                         └ reject → RANGE
                                    └ TTL → EXPIRED → RANGE
```

### 6.12 Exceptions / integrity (low)

No special `go_error` CRT state. Illegal transitions log **ILLEGAL** and return False. Integrity events (e.g. SHADOW_LEAK, EXPANSION_EXPIRED) emit observability; they do not invent states. Uncaught exceptions **propagate** (fail loud) — do not invent recovery states in analysis.

---

## 7. atr_abs vs FM-041

| | |
|---|---|
| `state.atr_abs` | Absolute SMA(TR) — **SM gates** |
| FM-041 `atr` | close-relative vector idx **13** |
| FM-050 | terciles of **absolute** ATR path |

---

## 8. Dual EMA

| | FM | Vector | Spans | Use |
|---|---|---|---|---|
| Pipeline | FM-043/044 | yes 7/8 | **9/21** | Vector / charts |
| CRT soft-conf | none | no | **2/5** | Soft-conf only |

---

## 9. Features

### 9.1 Full 39-dim CANONICAL_FEATURES (r3)

| Idx | Name | FM id |
|---:|---|---|
| 0 | open | OHLC primitive |
| 1 | high | OHLC primitive |
| 2 | low | OHLC primitive |
| 3 | close | OHLC primitive |
| 4 | volume | OHLC primitive |
| 5 | volume_ratio | FM-062 |
| 6 | double_sweep | FM-060 |
| 7 | ema_fast | FM-043 |
| 8 | ema_slow | FM-044 |
| 9 | ema_spread | FM-022 |
| 10 | trend_bias | FM-054 |
| 11 | trend_strength | FM-064 |
| 12 | momentum_score | FM-023 |
| 13 | atr | FM-041 |
| 14 | volatility_ratio | FM-024 |
| 15 | rsi_14 | FM-042 |
| 16 | macd_line | FM-047 |
| 17 | macd_signal | FM-048 |
| 18 | macd_hist_raw | FM-049 |
| 19 | macd_hist_z | FM-053 |
| 20 | sweep_detected | FM-059 |
| 21 | liquidity_sweep | FM-058 |
| 22 | break_of_structure | FM-057 |
| 23 | swing_high | FM-045 |
| 24 | swing_low | FM-046 |
| 25 | higher_high | FM-055 |
| 26 | lower_low | FM-056 |
| 27 | body_size | FM-001 |
| 28 | candle_range | FM-002 |
| 29 | body_ratio | FM-010 |
| 30 | volatility_regime | FM-050 |
| 31 | session | FM-052 |
| 32 | hour_of_day | FM-051 |
| 33 | disp_strength | FM-020 |
| 34 | retest_depth | FM-021 |
| 35 | candles_since_retest | FM-065 |
| 36 | liquidity_distance | FM-025 |
| 37 | liquidity_pressure_score | FM-026 |
| 38 | volume_spike | FM-063 |

Authority: `feature_schema.CANONICAL_FEATURES` + ontology.

### 9.2 Engine-cache FMs (not in vector)

| FM | Name | Role |
|---|---|---|
| FM-027 | displacement_retrace | Cached at RETEST |
| FM-028 | displacement_atr_ratio | Cached at RETEST / strength gate |

```text
Ontology FM  ≠  automatic vector slot
```

### 9.3 FM_CHART_CORE_V1 (chart default)

FM-010, FM-002, FM-041, FM-020, FM-028*, FM-027*, FM-021, FM-058, FM-059, FM-043/044, FM-051/052, FM-024, FM-050.  
*engine-cache. Exclude FM-022/023 by default (saturation).

### 9.4 Dual sessions

| | Config | Role |
|---|---|---|
| Feature FM-052 | `feature_pipeline.session_windows_utc` + `session_timestamp_basis` | Labels (wide); default **broker_local** (F-066) |
| CRT filter | `crt_engine.session_windows` | Trade allowed windows (narrow) |

Prod feature windows (UTC hours): ASIA [0,9), LONDON [7,16), NEWYORK [12,21).

---

## 10. INFRA (design frozen)

`INFRA_CHART_PAPER_COMPARE_V1.md`: charts A · paper B (demo on EXECUTION) · compare C.  
**Hold** until user authorizes `build A0`. ZONE-X reference only.

---

## 11. VA-XAUUSD-M15

```text
PYTHONPATH=src python scripts/governance/validation_access_cli.py
```

S→I→F→E. Observation 2026-08-06: S/I/F PASS, **E OPEN** — re-run for current. Not edge seal.

---

## 12. ZONE-X

Path **(a) Stop**. Design c=0.055 / empirical 0.0238. No geometry search; no CRT states from ZONE-X.

---

## 13. Known flow problems

| ID | Issue |
|---|---|
| F-057 | Three-way threshold surfaces (schema / router / prod) — §2 |
| F-066 | Broker clock on FM-052 |
| F-037 | Research fusion often off |
| F-060/064 | Don’t chart FM-022/023 default |
| Dual CRT | Fusion score ≠ CRTState |
| E OPEN | No sealed MC-* |

---

## 14. MUST / MUST NOT

**MUST:** resolve PRODUCTION_MERGED for live claims; fingerprint loader (§2.5); tag shadow; model soft-conf flag; keep atr_abs≠FM-041, EMA dual, FM-058≠SWEEP; FM-027/028 non-vector; dual sessions; canonical packet path.

**MUST NOT:** infer from schema defaults alone; assume builder=prod; claim all EXPANSIONs passed 4-gates; invent CRT from ML; reopen ZONE-X geometry; claim edge from VA green; build INFRA without authorize.

---

## 15. Topic track

T01 layers · T02 flow problems · T03 ZONE-X REF · T04 paper DESIGNED · T05 charts DESIGNED · T06 goal · T07 CRT rules · T08 semantic links.

---

## 16. Prompts for other models

Use packet **r3**. Quote **PROD effective** column. Separate shadow vs normal. Fingerprint loader before threshold advice.

---

## 17. Paths

```text
docs/handover/CRT_SM_INFRA_CONTEXT_PACKET.md   # canonical
configs/production/ACTIVE_VERSION
configs/production/v2_multi_2026_04.json
PYTHONPATH=src python scripts/governance/validation_access_cli.py
```

---

## 18. Integrity checklist

- [ ] Thresholds from PRODUCTION_MERGED or EXPLICIT, not schema alone  
- [ ] Ran or understood §2.5 fingerprint (ROUTER ≠ PROD on XAUUSD)  
- [ ] body gate: prod **looser** (0.65); expansion/retest: prod **stricter**  
- [ ] Shadow skips DISPLACEMENT 4-gates  
- [ ] Soft-conf is flag-driven; tier_2=0.30; shadow λ=0 in prod  
- [ ] 39-dim map §9.1; FM-027/028 not vector  
- [ ] atr_abs ≠ FM-041; dual EMA; dual sessions  
- [ ] ZONE-X ref; INFRA design-only; VA E OPEN  

---

## 19. Revision history

| Rev | Date | Change |
|---|---|---|
| r1 | 2026-08-06 | Initial packet |
| r2 | 2026-08-06 | H1–H3, shadow, soft-conf, authority hierarchy |
| **r3** | 2026-08-06 | DeepSeek audit: fixed looser/stricter claim; full threshold set (tier_2, expansion ages, atr_buffer, shadow λ); three-way schema/router/prod; loader fingerprint snippet; 39-dim FM map; JSON/router snippets; exception note |

---

*End of packet `CP-CRT-SM-INFRA-2026-08-06` **r3**.*
