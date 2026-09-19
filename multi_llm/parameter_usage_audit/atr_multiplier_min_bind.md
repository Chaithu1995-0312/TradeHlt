# atr_multiplier_min — P2 bind (measurement only)

**Policy (locked):** No silent fallbacks or defaults — declared/loaded config only; missing key = fail-closed. `.get(name, fallback)`, dataclass field defaults, and hardcoded constants that shadow declare are **defects**, not tunables.

**Scope:** Measurement / classification only. No threshold, engine, or production-config edits.

**Pin:** `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08` · repo evidence from `feature/trace-parquet-duckdb-query` @ `1890785daf31e9376c59b27e9f4d0e0998b99377` (Windows `D:\Tradelatest` may be ahead; re-verify if local SHA differs).

**Aliases:** `atr_mult` (informal / docs); runtime field name is `atr_multiplier_min`. Gate identity: range ATR gate (`candle.wick_size` / FM-002 `candle_range` ≥ multiplier × `atr_abs`).

---

## 1. Declared / loaded values

| Authority surface | Path | Value |
|---|---|---|
| YAML thresholds (resolver declare) | `configs/formulas/market_crt_states.yaml:305` | **1.0** |
| Production params (ACTIVE) | `configs/production/v2_htfcrt_2026_08.json` → `params.atr_multiplier_min` | **1.0** |
| market_router FOREX class | same JSON → `market_router.classes.FOREX` | 1.5 |
| market_router CRYPTO class | same JSON → `market_router.classes.CRYPTO` | 1.0 |
| CRTConfig dataclass default | `src/config_layer/state_identity.py:141` | 1.50 |
| YAML state prose (decorative) | `market_crt_states.yaml` DISPLACEMENT notes (~L185) | documents `(1.5)` |

**Authority value (locked policy):** **1.0** — production `params` under ACTIVE_VERSION (and YAML thresholds agree). Router FOREX / CRTConfig default / prose are **not** authority.

---

## 2. Live CRT engine bind path

1. `load_prod_config_from_registry(ACTIVE, instrument)` (`production_config.py`) merges `crt_engine ∪ params` (**params win**) as overrides onto `ConfigBuilder.build` → `market_router` class profile.
2. Live gate: `CRTEngine.try_sweep_to_displacement` — `src/config_layer/crt_engine_v2.py:1367`  
   `candle.wick_size < self.config.atr_multiplier_min * state.atr_abs`  
   Telemetry labels config_key `atr_multiplier_min` / config_source CRTConfig.
3. **Engine does not** `.get(..., fallback)` this key — it reads `self.config.atr_multiplier_min` only. Under production load, that field is **1.0** from `params` (overrides router FOREX 1.5).

**Resolver path (research-shadow, not live engine):**  
`CRTStateResolver._displacement_entry_allowed` — `crt_state_resolver.py:1820`  
`wick_min = float(thr.get("atr_multiplier_min", 1.5)) * atr_abs`  
reads YAML `thresholds` (declare 1.0) but carries **illegal fallback 1.5**.

---

## 3. Illegal fallback / default sites (defects)

| # | Site | Defect | Shadow value |
|---|---|---|---|
| 1 | `state_identity.py:141` `CRTConfig.atr_multiplier_min: float = 1.50` | dataclass field default | 1.50 vs authority 1.0 |
| 2 | `crt_state_resolver.py:1820` `thr.get("atr_multiplier_min", 1.5)` | silent `.get` fallback | 1.5 |
| 3 | `market_router.classes.FOREX.atr_multiplier_min = 1.5` | class profile diverges from `params` (masked until params merge) | 1.5 |
| 4 | YAML DISPLACEMENT prose `(1.5)` while thresholds declare 1.0 | decorative / mis-labeled prose | 1.5 |
| 5 | `scripts/backtest/manual_backtest.py:49` `DISP_WICK_MIN_ATR = 1.5` | hardcoded constant shadowing declare | 1.5 |
| 6 | `scripts/backtest/backtest_debug_harness.py` / `portfolio_validation.py` ad-hoc overrides `atr_multiplier_min: 1.2` | harness/governance literals | 1.2 |

**Value-aligned but still hardcoded (shadow class, value OK):**  
`src/research/visual_crt/driver.py:54` `ATR_MULTIPLIER_MIN = 1.0` — research sealed constant mirrors authority; still a declare-shadow under policy (not a live-engine bind).

---

## 4. Classification

| Dimension | Call |
|---|---|
| **Drift class** | **Shadowed** (+ **Duplicated** across YAML thr / CRTConfig / params / router) |
| Live engine bind | **Clean bind to loaded `self.config`** once production-merged (authority 1.0) |
| Resolver bind | **Masked** by illegal `.get(..., 1.5)` — declare 1.0 normally wins; missing key would wrongly use 1.5 instead of fail-closed |
| Prose | **Decorative** (stale 1.5 in state notes) |

P1 claim confirmed: declare ~1.0 vs fallback/default ~1.5.

---

## 5. Non-actions (this pass)

No engine patches, no YAML/JSON edits, no threshold changes.
