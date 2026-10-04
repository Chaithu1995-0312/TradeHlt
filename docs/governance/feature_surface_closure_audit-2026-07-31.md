# Feature Surface Closure Audit — 38 Canonical Features

_Generated 2026-07-31T05:51:03.854183+00:00 · ACTIVE_VERSION=`v2_multi_2026_04` · read-only synthesis._

## Verdict

**Code surface: 39/39 CLOSED · 0/39 PARTIAL · 0/39 OPEN. Doc alignment: 0/39 STALE_CENSUS labels. FC1-A structure + FC1-D rolling volregime production binds applied. RR/Zone remain PIT_UNCLEAN (separate economic-admissibility machine). No economic authority claimed.**

### Ready for
- PIT-correct batch production structure vectors (FC1-A)
- PIT-correct production volatility_regime rolling causal (FC1-D)
- Live delayed-confirmed structure via FeatureStore
- Research use of *_centered_batch / volatility_regime_global_batch
- wick_size as exact FM-002 candle_range alias (ontology)

### Blocked for CANONICAL FEATURE-SURFACE CLOSURE
- *(none — see rollup for residual PARTIAL/OPEN if any)*

### Blocked for ECONOMIC USE OF EXISTING ARTIFACTS
- RR PIT_UNCLEAN_CENTERED_SWINGS — no promote/re-enable without causal revalidation
- Zone PIT_UNCLEAN_CENTERED_SWINGS — same provenance rule
- Causal dataset regeneration / revalidation before promotion of structure-sensitive models
- Existing model-specific lineage defects and §6.5 marginal-value requirements

> Feature-surface closure and artifact economic admissibility are separate. Closing the 38-feature code surface does NOT authorize RR/Zone reuse or imply edge.

## Schema

- dim=39 · schema_hash=c87a1aba7bc79803d04c680e0232389e · order_hash=0edda573414f0a64

## Rollup

| Metric | Value |
|---|---:|
| CLOSED (code) | 39 |
| PARTIAL_* (code) | 0 |
| OPEN_* (code) | 0 |
| Doc STALE_CENSUS | 0 |
| Ontology hits | 10/38 |
| Identity-registry hits | 8/38 |
| Write-site hits | 36/38 |
| RR active dims | 28/38 |
| Features with artifact flags | 28 |

### Code-closure status histogram

```json
{
  "CLOSED": 39
}
```

### PIT class — census vs effective (FC1-A overlay)

| Class | Census (2026-07-10) | Effective (post-FC1-A) |
|---|---:|---:|
| `CALENDAR_SAME_BAR` | 2 | 2 |
| `CAUSAL_COUNTER` | 1 | 1 |
| `CAUSAL_DELAYED_PUBLICATION` | 2 | 2 |
| `CAUSAL_DERIVED` | 9 | 9 |
| `CAUSAL_EWM` | 4 | 4 |
| `CAUSAL_ROLLING` | 5 | 5 |
| `RAW_CONTEMPORANEOUS` | 7 | 7 |
| `RAW_OR_SYNTHETIC_SAME_BAR` | 1 | 1 |
| `STRUCTURE_WITH_CAUSAL_SWING` | 8 | 8 |

## FC1-A status

- contract: **IMPLEMENTED**
- change: `CH-fc1a-swing-causal`
- finding: F-051
- structure remapped: `break_of_structure`, `double_sweep`, `higher_high`, `liquidity_distance`, `liquidity_pressure_score`, `liquidity_sweep`, `lower_low`, `sweep_detected`, `swing_high`, `swing_low`
- ledger importance: INCONCLUSIVE (PC-2 failed) — see F-051

## Families

| Family | n | code statuses | doc |
|---|---:|---|---|
| `ohlcv_raw` | 5 | `{'CLOSED': 5}` | `{'ALIGNED': 5}` |
| `volume_derived` | 2 | `{'CLOSED': 2}` | `{'ALIGNED': 2}` |
| `ema_trend` | 6 | `{'CLOSED': 6}` | `{'ALIGNED': 6}` |
| `volatility` | 3 | `{'CLOSED': 3}` | `{'ALIGNED': 3}` |
| `momentum_indicators` | 3 | `{'CLOSED': 3}` | `{'ALIGNED': 3}` |
| `structure_fc1a` | 10 | `{'CLOSED': 10}` | `{'ALIGNED': 10}` |
| `retest_secondaries` | 2 | `{'CLOSED': 2}` | `{'ALIGNED': 2}` |
| `candle_anatomy` | 3 | `{'CLOSED': 3}` | `{'ALIGNED': 3}` |
| `calendar` | 2 | `{'CLOSED': 2}` | `{'ALIGNED': 2}` |

## Per-feature matrix

