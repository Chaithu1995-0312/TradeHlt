# Fix: HTF rollover no longer closes an open trade (EXECUTION) — validation report

## 1. The defect and the fix
`ResetLogic.should_reset` (`src/config_layer/crt_engine_v2.py`) ignored an HTF rollover in `EXPANSION` and `RETEST` but not in `EXECUTION`, so the next rollover force-closed any open trade at the next bar's close (`RESET_CLOSE`), regardless of its stop or targets. The fix is one token: `CRTState.EXECUTION` added to the protected list (`crt_engine_v2.py:1325`). Retrace, extension, sweep-expiry and session-gap resets still apply in `EXECUTION`. No config key changed, so no rehash.

## 2. Tests
- New `tests/test_reset_logic_execution.py` (10 tests): HTF change does not reset in EXPANSION / RETEST / EXECUTION; still resets in RANGE / SWEEP / DISPLACEMENT; retrace and extension resets still fire in EXECUTION; no reset without an active range. **Without the fix, exactly the EXECUTION case fails; with it, all 10 pass.**
- Full suite: before 12 failed / 881 passed; after **12 failed / 891 passed** (+10 new). The same 12 failures existed before the change: 11 in `tests/inout/test_probability_engine.py` and 1 in `tests/test_control_plane_doc_alignment.py`. They are unrelated to this fix and untouched.

## 3. Equivalence with the studied runtime patch (plain CLI, no monkeypatch)
| Run | Result | Equal to the runtime-patch run |
|---|---|---|
| M15, production defaults | 10 trades, 50% win rate, +0.18R, DD 2.4% | **identical summary** |
| H1, `--htf 24` | 13 trades, 53.8% win rate, +2.35R, DD 3.0% | **identical summary** |
| M15 re-run | identical (deterministic) | — |

The code fix is exactly the change evaluated in the earlier reports.

## 4. `ConfigValidator validate-prod`, before and after
Production params, `XAUUSD_M15.csv` alone in the data dir (the discovery helper maps files to instruments by name, so the four XAUUSD files in `data/` would collide).

| | Before | After |
|---|---|---|
| Decision | **APPROVE** | **APPROVE** |
| Trades | 12 | 12 |
| Win rate | 50.0% | 50.0% |
| Expectancy (avg RR net) | **−0.867R** | **+0.037R** |
| Max drawdown | 11.6% | 3.0% |
| Final fitness score | 0.378 | 0.500 |
| Warnings | low expectancy; low trade count | low trade count |

## 5. What this does and does not show
- The fix removes a real artifact: expectancy per trade moves from −0.87R to roughly zero, and drawdown from 11.6% to 3.0%.
- **APPROVE before the fix is itself a finding.** The old behavior, losing 0.87R per trade on average, passed the validator. Expectancy below −0.5R is only a soft warning in the gates (`min_expectancy`), and the fitness score is driven by win rate and trade count. The validator would have approved the buggy engine, so APPROVE here is weak evidence of quality.
- **The edge is not established.** Expectancy +0.04R on 12 trades is indistinguishable from zero (standard error is of order 0.3R), and 12 trades is a "marginal sample" per the validator's own warning.
- **In-sample.** The bug was found on this same two-year corpus. There is no out-of-sample test here.
- The validator runs with production params (12 trades); my CLI runs use CLI-default CRT params (10 trades). Both show the same effect.

## 6. Governance follow-ups (not done)
- `configs/production/v1_multi_2026_03.json` is unchanged, but its `validation_summary` was produced by the old engine behavior and is now stale. Updating it means re-validating, rehashing (`python scripts/maintenance/_compute_hash.py`) and going through `PromotionManager`.
- Consider tightening the gates (make expectancy a hard gate, or report it prominently) so a −0.87R/trade config cannot pass. That is a separate decision.
