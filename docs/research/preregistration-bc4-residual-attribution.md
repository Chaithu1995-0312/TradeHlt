# Pre-Registration — BC-4 residual attribution

> **Status:** PRE-REGISTERED. The candidate list below was frozen in the user-approved plan
> **before** any raw tick array existed, and this document was written before any candidate
> output was inspected. The discovery capture was taken first only because the trading session
> was closing; capture is not scoring.
> **Lane:** measurement / evidence.
> **Authority:** research/docs only. Grants no APPROVED, no BC-5, no OHLCV CLOSED, no G001,
> no R3b, no loader / Dataset Identity / Parent CRT change.

| Field | Value |
|---|---|
| Probe id | `BC4-RESIDUAL-ATTRIBUTION-XAUUSD-MT5-V1` |
| Authorized | 2026-09-03 (user: BC-4 residual attribution) |
| Population | Recently-closed XAUUSD M15 bars on the same MT5 family as BC-2 / BC-4 |
| Question | What explains the 0.548%–0.676% gap F-099 measured between `tick_volume` and `len(copy_ticks_range(..., COPY_TICKS_ALL))`? |
| Depends on | F-098 (T is the bar OPEN, so the window is `[T, T+15m)`) and F-099 (the residual itself, and the ~1h tick-history feasibility bound) |

---

## 1. What is being explained

F-099 measured, on four bars:

| T (broker) | `tick_volume` | `ticks_all` | diff | pct |
|---|---|---|---|---|
| 22:15 | 6654 | 6699 | 45 | 0.6763% |
| 22:30 | 7478 | 7524 | 46 | 0.6151% |
| 22:45 | 9483 | 9535 | 52 | 0.5483% |
| 23:00 | 4924 | 4955 | 31 | 0.6296% |

Not a constant offset (45/46/52/31), not an exact ratio, far too tight to be noise.

BC-5 is blocked on this. Approval means "we know what the bytes mean," not "the bytes mostly
look right."

## 2. Evidence recorded here for the first time (previously untracked)

During BC-4's Phase 0 gate, the three tick-class arguments were measured on the 22:45 bar:

```text
tick_volume = 9483
COPY_TICKS_ALL  = 9535
COPY_TICKS_INFO = 9535
COPY_TICKS_TRADE = 0
```

`INFO == ALL` exactly; `TRADE` is empty. **Only one tick class is populated on this
symbol/terminal**, so the residual cannot be attributed *across* the three class arguments.

This observation lived only in a session transcript and appeared in **no tracked file** until
this document. It is real evidence bearing on a live question — a measurement that was taken but
not kept. Recording it is part of the work (mildest member of the F-079 / F-083 / F-085
silent-gap family).

Incidental reproducibility check, also recorded here: `COPY_TICKS_ALL = 9535` on the 22:45 bar
reproduced exactly across two separate processes minutes apart.

**Consequence:** the residual cannot collapse to a tick *class*. It may still collapse to a tick
*filter*. That is the open question, and it requires decomposing WITHIN the returned stream.

## 3. Frozen candidate counting rules

Applied to the raw tick array for `[T, T+15m)`, compared against that bar's `tick_volume`.

| Id | Rule |
|---|---|
| `C0_len` | `len(ticks)` — the V1 rule; known to overshoot, kept as reference |
| `C1_exclusive_upper` | `time_msc < (T+900)*1000` — tests upper-bound inclusion |
| `C2_dedup_exact` | `C1` + drop exact duplicates on `(time_msc, bid, ask, last, flags)` |
| `C3_price_changed` | ticks where `(bid, ask)` differs from the previous tick's |
| `C4_flag_bid_or_ask` | ticks where `flags & (TICK_FLAG_BID \| TICK_FLAG_ASK)` |
| `C5_flag_last` | ticks where `flags & TICK_FLAG_LAST` |
| `C6_distinct_time_msc` | count of distinct `time_msc` values |
| `C7_excl_and_price_changed` | `C1` ∧ `C3` |
| `C8_excl_and_flag_bid_ask` | `C1` ∧ `C4` |

Leading prior, stated but **not** privileged in scoring: `C3`/`C4` — `tick_volume` counts ticks
where the quote actually moved, while `copy_ticks_range` returns repeats. ~0.6% repeated quotes
on gold is plausible.

### 3.1 Anti-overfit clause (load-bearing)

The list above is FROZEN. **No candidate may be added, tuned, or parameterised after seeing
discovery output.** Exact integer equality is required — no tolerance band. A rule must match on
**every** discovery bar to survive.

Without this clause the experiment degenerates into searching counting rules until one fits four
numbers. Zero survivors is a result to report, not a prompt to widen the list.

## 4. Outcome rules (frozen)

| Outcome | Condition |
|---|---|
| `ATTRIBUTED` | exactly one candidate matches every discovery bar **and** every holdout bar |
| `AMBIGUOUS` | ≥2 candidates survive discovery and the holdout cannot separate them |
| `UNATTRIBUTED` | zero candidates match every discovery bar |
| `PENDING_HOLDOUT` | discovery survivors exist but no independent holdout capture yet |
| `INSUFFICIENT` | stale feed, or no scorable bars |

The holdout must come from a **separate capture with a different `fetched_at`**. Discovery and
holdout in one capture is fitting and confirming on the same data.

`UNATTRIBUTED` is a real result: it promotes `TICK_VOLUME_APPROXIMATE` from "unexplained gap" to
"measured, bounded, and demonstrably not explained by tick class, boundary, duplication, or flag
filtering" — enough for BC-5 to reason about.

