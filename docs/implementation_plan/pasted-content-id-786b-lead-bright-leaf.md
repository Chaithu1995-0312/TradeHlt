# Set 2 consumer-scale fix: activate the existing unit switches on the active config

## Context
The pasted "Lead Architect" spec reports a real problem. On XAUUSD, `ema_spread`, `momentum_score` and `atr` are compared against dimensionless thresholds in the wrong units (F-061 / F-064 / F-109). As a result `detect_regime` returns `trend` on about 99.8% of bars, the breakout score is pinned at 1.0, `tanh(momentum_score)` saturates, and the live `_vol_score` is always 0.

Checking the spec against source showed that most of the work it describes already exists. This plan uses what is there rather than following the spec literally:
- **The spec's paths are wrong.** It names `src/engine/`, `src/kernels/` and `configs/active/`. The real locations are `src/core/engine_runner.py`, `src/core/gate_intelligence.py`, `src/engines/ema_momentum_kernel.py` and `configs/production/v2_htfcrt_2026_08.json` (ACTIVE_VERSION = `v2_htfcrt_2026_08`).
- **Decision 1 is one config key, not consumer rerouting.** `feature_pipeline.normalization_basis` = `atr_absolute` makes `src/features/feature_pipeline.py:1020-1029` emit FM-030/031 under the same column names. Every consumer then reads corrected values with no code change: `detect_regime`, `breakout_engine`, the kernel, `_derive_trade_intent` and REVERSAL. The catch is that the spec is wrong that FM-022/023 stay in slots 9 and 12: the switch **replaces** those values. Its claim that a Set 2 re-measurement would bit-match afterwards is therefore false for `ema_spread` and `momentum_score`. That change is expected and must be recorded, not treated as a revert trigger.
- **Decision 2 is one config key.** `gate_intelligence.gate_vol_atr_basis` = `absolute`; the code path already exists at `gate_intelligence.py:267-271`.
- **Decision 3** follows automatically from Decision 1.
- **Decision 5 is rejected.** `NORMALIZE_COLS` (`feature_pipeline.py:381`) was deliberately retired at schema v6.0 (F-107). Refilling it would bring back the in-place z-score defect. The kernel's `mu=0/sigma=1` problem is a registry calibration issue (F-060), which needs a separately authorized retrain.
- **"Sharpe > 1.0" is not a valid acceptance gate.** The active XAUUSD ledger produces only a handful of trades (F-110), and under §6.5 authority comes only from measured ΔG001. The backtest is reported as a diagnostic, not a pass/fail.

User decisions (2026-10-07): flip both switches **on the active config directly**, and include Decision 4 as a **config-gated arm**.

## Steps

0. **Preflight (CLAUDE.md §1.5).** `git status`; note the concurrent-session WIP and do not touch it. Confirm the interpreter is `venv`. Capture the green-floor baseline failure count with `check_governance_invariants.py --all` before any change.

1. **Baseline measurement (before the flip).** Add a SITS-registered, observe-only script `scripts/analysis/set2_consumer_scale_probe.py`. It runs the XAUUSD M15 corpus (`data/mt5/XAUUSD_M15.csv`; echo the path and row count) through `FeaturePipeline` plus the real consumers (`engine_runner.detect_regime`, `breakout_engine`, `GateIntelligence._vol_score`, the kernel score), once per `{normalization_basis} × {gate_vol_atr_basis}`, by building in-memory config variants. It reports:
   - regime distribution
   - breakout-score pinned fraction
   - non-zero rate of `_vol_score`
   - `|tanh(momentum_score)|>0.999` rate and the kernel score's standard deviation
   - median `|ema_spread|` and median `|momentum_score|`

   Output goes to `results/set2_consumer_scale/` (JSON). Reuse the existing fixtures in `tests/test_fm030_031_normalization_basis.py` / `test_fm030_031_implementation_validation.py`.

