# Parquet evidence layer — first run (2026-08-23)

> Point-in-time. Not a living spec (that is `docs/research/parquet_evidence_layer.md`).
> Not an F-id. Not G001. Artifact: `results/research/parquet_evidence_layer/report.json`.

**Lane:** measurement / evidence. **Change:** `CH-parquet-evidence-layer`.

## Grain (this is the load-bearing fact)

| Surface | n | Projection | Grain |
|---|---:|---|---|
| opportunities | 94,332 | FRESH | bar × direction |
| clean_labels | 94,332 | FRESH | bar × direction |
| events | 7,112 | FRESH | later CRT spine run |
| telemetry | 4,883 | FRESH | later CRT spine run |

94,332 = 47,166 timestamps × 2 sides. Join opportunities ↔ clean_labels: 94,332 / 94,332. Events/telemetry were **not** 1:1 joined onto that ledger.

This is a decision-lifecycle trace of two different objects. Treating all four files as one training table would invent a shared identity they do not have.

## Outcome surface (governing y = `y_tp1`, never stream `outcome`)

| Quantity | n | Value | Confidence |
|---|---:|---|---|
| unit TP hit (`y_tp1`) | 94,332 | 0.324 | CERTAIN (file count) |
| path reached 0.5R | 94,332 | 0.898 | CERTAIN |
| path reached 1R | 94,332 | 0.799 | CERTAIN |
| path reached 2R / stretch | 94,332 | 0.620 | CERTAIN |
| TP conversion given reached 1R | 75,383 | 0.405 | CERTAIN |
| high-MFE low-TP (reached ≥1R, missed unit TP) | 44,859 | 0.476 of ledger | CERTAIN |
| wins with MAE ≥ 0.8R | 16,334 / 30,525 | 0.535 of wins | CERTAIN |

Stream `outcome` on the same rows is 92,937 SL_HIT / 1,344 TP_HIT (F-022). The clean path is 62,190 SL_HIT / 30,525 TP_HIT. Using the ledger as a labelled dataset for XGBoost would train on the contaminated stream.

Path hit rates are **counterfactual on stored paths**, not t=0 policies.

## Feature / regime association (not skill)

Largest powered `y_tp1` spreads on already-emitted columns:

- hour-of-day cells: spread 0.079 (hour 8 ≈ 0.347, hour 18 ≈ 0.268) — LIKELY as a contrast, **not** an edge. Clock is F-066 broker-local.
- session spread 0.039; side 0.036 (long 0.342 / short 0.306); volatility_regime 0.028.
- trend_bias spread 0.001 — indistinguishable from the base rate.
- ontology flags (sweep / BOS / volume_spike / double_sweep): occurrence is real; Δ`y_tp1` present-absent is 0.001–0.013. Does not graduate a SEM node. Does not reverse F-086.

Median-split continuous features sit in the same 0.01 band. `momentum_score` / `ema_spread` remain F-061 contaminated.

## CRT spine journal (separate grain)

Events: RESET 2,887 · STATE_TRANSITION 2,382 · SWEEP 1,792 · TRADE_OPENED **3**.

Funnel: RANGE→SWEEP 1,792 · SWEEP→DISPLACEMENT 399 · DISPLACEMENT→EXPANSION 142 · EXPANSION→RETEST 24 · RETEST→EXECUTION 4.

Telemetry deaths (n=1,798 attributed): RESET_HTF 1,442 · RESET_RETRACE 166 · RESET_EXTENSION 109 · ACCEPTED 3.

This is a process to study. It is not the 94k outcome surface.

## Candidate findings (not registered)

1. Opportunity quality and trade outcome are different objects on this ledger: 47.6% of rows print ≥1R MFE and still miss the frozen 2R unit TP.
2. Feature/state vocabulary on this grain moves `y_tp1` by a few points at most. Information-scale association; no authority.
3. The CRT engine, on the later spine run, dies mostly at HTF reset before a trade exists. Throughput bottleneck is upstream of outcome.

No F-id. No production. `y_R_net` still uses protocol 12bps (F-082).