| # | Feature | PIT effective | Code closure | Doc | Ontology | RR | Zone Σ|w| | FC1-A |
|---:|---|---|---|---|---|---|---:|---|
| 0 | `open` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 1 | `high` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 2 | `low` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 3 | `close` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 4 | `volume` | `RAW_OR_SYNTHETIC_SAME_BAR` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 5 | `volume_ratio` | `CAUSAL_ROLLING` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 6 | `double_sweep` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 7 | `ema_fast` | `CAUSAL_EWM` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 8 | `ema_slow` | `CAUSAL_EWM` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 9 | `ema_spread` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | Y | Y | 0.000 | — |
| 10 | `trend_bias` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 11 | `trend_strength` | `CAUSAL_ROLLING` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 12 | `momentum_score` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | Y | Y | 0.000 | — |
| 13 | `atr` | `CAUSAL_ROLLING` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 14 | `volatility_ratio` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | Y | Y | 0.320 | — |
| 15 | `rsi_14` | `CAUSAL_ROLLING` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 16 | `macd_line` | `CAUSAL_EWM` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 17 | `macd_signal` | `CAUSAL_EWM` | **CLOSED** | ALIGNED | — | N | 0.000 | — |
| 18 | `macd_hist_raw` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 19 | `macd_hist_z` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 20 | `sweep_detected` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 21 | `liquidity_sweep` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 22 | `break_of_structure` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 23 | `swing_high` | `CAUSAL_DELAYED_PUBLICATION` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 24 | `swing_low` | `CAUSAL_DELAYED_PUBLICATION` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 25 | `higher_high` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 26 | `lower_low` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | — | N | 0.000 | Y |
| 27 | `body_size` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | Y | N | 0.000 | — |
| 28 | `candle_range` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 29 | `body_ratio` | `RAW_CONTEMPORANEOUS` | **CLOSED** | ALIGNED | Y | Y | 0.320 | — |
| 30 | `volatility_regime` | `CAUSAL_ROLLING` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 31 | `session` | `CALENDAR_SAME_BAR` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 32 | `hour_of_day` | `CALENDAR_SAME_BAR` | **CLOSED** | ALIGNED | — | Y | 0.320 | — |
| 33 | `disp_strength` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | Y | Y | 0.320 | — |
| 34 | `retest_depth` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | Y | Y | 0.320 | Y |
| 35 | `candles_since_retest` | `CAUSAL_COUNTER` | **CLOSED** | ALIGNED | — | Y | 0.320 | Y |
| 36 | `liquidity_distance` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | Y | Y | 0.320 | Y |
| 37 | `liquidity_pressure_score` | `STRUCTURE_WITH_CAUSAL_SWING` | **CLOSED** | ALIGNED | Y | Y | 0.320 | Y |
| 38 | `volume_spike` | `CAUSAL_DERIVED` | **CLOSED** | ALIGNED | — | Y | 0.000 | — |

## Open remediations (adjacent surface)

```json
{
  "FC1-A": {
    "status": "IMPLEMENTED",
    "change_id": "CH-fc1a-swing-causal",
    "affects": [
      "break_of_structure",
      "candles_since_retest",
      "double_sweep",
      "higher_high",
      "liquidity_distance",
      "liquidity_pressure_score",
      "liquidity_sweep",
      "lower_low",
      "retest_depth",
      "sweep_detected",
      "swing_high",
      "swing_low"
    ]
  },
  "FC1-B-VOLUME": {
    "status": "DRAFTED_FC0_NOT_IMPLEMENTED",
    "title": "Separate T-003 volume proxy identity from source volume",
    "change_id": "FC1-B-VOLUME-SEMANTIC-SPLIT"
  },
  "FC1-C-FM-IDENTITY": {
    "status": "DRAFTED_FC0_NOT_IMPLEMENTED",
    "title": "Separate FM-020/021 pipeline identities from FM-027/028 CRT identities",
    "change_id": "FC1-C-FM-IDENTITY-SEPARATION"
  },
  "FC1-D-VOLREGIME": {
    "status": "IMPLEMENTED",
    "title": "volatility_regime global rank \u2192 causal regime semantic",
    "change_id": "FC1-D-VOLREGIME-CAUSAL"
  },
  "F-051": "registered; FC1-A implemented",
  "rr_zone_provenance": {
    "rr": "PIT_UNCLEAN_CENTERED_SWINGS",
    "zone": "PIT_UNCLEAN_CENTERED_SWINGS",
    "rule": "no promote/re-enable/economic evidence without causal revalidation"
  }
}
```

## Sources

- **lineage_census:** `docs/governance/feature_38_lineage_census-2026-07-31.json`
- **producer_consumer_graph:** `docs/governance/phase1_run1_feature_producer_consumer_graph-2026-07-10.json`
- **consumer_binding_manifest:** `docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json`
- **dependency_graph:** `docs/governance/feature_dependency_graph_fc05-2026-07-10.json`
- **feature_contract_v1:** `docs/governance/feature_contract_v1-2026-07-10.json`
- **identity_registry:** `docs/governance/phase1_feature_identity_registry-2026-07-10.json`
- **universe_census:** `docs/governance/phase1_run1_feature_universe_census-2026-07-10.json`
- **ontology:** `configs/formulas/market_ontology.yaml`
- **fc05_closure_manifest:** `docs/governance/feature_pipeline_fc05_closure_manifest-2026-07-10.json`
- **fc1a_contract:** `docs/governance/feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json`
- **fc1a_impl:** `docs/governance/fc1a_post_implementation_measurement-2026-07-11.md`
- **pit_decision:** `docs/governance/pit_phaseA_centered_swing_decision_record-2026-07-11.json`
- **geometry_census_summary:** `docs/governance/geometry_census_summary.json`
- **rr_provenance:** `models/rr_model.provenance.json`
- **zone_provenance:** `models/zone_registry.provenance.json`

## Method notes

1. **Read-only** — no `src/` or config mutation; synthesizes dated artifacts.
2. **FC1-A overlay** updates *effective* PIT for the structure family; census file remains historical (DOC_STALE flag).
3. **CLOSED** requires schema + lineage + producer + no blocking issue; ontology gaps and stale docs yield PARTIAL.
4. **Authority:** architecture/governance surface hygiene only — no ΔG001 claim.
