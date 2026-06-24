# Backtest Trust Layer

## Context

**Why:** Research doctrine for this repo is `replay correctness > explainability > telemetry > advisory-AI > profit`. Before any further sweeps, OOS runs, or M4 qualification are trusted, the *measuring instrument* (the backtest accounting + metric layer) must be proven correct. An error near the top of the pipeline (prices → trade accounting → PnL → metrics) corrupts everything beneath it: optimizing a wrong PF is optimizing a bug, not an edge.

**Goal:** Establish a Backtest Trust Layer that (1) audits every trade-accounting and metric calculation, (2) fixes confirmed P0 correctness defects, and (3) institutionalizes the result with an independent recompute oracle + a byte-identical replay gate, so the numbers are reconciled before optimization resumes.

**Decisions taken (this session):**
- Deliverable = **Audit + fix confirmed P0 + institutional gate**.
- Intrabar close-only exit = **measure the realism gap, keep close-only as the default baseline**; promote any default change to a separate, evidence-gated decision (do not silently re-price all history).

## Confirmed findings (file:line evidence)

| # | Severity | Finding | Evidence |
|---|----------|---------|----------|
| F1 | P0 (leakage) | `center=True` swing detection: a swing flagged at bar *t-1* needs bars up to *t+SWING-1*, so the `.shift(1)` reference at decision bar *t* can absorb future-bar price info. Documented "backtest-valid, LIVE-UNSAFE" but **magnitude unquantified**. | `src/features/feature_pipeline.py:341-342`, consumers at `:359-360`, `:592-593` |
| F2 | P0 (realism) | Intrabar exit is **close-only**: a wick through SL/TP inside a bar never fills; exit triggers only when `candle.close` crosses the level. Understates stop-outs; distorts WR/RR/DD/PF/ROI. | `src/config_layer/crt_engine_v2.py:1962-1964` (called with `candle.close` from `backtest_v2.py:2178`) |
| F3 | P1 (RNG hygiene) | `on_trade_opened` calls `compute_fill_prices(...)` and **discards** all four results (`_, _, _, _ =`), then re-draws `entry_slip` again — burning RNG draws on a thrown-away computation; used entry/exit slips are not the paired pair. Deterministic (seed=42) but defective. | `src/runtime/backtest_v2.py:750-756`, `:385-396` |
| F4 | P1 (drift) | Divergent metric formulas across 4 modules: **PF ×3**, **expectancy ×4**, **max-DD ×3**, **win-rate ×2** — different units (R vs currency) and sentinels. Need to prove only the canonical `backtest_v2` path feeds `ConfigValidator`/promotion; quarantine/reconcile the rest. | `runtime/backtest_v2.py` (canonical) vs `analytics/performance.py:33-77`, `analytics/sl_tp_comparator.py:217`, `research/measurement/metrics.py:61-106` |
| F5 | P1 (consistency) | `score_std_dev` computed two ways: full std (`promotion_manager.py:382`) vs half-std penalty (`config_validator.py:197`). | as cited |
| — | OK | `slippage_seed: 42` (non-zero) → replay determinism preserved where threaded. Research harness uses sorted iteration + `sort_keys=True`. | `configs/production/v1_multi_2026_03.json:369`; `src/research/runner.py:102,124` |

## Workstreams

### WS1 — Trade-accounting & metric audit (read-only, produces findings doc)
Write `docs/analysis/backtest-trust-audit-2026-06-10.md` (point-in-time analysis, per `docs/analysis/` convention). For each of: entry/exit price, spread, slippage, commission (note: **none modelled** — flag), position sizing, planned RR, realized RR, per-trade PnL, aggregate PnL — record the authoritative `file:line`, the formula as written, units (R / pips / currency / %), and a verdict (correct / suspect / defect). Resolve F4/F5 by tracing which formula each *decision path* (`ConfigValidator.validate` → fitness gate; `PromotionManager`) actually consumes.

