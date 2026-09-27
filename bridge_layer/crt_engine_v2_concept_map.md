# crt_engine_v2_concept_map.md

> **GENERATED — do not edit by hand.** Regenerate with `python scripts/analysis/gen_bridge_layer.py`.

**This file does NOT touch the engine.** `src/config_layer/crt_engine_v2.py` remains the execution authority for live trading. This is a read-only bridge describing how trading vocabulary lands on the engine's declared states and predicate kernels.

## The traversal (SP-010 structural_walk)

```
RANGE -> SWEEP -> DISPLACEMENT -> EXPANSION -> RETEST -> EXECUTION -> RESOLUTION
  ^                    + SHADOW_PENDING branch (cross-window displacement memory)
  |                    + EXPIRED TTL branch
  +---------------------- reset (HTF window change / session gap)
```

Ordered application of `SP-001 swept_boundary` -> `SP-002 directional_impulse` -> (ATR extension) -> `SP-003 retest_band` -> soft-confirmation, driven by `StateMachine.process_candle`, one transition per bar.

## M15 execution states (subgraph: execution)

| State | ID | Ground | Memory | Emits bias | Emits signal | Resolver predicate |
|---|---|:--:|:--:|:--:|:--:|---|
| `RANGE` | `CRT-S-RANGE` | yes | — | — | — | yes |
| `SHADOW_PENDING` | `CRT-S-SHADOW_PENDING` | — | yes | — | — | yes |
| `SWEEP` | `CRT-S-SWEEP` | — | — | — | — | yes |
| `DISPLACEMENT` | `CRT-S-DISPLACEMENT` | — | yes | — | — | yes |
| `EXPANSION` | `CRT-S-EXPANSION` | — | yes | — | — | yes |
| `EXPIRED` | `CRT-S-EXPIRED` | — | yes | — | — | yes |
| `RETEST` | `CRT-S-RETEST` | — | yes | — | — | yes |
| `EXECUTION` | `CRT-S-EXECUTION` | — | yes | — | yes | yes |
| `RESOLUTION` | `CRT-S-RESOLUTION` | — | yes | — | — | yes |

## Parent-timeframe states (subgraph: parent_three_candle, disjoint)

| State | ID | Ground | Memory | Emits bias | Emits signal | Resolver predicate |
|---|---|:--:|:--:|:--:|:--:|---|
| `RANGE_C1` | `CRT-S-RANGE_C1` | yes | yes | — | — | **no** |
| `MANIPULATION_C2` | `CRT-S-MANIPULATION_C2` | — | yes | — | — | **no** |
| `DISTRIBUTION_C3` | `CRT-S-DISTRIBUTION_C3` | — | yes | **yes** | — | **no** |

`DISTRIBUTION_C3` is the **only** state in the whole identity with `can_emit_bias: true`.

## Concept -> state landing table

| Concept | Land on | Predicate kernel | Traversal step |
|---|---|---|---|
| Sweep | `CRTState.SWEEP` | `SP-001 swept_boundary` | RANGE -> SWEEP |
| Displacement | `CRTState.DISPLACEMENT` | `SP-002 directional_impulse` | SWEEP -> DISPLACEMENT |
| Retest | `CRTState.RETEST` | `SP-003 retest_band` | EXPANSION -> RETEST |
| Range | `CRTState.RANGE` | — (ground) | reset / initialise_range |
| Manipulation | `MANIPULATION_C2` | parent OHLC sweep of C1 boundary | parent subgraph |
| Distribution | `DISTRIBUTION_C3` | parent impulse away from swept side | parent subgraph |
| HTF Context | `HTFState` (NOT CRTState) | `classify_htf_state` | orthogonal |
| FVG / OB / Breaker / Mitigation / PDH / PDL / EQH / EQL / CHoCH | *no CRTState* | `features/smc/*` | distance features, not states |

## Declared valid transitions

