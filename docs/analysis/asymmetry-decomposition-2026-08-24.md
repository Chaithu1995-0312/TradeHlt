# Asymmetry decomposition — what actually changes directional opportunity (2026-08-24)

> Point-in-time. Object: `docs/research/asymmetry_object.md` (SEM-027).
> Split: sealed `MC-ASYM-XAUUSD-M15-V1` (F-091). PRIMARY not retuned.
> Artifact: `docs/research-readiness/asymmetry/mc_asym_xauusd_m15_v1/decomposition.json`
> Two-way: `…/decomposition_twoway.json`.
> Grain: paired timestamp ΔMFE = `y_mfe_r(long) − y_mfe_r(short)`. Not a trade. No G001.

**Change class:** DOCUMENTATION_ONLY (`CH-asymmetry-decomp-v1`). Diagnostic cells only.

## The object

```
trend_bias=+1  →  E[Δ] = +0.440    n=26,411
trend_bias=−1  →  E[Δ] = −0.017    n=20,752
```

Those are **full-sample** cells (mixed windows). They are the first thing to attack **because the sign agrees with subsequent directional opportunity**, not because the spread is the largest.

Largest E[Δ] spread is hour / session / vol. That ranking is the wrong object.

## Channel test

`E[Δ] = P(Δ>0)·E[Δ|Δ>0] + P(Δ<0)·E[Δ|Δ<0]`

| Cell | n | mean | median | P(Δ>0) | E[Δ\|Δ>0] | E[Δ\|Δ<0] | E[\|Δ\|] |
|---|---:|---:|---:|---:|---:|---:|---:|
| uncond (full) | 47,166 | +0.239 | +0.408 | 0.531 | +4.578 | −4.674 | 4.622 |
| trend_bias=+1 | 26,411 | **+0.440** | +0.518 | **0.539** | **+4.810** | −4.678 | 4.747 |
| trend_bias=−1 | 20,752 | **−0.017** | +0.277 | **0.520** | **+4.273** | −4.669 | 4.462 |

Hit-rate barely moves (**+1.9 pp**). Short-win magnitude is **identical** (−4.678 vs −4.669). Long-win magnitude moves **+0.54R**. Unsigned |Δ| spread is only 0.28.

```
State  →  how large the agreeing-side excursion is
not
State  →  which side wins
```

A side-classifier on `trend_bias` is the wrong consumer. The information is a **magnitude amplifier on the agreeing path**.

Holdout (both cells go negative; contrast keeps sign — F-091):

| Cell | n | mean | P(Δ>0) | E[Δ\|Δ>0] | E[Δ\|Δ<0] |
|---|---:|---:|---:|---:|---:|
| uncond | 9,454 | −0.546 | 0.489 | +4.278 | −5.157 |
| trend_bias=+1 | 4,942 | −0.322 | 0.496 | +4.537 | −5.111 |
| trend_bias=−1 | 4,511 | −0.791 | 0.480 | +3.984 | −5.205 |

Same shape: P moves 1.6 pp; E[Δ|Δ<0] almost flat; E[Δ|Δ>0] still +0.55R larger on `+1`. Relative information is not “gold goes up.”

## Family rank — two ladders

### A. Naive: spread of E[Δ] (full sample)

| Rank | Family | spread E[Δ] | spread P(Δ>0) | spread E[\|Δ\|] | contrast |
|---:|---|---:|---:|---:|---:|
| 1 | hour | 0.923 | 0.083 | **3.654** | — |
| 2 | session | 0.774 | 0.043 | **2.527** | — |
| 3 | volatility_regime | 0.615 | 0.015 | **2.627** | — |
| 4 | **trend_bias** | 0.457 | **0.019** | 0.285 | **+0.457** |
| 5 | BOS | 0.230 | 0.010 | 0.065 | +0.230 |
| 6 | higher_high | 0.187 | 0.009 | 0.155 | +0.187 |
| 7 | double_sweep | 0.177 | 0.015 | 0.573 | −0.177 |
| 8 | lower_low | 0.160 | 0.016 | 0.229 | −0.160 |
| 9 | volume_spike | 0.159 | 0.013 | 0.403 | −0.159 |
| 10 | sweep | 0.053 | 0.006 | 0.417 | −0.053 |
| 11 | liquidity_sweep | 0.008 | 0.002 | 0.284 | −0.008 |

Hour / session / vol move **unsigned path size** (London vs Asia range; high vs low vol). That is “how much move exists” in the tautological sense. F-066 still contaminates hour/session. Hour 0 is absent (F-080: engine day opens 01:00).

### B. Directional opportunity (what to attack)