The full candidate×bar table is recorded **regardless of outcome**. It is the evidence, whether
or not anything wins.

## 5. If `ATTRIBUTED` — the V2 re-verdict discipline

Following this repository's own F-084 / `MC-VCRT-...-V2` precedent:

1. **Reproduce V1 byte-identically first** (`TICK_VOLUME_APPROXIMATE`, diffs `45/46/52/31`).
   A V2 that cannot reproduce V1 is not a re-measurement.
2. Change **exactly one** named surface: the tick-population definition (`C0` → the winner).
3. Everything else — freshness window, `MIN_TEST1_BARS`, thresholds, Test 2, verdict vocabulary
   — unchanged, and asserted unchanged.

F-099's `APPROXIMATE` stays true as a statement about the V1-defined comparison; it is marked
`SUPERSEDED`, never deleted (CLAUDE.md §6.2 rule 4).

## 6. Predictions (frozen before inspecting candidate output)

1. At least one of `C3`/`C4`/`C7`/`C8` survives discovery — i.e. the residual is repeated or
   non-quote-moving ticks. Stated as the leading prior; a miss is recorded, not explained away.
2. `C0_len` does not survive (it is the measured overshoot, by construction).
3. `C5_flag_last` is ≈0 on every bar, since `COPY_TICKS_TRADE` returned 0 — no trade prints.

## 7. Artifacts

| Path | Role |
|---|---|
| This file | Pre-registration (authoritative rules) |
| `src/research/ohlcv_tick_attribution.py` | Frozen candidate counters + outcome rules |
| `tests/test_ohlcv_tick_attribution.py` | Synthetic tests, including negative cases |
| `docs/research-readiness/bc4_residual_attribution/` | discovery / holdout captures + `attribution.json` |

Live capture is opt-in. Absence of a holdout is `PENDING_HOLDOUT`, not a test failure, and no V2
verdict issues until it lands.

---

## 8. Amendment — V2 hypothesis (append-only, written before the holdout was scored)

Sections 1-7 are FROZEN and unedited. This section is append-only (CLAUDE.md §6.2 rule 4).

### 8.1 V1 outcome: `UNATTRIBUTED`

None of the 9 frozen candidates matched every discovery bar. Recorded, not re-spun.

**Prediction scorecard (§6), reported honestly:**

| # | Prediction | Result |
|---|---|---|
| 1 | one of `C3`/`C4`/`C7`/`C8` survives | **FAILED** — none survived |
| 2 | `C0_len` does not survive | CONFIRMED (deltas 52/38/41/15) |
| 3 | `C5_flag_last` ≈ 0 on every bar | CONFIRMED (exactly 0 on all four) |

### 8.2 The hypothesis discovery generated

The discovery flag histograms are:

| T | flags 134 | flags 130 | flags 4 | `tick_volume` | 134+130 |
|---|---|---|---|---|---|
| 22:45 | 9422 | 61 | 52 | 9483 | **9483** |
| 23:00 | 4878 | 46 | 38 | 4924 | **4924** |
| 23:15 | 4231 | 55 | 41 | 4286 | **4286** |
| 23:30 | 2508 | 23 | 15 | 2531 | **2531** |

`134 = 128|4|2` and `130 = 128|2` both carry `TICK_FLAG_BID` (bit 2); bare `4` is
`TICK_FLAG_ASK` alone. So on all four discovery bars:

```text
tick_volume == count(ticks where flags & TICK_FLAG_BID)
```

exactly, and the residual is exactly the ask-only tick count.

**This is a hypothesis, not a result.** It was formed by looking at discovery output, which the
§3.1 anti-overfit clause explicitly forbids as a basis for any claim. It currently has **zero**
out-of-sample support. `C4_flag_bid_or_ask` — pre-registered — tested `BID|ASK` and failed
because it also counts the bare-ASK ticks; the surviving hypothesis is `BID` only. One bit
different from what was frozen, which is precisely why it does not get to claim V1's outcome.

### 8.3 V2 — frozen before the holdout was scored

Single candidate, no list to search:

```text
C9_flag_bid := count(ticks where flags & TICK_FLAG_BID)
```

| Rule | Value |
|---|---|
| Population | Holdout capture only — a separate capture with a different `fetched_at`, no bar shared with discovery |
| Match | exact integer equality on **every** holdout bar; no tolerance band |
| Minimum n | **3 holdout bars.** Fewer → `PENDING_HOLDOUT`, partial result recorded, no verdict |
| `ATTRIBUTED_V2` | `C9_flag_bid` matches every holdout bar, n ≥ 3 |
| `UNATTRIBUTED_V2` | any holdout bar mismatches — the discovery pattern was a coincidence of that session |

No further candidates may be introduced. If `C9_flag_bid` fails the holdout, the outcome is
`UNATTRIBUTED_V2` and the residual stands unexplained; it does not license a third search.

### 8.4 What `ATTRIBUTED_V2` would and would not license

Would: a `MC-...-V2` re-verdict of BC-4b under the §5 discipline (reproduce V1 byte-identically,
change exactly one surface — the tick-population definition — assert everything else unchanged),
under which `TICK_VOLUME_CONFIRMED` becomes reachable.

Would not: any change to BC-1/BC-3/BC-5/BC-6, R3b, the loader, Dataset Identity, Parent CRT, the
fetcher, or production config. F-099's `APPROXIMATE` would be marked `SUPERSEDED`, never deleted.
