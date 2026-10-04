# CRT IN/OUT + Formula Runtime Trace — XAUUSD

> **Instrument note:** The task named `XAUUSDT`. Repository search found **zero** `XAUUSDT` corpus/config/test hits. User authorized substitution to **`XAUUSD`** (the governed metals instrument). All runtime evidence below is for **XAUUSD** only. No `XAUUSD`↔`XAUUSDT` aliasing was invented in loaders.

**Report path:** `reports/CRT_IN_OUT_XAUUSDT_TRACE.md`  
**Status:** `CRT_XAUUSDT_TRACE_STATUS = COMPLETE`  
**Generated:** 2026-07-11  
**Authority:** observational only — no CRT redesign, no production formula/config/model changes.

---

## 1. Executive Verdict

| Item | Result |
|------|--------|
| Instrument executed | **XAUUSD** (user-approved substitute for XAUUSDT) |
| Corpus | `data/mt5/XAUUSD_M15.csv` Phase-1 frozen candidate **FOUND** (sha256 `4d73f5ce…b26aba56`) |
| Active CRT authority | **`CRTEngine` / `src/config_layer/crt_engine_v2.py`** via `process_candle` |
| Canonical backtest | `BacktestRunner.run` in `src/runtime/backtest_v2.py` |
| Baseline trades | **1** approved trade |
| Candidates (telemetry lifecycle) | **3433** |
| Trace behavior parity | **PASS** (trade CSV + summary JSON byte-identical baseline vs trace) |
| Lineage completeness | **COMPLETE** for CRT boundary values enumerated below |

CRT consumes **raw `Candle` OHLCV streams** (not FeaturePipeline vectors) for state/gates. FeaturePipeline still runs in the harness for journal columns / calibrated scorer and is **OUT OF SCOPE** for CRT math lineage (marked throughout).

---

## 2. Scope and Explicit Exclusions

**In scope (CRT boundary):**

```text
XAUUSD RAW MARKET DATA
        ↓
CandleLoader / Candle construction
        ↓
Values read by CRTEngine.process_candle
        ↓
CRT formulas / state / gates / transformations
        ↓
CRT action dict + TRADE_OPENED / explicit non-trade terminals
```

**Explicit exclusions:**

| Surface | Status |
|---------|--------|
| Full 38-dim FeaturePipeline math | OUT OF SCOPE (harness may compute; CRT state machine does not consume the 38-vector for gates) |
| Gaussian / ZoneGate / RR fusion (`EngineRunner`) | OUT OF SCOPE — run with `BACKTEST_ENGINE_GATE=0` (F-037 CRT isolation) |
| BitNet | INERT (`use_bitnet: false`) |
| UltronRiskGate / ExecutionPlanner live path | OUT OF SCOPE |
| Economic edge claims / promotion | Not made |
| Production config / formula remediation | Forbidden by task |

---

## 3. Repository / Commit / Config / Corpus Pin

