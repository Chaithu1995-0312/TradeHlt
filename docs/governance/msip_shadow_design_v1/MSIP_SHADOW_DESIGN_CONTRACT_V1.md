# MSIP Shadow Design Contract V1

**Status:** FROZEN design package — **PENDING_OWNER_ACCEPTANCE**  
**Generated:** 2026-07-14T10:26:18.740565+00:00  
**Architecture decision:** **C** — continuous market-state observation separate from CRT opportunity lifecycle  
**Task class:** OBSERVATION_ONLY  

---

## 1. Purpose

Define the **executable contract** for the next phase  
`MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN` **before any implementation**.

This contract answers five questions:

1. What is MarketStateVector?  
2. Which governed WHAT quantities feed each dimension?  
3. What belongs to HOW?  
4. How does shadow execution work?  
5. What evidence permits the next decision (A / B / CRT migration)?

---

## 2. Non-goals (hard)

- No `MarketStateVector` class coding until **G-IMPL-01**  
- No dynamic-loader coding  
- No CRT migration / cutover  
- No threshold selection for CRTConfig  
- No concurrent-candidate implementation  
- No trade-count optimization as success metric  
- No restoration of historical baseline hash golden equality  

---

## 3. MarketStateVector (summary)

See `MARKET_STATE_VECTOR_SCHEMA_V1.json`.

Dimensions: structure, liquidity, volatility, session, trend, candle_quality, optional crt_phase_observation (read-only).

**Must not include:** CRT private lifecycle memory, orders, fusion scores, economic metrics, HOW thresholds as identity.

---

## 4. WHAT feeds

See `MARKET_STATE_DIMENSION_AUTHORITY_MATRIX_V1.json`.

Primary producer: **FeaturePipeline / formula registry**.  
CRT-local ATR/EMA/body_ratio/wick: **parity audit required** before deprecating CRT-local use (`CRT_LOCAL_MATH_PARITY_AUDIT_V1`).

---

## 5. HOW

See `INTERPRETATION_CONFIG_SCHEMA_V1.json` (`msip_shadow` section).

HOW = bands, enables, instrument/timeframe overrides, comparison flags.  
HOW must not mutate CRT lifecycle or production admission.

---

## 6. Shadow execution

See `SHADOW_RUNTIME_BINDING_SPEC_V1.json`.

Hard invariant: **shadow cannot affect CRT state, events, trades, or execution**.

Provenance: `SHADOW_PROVENANCE_CONTRACT_V1.json`.

---

## 7. Comparison evidence for later decisions

See `SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1.json`.

Later **A** (policy research), **B** (concurrent candidates), or CRT consumer migration each have explicit criteria — none are automatic.

---

## 8. Promotion gates

See `MSIP_SHADOW_PROMOTION_GATES_V1.json`.

| Gate | Blocks |
|---|---|
| G-DESIGN-01 | Proceeding without owner acceptance |
| G-IMPL-01 | Coding MarketStateVector |
| G-SHADOW-01 | Claiming shadow quality |
| G-PARITY-01 | Deprecating CRT-local math |
| G-MIG-01 | CRT consumer cutover |

---

## 9. Option D wording (architecture package correction)

**D requires explicit CRT-boundary reopen authority and is unsupported by current evidence.**  
CLOSED does **not** make replacement permanently impossible; it makes D unauthorized until reopen conditions and new evidence.

---

## 10. Project state

```text
ARCHITECTURE QUESTION → DECIDED (C)
CURRENT CRT → remains authoritative opportunity lifecycle
NEXT PHASE → MSIP_SHADOW design (this package)
IMPLEMENTATION → NOT YET AUTHORIZED
```

---

## 11. Authority

Design freeze only. Grants no production authority, no economic claims, no CRT reopen.


---

## 12. WHAT/HOW consistency amendment (2026-07-14)

Consistency review: **PASS** (`DESIGN_CONTRACT_CONSISTENCY_REVIEW_V1`).

Every MarketStateVector field declares one of:

- `GOVERNED_OBSERVABLE`
- `DETERMINISTIC_DERIVED_WHAT`
- `INTERPRETED_STATE_LABEL_HOW` (requires config/version provenance + continuous twins)
- `OBSERVATIONAL_JOIN_ONLY` (`crt_phase_observation` only; no identity dependency)

Instrument/timeframe overrides are **HOW-only**.  
CRT-local atr/ema/body/wick: **no silent replacement** until parity audit.  
Owner acceptance authorizes **shadow implementation planning only**, not coding until G-IMPL-01.
