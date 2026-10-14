# Feature audit: trunk vs divergence branches (XAUUSD H4)

Source of the published report <https://claude.ai/artifact/AZnzfViBRctbrFARiCdBrt> ("Divergence Branches").

For every canonical feature it checks two things:

- **Trunk**: the feature pipeline's value against an independent recompute of the feature's
  *registered* formula (`configs/formulas/market_ontology.yaml`), on every H4 bar. The recompute is
  plain loops in `audit_primitives.py` and the group scripts; it does not import `features.*` or
  `structure.*`, so it can disagree with them.
- **Branches**: alternative definitions (textbook / TradingView), implementation details (for
  example float32 storage) and data caveats. A branch is **open** only when it changes something a
  decision reads on at least one bar (a zone, flag, regime, sign or threshold class); otherwise it is
  **closed** with its numbers shown. Decisions are recorded on the published page (its `db` store,
  collection `branches`), never in code.

Observation tooling only: no production authority, no economic claim (CLAUDE.md §6.5).

## Data

`data/mt5/XAUUSD_H4.csv`, with timestamps converted to UTC in memory through the file's declared
clock (`mt5_icmarkets_xau`, see `configs/data_provenance/ohlcv_clock_registry.json`) by
`h4_loader.py`. Nothing is written to `data/`. The loader also tags the frame
(`df.attrs["instrument"] = "XAUUSD"`, as `corpus_store.frame()` does); without that tag
`FeaturePipeline` silently uses the UTC day instead of the 17:00 New York trading day. The active config is read from
`configs/production/ACTIVE_VERSION`. The pipeline's windows are bar counts tuned on M15, so on H4
they span about four times as long.

## Rebuild (repo root, `venv` interpreter)

Run in this order; each data step adds its group to `results/divergence_h4.json`:

| # | Script | Group |
|---|---|---|
| 1 | `divergence_data.py` | trend, volatility, momentum, volume (rewrites the JSON) |
| 2 | `session_data.py` | session / time |
| 3 | `structure_data.py` | sweeps / structure |
| 4 | `disp_data.py` | displacement / retest |
| 5 | `liquidity_data.py` | liquidity |
| 6 | `smc_data.py` | SMC zones (about a minute; runs the pipeline twice for the calendar branch) |
| 7 | `rejection_data.py` | rejection blocks |
| 8 | `ohlcv_data.py` | raw OHLCV (identity trunk + file checks: candle validity, H4 vs M15 buckets, short 00:00 bar) |
| 8b | `candle_images_data.py` | Candle Images workflow: study-card pattern rules vs FM-107..114/120, last month of H4 |
| 9 | `render_divergence.py` | writes `results/branch_mockup_rsi.html` (uses `divergence.css` / `divergence.js`) |

```
venv\Scripts\python.exe tools\feature_audit\divergence_data.py
venv\Scripts\python.exe tools\feature_audit\session_data.py
venv\Scripts\python.exe tools\feature_audit\structure_data.py
venv\Scripts\python.exe tools\feature_audit\disp_data.py
venv\Scripts\python.exe tools\feature_audit\liquidity_data.py
venv\Scripts\python.exe tools\feature_audit\smc_data.py
venv\Scripts\python.exe tools\feature_audit\rejection_data.py
venv\Scripts\python.exe tools\feature_audit\ohlcv_data.py
venv\Scripts\python.exe tools\feature_audit\candle_images_data.py
venv\Scripts\python.exe tools\feature_audit\render_divergence.py
```

Then publish `results/branch_mockup_rsi.html` to the same artifact URL (the file name is kept so the
page and its recorded decisions keep their link). Charts are inline SVG generated from the computed
numbers, not images.

## Files

- `h4_loader.py`: H4 load + UTC conversion through the declared clock (read-only).
- `audit_primitives.py`: independent EMA, SMA, true range, pivots, causal publication, MKT-E01 level book.
- `*_data.py`: one script per feature group (trunk check + branch measurements).
- `render_divergence.py`, `divergence.css`, `divergence.js`: the page; the script only saves and
  loads decisions.

Generated files (`results/*.json`, `results/*.html`) are not part of this folder.
