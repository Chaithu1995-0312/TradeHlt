# B6 — schema-v4 artifact reconciliation

## Context

Schema v4.0 (39 dims) is live: `macd_hist` → `macd_hist_raw`+`macd_hist_z`, `wick_size` →
`candle_range`, FM-052 session domain {0,1,2} → {0..4}. The pipeline emits it, consumers are
migrated, and `SCHEMA_HASH` moved to `c87a1aba…`.

The B0 safety net is now doing its job and **blocking the spine**:

```
ZoneFeatureOrderError: zone registry models/zone_registry.json was trained on feature(s)
absent from the live schema: ['macd_hist', 'wick_size']
```

ZoneGate is the only artifact that can actually mis-decide — it's the sole live HARD gate (F-041,
`zone_mode=hard`) — so it refuses to load rather than score a misaligned vector. Nothing runs until
it's reconciled. B6 closes that, and stamps the four inert artifacts so their state is declared
rather than assumed.

### What the measurements say (read-only probes, this session)

**The zone "weights" are not learned.** Every zone carries `total_w = 1.0` made of exactly 25
weights of `0.04` — uniform `1/25` — with an **identical zero-set across all 8 zones**
(`open, high, low, close, volume, ema_fast, ema_slow, ema_spread, momentum_score, macd_line,
macd_signal, body_size, wick_size`). That is a hand-specified mask dropping the 13 price-level
dims, not a trained importance vector. Consistent with F-036 (non-pivotal) and F-041B (0/8 zones
clear honest E>0).

**Two of the three renames are numerically free:**

| v3 name | weight in all 8 zones | consequence |
|---|---|---|
| `wick_size` → `candle_range` | **0.0** (already masked out) | rename is inert — the dim was never scored |
| `macd_hist` → `macd_hist_z` | 0.04 | pure rename: stored `mu=-0.041, sigma=1.18` is unmistakably the **z-scored** distribution, so the trained stats describe `macd_hist_z` exactly |
| `session` | 0.04 | **genuine distribution change** — see below |

**Only `session` is a real problem, and it is decision-inert anyway.** Trained `mu=0.968,
sigma=0.8165` (σ = √(2/3), the exact std of a uniform 3-value partition — note it is *identical*
in all 8 zones, i.e. never estimated per-cluster) versus the measured v4 distribution
`mu=1.624, sigma=1.380` on 19,922 BNBUSDT bars. So the stored statistics no longer describe the
feature. Measured impact of zero-weighting it (6,000 bars, top_k=3, cluster_min_n=2,
spread_max=0.15, threshold=0.25):

```
cluster score  keep(stale mu/sigma) mean 0.74254   drop(zero-weight) mean 0.75461
delta          mean +0.01206   p95|d| 0.03219   max|d| 0.03576
pass rate      keep 100.0000%   drop 100.0000%   DECISION FLIPS = 0 (0.0000%)
```

Scores sit ~0.74 against a 0.25 threshold, so neither choice moves a decision. The choice is
therefore about **honesty, not economics** — and asserting a distribution we know is wrong is the
one option with no argument for it.

Re-estimating `mu`/`sigma` is **not** available: they are per-zone *cluster member* statistics, and
recomputing them would need the training set plus cluster membership. A global re-estimate would
fabricate provenance.

**Intended outcome:** the spine runs again on v4, with every artifact either (a) remapped with
proven alignment or (b) explicitly quarantined — and no artifact silently asserting stats that no
longer describe its inputs.

---

## B6.1 — ZoneGate (the only live artifact)

New file `models/zone_registry_v4_2026_07.json`, promoted; the v3 file stays untouched for
rollback and diffing (the F-041A register-and-promote pattern, not an in-place rewrite).

Build it with a small one-shot script (`scripts/governance/remap_zone_registry_v4.py`, kept for
provenance) that reads the v3 file and writes the v4 file — never hand-edit vectors:

