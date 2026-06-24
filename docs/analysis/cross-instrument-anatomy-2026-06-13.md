# Cross-Instrument Trade Anatomy — BNB / BTC / ETH / SOL (2026-06-13)

> **Point-in-time study** (history, `docs/analysis/`). Measure-only; extends the BNBUSDT anatomy
> ([`BNBUSDT_TRADE_ANATOMY_2026_06_13.md`](BNBUSDT_TRADE_ANATOMY_2026_06_13.md)) to BTC/ETH/SOL to
> test whether **F-022/F-024** are repository-wide and whether the cost-domination result (existing
> **F-025**) holds across instruments. **No optimization, no tuning.**
>
> **Reproduce:** regenerate `python scripts/research/opportunity_scanner.py --csv data/{INST}_M15.csv
> --instrument {INST} --output-dir logs --run-id anatomy_{INST}_20260613` then
> `python scripts/analysis/bnbusdt_trade_anatomy.py --instrument {INST}` for {BNB,BTC,ETH,SOL}USDT.
> Per-coin substrates: `results/research/{inst}_trade_anatomy/` — **frozen canonical**, each with a
> `README.md` (provenance + sha256 pin) like the BNB substrate. Pins:
> BTC `09baca48…`, ETH `530c9a35…`, SOL `69cdc70e…` (BNB `f8bdabbe…`).

## Provenance — the opportunity streams are TRAILING-STOP ground truth

All four `opportunities.jsonl` come from `scripts/research/opportunity_scanner.py`, which labels
`outcome`/`rr_achieved` under a **0.5R trailing stop** (`trail_mult=0.5`, `sl_atr_mult=1.0`,
`tp_atr_mult=2.0`, `max_forward=40`; `_simulate()` :53). A trailing `SL_HIT` legitimately carries
`rr>0` and `mae > -risk`. The realized layer here is **derived** via the governing
`forward_walk(intrabar_fixed)`; the artifact's own outcome/rr are the flagged `art_*` x-ref.

## Result — every finding replicates, near-identically (139,942 opportunities/coin)

| Coin | art-consistency | artifact SL% | governing SL% / TP% | win-rate | P(next-15m>0) | survival @90m |
|---|---|---|---|---|---|---|
| BNBUSDT | 0.368 | 98.7% | 65.7 / 33.3 | 0.341 | 0.494 | 0.511 |
| BTCUSDT | 0.372 | 98.4% | 65.7 / 32.6 | 0.339 | 0.500 | 0.515 |
| ETHUSDT | 0.370 | 98.2% | 65.7 / 32.9 | 0.340 | 0.500 | 0.522 |
| SOLUSDT | 0.358 | 99.0% | 66.0 / 32.8 | 0.337 | 0.495 | 0.513 |

### F-022 — artifact defect is REPOSITORY-WIDE
Self-consistency clusters at **0.358–0.372** on all four coins; the artifact reads ~98–99% `SL_HIT`
while the governing exit gives ~66% SL / ~33% TP — the **same** structure everywhere. This is the
expected signature of one shared generator with a trailing-stop model, **not** per-coin corruption.
⇒ F-022 broadens from a BNB note to a **repository-wide** truth, with the mechanism named
(trailing-stop ground-truth ≠ governing fixed-stop; reading its labels as fixed-stop results is the error).

### F-024 — timing asymmetry REPLICATES (within-trade peak)
| Coin | winners p50 / p90 | losers p50 / p90 |
|---|---|---|
| BNBUSDT | 6 / 18 | 1 / 6 |
| BTCUSDT | 6 / 19 | 1 / 6 |
| ETHUSDT | 6 / 19 | 1 / 6 |
| SOLUSDT | 6 / 18 | 1 / 6 |

Identical on all four: **losers resolve almost immediately (median 1 bar), winners mature over ~90 min
(median 6 bars, p90 ~18).** Descriptive and partly mechanical (coupled to survival/duration), now
cross-instrument robust. (The exit-agnostic `bars_to_peak_path` remains random-walk/uninformative on all coins.)

### Cost-domination — CORROBORATES existing F-025 (exit-grid)
Fixed-time-exit expectancy (mean R), gross → net 12 bps, at 15m & 90m:

| Coin | 15m gross→net | 90m gross→net |
|---|---|---|
| BNBUSDT | −0.000 → −0.428 | +0.000 → −0.428 |
| BTCUSDT | +0.000 → −0.520 | −0.000 → −0.520 |
| ETHUSDT | −0.000 → −0.327 | −0.000 → −0.327 |
| SOLUSDT | +0.000 → −0.251 | +0.000 → −0.251 |

**Gross ≈ 0 at every coin and horizon; net < 0 everywhere** — economics are **cost-dominated, not
signal-dominated**, exactly the conclusion the existing **F-025** (exit/cost is a risk/cost lever,
not expectancy) already owns. The per-coin net magnitude differs (BTC −0.52 worst, SOL −0.25 best)
because cost-in-R = `0.0012 · entry / ATR`: BTC's low ATR/price ratio makes the same 12 bps a larger
R-fraction. This is **not a new finding** — it is cross-instrument corroboration of F-025.

## Conclusion

The BNBUSDT anatomy was not idiosyncratic. Across BNB/BTC/ETH/SOL the detection-stream artifact
defect (F-022), the win/loss timing asymmetry (F-024), the morphology-≠-expectancy result (F-023, by
construction of the same pipeline), and the cost-domination of a neutral gross edge (F-025) all hold.
Standing redirect is unchanged: the bottleneck is **entry information**, not exits — Phase D / the
next research **program**, not a parameter pass on these majors.