| Pin | Value |
|-----|-------|
| Commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` |
| Branch | `feature/truth-registry-v2` |
| Working tree | Dirty (pre-existing uncommitted work; **no production CRT/config mutated for this task**) |
| Python | 3.14.3 |
| Active config | `v2_multi_2026_04` (`configs/production/ACTIVE_VERSION`) |
| Config file SHA-256 | `8f45c66c1175cf87c3a1ddd2c01c715d84e14f7b3ab1fdb4dd31f9dc58e778ae` |
| Embedded config hash field | `7de09f6233b712f0136fc1bf1d2a51322b5b7c65395c75b035d0f96db689d613` |
| Corpus path | `data/mt5/XAUUSD_M15.csv` |
| Corpus SHA-256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Rows | 47275 |
| Date range | `2024-05-22 01:00:00` → `2026-05-21 23:45:00` |
| Phase-1 binding | `docs/governance/xauusd_m15_phase1_frozen_candidate.json` (hash match verified) |
| Backtest command | See §14 |
| RNG seed | `backtest.slippage_seed = 42` |
| Exit model | `crt_engine.exit_model = intrabar_touch` (CRTConfig) |
| Spread | `backtest.simulated_spread_pct = 0.0002` |
| Slippage | ON, `slippage_atr_fraction = 0.1` |
| Engine gate | `BACKTEST_ENGINE_GATE=0` (CRT isolation) |
| Scorer | `calibrated` → NoOpScorer (no active gaussian registered; gating disabled) |

Artifacts:

- Baseline: `results/crt_xauusd_trace_run/baseline/run_20260711_182138_XAUUSD/`
- Trace: `results/crt_xauusd_trace_run/trace/run_20260711_182221_XAUUSD/`
- Runtime trace JSONL: `results/crt_xauusd_trace_run/runtime_trace.jsonl` (14592 rows)
- Parity: `results/crt_xauusd_trace_run/parity_compare.json`
- Harness: `scripts/analysis/crt_xauusd_runtime_trace.py` (post-call observational wrap only)

---

## 4. XAUUSDT Support Verification (Step 0)

### 4.1 Literal XAUUSDT

| Check | Result |
|-------|--------|
| Corpus files named `*XAUUSDT*` | **0** |
| String `XAUUSDT` in configs/src/scripts/tests/docs/reports/data | **0 hits** |
| Market router / instrument metadata for XAUUSDT | **None** |

```text
XAUUSDT_CORPUS = NOT_FOUND
XAUUSDT_BACKTEST_SUPPORTED = NO
XAUUSDT_CONFIG_SUPPORTED = NO
```

### 4.2 User-approved substitute: XAUUSD

| Check | Result |
|-------|--------|
| Corpus | **FOUND** — `data/mt5/XAUUSD_M15.csv` (+ other paths; loader rewrites to Phase-1 candidate) |
| Config | **YES** — `params`/risk maps, metals_prefixes `XAU*`, known_gaps for XAUUSD in `v2_multi_2026_04.json` |
| Backtest | **YES** — `python src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD` |
| Guard | `guard_xauusd_csv_path` fail-closed rewrite + hash/range |

```text
XAUUSD_CORPUS = FOUND
XAUUSD_BACKTEST_SUPPORTED = YES
XAUUSD_CONFIG_SUPPORTED = YES
```

**Missing dependency for literal XAUUSDT:** an OHLC/OHLCV corpus file whose identity is the symbol **XAUUSDT** (plus any instrument map entry). Task continued under explicit user approval of **XAUUSD**.

---

## 5. Active CRT Authority

### 5.1 Identity (source-verified)

| Role | Authority |
|------|-----------|
| CRT implementation | `src/config_layer/crt_engine_v2.py` — class `CRTEngine` |
| Runtime entry | `CRTEngine.process_candle(candle, htf_candle_id) -> dict` (~L2283) |
| Constructor | `CRTEngine(config: CRTConfig, …)` — requires explicit `CRTConfig` |
| Config build | `load_prod_config_from_registry(PROD_VERSION, instrument)` → `ConfigBuilder` merge of `params` + `crt_engine` + market router |
| Backtest entry file | `src/runtime/backtest_v2.py` |
| Backtest entry command | CLI `main()` or programmatic `BacktestRunner.run` |
| Candle schema | `@dataclass Candle` in `crt_engine_v2.py` (timestamp, open, high, low, close, volume, index) |
| Loader | `CandleLoader` in `backtest_v2.py` |
| Terminal emission | `action["action"]` from `process_candle`; event log via `EventLogger`; journal via `TradeJournal.on_trade_opened` when `TRADE_OPENED` |

### 5.2 Call chain (canonical backtest, gate OFF)

```text
backtest_v2.main / crt_xauusd_runtime_trace._run_backtest
  → load_prod_config_from_registry(v2_multi_2026_04, XAUUSD)
  → BacktestConfig.from_prod_config
  → CandleLoader(filepath, "XAUUSD")  # guard_xauusd_csv_path
  → BacktestRunner.run(loader.stream(), count, output)
       → CRTEngine(self.crt_cfg)
       → for candle in stream:
            htf.push(candle)
            engine.process_candle(candle, htf.current_htf_id)   # CRT BOUNDARY
            if TRADE_OPENED: journal + optional scorer (NoOp)
```

**Proof points (file:line):**

- Loader guard: `backtest_v2.py` ~692–709  
- Engine construct: ~1804  
- Process call: ~1976  
- TRADE_OPENED handling: ~1998+  

---

## 6. XAUUSD Data Loading Chain

```text
data/mt5/XAUUSD_M15.csv
  → guard_xauusd_csv_path (Phase-1 hash/range fail-closed)
  → csv.reader (utf-8-sig)
  → require_unique_ohlcv_headers + require_ohlcv_columns
  → parse_ohlcv_timestamp (shared OHLCV_DATE_FORMATS)
  → float(open/high/low/close/volume)
  → validate_ohlcv_row (non-neg volume, OHLC consistency; raise on bad row)
  → yield Candle(...)
  → HTFBuilder.push / seed
  → CRTEngine.process_candle
