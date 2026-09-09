# Pre-Registration — BC-4 volume semantics proof

> **Status:** PRE-REGISTERED (written before any live volume/tick data is scored beyond the
> Phase 0 feasibility gate, whose result is recorded in section 3.1 and binds Test 1's window).
> **Lane:** measurement / evidence.
> **Authority:** research/docs only. Grants no APPROVED, no BC-5 flip, no OHLCV CLOSED, no G001,
> no fetcher rewrite, no production config change until a verdict is scored.

| Field | Value |
|---|---|
| Probe id | `BC4-VOLUME-SEMANTIC-XAUUSD-MT5-V1` |
| Authorized | 2026-09-03 (user: BC-4 program, probe + enforcement) |
| Population | Same MT5 M15 acquisition family as BC-2 (`docs/research/preregistration-bc2-open-close-label.md`), which produced `XAUUSD_MT5_PHASE1_20260521` |
| Admitted artifact (inference target) | `data/mt5/XAUUSD_M15.csv` @ `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Declared value under test | `volume_semantic = TICK_VOLUME` (`docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json`) |
| Missing artifact named 2026-07-10 | executable proof these bytes are tick counts (`docs/governance/CORPUS_AUTHORITY.md:108`, G4/BC-4 residual) |
| Closure report requirement | per-corpus `volume_semantic` (+ `is_synthetic`) metadata, load-bearing, with a test on the proxy branch (`docs/governance/ohlcv-closure-report-2026-07-10.md:106`, SEED-OHLCV-19) — this probe answers the SEMANTIC half only; the ENFORCEMENT half is a separate, later change |
| Depends on | BC-2 / F-098 (`G-06_MT5 = PROVEN`) — the bar-open convention. The tick window below is `[T, T+15m)` and is only well-defined because T is known to be the OPEN, not the close |

This document FREEZES hypotheses, the test windows, the thresholds, and the interpretation
rule **before** live data beyond the Phase 0 feasibility gate is scored. A null cannot be
re-spun into CONFIRMED. A shortfall cannot be re-spun into BOUND.

---

## 1. What this is not

- Not a re-measurement of BC-2 (F-098 stands; this probe CONSUMES its result, does not re-derive it).
- Not proof that `real_volume` is meaningless in general — only that it is absent/zero on this
  family's bars, which is itself evidence against `H_REAL`.
- Not BC-1 / BC-3 / BC-5 / BC-6.
- Not the BC-4 ENFORCEMENT half (schema wiring, `is_synthetic`, SEED-OHLCV-19) — that is Phase C
  of the same program, executed only after this probe returns a verdict, so the vocabulary is
  wired against a proven answer rather than a guess.
- Not a claim that this terminal is the one that produced `4d73f5ce…` (that is BC-2's
  `producer_family_match`, still `UNVERIFIED_NO_RECORDED_TERMINAL` — Test 2 below narrows this
  for the volume COLUMN specifically, but does not resolve terminal identity in general).

---

## 2. Hypotheses (closed)

| Id | Claim |
|---|---|
| `H_TICK` | `volume` is a count of ticks (price/quote updates) received during the bar interval |
| `H_REAL` | `volume` is real traded volume (executed size) |
| `H_SYNTHETIC` | `volume` is derived/proxy (constant, range-derived, row-index-derived) |
| `H_OTHER` | a broker-defined counter matching none of the above |
| `H_INSUFFICIENT` | preconditions unmet (no tick history for the window, stale feed, terminal unavailable) |

Prior (STATIC, not evidence): `src/inout/mt5_candle_fetcher.py:186` (and `:284`) write
`int(r["tick_volume"])` into the `volume` column. Integer-typing is imposed by the Python `int()`
cast at the writer and is not evidence of what the field counts (D-note: this was checked and
ruled out as a discriminator before this probe was written).

---

## 3. Preconditions and clock

Same clock rule as BC-2 §3: `fetched_at` / bar timestamps use the MT5 tick-time conversion
(`fromtimestamp(..., tz=utc)`), broker-local by provenance (F-066). `datetime.now(UTC)` alone is
forbidden as a verdict input. A capture whose skew exceeds 6h (the same threshold BC-2 froze,
`STALE_THRESHOLD_SECONDS`) is `INSUFFICIENT`, not scored.

### 3.1 Phase 0 feasibility gate — RESULT (binds Test 1's window)

Measured 2026-09-02T23:0x UTC broker time, `ICMarketsSC-Demo`, build 6140, connected:

| Window requested | `copy_ticks_range` result |
|---|---|
| 15 min ago | returns immediately (8,117–9,535 ticks) |
| 1 hour ago | returns immediately (8,836 ticks) |
| 3 hours ago | **hangs** — no return, no error, within a 165s+ observed wait |
| 1 day ago | **hangs** — no return, no error, within a 130s+ observed wait |

`last_error()` reports `(1, "Success")` on every returned call — there is no error signal to
catch; the failure mode is an indefinite stall, not an exception or an empty result. This is a
genuine feasibility boundary on this terminal, not a bug in the probe.

**Consequence, frozen now:** Test 1 is scoped to bars whose window `[T, T+15m)` closed within
the **last 60 minutes** of capture time. This is not a weakened test — the semantic question
("does this field count ticks?") does not depend on how old the bar is, and BC-2's F-098 result
already establishes what `T` means for any bar in the corpus. It is a feasibility-driven scope
reduction, recorded here rather than discovered mid-test. A probe that tried to force a wider
window by waiting indefinitely would violate the "never substitute a weaker test and call it
proof" discipline in the opposite direction — it would inflate confidence in a result obtained
by luck of timing, not by a wider evidentiary base.

If future capture cannot find any bar within the 60-minute freshness window (e.g., session
close), Test 1 for that run is `INSUFFICIENT (no_fresh_bar)`.

---

## 4. Test 1 — semantic identity (live, decisive)

For each recently-closed M15 bar `T` with `now(broker) − (T+15m) ≤ 3600s`:

```text
tick_volume(T)   := that bar's tick_volume field from copy_rates_from_pos
ticks_all(T)     := len(copy_ticks_range(symbol, T, T+15m, COPY_TICKS_ALL))
real_volume(T)   := that bar's real_volume field from copy_rates_from_pos
```

Record, per bar: `tick_volume`, `ticks_all`, `real_volume`, `diff = ticks_all - tick_volume`,
`exact_match = (diff == 0)`.

**`H_REAL` kill rule (independent of the count comparison):** if `real_volume(T) == 0` for
every scored bar while `tick_volume(T) > 0`, `H_REAL` is REJECTED for this family. This does not
by itself CONFIRM `H_TICK` — it only removes one hypothesis — but it is evidence the frozen
artifact alone could not supply (the CSV has no `real_volume` column).

### Verdict rule for Test 1

1. Fewer than 3 bars scored (feasibility or stale-feed shortfall) → `volume_semantic_verdict = INSUFFICIENT`
2. `exact_match` rate ≥ 0.90 **and** median(`diff`) == 0 → `TICK_VOLUME_CONFIRMED`
3. `exact_match` rate < 0.90 but `ticks_all` and `tick_volume` correlate with |diff| small and
   directionally consistent (e.g., `ticks_all` systematically ≥ `tick_volume`, consistent with
   `COPY_TICKS_ALL` counting a superset such as flag-only updates) → `TICK_VOLUME_APPROXIMATE`,
   reported as a DISTINCT verdict — not silently folded into CONFIRMED
4. Otherwise → `TICK_VOLUME_CONTRADICTED`

Rule 3 exists because ticks and bar tick_volume are computed by different internal paths in the
terminal (per-tick stream vs bar aggregation) and a small systematic bias is a plausible honest
outcome, not a proof failure — but it must never be silently reported as `CONFIRMED`.

---

## 5. Test 2 — artifact binding

Independent of Test 1; uses only `copy_rates_range` (M15 bars), so it is unaffected by the
tick-history feasibility limit in §3.1.

Sample K ≥ 20 bars spread across the frozen corpus's full range
(`2024-05-22T01:00:00` → `2026-05-21T23:45:00`), re-fetch via `copy_rates_range` for those exact
timestamps, and compare the frozen CSV's `volume` column to the re-fetched `tick_volume`.

### Verdict rule for Test 2

1. `exact_match` rate ≥ 0.99 on sampled bars → `artifact_binding = BOUND`
2. Mismatches present but no systematic pattern (broker history revision is the known confound:
   MT5 servers can revise historical tick_volume as more history backfills) → `UNCONFIRMED`
3. Mismatches follow a constant offset or scale factor → `CONTRADICTED`, with the offset/scale
   recorded
4. Sample unobtainable (rates absent for sampled timestamps) → `NOT_TESTED`

`BOUND` narrows — but does not resolve — BC-2's `producer_family_match`: it would mean the
volume COLUMN in `4d73f5ce…` is reproducible from a live re-fetch on this terminal, which is
evidence for (not proof of) common producer family, scoped to this one column.

---

## 6. Two verdicts, reported separately

```text
volume_semantic_verdict ∈ {TICK_VOLUME_CONFIRMED, TICK_VOLUME_APPROXIMATE,
                            TICK_VOLUME_CONTRADICTED, INSUFFICIENT}
artifact_binding        ∈ {BOUND, UNCONFIRMED, CONTRADICTED, NOT_TESTED}
h_real_status            ∈ {REJECTED, NOT_REJECTED, NOT_TESTED}
```

These are never collapsed into one boolean. A single flag carrying two distinct claims was
BC-2's D1 defect (`grants_g06_mt5` on the CLOSE branch); this probe is written to not repeat it.

---

## 7. Interpretation

| `volume_semantic_verdict` | Meaning |
|---|---|
| `TICK_VOLUME_CONFIRMED` | Executable proof the declared `volume_semantic: TICK_VOLUME` is correct for this family. G4/BC-4b residual closes for mt5. |
| `TICK_VOLUME_APPROXIMATE` | The field counts something tick-adjacent but not identical to `COPY_TICKS_ALL`; record as a DISTINCT semantic note, do not report as CONFIRMED. |
| `TICK_VOLUME_CONTRADICTED` | The dataset record's declared semantic is FALSE. BC-5 must reject or re-declare, not approve as-is. A real and valuable outcome. |
| `INSUFFICIENT` | BC-4b stays open. Not a failure of `H_TICK`. |

`artifact_binding` and `h_real_status` are reported alongside but do not by themselves flip
`volume_semantic_verdict`.

---

## 8. Predictions (frozen before live scoring)

1. `h_real_status = REJECTED` (real_volume already observed 0 on a live bar during Phase 0,
   §3.1's feasibility check — this prediction is recorded as ALREADY OBSERVED, honestly, not as
   a blind prediction; it is not re-tested as if unknown).
2. Test 1 lands `TICK_VOLUME_CONFIRMED` or `TICK_VOLUME_APPROXIMATE`, given the STATIC prior and
   the near-match already observed (`tick_volume=9483` vs `ticks_all=9535` on one bar during
   Phase 0, a 0.5% gap) — this too is a partial pre-observation, disclosed rather than hidden.
3. Test 2 (`BOUND` vs `UNCONFIRMED`) is undetermined a priori; broker history revision could
   plausibly produce `UNCONFIRMED` on an otherwise-correct field.

---

## 9. Artifacts

| Path | Role |
|---|---|
| This file | Pre-registration (authoritative rules) |
| `src/research/ohlcv_probe_report.py` | Shared emission contract (extracted from the BC-2 scorer) |
| `src/research/ohlcv_volume_semantics.py` | Test 1 + Test 2 + capture |
| `tests/test_ohlcv_volume_semantics.py` | Synthetic tests only |
| `docs/research-readiness/bc4_volume_semantics/` | Live snapshots + score JSON when captured |

Live capture is opt-in. Absence of live files is `INSUFFICIENT`, not a test failure.
