# Evidence atlases — leakage, state value, asymmetry (2026-08-24)

> Point-in-time. Spec: `docs/research/parquet_evidence_layer.md`.
> Artifact: `results/research/parquet_evidence_layer/atlases.json`.
> Grain: 94,332 = 47,166 timestamps × 2 sides. Not CRT `TRADE_OPENED`.
> No F-id. No G001. Path-conditioned rates are not t=0 policies.

**Change:** `CH-evidence-atlases`.

## 1. Opportunity leakage atlas

Nested modes (overlap allowed):

| Mode | n | rate |
|---|---:|---:|
| Reached 0.5R, missed unit TP | 54,157 | 0.574 |
| Reached 1R, missed unit TP | 44,858 | 0.476 |
| Reached 2R, missed unit TP | 28,007 | 0.297 |
| High MFE (≥1R) and high MAE (≥1R) | 56,664 | 0.601 |
| Low MAE (<0.5R) and failed TP | 498 | 0.005 |

Exclusive missed-TP ladder (sums to 94,332):

| Bucket | n | rate |
|---|---:|---:|
| TP captured | 30,525 | 0.324 |
| Reached 2R, missed TP | 28,007 | 0.297 |
| Reached 1R not 2R, missed TP | 16,851 | 0.179 |
| Reached 0.5R not 1R, missed TP | 9,299 | 0.099 |
| Missed TP, never 0.5R | 9,650 | 0.102 |

The 2R-missed-TP cell is the sharp leak: unit TP **is** 2R geometry on this corpus (`tp1_reward_mult` frozen at 2.0), so a 2R horizon print that is not `y_tp1` is SL-first / same-bar path disagreement (F-088 class), not a mistuned target. High-MFE+high-MAE is the typical two-sided path (60%). Clean “failed without heat” is rare (0.5%).

## 2. State value surface (not win rate)

CRT engine states are **not** on this grain. Discrete columns already on the ledger: session, volatility, hour, trend_bias, side, ontology flags.

On a both-sides ledger, **long MFE ≈ short MAE** at the same timestamp. So for any state shared by both sides, `E[MFE] ≈ E[MAE]` and `path_net ≈ 0` **by construction**. That is not “states have no value.” Opportunity **magnitude** and **speed** still move:

| State | n | E[MFE] | E[time to MFE] | E[TP1] | E[TP2] |
|---|---:|---:|---:|---:|---:|
| hour=8 | 4,120 | 5.30 | 3.07 | 0.347 | 0.251 |
| hour=18 | 4,120 | 2.17 | 9.40 | 0.268 | 0.154 |
| session=1 | 20,600 | 4.76 | 3.86 | 0.337 | 0.247 |
| session=2 | 20,580 | 2.57 | 7.56 | 0.298 | 0.187 |
| vol=0 | 31,828 | 4.99 | 3.55 | 0.334 | 0.251 |
| vol=2 | 33,200 | 2.80 | 6.79 | 0.307 | 0.201 |
| side=long | 47,166 | 4.03 | 5.36 | 0.341 | 0.246 |
| side=short | 47,166 | 3.80 | 4.58 | 0.306 | 0.216 |

`E[MFE]` spread: hour 3.13, session 2.20, volatility 2.19. Ontology flags move E[MFE] by 0.06–0.37. Hour/session carry F-066 broker-clock.

Side is the only cell where `path_net` is not zero: long +0.239, short −0.239 (the same number as unconditional long−short MFE).

## 3. Asymmetry atlas — Long MFE − Short MFE at the same timestamp

Paired timestamps n=47,166 (complete).

Unconditional: **E[MFE_L − MFE_S] = +0.239**, median +0.408, P(Δ>0)=0.531. That is gold’s long-side path bias on this horizon, not a model.

State-conditional **excess vs +0.239** (directional association in the t=0 column):

| State | n | E[ΔMFE] | excess |
|---|---:|---:|---:|
| session=4 | 5,995 | +0.684 | +0.445 |
| session=3 | 8,240 | −0.090 | −0.329 |
| vol=0 | 15,914 | +0.597 | +0.358 |
| vol=2 | 16,600 | −0.017 | −0.256 |
| hour=23 | 1,987 | +0.822 | +0.583 |
| trend_bias=+1 | 26,411 | +0.440 | +0.201 |
| trend_bias=−1 | 20,752 | −0.017 | −0.256 |
| BOS present | 10,920 | +0.416 | +0.177 |
| sweep present | 7,540 | +0.194 | −0.044 |

Hour spread 0.92 (F-066). Session spread 0.77. Volatility 0.61. trend_bias 0.46 — the feature’s sign agrees with subsequent long-vs-short MFE in **magnitude**, while P(Δ>0) only moves 0.539 vs 0.520.

That is directional **information** in the state. It is not expectancy, not a gate, not G001.

## Candidate findings (not registered)

1. Leakage is mostly “the path printed 1–2R and the 2R walk still lost,” not “never went anywhere.”
2. State value on this grain is path **size and speed**, not path_net, except through `side`.
3. Same-timestamp long−short MFE is the directional object this corpus actually supports. Session / vol / hour / trend_bias move E[ΔMFE]. Ontology sweep barely does.

No production. `y_R_net` still 12bps.
