# Pre-Registration — BC-2 executable open-vs-close label proof

> **Status:** PRE-REGISTERED (written before any live MT5 snapshot is scored).
> **Lane:** measurement / evidence.
> **Authority:** research/docs only. Grants no APPROVED, no G-06 flip until a live pair
> scores OPEN or CLOSE, no OHLCV CLOSED, no G001, no R3b.

| Field | Value |
|---|---|
| Probe id | `BC2-OPEN-CLOSE-XAUUSD-MT5-V1` |
| Authorized | 2026-09-02 (user: BC-2 only) |
| Population | MT5 M15 acquisition family that produced `XAUUSD_MT5_PHASE1_20260521` |
| Admitted artifact (inference target) | `data/mt5/XAUUSD_M15.csv` @ `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Missing artifact named 2026-07-10 | `executable_open_vs_close_label_proof` |
| Closure report flip | [`ohlcv-closure-report-2026-07-10.md`](../governance/ohlcv-closure-report-2026-07-10.md) §6 BC-2 |
| Phase-1 residual | G2 `PASS_CONSISTENT_UNPROVEN_LABEL`; `executable_open_vs_close_label_proof = ABSENT` |

This document FREEZES hypotheses, preconditions, and the interpretation rule
**before** a live pair exists. A null cannot be re-spun into OPEN. A hit cannot
widen the clock.

---

## 1. What this is not

- Not another 15-minute lattice census (G2 already has that on `4d73f5ce…`).
- Not a proof that the frozen CSV bytes were fetched mid-bar (those rows are complete).
- Not G-06 for binance/yfinance (family-scoped).
- Not BC-4 / BC-5 / BC-3 / BC-6.
- Not `datetime.now(UTC)` vs bar timestamps (F-066: naive stamps are broker-server).

The inference to the admitted artifact is **producer identity**: the same MT5
`rates['time']` → CSV path that wrote the family. A live OPEN/CLOSE verdict is
evidence about that producer, hence about how `4d73f5ce…` timestamps are to be
read. It is not a re-hash of the file.

---

## 2. Hypotheses (closed)

| Id | Claim |
|---|---|
| H_OPEN | Timestamp T is the bar **open**. Interval `[T, T+15m)`. |
| H_CLOSE | Timestamp T is the bar **close**. Interval `(T−15m, T]` or `[T−15m, T]`. |
| H_OTHER | Lattice or mutation pattern matches neither. |
| H_INSUFFICIENT | Probe did not meet preconditions (no live MT5, not mid-interval, no mutation, clock unusable). |

Prior (STATIC, not this proof): `mt5_candle_fetcher.py` treats `rates['time']` as
bar-open epoch. Belief ≠ evidence.

---

## 3. Clock (frozen)

`fetched_at` is the MT5 tick time converted with the **same**
`fromtimestamp(..., tz=utc)` as `r["time"]` (`mt5_candle_fetcher.py` conversion).

Forbidden as a verdict input: `datetime.now(timezone.utc)` alone.

If tick time is missing → `INSUFFICIENT` (`clock=unavailable`).

---

## 4. Snapshots

Each snapshot:

```text
fetched_at   # broker/MT5 clock, as §3
symbol
bars[]       # chronological; last = latest returned bar
  timestamp, open, high, low, close, volume
