# Population Registry (research sets)

**Status:** `STUB_REGISTERED`  
**version:** `POPREG.v1-stub`  
**run_id:** `arch_review_falsify_pack_20260908_023341`  
**arch_review:** `ARCH-REVIEW.v1`  
**Pin:** `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**Generated (IST):** 2026-09-08 02:33:41 IST

Machine-readable: `docs/governance/population_registry.json`  
Schema: `docs/research/reports/schemas/population.schema.json`

> **Freeze note:** L-003 package remains **L003_PACKAGE_FROZEN**. This registry is an **episode/registry extension** requested by architecture review — not a doctrine reopen.

## Purpose

Register **Populations** as first-class sets of units. Complements MeasurementObject Registry (Y_*). Closes Omega ambiguity called out in the architecture review (Population grade B).

## Layer reminder

| Layer | Role |
|---|---|
| MeasurementObject | maps on populations (`Y_* : Omega -> ...`) |
| **Population** | set of units (this registry) |
| JointStateCoordinate | `s in S` |
| JointStatePopulation | `{ x in Omega : Y_joint(x) = s }` |

## Registered populations (stub)

### Omega_anatomy_opportunity

| Field | Value |
|---|---|
| population_id | `Omega_anatomy_opportunity` |
| unit | anatomy trade_dataset opportunity row |
| membership_rule | BNB/BTC/ETH/SOL `trade_dataset_*.csv` rows (L-003F join corpus) |
| instrument_scope | BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT |
| n_observed | 559,768 |
| status | REGISTERED_STUB |

### Omega_bnb_anatomy

| Field | Value |
|---|---|
| population_id | `Omega_bnb_anatomy` |
| unit | BNBUSDT anatomy opportunity row |
| membership_rule | Subset of `Omega_anatomy_opportunity` with instrument=BNBUSDT |
| parent | `Omega_anatomy_opportunity` |
| n_observed | 139,942 |
| status | REGISTERED_STUB |
| used_by | JSE-001 / JSE-002 / JSE-003 |

### STATE_SL_TP_anatomy

| Field | Value |
|---|---|
| population_id | `STATE_SL_TP_anatomy` |
| membership_rule | `{ x in Omega_anatomy_opportunity : Y_joint(x) = STATE_SL_TP }` |
| parent | `Omega_anatomy_opportunity` |
| n_observed | 176,471 (L-003F/L-003L mass note) |
| aliases | `JOINT_STATE_SL_TP`, `EARLY_STOP_CANDIDATE` (SAFE_ALIAS only) |
| status | REGISTERED_STUB |
| next_episode | `PATH_GENERATION_FOR_STATE_SL_TP` (observe path-generation process) |

## Mathematical maps (bound)

```text
Y_scanner : Omega_anatomy_opportunity -> OutcomeLabel
Y_oracle  : Omega_anatomy_opportunity -> OutcomeLabel
Y_joint   : Omega_anatomy_opportunity -> S = L x L
```

## Non-promotions

- No edge / attribution unlock
- No src/ edits
- No L-003 doctrine rewrite
- Stub only — membership rules may be refined with explicit dataset SHA pins in a later errata
