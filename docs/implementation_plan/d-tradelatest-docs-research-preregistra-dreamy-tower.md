# BC-4 residual attribution — explain the 0.6% gap, then decide if CONFIRMED is reachable

## Context

BC-4b returned `TICK_VOLUME_APPROXIMATE` (F-099): `tick_volume` and
`len(copy_ticks_range(..., COPY_TICKS_ALL))` differ by a consistent **0.548%–0.676%** across
four bars — diffs `45/46/52/31` on volumes `6654/7478/9483/4924`. Not a constant offset, not an
exact ratio, but far too tight to be noise.

The bottleneck is no longer infrastructure. BC-1 is implemented, BC-2 is proven, BC-4a is
enforced. BC-5 (approve/reject the corpus) is now blocked on a single question: **what is that
0.6%?** Approval means "we know what the bytes mean," not "the bytes mostly look right."

So this program does one thing: **attribute the residual**. Not predict it. If it resolves to a
specific counting rule, `TICK_VOLUME_CONFIRMED` becomes reachable under a V2 contract. If it
proves irreducible, `TICK_VOLUME_APPROXIMATE` becomes the permanent, *understood* truth. Both
outcomes close the question; only an unattributed residual leaves BC-5 stuck.

**Authority:** research/evidence. No BC-1/BC-3/BC-5/BC-6, no R3b, no loader work, no Dataset
Identity change, no Parent CRT change, no fetcher rewrite, no production config.

---

## Observation that reshapes the experiment

One of the four candidate explanations is **already largely falsified** by data collected during
BC-4's Phase 0 gate. On the 22:45 bar:

```
tick_volume = 9483    COPY_TICKS_ALL = 9535    COPY_TICKS_INFO = 9535    COPY_TICKS_TRADE = 0
```

`INFO == ALL` exactly; `TRADE` is empty. **There is only one populated tick class**, so the
residual cannot be attributed *across* the three class arguments. The experiment must decompose
*within* the returned stream instead.

The residual can therefore not "collapse to one tick class" — but it may still collapse to one
tick **filter**. That is the open question.

**Governance debt this exposes:** that INFO/TRADE split exists in **no tracked file** — only in
a session transcript. It is real evidence bearing directly on a live question, and unrecorded.
Persisting it is part of this work, not a footnote. (Same silent-gap family as F-079/F-083/F-085,
in its mildest form: a measurement that was *taken* but not *kept*.)

Incidental reproducibility check, worth recording: `ALL = 9535` on the 22:45 bar reproduced
exactly across two separate processes minutes apart.

---

## Design — `BC4-RESIDUAL-ATTRIBUTION-XAUUSD-MT5-V1`

Pre-registered before any raw tick array is inspected.

### Population

Recently-closed M15 bars within the ~60-minute tick-history window (the Phase 0 feasibility
bound from F-099 — deeper `copy_ticks_range` calls hang indefinitely on this terminal, no error,
no return). Discovery: the bars available in one capture. Holdout: bars from a **separate later
capture**, per the approved plan.

### Measurement

For each bar, pull the **raw tick array** (not just `len()`) for `[T, T+15m)` and record every
candidate count below alongside the bar's `tick_volume`. Fields expected on this build
(`time, bid, ask, last, volume, time_msc, flags, volume_real`) — verified at execution as step 1,
because a missing field silently changes what a candidate means.

### Candidate counting rules — FROZEN, no additions after the discovery run

| Id | Rule |
|---|---|
| `C0` | `len(ticks)` — the V1 rule; known to overshoot, kept as the reference |
| `C1` | exclusive upper bound: `time_msc < (T+900)*1000` (tests boundary inclusion) |
| `C2` | `C1` + drop exact duplicates on `(time_msc, bid, ask, last, flags)` |
| `C3` | ticks where `(bid, ask)` differs from the previous tick's `(bid, ask)` — price-changing quotes |
| `C4` | ticks where `flags & (TICK_FLAG_BID \| TICK_FLAG_ASK)` |
| `C5` | ticks where `flags & TICK_FLAG_LAST` |
| `C6` | count of distinct `time_msc` values |
| `C7` | `C1` ∧ `C3` |
| `C8` | `C1` ∧ `C4` |

Leading prior (stated, not assumed): `C3`/`C4` — `tick_volume` counts ticks where the quote
actually moved, while `copy_ticks_range` returns repeats too. ~0.6% repeated quotes on gold is
plausible. The prior does not privilege those candidates in scoring.

**Anti-overfit clause (the load-bearing rule):** the candidate list is frozen above. No candidate
may be added, tuned, or parameterised after seeing discovery output. Exact integer equality is
required — no tolerance band. A rule must match on **every** discovery bar to survive.

### Outcomes

