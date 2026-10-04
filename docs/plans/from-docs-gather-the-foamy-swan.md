# ROI Increase Plan — Gap Analysis & Implementation (BNBUSDT M15)

> Created: 2026-05-29 · Updated: 2026-05-29 · Milestone: optimization track (Phase 6b — ROI gaps)

---

## Context

The ROI Step (Phase 6a, 2026-05-29) established the first measured baseline:

| Metric | Baseline value |
|---|---|
| Total return (ROI) | +4.91% over 2 yr |
| CAGR | +2.43% |
| Profit factor | 1.79 |
| Return / max-DD | 2.38 |
| Trades | 15 (2 yr), 60% WR, +0.328R avg |

**The ROI equation is multiplicative:** `ROI ≈ N × R̄ × risk%` = 15 × 0.328 × 1.0% = 4.9%

Three independent levers, each with a measurable gap. This plan identifies the gaps from the trades ledger (`results/roi_baseline/run_20260529_161443_BNBUSDT/`) and the codebase exploration, then sequences additive work to close them — following the same measure-first doctrine as Phases 0–5.

`docs/architecture/goal.md` still holds: correctness invariants are not touched. All work is additive telemetry + config-tuning + governance-safe parameter sweep. Changes that would require an explicit deviation flag (e.g. raising risk% above current gate) are flagged explicitly.

---

## Gap Analysis

### Gap 1 — Frequency (N = 15 / 2 yr) is the dominant throttle

`ROI sensitivity: +1 trade ≈ +0.33%` (at current R̄ and risk). Frequency is so low that a 2× lift here doubles ROI more than any other lever.

**Root cause is unmeasured.** `BacktestMetrics.state_distribution` tracks *candle-counts per state* (how long setups dwell), NOT *how many setups entered each state*. The binding constraint — which funnel stage drops the most candidates — is invisible in the current telemetry.

Phase 0 memory identified DISPLACEMENT→EXPANSION at 5.2% as the old bottleneck, but that was on an earlier config and measured manually from JSONL events. With the current config (TTL guard, shadow path, selectivity from Phases 1–5) the binding stage may have shifted.

**Sub-gaps from the trades ledger:**
- 5 of 15 losses are SL hits within 2–11 candles; losers confirm clean −1R structure (not the frequency problem).
- The detection thresholds that control funnel entry are: `body_ratio_min` (0.65), `atr_multiplier_min` (1.50), `expansion_atr_min_distance` (0.20), `retest_depth_max` (0.30). These live in the tuner `PARAM_SPACE` (`scripts/training/auto_tuner_multi.py:98–110`).
- The tuner's current fitness gives 20% weight to `trade_count_norm` with target=50 — at N=15 vs target=50 this should already push toward more trades, yet 15/50 is still only 30% of target. The binding constraint is upstream of the parameters already being swept.

### Gap 2 — R-capture ceiling (R̄ = 0.328R; winners capped at ~+1.9R)

All 5 winners hit TP2 (~+1.9R). Zero TP1-only exits. No runner / TP3 exists. Strong moves (like CRT-0004 +1.90R, CRT-0005 +1.83R) are capped at TP2 with no tail.

**Sub-gaps:**
- `tp2_atr_multiplier = 2.0` in the active config, which with typical SL distance ~3.2 ATR gives TP2 ≈ 6.4 ATR from entry. A TP3 at 3.0× or a trail-after-TP2 would extend R-capture without increasing risk.
- CRT-0012 ran 90 candles to TP2 (+1.92R). A trailing stop activated after TP2 could have captured additional R.
- Config keys for TP extension already exist in the `crt_engine` section pattern (tp1/tp2 multipliers per intent) — a `tp3_atr_multiplier` key follows the same pattern.

### Gap 3 — Cost drag (0.99R = 17% of gross 5.91R)

`simulated_spread_pct = 0.0002` + slippage_atr_fraction = 0.1. Per-trade avg cost = 3502 pips. This is already measured but not broken down by session.

NEWYORK session: 7 trades, 71% WR, +2.99R net — best session.  
LONDON session: 8 trades, 50% WR, +1.93R net — more trades but worse WR and lower R/trade.

Session-level cost drag is not currently separated in telemetry. LONDON trades may carry disproportionate cost (wider spreads). This is a read-only audit gap, not a code change.

### Gap 4 — Risk headroom (risk% = 1.0%; gate ceiling = 5.0%)

Current: 1.0% risk/trade (backtest + gate). Gate max_risk_per_trade_pct = 1.0% and max_portfolio_risk_pct = 5.0%.

