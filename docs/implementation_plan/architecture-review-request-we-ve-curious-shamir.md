# ZoneGate 39-dim Retrain + Registration

> Supersedes the Research-Runtime plan in this file (Steps 0/1/1b/1c are SHIPPED — boundary gate,
> read-only enumeration, ProductionBundle, ExperimentSpec). Step 2 is deferred behind this work.

## Context

I flagged a "divergence" on the ZoneGate: identity claims `feature_schema_dim: 39` while the v4
artifact's `feature_order` lists 38 names (missing `macd_hist_raw`). You directed: go with 39,
retrain, register.

**First, a correction to my flag.** It was not a defect. `models/zone_registry_v4_2026_07.provenance.json`
already adjudicates it explicitly — `scored_dims: 38`, `live_schema_dim: 39`, and:

> `macd_hist_raw` is deliberately absent: it has no trained statistics. The name-anchored
> extractor supports any subset in any order.

The v4 artifact was an `ALIGNMENT_REMAP`, **not a retrain** — it relabelled two names and zeroed one
weight, copying every `mu`/`sigma` through unchanged. Adding `macd_hist_raw` then would have
fabricated provenance. So the 38/39 gap is a deliberate, documented state, and the honest way to
close it is exactly what you asked for: a real retrain that produces real statistics.

**What this work is actually worth.** Two governance wins, and no economic claim:

1. **PIT cleanliness.** The live artifact is tagged `PIT_UNCLEAN_CENTERED_SWINGS` (F-051) and
   carries a second contaminated dim (`volatility_regime` trained under the GLOBAL_BATCH full-frame
   rank, pre-FC1-D). F-051's operational rule forbids promotion "without causal re-dataset/rebuild/
   revalidation." FC1-A and FC1-D have since shipped — `feature_pipeline.py:653` publishes
   `df["swing_high"] = swing_high_causal` and `:550` sets `volatility_regime =
   volatility_regime_rolling_causal`. So a retrain on a **regenerated** corpus is the causal
   revalidation F-051 demands. This is the real prize.
2. **Schema alignment.** The artifact stops being a hand-remapped descendant of a May-2026 training
   run and becomes a first-class trained model against the current schema.

**What it is NOT.** F-041B established 0/8 zones clear honest `E>0`, and F-036 established the gate
is non-pivotal (ΔG001 ≡ 0). Retraining grants **no** economic authority (§6.5). Expect ~0 decision
change; if the ledger moves materially, that is a signal to investigate, not to celebrate.

### Decisions taken

| Decision | Choice | Consequence |
|---|---|---|
| 39th dim | **Retrain the 38-name subset only** | `macd_hist_raw` = `macd_line − macd_signal` is a price-unit quantity; `scale_free_v1` already zeroes both its parents, so including it would add a weight-0.0 inert dim. Excluded — centroids/sigma computed on exactly the scored names. |
| Corpus | **Regenerate BNBUSDT detections** | Like-for-like with v3 (same population: the detection stream), so new-vs-old centroids are directly comparable. |

"Go with 39" therefore means: **accept the 39-dim live schema as truth**, and have the zone model
score a 38-name subset of it — which is precisely what the name-anchored extractor supports and what
the v4 provenance already declares correct.

### Blocking prerequisite

`src/features/feature_schema.py` is **modified but uncommitted** (`macd_hist_raw` is absent at HEAD,
present in the working tree). Training and registering a production model against an uncommitted
schema produces **unreproducible provenance** — the registered artifact would cite a schema no
commit contains. The 39-dim schema change must be committed (or explicitly frozen with a recorded
SHA) before the artifact is registered. This is a decision for you; I will not commit unprompted.

---

## Implementation

### Phase 0 — verify the PIT premise (read-only, blocking)

Do not assume the retrain will be PIT-clean; prove it before spending the corpus run.

- Confirm `scripts/research/opportunity_scanner.py` builds its feature payload through
  `FeaturePipeline` (so it inherits the causal swing/vol-regime publication) and not through a
  legacy or centered path.
- Confirm the emitted record carries all 39 canonical names, and that
  `swing_high`/`swing_low`/`volatility_regime` come from the causal columns.
- If either fails, **stop**: the retrain would silently reproduce F-051 contamination under a
  "clean" label, which is worse than the current honestly-tagged artifact.

### Phase 1 — regenerate the BNBUSDT detection corpus

```bash
python scripts/research/opportunity_scanner.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT
```

Output: `logs/BNBUSDT/<run>/opportunities.jsonl`. Record its SHA-256, row count, and the
`git rev-parse HEAD` of the schema commit — these become the retrain's provenance.

### Phase 2 — additive `--exclude-feature` on the clusterer

`scripts/research/discover_zones.py` clusters over `CANONICAL_FEATURE_ORDER`, which is now 39 wide.
To train the 38-name subset, add a **repeatable, default-empty** `--exclude-feature` flag.
Default (no flag) must leave existing invocations byte-identical — that is the acceptance test.

```bash
python scripts/research/discover_zones.py \
  --opportunities logs/BNBUSDT/<run>/opportunities.jsonl \
  --exclude-feature macd_hist_raw \
  --n-clusters 8 --output models/zone_registry_v5_2026_07_v1.json
```

