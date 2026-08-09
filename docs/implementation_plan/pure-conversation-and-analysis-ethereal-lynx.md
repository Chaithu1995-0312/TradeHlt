# Train ZoneGate, RR, TradeNet, BitNet, Envelope on the Frozen XAUUSD Corpus (Research-Only)

## Context

The user wants all trainable models exercised on the frozen/preferred XAUUSD data file
(`data/mt5/XAUUSD_M15.csv`, SHA-256 `4d73f5ce…`, range 2024-05-22→2026-05-21, 47,275 rows,
status `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` per
[`docs/governance/CORPUS_AUTHORITY.md`](docs/governance/CORPUS_AUTHORITY.md)). Gaussian is
already done — trained twice, registered, and economically **closed/REJECTED** under the M4
gate ([xauusd-gaussian-toward-economics-2026-07-23.md](docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md)) —
so it is **not** re-run here. The remaining five families (ZoneGate, RR, TradeNet, BitNet,
Envelope) have never been trained on XAUUSD at all. The user confirmed this stays
**research-only**: train + register, never flip any production config, consistent with the
corpus's FROZEN (not APPROVED) status and the §6.5 Authority Ladder (information ≠ authority).

Four research passes (Explore agents) mapped every trainer's actual invocation, its upstream
data dependency, and surfaced concrete blockers that must be fixed *before* training will even
run correctly — this plan sequences fixes first, then training, in dependency order.

## Blockers found that must be fixed first (Phase 0 — small, additive, mechanical)

1. **Frozen-candidate guard is missing at 3 CSV-load sites this work will exercise.** The
   existing idiom (`if instrument == "XAUUSD": csv_path = guard_xauusd_csv_path(csv_path, "XAUUSD")`,
   e.g. [`scripts/research/build_zone_census.py:38-40`](scripts/research/build_zone_census.py),
   [`scripts/research/qualify_xauusd.py:65-67`](scripts/research/qualify_xauusd.py)) is **not**
   present in:
   - [`scripts/research/opportunity_scanner.py`](scripts/research/opportunity_scanner.py) `_load_csv` (~line 42-50)
   - [`scripts/training/train_bitnet.py`](scripts/training/train_bitnet.py) `build_dataset()` (~line 87-93)
   - [`scripts/research/build_clean_labels_tn_env.py`](scripts/research/build_clean_labels_tn_env.py) candle load (~line 87)

   Without the guard, a typo or a stale default could silently read `data/XAUUSD_M15.csv`
   (the unresolved, out-of-scope extended-root file, hash `486cf361…`) instead of the frozen
   candidate — both files exist side by side on disk today. Add the guard call at each site,
   mirroring the existing idiom exactly (no new abstraction).

2. **Envelope trainer has a real, pre-existing 38-vs-39 feature-dim bug**, independent of
   XAUUSD. `src/features/feature_schema.py` migrated to `CANONICAL_FEATURE_DIM = 39` on
   2026-07-22 (schema hash `c87a1aba…`), but
   [`src/research/envelope_offline/train.py:138`](src/research/envelope_offline/train.py:138)
   still hard-filters `len(vec) != 38`, and
   [`src/research/clean_labels/protocol.py:35`](src/research/clean_labels/protocol.py:35) still
   declares `FEATURE_DIM = 38`. The existing BNBUSDT clean-labels dataset (built 2026-07-21,
   pre-migration) genuinely has 38-dim rows — so **do not** hardcode the new 39 in its place
   (that would silently break loading of the existing BNBUSDT artifact). Fix: make
   `load_l2_matrix` validate that all rows in a given dataset share the **same** length
   (self-consistency), derived from the dataset's own `dataset_meta.json`/first row, rather than
   comparing against any hardcoded literal. This lets BNBUSDT (38-dim) and a fresh XAUUSD build
   (39-dim) each load correctly without cross-breaking the other.

