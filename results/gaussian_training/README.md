# Gaussian training run (EXPERIMENTAL, operator-approved sample-count override)

Command:
`python src/runtime/backtest_v2.py --csv data/XAUUSD_M15.csv --instrument XAUUSD --output results/gaussian_training/backtest`
`python scripts/training/gaussian_from_backtest.py --trades <run>/XAUUSD_trades.csv --csv data/XAUUSD_M15.csv --version xau_m15_causal_n9_20261011 --min-samples 5 --register --promote`

- Dataset: 9 production-config M15 trades on XAUUSD (the only available corpus), features = entry-bar snapshot from the batch FeaturePipeline (causal_v2 swings, causal volatility_regime A). OHLCV sha256 4d73f5ce..., trades sha256 78cdecb....
- Split: temporal 70/30. Train 6 (2024-08-02..2025-07-14; loss 4, small win 2). Validation 3 (2025-11-19..2026-01-27; small win 3). Classes 2 and 3 absent.
- Metrics (trainer.train_gaussian): corr_expected_rr 0.0, calibration_error 0.0. **Degenerate**: validation R values fall in one class and n=3, so these numbers carry no evidence.
- Previous active `v1` (corr 0.20, cal 0.08) was a registry entry with no model file; promoted over it with force=True. Old state: `models/gaussian_registry.pre_xau_m15_causal_n9_20261011.json`. The 12 `gaussian_p5_*` files are unchanged and unregistered.
- Artifact: `models/gaussian_xau_m15_causal_n9_20261011.json` (35 ordered features, schema checksum f9b806ea..., feature-definition hash 60b81319...; bundle also holds `feature_definition` and `provenance`).
- Not claimed: live inference works. Known live blockers remain (see ../training_live_parity/REPORT.md): missing `build_feature_vector`, no `trade_data` producer, wick_size/body_ratio/double_sweep divergence.
- Rollback: restore the `.pre_` registry file over `models/gaussian_registry.json`.
