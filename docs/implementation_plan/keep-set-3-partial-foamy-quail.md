# Plan — Set 3 freeze, S5/S6 consumer-contract reconciliation, XAUUSD strategy lot-sizing fix

## Context
Set 3 closed PARTIAL: 6 PASS, 2 PARTIAL. Both PARTIALs are consumer failures, not measurement failures:
- **S6** (`src/strategies/s06_scalping.py:124,132`) reads `macd_hist_z` and compares it to `macd_hist_min = 2e-05`. `|z| > 2e-05` is true on 47,197 of 47,197 bars, so the gate never filters anything.
- **S5** (`src/strategies/s05_grid.py:131-134`) compares `str(volatility_regime)` to `"TRENDING"`. The regime is an int code, so the comparison is always false.

Behind both sits a third problem that blocks any influence claim. `BaseStrategy._get_lot_size` (`src/strategies/base_strategy.py:118-130`) sizes trades with FX pip math. XAUUSD is not in `capital_management.pip_value_per_lot`, so it gets `unknown_pair_pip_value=10` and `_pips_per_unit()=10,000`. The resulting lot size rounds to 0.00, and **all 10 strategies return `NO_TRADE` on gold**.

I checked the config: XAUUSD is genuinely missing from `pip_value_per_lot`. But the config already declares XAUUSD's broker facts in `instrument_specs`: contract_size 100, lot_step 0.01, min 0.01, max 10. `src/core/position_sizing.py:size_trade_lots` is the one module that turns INR risk into lots, and Ultron and backtest `CapitalCurve` already use it. `BaseStrategy` is the only sizing path still on pip math. So F-115 is a **code fix** (route to the existing module), not a config fix.

**What you asked for (overrides the pasted read-out where they conflict):**
- Set 3 stays PARTIAL and frozen.
- S5/S6 are **not** fixed. They are investigated only.
- Set 4 stays closed.
- F-116 (unit/dtype declarations for all 48 features) is **not** in this cycle. It is listed only as a candidate output of Part A.

---

## Part A — Consumer-contract reconciliation (read-only, no `src/` edits)
For each pair, answer: which feature identity was the consumer written against, canonical or legacy? The verdict uses the §6.8 closing vocabulary.

**A1. `macd_hist_z → S6`**
- `git log -S"macd_hist_min"` and `git log -L` on `s06_scalping.py:100-176`. Find when `2e-05` entered and what S6 read at that commit. Candidates: `b34d6a8c` "stable before rename" and `45482e44`.
- Check `feature_schema.py:53,148`. They say v3.0's `macd_hist` already **emitted the z-score**. If so, the threshold was miscalibrated from the start; it was not broken by the v4.0 rename. That contradicts the read-out's "threshold set for `macd_hist_raw`" hypothesis, so it must be settled from git, not assumed.
- Measure the distribution of `macd_hist_raw` on XAUUSD and test whether `2e-05` is plausible against the raw scale. The S8 docstring says the histogram is "~100× smaller than ATR".
- Also record S6's second input, `momentum_score`. Its unit changed under F-114 (`atr_absolute`), so `momentum_min` faces the same question.

**A2. `volatility_regime → S5`**
- Trace the history of S5's `"TRENDING"` check and whether any producer ever emitted a string regime. Check ontology FM-050, `feature_pipeline`, and the legacy `regime` string produced by `dual_engine.detect_regime` (`"trend"`/`"range"`).
- Decide which of two things S5 was written against: (a) a different string-valued regime feature (an identity mismatch: wrong feature), or (b) `volatility_regime` with a wrong type assumption.

**A3. Output, in chat and the session log.** Per pair:
- intended identity
- the identity it actually consumes
- the commit where they diverged (or "never matched")
- §6.8 verdict
- the minimal fix shape, written down only, not applied

Register a finding only if a conclusion is validated, following the Findings Mandate. Note whether the evidence supports scoping F-116, but do not implement it.

## Part B — F-115: route XAUUSD strategy sizing through the canonical module (behavior change, needs authorization)
Task class: `BEHAVIOR_CHANGE_AUTHORIZED`, strategy layer only. It affects only instruments that have an `instrument_specs` entry, which today is XAUUSD alone. FX stays byte-identical.

