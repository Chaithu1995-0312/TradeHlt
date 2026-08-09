# CRT Configuration Reachability — Phase 5

**Program:** CRT Closure (audit-first)  
**Phase:** 5 of 8  
**Status:** **PASS**  
**Twin:** [`crt_config_reachability.json`](crt_config_reachability.json)  
**Probe instrument:** `BNBUSDT` via `load_prod_config_from_registry(v2_multi_2026_04)`  
**Field count:** 49 `CRTConfig` fields (IC-007 PLAN-001 added `retest_min_depth_atr_fraction`)

---

## Verdict

| Field | Value |
|---|---|
| **CRT_CONFIG_REACHABILITY_STATUS** | **MAPPED_WITH_GAPS** |
| REACHABLE | 43 |
| CONSUMED_DYNAMIC (intent TP1 mults) | 4 |
| LEGACY_ONLY | 1 (`score_threshold`) |
| DEAD_LOADED | 1 (`news_blackout_minutes`) |
| New findings | **none** (gaps documented; not flipped to F-ids this phase) |

Every CRTConfig field is classified. Highest-risk gaps are hardcoded policy and one dead loaded key — not silent unknown fields.

---

## Load chain (production backtest)

```text
production JSON (ACTIVE_VERSION)
  params  ──┐
  crt_engine ──┼─► merge (params wins over crt_engine)
  engine_runner.allowed_sessions ─► allowed_sessions
  crt_engine.instrument_overrides ─► last win
        │
        ▼
ConfigBuilder.build(instrument, overrides)
  base = market_router profile (5 keys CRYPTO/FOREX)
  replace(base, **overrides)   # prod merge wins for all provided keys
        │
        ▼
frozen CRTConfig → CRTEngine(config)
```

Entry: `backtest_v2.main` → `load_prod_config_from_registry(PROD_VERSION, instrument)`.

---

## Dual authorities

| ID | Description | Impact on BNB baseline |
|---|---|---|
| **DA-PARAMS-VS-CRT-ENGINE** | `params` and `crt_engine` both set CRT fields; **params wins** | Profile knobs (`body_ratio_min`, `retest_depth_max`, …) come from `params` |
| **DA-MARKET-ROUTER-VS-PROD** | Router seeds FOREX/CRYPTO 5-key base before overrides | BNB classified **FOREX** (not in `CRYPTO_SYMBOLS={BTC,ETH}`) — latent if a key is missing from JSON |
| **DA-ALLOWED-SESSIONS** | Not in `crt_engine` JSON; injected from `engine_runner` | Runtime `('LONDON','NEWYORK','OVERLAP')` |

### Market router misclassification (latent)

```text
classify_market("BNBUSDT") → FOREX
classify_market("SOLUSDT") → FOREX
classify_market("BTCUSDT") → CRYPTO
```

For the frozen BNB run, **params/crt_engine cover the profile keys**, so finals match prod JSON (e.g. `body_ratio_min=0.65`, not FOREX 0.6). Still an architectural footgun for any future key omitted from JSON.

---

## Status summary (all 48 fields)

### REACHABLE (42)
Includes ATR, sweep/expansion/retest gates, soft-conf manifold, shadow TTL/decay, SL/TP base mults, sessions, sizing_bands, exit_model, BitNet flags, etc.  
Full site list: JSON `matrix[]`.

### CONSUMED_DYNAMIC (4)
`tp1_atr_multiplier_{breakout,pullback,liq_sweep,reversal}` via:

```text
getattr(self.config, f"tp1_atr_multiplier_{intent}", self.config.tp1_atr_multiplier)
# crt_engine_v2.py:1957-1958
```

### LEGACY_ONLY (1)
| Key | Issue |
|---|---|
| `score_threshold` | Only `UltronRiskEngine.approve()` L1827. Live CRT path uses **`approve_with_soft_conf`** + `tier_1`/`tier_2`. Loaded from prod but **inert on primary soft-conf path**. |

### DEAD_LOADED (1)
| Key | Issue |
|---|---|
| `news_blackout_minutes` | In prod `crt_engine` JSON and CRTConfig; **never read**. News gate is boolean `set_news(active)` only. |

---

## Hardcoded shadows (not CRTConfig)

| ID | Literal | Site | Severity |
|---|---|---|---|
| HC-G-WEIGHTS | 0.35/0.25/0.20/0.20 structural G | L216-219 | **HIGH** |
| HC-RETEST-MIN-DEPTH | `config.retest_min_depth_atr_fraction * atr` | try_expansion_to_retest | **REMEDIATED** (PLAN-001) |
| HC-RISK-FLOOR | 0.005 / 0.015 | L1975-1981 | MED |
| HC-SESSION-PENALTY | 0.10 | L1817 legacy approve | LOW |
| HC-DOUBLE-SWEEP-BONUS | 0.10 | L1822 legacy approve | LOW |

Env: **`TRUST_INTRABAR_TOUCH`** can override `exit_model` (L2151).

---

## Highest-risk list (for later remediation — not Phase 5 fixes)

1. Structural G weights hardcoded (vs config-driven `conf_weights`)  
2. ~~Retest min depth `0.1*atr` hardcoded~~ → **REMEDIATED PLAN-001** (`retest_min_depth_atr_fraction`)  
3. `news_blackout_minutes` dead-loaded  
4. `score_threshold` legacy-only on soft-conf spine  
5. BNB/SOL → FOREX market_router classification  

---

## Test

`tests/test_crt_config_reachability.py` pins:

- 49 fields present in matrix (`retest_min_depth_atr_fraction` PLAN-001)  
- no unexpected UNREACHABLE keys  
- `news_blackout_minutes` DEAD_LOADED  
- `score_threshold` LEGACY_ONLY  
- intent TP1 mults CONSUMED_DYNAMIC  
- BNB runtime load matches prod for profile keys  
- BNB market class is FOREX (documents latent bug)

---

## Phase 5 return

```text
CRT_CONFIG_REACHABILITY_STATUS = MAPPED_WITH_GAPS
FIELD_COUNT = 49
DEAD_LOADED = news_blackout_minutes
LEGACY_ONLY = score_threshold
HARDCODED_HIGH = HC-G-WEIGHTS
HC-RETEST-MIN-DEPTH = REMEDIATED_PLAN001
BNB_MARKET_CLASS = FOREX (latent misclassification)
PHASE5_STATUS = PASS
NEXT = await Phase 6 authorization (PLAN-002 blocked pending dual-path design)
```

