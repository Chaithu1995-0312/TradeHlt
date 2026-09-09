# CRT Trace Workflow — SURVEY → LOCATE → PROVE

A repeatable, observe-only method for finding and *proving* defects in the CRT decision flow.
Written to be followed with no memory of the session that produced it.

```bash
venv/Scripts/python.exe scripts/analysis/run_crt_trace_workflow.py --instrument EURUSD
```

Everything here is **descriptive**. It explains engine behavior and surfaces defects. It grants
no authority to change the SL rule, session windows, the RETEST acceptance rule, or any config.
Anything found that warrants a behavior change is a separate, separately authorized decision.

---

## The three stages

| Stage | Script | Question it answers | Stop when |
|---|---|---|---|
| **1. SURVEY** | `xauusd_excel_feature_state_trace.py` | What happened, bar by bar? OHLC → 39 canonical features → CRT state | You know how many setups formed and roughly where they ended |
| **2. LOCATE** | `session_filter_funnel_probe.py` | Which gate kills them, and what would change that? Gate funnel × counterfactual arms | You know the binding gate and whether it is the *only* one |
| **3. PROVE** | `crt_episode_number_trace.py` | Exactly which numbers produced that outcome? Provenance-classed operands + engine parity | The arithmetic reproduces the engine's own value |

Run them in order. Stage 2 without stage 1 measures something you cannot picture; stage 3 without
stage 2 proves a number nobody asked about.

---

## Rule 1 — debug on the SMALL corpus

The 2-year corpus (47,275 bars) **hid two instrumentation defects**. The 17-day corpus
(1,195 bars, 2 RETESTs) exposed both in a single run, because with n=2 you can check every
decision by hand.

Use the large corpus **only** to put rates on a mechanism the small corpus has already explained.
"How often?" is a large-corpus question. "Why?" is a small-corpus question. Asking "why" of 47k
bars produces aggregates that look like answers and aren't.

---

## Rule 2 — an assert that cannot fail is worse than none

It manufactures confidence while the output is wrong. This happened **twice** in one session:

**Vacuous assert #1.** The funnel defined `reached_session = session_rejected + session_passed`,
then asserted that identity held. Tautological — it could never fail. It was hiding a real
blind spot: session passes were counted only on `TRADE_OPENED`, so setups that passed session and
then died in `build_trade` (which emits neither a rejection nor an open) vanished from the funnel
entirely. Reported as "3 of 17 RETESTs unaccounted, probably a soft-conf timeout" — wrong; they
were dropped by the counter.

**Vacuous assert #2.** Guarding DERIVED/ENGINE separation with
`if "sl_engine" in names: assert "sl_trace" in names`. False exactly when the ENGINE row was
missing, which is the bug it was written to catch. And it *was* missing: a `dict()` copy of the
geometry was taken before the parity loop attached the engine values, so all four reports
rendered an empty parity block while the internal assert logged "passed".

**The fix, and the standing rule:** phrase asserts as *positive requirements over a known set*
("every inverted-SL episode must have both rows"), not as conditionals on the thing that might be
absent. And ship every parity-style assert with a **three-state demo**:

```
normal    → PASS
perturbed → FAIL     (e.g. multiply the recomputed value by 1.001)
restored  → PASS
```

If you cannot make it fail, it is not protecting anything.

---

## Rule 3 — provenance on every number

Six classes. Every displayed value carries one; a missing class is an **instrumentation error**,
not an incomplete display, so the constructor raises.

| class | meaning |
|---|---|
| `OHLC` | raw candle field, with bar timestamp |
| `FEATURE` | FeaturePipeline output, with FM id |
| `STATE` | `EngineState` field, **with the bar whose value it is** |
| `CONFIG` | `CRTConfig` field, with the key path |
| `DERIVED` | arithmetic performed by the script |
| `ENGINE` | value the engine itself emitted |

**Never collapse `DERIVED` and `ENGINE`, even when they agree.** `sl_engine = 4148.66243` and
`sl_trace = 4148.6624286` are different epistemic objects that happen to share a value; showing
one in place of the other destroys the evidence the parity check creates.

**Name the bar, not just the field.** The SL uses `state.atr_abs` from the **soft-confirmation**
bar, not the RETEST bar. On 2026-07-22 those were `9.562143` and `10.473571`. Substituting the
visually-closest one reproduces neither the engine's SL nor its rejection.

### Epistemic ladder

`OBSERVED` > `DERIVED` > `INFERRED_BY_ORDER`.

The error this prevents: calling something observed when it was only inferred from control flow.
A session **rejection** is `OBSERVED` — the engine emits the reason and `session_name`. A session
**pass** is `INFERRED_BY_ORDER` — nothing is emitted; it is known only because `build_trade` was
subsequently called. Never render the second as the first.

