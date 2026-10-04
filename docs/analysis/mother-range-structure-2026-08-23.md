# Mother-range / InsideScore structure census (XAUUSD M15)

Point-in-time. **No `y_R_gross`. No trades. No pocket harvest.**

Generator: `scripts/analysis/mother_range_inside_close.py`  
Corpus: `data/mt5/XAUUSD_M15.csv` · 47,275 bars · 516 trading days · median **92 bars/day** (not 96).

Inside = `L1 ≤ C2 ≤ H1`. InsideScore = `(C2 − L1) / R1` (outside closes fall outside [0, 1]).

## Frequencies

| x | mode | pairs | inside rate (all) | inside n | outside n | big-filter | big n | inside rate (big) | lift |
|---|---|---|---|---|---|---|---|---|---|
| 16 | positional | 2953 | 51.8% | 1529 | 1424 | P90/100 | 348 | 68.1% | +16.3pp |
| 16 | calendar | 3094 | 51.7% | 1600 | 1494 | P90/100 | 378 | 70.6% | +18.9pp |
| 32 | positional | 1476 | 52.1% | 769 | 707 | P90/100 | 184 | 65.8% | +13.7pp |
| 32 | calendar | 1547 | 53.1% | 821 | 726 | P90/100 | 184 | 62.5% | +9.4pp |
| 96 | positional | 491 | 50.3% | 247 | 244 | P90/100 | 77 | 68.8% | +18.5pp |
| 96 | calendar | 515 | 50.9% | 262 | 253 | P90/100 | 79 | 58.2% | +7.4pp |
| 16 | calendar | 3094 | 51.7% | 1600 | 1494 | 1.5×ATR/20 | 478 | 66.9% | +15.2pp |

`big n` is the big-mother **denominator**. Calendar x=16 × 1.5×ATR/20: **320** pairs are both big and inside (matches SEM-026 detection count before one-open).

## InsideScore (when inside)

Calendar x=16: n=1600 · min 0.00 · p25 0.30 · median **0.53** · mean 0.52 · p75 0.76 · max 1.00.  
Share of inside closes below 0.5: **46.4%**. Above 0.5: **53.6%**.

All-pairs InsideScore medians sit near **0.61–0.72** because outside closes are not clipped to [0, 1].

## Mother-range size (R1), calendar x=16

n=3094 · min 1.86 · median **18.38** · mean 26.70 · p75 32.03 · max 444.58 (price units).

Does not reopen F-086. Does not rewrite identity L5. Does not change MC-MRANGE.
