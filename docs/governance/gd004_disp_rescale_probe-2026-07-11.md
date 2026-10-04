# GD-004 disp_strength rescale probe (identity-closure characterization)

_Generated 2026-07-11T05:53:33.407209+00:00 · symbol BNBUSDT · 29922 bars · read-only._

Site: `scoring_engine.py:31 disp_strength = move/atr; caller crt_engine.py:23 move=features['disp_strength']`

## ATR-unit verification
- pipeline `atr` == atr_14_raw/close on **100.0%** of 29909 checkable bars
- atr column: median 0.003591 · p95 0.008451

## As-wired quantity (FM-020 / atr_rel)
- distribution: median 110.37 · mean 160.35 · p95 488.09
- s_breakout saturation (x ≥ 2.0): **97.5%** of bars

## Identity adjudication
- equals FM-020: 2.08% · equals FM-028: 0.00%
- criterion: both rates ~0 ⇒ genuinely new quantity (register FM-029); either ~1 ⇒ STOP, adjudication wrong

> Characterization only — feeds the FM-029 ontology note and the GD-004 retirement fields. Backtests run gate-OFF (F-037) and run() never executes (F-048), so no production-loss claim.