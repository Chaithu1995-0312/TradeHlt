# expansion_atr_min_distance — P2 bind (measurement only)

**Policy (locked):** No silent fallbacks or defaults — declared/loaded config only; missing key = fail-closed.

**Scope:** Measurement / classification only.

**Pin:** ACTIVE_VERSION `v2_htfcrt_2026_08` · evidence SHA `1890785daf31e9376c59b27e9f4d0e0998b99377` (re-verify on Windows if ahead).

---

## 1. Declared / loaded values

| Authority surface | Path | Value |
|---|---|---|
| YAML thresholds | `configs/formulas/market_crt_states.yaml:309` | **0.30** |
| Production params | `v2_htfcrt_2026_08.json` → `params.expansion_atr_min_distance` | **0.3** (= 0.30) |
| market_router FOREX | same JSON | 0.08 |
| market_router CRYPTO | same JSON | 0.15 |
| CRTConfig dataclass default | `state_identity.py:152` | 0.20 |

**Authority value:** **0.30** (production `params` / YAML thresholds). Router class profiles and CRTConfig default are not authority.

---

## 2. Live CRT engine bind path

1. Same production merge as other Tier-1 params: `load_prod_config_from_registry` → `ConfigBuilder.build(..., overrides=merged)` with **params winning**.
2. Live gate: `CRTEngine.try_displacement_to_expansion` — `crt_engine_v2.py:1551`  
   `min_distance = self.config.expansion_atr_min_distance * state.atr_abs`  
   then `abs(close - disp_close)` compared to that floor. Telemetry `config_key: expansion_atr_min_distance`.
3. Engine path: **`self.config.expansion_atr_min_distance` only** (no `.get` fallback). Under production load → **0.30**.

**Resolver path:**  
`CRTStateResolver._expansion_entry_allowed` — `crt_state_resolver.py:1887`  
`min_dist = float(thr.get("expansion_atr_min_distance", 0.20)) * atr_abs`  
YAML declare 0.30 + **illegal fallback 0.20**.

---

## 3. Illegal fallback / default sites

| # | Site | Defect | Shadow value |
|---|---|---|---|
| 1 | `state_identity.py:152` `expansion_atr_min_distance: float = 0.20` | dataclass default | 0.20 vs 0.30 |
| 2 | `crt_state_resolver.py:1887` `thr.get("expansion_atr_min_distance", 0.20)` | silent `.get` fallback | 0.20 |
| 3 | `market_router.classes.FOREX` = 0.08 / CRYPTO = 0.15 | class profiles diverge from params | 0.08 / 0.15 |
| 4 | `scripts/backtest/manual_backtest.py:50` `EXPANSION_ATR_MIN = 0.20` | hardcoded constant | 0.20 |

`threshold_refs` marks this key `crtconfig_duplicate` / `consumed: true` (resolver does read it).

---

## 4. Classification

| Dimension | Call |
|---|---|
| **Drift class** | **Shadowed** (+ **Duplicated**; router **Overloaded**/class-divergent) |
| Live engine bind | Clean `self.config` after production merge → authority **0.30** |
| Resolver bind | Masked by illegal `.get(..., 0.20)` |

P1 claim confirmed: declare ~0.30 vs fallback ~0.20.

---

## 5. Non-actions

No patches this pass.