```yaml
RANGE: ['SWEEP', 'SHADOW_PENDING']
SHADOW_PENDING: ['SWEEP', 'RANGE']
SWEEP: ['DISPLACEMENT', 'EXPANSION', 'RANGE']
DISPLACEMENT: ['EXPANSION', 'RANGE']
EXPANSION: ['RETEST', 'EXPIRED', 'RANGE']
EXPIRED: ['RANGE']
RETEST: ['EXECUTION', 'RANGE']
EXECUTION: ['RESOLUTION']
RESOLUTION: ['RANGE']
RANGE_C1: ['MANIPULATION_C2', 'RANGE_C1']
MANIPULATION_C2: ['DISTRIBUTION_C3', 'RANGE_C1']
DISTRIBUTION_C3: ['RANGE_C1']
```

## State metadata notes (verbatim from the identity authority)

- **`RANGE`** — Both constructors treat RANGE as ground. Resolver default: bars that fail every predicate set still fall through to RANGE (first-match exhaust, market_crt_states.yaml). Engine: RANGE is also where the pending-displacement TTL is counted down — a construction fact, recorded under constructors.engine, not here.
- **`SHADOW_PENDING`** — Memory-only occupancy: cannot be resolved from a single bar's features (market_crt_states.yaml declares an empty when-block for this state). Collapse SHADOW_PENDING -> SWEEP -> EXPANSION is TWO legal hops inside one process_candle on the engine constructor. Identity graph does NOT contain SHADOW_PENDING -> EXPANSION directly; see constructors.resolver.projection_allowances.
- **`SWEEP`** — The directional-impulse contract on the SWEEP-to-DISPLACEMENT edge (F-074) is owned by each constructor's own construction, not by this identity node.
- **`DISPLACEMENT`** — Unsigned energy-only SWEEP-to-DISPLACEMENT is illegal (F-074). Directional-impulse enforcement is a construction fact (constructors.engine / constructors.resolver), not a semantic-core field.
- **`EXPANSION`** — F-069 Category C: the resolver reaches EXPANSION via a declarative when-block (displacement_flag: [Displacement]) or sticky-dwell, never via the engine's try_displacement_to_expansion() ATR-extension state machine. This identity node does NOT encode the resolver predicate and does NOT encode the engine's extension algorithm — both are constructor bindings.
- **`EXPIRED`** — Temporal state — the resolver documents this as undetectable from features alone; it requires temporal TTL tracking (market_crt_states.yaml).
- **`RETEST`** — On the engine constructor, occupancy of RETEST is not a process_candle `s ==` dispatch branch — soft-confirmation runs on a flag-gated prelude (elif self.state.evaluating_soft_conf) after the dispatch chain. That is a construction fact, not a semantic-core fact; see constructors.engine.
- **`EXECUTION`** — The ONLY state with can_emit_signal: true (TRADE_OPENED commitment, concepts.yaml:442) — this is a Tier-1 capability declaration: what occupying EXECUTION AUTHORIZES, independent of which constructor reaches it. On the engine constructor, occupancy is not a process_candle `s ==` branch either — open-trade handling runs on state.active_trade BEFORE the dispatch switch and returns on close (construction fact). The resolver constructor cannot currently reach this state at all — see constructors.resolver.capabilities.blocking_gaps.
- **`RESOLUTION`** — is_cycle_reset: true — not a dead-end; the cycle-closing state before RANGE. Structurally unreachable on the resolver constructor today — no trade-state model at all.
- **`RANGE_C1`** — Ground state of the disjoint parent_three_candle subgraph (F-075). Not the same node as M15 RANGE — do not collapse.
- **`MANIPULATION_C2`** — A C2 sweep alone does not set the parent bias — bias requires DISTRIBUTION_C3 (F-074 at parent scale).
- **`DISTRIBUTION_C3`** — The ONLY state with can_emit_bias: true — a Tier-1 capability declaration (parent_crt.py:102-110). Not HTFState.DISTRIBUTION and not Romeo/Sujan 4H "State 3 Distribution" (F-077 — near-inverted meaning); do not collapse.

