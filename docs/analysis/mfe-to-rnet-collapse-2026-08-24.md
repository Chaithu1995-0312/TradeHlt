# Why +0.21R extra path becomes +0.025R of y_R_net (2026-08-24)

> Point-in-time. Same sealed split as SEM-028 / SEM-029 / MC-ASYM.
> Artifact: `docs/research-readiness/rnet_overlay/mc_rnet_overlay_xauusd_m15_v1/collapse.json`.
> Not a new PRIMARY. No G001.

Two different y's on the same `(decision_ts, side)` rows:

| y | What it is | Extra on agree (holdout) |
|---|---|---:|
| `y_mfe_r` | exit-agnostic 40-bar horizon excursion | **+0.209R** |
| `path_mfe_r` | MFE **while the unit-TP walk is still open** | **+0.035R** |
| `y_R_net` | `rr_achieved − 12bps` of that walk | **+0.026R** |

`tp1_reward_mult` is **exactly 2.0** on every row. Mean horizon MFE is ~4R. Mean walk-bounded MFE is ~1.3R.

## The chain (holdout n=18,906)

```
horizon MFE contrast     +0.209
        │
        │  −0.174   (83%)   path printed after the walk already exited
        ▼
walk-bounded MFE         +0.035
        │
        │  −0.009           discrete R / TP cap / cost
        ▼
y_R_net contrast         +0.026
```

Train is the same shape: +0.265 → +0.042 → +0.023. **83% / 84% of the extra path is post-exit.**

That leftover +0.026R of booked R is **not fatter R given the same outcome**. Mix vs within-outcome on holdout:

| Component | Holdout |
|---|---:|
| Outcome-mix (a bit more TP_HIT, a bit less SL_HIT) | **+0.025** |
| Within-outcome E[R] | **+0.0005** |

TP_HIT rate: 0.332 agree vs 0.321 disagree (**+1.1 pp**). Once the walk has an outcome, booked R barely moves.

## Where the extra MFE sits

Holdout, by walk outcome:

| Outcome | P(agree) | P(disagree) | horizon MFE Δ | walk MFE Δ | R-net Δ |
|---|---:|---:|---:|---:|---:|
| SL_HIT | 0.661 | 0.668 | **+0.156** | +0.009 | −0.008 |
| TP_HIT | 0.332 | 0.321 | **+0.209** | +0.036 | +0.020 |
| TIMEOUT | 0.007 | 0.011 | −0.070 | −0.070 | −0.097 |

On SL_HIT the agreeing side still prints +0.16R more *horizon* MFE, then gives it back into the stop. Walk-bounded MFE is almost identical. High-MFE + high-MAE (atlas 60%) is the typical path.

Leak ladder, holdout — the 2R-missed-TP cell is the dump:

| Bucket | P(agree) | P(disagree) | MFE Δ | R-net Δ |
|---|---:|---:|---:|---:|
| TP captured | 0.332 | 0.321 | +0.209 | +0.020 |
| Reached 2R, missed TP | 0.280 | 0.289 | **+0.501** | **+0.006** |
| Reached 1R not 2R, missed TP | 0.180 | 0.191 | −0.026 | −0.063 |

Unit TP **is** 2R on this corpus. A 2R horizon print that is not `y_tp1` is SL-first / same-bar disagreement (F-088), not a mistuned target. That is where the extra path concentrates, and the walk books none of it.

## What this is not

- Cost. 12bps is in the **level** (E[y]≈−0.55). It does not eat the contrast: walk-MFE → R-net only drops 0.009R of contrast.
- A side picker. TP-hit moves 1.1 pp; that is the whole booked residual.
- A reason to widen TP to harvest the extra 0.21R. That would be a new object, a new `MC-*`, and F-087 already said the exit cannot create expectancy the entry lacked. This measurement says the extra path is mostly **after the current trade is dead**, not sitting unused in an open trade.

Mechanism: **horizon excursion is not the trade.** The walk exits; the extra path keeps printing; booked R is a 2R/−1R stamp plus a 1 pp mix shift.