### WS2 — Fix confirmed P0/P1 defects (surgical, additive)
- **F3 (RNG hygiene):** in `runtime/backtest_v2.py:750`, remove the discarded `compute_fill_prices` call and source entry fill from a single paired draw (or call `compute_fill_prices` once and *use* its outputs). Preserve seed=42 determinism; regenerate the baseline ledger and document the (expected small) delta.
- **F4/F5 (formula unification):** make `backtest_v2` MetricsEngine the single source; have `analytics/*` and `research/measurement/metrics.py` either import the canonical helpers or be explicitly quarantined as non-decision analytics (docstring + assertion they never feed promotion). No magic-number formulas duplicated.
- **F1/F2 are NOT silently changed** — handled measure-only in WS4.

### WS3 — Independent recompute oracle + replay gate (the institutional layer)
- New `src/analytics/metrics_oracle.py`: **pure** functions that recompute PF, expectancy, win-rate, max-DD (R and %), total-return, CAGR, MAR **from the trade ledger alone** (`list[TradeRecord]` / `trades.csv`), independent of `MetricsEngine`. Config-driven constants via `get_prod_section`; no re-derivation of formulas inline.
- New `tests/analytics/test_metrics_oracle_parity.py`: run a backtest, then assert oracle output == reported `BacktestMetrics` within tight tolerance. Any divergence = a trust-layer failure.
- New `tests/runtime/test_replay_determinism.py`: run the same CSV+seed+config twice; assert byte-identical trade ledger + summary (formalizes `docs/architecture/replay-governance.md` §6 as an executable gate).

### WS4 — Exit-model realism measurement (measure-only, no default change)
Add a flagged intrabar high/low-touch detection path alongside close-only (config toggle, default = close-only). Run both on the standard universe; emit a comparison (`WR/RR/DD/PF/total-return` delta) into the audit doc. Same approach to **quantify F1**: run a causal (trailing) swing detector vs `center=True` and report the edge inflation. Output is evidence for a *future* gated decision — the live default does not move in this plan.

### WS5 — Governance: freeze optimization until reconciled
Document in the audit doc + `MEMORY.md` pointer: sweeps/OOS/M4 are **frozen** until WS3 parity + replay gates are green. Score against the Five Governance Questions. Append the §6 SESSION LOG entry to `assistant_project.md`.

## Critical files
- Read/trace: `src/runtime/backtest_v2.py` (accounting + MetricsEngine), `src/config_layer/crt_engine_v2.py` (exit logic, Trade), `src/config_layer/config_validator.py` (fitness gate), `src/governance/promotion_manager.py` (std-dev), `src/features/feature_pipeline.py` (swing lookahead).
- Edit (WS2): `src/runtime/backtest_v2.py`, `src/analytics/performance.py`, `src/analytics/sl_tp_comparator.py`, `src/research/measurement/metrics.py`.
- New (WS3/WS4): `src/analytics/metrics_oracle.py`, `tests/analytics/test_metrics_oracle_parity.py`, `tests/runtime/test_replay_determinism.py`, `docs/analysis/backtest-trust-audit-2026-06-10.md`, plus a config flag for the intrabar/causal-swing toggles in `configs/production/v1_multi_2026_03.json` (then `python scripts/maintenance/_compute_hash.py`).

## Verification
1. `pytest tests/analytics/test_metrics_oracle_parity.py tests/runtime/test_replay_determinism.py -v` → both green (oracle reconciles; replay byte-identical).
2. Full regression: `pytest` per `docs/TESTING.md` → no regressions from WS2 edits.
3. Re-run baseline backtest pre/post WS2 → ledger delta is only the expected RNG-hygiene change, documented.
4. WS4 comparison table present in the audit doc with concrete deltas; no change to live default exit/swing behavior.
5. Five Governance Questions scored; §6 SESSION LOG appended.

## Out of scope
Flipping the intrabar default to high/low touch (separate evidence-gated decision); commission modelling (flagged, not added); F1 causal-swing cutover for live mode; any new sweeps/optimization (frozen per WS5).