3. **`train_envelope_offline.py` hardcodes `"BNBUSDT"`** in the doc-summary overwrite path
   (~lines 91, 93 — `docs/analysis/envelope-offline-train-BNBUSDT.LATEST.md/.json`). Running it
   for XAUUSD today would silently clobber BNBUSDT's docs summary. Parametrize by
   `args.instrument`.

**Parity requirement:** all three fixes must leave existing BNBUSDT/ETHUSDT/EURUSD runs
byte-identical (guard is a no-op pass-through for non-XAUUSD-M15 paths; dim-check becomes
self-consistency, which the existing 38-dim BNBUSDT dataset already satisfies; doc-path fix only
changes behavior when `--instrument` ≠ BNBUSDT).

**Explicitly out of scope for this plan** (flagged, not fixed here — separate concerns):
`src/governance/portfolio_validation.py` reads `data/XAUUSD_M15.csv` directly with no guard at
all (a live bypass, but unrelated to training); `models/gaussian_registry.json`'s
`__active__.XAUUSD` pointer contradicts its own "not promoted" note (pre-existing, inert per
F-060). Worth a separate follow-up, not bundled into this training pass.

## Phase 1 — Generate the shared `opportunities.jsonl` stream for XAUUSD

Prerequisite for ZoneGate and TradeNet. `opportunity_scanner.py` is CRT-independent (pure
ATR-based forward-simulation), so this is a clean detection pass, not a spine run.

```bash
python scripts/research/opportunity_scanner.py \
  --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD \
  --run-id xauusd_phase1_<date> --output-dir logs \
  --tp-atr-mult 2.0 --sl-atr-mult 1.0 --max-forward-candles 40 --warmup-candles 30 --trail-mult 0.5
```

Writes `logs/XAUUSD/xauusd_phase1_<date>/opportunities.jsonl` (+ `run_header`).

## Phase 2 — ZoneGate

```bash
python scripts/research/discover_zones.py \
  --instrument XAUUSD --run-id xauusd_phase1_<date> \
  --n-clusters 8 --min-samples 15 --no-promote
```

`--no-promote` keeps this a research registry entry only (writes
`models/XAUUSD/<run_id>/zone_registry_XAUUSD_<version>.json`, registers in
`zone_gate_registry.json`) — the active production `zone_registry_v4_2026_07.json` (BNB/ETH
trained) is untouched.

## Phase 3 — TradeNet

```bash
python scripts/training/train_trade_net_v2.py --instrument XAUUSD
```

Globs `logs/XAUUSD/**/opportunities*.jsonl` from Phase 1. **Verify label source before trusting
results**: check whether `train_trade_net_v2.py` reads raw `opportunities.jsonl` `outcome`/`rr`
fields (same F-022 risk as RR) or something more honest — if raw, treat its metrics as
information-only, not economic evidence, same posture as the RR fix below.

## Phase 4 — Clean-label dataset (shared by RR + Envelope)