---

## Rule 4 — pre-register predictions

Hand-compute the expected outcome of every arm *before* running. A run that confirms four
predicted cells is evidence; a run you read afterwards is a lookup.

Worked example — the four session arms, computed from the windows and the clock by hand:

| Arm | 19:15 → 16:15 UTC | 05:45 → 02:45 UTC | predicted | actual |
|---|---|---|---|---|
| A0 broker clock | OFF_SESSION | OFF_SESSION | 0 passes | 0 ✓ |
| A1 utc clock | OFF_SESSION (misses NY by 15 min) | ASIA — not allowed | 0, reason flips to `ASIA` | ✓ |
| A2 +ASIA allowed | OFF_SESSION | OFF_SESSION | 0, identical to A0 | ✓ |
| A3 utc + wide windows | NEWYORK | ASIA | 2 passes | 2 ✓ |

4/4. That is what makes the arm machinery trustworthy enough to believe on a corpus you *can't*
check by hand.

---

## Rule 5 — the failure-mode checklist

Run this against any new probe before trusting its output:

1. **Does every assert have an input that would make it fail?** If not, delete it or fix it.
2. **Am I recomputing something the engine already emits?** Prefer capturing. If recomputation is
   unavoidable, assert against the engine's own output (a log handler works).
3. **Does my counterfactual override a field something *else* also reads?**
   `session_windows` also feeds `UltronRiskEngine.score_time` → `RiskScore.time_score` → `final_S`
   (`crt_engine_v2.py:1837-1844`). So arm A3 raises the score as well as opening the gate — it is
   not a clean session-only counterfactual. Grep every reader of a field before overriding it.
4. **Am I snapshotting after a reset that already cleared the state?** `reset_to_range` wipes
   `retest_candle` / `displacement_candle` / `sweep_event`. Snapshot inside the `ev_log.record`
   wrapper, which fires *before* the reset.
5. **Copy or reference?** `dict(x)` strands the stored object from later enrichment.
6. **Is a "0 results" outcome real, or is my terminal-detection missing a silent path?**
   A `build_trade` failure leaves `action="NONE"` — keying on terminal action names alone finds
   zero episodes and looks like a clean run.

---

## Reading the output

`INDEX.md` is the entry point for a run. Then:

- **Preflight** — bar count, window, resolved config, and any **dead tokens** (an entry in
  `allowed_sessions` with no matching `session_windows` key can never match; `OVERLAP` is one).
- **Stage 1** `trace.csv` — one row per bar: OHLC, 39 features, state before/after, action.
  Warmup cells are **empty, never zero-filled** — `warmup_complete` tells you which.
- **Stage 2** `funnel.csv` (per-gate counts per arm), `rejections.csv`, `hour_profile.csv`
  (when setups occur vs when they are allowed), `events.csv` (per-RETEST detail).
- **Stage 3** `journeys.md` (the causal ladder per arm), `proof_*.md` (the evidence chain),
  `operands.csv` (every number with its class), `bars.csv`.

### Known-good regression values (XAUUSD, 17-day corpus)

Use these to check the workflow still behaves after any change:

```
bars 1,195 · RETESTs 2
A0 passed=0 build_failed=0 trades=0
A1 passed=0 build_failed=0 trades=0
A2 passed=0 build_failed=0 trades=0
A3 passed=2 build_failed=2 trades=0
parity A3 2026-07-22 19:15  |delta|=1.429e-06 PASS
parity A3 2026-07-28 05:45  |delta|=4.286e-06 PASS
```

---

## What one pass already found

Not a claim that these are fixed — they are what the method surfaced on its first run:

1. **`OVERLAP` is a dead token** — in `allowed_sessions`, absent from `session_windows`, so no bar
   can ever carry that label. **Repo-wide**: all six MT5 instruments resolve to identical config.
2. **The session windows cover 6 of 23 hours**, and CRT activity is anti-correlated with them.
3. **The windows are commented UTC but compared against broker time** (`session_timestamp_basis`
   defaults to `broker_local`). F-066 records this was deliberate; the arms measure what a
   correction *would* do without asserting it should happen.
4. **A second binding gate sat behind the first** — inverted SL in `build_trade`. On the 2-year
   corpus, arm A3 passes all 17 RETESTs at the session gate and still loses 6 of them here.
   Opening a gate does not create a trade; it exposes the next gate.

---

## Cross-instrument caveat

All MT5 instruments (XAUUSD, EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD) currently resolve to the
**same** CRT config — same `allowed_sessions`, `sl_atr_buffer`, `body_ratio_min`. A
cross-instrument run therefore varies **data only**. It is not a config comparison, and any
config-level defect it finds is repo-wide rather than instrument-specific. Preflight prints this
on every run so the distinction cannot quietly be lost.