- `feature_order`: rename `wick_size` → `candle_range`, `macd_hist` → `macd_hist_z`. **Length stays
  38** — `macd_hist_raw` is deliberately NOT added, because there are no trained statistics for it.
  A 38-name subset of a 39-dim schema is fully supported by the B0 name-anchored extractor
  (`tests/test_zone_gate_alignment.py::test_shorter_trained_order_scores_on_the_trained_subset`).
- `mu` / `sigma`: **byte-identical**, all 8 zones. The remap is a relabelling; no value moves.
- `weights`: single change — `session` → `0.0` in all 8 zones. Keep the slot (don't delete it) so
  the artifact stays positionally diffable against v3 and records that the dim existed and was
  retired. Active dims go 25 → 24; `total_weight` 1.0 → 0.96, which the scorer normalizes by.
- `schema_version`: `v2_gaussian` → `v4_gaussian`.
- New `provenance` block naming the source file + sha, the three renames, the zeroed dim with its
  reason and the measured 0-flip evidence, and `PIT_UNCLEAN_CENTERED_SWINGS` carried forward from
  `models/zone_registry.provenance.json` (F-051 — the remap does not clean it).

Then:
- `models/zone_gate_registry.json`: add `v4_gaussian_runtime_2026_07` (`active: true`, `model_file`
  = the new path, `feature_order` = the v4 list); set `v2_gaussian_runtime_2026_07` to
  `active: false`. The manifest requires exactly one active
  (`tests/test_zone_manifest_runtime_parity.py`).
- `engine_runner.zone_registry_path` in `v2_multi_2026_04.json` **and** the dimfix shadow config —
  they must stay one-key-apart (`tests/test_fm030_031_implementation_validation.py`).
- `active_models.yaml` zone_gate `identity`: `selection.version` → the new id;
  `feature_schema_dim` 38 → 39 at both sites (~:685, ~:702) since that field describes schema
  compatibility, plus a new `scored_dims: 38` so the subset relationship is explicit rather than
  inferred. `how_path_ref` must match the new config path or `resolve_zone_gate_runtime` fails
  closed (`require_how_match=True`, `require_identity_parity=True`).
- New `models/zone_registry_v4_2026_07.provenance.json` mirroring the v3 provenance + the remap.

## B6.2 — RR model: quarantine, do not remap

`models/rr_model.json` (and `_202605_bnb_v1/v2`) carry `n_features: 38`,
`feature_schema: canonical_38`, and **positional** `scale_mu` / `scale_sigma` / `ridge_w` (38 each)
plus `zero_indices` (11). Positional against the v3 order ⇒ structurally invalid under v4.

`rr_fusion.enabled = false` (F-038) so nothing loads it, and F-044/F-045/F-059 grant no authority to
retrain. Stamp only: add `schema_version: "3.0"` and
`incompatible_with_schema: "4.0"` + a one-line reason. **Do not** invent a `schema_hash` — these
files never had one, and adding it now would fabricate provenance. Add a test asserting the model is
not loadable-and-served under v4.

## B6.3 — Gaussian registry: verify, then stamp

`models/gaussian_registry.json` entries are pointers (`version`, `model_file`, `feature_schema`,
`schema_version`, `metrics`, `trained_at`, `active`) — no positional vectors. F-060 established that
no `mu`/`sigma` reach the live score at all, and the live kernel reads three features **by name**
(`ema_fast`, `ema_slow`, `momentum_score`), all unchanged in v4. Verify no positional read exists,
then stamp `schema_version` on the entries. No behavior change expected.

## B6.4 — BitNet: guard already shipped, just prove it

`models/model.json` is **absent** from the repo and `use_bitnet: false` (F-004). The import-time
`assert CANONICAL_FEATURE_DIM == 38` was already demoted to a load-time
`model_contract.assert_canonical_dim()` (it was taking the whole spine down via
`crt_engine_v2 → bitnet_inference → model_contract`). Add a test that a canonical-v3 envelope raises
under v4 and that legacy 6-input models — which map by name (F-050 CH-002) — are unaffected.

## B6.5 — TradeNet: stamp only

Unwired (F-005), `.pth` absent, wire-up gated behind `TN_QUAL_V1`. Stamp `tradenet_registry.json`
with the schema it was built against.

## B6.6 — the 6 red tests

- `test_zone_gate_alignment.py::test_registry_feature_order_matches_live_schema_today` and
  `::test_live_registry_loads_and_exposes_feature_order` — repoint at the **v4** registry. These are
  currently red *because the safety net is working*; they go green once the artifact is remapped.
- `test_feature_pipeline.py::test_session_encoding` — rewrite against the 5-value window model
  (the hour→session table is already pinned in `tests/test_session_classifier.py`; assert the
  pipeline agrees with `session_classifier`, don't duplicate the table).
- `test_feature_pipeline.py::test_normalized_features_mean_std` and
  `::test_retest_flag_uses_recent_sweep_not_bos`, `test_candle_math.py::test_pipeline_vectorized_equals_scalar_primitive`
  — `wick_size` → `candle_range`, `macd_hist` → `macd_hist_z`. The candle_math parity assertion is
  unchanged in substance: the scalar `candle_math.candle_range` now matches a column of the same
  name instead of a misnamed one.

Remaining v3-name references (~49 files: fixtures, dead `crt_feature_builder`, msip/uat scaffolding)
are inert and sweep in B7.

---

## Critical files

`models/zone_registry_v4_2026_07.json` (new) · `models/zone_gate_registry.json` ·
`scripts/governance/remap_zone_registry_v4.py` (new) · `configs/production/v2_multi_2026_04.json` +
`v2_multi_dimfix_shadow_2026_07.json` · `active_models.yaml` · `models/rr_model*.json` ·
`models/gaussian_registry.json` · `models/tradenet_registry.json` ·
`tests/test_zone_gate_alignment.py` · `tests/test_feature_pipeline.py` · `tests/test_candle_math.py`
· `tests/test_schema_v4_artifact_reconciliation.py` (new)

## Verification

**1. The gate loads again, name-anchored:**

```bash
D:/Tradelatest/venv/Scripts/python.exe -m pytest tests/test_zone_gate_alignment.py tests/test_zone_manifest_runtime_parity.py tests/test_model_paths_resolver.py -q
```

**2. Feature + schema floors:**

```bash
D:/Tradelatest/venv/Scripts/python.exe -m pytest tests/test_feature_pipeline.py tests/test_candle_math.py tests/test_session_classifier.py tests/test_fm030_031_implementation_validation.py tests/test_schema_v4_artifact_reconciliation.py -q
```

**3. The ledger, and its attribution.** Run the gate-ON BNBUSDT spine and record the new v4 SHA:

```bash
D:/Tradelatest/venv/Scripts/python.exe scripts/research/dimensional_mix_shadow_diagnostic.py --instruments BNBUSDT
```

It **will** differ from `9bcba138775d4109` — that is expected (`PRODUCTION_BEHAVIOR_CHANGED = YES`),
and the freeze waiver's binding requirement is **attribution, not parity**. The delta must decompose
across the three sub-changes measured independently:

- **session re-encoding** — the only sub-change with a live decision path, and B6 zero-weights it
  out of ZoneGate, so its residual effect enters only through consumers that read the `session`
  feature directly (`trap_validator_engine`, the CRT session filter).
- **MACD split** — predicted **zero** ledger effect: `macd_hist_z` carries the identical values v3's
  `macd_hist` did, and `macd_hist_raw` is scored by nothing.
- **`candle_range` rename** — predicted **zero**: the dim is weight-0 in every zone and the rename
  is pure.

So the prediction is that essentially all of the delta is attributable to session. **An
unattributed delta means stop**, per the waiver.

**4. Not in scope, deliberately:** `baseline_capture --label schema_v4` and the freeze-pin
regeneration are B5/B7 — they should record the *settled* v4 state, so they run after the artifacts
are reconciled, not before.

**Known pre-existing reds, not caused by and not fixed here:** the Gate-6 construction floor is RED
on 6 geometry-census staleness failures (separate task), and three freeze-pinned sources had drifted
before this session (declared in the pin's `waiver_log`).