| Outcome | Condition |
|---|---|
| `ATTRIBUTED` | exactly one candidate matches every discovery bar **and** every holdout bar |
| `AMBIGUOUS` | ≥2 candidates survive discovery and the holdout cannot separate them |
| `UNATTRIBUTED` | zero candidates match — the residual is irreducible under this frozen list |

`UNATTRIBUTED` is a real result, not a failure: it promotes `TICK_VOLUME_APPROXIMATE` from
"unexplained gap" to "measured, bounded, and demonstrably not explained by tick class, boundary,
duplication, or flag filtering." That is enough for BC-5 to reason about.

The full candidate×bar table is recorded **regardless of outcome** — it is the evidence, whether
or not anything wins.

### If `ATTRIBUTED` — the V2 re-verdict

A new `MC-...-V2` prereg, following this repo's own F-084 / MC-VCRT-V2 precedent:

1. **Reproduce V1 byte-identically first** (`TICK_VOLUME_APPROXIMATE`, diffs `45/46/52/31`).
   A V2 that cannot reproduce V1 is not a re-measurement.
2. Change **exactly one** named surface: the tick-population definition (`C0` → the winning rule).
3. Everything else — freshness window, `MIN_TEST1_BARS`, thresholds, Test 2, verdict vocabulary —
   unchanged and asserted unchanged.

F-099's `APPROXIMATE` stays true as a statement about the V1-defined comparison and is marked
`SUPERSEDED`, never deleted (§6.2 rule 4).

---

## Files

| Path | Change |
|---|---|
| `docs/research/preregistration-bc4-residual-attribution.md` | New. Population, frozen candidate list, anti-overfit clause, outcome rules, and the unpersisted Phase 0 INFO/TRADE observation recorded as evidence. |
| `src/research/ohlcv_tick_attribution.py` | New. Raw-tick capture + the 9 candidate counters. Reuses `ohlcv_probe_report.py` (`base_report`, `ProbeSnapshot`, `staleness_reason`, `terminal_provenance`, `SOURCE_LIVE` fail-closed) — the emission contract is already proven, do not re-author it. |
| `tests/test_ohlcv_tick_attribution.py` | New. Synthetic: each candidate counts what it claims on hand-built tick arrays; a planted duplicate/boundary/repeat-quote fixture is recovered by the right candidate and missed by the wrong ones; synthetic-cannot-prove holds. |
| `docs/research-readiness/bc4_residual_attribution/` | New. Discovery snapshot, holdout snapshot, `attribution.json` with the full candidate×bar table. |
| `docs/current-findings.md` · `CLAUDE.md` | F-100 on a real outcome (any of the three). Truths Index row. |
| `docs/governance/CORPUS_AUTHORITY.md` | BC-4 block updated only on a real outcome. Expect the freeze-token floor to fire again — re-pin deliberately, do not delete tokens that are still true. |
| `docs/governance/build_manifests/CH-bc4-residual-attribution-v1.impact.json` | New, class `CORPUS_AUTHORITY_CHANGE`. |
| `assistant_project.md` | SESSION LOG entry. |

Only on `ATTRIBUTED`: a V2 prereg + a scoped edit to `ohlcv_volume_semantics.py`'s population
definition, behind the reproduce-V1-first discipline above.

---

## Verification

1. `venv/Scripts/python.exe -m pytest tests/test_ohlcv_tick_attribution.py -q` — every candidate
   on planted fixtures, including negative cases (the wrong candidate must *miss* a planted
   duplicate).
2. `venv/Scripts/python.exe -m pytest tests/test_ohlcv_volume_semantics.py tests/test_ohlcv_open_close_label.py tests/test_dataset_registry.py tests/test_corpus_authority_decisions.py tests/test_xauusd_phase1_frozen_candidate.py tests/test_construction_protocol.py tests/test_ohlcv_clock_provenance.py -q`
   — 111 currently green; BC-2's and BC-4's floors must stay green and their scorers byte-identical
   (`git diff` on both, expected empty).
3. Manual read of `attribution.json`: the candidate×bar table is complete, discovery and holdout
   are from separate captures with separate `fetched_at`, and the declared outcome follows
   mechanically from the frozen rules.

## Operational note

Gold has roughly 40 minutes of session left at time of writing (~23:15 broker, daily break near
23:59). Discovery should land tonight; the holdout may not. **No V2 verdict is issued until the
holdout lands** — if the session closes first, the run reports discovery-only with outcome
`PENDING_HOLDOUT` and stops. That is the honest state, and it is not re-timed or forced.

## Known-pre-existing failures — not this program's, not to be fixed opportunistically

`test_ohlcv_corpus_freeze` (drift on untracked `data/XAUUSD_M15.csv`, modified 2026-08-16 — not
the admitted `data/mt5/` file); `test_session_log` count bound (58 > 30; its suggested
`rotate_session_log.py` is recorded as unsafe on this file); `test_current_findings` residuals
naming only F-096 and stale 2026-08-31/09-01 revalidate-by dates on F-001…F-012.
