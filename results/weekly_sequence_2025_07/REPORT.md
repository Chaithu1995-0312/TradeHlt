# Weekly BUY/SELL sequence, July 2025 — does the "previous outcome" algo work?

> **Illustration of mechanics, not a test.** Five weekly trades per sequence. XAUUSD H1, plain price bars (no CRT setup). Hypothetical, not promotable, no engine/config change.

## 1. Design (fixed before any result was seen)
- **One trade per week, weekly start → weekly end:** entry at the **open of the first bar of the week**, exit at the **close of its last bar**. Weeks are bounded by the month: W1 Tue 07-01 → Fri 07-04 (19 bars on 07-04), W2 07-07 → 07-11, W3 07-14 → 07-18, W4 07-21 → 07-25, W5 Mon 07-28 → Thu 07-31 (truncated at month end).
- **Direction decided from the previous week only** (the policy's own previous completed trade; win = net R > 0). Policies A reverse after loss, B continue after win, C opposite controls (reverse after win, retain after loss). A branch a policy does not name keeps the direction. Week 1 uses a seed, so each policy is shown with a BUY seed and a SELL seed. Controls: D1 always BUY, D2 always SELL, E strict BUY/SELL alternation.
- **1R:** mean daily high−low of the 14 complete days before the week (no stop; exit is time-based). **Costs:** the corrected `backtest_v2` model (0.02% round-trip spread via `signed_half_spread`, slippage 0–0.1×ATR, same slip draws for BUY and SELL in a given week), adverse in both directions.
- Code: `scripts/analysis/weekly_sequence_policy.py`; tests: `tests/test_weekly_sequence_policy.py` (13). Full ledger: `ledger.csv`.

## 2. The month in weeks (both directions, same costs)
| Wk | Start → end (bars) | Entry (open) | Exit (close) | 1R | BUY net R | SELL net R |
|---|---|---|---|---|---|---|
| 1 | 07-01 01 → 07-04 19 | 3303.27 | 3337.06 | 51.01 | +0.638 | -0.687 |
| 2 | 07-07 01 → 07-11 23 | 3334.35 | 3355.5 | 45.45 | +0.437 | -0.494 |
| 3 | 07-14 01 → 07-18 23 | 3364.3 | 3350.12 | 46.04 | -0.337 | +0.279 |
| 4 | 07-21 01 → 07-25 23 | 3349.28 | 3336.8 | 41.43 | -0.330 | +0.273 |
| 5 | 07-28 01 → 07-31 23 | 3329.24 | 3289.94 | 44.6 | -0.920 | +0.843 |

BUY and SELL raw R are exact negatives; the net numbers differ only by costs (about 0.03R per weekly trade). The market went up for two weeks, then down for three: W1 +0.66R, W2 +0.47R, W3 −0.31R, W4 −0.30R, W5 −0.88R (raw, BUY side).

## 3. Sequences and results
| Policy | Sequence (W1–W5) | Total net R | Exp./week | PF | WR | MaxDD (R) | Cost R/trade |
|---|---|---|---|---|---|---|---|
| A(BUY-seed) | BUY BUY BUY SELL SELL | +1.85 | +0.371 | 6.49 | 80% | 0.34 | 0.03 |
| A(SELL-seed) | SELL BUY BUY SELL SELL | +0.53 | +0.106 | 1.52 | 60% | 0.69 | 0.03 |
| B(BUY-seed) | BUY BUY BUY BUY BUY | -0.51 | -0.102 | 0.68 | 40% | 1.59 | 0.03 |
| B(SELL-seed) | SELL SELL SELL SELL SELL | +0.21 | +0.043 | 1.18 | 60% | 1.18 | 0.03 |
| C(BUY-seed) | BUY SELL SELL BUY BUY | -0.83 | -0.165 | 0.53 | 40% | 1.46 | 0.03 |
| C(SELL-seed) | SELL SELL SELL BUY BUY | -2.15 | -0.430 | 0.11 | 20% | 2.15 | 0.03 |
| D1 always BUY | BUY BUY BUY BUY BUY | -0.51 | -0.102 | 0.68 | 40% | 1.59 | 0.03 |
| D2 always SELL | SELL SELL SELL SELL SELL | +0.21 | +0.043 | 1.18 | 60% | 1.18 | 0.03 |
| E(BUY-seed) | BUY SELL BUY SELL BUY | -0.84 | -0.168 | 0.52 | 40% | 1.48 | 0.03 |
| E(SELL-seed) | SELL BUY SELL BUY SELL | +0.54 | +0.108 | 1.53 | 60% | 0.69 | 0.03 |

Sequential ledger for A and C (BUY seed), so the matching of BUY and SELL in order is visible:

| Wk | A (BUY seed) dir → net R | equity R | C (BUY seed) dir → net R | equity R |
|---|---|---|---|---|
| 1 | BUY → +0.638 | +0.638 | BUY → +0.638 | +0.638 |
| 2 | BUY → +0.437 | +1.075 | SELL → -0.494 | +0.144 |
| 3 | BUY → -0.337 | +0.738 | SELL → +0.279 | +0.423 |
| 4 | SELL → +0.273 | +1.011 | BUY → -0.330 | +0.093 |
| 5 | SELL → +0.843 | +1.853 | BUY → -0.920 | -0.826 |

## 4. What the sequences really are
- **A is weekly momentum.** After the first week, "stay after a win, flip after a loss" equals "trade last week's market direction". A's seed does not matter after week 1: both seeds run BUY BUY SELL SELL in weeks 2–5.
- **C is weekly reversal** (it fades last week's move) and **B is a constant direction** after its seed, identical to D1 or D2.
- So testing "does the previous trade's outcome predict the next direction" in this mode reduces to "does last week's direction persist". In July 2025 it persisted in 3 of 4 transitions (up→up, down→down, down→down; up→down failed).

## 5. Did the previous algo work this month?
Seed-independent comparison, weeks 2–5 only (4 trades each):

| Sequence (W2–W5) | Total net R |
|---|---|
| A momentum: BUY BUY SELL SELL | **+1.22** |
| C reversal: SELL SELL BUY BUY | −1.46 |
| D1 always BUY | −1.15 |
| D2 always SELL | +0.90 |
| E alternation (SELL seed): BUY SELL BUY SELL | +1.23 |
| E alternation (BUY seed): SELL BUY SELL BUY | −1.48 |

- A beat the reversal and the always-BUY control, but it did **not beat the always-SELL control (+0.90R) or one of the alternation sequences (+1.23R)**. The A-over-D2 gap is +0.32R from one extra correct flip in one week.
- Persistence 3 of 4 times: a sign test gives p = 0.62 (two-sided), so no evidence of predictive information.
- A's best-looking line (BUY seed, +1.85R over 5 weeks) leans on the seed's lucky week 1 (+0.64R); the SELL seed gives +0.53R.
- With 4–5 trades per sequence and 10 sequences, any ranking is luck-sensitive, so **no policy is selected**, and there is no hold-out.

## 6. CRT overlay (corrected engine, signals inside the month)
| Week | CRT signal (frozen lists) | A (BUY seed) | D2 always SELL |
|---|---|---|---|
| W2 | H1 htf24: LONG 07-09 (TP1, +0.88R) | BUY — agrees | SELL — disagrees |
| W3 | M15: SHORT 07-14 (TP1, +0.83R) | BUY — disagrees | SELL — agrees |
| W5 | H1 htf24: LONG 07-29 (stopped, −1.03R) | SELL — disagrees | SELL — disagrees |

Three signals, so this is anecdote. CRT's LONG in the down-trending last week lost while the weekly SELL won.

## 7. Caveats and what would make it a test
- One month, five weeks: the month's trend (up then down) decides the ranking, not the policy.
- Weeks are calendar-bounded; W1 and W5 are shorter than a full week.
- To test persistence properly use all ~104 weekly bars in the file (and more instruments) with rules frozen first. You asked for one month, so I have only offered it.
- Consistent with the earlier CRT-based pilot (`results/outcome_policy_pilot/REPORT.md`): no detectable information, no power.
