# XAUUSD bar-features chart

Source of the published page <https://claude.ai/artifact/Vjb2nDRmoebsxfswGwen7W>: a multi-timeframe
XAUUSD chart (M5…D1) with the canonical features per bar, D1_AMD state shading, SMC zone boxes
(order block / FVG / breaker / mitigation / rejection, with checkboxes), oracle trades, the
profitable-zone study, the 2-year forward test and a "right now" read of the latest bar.

Observation tooling only — no production authority, no economic claim.

## Rebuild (run from the repo root, `venv` interpreter)

MT5 must be running (the 10-day window is fetched live). Steps, in order:

| # | Script | Writes |
|---|---|---|
| 1 | `xau_10d_features.py` | `xau_10d_features.json` — last ~10 days of M15 from MT5, features, AMD states, SMC zone prices, oracle trades |
| 2 | `zone_full.py` | `zone_full.json` — profitable-zone study on the 2-year file `data/mt5/XAUUSD_M15.csv` |
| 3 | `zone_10d.py` | adds `zones10` / `zones_full` to the JSON |
| 4 | `zone_edge.py` | `zone_edge.json` + cache `zone_full_enriched.parquet` — 2-year forward decile test |
| 5 | `attach_now.py` | adds `zone_edge` and `now` to the JSON |
| 6 | `render_xau.py` | `xau_bar_features.html` — the template with the data filled in |

`build.py` runs all six in order. Then publish `xau_bar_features.html` (same artifact URL).

## Files

- `xau_template.html` — the page (lightweight-charts 4.2.3, canvas overlays for AMD bands and zone
  boxes, green/red candles). Data placeholder: `__DATA__`.
- `smc_zone_prices.py` — zone prices from the repo's own SMC finders (`features/smc/*`); rejection
  block is defined here (not in the repo): wick of a confirmed swing until retested or closed through.
- `amd_state.py` — D1_AMD state classifier (option C2) used for the shading.
- `zone_study.py` — profitable-zone labels (2×ATR target before 1×ATR stop within 16 bars, runs ≥3)
  and the AUC event study.

Generated files (`*.json`, `*.parquet`, `xau_bar_features.html`) are git-ignored.