```

Two snapshots A then B. Bar minutes = 15. `margin_seconds = 60`.

Mid-interval (A), else `INSUFFICIENT` (`not_mid_interval`):

```text
last = last bar of A
delta = fetched_at_A - last.timestamp     # signed
```

- Open-candidate window: `margin < delta < 15m - margin` (T in the past, inside the bar)
- Close-candidate window: `margin < -delta < 15m - margin` (T in the future, inside the bar)
- Else: `INSUFFICIENT`

Post-close (B), else `INSUFFICIENT` (`not_post_close`):

- If A was open-candidate: `fetched_at_B >= last_A.timestamp + 15m + margin`
- If A was close-candidate: `fetched_at_B >= last_A.timestamp + margin`

Mutation of bar T (else `INSUFFICIENT`, `no_mutation` — quiet tape is not CLOSE):

```text
bar T exists in A and B
{high, low, close, volume} of T at B ≠ that set at A
```

`open` of T is allowed to stay equal (open-label forming). If `open` of T changes,
record it; do not by itself force OTHER.

---

## 5. Verdict rule (frozen)

Apply in this order. First match wins.

1. Missing MT5 / empty rates / missing tick clock → `INSUFFICIENT`
2. A fails mid-interval → `INSUFFICIENT`
3. B fails post-close → `INSUFFICIENT`
4. T not on 15-minute lattice (seconds=0, minute % 15 == 0) → `OTHER`
5. Open-candidate **and** mutation of T → **`OPEN`**
6. Close-candidate **and** mutation of T → **`CLOSE`**
7. Open- or close-candidate **and** T missing in B → `OTHER`
8. Else → `INSUFFICIENT`

No averaging. No “probably open because STATIC.” Synthetic fixtures never flip
governance. Only a live pair with `OPEN` or `CLOSE` may be cited as
`executable_open_vs_close_label_proof`.

---

## 6. Interpretation (frozen)

| Verdict | Meaning for BC-2 / G-06 (mt5 family) |
|---|---|
| `OPEN` | Executable proof: T is bar open. G-06 for **mt5** may be marked PROVEN in CORPUS_AUTHORITY / a Phase-1 residual update. Output contract 2026-07-10 stays a PASS-B artifact (not silently rewritten). OHLCV_CLOSURE_STATUS stays BLOCKED (other BCs). |
| `CLOSE` | Executable proof against the STATIC prior. Record as CONTRADICTED for the family. Do not “fix” the fetcher this program. |
| `OTHER` | Label convention is not the two-hypothesis set. Do not force OPEN. |
| `INSUFFICIENT` | BC-2 remains UNPROVEN. Not a fail of H_OPEN. |

---

## 7. Predictions (frozen before live capture)

1. If a valid mid/post pair is captured on XAUUSD M15, verdict is `OPEN`.
2. `datetime.now(UTC)` vs bar T without tick time would often be `INSUFFICIENT` under F-066; that is why tick time is mandatory.
3. A 15-minute wait with no OHLC/volume change is `INSUFFICIENT`, not `CLOSE`.

---

## 8. Artifacts

| Path | Role |
|---|---|
| This file | Pre-registration (authoritative rules) |
| `src/research/ohlcv_open_close_label.py` | Scorer + optional MT5 capture |
| `tests/test_ohlcv_open_close_label.py` | Synthetic pairs only |
| `docs/research-readiness/bc2_open_close/` | Live snapshots + score JSON when a pair is captured |

Live capture is opt-in (`--capture` / `--score`). Absence of live files is
`INSUFFICIENT`, not a test failure.

---

## 9. Amendments (2026-09-03)

Sections 1–8 are FROZEN and unedited. This section is **append-only** (CLAUDE.md §6.2
rule 4). It records changes to the **emission layer** — what the scorer *reports* —
made before any live pair was scored, plus one new precondition.

**None of 9.2–9.5 can change a verdict.** They were found by a design/schema trace of
`src/research/ohlcv_open_close_label.py` against §5 and are `CODE_DRIFT` (the frozen
prereg is the authority; the code is corrected to it). Rules 1–8 of §5 are untouched.

### 9.1 New precondition — stale-feed guard (D5)

`.grok/PENDING.md` warns against capturing against a stale terminal (an August tick in
a September session). §5 has no guard for it: `no_mutation` catches a *fully frozen*
feed but not a stale-then-reconnecting one.

Added, evaluated after §5 rule 1 and before rule 2:

```text
wall_clock_skew_seconds = now(UTC) - fetched_at     # measured AT CAPTURE, stored in the snapshot
abs(skew) > stale_threshold_seconds  ->  INSUFFICIENT, reason stale_feed_{a|b}
source == live_mt5 and skew is None  ->  INSUFFICIENT, reason stale_feed_unmeasured_{a|b}
```

`stale_threshold_seconds = 21600` (6h). **Deliberately offset-tolerant:** MT5 server
time runs ~UTC+2/+3 (F-066), so a *healthy* terminal shows a legitimate multi-hour
skew — measured `-10799s` (exactly UTC+3) on `ICMarketsSC-Demo` 2026-09-02. A tight
threshold would reject a live feed. 6h clears any plausible broker offset and still
catches a weeks-stale terminal.

**Why this does not violate §3.** §3 forbids `datetime.now(UTC)` *as a verdict input*.
This guard is one-directional: it can only downgrade a result to `INSUFFICIENT`, never
produce `OPEN` or `CLOSE`. It cannot manufacture a hit. The skew is measured at capture
time and persisted, so scoring a snapshot later does not re-measure it against the
scoring clock. Pinned by `test_staleness_guard_can_only_downgrade`.

### 9.2 G-06 tri-state (D1)

G-06 is *open-time labeling* (`docs/governance/ohlcv-closure-report-2026-07-10.md:52`),
so a `CLOSE` verdict **contradicts** G-06 — §6 already says CONTRADICTED. The scorer
emitted `grants_g06_mt5: true` on the CLOSE branch, one boolean carrying two opposite
meanings. Corrected to:

| verdict | `g06_mt5` | `grants_g06_mt5` |
|---|---|---|
| `OPEN` | `PROVEN` | `true` |
| `CLOSE` | `CONTRADICTED` | `false` |
| `OTHER`, `INSUFFICIENT` | `UNPROVEN` | `false` |

### 9.3 Proof flag — synthetic fixtures mechanically cannot prove (D3)

§5's "Synthetic fixtures never flip governance" was prose with no mechanism: a
synthetic `FetchSnap` scored identically to a live one. Now `source` is `synthetic` by
default and only `capture_mt5_snapshot` may set `live_mt5`; `snap_from_dict` fails
closed. The citable artifact is a single derived field:

```text
executable_open_vs_close_label_proof =
    verdict in {OPEN, CLOSE} and source_a == source_b == live_mt5
    and admitted_sha256_match is True
