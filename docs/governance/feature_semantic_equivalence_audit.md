# Feature semantic equivalence audit

Contract `FEATURE-SEMANTIC-EQUIVALENCE-V1` version `1.0.0`.
Contract hash `02ab5280686e767798ba1094f5757e4cddfe9866595b9d874bf487aca00e0818`.

The frozen 35-feature prefix order is unchanged. This audit does not migrate it.
Name equality, vector length, read-side aliases, and schema hashes are not semantic equivalence.
Semantic conformance is not model quality, execution correctness, or profitability.

Architecture semantically consistent: **False**.

| Status | Edges |
|---|---:|
| MATCH | 0 |
| DRIFT | 5 |
| UNMAPPED | 3 |
| AMBIGUOUS | 0 |
| UNVERIFIED | 17 |

| Branch | Concept | Status | Evidence |
|---|---|---|---|
| `manifest:FeaturePipeline` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:BacktestRunner` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:CRTEngine` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:BitNet` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:Gaussian_live_heuristic` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:Gaussian_v4_mirrored_38dim` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:ZoneGate` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:RR_Engine` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:rr_fusion` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:TradeNet` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:secondlow` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:HypothesisRunner` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `manifest:live_engine_hook` |  | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |
| `live_engine_hook.historical_body_ratio` | FM-010 | DRIFT | `src/features/candle_math.py` 64-74 |
| `live_engine_hook.current_body_ratio` | FM-010 | UNMAPPED | `src/runtime/live_engine_hook.py` 595-599 |
| `live_engine_hook.wick_size_local` | FM-002 | DRIFT | `src/runtime/live_engine_hook.py` 588-593 |
| `live_engine_hook.session_string` | FM-052 | DRIFT | `src/runtime/live_engine_hook.py` 219-262 |
| `semantics.market.levels.double_sweep_window_1` | FM-060 | DRIFT | `src/semantics/market/levels.py` 79 |
| `semantics.market.conditions.double_sweep_window_param` | FM-060 | UNVERIFIED | `src/semantics/market/conditions.py` 53-58 |
| `feature_pipeline.double_sweep_legacy_arm` | FM-060 | UNMAPPED | `src/features/feature_pipeline.py` 1107-1127 |
| `feature_pipeline.double_sweep_e01_arm` | FM-060 | DRIFT | `src/features/feature_pipeline.py` 1108-1111 |
| `feature_store.missing_value_substitutes` | FM-060 | UNMAPPED | `src/core/feature_store.py` 108-111 |
| `gaussian_artifact.dimension_only` | gaussian_feature_schema | UNVERIFIED | `src/training/trainer.py` 414-539 |
| `tradenet_artifact.dimension_only` | tradenet_feature_names | UNVERIFIED | `src/training/trade_net_v2.py` 182-201 |
| `gaussian_live_heuristic.names_only` | FM-023 | UNVERIFIED | `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json` |

Unresolved edges stay UNMAPPED, AMBIGUOUS, or UNVERIFIED. They are not promoted to MATCH.
No production formula, model artifact, or config was edited to produce this report.
