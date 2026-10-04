# bridge_layer — trading vocabulary → repository measurement authorities

> **GENERATED — do not edit by hand.** Regenerate with
> `python scripts/analysis/gen_bridge_layer.py`.

This directory is a **BRIDGE**, not a trading course. It maps trading VOCABULARY onto the
authorities the repository already owns, so that a question phrased in market terms can be
answered by naming a module, a vector slot, a state, and an artifact — not an opinion.

    OHLCV  →  Feature Ontology  →  State Ontology  →  Decision Ontology  →  Measurement Ontology

It teaches no entries and makes no directional claim. It is a **measurement system index**.

## Provenance

| Fact | Value |
|---|---|
| Generated from commit | `09ffcb11c6946c83fe8d984fa967a64952db234c` |
| Branch | `grokbotchanges` |
| Feature schema dimension | `48` |
| `SCHEMA_HASH` | `d40e7c7d5b624ef6d27670255ad95a35` |
| `FEATURE_ORDER_HASH` | `7901bb0d34f3d0af` |
| CRT identity states | `12` |
| CRT constructors | `2` |
| Vector-bound stateful identities | `13` |
| Declared non-vector stateful identities | `6` |
| Continous (uninterpreted) features | `35` |
| Concepts recorded | `17` |
| Dtype measurement | `data/mt5/XAUUSD_M15.csv (first 400 rows)` |

## Source authorities (read, never modified by the generator)

| Layer | Authority | File |
|---|---|---|
| Measurement | `CANONICAL_FEATURES`, `_FM_ID_TO_NAME` | `src/features/feature_schema.py` |
| Measurement | pipeline stages | `src/features/feature_pipeline.py` |
| Feature (WHAT) | ontology sections + `impl` bindings | `configs/formulas/market_ontology.yaml` |
| State | value → declared state | `src/features/feature_states.py` |
| Decision | state identity (Tier 1) | `configs/formulas/crt_state_identity.yaml` |
| Decision | resolver predicates | `configs/formulas/market_crt_states.yaml` |
| Execution | engine traversal | `src/config_layer/crt_engine_v2.py` |
| SMC primitives | `impl` for FM-075…FM-083 | `src/features/smc/*.py` |
| Ingestion | raw OHLCV contract | `src/data_ingestion/ohlcv_schema.py` |

## Files

| File | Answers |
|---|---|
| [`CANONICAL_FEATURES.html`](CANONICAL_FEATURES.html) | What are the 48 vector slots, their FM-IDs, sections, categories, and measured dtypes? |
| [`concepts.yaml`](concepts.yaml) | For each trading concept: observable definition, feature, state, authority, storage, evidence, observable-vs-derived, status. |
| [`feature_schema.bridge.md`](feature_schema.bridge.md) | Which concept does each vector index / FM-ID belong to? Coverage gaps. |
| [`state_ontology.md`](state_ontology.md) | Every declared feature state, vector-bound and not. |
| [`crt_engine_v2_concept_map.md`](crt_engine_v2_concept_map.md) | Which CRT state does a concept land on, via which predicate kernel? |
| [`crt_state_resolver_bridge.md`](crt_state_resolver_bridge.md) | Which states can each constructor actually reach, and what blocks the rest? |

## Generation order

1. `read_schema()` — live `CANONICAL_FEATURES`, `_FM_ID_TO_NAME`, hashes
2. `read_ontology()` — section / category / `impl` / states per feature
3. `read_states()` — `FeatureStateEncoder` inventory
4. `read_crt_identity()` + `read_resolver_states()` — 12 identities, 2 constructors, resolver scope
5. `measure_dtypes()` — real dtypes via `FeaturePipeline.run()` (degrades to "not measured")
6. `validate()` — fail-closed consistency gate
7. render → write

## Validation

```bash
# regenerate / revalidate (no writes)
python scripts/analysis/gen_bridge_layer.py --check

# regenerate artifacts
python scripts/analysis/gen_bridge_layer.py
```

The generator **fails closed**: a non-empty validation problem list aborts before any file is
written. Checks enforced:

- canonical feature count equals `CANONICAL_FEATURE_DIM`, names unique
- the FM-ID map is **bijective** onto `CANONICAL_FEATURES`
- every concept record carries all required fields and a status from the closed vocabulary
- every FM-ID cited by a concept exists in the live identity map
- a `present*` record must name an authority; an `absent` record must not
- any concept declared `present_no_resolver_predicate` must genuinely be absent from the
  resolver's declared predicate list

## Status vocabulary

| Status | Meaning |
|---|---|
| `present` | declared + authority + reachable |
| `present_unwired` | declared + authority implemented, not wired to runtime |
| `present_no_resolver_predicate` | declared + engine constructor; resolver config has no predicate |
| `present_constructor_unreachable` | declared; named blocking gap in the capability contract |
| `present_undefined` | identity slot exists; no definition |
| `absent` | no declaration, no authority — stated explicitly, never silently omitted |

## Coverage

**23 / 48** canonical features are named by at least one
concept record. The remainder are measured but not yet bridged to vocabulary — see
`feature_schema.bridge.md` §Coverage for the list. That gap is a **finding**, not a defect:
it is exactly the set of quantities the repository computes that no trading word in this
bridge's scope refers to.

## Scope limits

- Concepts in scope: OHLCV, Range, Liquidity, Sweep, Displacement, FVG, Order Block, Breaker Block, Mitigation Block, HTF Context, Manipulation, Distribution, CHoCH, EQH, EQL, PDH, PDL.
- Not in scope: entry/exit rules, directional prediction, position sizing.
- This bridge grants **no** runtime authority, **no** promotion, and changes **no** engine
  behaviour. Promotion is a governance act (M4 QualificationGate → PromotionManager).