**Changes (all in `src/strategies/base_strategy.py`; the 10 strategy files are untouched):**
1. **Load the spec at init.** Load `instrument_specs` strictly via `get_prod_section`. In `__init__`, resolve `self._spec` with `position_sizing.instrument_spec(...)` when `has_instrument_spec(...)`, otherwise `None`.
2. **Size through the canonical module.**
   - `_get_lot_size(sl_pips)`: when `self._spec` is set, recover the price distance as `sl_pips / self._pips_per_unit()`. That is the exact inverse of `_sl_pips`, so call sites do not change. Then call `size_trade_lots(_MAX_RISK_PER_TRADE, _USD_TO_INR_RATE, dist, **spec)`.
   - If it returns `(None, reason)`, return `0.0`. Existing callers already turn that into `NO_TRADE`. Log the reason.
   - When `self._spec` is `None`, keep the current pip path unchanged.
3. **Compute INR P&L through the canonical module.** `_calc_sl_inr` / `_calc_tp_inr`: on the spec path, use `position_sizing.usd_quote_pnl_inr(|Δprice|, contract_size, lots, usd_inr)`. Without this, `sl_inr` would be priced in pips × 10 and come out about 1000× too large.
4. **No duplicate gold facts.** Do **not** add XAUUSD to `pip_value_per_lot`, and do not special-case `_pips_per_unit` for gold. Either would be a second authority for gold's contract facts.
5. **Leave the risk budget alone.** It stays `max_risk_per_trade_inr` (25,000 INR), which is the existing semantics. The mismatch with F-111's `risk_percent` is reported, not changed.

**Expected on the S6-reachable bar** (ATR 5.54, sl_mult 0.5, so the stop distance is 2.77):
- 25,000 / 84 = 297.6 USD of risk
- 297.6 / 2.77 = 107.4 oz
- 107.4 / 100 = 1.074 lots, floored to **1.07**
- `sl_inr` ≈ 24,900, which is at or under the 25,000 cap

**Downstream reach — measure, don't assume:**
- Find where `StrategyResult` reaches a decision: `live_engine_hook`, then the orchestrator, then `strategy_consensus` (`fusion_engine.py:159`, weight 0.0 means disabled), then `engine_runner.py:833`.
- Record the active consensus weight. If it is 0, F-115 unblocks *measurement* of strategy scores, but there is still **no decision influence**, and the plan says so explicitly.

**Governance (same turn):**
- BUILD_IMPACT_MANIFEST, then `construction_protocol.py validate-completion`.
- F-115 row in `docs/current-findings.md`, plus the CLAUDE.md Truths Index row (test-enforced pair).
- Topic sync and a config-reference note.
- SESSION LOG in `assistant_project.md`.
- Hash-neutral: no `params` edit.

## Verification
1. **Baseline first:** run the green floor (`check_governance_invariants.py --all`) and record the pre-existing reds. The two known reds from other sessions are noted, not touched.
2. **New test** `tests/test_base_strategy_instrument_sizing.py`:
   - XAUUSD S6 bar gives 1.07 lots and `sl_inr` ≤ cap.
   - A tiny risk budget is rejected below the minimum lot (returns 0.0).
   - EURUSD/USDJPY lots and INR values are byte-identical to the pre-change formula.
   - An instrument with no spec stays on the legacy path.
3. Run the existing strategy tests (`pytest -k strategy`) and `tests/test_backtest_declared_constants.py`.
4. **Re-run the Set 3 probe on XAUUSD** (same corpus; echo path and row count): count non-`NO_TRADE` `StrategyResult`s per strategy, before and after. This is the measurement Set 3 could not make.
   - Set 3's verdict stays frozen.
   - S5/S6 numbers are reported as "consumer still defective per Part A".
5. Green floor again, then construction-protocol `check`.

## Not in scope (reported only)
- S5/S6 code fixes
- F-116 ontology unit/dtype rollout
- Set 4
- The 78-row warmup
- The pasted read-out's "fabricated-hash incident" claim: **UNVERIFIED** in this repo. I will look for it in `assistant_project.md` before mentioning it, and will not log it from the read-out alone.
