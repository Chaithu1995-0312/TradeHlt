# FeatureState census (2026-09-16)

Point-in-time. **Not a finding.** Same corpus as F-106 / H1 ReportWriter `run_20260915_224051`.
Source run ids (one run, F-101): logging `20260915_223437`; ReportWriter `run_20260915_224051`; config-dump UTC `run_20260915_171051` (= 22:40:51 local at +5:30).

Encoder: `FeatureStateEncoder` — shadow-only; spine does not consume it. 13 vector-bound identities classified; 0 `X_` markers. Non-vector states (`rsi_state`, flags, magnitude bands) not invented from the vector.

## Structural relations

`liquidity_sweep` refines `sweep_detected`: NoSweep counts identical; SweepDetected = BuySide ∪ SellSide exactly.

| Layer | NoSweep | Directional | Total |
|---|---:|---:|---:|
| `sweep_detected` | 39,655 | 7,542 | 47,197 |
| `liquidity_sweep` | 39,655 | Buy 3,969 + Sell 3,573 = 7,542 | 47,197 |

On engine SWEEP (n=1,792): NoSweep 865; Buy 490 + Sell 437 = 927 = SweepDetected. 865+490+437 = 1,792.

`trend_bias` on engine SWEEP is fully directional: Bullish 1,025 / Bearish 767 / **Neutral 0** (all-corpus Neutral = 3).

## Engine SWEEP ≠ FeatureState `sweep_detected`

Overlap: **927 / 1,792 = 51.7%**. Do not extend F-106 random-parity to FeatureState sweep.

## Two session objects (same 1,792 engine-SWEEP bars)

| Taxonomy | Split |
|---|---|
| CRT filter (F-106) | ASIA 175 · LONDON 246 · NEWYORK 297 · OFF_SESSION 1,074 |
| FM-052 | ASIA 531 · LONDON 405 · OVERLAP 369 · NY 340 · CLOSED 147 |

F-106 used CRT filter hours, not FM-052. CLOSED carries 147 engine-SWEEP bars (8.2%) under `broker_local` (F-066).

## Incidental (not claims)

- `volume_spike` Spike: 26.0% all bars vs 43.3% on engine SWEEP (777/1,792).
- Gitignored machine copy: `results/run_20260915_224051_XAUUSD/feature_state_census.json` (`/results/*` is gitignored; this note is the tracked census).