```

### Explicit answers

| # | Question | Answer |
|---|----------|--------|
| 1 | Where are O/H/L/C/V read? | `CandleLoader.stream` `backtest_v2.py` ~776–787 |
| 2 | Direct or transformed? | Direct floats from CSV cells; no unit conversion; no price scaling |
| 3 | Resampled? | **No** (M15 native; HTF is logical window of N M15 bars, not a resampled series fed to CRT) |
| 4 | Normalized? | **No** (absolute prices; ATR in price units) |
| 5 | Missing filled? | **No** — blank rows skipped; corrupt rows **raise** |
| 6 | Volume type? | CSV column `volume` — MT5 **tick volume** semantics (integer-like counts in corpus, e.g. 409…1251); **not** used in CRT gates/formulas (stored on `Candle.volume` only) |
| 7 | FeaturePipeline before CRT? | Pipeline **runs in harness** for journal/scorer vectors; **CRT gates do not read** the 38-vector. CRT receives **raw `Candle` objects** |
| 8 | CRT input surfaces? | Primary: `Candle` + `htf_candle_id` string + internal `EngineState`. Optional: spread via `set_spread` from backtest loop |

---

## 7. CRT IN Contract

**Required inputs per candle:**

| Input | Type | Required |
|-------|------|----------|
| `candle.timestamp` | datetime | yes |
| `candle.open/high/low/close` | float | yes |
| `candle.volume` | float | loaded; **not decision-binding inside CRT formulas** |
| `htf_candle_id` | str | yes (reset / range identity) |
| `CRTConfig` | frozen dataclass | yes at construct |
| Prior `EngineState` | mutable | yes after init |
| `candle_buffer` | list[Candle] | ATR + range re-seed |

**Warmup / init (backtest):**

- Skip first `backtest.warmup_candles` (30) bars without full process  
- `initialise_range(htf.seed_candles(), htf_id, session)` seeds range + ATR  

**Session name on range:** often `"UNKNOWN"` at init path used here (session string from `_session` only partially applied).

---

## 8. Exhaustive CRT-Consumed Value Inventory

Master table (compact). Runtime samples from `runtime_trace.jsonl` / TRADE_OPENED @ `2024-06-17 15:00:00`.

| Value | Source | File:line | Formula | Config key | CRT consumer | Runtime samples | CRT output effect |
|-------|--------|-----------|---------|------------|--------------|-----------------|-------------------|
| open | CSV→Candle | backtest_v2.py:776 | identity | — | sweep/disp/soft-conf body | TRADE: o=2318.24 | gates + scores |
| high | CSV→Candle | :776 | identity | — | sweep high, ATR TR, range H, SL short | h=2319.92 | sweep SHORT/LONG + ATR |
| low | CSV→Candle | :776 | identity | — | sweep low, ATR TR, range L, SL long | l=2317.81 | same |
| close | CSV→Candle | :777 | identity | — | nearly all gates/scores/EMA/entry | c=2319.29 | entry=retest.close |
| volume | CSV→Candle | :777 | identity | — | **not used in CRT gates** | 1692 | no CRT decision effect |
| timestamp | CSV→Candle | :758 | parse_ohlcv_timestamp | — | session time score, expansion hour TTL | 2024-06-17 15:00:00 | time_score / TTL hours |
| candle.index | process_candle | crt_engine_v2.py:2285-2286 | sequential counter | — | ages, TTL, telemetry | 1676 | age gates |
| prev close | buffer[i-1] | :1009-1014 | TR input | atr_period | ATR | atr≈2.167 | displacement/expansion/retest |
| body_size | candle_math | candle_math.py:25-27 | \|C−O\| | — | displacement move gate | disp body used | pass/fail disp |
| candle_range / wick_size | candle_math | :30-32; Candle:111-114 | H−L | — | ATR mult gate, FM-028 | range on bars | disp/retest strength |
| body_ratio | candle_math | :50-61; Candle:116-117 | body/range | body_ratio_min | disp gate, soft conf | 0.74 on disp | hard gate |
| is_bullish | Candle | :120-121 | C>O | — | expansion direction | — | expansion |
| range h_ref/l_ref | RangeDetector | :991-992 | max H / min L window | atr_period (window) | sweep + retest + zone filter | H=2326.24 L=2316.85 | sweep detect |
| equilibrium / mid | Range | :993; soft conf | (H+L)/2 | — | discount/premium filter | mid=2321.545 | FILTER_REJECTED path |
| range.size | Range | :139-140 | H−L | retest_depth_max | adaptive ceiling | 9.39 | retest depth |
| ATR | RangeDetector.compute_atr | :1005-1018 | mean TR over period | atr_period, atr_buffer_multiplier | many gates | 2.167 | scale all ATR gates |
| TR | compute_atr | :1011-1015 | max(H−L,\|H−pc\|,\|L−pc\|) | — | ATR | — | ATR |
| sweep price/dir | detect_sweep | :1027-1034 | wick beyond range + close back | — | state + scores | price=2316.56 LONG | SWEEP |
| double_confirmed | detect_sweep | :1036-1039 | prev opposite sweep | — | score_sweep bonus | false | +0.4 score |
| upper/lower wick frac | detect_sweep | :1045-1047 | taxonomy only | — | metadata only | — | diagnostic only |
| displacement OHLC | state | try_sweep_to_displacement | hold candle | body_ratio_min, atr_* | expansion/retest/SL | o=2321.45 c=2318.68 | structure |
| expansion close distance | try_displacement_to_expansion | :1292-1299 | \|C−disp_C\| ≥ k·ATR | expansion_atr_min_distance | EXPANSION | — | gate |
| retest depth_abs | try_expansion_to_retest | :1329-1332 | close−L or H−close | retest_* | RETEST | — | gate |
| adaptive_ceiling | same | :1324-1326 | max(static, atr) | retest_depth_max, retest_atr_depth_fraction | RETEST + scores | — | gate |
| min_depth | same | :1334 | 0.1·ATR | **hardcoded 0.1** | RETEST | — | gate |
| displacement_atr_ratio | derived_math FM-028 | :1360 | range/ATR | max_displacement_strength | retest reject if > max | 1.713 | PATCH7 gate |
| displacement_retrace | derived_math FM-027 | :1385-1388 | \|retest−disp_O\|/\|disp_C−disp_O\| clip[0,1] | — | cache/BitNet map | 1.0 | soft conf / intent |
| ema_fast/slow | EngineState.update_emas | :295-303 | EMA α=2/(N+1) | ema_fast, ema_slow | soft conf f_mom | 2319.24 / 2319.49 | C score |
| risk component scores | UltronRiskEngine | :1556-1632 | see §10 | weights hardcoded + decay λ | fusion G | S path | approve |
| soft conf C | compute_soft_confirmation | :1647-1700 | blend + weak link | conf_* | S = G^α C^β | — | tier gate |
| fusion S | approve_with_soft_conf | :1759 | G^α·C^β | conf_alpha/beta, tier_* | EXECUTION | TRADE path | open/reject |
| spread pct | set_spread | :1550-1552 | (ask−bid)/mid | max_spread_pct | hard reject | from bt spread | HIGH_SPREAD |
| session window hit | score_time / filter | :1587-1594; :2717-2737 | clock in windows | session_windows, allowed_sessions | time score + open filter | NEWYORK path | score / FILTER |
| SL/TP/entry | build_trade | :1925-2025 | entry=retest.close; SL=disp extreme±buf·ATR; TP=entry±mult·R | sl_atr_buffer, tp1_* , tp2_* | TRADE_OPENED emit | entry 2318.21 raw | trade geometry |
| risk_pct | resolve_risk_pct | :1635-1643 | band table | sizing_bands | trade.risk_pct | — | sizing only |
| pending displacement TTL | process_candle RANGE | :2362-2369 | countdown | pending_displacement_ttl_candles | shadow path | 43 shadow events | shadow resume |
| expansion age | EXPANSION TTL | :2543-2556 | idx/hours | max_expansion_age_* | EXPIRED | — | soft archive |
| shadow age penalty | soft conf | :2641-2656 | exp(−λ·age) | shadow_age_* | may un-approve | λ=0 → off | inert on pin |
| retrace reset | ResetLogic | ResetLogic.should_reset | \|price−disp_C\|/body | retrace_reset_pct | RESET | many RESET | abort setup |
| extension reset | ResetLogic | same | fib·\|disp_C−sweep\| | extension_reset_fib | RESET | — | abort setup |
| HTF id change | ResetLogic | same | id inequality | — | RESET (unless EXPANSION/RETEST protect) | gap/HTF | range reseed |

---

## 9. Source Code vs Configuration Ownership

| Class | Ownership | Examples |
|-------|-----------|----------|
| STRUCTURAL (code) | Frozen formulas | body_ratio identity, TR definition, state graph `VALID_TRANSITIONS`, RiskScore weight vector 0.35/0.25/0.20/0.20 |
| BEHAVIORAL (config) | `CRTConfig` via prod JSON | thresholds, TTL, sessions, soft-conf weights, sizing bands, exit_model |
| BACKTEST harness | `backtest` section | warmup, HTF size, spread, slippage seed, capital |
| OUT OF SCOPE | FeaturePipeline / models | 38-dim vectors, gaussian NoOp |

**XAUUSD-resolved CRTConfig snapshot (runtime `ConfigBuilder.build("XAUUSD")`):**  
`body_ratio_min=0.6`, `atr_multiplier_min=1.5`, `atr_min_displacement=1.2`, `retest_depth_max=0.35`, `expansion_atr_min_distance=0.08`, `max_displacement_strength=2.0`, `tier_2_threshold=0.3`, `use_bitnet=False`, `exit_model=intrabar_touch`, `allowed_sessions=(LONDON,NEWYORK,OVERLAP)`, … (full 48 fields in pin JSON).

---

## 10. Formula Registry and Exact Executable Formulas

### FM-BODY_SIZE
```text
Runtime name: body_size / Candle.body_size
Producer: features.candle_math.body_size
Source: src/features/candle_math.py:25-27
Exact formula: |close - open|
Inputs: open, close — raw candle
Config: none
Hardcoded: none
First consumer: displacement move gate; soft conf f_disp
Output reachability: yes
```

### FM-CANDLE_RANGE (historically `wick_size`)
```text
Runtime name: wick_size property / candle_range
Producer: candle_math.candle_range
Source: candle_math.py:30-32; crt_engine_v2.py:111-114
Exact formula: high - low
First consumer: ATR mult gate; FM-028
```

### FM-BODY_RATIO (FM-010)
```text
Exact formula: body_size / candle_range   (0 if range<=0)
Config consumer: body_ratio_min
Gate: try_sweep_to_displacement — reject if body_ratio < body_ratio_min
```

### FM-ATR-SMA
```text
Producer: RangeDetector.compute_atr
Source: crt_engine_v2.py:1005-1018
TR_i = max(H_i-L_i, |H_i-C_{i-1}|, |L_i-C_{i-1}|)
ATR = mean(TR window of atr_period)   # simple mean, not Wilder RMA
Buffer cap: atr_period * atr_buffer_multiplier
```

### FM-RANGE
```text
h_ref = max(highs), l_ref = min(lows), equilibrium = (h_ref+l_ref)/2, size = h_ref-l_ref
Producer: detect_htf_range :987-1003
```

### FM-SWEEP
```text
swept_high = high > h_ref AND close < h_ref
swept_low  = low  < l_ref AND close > l_ref
direction = SHORT if swept_high else LONG
price = high if swept_high else low
```

### FM-DISP-MOVE-GATE
```text
move = |close-open|
require move >= atr_min_displacement * ATR
require body_ratio >= body_ratio_min
require candle_range >= atr_multiplier_min * ATR
require sweep age <= max_sweep_age_candles
```

### FM-EXPANSION
```text
directional body: long ⇒ close>open; short ⇒ close<open
close beyond disp_close in trade direction
|close - disp_close| >= expansion_atr_min_distance * ATR
```

### FM-RETEST-ADAPTIVE
```text
static_ceiling = retest_depth_max * range.size
atr_ceiling    = retest_atr_depth_fraction * ATR
adaptive_ceiling = max(static, atr)
depth_abs = (close - l_ref) if LONG else (h_ref - close)
require min_depth = 0.1*ATR <= depth_abs <= adaptive_ceiling
require displacement_atr_ratio <= max_displacement_strength
```

### FM-027 displacement_retrace
```text
Producer: features.derived_math.displacement_retrace
|retest_close - disp_open| / |disp_close - disp_open|  clipped [0,1]
```

### FM-028 displacement_atr_ratio
```text
candle_range(disp) / ATR
```

### FM-EMA
```text
α = 2/(N+1); ema = close*α + ema*(1-α); seed on first close
N ∈ {ema_fast=2, ema_slow=5}
```

### FM-SCORE-SWEEP / BREAKOUT / RETEST / TIME / DECAY / FINAL
```text
sweep_score = clamp(0.6 + 0.4*double - min(overshoot/size, 0.2), 0, 1)
breakout_score = 0.5*min(body_ratio,1) + 0.5*min((range/ATR)/3, 1)
retest_score = max(0, 1 - depth_abs/adaptive_ceiling)
time_score = 1.0 if ≥2 session windows match else 0.8 if 1 else 0.0
decay = exp(-score_decay_lambda * candles_since_retest)  (1 if elapsed<=0)
FINAL G = (0.35*sweep + 0.25*breakout + 0.20*retest + 0.20*time) * decay
         (or score_override if set)
