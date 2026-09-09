# Clock Evidence Sheet — `data/mt5/XAUUSD_M15.csv`

Purpose: establish **what clock every timestamp in this corpus is written in**, to a standard
sufficient to sign `user_reviewed` in `configs/data_provenance/ohlcv_clock_registry.json`.

**Two questions, kept separate. Do not merge them.**

| | Question | Answer lives in |
|---|---|---|
| **A** | What does the timestamp *physically mean*? | This sheet. A measurement. |
| **B** | Should the pipeline *convert* it to UTC? | `feature_pipeline.session_timestamp_basis`. A governance decision, default `broker_local`. |

This sheet answers **A only**. Signing it does not activate any conversion.

---

## Corpus identity

| field | value |
|---|---|
| path | `data/mt5/XAUUSD_M15.csv` |
| sha256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| rows | 47,275 |
| span | 2024-05-22 01:00:00 .. 2026-05-21 23:45:00 (corpus labels) |
| symbol / timeframe | XAUUSD / M15 |
| broker (from the sibling xlsx provenance) | Raw Trading Ltd — server `ICMarketsSC-Demo` |
| current registry state | `timezone: ""`, `user_reviewed: false` |
| detector verdict | `INCONCLUSIVE (low)` — "no declared-UTC reference corpus" |

**Until this sheet is signed, do not call these timestamps UTC.** Call them
*MT5 broker-server labels*.

---

## Evidence ladder

Ranked by independence. Levels 2–4 are filled in; **Level 1 is yours and is deliberately blank**
— it is the only one that does not route through this repository.

### Level 1 — DIRECT: MT5 terminal clock vs independent UTC  ☐ NOT YET DONE

The cleanest physical proof. Open the same MT5 terminal/server that produced this export and
read two clocks at the same instant.

| | winter reading | 2026-03-16-equivalent | summer reading |
|---|---|---|---|
| date | ____________ | ____________ | ____________ |
| MT5 server clock | ____________ | ____________ | ____________ |
| independent UTC (e.g. `time.is/UTC`) | ____________ | ____________ | ____________ |
| **difference** | ____________ | ____________ | ____________ |
| server name | ____________ | ____________ | ____________ |

Expected if the conclusion below is right: **+2 winter, +3 summer**.

> One summer reading alone proves only "August offset = +3". It does **not** establish
> `MT5_SERVER_NY_DST`. A winter reading is required to distinguish a DST-tracking server from a
> fixed +3.

### Level 2 — Independent UTC-timestamped feed  ☑ measured

`tools/tv_forensic/measure_corpus_clock.py` vs TradingView served in `Etc/UTC`.
Raw output: `results/corpus_clock_evidence.json`.

| anchor date | measured offset | mean abs err | runner-up | margin |
|---|---|---|---|---|
| 2026-01-15 (US standard) | **UTC+2** | 0.707 | UTC+10 @ 42.40 | 60x |
| 2026-03-16 (US DST on, EU DST off) | **UTC+3** | 0.636 | UTC-3 @ 44.98 | 71x |
| 2026-05-19 (US DST) | **UTC+3** | 0.574 | UTC+2 @ 41.67 | 73x |

