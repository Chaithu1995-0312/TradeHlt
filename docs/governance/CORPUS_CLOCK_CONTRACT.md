# Corpus Clock Contract

| Field | Value |
|---|---|
| Status | **FROZEN v1.0.0** (contract `clock-contract/1`) |
| Date | 2026-10-08 |
| Change | `CH-corpus-clock-contract-v1` |
| Finding | F-120 |
| Authority | the Corpus SSOT (`data_ingestion.corpus_store.load`, F-119) — no second temporal authority |
| Code | `src/data_ingestion/clock_contract.py` · `clock_registry.py` · `src/features/market_calendar.py` |
| Config | `configs/data_provenance/ohlcv_clock_registry.json` (`clocks`, records) · `configs/data_provenance/market_calendar.json` |
| Tests | `tests/test_corpus_clock_contract.py` (A–N) · `tests/test_ohlcv_clock_provenance.py` · `tests/test_corpus_ssot.py` |

## The question this contract answers

> **What does the timestamp in this corpus actually mean?**

Nothing is inferred. A corpus carries an explicit, configured clock identity, and everything downstream reads UTC.

```text
raw bytes ──► corpus_store.load ──► declared clock (provider / broker / clock_id) ──► configured clock
                                                            │ exact match, reviewed, sha-bound
                                                            ▼
                                     normalize ONCE ──► canonical UTC `timestamp`
                                                         + `source_timestamp` (audit only)
                                                            ▼
                         market calendar (day / week / HTF grids) · session windows (UTC) · features · CRT · research
```

## Invariants

1. **A dataset without an explicit, configured clock identity cannot enter the research system.**
2. **The declared provider / broker / clock_id must exactly match the configured clock.** No guessing: no "looks like UTC", no "same broker, probably same clock", no boundary or DST deduction. `clock_detector` is a diagnostic with **zero admission authority**.
3. **Normalization happens exactly once, at the corpus SSOT.** Canonical UTC cannot be normalized again (`DoubleNormalizationError`); a static scan forbids source-clock conversion primitives outside the boundary.
4. **Broker timestamp timezone and trading-session / calendar timezone are separate concepts.** A calendar is declared for the market and selected by the instrument, never derived from a broker.
5. **DST comes only from IANA rules.** No stored offset (`wall_offset`, `utc_offset`, `UTC+2/+3`) exists in any conversion input; the registry schema rejects such fields. `observed_utc_offsets` is evidence only and is never read by the converter.

## 1. Corpus identity — what identifies a corpus

`dataset_id` (registered, `docs/governance/dataset_identity_registry.json`) or the content address `sha256:<hex>` of the exact bytes read (F-119). Identity is the SOURCE bytes; normalization never changes it.

## 2. Broker / feed identity — who produced it

`provider` + `broker` (+ optional `server`), declared on the configured clock and repeated on the dataset record (bound corpora) and on the artifact's registry record. All three declarations must be equal.

## 3. Raw clock — what the timestamp means

A configured clock definition: `{provider, broker, server?, timezone (IANA), server_midnight_local ("HH:MM"), evidence[], observed_utc_offsets[]?}`.
`server_midnight_local` is *the local time in `timezone` at which the server's clock reads 00:00* — the relation between a broker server clock and an IANA zone.

| clock_id | provider / broker | timezone | server_midnight_local |
|---|---|---|---|
| `mt5_icmarkets_xau` | mt5 / ICMarkets (server `ICMarketsSC-Demo`) | `America/New_York` | `17:00` |
| `binance_utc` | binance / Binance | `UTC` | `00:00` |
| `constructed_utc` | synthetic / none (in-process, tests only) | `UTC` | `00:00` |

## 4. Timezone and DST

One uniform rule:

```text
local = server_wall - ((24h - server_midnight_local) mod 24h)
utc   = zoneinfo(timezone).localize(local)        # DST from the IANA rules; gap / overlap raise
```

For `mt5_icmarkets_xau` this gives the +2h (EST) / +3h (EDT) server offset *as a consequence* of New York DST, including the US/EU mismatch weeks. It reproduces the independent legacy reference (`features.broker_clock`) on all 47,275 bars of the standing XAUUSD corpus.

## 5. Canonical time

UTC (naive UTC wall values in memory and in text). `AdmittedCorpus.text / records() / frame()` carry canonical `timestamp` and `source_timestamp`; `frame().attrs` carry `timestamp_clock="UTC"`. The rebuild is line-preserving, so source integrity defects (blank lines, short rows, unparseable cells) stay visible to downstream fail-closed checks.

## 6. Session and calendar time

* **Session windows** (`crt_engine.session_windows`, `feature_pipeline.session_windows_utc`) are authored in UTC and compare directly against canonical UTC; `exchange_session_windows` carry their own IANA zone.
* **Market calendar** (`market_calendar.json`): `fx_metals` = `America/New_York` day starting `17:00`; `crypto` = the UTC day. `wall = local(timezone) + ((24h - day_start) mod 24h)`; the day starts at wall 00:00. It drives day-of-week, D1/H4/H1/W1/MN1 grids, PDH/PDL, weekly range and swap nights. The asset class comes from the existing classifier `dataset_integrity.classify_market`.
* `feature_pipeline.session_timestamp_basis` is **RETIRED**; a config that still carries it raises.

## 7. Authority — which component owns each fact

| Fact | Owner |
|---|---|
| Corpus / content identity | Corpus SSOT (`corpus_store.load`), dataset registry for bound `dataset_id` |
| Clock definitions | `ohlcv_clock_registry.json` `clocks` |
| Which clock a corpus is on | the reviewed, sha-bound registry record **and** (bound corpora) the dataset record |
| Conversion | `clock_contract.py` (one place) |
| Market calendar | `market_calendar.json` |
| Session windows | production config |

## 8. Derived datasets

A window written by the replay harness is cut on canonical UTC but **written in the parent's source representation**, with a `.parent.json` sidecar `{derived_from (parent provenance incl. sha), derived_corpus_sha256, window_start_utc, window_end_utc, selection_rule, clock_inherited_from}`. The window inherits the parent's declared clock through that explicit lineage; the sidecar is bound to the window's own sha, so a changed window loses it.

## 9. Governance — unknown / unreviewed

Unchanged in intent: no record, a sha mismatch, `user_reviewed=false`, a missing `clock_id`, an unknown `clock_id` or a provider/broker mismatch → `ClockProvenanceError`. There is no environment escape hatch; `declare_in_process` exists for constructed (test) data and the floor test forbids it under `src/`. An unknown clock never silently becomes UTC.

## 10. Automation — what prevents duplicate normalization

`DoubleNormalizationError` (type guard on the canonical state) + the static scan in `tests/test_corpus_clock_contract.py::test_E_no_source_clock_conversion_outside_the_boundary` + the full-corpus parity test against the independent legacy reference.

## Adding a broker

Add a `clocks` entry (IANA `timezone` + `server_midnight_local` + evidence), then declare corpora on it with the review CLI:
`python scripts/governance/review_ohlcv_clocks.py --review <path> --clock-id <id> --reviewed-by <you>`. No code change.