```

### FM-SOFT-CONF C
```text
f_body = min(1, body_ratio / confirmation_body_min)
f_mom  = clamp( dir*(ema_fast-ema_slow)/ATR , 0, 1)
f_dist = exp(-(depth/adaptive_ceiling)^2)
f_disp = min(1, |disp_C-disp_O| / (1.5*ATR))
C_linear = Σ w_i f_i   (conf_weights)
C = (1-weak_link_weight)*C_linear + weak_link_weight*min(f_body,f_mom)
C = max(conf_floor, C)
```

### FM-FUSION-S
```text
S = G ** conf_alpha * C ** conf_beta
approve tier1 if S>=tier_1_threshold; tier2 if S>=tier_2_threshold
```

### FM-TRADE-GEOMETRY
```text
entry = retest_candle.close
LONG:  sl = disp.low  - sl_atr_buffer*ATR
SHORT: sl = disp.high + sl_atr_buffer*ATR
risk = |entry-sl|
tp1 = entry ± tp1_mult(intent)*risk
tp2 = entry ± tp2_atr_multiplier*risk
reject if SL on wrong side of entry (inverted SL)
```

### FM-RESET
```text
HTF id change (except protect EXPANSION/RETEST; never interrupt OPEN/TP1 trade)
retrace >= retrace_reset_pct of displacement body
price beyond extension_reset_fib * |disp_close - sweep_price| from sweep
```

---

## 11. Formula Execution Order

```text
RAW OHLCV (Candle)
  ↓
