## m15
Frozen list: `m15_trades.csv` sha256 `f4d9d81b91af9c3e28f4c1d16f8587e402d1396c82845fdf16482e605337710d`; opportunities 9 (development 5, hold-out 4); per-window opportunity counts (all periods): open=1, middle=7, close=1

### Development period (< 2025-05-22) — all policies
| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |
|---|---|---|---|---|---|---|---|---|
| A | open | 0 | - | - | - | - | - | - |
| A | middle | 3 | -0.205 [-3.01, 2.6] | 0.6 | 33% | 1.54 | 0.473 | 123.3 |
| A | close | 1 | -1.040 n/a | 0.0 | 0% | 1.04 | 0.078 | 66.2 |
| A | all | 4 | -0.414 [-2.02, 1.2] | 0.36 | 25% | 1.66 | 0.374 | 109.0 |
| B | open | 0 | - | - | - | - | - | - |
| B | middle | 4 | -0.441 [-2.09, 1.21] | 0.34 | 25% | 1.76 | 0.473 | 117.6 |
| B | close | 1 | -1.040 n/a | 0.0 | 0% | 1.04 | 0.078 | 66.2 |
| B | all | 5 | -0.561 [-1.72, 0.6] | 0.25 | 20% | 2.8 | 0.394 | 107.3 |
| C | open | 0 | - | - | - | - | - | - |
| C | middle | 1 | -1.146 n/a | 0.0 | 0% | 1.15 | 0.473 | 100.3 |
| C | close | 1 | -1.040 n/a | 0.0 | 0% | 1.04 | 0.078 | 66.2 |
| C | all | 2 | -1.093 [-1.77, -0.42] | 0.0 | 0% | 2.19 | 0.276 | 83.3 |
| D | open | 0 | - | - | - | - | - | - |
| D | middle | 4 | -0.441 [-2.09, 1.21] | 0.34 | 25% | 1.76 | 0.473 | 117.6 |
| D | close | 1 | -1.040 n/a | 0.0 | 0% | 1.04 | 0.078 | 66.2 |
| D | all | 5 | -0.561 [-1.72, 0.6] | 0.25 | 20% | 2.8 | 0.394 | 107.3 |

### Selection (pre-registered: eligible = A/B/C with dev n >= 3 and dev expectancy > D's -0.561; pick the highest)
Selected: **A**

### Hold-out (>= 2025-05-22) — selected policy A vs D, evaluated once
| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |
|---|---|---|---|---|---|---|---|---|
| A | open | 0 | - | - | - | - | - | - |
| A | middle | 3 | +0.886 [0.7, 1.07] | inf | 100% | 0.0 | 0.075 | 183.5 |
| A | close | 0 | - | - | - | - | - | - |
| A | all | 3 | +0.886 [0.7, 1.07] | inf | 100% | 0.0 | 0.075 | 183.5 |
| D | open | 1 | +0.829 n/a | inf | 100% | 0.0 | 0.11 | 88.8 |
| D | middle | 3 | +0.886 [0.7, 1.07] | inf | 100% | 0.0 | 0.075 | 183.5 |
| D | close | 0 | - | - | - | - | - | - |
| D | all | 4 | +0.872 [0.77, 0.98] | inf | 100% | 0.0 | 0.084 | 159.8 |

### Descriptive transitions (all opportunities, not used for selection)
| Previous | Relation to previous direction | next trades | next wins |
|---|---|---|---|
| prev loss | reverse | 2 | 1 |
| prev loss | same dir | 2 | 1 |
| prev win | reverse | 1 | 1 |
| prev win | same dir | 3 | 2 |

Fisher exact, prev loss: same-vs-reverse win rate 1/2 vs 1/2, p = 1.00

Fisher exact, prev win: same-vs-reverse win rate 2/3 vs 1/1, p = 1.00

## h1_htf24
Frozen list: `h1_htf24_trades.csv` sha256 `6ddb9feedacc1e735630874b038f7c899bc1abc3353d1bf3d9d29e0c62280de3`; opportunities 12 (development 5, hold-out 7); per-window opportunity counts (all periods): open=0, middle=10, close=2

### Development period (< 2025-05-22) — all policies
| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |
|---|---|---|---|---|---|---|---|---|
| A | open | 0 | - | - | - | - | - | - |
| A | middle | 3 | +0.602 [-0.76, 1.96] | inf | 100% | 0.0 | 0.277 | 128.4 |
| A | close | 2 | +0.215 [-2.94, 3.37] | 13.79 | 50% | 0.03 | 0.051 | 130.5 |
| A | all | 5 | +0.447 [-0.14, 1.04] | 67.51 | 80% | 0.03 | 0.187 | 129.2 |
| B | open | 0 | - | - | - | - | - | - |
| B | middle | 1 | +0.029 n/a | inf | 100% | 0.0 | 0.635 | 176.1 |
| B | close | 2 | +0.215 [-2.94, 3.37] | 13.79 | 50% | 0.03 | 0.051 | 130.5 |
| B | all | 3 | +0.153 [-0.52, 0.83] | 14.64 | 67% | 0.03 | 0.246 | 145.7 |
| C | open | 0 | - | - | - | - | - | - |
| C | middle | 2 | +0.888 [-2.04, 3.81] | inf | 100% | 0.0 | 0.098 | 104.5 |
| C | close | 1 | +0.463 n/a | inf | 100% | 0.0 | 0.039 | 82.1 |
| C | all | 3 | +0.747 [-0.09, 1.58] | inf | 100% | 0.0 | 0.078 | 97.1 |
| D | open | 0 | - | - | - | - | - | - |
| D | middle | 3 | +0.602 [-0.76, 1.96] | inf | 100% | 0.0 | 0.277 | 128.4 |
| D | close | 2 | +0.215 [-2.94, 3.37] | 13.79 | 50% | 0.03 | 0.051 | 130.5 |
| D | all | 5 | +0.447 [-0.14, 1.04] | 67.51 | 80% | 0.03 | 0.187 | 129.2 |

### Selection (pre-registered: eligible = A/B/C with dev n >= 3 and dev expectancy > D's 0.447; pick the highest)
Selected: **C**

### Hold-out (>= 2025-05-22) — selected policy C vs D, evaluated once
| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |
|---|---|---|---|---|---|---|---|---|
| C | open | 0 | - | - | - | - | - | - |
| C | middle | 3 | +0.276 [-2.51, 3.06] | 1.81 | 67% | 1.02 | 0.048 | 138.2 |
| C | close | 0 | - | - | - | - | - | - |
| C | all | 3 | +0.276 [-2.51, 3.06] | 1.81 | 67% | 1.02 | 0.048 | 138.2 |
| D | open | 0 | - | - | - | - | - | - |
| D | middle | 7 | -0.326 [-1.15, 0.49] | 0.45 | 29% | 3.11 | 0.063 | 175.8 |
| D | close | 0 | - | - | - | - | - | - |
| D | all | 7 | -0.326 [-1.15, 0.49] | 0.45 | 29% | 3.11 | 0.063 | 175.8 |

### Descriptive transitions (all opportunities, not used for selection)
| Previous | Relation to previous direction | next trades | next wins |
|---|---|---|---|
| prev loss | reverse | 3 | 0 |
| prev loss | same dir | 2 | 1 |
| prev win | reverse | 3 | 3 |
| prev win | same dir | 3 | 1 |

Fisher exact, prev loss: same-vs-reverse win rate 1/2 vs 0/3, p = 0.40

Fisher exact, prev win: same-vs-reverse win rate 1/3 vs 3/3, p = 0.40