```

`admitted_sha256_match` is now **checked**, not asserted: the report hashes
`data/mt5/XAUUSD_M15.csv` and reports `null` when absent. A mismatch withholds the
*proof claim* only — it never rewrites a verdict, because the label convention is a
property of the producer, not of the CSV.

Snapshots also record the capturing terminal (`company`, `name`, `build`, `connected`,
`server`). The account login is deliberately **not** recorded. The frozen dataset record
`docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json` carries no terminal identity,
so the report emits `producer_family_match: UNVERIFIED_NO_RECORDED_TERMINAL` — recording
the live terminal makes a future comparison possible; claiming a match now would be
fabrication.

### 9.4 One report shape (D2) and clock basis (D4)

The `snapshot_capture_failed` path emitted 3 of 12 keys, dropping `probe_id`, `prereg`
and `ohlcv_closure`. All paths now return one key set from a single `_base_report()`
(pinned by `test_every_exit_path_returns_the_same_key_set`).

Persisted timestamps carry `clock_basis: "broker_local"` — the token the dataset
identity record already declares. MT5 epochs are broker-server seconds, so the `+00:00`
suffix on a persisted stamp is **nominal** (F-066). Verdict arithmetic is unaffected:
`delta` is offset-invariant, and a whole-hour offset preserves `minute % 15`.

### 9.5 Notes on §2 and on capture (D8)

- §2 says "the same MT5 `rates['time']` → CSV path". The probe uses
  `copy_rates_from_pos`; `src/inout/mt5_candle_fetcher.py:186` uses `copy_rates_range`.
  The inference still holds — the label convention is a property of the `rates['time']`
  field, not of the call — but the two calls are not one path.
- **Cold-cache hazard (observed 2026-09-02):** the first `copy_rates_from_pos` after
  `symbol_select` can return a cached window 5099s behind a live tick. That scores
  `not_mid_interval` (a correct rejection) but is indistinguishable from a closed
  market. `capture_mt5_snapshot` now retries until the returned window reaches the tick.
- `score` exit codes: `0` = pair scored (any verdict), `2` = capture/IO failure,
  `1` only under `--require-verdict`. Previously `INSUFFICIENT` — the *expected* steady
  state — exited non-zero, which would turn absence-of-evidence into a red build.