index++ ; append candle_buffer ; ATR = mean TR
  ↓
EMA update (fast/slow)
  ↓
ResetLogic.should_reset? → reseed range + reset_to_range (fall through)
  ↓
If active trade: intrabar trigger price → update_trade → TRADE_TP*/STOPPED
  ↓
STATE = RANGE:
    TTL countdown on pending_displacement
    detect_sweep → SWEEP or SHADOW_PENDING
  ↓
SWEEP: try_sweep_to_displacement (move/body/range/age gates) → DISPLACEMENT
       or SWEEP_EXPIRED
  ↓
DISPLACEMENT: try_displacement_to_expansion → EXPANSION
  ↓
EXPANSION: try_expansion_to_retest (depth + FM-028 ceiling) → RETEST + cache FM-027/028
           else expansion TTL → EXPIRED → RANGE
  ↓
SOFT CONF window (evaluating_soft_conf):
    compute_score G → soft conf C → S = G^α C^β
    shadow age penalty (λ=0 inert)
    zone mid filter + session allowlist
    → EXECUTION + build_trade + TRADE_OPENED
       or FILTER_REJECTED / inverted-SL (no trade object)
  ↓
CRT OUTPUT action dict + EventLogger + optional Trade
```

---

## 12. CRT State / Gate Trace

**Legal graph** (`VALID_TRANSITIONS`, crt_engine_v2.py:1076-1086):

```text
RANGE ↔ SHADOW_PENDING → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION → RANGE
EXPANSION → EXPIRED → RANGE
any setup → RANGE via reset
```

**XAUUSD funnel (bar-state occupancy counts):**

| State | Bars |
|-------|------|
| RANGE | 35197 |
| SWEEP | 7005 |
| DISPLACEMENT | 373 |
| SHADOW_PENDING | 43 |
| EXPANSION | 4605 |
| RETEST | 17 |
| EXECUTION | 5 |

**Event log (baseline events.jsonl):**

| Event | Count |
|-------|------:|
| RESET | 10881 |
| STATE_TRANSITION | 3874 |
| SWEEP | 3390 |
| BEGIN_SOFT_CONF | 17 |
| FILTER_REJECTED | 12 |
| TRADE_OPENED | 1 |
| TRADE_TP1 | 1 |
| TRADE_STOPPED | 1 |

**Telemetry:** 3433 `CANDIDATE_LIFECYCLE`, 17 `DECISION_DISTANCE`, 13 `RETEST_REPLAY`.

---

## 13. CRT OUT Contract

| Terminal | Producer | File region | Preceding state | Emitted | Destination |
|----------|----------|-------------|-----------------|---------|-------------|
| TRADE_OPENED | process_candle soft-conf approve | ~2759-2793 | RETEST→EXECUTION | trade id, entry/SL/TP, risk_pct, live_metrics | EventLogger + action dict → journal |
| TRADE_TP1 / TRADE_STOPPED / TRADE_TP2 | active trade mgmt | ~2329-2355 | EXECUTION | pnl metadata | EventLogger; journal close |
| TRADE_ABORTED | reset with open trade | ~2313-2316 | OPEN | reason | EventLogger |
| FILTER_REJECTED | zone / session | ~2696-2737 | soft conf approved | reason | EventLogger; no trade |
| inverted SL (no TRADE_OPENED) | build_trade returns None | ~1960-1975 | EXECUTION | log warning | no journal trade (funnel EXECUTION can > TRADE_OPENED) |
| SWEEP_DETECTED / DISPLACEMENT_CONFIRMED / EXPANSION_CONFIRMED / RETEST_CONFIRMED | state machine | process_candle branches | prior state | action string | action dict + telemetry |
| SWEEP_EXPIRED / EXPANSION_EXPIRED / EXPANSION_TTL_RESET | TTL/age | ~2488-2615 | SWEEP/EXPANSION | action | EventLogger / integrity |
| SHADOW_* | shadow path | ~2377-2480 | RANGE/SHADOW | action | telemetry counters |
| RESET | ResetLogic or post-resolution | multiple | any | reason | EventLogger |
| NONE | default | process_candle | any | none | — |

**Computed but not always emitted on TRADE_OPENED:** intermediate soft-conf component scores `f_body/f_mom/f_dist/f_disp` (debug logs only); taxonomy sweep_type (metadata).

---

## 14. XAUUSD Backtest Baseline

### Command

```text
PYTHONPATH=src BACKTEST_ENGINE_GATE=0 \
  python scripts/analysis/crt_xauusd_runtime_trace.py \
    --mode both --output-dir results/crt_xauusd_trace_run
