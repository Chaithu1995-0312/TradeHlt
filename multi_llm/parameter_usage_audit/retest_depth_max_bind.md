# retest_depth_max — P2 bind (measurement only)

**Policy (locked):** No silent fallbacks or defaults — declared/loaded config only; missing key = fail-closed.

**Scope:** Measurement / classification only.

**Pin:** ACTIVE_VERSION `v2_htfcrt_2026_08` · evidence SHA `1890785daf31e9376c59b27e9f4d0e0998b99377` (re-verify on Windows if ahead).

**Aliases checked:** `retest_depth_max` (canonical) · companion `retest_atr_depth_fraction` (adaptive ATR ceiling; **not** a rename of `retest_depth_max`).

---

## 1. Declared / loaded values (`retest_depth_max`)

| Authority surface | Path | Value |
|---|---|---|
| YAML thresholds | `market_crt_states.yaml:328` | **0.15** (Phase E1 align note) |
| Production params | `v2_htfcrt_2026_08.json` → `params.retest_depth_max` | **0.15** |
| market_router FOREX | same JSON | 0.35 |
| market_router CRYPTO | same JSON | 0.25 |
| CRTConfig dataclass default | `state_identity.py:142` | 0.25 |

**Authority value:** **0.15**.

### Companion alias `retest_atr_depth_fraction` (status)

| Surface | Value | Notes |
|---|---|---|
| YAML thresholds `:329` | 0.50 | declare for resolver thr block |
| Production `params` | **0.3** | engine authority when production-loaded |
| CRTConfig default `:155` | 0.50 | illegal default vs prod 0.3 |
| Resolver reads | **none** | `threshold_refs`: `crtconfig_duplicate_dead` / `consumed: false` |
| Engine reads | `self.config.retest_atr_depth_fraction` at `crt_engine_v2.py:1634`, `:1990`, `:2084` | LIVE on engine |

Engine adaptive ceiling (PATCH 5):  
`static_ceiling = retest_depth_max * range.size`  
`atr_ceiling = retest_atr_depth_fraction * atr`  
`adaptive_ceiling = max(static_ceiling, atr_ceiling)` (`crt_engine_v2.py:1633–1635`).

---

## 2. Live CRT engine bind path (`retest_depth_max`)

1. Production merge → `self.config.retest_depth_max` = **0.15**.
2. Sites: `crt_engine_v2.py:1633`, `:1989`, `:2083` (and telemetry `:1698`); also `_retest_ceiling` diagnostic `:3229`.
3. No engine `.get` fallback for this field.

**Resolver path:**  
`_continuous_gates_pass` for RETEST/EXECUTION — `crt_state_resolver.py:1598`  
`depth_max = float(thr.get("retest_depth_max", 0.25))`  
YAML declare 0.15 + **illegal fallback 0.25**.  
Prior E1 probe: resolver RETEST branch inert on measured corpus (value change did not move output) — still a policy defect.

**Research script:** `scripts/research/retest_divergence_probe.py:135` same `.get(..., 0.25)`.

---

## 3. Illegal fallback / default sites

| # | Site | Defect | Shadow value |
|---|---|---|---|
| 1 | `state_identity.py:142` `retest_depth_max: float = 0.25` | dataclass default | 0.25 vs 0.15 |
| 2 | `crt_state_resolver.py:1598` `thr.get("retest_depth_max", 0.25)` | silent `.get` | 0.25 |
| 3 | `retest_divergence_probe.py:135` same fallback | research script defect | 0.25 |
| 4 | Router FOREX 0.35 / CRYPTO 0.25 | class profile ≠ params | 0.35 / 0.25 |
| 5 | `manual_backtest.py:51` `RETEST_RANGE_FRAC = 0.25` | hardcoded shadow | 0.25 |
| 6 | `state_identity.py:155` `retest_atr_depth_fraction = 0.50` | dataclass default vs prod **0.3** | 0.50 |
| 7 | YAML `retest_atr_depth_fraction: 0.50` vs prod params **0.3** | declare split (YAML≠params); resolver never reads key | 0.50 vs 0.3 |

**Value-aligned research constants:** `visual_crt/driver.py` `RETEST_DEPTH_MAX = 0.15`, `RETEST_ATR_DEPTH_FRACTION = 0.3` — mirrors prod; still hardcoded shadows.

---

## 4. Dead candidates (brief)

| Candidate | Status |
|---|---|
| `max_displacement_age_candles` | YAML declare 3; `threshold_refs` **dead_unconsumed**; not a CRTConfig field; resolver does not read by name (displacement TTL is `lifecycle.pending_displacement_ttl_candles`). **Dead.** |
| `retest_atr_depth_fraction` | **Dead for resolver** (`consumed: false`); **Live for CRT engine** via `self.config` (prod authority **0.3**). Not an alias of `retest_depth_max` — companion adaptive ceiling. |

---

## 5. Classification (`retest_depth_max`)

| Dimension | Call |
|---|---|
| **Drift class** | **Shadowed** (+ **Duplicated**; companion fraction **Dead@resolver / Live@engine**) |
| Live engine bind | Clean `self.config` → authority **0.15** |
| Resolver bind | Masked by illegal `.get(..., 0.25)`; historically **Decorative/inert** on E1 corpus |

P1 claim confirmed: declare ~0.15 vs fallback ~0.25.

---

## 6. Non-actions

No patches this pass.
