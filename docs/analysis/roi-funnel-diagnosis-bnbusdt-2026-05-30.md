# ROI Funnel Diagnosis — BNBUSDT M15 (2026-05-30)

> **Point-in-time snapshot, not a living doc.** Captures the binding-constraint diagnosis
> for trade frequency, produced by the Phase 6b funnel telemetry (Step 1). For current
> truth re-run the backtest. Authoritative knobs live in `configs/production/*.json`.

## Why this matters

The ROI baseline (+4.91% / 2 yr) is throttled primarily by **frequency** (15 trades / 2 yr).
`ROI ≈ N × R̄ × risk%`, so finding *where candidate trades die* is the highest-leverage
question. Phase 6b Step 1 added funnel transition-count telemetry to answer it.

## Funnel (BNBUSDT M15, 70,080 candles, active config)

| Stage | Entries | Conv from prev |
|---|---:|---:|
| RANGE | 16,187 | — |
| SWEEP | 4,816 | 29.8% |
| DISPLACEMENT | 1,103 | 22.9% |
| EXPANSION | 202 | 18.3% |
| RETEST | 134 | 66.3% |
| **EXECUTION** | **15** | **11.2%** ◄ binding |
| RESOLUTION | 15 | 100% |

**RETEST→EXECUTION at 11.2% is the binding constraint** — 134 setups reach retest, only 15
become trades. 119 scored, structurally-valid candidates are lost here.

## Where the 119 die (root cause)

Two layers gate RETEST→EXECUTION. The telemetry decomposes them:

**1. Score gate (`tier_2_threshold = 0.3`) — NOT binding.**
`DECISION_DISTANCE` records: 134 of 135 soft-confirmations **APPROVED** (mean score 0.496,
only 1 rejected `score_below_threshold`). Sweeping `tier_2_threshold` would do almost nothing.

**2. Post-score filters — THE binding constraint.** 93 `FILTER_REJECTED` events:

| Reason | Count | % of filter rejects |
|---|---:|---:|
| `off_session:OFF_SESSION` | 44 | 47% |
| `off_session:ASIA` | 20 | 22% |
| Not in discount zone | 16 | 17% |
| Not in premium zone | 13 | 14% |

**64 of 93 (69%) are session filters.** The system trades only LONDON (07:00–10:00) and
NEWYORK (13:00–16:00) UTC — **9 of 24 hours**. ASIA (00:00–03:00) is *defined* in
`crt_engine.session_windows` but *excluded* from `engine_runner.allowed_sessions =
['london','new_york','overlap']`. So:
- 44 retests fall in uncovered hours (03–07, 10–13, 16–24) → `OFF_SESSION`.
- 20 retests fall in the defined ASIA window but are blocked → `ASIA`.

The remaining 29 are zone filters (entry on wrong side of range mid).

## Actionable conclusion

The single biggest frequency lever is **the session filter**, a config-only knob:
- Adding `asia` to `allowed_sessions` recovers up to **20** candidate retests.
- Widening session windows (or adding more) recovers up to **44** `OFF_SESSION` retests.

This **invalidates the original Step 2 plan** (sweep detection thresholds `body_ratio_min`,
`atr_multiplier_min`, etc.). Those govern the *early* funnel (SWEEP→DISPLACEMENT→EXPANSION),
which is not the binding constraint — the early funnel already delivers 134 retests.

## Caveats before acting (governance)

- Session expansion is a **config change requiring promotion** through `ConfigValidator`
  hard/soft gates. ASIA/off-session trades must be validated for edge — they may have
  worse WR or higher cost drag than LONDON/NEWYORK. Measure before promoting.
- Determinism preserved: this diagnosis is post-hoc telemetry on the existing deterministic
  run. ROI/trade-count identical to baseline (+4.91%, 15 trades) — confirms additive-only.

## Revised next step

Run a **session-window sweep** (not a detection-threshold sweep): backtest with ASIA added
to `allowed_sessions`, then with widened windows, comparing trade count, WR, avg RR, ROI,
and max-DD per session. Promote only if added sessions hold expectancy ≥ baseline.
This supersedes the frequency-boost detection sweep in the Phase 6b plan.