**2026-03-16 is the US-vs-EU discriminator.** US DST began Mar 8 2026; EU DST began Mar 29. A
server on EU DST would still read +2 on Mar 16. It reads **+3** — therefore **America/New_York**,
not Europe/*.

*Method note:* this is not a test of price equality. OANDA and IC Markets are different feeds and
their prices differ by ~0.1–0.6. The test is that the *correct* offset agrees ~70x better than
any other candidate — a whole-bar misalignment scores 40+. Structure, expressed numerically.

### Level 3 — NFP invariant, entirely inside this corpus  ☑ measured

US Non-Farm Payrolls releases at **08:30 America/New_York, year-round**:
summer 08:30 ET = 12:30 UTC; winter 08:30 ET = 13:30 UTC. A server at +3/+2 places **both** at
**15:30 server time**. A fixed-offset server cannot.

Elevation = (that slot's range) / (that day's median range). Ratio form, so a few misdated days
cannot drive it.

| slot | summer | winter | what a peak here would mean |
|---|---|---|---|
| 14:30 | 1.16x | 0.88x | fixed UTC+2 — **rejected** |
| **15:30** | **6.05x** | **3.83x** | **US-DST server — consistent** |
| 16:30 | 2.92x | 2.46x | fixed UTC+3 — **rejected** |

Same test across every MT5 corpus (all six show the identical signature, consistent with one
broker export — but see Scope):

| corpus | 14:30 S/W | 15:30 S/W | 16:30 S/W |
|---|---|---|---|
| AUDUSD | 1.27 / 0.92 | **7.33 / 5.88** | 2.66 / 2.57 |
| EURCAD | 1.37 / 1.20 | **7.82 / 7.71** | 2.39 / 3.12 |
| EURUSD | 1.35 / 0.97 | **9.39 / 6.89** | 2.67 / 2.53 |
| GBPUSD | 1.30 / 1.10 | **8.08 / 6.51** | 2.72 / 2.22 |
| USDJPY | 0.90 / 0.95 | **8.41 / 4.77** | 2.14 / 2.67 |
| XAUUSD | 1.16 / 0.88 | **6.05 / 3.83** | 2.92 / 2.46 |

**⚠ Calendar caveat — verify before signing.** NFP dates here are generated as *first Friday of
month, except January = second Friday*. That is the usual BLS pattern but it is **not
authoritative**; releases shift for holidays. Check against
`bls.gov/schedule/news_release/empsit.htm`. An earlier version of this analysis used plain
first-Friday and wrongly included 2025-01-03 and 2026-01-02, which are not NFP days.

**⚠ Known failure mode.** Identifying NFP days by "largest Friday range of the month" does **not**
work from late 2025 on — gold volatility grew until NFP stopped being the largest monthly event
(that method picks 2026-01-30, 2026-02-20, 2025-10-17: all non-NFP). Use a real calendar.

### Level 4 — Session / daily-boundary corroboration  ☑ observed

Corpus daily bars run **01:00 -> 23:45** server, and that boundary holds **through** the US/EU
DST-mismatch window. Weakest evidence — it depends on assumptions about market hours — but it is
consistent with Levels 2 and 3 and inconsistent with a Europe/* server.

### Level 5 — Repository code (NOT independent; recorded for consistency only)

`src/features/broker_clock.py` already implements `offset_h = 3 if _ny_is_dst_on_date(...) else 2`
against `ZoneInfo("America/New_York")`. This **cannot be used as proof** — it is the thing being
certified. Listed only to show that code and measurement agree.

---

## Conclusion — written by the reviewer, not the assistant

```
Observed offset, winter        : ______________
Observed offset, summer        : ______________
2026-03-16 discriminator       : ______________
DST rule                       : ______________
Evidence strength              :  DIRECT  /  CORROBORATED  /  INFERRED
Reviewed by                    : ______________
Date                           : ______________
```

Proposed statement, if the Level 1 readings agree with Levels 2–4:

> `data/mt5/XAUUSD_M15.csv` timestamps are MT5 broker-server local time: **UTC+3 during US
> daylight saving, UTC+2 during US standard time**, following America/New_York transitions.
> Scoped to this corpus.

Declaration command:

```
python scripts/governance/review_ohlcv_clocks.py --review data/mt5/XAUUSD_M15.csv \
    --timezone MT5_SERVER_NY_DST --reviewed-by "<you>"
```

---

## Scope

- This sheet certifies **`data/mt5/XAUUSD_M15.csv` only.**
- The other five MT5 corpora pass the same Level-3 test and are very likely the same export, but
  **that is not a measurement**. Each needs its own sheet and its own Level-1/Level-2 evidence
  before signing. Do not bulk-declare.
- Binance `data/*USDT*.csv` should be plain `UTC` by API contract — **unverified here**, not
  covered by this sheet.
- Signing answers Question A only. Question B (`session_timestamp_basis`) stays `broker_local`
  and is a separate, explicitly gated decision.
