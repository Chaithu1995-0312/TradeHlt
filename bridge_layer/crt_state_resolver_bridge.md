# crt_state_resolver_bridge.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_bridge_layer.py`.

CRT state identity is constructor-NEUTRAL: `crt_state_identity.yaml` declares what a state IS; the engine (`crt_engine_v2.py`) and the resolver (`crt_state_resolver.py`) are two CONSTRUCTORS of that one identity. A future constructor registers under `constructors:`, never re-declares `states:`. This file is the reachability bridge between vocabulary and each constructor.

Identity schema `crt_state_identity/v1` v`1`. 12 states, 2 declared constructors.

## Constructor capability contract

| Constructor | runtime_eligible | reaches_signal_state | produces_trade_geometry | produces_occupancy | produces_memory | covers_states |
|---|:--:|:--:|:--:|:--:|:--:|---|
| `engine` | True | True | True | True | True | 12 of 12 |
| `resolver` | False | False | False | True | True | 9 of 12 |

### Blocking gaps

- **`resolver` (GAP-RESOLVER-001)** — capability `reaches_signal_state`: EXECUTION is structurally unreachable — score gate fail-closes on every real vector.
- **`resolver` (GAP-RESOLVER-002)** — capability `produces_trade_geometry`: No entry/SL/TP model — the resolver has no trade-geometry construction at all.

## Per-state coverage by constructor

`not covered` means the constructor's capability contract does not list the state in `covers_states` — it makes no claim about it at all.

| State | ID | `engine` | `resolver` |
|---|---|---|---|
| `RANGE` | `CRT-S-RANGE` | covered | reachable |
| `SHADOW_PENDING` | `CRT-S-SHADOW_PENDING` | covered | reachable |
| `SWEEP` | `CRT-S-SWEEP` | covered | reachable |
| `DISPLACEMENT` | `CRT-S-DISPLACEMENT` | covered | reachable |
| `EXPANSION` | `CRT-S-EXPANSION` | covered | reachable |
| `EXPIRED` | `CRT-S-EXPIRED` | covered | reachable |
| `RETEST` | `CRT-S-RETEST` | covered | reachable |
| `EXECUTION` | `CRT-S-EXECUTION` | covered | **unreachable** |
| `RESOLUTION` | `CRT-S-RESOLUTION` | covered | **undefined** |
| `RANGE_C1` | `CRT-S-RANGE_C1` | covered | not covered |
| `MANIPULATION_C2` | `CRT-S-MANIPULATION_C2` | covered | not covered |
| `DISTRIBUTION_C3` | `CRT-S-DISTRIBUTION_C3` | covered | not covered |

## Named gaps (the honest part of the bridge)

- **`EXPANSION` / `resolver`** — `construction_diverges_from_engine: true` (declared divergence, not disputed)
- **`EXECUTION` / `resolver`** — GAP-RESOLVER-001 — see constructors.resolver.capabilities.blocking_gaps
- **`RESOLUTION` / `resolver`** — No states[].name block; no trade-state model to detect resolution from (market_crt_states.yaml comment on RESOLUTION).

## States with no resolver predicate

Declared in the identity authority, but `configs/formulas/market_crt_states.yaml` carries **no `when:` block** for them, so the resolver constructor cannot resolve them. The engine constructor is unaffected.

- `RANGE_C1` (CRT-S-RANGE_C1) — subgraph `parent_three_candle`
- `MANIPULATION_C2` (CRT-S-MANIPULATION_C2) — subgraph `parent_three_candle`
- `DISTRIBUTION_C3` (CRT-S-DISTRIBUTION_C3) — subgraph `parent_three_candle`


## Reading rule

`reachable` here means *this constructor's config declares and can reach the state*, NOT that a live trade path exists. Runtime eligibility is the separate `capabilities.runtime_eligible` flag, and promotion is a governance act (M4 QualificationGate -> PromotionManager) — never implied by a reachability cell.