```

Equivalent canonical CLI (without observational wrap):

```text
PYTHONPATH=src BACKTEST_ENGINE_GATE=0 \
  python src/runtime/backtest_v2.py \
    --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD \
    --output results/crt_xauusd_baseline --scorer calibrated
```

Note: `--scorer static` currently crashes (`CRTGaussianScorer.compute` lacks `direction` kwarg) — pre-existing harness bug; **not remediated** per task constraints. Calibrated path uses NoOpScorer when no gaussian is registered → CRT-only scoring decisions.

### Baseline metrics

| Metric | Value |
|--------|------:|
| Candidates (telemetry lifecycle) | 3433 |
| SWEEP events | 3390 |
| Soft-conf starts | 17 |
| FILTER_REJECTED | 12 |
| Approved trades | **1** |
| Win rate | 0.0 |
| Expectancy (avg_rr_net) | −0.0383 R |
| Profit factor | 0.0 |
| Max drawdown pct | 0.0004 |
| Gap resets | 121 |
| Sole trade | CRT-0001 LONG entry_raw=2318.21 @ 2024-06-17T15:00 → STOPPED pnl_rr_net≈−0.0383 |
| Trades CSV SHA-256 | `c4a10db1206d6310bee23a302792d284a573f1308fbe6682b49dc87c17c4fdc2` |

---

## 15. Runtime Value Trace Evidence

**Mechanism:** post-return wrap of `CRTEngine.process_candle` in `scripts/analysis/crt_xauusd_runtime_trace.py` — append-only JSONL; no mutation of return value or state.

**Trace file:** `results/crt_xauusd_trace_run/runtime_trace.jsonl`  
**Rows:** 14592 (all interesting actions + 80-sample budget for raw/NONE path proof)  
**Interesting action histogram (runtime wrap):**

| Action | Count |
|--------|------:|
| RESET | 10746 |
| SWEEP_DETECTED | 3390 |
| DISPLACEMENT_CONFIRMED | 315 |
| EXPANSION_CONFIRMED | 17 |
| RETEST_CONFIRMED | 17 |
| FILTER_REJECTED | 12 |
| SHADOW_SWEEP_DETECTED | 43 |
| SHADOW_EXPANSION_CONFIRMED | 43 |
| TRADE_OPENED | 1 |
| TRADE_TP1 | 1 |
| TRADE_STOPPED | 1 |

**TRADE_OPENED sample (abbreviated):**

```json
{
  "symbol": "XAUUSD",
  "timestamp": "2024-06-17 15:00:00",
  "candle_index": 1676,
  "raw_ohlcv": {"open": 2318.24, "high": 2319.92, "low": 2317.81, "close": 2319.29, "volume": 1692.0},
  "crt_inputs": {
    "atr": 2.167142857142835,
    "active_range": {"h_ref": 2326.24, "l_ref": 2316.85, "size": 9.39},
    "sweep": {"direction": "LONG", "price": 2316.56},
    "displacement_ohlc": {"open": 2321.45, "close": 2318.68, "low": 2317.89},
    "retest_ohlc": {"close": 2318.21},
    "cached_features": {
      "displacement_retrace": 1.0,
      "body_ratio": 0.7386666666666618,
      "displacement_atr_ratio": 1.712887438825469
    }
  },
  "crt_output": {"terminal_result": "TRADE_OPENED"}
}
```

Existing hooks also used: `XAUUSD_crt_telemetry.jsonl`, `XAUUSD_events.jsonl`, sweep_trace logger.

---

## 16. Baseline vs Trace Parity

```text
TRACE_BEHAVIOR_PARITY = PASS
```

| Check | Result |
|-------|--------|
| approved_trades | identical (1) |
| win_rate / expectancy / PF / maxDD / total_pnl_rr_net | identical |
| funnel_counts | identical |
| trades CSV SHA-256 | **byte-identical** `c4a10db1…c4fdc2` |
| summary JSON SHA-256 | **byte-identical** |

Evidence: `results/crt_xauusd_trace_run/parity_compare.json`.

---

## 17. Contradictions and Unresolved Gaps

1. **Symbol name:** Task title uses XAUUSDT; corpus/config use **XAUUSD** only. User authorized substitution; literal XAUUSDT still absent.
2. **EXECUTION count (5) > TRADE_OPENED (1):** soft-conf can transition to EXECUTION then `build_trade` returns `None` on inverted SL (logged warnings) — funnel occupancy ≠ journaled trades.
3. **`total_setups=1` vs 3433 candidates:** journal “setups” ≠ telemetry candidate lifecycle (detection stream vs accepted trade).
4. **FeaturePipeline still runs** in harness (`skip_features=False`) — OUT OF SCOPE for CRT gates but present for journal feature columns; scorer is NoOp.
5. **`--scorer static` broken** by `direction=` kwarg mismatch — harness bug, not CRT formula.
6. **Volume unused** by CRT decision math but mandatory in loader schema.
7. **RiskScore weights** (0.35/0.25/0.20/0.20) and several coefficients (0.1·ATR min depth, 1.5·ATR in f_disp) are **hardcoded**, not config.
8. **Working tree dirty** at run time — commit pin is HEAD; absolute reproducibility of non-CRT dirty modules not claimed.
9. **Phase-1 corpus status** remains non-AUTHORITATIVE per binding JSON residuals (open-time label, broker calendar, E-MT-01) — does not block observational CRT trace.
10. **PowerShell stderr wrapping** may yield process exit 1 even when parity PASS (NativeCommandError on log lines); parity JSON is authoritative.

---

## 18. Final Verdict

```text
CRT_XAUUSDT_TRACE_STATUS = COMPLETE

