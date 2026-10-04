# CRT Config Construction Protocol (P0 Design Freeze)

| Field | Value |
|---|---|
| **ID** | `CRT_CONFIG_CONSTRUCTION_PROTOCOL` |
| **Phase** | **P0 DESIGN** + **P1 OBSERVE** + **P2 PRODUCT FAIL-CLOSED** (shipped 2026-08-06) |
| **Frozen** | 2026-08-06 |
| **Closes (partial)** | F-057 class — silent threshold surface divergence on BacktestRunner product path |
| **Does not** | Change gate math / production JSON values; ban `ConfigBuilder.build` for tests |
| **Authority** | Protocol + observe stamps + product-path refuse ROUTER_BASE/UNKNOWN/SCHEMA |

Companion: `docs/handover/CRT_SM_INFRA_CONTEXT_PACKET.md` (r3) · `src/config_layer/crt_config_provenance.py` · `src/config_layer/config_builder.py` · `src/config_layer/production_config.py`.

---

## 0. Problem

Three different ways to obtain a `CRTConfig` produce **different numbers** for the same instrument:

| Source | How | Example XAUUSD `expansion_atr_min_distance` |
|---|---|---:|
| SCHEMA | `CRTConfig()` field defaults | 0.20 |
| ROUTER_BASE | `ConfigBuilder.build("XAUUSD")` → `market_router.classes.FOREX` | 0.08 |
| PRODUCTION_MERGED | `load_prod_config_from_registry(ACTIVE_VERSION, "XAUUSD")` | 0.30 |

Agents and programmatic callers that treat **builder == production** mis-model the spine.

---

## 1. Construction modes

| Mode | Meaning | Typical entry |
|---|---|---|
| **`PRODUCTION_MERGED`** | ACTIVE/versioned production JSON → `crt_engine` ∪ `params` (params win) ∪ instrument_overrides → builder | `load_prod_config_from_registry` · BacktestRunner when `crt_config is None` |
| **`ROUTER_BASE`** | market_router class profile ± optional sparse overrides | bare `ConfigBuilder.build(instrument)` |
| **`EXPLICIT`** | Caller-owned full field set (tests, A/B, replay via `from_existing`) | `ConfigBuilder.from_existing` · injected `BacktestConfig.crt_config` |
| **`SCHEMA`** | Raw dataclass defaults (discouraged in app code) | direct `CRTConfig()` — forbidden in app per builder rules |
| **`UNKNOWN`** | No provenance stamp | pre-P1 objects or direct construction |

---

## 2. Authority hierarchy (runtime)

```text
Intended product analysis
        ↓
PRODUCTION_MERGED CRTConfig
        ↓
Engine process_candle
        ↓
Docs / packet  (never authoritative)
```

**Rule:** never infer live thresholds from SCHEMA or ROUTER_BASE when claiming production fidelity.

---

## 3. Fail-closed matrix (design — not all enforced yet)

| Situation | P1 (observe) | P2 (shipped) |
|---|---|---|
| Product/backtest path, no instrument, no crt_config | Already errors (BacktestRunner) | keep |
| **BacktestRunner** with ROUTER_BASE / SCHEMA / UNKNOWN | WARN if stamped ROUTER | **RAISE** unless `BacktestConfig.allow_router_crt_config=True` |
| BacktestRunner + PRODUCTION_MERGED / EXPLICIT | allow | **allow** |
| Test inject via `mark_explicit(cfg)` or `from_existing` | EXPLICIT | **allow** |
| `CRT_CONFIG_STRICT=1` on `require_mode` | raise on mismatch | same |
| Live paper (future) | — | use same `assert_product_crt_config` |

**P2 entry:** `assert_product_crt_config` in `crt_config_provenance.py`, wired into `BacktestRunner.__init__` after CRTConfig resolution.

---

## 4. P1 observe implementation

| Artifact | Role |
|---|---|
| `src/config_layer/crt_config_provenance.py` | Mode enum, stamp/get/fingerprint, observe log |
| `ConfigBuilder.build` / `from_existing` | Stamp ROUTER_BASE or EXPLICIT |
| `load_prod_config_from_registry` | Re-stamp **PRODUCTION_MERGED** (wins over builder stamp) |
| `scripts/governance/crt_config_construction_census.py` | Static call-site census + optional live fingerprint demo |
| `tests/test_crt_config_provenance.py` | Floors |

### API (observe)

```python
from config_layer.crt_config_provenance import (
    ConstructionMode,
    get_provenance,
    fingerprint,
    require_mode,  # observe: logs; strict optional
)

cfg = load_prod_config_from_registry(get_active_version(), "XAUUSD")
prov = get_provenance(cfg)
assert prov.mode == ConstructionMode.PRODUCTION_MERGED
```

### Fingerprint (threshold identity, not full equality)

```text
(body_ratio_min, atr_multiplier_min, expansion_atr_min_distance,
 retest_depth_max, retest_atr_depth_fraction, atr_min_displacement)
```

---

## 5. Product entry points (P2 candidates — do not change in P1)

| Entry | Desired mode |
|---|---|
| CLI backtest | PRODUCTION_MERGED |
| BacktestRunner without explicit crt_config | PRODUCTION_MERGED (already via registry load) |
| Live hook / paper (when built) | PRODUCTION_MERGED |
| VA economic claims | N/A thresholds via other paths; CRT claims need PRODUCTION_MERGED |
| Unit tests | EXPLICIT or ROUTER_BASE OK |

---

## 6. Non-goals (P0/P1)

- No change to gate math or production JSON values.
- No global ban on `ConfigBuilder.build` without production merge.
- No fail-closed inside builder for missing production JSON.
- No CRTConfig schema field for source (frozen dataclass stays clean; side registry by `id(cfg)`).

---

## 7. Reopen / next

| Phase | Status |
|---|---|
| **P2** | **Shipped** — BacktestRunner product gate |
| **P3** | Optional: wire live_engine_hook / other product runners; CI job runs census |

### Escape hatches (documented)

```python
# Intentional router-profile experiment on backtest path:
BacktestConfig(..., crt_config=ConfigBuilder.build("XAUUSD"), allow_router_crt_config=True)

# Test inject custom thresholds without production merge:
from config_layer.crt_config_provenance import mark_explicit
cfg = mark_explicit(CRTConfig(body_ratio_min=0.55), instrument="TEST")
BacktestConfig(..., crt_config=cfg)  # EXPLICIT → allowed
```

---

## 8. How to run observe tools

```text
PYTHONPATH=src python scripts/governance/crt_config_construction_census.py
PYTHONPATH=src python scripts/governance/crt_config_construction_census.py --live-fingerprint
PYTHONPATH=src python -m pytest tests/test_crt_config_provenance.py -q
```

---

*P0 design frozen 2026-08-06. P1 observe shipped same date.*