Keep `k=8` and `seed=1337` to stay comparable with v3.

### Phase 3 — convert to the `v2_gaussian` runtime schema

Reuse `scripts/research/convert_zones_v1_to_gaussian.py` **unchanged**. Its method is verified
against the live artifact (membership 8/8, mu Δ0.0 across 38×8, sigma 38/38 exact) by
`scripts/analysis/zone_registry_provenance_probe.py`. Do not re-derive it:

- `mu` = KMeans centroid
- `sigma` = **global** per-dim std (ddof=0) over the whole corpus, floor `0.01`, replicated per zone
  (per-cluster dispersion was tested and refuted)
- `weights` = `scale_free_v1` — 0.0 on absolute price/volume dims, uniform `1/n_active` on the rest
- `threshold` = 0.3 declared constant (inert on the live path — the spine reads only `top_scores`)

### Phase 4 — measure decision impact BEFORE promoting

This is the only live HARD gate, so measure first. Use the established F-036 / remap-probe method
(gate-ON, `BACKTEST_ENGINE_GATE=1`), comparing v4 → v5 on BNBUSDT and at least one non-training
instrument (ETH or SOL) to expose overfit:

- cluster-score mean/max-|Δ|, pass rate, **decision flips**, and the trade ledger diff
- the v4 remap's own baseline for reference: score mean 0.74254 → 0.75461, `decision_flips: 0`

Write the result into the new artifact's provenance whichever way it lands.

### Phase 5 — register and promote

```bash
# register (inactive) — src/core/model_registry.py:1398
register_zone_gate(version="v5_causal_2026_07", model_file="models/zone_registry_v5_2026_07.json",
                   n_zones=8, n_clusters_requested=8, feature_order=[...38 names...])
promote_zone_gate("v5_causal_2026_07")   # atomic, single-active enforced
```

Then point the runtime at it: `engine_runner.zone_registry_path` in
`configs/production/v2_multi_2026_04.json`. **Editing the active config requires your approval**
(§6.2 gate) and the manifest-vs-runtime parity invariant
(`tests/test_zone_manifest_runtime_parity.py`) must be green after the change — the manifest's
active `model_file` and the config-loaded path must be the same file by SHA.

### Phase 6 — provenance + findings

- Write `models/zone_registry_v5_2026_07.provenance.json` following the v4 file's shape:
  `derived_from`, corpus SHA + row count, schema commit SHA, `change_class: RETRAIN`, the Phase-4
  measured impact, and `authority: "NONE"`.
- `pit_status`: claim `PIT_CLEAN_CAUSAL` **only if Phase 0 passed**; cite FC1-A/FC1-D. Otherwise
  carry `PIT_UNCLEAN_CENTERED_SWINGS` forward.
- Update `docs/current-findings.md`: F-041/F-051 gain a dated entry recording that the ZoneGate
  artifact was causally revalidated. Do **not** flip F-041B (0/8 zones, no edge) — this retrain
  produces no economic evidence.
- `active_models.yaml` `zone_gate` identity: update selection version; keep
  `feature_schema_dim: 39` (the live schema) — the 38-name `feature_order` is the scored subset,
  and `production_bundle.py` will keep reporting both. Consider recording the subset explicitly so
  the bundle's dim divergence resolves to an intended state rather than a flagged one.

---

## Risks

1. **Phase 0 is the whole gamble.** If the scanner does not emit causal features, a "PIT_CLEAN"
   label would be a false claim on the only live gate — strictly worse than today's honest tag.
2. **New centroids on a fresh corpus are a real behavior change**, unlike the v4 remap. The May-2026
   corpus and a 2026-07 regeneration cover different market history, so centroid drift will mix
   "causal fix" with "different data." Phase 4 measures the combined effect; it cannot separate
   them. Attribute claims accordingly.
3. **F-009 per-instrument doctrine**: a BNBUSDT-trained zone model applied to all instruments is the
   pre-existing arrangement, not something this retrain fixes.
4. **Single-active invariant**: `_assert_single_active` and the parity test both gate promotion; a
   half-applied promote (registry flipped, config not) breaks the runtime. Do Phase 5's two edits
   together and re-run the parity test immediately.
5. **Rollback**: keep `zone_registry_v4_2026_07.json` in place and its registry entry intact.
   Rollback = `promote_zone_gate("v4_gaussian_runtime_2026_07")` + revert the config path.

## Verification

```bash
python -m pytest tests/test_zone_manifest_runtime_parity.py tests/test_zone_schema_migration.py -q
python -m pytest tests/test_model_paths_resolver.py tests/test_production_bundle.py \
  tests/test_model_resolver_enumeration.py tests/test_runtime_boundary.py -q
python scripts/governance/scan_runtime_boundary.py
python scripts/analysis/zone_registry_provenance_probe.py     # method re-verification
```

- `discover_zones.py` with no `--exclude-feature` reproduces its prior output byte-identically.
- `load_production_bundle()` reports the new version as `selected_and_enabled`, still
  `contested=False`, with the dim divergence either resolved or explicitly intended.
- Phase-4 ledger diff recorded in provenance (expected: ~0 flips, consistent with F-036).
- Pre-existing RED floors (geometry census, doc citations, model-paths literals) remain out of
  scope — do not let this work be blamed for them, and do not fix them here.
