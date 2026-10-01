# Net-R trace (backtest ledger) + one confirmed defect

## Context
The user asked to trace how `pnl_rr_net` (net R) is computed. Read-only trace of `src/runtime/backtest_v2.py`
on the active `v2_htfcrt_2026_08`, checked by reproducing `run_20260930_163142`'s trades by hand.

## The formula, step by step
1. **Entry fill** (`TradeJournal.on_trade_opened`, `backtest_v2.py:1365-1366`):
   `entry_fill = entry_raw + e_slip + spread_half`.
   - `entry_raw` = the engine's `trade.entry_price` (the RETEST close).
   - `e_slip` = uniform(0, `slippage_atr_fraction` 0.1 × ATR), always adverse (`SlippageModel`, `:769`).
   - `spread_half` = bar close × `simulated_spread_pct` 0.0002 / 2 (`:3654`), taken from the OPEN bar.
2. **Stop re-floor** (`:1373-1390`): if the fill sits closer than `sl_atr_buffer` × ATR to the SL, the
   stop is moved out. `rec.sl_price` = that effective SL.
3. **Exit raw** (`_resolve_exit`, `:1773`): STOPPED → `t.sl_price`; TP2 → `t.tp2_price`; with a TP1
   partial the blend `f·tp1 + (1−f)·level`; structural/timeout/unconfirmed → bar close.
4. **Exit fill** (`on_trade_closed`, `:1454-1455`): `exit_fill = exit_raw + x_slip − spread_half`,
   using the CLOSE bar's spread and a fresh adverse slip draw.
5. **R** (`:1471-1473`), with risk = `|entry_fill − rec.sl_price|`:
   - `pnl_rr_net = (exit_fill − entry_fill) / risk`
   - `pnl_rr_raw = (exit_raw − entry_raw) / risk` (raw move over the FILL-based denominator)
   - Direction-signed for shorts. `pip_size` cancels out.
6. **Totals**: `total_pnl_rr_net` = Σ (`:1877`); cost drag = Σraw − Σnet.

**Worked example, CRT-0001** (matches `trades.csv` to 4 dp): risk = 2615.0827 − 2610.0476 = 5.0351;
net = (2609.7720 − 2615.0827)/5.0351 = **−1.0547**; raw = (2610.0476 − 2614.46)/5.0351 = −0.8763; cost
= 0.1786R (entry 0.6227 + exit 0.2756 in price).

## Confirmed defect: the TP1 partial is never booked in the ledger
- After TP1, the runner skips the close (`:4296`). On the bar that closes the runner it reads
  `_trade_status = t.status` (`:4295`) AFTER `process_candle`, where `update_trade` has already set the
  status to `TP2` or `STOPPED`.
- So the `trade_status == "TP1"` blend branches in `_resolve_exit` (`TP1_TP2`, `TP1_BE_STOP`, and my new
  `TP1_UNCONFIRMED`) are unreachable from this call site. The whole position books at the final level.
- **Evidence, CRT-0003:**
  - Ledger `pnl_pips_raw` = 236.0 = TP2 2936.75 − 2934.39 (full TP2).
  - The engine's own `TRADE_TP2` event has pnl 2.065 = 0.5·(2936.16 − 2934.39) + 0.5·(2936.75 − 2934.39) (blend).
  - Ledger over-books by 0.295 / 1.816 ≈ **+0.16R**.
  - Same bug on a TP1-then-trail stop: it books the full position at the trailed stop.
- Unit tests pass `trade_status="TP1"` directly into `_resolve_exit`, so they never see the real call
  order.

## Other issues noted (not fixed)
- `pnl_rr_raw` mixes bases, so a clean stop shows −0.876R, not −1R.
- Spread is 0.02% of price (~$0.52 round trip on gold) vs ~$0.13 measured (F-082). Slippage is always
  adverse on both sides; stops fill at the level even on a gap.
- If the SL was re-floored, `_resolve_exit` books STOPPED at the engine's `t.sl_price`, not the
  re-floored `rec.sl_price`, so a stop-out ≠ −1R.
- `slippage_pips` backs out entry slip using the CLOSE bar's spread (cosmetic).

## Proposed fix (on lane/entry-chain, after approval)
1. In the runner, capture `_pre_status = engine.state.active_trade.status` BEFORE `process_candle`
   (`backtest_v2.py:3662`), and pass it as `trade_status` to `_resolve_exit` at the closing call site
   (`:4295-4307`).
2. Test: drive a real `CRTEngine` + `_resolve_exit` through TP1 then TP2, and through TP1 then trail stop.
   Assert the blended exit; mutation-check it.
3. Re-run the legacy arm. Expect CRT-0003 to change from +0.61R to about +0.45R and nothing else to move.
   Record it in F-110's note or as a new finding.