A family earns this ladder only if (1) the cell **sign agrees** with subsequent ΔMFE, (2) the **contrast keeps sign on holdout**, (3) the move is in E[Δ|Δ>0] not P(Δ>0), (4) it is not nested in another family.

| Rank | Family | Why |
|---|---|---|
| 1 | **trend_bias** | Sign agrees. Contrast +0.415 train / +0.469 holdout (F-091). P-stable. E[Δ\|Δ<0] invariant. Not nested. |
| — | hour, session | Largest spread, **clock-contaminated** (F-066), OUT OF PATH for PRIMARY. |
| — | volatility_regime | Large spread, **ranking flips** on holdout (vol=0 train +1.008 → holdout −0.939). Magnitude, not direction. |
| — | BOS, higher_high | Marginal lift is almost entirely nested in `trend_bias=+1`. |
| — | sweep / double_sweep / volume_spike / liquidity_sweep | Near-zero or wrong-signed. Sweep present is **below** uncond on the full sample. |

Do not retune PRIMARY to hour, session, vol, or BOS after seeing y. That is the SEM-027 kill.

## Powered cells (full sample)

n, mean, median, P(Δ>0) — the four numbers asked. Excess vs uncond +0.239.

| State | n | mean | median | P(Δ>0) | excess |
|---|---:|---:|---:|---:|---:|
| trend_bias=+1 | 26,411 | +0.440 | +0.518 | 0.539 | +0.201 |
| trend_bias=−1 | 20,752 | −0.017 | +0.277 | 0.520 | −0.256 |
| vol=0 | 15,914 | +0.597 | +0.755 | 0.537 | +0.358 |
| vol=1 | 14,652 | +0.140 | +0.339 | 0.523 | −0.099 |
| vol=2 | 16,600 | −0.017 | +0.301 | 0.532 | −0.256 |
| session=4 | 5,995 | +0.684 | +0.607 | 0.544 | +0.445 |
| session=0 | 12,341 | +0.334 | +0.474 | 0.532 | +0.095 |
| session=2 | 10,290 | +0.248 | +0.395 | 0.547 | +0.009 |
| session=1 | 10,300 | +0.119 | +0.469 | 0.527 | −0.120 |
| session=3 | 8,240 | −0.090 | +0.085 | 0.504 | −0.329 |
| BOS present | 10,920 | +0.416 | +0.501 | 0.539 | +0.177 |
| BOS absent | 36,246 | +0.185 | +0.380 | 0.528 | −0.054 |
| sweep present | 7,540 | +0.194 | +0.398 | 0.526 | −0.044 |
| sweep absent | 39,626 | +0.247 | +0.409 | 0.532 | +0.008 |
| double_sweep present | 3,049 | +0.073 | +0.293 | 0.517 | −0.166 |
| volume_spike present | 12,279 | +0.121 | +0.314 | 0.521 | −0.118 |
| hour=23 | 1,987 | +0.822 | +0.616 | 0.535 | +0.583 |
| hour=8 | 2,060 | +0.211 | +0.725 | 0.539 | −0.028 |

Hour=8 is the **state-value** high-MFE hour (E[MFE]=5.30 on the both-sides atlas) and is **near-zero on ΔMFE**. Unsigned opportunity ≠ directional opportunity.

## Two-way: BOS is not a second object

Full sample, BOS present is 9,472 / 10,920 = **87%** `trend_bias=+1`.

| Cell | n | mean | P(Δ>0) |
|---|---:|---:|---:|
| +1, BOS absent | 16,939 | +0.434 | 0.539 |
| +1, BOS present | 9,472 | +0.450 | 0.540 |
| −1, BOS absent | 19,304 | −0.032 | 0.520 |
| −1, BOS present | 1,448 | +0.191 | 0.528 |

Conditional on `trend_bias=+1`, BOS adds **+0.016**. The atlas “BOS present +0.416” is mostly “BOS fires when trend is already +1.” Same shape for `higher_high`.

Vol is **not** nested — both trend signs exist in every regime — and the vol=0 cell **flips sign** on holdout even inside `trend_bias=+1` (train +1.071 → holdout −1.140). Do not attack vol for direction.

## What this is not

- A trade, a gate, G001, or authority to promote `trend_bias`.
- A retune of SEM-027 PRIMARY.
- A claim that hour/session are useless — they move **unsigned** path size, which is a different consumer.
- F-086 stride (unspent).

Attack ranking: **trend_bias as a magnitude prior on the agreeing path**, not as a side picker, not as a replacement PRIMARY. A tradable consumer is a new object and a new `MC-*`.
