# Consensus-Gate Sensitivity Sweep — NULL RESULT (MEASURE-ONLY)

> Date: 2026-06-09 · Code: `scripts/analysis/consensus_sweep.py` · Artifact:
> `results/consensus_sweep/bnbusdt_*.json`. 3×5 grid over the fusion consensus gate.
> **No config change / no promotion.** Prod = `v2_multi_2026_04`.

## Question

Vary the two fusion consensus-gate parameters before tuning, to measure their effect on
trade count and PF:

- `min_consensus_signals` ∈ {1, 2 (baseline), 3}
- `min_consensus_agreement` ∈ {0.50, 0.55, 0.60 (baseline), 0.65, 0.70}

## Result — all 15 combinations bit-identical

| metric | every run |
|---|---|
| approved_trades | 18 |
| profit_factor | 1.1803 |
| avg_rr_net | −0.0367 |
| max_drawdown_pct | 4.88% |

The fail-fast assertion (verifying `FusionConfig.min_consensus_signals`/`_agreement` actually
received the swept values) **passed** on every run — so the parameters reached `FusionConfig`.
They simply have **zero influence on any trade decision**.

## Root cause — the consensus gate is a dormant pathway

`min_consensus_signals` / `min_consensus_agreement` are consumed **only** by
`FusionEngine.fuse_strategy_results()` (`src/core/fusion_engine.py:683`). That method is called
exclusively by the dormant strategy-consensus layer (`src/strategies/` S01–S10), whose fused
contribution is weighted by `weight_strategy_consensus = 0.0` in production. It is **never**
called on the live decision path.

The live approval gate is `FusionEngine._decide()` (`src/core/fusion_engine.py:670`), driven by
the score-tier thresholds `tier_full` / `tier_half` / `tier_quarter` — not by consensus
signals/agreement. `score < tier_quarter → REJECT`; the tiers also set risk sizing (1.0× /
0.5× / 0.25×).

Wiring note: a latent bug was fixed in passing — `engine_runner.py` previously constructed
`FusionConfig` **without** passing these two keys (they silently fell back to dataclass
defaults). `src/core/engine_runner.py:389–390` now reads them from the `fusion_engine` config
section. This is correct for when the strategy-consensus layer is eventually activated, but
has no effect on current production (`weight_strategy_consensus = 0.0`).

## Interpretation — null ≠ "optimal"

The correct conclusion is **"changing these parameters currently has zero observable effect,"**
not "the current settings are optimal." Under the current architecture the consensus gate is
not where the edge or the bottleneck resides.

This is consistent with the Phase 6b funnel diagnosis
([[project_phase6b_funnel_diagnosis]]): the BNBUSDT frequency bottleneck is `RETEST→EXECUTION`,
killed by the **SESSION filter** (44 OFF_SESSION + 20 ASIA rejects), with the score gate
non-binding (134/135 valid retests pass). The session filter — not any fusion-internal gate —
is the #1 live throughput lever.

## Redirect

Sensitivity effort moved to the session filter via the canonical `scripts/analysis/session_sweep.py`.
(That tool — and `detection_sweep.py` — were found broken on this branch because they consumed
an unimplemented `BacktestMetrics` ROI/PF layer; that layer was implemented TDD-style against
`tests/test_roi_metrics.py` + `tests/test_roi_gaps.py` Step 1, restoring both tools. The
session-sweep V0 hard gate then reproduced the published baseline exactly: 15 trades / PF 1.79 /
+4.91%.)

**Artifacts:** `results/consensus_sweep/bnbusdt_20260609T175338Z.json` (15 rows).