XAUUSDT_CORPUS = NOT_FOUND
XAUUSDT_BACKTEST_SUPPORTED = NO
XAUUSD_CORPUS = FOUND
XAUUSD_BACKTEST_SUPPORTED = YES
XAUUSD_CONFIG_SUPPORTED = YES
INSTRUMENT_EXECUTED = XAUUSD   # user-approved substitute

ACTIVE_CRT_AUTHORITY = CRTEngine.process_candle @ src/config_layer/crt_engine_v2.py
CRT_INPUT_VALUE_COUNT = 34
CRT_DERIVED_FORMULA_COUNT = 22
CRT_CONFIG_DEPENDENCY_COUNT = 48
CRT_HARDCODED_BEHAVIOR_CONSTANT_COUNT = 18
CRT_TERMINAL_OUTPUT_COUNT = 16
BASELINE_CANDIDATE_COUNT = 3433
BASELINE_TRADE_COUNT = 1
TRACE_BEHAVIOR_PARITY = PASS
UNRESOLVED_GAPS = 10
REPORT_PATH = reports/CRT_IN_OUT_XAUUSDT_TRACE.md
```

### Count definitions (audit)

- **Input values (34):** O,H,L,C,V,ts,index,prev_close,body_size,range,body_ratio,is_bullish,h_ref,l_ref,eq,size,ATR,TR,sweep_price,sweep_dir,double,disp_OHLC,retest_OHLC,depth_abs,adaptive_ceiling,disp_atr_ratio,disp_retrace,ema_fast,ema_slow,G components,C,S,spread_pct,session_label,htf_id (+ state ages/TTL as bound counters).  
- **Derived formulas (22):** listed in §10 (body through reset/trade geometry).  
- **Config deps (48):** all `CRTConfig` fields.  
- **Hardcoded behavior constants (~18):** RiskScore weights; sweep base/bonus/prox cap; breakout 0.5/3; time 1.0/0.8/0; min_depth 0.1; f_disp 1.5; risk floors 0.005/0.015; wick eps 0.001; soft-conf structure; inverted-SL logic; partial TP 50% in executor (harness-adjacent).  
- **Terminals (16):** TRADE_OPENED, TRADE_TP1, TRADE_TP2, TRADE_STOPPED, TRADE_ABORTED, FILTER_REJECTED, SWEEP_DETECTED, DISPLACEMENT_CONFIRMED, EXPANSION_CONFIRMED, RETEST_CONFIRMED, SWEEP_EXPIRED, EXPANSION_EXPIRED, EXPANSION_TTL_RESET, SHADOW_SWEEP_DETECTED, SHADOW_EXPANSION_CONFIRMED, RESET (+ NONE non-terminal).

---

*End of observational report. No production formulas, configs, or models were modified for this trace.*
