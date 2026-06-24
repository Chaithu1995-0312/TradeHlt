# Gate Contribution Audit — BNBUSDT (Study 2)

> Point-in-time, 2026-06-03T06:54:45.228745+00:00. PURE MEASUREMENT — no production change. Instrument BNBUSDT on `v4_multi_2026_06` (the promoted config). Funnel from `logs/crt_transitions.jsonl` (231,888 transitions); per-stage counterfactual expectancy joined from BNBUSDT `opportunities.jsonl` (69,971 candles); EXECUTION = real executed trades (35, `results\run_20260603_122112_BNBUSDT\BNBUSDT_trades.csv`).

## Funnel — count, conversion, and expectancy after each gate

| Stage | Count | Conv% (from prev) | mean rr | PF | WR | Δ mean-rr (gate adds?) | outcome-N (join cov) | source |
|---|---|---|---|---|---|---|---|---|
| **SWEEP** | 186,399 | 100.0% | -0.028 | 0.83 | 44.5% | — | 186,093 (100%) | counterfactual (opportunities join) |
| **DISPLACEMENT** | 33,915 | 18.2% | +0.021 | 1.15 | 49.4% | +0.048 | 33,806 (100%) | counterfactual (opportunities join) |
| **EXPANSION** | 6,302 | 18.6% | -0.023 | 0.86 | 45.6% | -0.043 | 6,300 (100%) | counterfactual (opportunities join) |
| **RETEST** | 4,126 | 65.5% | -0.039 | 0.76 | 42.2% | -0.017 | 4,124 (100%) | counterfactual (opportunities join) |
| **EXECUTION** | 1,146 | 27.8% | +0.545 | 2.54 | 65.7% | +0.584 | 35 (100%) | real executed trades |

## Headline — the edge is the FINAL gate, not the pattern funnel

- **Every pre-execution stage leaves candidate expectancy at ~0 / negative** (SWEEP→RETEST mean rr ∈ [-0.039, +0.021]R). The geometric funnel (sweep→displacement→expansion→retest) cuts COUNT 186k→4k but **does not concentrate winners** — candidate quality stays flat-to-negative through RETEST.
- **The entire selection edge appears at RETEST→EXECUTION:** -0.039R → **+0.545R** (PF 0.76→2.54, WR 42%→66%). That gate = **session filter + score threshold + execution-planner SL/TP**.
- **Combined with Study 1** (features ≈ chance, AUC 0.515; accepted-trade AUC only 0.60): the edge is **neither in the features NOR in the pattern geometry** — it is in the **execution-selection process**. This is why the session-policy change (part of that final gate) moved BNB +4.91%→+20.59%, and it says the highest-leverage work is the EXECUTION gate (session/score/SL-TP selectivity), not new features, clusters, Probability Surface, ReplayMemory, or TradeNet.

## Verdict — per-gate

- **Edge-CREATING gate (largest +Δ expectancy):** **EXECUTION** (+0.584R) — dominates everything.
- **Mildly edge-positive pre-execution gate:** DISPLACEMENT (+0.048R, PF 0.83→1.15) — the only pattern stage that nudges candidate quality up.
- **Dead-weight / mildly edge-negative:** EXPANSION (-0.043R) and RETEST (-0.016R) — they shrink count without improving (slightly worsening) per-candidate expectancy.

## Critical caveat (do not over-read the final jump)

- The +0.58R EXECUTION jump **conflates two things that this method cannot separate**: (a) *which* retest candles are selected (session + score), and (b) the execution-planner's **structure-based SL/TP** (vs the counterfactual's vanilla fixed SL/TP). Both are part of the *execution process* (not features/geometry), so the headline holds — but to split selection-vs-SL/TP would need a counterfactual that replays the execution planner's SL/TP on the rejected retest candidates. **Recommended next experiment.**
- The geometric stages are not 'useless' — they reduce 186k→4k so the final gate is tractable; they just don't *create expectancy*.

## Caveats

- Counterfactual stages use the scanner's **vanilla SL/TP** outcome at the stage-entry candle — it measures *candidate-population quality* at each stage, not exact realized PnL. EXECUTION uses real trades.
- A candle's outcome is the mean over its long/short opportunity records (direction is not always carried on the transition). Join coverage <100% means some stage-entry candles had no opportunity record (different scan window) — see the coverage column; regenerate opportunities on the same CSV to raise it.
- One BNBUSDT run on v4; counts/period specific to `data/BNBUSDT_M15.csv`.