At N=15 / 2yr there is virtually never more than 1 open position, so portfolio cap is never binding. Raising risk/trade from 1.0% to 1.5% would lift ROI by ~50% with the same edge — but this is a **deliberate deviation** that changes expected drawdown. Must be flagged and measured before applying. For now: measure what drawdown would look like at 1.5% (re-run with `--risk-pct 0.015`) and compare to gate before promoting.

---

## Proposed Work (sequenced by confidence and reversibility)

### Step 1 — Funnel transition-count telemetry (additive, measure-first) ★ Start here

**Why first:** Can't fix frequency without knowing where the funnel breaks. Mirrors Phase 0 doctrine.

**What:** Add a `funnel_counts` dict to `BacktestMetrics` tracking *setup entry counts* per CRT state (not candle-dwell). A "setup" enters SWEEP when it transitions out of RANGE with a valid sweep; DISPLACEMENT when transitioning out of SWEEP; etc.

**How:**
- `src/config_layer/crt_engine_v2.py`: add a `transition_counts` dict to `CRTEngine.__init__` (around line 509); increment on each legal state transition in the transition handler (around line 550).
- `src/runtime/backtest_v2.py`: add `funnel_counts: dict = field(default_factory=dict)` to `BacktestMetrics`; populate from the engine's `transition_counts` in `MetricsEngine.compute`. Add to `to_dict()`.
- Report writer: add a `── FUNNEL ──` block showing transition counts and per-stage conversion rates (e.g. `SWEEP→DISPLACEMENT: 83 / 847 = 9.8%`).
- **No gate, no fitness change.** Additive telemetry only (invariant #5).
- Config: no new config knobs needed — this is pure instrumentation.

**Verification:** Run BNBUSDT baseline again; confirm `funnel_counts` in summary JSON shows non-zero counts for each stage; conversion rates sum correctly; pytest green.

---

### Step 2 — Detection-threshold sweep targeting frequency (tuner, config-safe)

**Why:** Once funnel counts reveal the binding stage, run a targeted parameter sweep with frequency-weighted fitness. The tuner infrastructure already exists (`scripts/training/auto_tuner_multi.py`, CLI entry, `PARAM_SPACE`, checkpointing to `results/tuner/checkpoint_multi.json`).

**What:** Modify the tuner fitness to temporarily up-weight `trade_count_norm` (e.g. from 0.20 → 0.40) and down-weight `expectancy_rr` (0.50 → 0.30), with a floor on expectancy (reject if exp < 0.10R). This finds configs that trade more without going negative-expectancy.

**How:**
- Add a `frequency_boost_mode: false` flag to the `tuner` config section in `configs/production/v2_multi_2026_04 - deepdeektry.json`. When true, `auto_tuner_multi.py:fitness_multi()` swaps weights. A single boolean switch — no fitness logic duplication.
- Set `trade_count_target: 30` (from 50) as the new reasonable target for BNBUSDT (given the 2yr data).
- Run: `python scripts/training/auto_tuner_multi.py --data-dir data/ --instruments BNBUSDT --max-trials 200`
- Promote via governance if improved: `python src/governance/promotion_manager.py promote ...`
- **No behavior change without promotion.** The sweep is read-only until the config is promoted.

**Deviation flag:** Re-weighting fitness is within the existing ConfigValidator governance path. The resulting config still must pass all hard/soft gates (min trades, max drawdown, score threshold) before promotion. No invariant is touched.

---

### Step 3 — TP3 / trail-after-TP2 for R-capture extension (config + thin code)

**Why:** All winners are currently capped at TP2 (~+1.9R). A TP3 target at 3.0× ATR would extend R on strong moves without increasing risk (SL is already set; only the upside cap changes).

**How:**
- `configs/production/v2_multi_2026_04 - deepdeektry.json`: add `"tp3_atr_multiplier": 3.0, "tp3_enabled": false` to the `crt_engine` section. Default false = no behavior change until explicitly enabled.
- `src/config_layer/crt_engine_v2.py`: add `tp3_atr_multiplier: float = 3.0` and `tp3_enabled: bool = False` to `CRTConfig` (same pattern as existing tp1/tp2 fields). In `compute_crt_levels()` (approx. line 1888): compute `tp3_price` if enabled.
- `src/runtime/backtest_v2.py`: check `tp3_price` in the trade-resolution logic alongside TP1/TP2 checks. Add `tp3_hits: int = 0` to `BacktestMetrics`.
- **Enabled only by config flag.** Default false means zero behavior change until user promotes a config with `tp3_enabled: true`.

**Reuse pattern:** Exactly mirrors the existing tp1/tp2_atr_multiplier_breakout/pullback per-intent pattern. No new architectural concept.

---

### Step 4 — Risk% sensitivity study (read-only, then config decision)

**Why:** At N=15 / 2yr, raising risk/trade from 1.0% to 1.5% would lift ROI by ~50% if edge holds. But this increases max drawdown proportionally. Must be measured before deciding.

**How (read-only first):**
- Run three CLI backtests at risk_pct 0.01, 0.015, 0.02 using `--risk-pct` flag.
- Compare: total_return_pct, max_drawdown_pct, return_to_max_dd (already in the new ROI metrics).
- Record in a dated analysis doc in `docs/analysis/`.

**If the MAR ratio stays above 2.0 at 1.5% risk:** raise `risk_pct_per_trade` in the `backtest` section and `max_risk_per_trade_pct` in the `ultron_risk_gate` section, re-hash (params key only), promote. This is an **explicit deviation step** — must be flagged in SESSION LOG and the promotion log.

---

### Step 5 — Session-level cost audit (additive report, no code change)

**Why:** LONDON vs NEWYORK have different WR/R but cost drag is not separated. If LONDON's lower WR is partly cost-driven, a session filter or wider SL buffer in London could improve net R.

**How:** The `session_breakdown` dict is already in the distribution output. A simple post-processing script (`scripts/analysis/session_cost_audit.py`) reads the trades CSV and computes gross vs net PnL per session. No new telemetry needed — the data is already in `BNBUSDT_trades.csv`. This is a one-off analytical script in `scripts/`, not production code.

---

## File inventory

| File | Change type |
|---|---|
| `src/config_layer/crt_engine_v2.py` | Add `transition_counts` to `CRTEngine` (Step 1); add `tp3_*` to `CRTConfig` (Step 3) |
| `src/runtime/backtest_v2.py` | Add `funnel_counts`, `tp3_hits` to `BacktestMetrics`; populate from engine (Steps 1, 3) |
| `configs/production/v2_multi_2026_04 - deepdeektry.json` | Add `frequency_boost_mode` to `tuner`; add `tp3_*` to `crt_engine`; adjust `trade_count_target` (Steps 2, 3) |
| `scripts/training/auto_tuner_multi.py` | Add `frequency_boost_mode` branch to `fitness_multi()` (Step 2) |
| `scripts/analysis/session_cost_audit.py` | New read-only analysis script (Step 5) |
| `tests/test_roi_gaps.py` | Tests for funnel_counts, tp3 logic, fitness boost mode (Steps 1–3) |

---

## Sequence rationale

1 → 2: You can't sweep for frequency without knowing where the funnel breaks — Step 1 unblocks Step 2.  
2 → 3: TP3 is independent of frequency and can be done in parallel, but it has smaller expected impact (only affects existing winners).  
4: Deferred until edge is confirmed at higher frequency (Step 2). Raising risk on 15 trades / 2yr is not yet validated.  
5: Purely analytical, can run at any point.

---

## Invariant / governance check

- **Deterministic?** All changes are post-hoc metrics (Step 1) or config-gated with default=false (Steps 3–4). Step 2 sweep is read-only until promoted. ✅
- **Telemetry additive?** funnel_counts, tp3_hits are additive new fields. Nothing removed. ✅
- **No partial fusion?** EXPECTED_ENGINES untouched. ✅
- **Governance path?** Tuner sweep → ConfigValidator gates → PromotionManager → promotion_log. ✅
- **Deviation flags required?** Step 4 (raise risk%) and enabling tp3 in production require explicit SESSION LOG deviation note + Five Governance Questions pass before promoting.

---

## Verification (end-to-end, after Steps 1–3)

1. `python -m pytest tests/ -k "roi or funnel or tp3"` — green
2. Re-run BNBUSDT baseline: `python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/roi_gap1`  
   → confirm `funnel_counts` in summary JSON; report shows `── FUNNEL ──` block with conversion rates.
3. (Step 2) Run frequency sweep: `python scripts/training/auto_tuner_multi.py --data-dir data/ --instruments BNBUSDT --max-trials 200`  
   → checkpoint at `results/tuner/checkpoint_multi.json`; confirm improved trade count with expectancy floor holding.
4. (Step 3) Enable `tp3_enabled: true` locally; re-run baseline; confirm `tp3_hits > 0` on historical data; confirm no regressions in gate logic.
