# FC1-A Post-Implementation Measurement Note

_Date: 2026-07-11 · change_id `CH-fc1a-swing-causal` · ACTIVE_VERSION=`v2_multi_2026_04`._

## Acceptance (tests — green)

| Requirement | Evidence |
|---|---|
| Production binds to causal | `tests/test_fc1a_swing_causal.py::test_production_binds_to_causal_not_centered` |
| Centered_batch preserved | `test_centered_batch_preserved_byte_stable_vs_math` |
| No hybrid graph | `test_no_hybrid_graph_structure_uses_causal_refs` |
| Prefix-invariance (production interior) | `test_prefix_invariance_production_structure_interior` |
| Env non-mutation | `test_trust_env_does_not_mutate_production_or_centered` |
| Online ≈ batch structure | `test_online_causal_matches_batch_on_history` |
| Live FeatureStore causal overwrite | `test_feature_store_overwrites_zero_structure_with_causal` |
| Provenance sidecars | `test_provenance_sidecars_exist` |

## Ledger differential policy

Per contract §7: **byte-identical ledgers are NOT required**. Phase A already measured the centered→causal total-effect magnitude on BNB/SOL under gate-ON/OFF (ledgers identical on that population; PC-2 failed → structural importance inconclusive). Post-FC1-A production **is** the former causal arm; a re-run vs pre-change baseline would restate Phase A A/B, not a new authority claim.

**Do not** interpret any post-change identical ledger as “structure economically irrelevant.”

## Artifacts

- `models/rr_model.provenance.json` — `PIT_UNCLEAN_CENTERED_SWINGS`
- `models/zone_registry.provenance.json` — `PIT_UNCLEAN_CENTERED_SWINGS`

## Code surfaces

- `src/features/feature_pipeline.py` — production bind + causal structure graph
- `src/features/causal_structure.py` — online series helper
- `src/core/feature_store.py` — live delayed-confirmed structure
- Identity registry: bare `swing_high`/`swing_low` → `FEAT-SWING_*_CAUSAL_CONFIRMED`