`train_rr_model.py`'s default dataset builder (`build_rr_dataset.py` →
`rr_dataset_builder.py:extract_target`) reads raw `opportunities.jsonl` `outcome`/`rr_achieved`
fields — the exact F-022-contaminated stream (only ~36.8% self-consistent, per
`docs/current-findings.md` F-022/F-045/F-059). Do **not** repeat that mistake for XAUUSD's first
RR pass. Use the clean-label pipeline instead (`forward_walk(intrabar_fixed)`-derived, per
`src/research/clean_labels/builder.py`'s own governing-path doctrine):

```bash
python scripts/research/build_clean_labels_tn_env.py \
  --opportunities logs/XAUUSD/xauusd_phase1_<date>/opportunities.jsonl \
  --candles data/mt5/XAUUSD_M15.csv --instrument XAUUSD
```

Writes `results/clean_labels/XAUUSD/<run_id>/{clean_labels.jsonl, dataset_meta.json,
label_rederive_report.json, freeze.json}` + `results/clean_labels/XAUUSD/LATEST/pointer.json`.

## Phase 5 — RR (on clean labels, not the contaminated builder)

`train_rr_model.py` expects `rr_dataset.json`'s `X`/`y_rr`/`y_win`/`feature_names`/`schema_hash`
shape (`rr_dataset_builder.py:329-348`), which is a different shape from the clean-labels JSONL
rows. Write a small adapter (new, additive — reshape only, no new label logic) that reads
Phase 4's `clean_labels.jsonl` and emits `models/XAUUSD/<run_id>/rr_dataset.json` in the expected
schema, using its already-honest `y_rr`/direction fields. Then:

```bash
python scripts/training/train_rr_model.py --instrument XAUUSD --run-id xauusd_phase1_<date>
```

No `--promote` — research registry entry only.

## Phase 6 — Envelope

Unblocked once Phase 0 item 2 (dim self-consistency fix) and Phase 4 (clean labels) land:

```bash
python scripts/research/train_envelope_offline.py --instrument XAUUSD
```

Writes `results/envelope_offline/XAUUSD/<run_ts>/envelope_bundle.json` +
`results/envelope_offline/XAUUSD/LATEST/pointer.json`.

## Phase 7 — BitNet

No `opportunities.jsonl` dependency — trains directly off the CSV via `FeaturePipeline`.

```bash
python scripts/training/train_bitnet.py --csv data/mt5/XAUUSD_M15.csv --version xauusd_v1
```

Produces a standalone XAUUSD research checkpoint. `bitnet_registry.json` has no per-instrument
selection structure today (catalog is global: `legacy_6_root_model_json` /
`export_v5_35_results`) — do not invent new instrument-scoping for it; store this as a labeled
research artifact without touching the existing catalog's `composition_default`/selection
(`use_bitnet` stays `false` either way).

## Phase 8 — Verify research-only status

For each of the five: confirm the registry write path did not set any `active`/promoted pointer
that a live config reads, and that no file under `configs/production/` changed. Add/extend a
focused test per model mirroring the existing pattern (e.g.
`tests/test_gaussian_registry_retry_cache.py`-style) confirming the new XAUUSD entries load and
report `research_only`/`active:false` where applicable. Re-run the existing BNBUSDT/ETHUSDT
regression tests for each touched trainer to confirm the Phase 0 fixes are byte-identical for
those instruments.

## Explicitly out of scope (follow-up, not this pass)

- **Economics (E0→E1→E2 M4 QualificationGate)** for ZoneGate/RR/TradeNet/BitNet/Envelope,
  mirroring what Gaussian already went through. That's a substantial per-model pre-registration
  effort (arms, kill criteria, cost model) — a natural next task once training artifacts exist,
  not part of "train the models."
- Fixing `portfolio_validation.py`'s unguarded XAUUSD path, and the stale `gaussian_registry`
  active-pointer inconsistency — separate, unrelated governance items surfaced along the way.

## Critical files

- `src/data_ingestion/xauusd_phase1_candidate.py` (guard to wire in 3 more places)
- `scripts/research/opportunity_scanner.py`, `scripts/research/discover_zones.py`
- `scripts/training/train_trade_net_v2.py`, `scripts/training/train_rr_model.py`,
  `scripts/data/build_rr_dataset.py` (do not use its default path for XAUUSD), `src/config_layer/rr/rr_dataset_builder.py`
- `scripts/research/build_clean_labels_tn_env.py`, `src/research/clean_labels/builder.py`,
  `src/research/clean_labels/protocol.py`
- `scripts/research/train_envelope_offline.py`, `src/research/envelope_offline/train.py`
- `scripts/training/train_bitnet.py`

## Verification

- Run the existing test suites touched: `tests/test_xauusd_phase1_frozen_candidate.py`,
  any RR/zone-gate/envelope/bitnet unit tests, plus new focused tests per Phase 8.
- For each trained artifact, confirm via its manifest/registry entry that `authority`/`active`
  states stay research-only (no production wire), matching the Gaussian precedent's own
  manifests (`"NOT promoted"`, `economic_authority: false`).
- Confirm `configs/production/*.json` and `configs/production/ACTIVE_VERSION` are untouched by
  a diff at the end of the work.
