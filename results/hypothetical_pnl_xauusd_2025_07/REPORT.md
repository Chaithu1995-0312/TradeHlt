# Hypothetical P&L — XAUUSD, one month (July 2025), H1 and M15

> **HYPOTHETICAL.** Historical simulation only. Not a `ValidationReport`, not promotable, and not evidence of an edge.

## 1. Data and month selection
- Slices of the two-year files, 2025-07-01 01:00 → 2025-07-31 (not committed; `data/` is gitignored):
  - `data/XAUUSD_H1_2025-07.csv`: 525 bars, SHA-256 `a1ef423d…1752`
  - `data/XAUUSD_M15_2025-07.csv`: 2,100 bars, SHA-256 `0c32998d…3a7`
- **Selection rule, disclosed:** a read-only count of the earlier trade entries showed that any single month holds 0–2 trades. 2025-07 was the only month with entries on both timeframes in the earlier runs (M15: 07-09 and 07-14; H1 htf=24: 07-09 and 07-29). It was chosen for trade availability, not for P&L. I had already seen the full-period results for those trades, so this is **not a blind pick**.
- Each run starts cold on the slice: the engine has only the 30 warmup bars, and range boundaries are counted from the first bar of the slice, so entries can differ from the two-year runs.

## 2. Rules (nothing tuned)
- **M15:** production defaults, native (`htf=4`, 1-hour ranges).
- **H1:** `--htf 24` (the value pre-chosen earlier, daily ranges).
- **Variant:** the runtime patch from the earlier reports (an HTF rollover cannot close a trade in `EXECUTION`). Nothing in `src/` or `configs/` was edited.
- Costs as before: slippage random(0, 0.1×ATR) seed 42, spread 0.0002, 1% risk, gap reset 120 min.

## 3. Results

| Run | Bars | Trades | Exits | Net R | Max DD |
|---|---|---|---|---|---|
| M15, production | 2,100 | **2** | RESET_CLOSE ×2 (1 bar) | **−5.01R** | 5.2% |
| M15, protected | 2,100 | 2 | STOPPED ×1, TP1 ×1 | **+0.64R** | 0.4% |
| H1 htf=24, production | 525 | **0** | — | 0.00R | 0% |
| H1 htf=24, protected | 525 | **0** | — | 0.00R | 0% |

M15 trades (both short):

| Trade | Opened | Production exit | Protected exit |
|---|---|---|---|
| CRT-0001 | 2025-07-09 15:45 | reset-close at next bar, **−5.23R** | stopped, −0.38R |
| CRT-0002 | 2025-07-14 11:30 | reset-close at next bar, +0.22R | TP1 at 15:15, +1.02R |

H1 funnel for the month (htf=24): 20 RANGE→SWEEP, 9 →DISPLACEMENT, 3 →EXPANSION, **0 →RETEST**. Resets: 20 HTF rollover, 4 session gap, 7 retrace, 2 extension, 2 sweep expired. Nothing reached entry.

## 4. Reading it
- **M15 reproduces the two-year run's July trades** (same entry timestamps as CRT-0005 and CRT-0006 there). The production exit is again the problem: a reset-close at the next bar's close priced one trade at −5.23R, a large overshoot of its stop. The protected variant gives −0.38R and +1.02R. This is the same mechanism as in the M15 and H1 reports.
- **H1 shows 0 trades in the month.** The two-year H1 run had entries on 07-09 and 07-29, but with a cold start the range boundaries shift and those setups do not form. One month of H1 at daily ranges gives about 3 expansion events and no retest.
- **Statistical content: none.** Two trades and zero trades. The validator's hard gate is 10. These runs only show the mechanics.

## 5. Caveats
- Month chosen for trade availability, not blind.
- Not promotable. No `ConfigValidator` run, and the protected variant is a monkeypatch.
- Controls: re-runs are identical, and the unpatched script reproduces the plain CLI runs exactly for both timeframes.