2. **Decision 4 config-gated arm.** In `engine_runner.detect_regime` (`src/core/engine_runner.py:178`), add strict keys under `engine_runner.dual_engine`:
   - `regime_trend_confirmation`: `"none"` | `"trend_strength_z"`; default `"none"`, which is byte-identical to today.
   - `regime_trend_strength_z_threshold`: 1.5.

   Read both with `_cfg_require` (no silent default, §6.5). Under `"trend_strength_z"`, `trend` additionally requires `|trend_strength_z| > thr` and `sign(trend_strength_z) == sign(ema_spread)`.

   The new keys must be added to **every** config that carries `dual_engine`, because they are strict reads. They sit outside `params`, so they are hash-neutral; confirm with `_compute_hash.py`. Add the arm to the step 1 probe as a third axis.

3. **Flip the active config** (`configs/production/v2_htfcrt_2026_08.json`): `feature_pipeline.normalization_basis` → `atr_absolute`, `gate_intelligence.gate_vol_atr_basis` → `absolute`. Update the `_comment_*` provenance strings. Set `regime_trend_confirmation` to `"none"` on the active config. Decision 4 remains a measured arm only, unless step 5 shows a reason to arm it and the user approves.
   - Run `_compute_hash.py`. Both keys are non-`params`, so the hash should be unchanged; verify.

4. **Freeze-pin re-certification.** `tests/test_feature_layer_freeze.py` pins the XAUUSD vector SHA under the legacy arm. Re-pin it under `atr_absolute` with the old SHA kept as a superseded comment, following the F-076 / F-107 re-certification pattern. Run the `test_fm030_031_*` tests, `test_feature_layer_freeze.py`, the gate_intelligence tests and the engine_runner tests. Some tests hardcode `legacy_relative` / `atr_relative` from the active config; inspect each failure. If a test encodes the active value, update it with a note; if it encodes a legacy-arm invariant, pin it to an explicit legacy config instead.

5. **After-measurement + backtest A/B (diagnostic).**
   - Re-run the probe on the flipped config.
   - Run `python src/runtime/backtest_v2.py --csv data/mt5/XAUUSD_M15.csv --output results/set2_scalefix_after` against the pre-flip baseline run, using the measured broker cost model (SEM-015/016), not a 12bps cost.
   - Report a before/after table: trades, net R, win rate, max drawdown, regime and vol distributions. Make no economic claim at this n.
   - Run the 600-row prefix rerun for causality, using the existing PIT/prefix tests.

6. **Doc / findings synchronization (§6.2, same turn).**
   - New finding F-114 (ARCH) in `docs/current-findings.md` and the CLAUDE.md Truths Index: the active config is now on the corrected basis, with the measured distributions; this refines F-061 / F-064 / F-109.
   - Update the F-064 row text ("stays atr_relative by explicit decision" → superseded 2026-10-07).
   - Update `docs/reference/config-reference.md` and the matching `docs/topics/` entry.
   - Run the citation sync for any shifted `engine_runner.py` lines.
   - Add the SESSION LOG entry to `assistant_project.md`.
   - Note that the live paper rail sizing/approval behavior changes: `_vol_score` becomes non-zero, which raises the F-113 ceiling.

7. **Gate.** Run `check_governance_invariants.py --all` (compare against the step 0 baseline) and `construction_protocol.py check`. Commit only my own paths, with an explicit file list (concurrent sessions).

## Explicitly not done
- Decision 5 (`NORMALIZE_COLS`): rejected, see F-107.
- Kernel `mu/sigma` retrain: F-060, separate authorization.
- Set 3 opening: after this lands, per the user.

## Verification
The probe JSON shows, on XAUUSD:
- regime `trend` share falls well below 99.8%
- `_vol_score` is non-zero on a meaningful fraction of bars
- the `tanh` saturation rate drops sharply
- median `|ema_spread|` / `|momentum_score|` are O(1)

The spec's 15–30% range band, 20–40% vol band and std > 0.05 are reported against, not enforced. Also required:
- freeze test re-pinned and green
- prefix-causality tests green
- green floor no worse than the step 0 baseline
- backtest A/B table produced
