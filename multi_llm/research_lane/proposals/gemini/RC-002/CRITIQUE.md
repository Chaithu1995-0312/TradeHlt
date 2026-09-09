# CRITIQUE — discriminating-test design

```yaml
schema_version: "1.0"
package_id: RC-002-CRIT-GEMINI-001
kind: CRITIQUE
cycle_id: RC-002
created_at: 2026-09-04T00:00:00Z
author_role: architect
author_model: gemini
claim_type: process
related_package_ids: [RC-002-CRIT-DEEPSEEK-001, RC-002-PROP-GROK-001]
status: PROPOSED
promise_rung_max_claim: PL-0
```

## 1. Blocking defects: the matched-control problem

The 32 bars are strictly defined by a directional selection rule (`candle_dir != sweep_implied_dir`).
Any metric derived from price direction, close-to-open sign, or directional alignment is
structurally contaminated. Comparing this population's directional behaviour against a global
baseline is circular. Uncontaminated classes:

- **Unsigned forward energy** — maximum absolute excursion in ATRs over k bars, regardless of direction.
- **Time-to-event (duration)** — bars elapsed until the next structural trigger.
- **Volume / participation metrics** — if available in the Phase-1 corpus.

## 2. Candidate test: time-to-next-structural-event

- **Metric:** bars elapsed from the event bar `t` to the next `liquidity_sweep` or `break_of_structure`.
- **Control group:** the 39 CONTINUATION bars that cleared the directional contract and reached occupancy.
- **H0:** the survival distribution for the 32 is identical to that for the 39.
- **Falsifier:** a non-parametric survival comparison (log-rank) fails to reject at alpha = 0.05.

If H0 holds, this population does not alter structural cadence differently from standard
continuation, terminating any claim that it is a distinct unmodelled market state.

## 3. Serial dependence and effective n

2,038 M15 bars (~21 trading days), 203 sweep events (~10/day). Sweeps and structural breaks cluster
in range expansions and liquidity zones, so the 32 are not independent draws.

- **n_eff:** `UNKNOWN:` requires the sweep-event autocorrelation coefficient over the lag window.
  Assuming a conservative design effect of 2, n_eff for the 32 is approximately **15–20**.
- **Required:** to detect a medium effect (d = 0.5) at 80% power needs n_eff ~ 64 per group, i.e.
  roughly **150–200 raw events per group** — expanding from 1 month of M15 to at least **6–8 months**,
  preferably the frozen Phase-1 admitted corpus (47,275 bars).

## 4. Is 89.66% suspicious? No — it is mechanical

`trend_bias` is the sign of `ema_fast` vs `ema_slow`. A sweep triggers when price reaches and
rejects a local HTF extreme. To trigger a high-side sweep, price must push up to that extreme,
which pulls the fast EMA upward and establishes a Bullish `trend_bias`; the high-side sweep itself
carries a bearish implied direction. The sweep's implied direction is therefore structurally forced
to oppose the established EMA trend at the moment of the extreme. **A geometric reality of the
indicators, not an anomaly demanding separate investigation.**

## 5. Recommendation and pre-registration minimum

**REPAIR** — run the duration test on a sufficiently powered corpus before any identity claim.
Minimum pre-registration: (1) target corpus `data/mt5/XAUUSD_M15.csv` (sha `4d73f5ce…`) with explicit
start/end; (2) exact metric `bars_to_next_sweep_or_bos`; (3) control = all magnitude-qualifying,
sweep-held bars passing Gate 0 in that corpus; (4) alpha = 0.05, log-rank; (5) commitment — if the
falsifier triggers, identity remains `UNKNOWN`, logged as structurally indistinguishable from
continuation noise, and **no secondary tests may be fished from the results**.

---

## Executor adjudication (Claude, 2026-09-04)

### §4 mechanism — TESTED, partially confirmed

The claim is checkable against data already on disk, so it was checked. If the sweep candle's push
to the extreme *creates* the opposing `trend_bias`, opposition should be near chance before the
event and high at it.

| `trend_bias` measured at | opposes implied direction |
|---|---|
| `t` (the sweep bar) | 182/203 = **89.66%** |
| `t-1` | 169/203 = **83.25%** |
| `t-2` | 158/203 = **77.83%** |
| `t-3` | 139/203 = **68.47%** |

**Verdict: SUPPORTED but not complete.** The monotone gradient into the event (+21pp from `t-3` to
`t`) is exactly what the EMA-pull mechanism predicts. But opposition is already **68.47%** three
bars out — far above the 50% a purely event-created effect implies — so a pre-existing counter-trend
condition is also present. The two cannot be cleanly separated at these lags, because the approach
to a range extreme itself spans several bars. Either way §4's *conclusion* stands and is
strengthened: **89.66% is structurally determined by how the two constructions interact, not an
independent finding.** Open question (1) of turn 2 is closed.

### §2 test — sound, but it does not answer the question this turn was asked

This turn's prompt asked two things. Effective-n (§3) is answered thoroughly. **The referent
disambiguation was not addressed at all** — `range_h_ref`/`range_l_ref` vs the founding candle's own
extreme vs engine `SWEEP.price` are not mentioned, and neither is whether definition (2) alone can
honestly kill `SAME_SIDE_CONTINUATION_THROUGH_SWEEP`.

The proposed duration test is a *different* test, not an adjudication of the one on the table.
Mapping it against the standing candidates:

| Grok candidate | Does the duration test discriminate it? |
|---|---|
| `NOT_A_DISTINCT_OBJECT` | **Yes** — a null result supports it |
| `INDEPENDENT_IMPULSE_WITH_LIVE_SWEEP` | Partly |
| `SAME_SIDE_CONTINUATION_THROUGH_SWEEP` | **No** — this candidate is geometric |
| `MISPARENTED_DISPLACEMENT` | **No** — untested by duration |
| `UNKNOWN_SWEEP_CHILD_MEMBERSHIP` | n/a (the default) |

So the referent question **remains open** and is carried forward, not merged away.

### §3/§5 corpus recommendation — correct in spirit, with an unstated consequence

Moving to the frozen Phase-1 corpus is a real improvement: it is both larger (47,275 bars) and
**admitted**, where the entire 32-bar analysis to date sits on a non-admitted one-month export.
But Phase-1 ends **2026-05-21** and this investigation's window is **2026-07-07 to 2026-08-06** —
they do **not overlap**. So this is a *different population*, not an extension of the current one:
the 32 bars themselves would not be in it, and the test would be a fresh construction of the same
object on other data. That is arguably better, but it is a replication, not a rescue, and the
package does not say so.
