# Fixes: spread sign on shorts (F2) and one-bar entry lookahead (F1)

## Changes
| Where | Change |
|---|---|
| `src/runtime/backtest_v2.py` | New `signed_half_spread(direction, spread_half)`: `+` for LONG, `−` for SHORT. `compute_fill_prices`, `TradeJournal.on_trade_opened` / `on_trade_closed` and the `slippage_pips` expression use it, so entry and exit fills are adverse for either direction (before: spread favored shorts). The RNG draw order is unchanged, so slippage values are identical. |
| `src/config_layer/crt_engine_v2.py` | `ExecutionEngine.build_trade(..., entry_price=None)`. The soft-confirmation block now enters at the **confirming bar's close** (`entry_price = candle.close`), where before it used the earlier retest-bar close while reading the confirming bar in full. The range-position filter uses the same price. SL stays anchored to the displacement extreme + 0.2×ATR; TP1/TP2 are re-derived from the new 1R. The default (no argument) still falls back to the retest close. |
| Tests | `tests/test_backtest_fill_prices.py` (8 tests), `tests/test_entry_price_no_lookahead.py` (3 tests). |

Entry choice: the confirming-bar close. It is the price known when the decision is made. A stricter option (the next bar's open) was not used; the close is slightly optimistic.

## Results (corrected engine, plain CLI, production defaults)
| | M15 before | M15 after | H1 `--htf 24` before | H1 after |
|---|---|---|---|---|
| Trades | 10 | **9** | 13 | **12** |
| Win rate | 50% | 55.6% | 53.8% | 50.0% |
| Raw R | +0.25 | +2.99 | +2.68 | +1.33 |
| Net R | +0.18 | **+0.68** | +2.35 | **−0.05** |
| Expectancy / trade | +0.02R | **+0.08R** (SE 0.34R) | +0.18R | **−0.004R** (SE 0.24R) |
| Max DD | 2.4% | 2.8% | 3.0% | 3.1% |
| Exits | 5 TP1 / 5 stops | 6 TP1 / 3 stops | 6 TP1 / 3 stops / 4 resets | 3 TP1 / 3 stops / 5 gap / 1 reset |

"Before" = after the rollover fix, before F1/F2. Checks: a re-run is identical (deterministic); in every trade, `entry_raw` equals the close of the opening (confirming) bar (9/9 and 12/12); net R < raw R on every trade (9/9 and 12/12).

Cost drag is large on M15: raw +2.99R becomes net +0.68R (about 0.26R per trade), because the 0.02% spread is a big fraction of M15 stop distances.

## Validator (`validate-prod`, XAUUSD M15, production params)
| | Before F1/F2 | After |
|---|---|---|
| Trades / expectancy / drawdown | 12 / +0.037R / 3.0% | 9 / +0.085R / 2.2% |
| Decision | APPROVE | **REJECT**: "only 9 trade(s) — minimum is 10" |

The reject is on sample size only; expectancy passes the 0.0R gate. It says nothing about quality in either direction.

## Reading it
- Correcting the two defects removes most of the apparent edge on H1 (net +2.35R → −0.05R) and leaves M15 marginal (+0.08R per trade, SE 0.34R). Neither is distinguishable from zero.
- The earlier "APPROVE, +0.037R" is superseded by this result.
- Full suite: 12 failed / 913 passed; the same 12 failures existed before these changes.
- Not changed: features (F4–F10), TP2/runner accounting (F3), configs, hashes, promotion.
