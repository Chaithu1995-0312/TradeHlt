# OHLCV load-path coverage assessment (report-only)

**User decision: report only, NO CODE.** This file is the deliverable, not an implementation plan.
It refreshes the validation-coverage matrix after the B1–B5 loader work and names what is still
pending. No source changes proposed.

## What changed since the last table

- **B1** moved header resolution to `ohlcv_schema.resolve_ohlcv_column_indices` (SSOT) — L1 is now
  one authority for every `CandleLoader.stream()` consumer; `tick_volume` resolves.
- **B4** added source/line context to numeric coercion (still L2-inline value).
- **B5** added mid-file-blank detection (new L2-inline sequence check).
- All three live *inside* `stream()`, so every Path-A consumer inherits them at once.

## The matrix is really TWO paths, not one

**Path A — `CandleLoader.stream()`** (row-streaming): backtest CLI, `config_validator`,
`portfolio_validation`, `exit_model_band`, `unified_replay_harness`, `sl_tp_comparator`, and the
research adapters (`spine_signal_source`, `structural_event_source`, `cross_sectional`,
`forensics`, `runner`).

| Path-A consumer | Pin | L1 presence | L2 value (+B4) | L2 sequence (+B5) | L3 preflight |
|---|---|---|---|---|---|
| backtest_v2 CLI | ✅ | ✅ | ✅ | ✅ | ✅ |
| research adapters | ✅ | ✅ | ✅ | ✅ | ❌ |
| validator/portfolio/exit_model/replay/sl_tp | ✅ | ✅ | ✅ | ✅ | ❌ |

**Path B — raw `pd.read_csv` → `FeaturePipeline`** (bypasses the loader): `zone_mapping/*`,
`ic002_entry_evolution/build_trajectories`, `secondlow_v1/detector`. Validation is
`FeaturePipeline._validate_input` only = `require_ohlcv_columns` + `pd.to_numeric` +
`validate_ohlcv_frame`.

| Path-B consumer | Pin | L1 presence | L2 value | L2 sequence | L3 preflight |
|---|---|---|---|---|---|
| `collect_trade_opened_features` | ✅ (guards) | ✅ | ✅ (NaN-coerce) | ❌ | ❌ |
| other zone_mapping / ic002 / secondlow | ❌ | ✅ | ✅ (NaN-coerce) | ❌ | ❌ |

(Within `backtest_v2` itself both paths run on the same file — the candle stream sequence-checks
what the feature DataFrame does not, so they cover each other. Standalone Path-B scripts have no
such cover.)

## Pending — ranked by materiality

1. **Path-B sequence + pin gap (MORE material).** Standalone raw-`read_csv` research scripts get
   **no duplicate / out-of-order / blank check** and **no corpus pin** (except one). A gappy,
   duplicated, or out-of-order file would flow into features silently. This is a genuine hole, not
   just a confidence gap — the inline backstop that protects Path A is simply absent here.
2. **L3-preflight gap on non-backtest Path-A consumers (F-039, LOWER).** Confidence only: per
   F-039's scope guard the inline L1/L2 backstop already enforces schema + chronology, so missing
   modal-timeframe / future-ts / gap-threshold analysis does **not** invalidate their results — it
   removes one net, not the net.

## Closed / not pending

- Header-alias drift (former B1 triplication) — **closed**, single authority.
- L2-inline value + sequence on Path A — **complete**, and now stronger (B4/B5).
- Corpus pin on all Path-A consumers — **present** (fires in `CandleLoader.__init__`).

## If remediation is ever wanted (not now)

- Path-B gap → a shared `load_validated_ohlcv_frame()` helper that runs the pin + full L1/L2
  (including sequence) before handing a DataFrame to `FeaturePipeline`; route the bypass scripts
  through it. Behaviour-changing (a tolerated-today gappy file would raise).
- L3 gap → call `dataset_integrity.validate_dataset` in the non-backtest Path-A entry points.
  Lowest value, widest surface; flips gappy files from WARN-and-run to REJECT.

Both deferred by the report-only decision.
