# Corpus Clock / Calendar Contract — CH-corpus-clock-contract-v1 (design + implementation plan)

## Context
F-117 (v7) activated `feature_pipeline.session_timestamp_basis=utc_corrected`. One global key now
decides "subtract the MT5 broker offset", whatever corpus is loaded. The A/B analysis attributed
**46 of the 60 failing/erroring tests to v7 keys**:
- 24 to the session basis alone,
- 13 heavy tests to the clock guard,
- 7 to `sweep_semantics`,
- 2 to `retrace_semantics`.

The other 14 are unrelated (other sessions' work, v9, baseline).

The root cause is architectural. The repository records which clock a corpus is on in
`ohlcv_clock_registry.json`, but the conversion is chosen by config rather than by the corpus.
So a UTC corpus under `utc_corrected` hits "DOUBLE CONVERSION refused".

**User decisions (2026-10-08):**
- **Full migration.** `Candle.timestamp` / frame `timestamp` become canonical UTC at the corpus boundary. HTF/day/week grids move to an explicit calendar contract.
- **Sweep/retrace certification tests** name the identity they certify. Legacy tests inject legacy keys. The new FM-090..093 / FM-096 get their own certification where it is missing.

**Verified this session (read-only):** the IANA model "broker wall = America/New_York local + 7h"
equals the current `broker_clock.mt5_server_to_utc` on **all 47,275 bars** of
`data/mt5/XAUUSD_M15.csv` (0 mismatches). Over a synthetic 15-minute grid for 2024–2026, the two
models differ only on **228 Sunday slots, server hours 00–09**, around DST transitions. The corpus
has no weekend bars (weekday counts Mon..Fri only).

---

## 1. Design objective
**Response.** One machine-readable contract per corpus answers "what does this timestamp mean":
- which clock produced it (basis),
- which timezone governs it, with DST by IANA rules,
- how it maps to canonical UTC (one normalizer),
- under which calendar contract days, weeks and sessions are computed (separate from the corpus).

New brokers are added as data: a clock-kind entry plus a reviewed record. No code change. XAUUSD/ICMarkets is one instance, not the model.

**Evidence.**
- `clock_registry.py`: `ClockRecord.timezone` already accepts named kinds or any IANA zone.
- The registry holds 227 records: 18 reviewed `MT5_SERVER_NY_DST`, 6 reviewed `UTC` (`data/binance/*_M5.csv`), 203 unreviewed.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 2. Separate temporal concepts
**Response.** The five concepts get separate fields. None of them is called `utc_corrected`.

| Concept | Field | Owner |
|---|---|---|
| A raw basis | `storage_basis` ∈ `utc_epoch` · `broker_server_time` · `exchange_time` · `named_timezone` | clock kind |
| B raw timezone | `timezone` (IANA) + `wall_offset` (e.g. `+07:00` for NY-anchored MT5 servers) | clock kind |
| C DST policy | `dst_policy` = `none` · `iana:<zone>`. **Never** seasonal `UTC+2/UTC+3` literals | clock kind |
| D canonical time | always `UTC` (naive UTC wall values internally; see §7) | contract constant |
| E session/calendar tz | `calendar` = {`timezone`, `day_start`, `week_start`} per asset class; `session_windows` carry their own tz | market calendar config |

The contract states verbatim: *"Broker timestamp timezone and trading-session/calendar timezone are separate concepts. A calendar is never inferred from a broker."*

**Evidence.**
- `clock_evidence/XAUUSD_M15_clock_evidence.md` already separates "A: what the timestamp means" from "B: should we convert".
- `exchange_session_windows` already carries a per-session IANA `tz` (`broker_clock.py:122`).

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 3. Canonical flow
**Response.**
```
raw bytes → corpus_store.load (identity, sha, admission: integrity gate runs on SOURCE clock)
          → clock contract (reviewed record → ClockContract)
          → normalize once → frame/Candle `timestamp` = canonical UTC (+ `source_timestamp` raw, audit only)
          → calendar contract (UTC → calendar wall time for day/week/HTF grids)
          → features / CRT / research / live
```
Downstream code never sees a broker name or zone. It sees UTC plus the calendar contract for its asset class.

**Evidence:** today `compute_context` (`feature_pipeline.py:763`), `_session_name_at` (`crt_engine_v2.py:3440`) and `exchange_sessions_at` (`broker_clock.py:161`) each convert on their own.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 4. Corpus clock contract (machine-readable)
**Response.** Reuse existing terms: `timezone`, `user_reviewed`, `reviewed_by`, `source_family`, `clock_basis`.

`configs/data_provenance/ohlcv_clock_registry.json` moves to schema **2.0.0**. Changes are additive, and existing records stay valid.
- **New top-level `clock_kinds` table:**
  ```json
  "clock_kinds": {
    "UTC": {"storage_basis":"utc_epoch","timezone":"UTC","wall_offset":"+00:00","dst_policy":"none"},
    "MT5_SERVER_NY_DST": {"storage_basis":"broker_server_time","timezone":"America/New_York",
       "wall_offset":"+07:00","dst_policy":"iana:America/New_York","bar_label":"open",
       "evidence":["F-066","F-098","docs/governance/clock_evidence/XAUUSD_M15_clock_evidence.md"]}
  }
  ```
- **Implicit kinds.** A record whose `timezone` is a bare IANA zone gets `{storage_basis: named_timezone, wall_offset: +00:00, dst_policy: iana:<zone>}`.
- **Optional `producer` block on each record:** `{source_family, broker, server, terminal_build, evidence}`. `UNKNOWN` is allowed. Per `CORPUS_AUTHORITY.md:254`, broker is lineage and is never guessed.
- **`contract_version: "clock-contract/1"`.**

Code goes in a new `src/data_ingestion/clock_contract.py`:
- `ClockContract` (frozen dataclass),
- `contract_for(record)`,
- `to_canonical_utc(raw_view)`,
- `source_wall_time(utc, contract)` (the inverse, used only for the legacy session arm in §8).

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 5. Examples from the repository
**Response.**
- **XAUUSD (`data/mt5/XAUUSD_M15.csv`, kind `MT5_SERVER_NY_DST`).** UTC = localize(raw − 7h, America/New_York) → UTC. Verified equal to the current rule on 47,275/47,275 bars. On the non-trading Sunday DST hours the model is ambiguous or nonexistent and raises (fail-closed). The producer block records `broker: UNKNOWN` for the two-year candidate (no fetch log), but `ICMarketsSC-Demo` for windows whose registry notes cite the terminal.
- **Binance (`data/binance/*_M5.csv`, reviewed `UTC`).** Identity normalization: same values, state becomes `canonical_utc`. A second pass is impossible by construction (§7).
- **Broker-local FX.** The repo's FX corpora (`data/mt5/EURUSD_M5.csv` etc.) sit on the **same** MT5 server kind, so they get the same contract. **There is no repository corpus on a plain named IANA zone.** That case is covered by the generic `named_timezone` kind and synthetic tests only. No broker contract is invented.

**Classification:** FACT (XAUUSD/Binance) · DESIGN (named-zone) · **Confidence:** High · **Status:** PASS

## 6. Authority
**Response.**
- The Corpus SSOT (`corpus_store.load` → `AdmittedCorpus`) stays the only entry point.
- It joins dataset identity (dataset registry), content identity (sha256 of the bytes), and clock + producer (clock registry record keyed by the admitted path and **sha-checked**, as `require_reviewed_clock` does today).
- It exposes `AdmittedCorpus.clock` (a `ClockContract`) and `provenance()["clock"]`.
- No research module reads the clock registry or picks a conversion. `require_reviewed_clock` keeps running, but **inside** the SSOT load.

**Evidence:** `corpus_store.py:474-531` (`AdmittedCorpus`, `provenance()`); `backtest_v2.py:1071`, which today calls the clock gate separately after the SSOT load.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 7. Normalization semantics (exactly once, machine-checked)
**Response.**
- Normalization happens in `AdmittedCorpus.frame()` / `.records()` / the `CandleLoader` stream.
- `AdmittedCorpus` gains `clock_state` ∈ {`source`, `canonical_utc`}. `to_canonical_utc()` accepts only a `source` view and returns a `canonical_utc` view. A second call raises `DoubleNormalizationError`.
- Frames carry `df.attrs["timestamp_clock"]="UTC"`. `_view()` per-request objects inherit the state.

**Machine checks:**
- **(a)** A unit test proves the second call raises.
- **(b)** A static scan, extending `tests/test_corpus_ssot.py` §E, finds no source-clock conversion primitive (`mt5_server_to_utc*`, `wall_offset` math, `tz_localize(...America/New_York...)`) outside `clock_contract.py` / `corpus_store.py`. It covers `src/`, `scripts/`, `tools/` and root.
- **(c)** Admission and integrity checks keep running on the source clock before normalization. They describe the artifact.

Canonical values are **naive UTC**, not tz-aware. Tz-aware values would change every timestamp string in events and ledgers and every naive-vs-aware comparison. The repo already uses "naive-UTC" (`dataset_integrity.py:154`).

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 8. New role of `session_timestamp_basis`
**Response.** The key stays, strict and required, so all 12 configs keep loading. Its meaning becomes **"which clock session/hour semantics are evaluated on"**. It is no longer "convert timestamps".
- `utc_corrected` → session semantics consume **canonical UTC** as provided by the corpus. Nothing converts.
- `broker_local` → the legacy research arm: session semantics are evaluated on the corpus **source wall clock**, obtained from `AdmittedCorpus.clock` via `source_wall_time`. For a UTC corpus that is identical to UTC, so it is harmless.

The double-conversion guard (`require_basis_compatible`) is removed because it cannot fire any more. The reviewed-clock gate stays. The `_comment_session_timestamp_basis` text in configs is rewritten to the new meaning.

**Evidence:** current semantics are at `feature_pipeline.py:125-142` and `clock_registry.py:324-345`.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 9. Session/calendar semantics
**Response.** There are two distinct contracts.
- **Session windows** (`crt_engine.session_windows`, `feature_pipeline.session_windows_utc`) are authored in UTC (their own comments say so). They now compare directly against canonical UTC. `exchange_session_windows` converts UTC to each session's own IANA zone.
- **Market calendar.** A new production-config section `market_calendar` defines `by_asset_class`. Each entry is `{timezone, day_start, week_start_weekday}`:
  - `fx_metals`: `America/New_York`, `17:00`
  - `crypto`: `UTC`, `00:00`

  The asset class comes from the **existing** classifier in `dataset_integrity.session_calendar` (`crypto_quote_suffixes`, `metals_prefixes`). No second classifier is added.

  It drives: `day_of_week`, D1/H4/H1 grids, W1/MN1 keys, PDH/PDL, weekly range, carry rollover days and the oracle's day difference.

  `calendar_wall_time(utc) = local(tz) + (24h − day_start)`. That is NY + 7h for fx_metals, which reproduces today's broker grid exactly (the §1 0-mismatch result). F-080's H4 grid stays valid.

The calendar is never derived from the broker. It is declared for the market.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 10. DST semantics
**Response.**
- DST is represented only as `dst_policy: iana:<zone>` + `wall_offset`.
- `broker_clock._ny_is_dst_on_date` (a date-at-noon lookup with hard-coded 3/2 hours, `broker_clock.py:49-74`) is superseded by zoneinfo instant rules in `clock_contract.py`. The old functions are kept as thin delegating wrappers (archive rule, nothing deleted) and are scan-blocked outside the boundary.
- Ambiguous or nonexistent local instants raise; they never round.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 11. Unknown/unreviewed corpus behaviour (preserved)
**Response.** Existing intent is kept unchanged:
- No record, a sha mismatch or `user_reviewed=false` → `ClockProvenanceError`. There is no environment escape hatch.
- The detector verdict is advisory only.
- `UNKNOWN` is illegal for a reviewed record.

New, but explicit: `to_canonical_utc` on a corpus without a reviewed contract raises the same error. It **never** defaults to UTC.

Test harnesses keep `declare_in_process` / `declare_tree_in_process` (`tests/conftest.py:41-91`), and the floor test still forbids them in `src/`. Production still refuses unreviewed BNB/BTC/EURUSD M15.

**Classification:** FACT (current) · DESIGN (normalizer rule) · **Confidence:** High · **Status:** PASS

## 12. Dataset registration
**Response.** No new registry.
- `dataset_identity_registry` stays identity authority: `dataset_id`, `symbol`, `source_family`, artifacts and their sha.
- The clock registry stays the clock + producer authority per artifact sha. It covers all 227 corpora; only 3 have dataset records.

The 9 questions are answered by the **SSOT join**, `AdmittedCorpus.provenance()["clock"]`. It returns `dataset_id, instrument, broker, feed, storage_basis, timezone, dst_policy, canonical_timezone="UTC", contract_version`.

Dataset-schema change, additive (needs your sign-off because `CORPUS_AUTHORITY.md` is FROZEN v1.0.0):
- the `clock_basis` field is documented as a legacy alias (`broker_local` ⇔ source clock ≠ UTC);
- a consistency check is added: the dataset record's `clock_basis` must agree with the clock-registry kind of its canonical artifact.

No clock facts are duplicated into dataset records.

**Evidence:** `dataset_identity.schema.json` currently has `clock_basis` enum [`broker_local`, `utc_corrected`, `UNKNOWN`], which mixes concept A with a transform.

**Classification:** DESIGN · **Confidence:** Medium (frozen-doc amendment) · **Status:** PARTIAL

## 13. Derived corpus/window lineage
**Response.** A derived corpus records:
```
{parent_dataset_id, parent_corpus_sha256, derived_corpus_sha256,
 window_start_utc, window_end_utc, selection_rule, clock_inherited_from: parent sha}
```
- The window is cut on **canonical UTC** from the parent's `canonical_utc` view.
- It is written with `source_timestamp` (raw) as the timestamp column, so its bytes are a true subset of the parent's.
- Its clock is **inherited** by an in-SSOT lookup through the `.parent.json` sidecar. No new review is needed. The sidecar's parent sha must match a reviewed parent.

**Today's defect fixed by this.** `unified_replay_harness._materialize_month_window_csv` (`:69-98`) writes the window under the output dir. Under pytest that dir is inside the tmp tree that `conftest` declares **UTC**, so XAUUSD windows were judged UTC: wrong clock, then double conversion. In production the window has no record and is refused.

**Classification:** DESIGN + FACT (defect) · **Confidence:** High · **Status:** PASS

## 14. Timestamp consumer audit
Classes: **1** corpus normalization · **2** session/calendar · **3** duplicate/incorrect · **4** test-only · **5** unknown

| Site | Today | Class | Migration |
|---|---|---|---|
| `feature_pipeline.compute_context:763-769` (hour/session) | own MT5→UTC | 3 | UTC hour; legacy arm via contract |
| `feature_pipeline:756` `day_of_week` | raw broker dow | 2 (implicit) | calendar contract |
| `crt_engine_v2._session_name_at:3440` | own MT5→UTC | 3 | read UTC |
| `crt_engine_v2.score_time:2133-2139` | **raw** `.time()` vs UTC windows | 3 (**inconsistent under v7**, the clock_registry docstring's surface #1) | read UTC (behaviour fix) |
| `broker_clock.exchange_sessions_at:161` | always MT5→UTC, even for UTC corpora | 3 | take UTC |
| `semantics/market/conditions.py:165` | own MT5→UTC | 3 | read UTC |
| `backtest_v2:1071` clock gate · `:1437-1439` · `:887-896` · `:4704` | gate + raw hour/dow/week | 1 / 2 | gate into SSOT; hour=UTC, dow/week=calendar |
| `features/calendar_periods.py:67-105` · `parent_candle.py` · SMC PDH/PDL (`feature_pipeline:1410`) | floors raw | 2 (implicit) | `calendar_wall_time` |
| `research/resample.py:84-92` · `mother_range/geometry.py:56` · `weekly_sweep/weekly_range.py` · `hypotheses/weekly_sweep_reversal.py` | floors raw | 2 (implicit) | calendar |
| `research/forensics.py:77` · `conditional_entropy_grid.py:40` · `oracle/labeler.py:152` | raw hour/dow/date | 2 | UTC hour / calendar day |
| `semantics/execution/carry.py:40,79` (swap days) | raw date | 2 | calendar |
| `engine_runner.py:992` (daily counters) | raw date | 2 | calendar |
| `research/mt5_cost_calibration.py:328` | MT5 server epoch read `utc=True` | 3 (F-066 class) | contract |
| `governance/identity_spine.py:147,157` | aware → **machine-local tz** | 3 (machine-dependent bar keys) | aware → UTC |
| `dataset_integrity` / `session_autoderive` / `clock_detector` | raw source clock at admission | 1 (correct: they describe the artifact) | keep |
| `inout/live_rail/tickdb_adapter.py:35-48` | clock gate + basis | 1 | contract via record |
| `live_engine_hook:705`, `ultron_live_adapter:70` | `datetime.now(utc)` | n/a (wall clock, not corpus) | keep |
| `research/ohlcv_probe_report.py:50`, `ohlcv_open_close_label.py:95` | `astimezone(utc)` on MT5 probes | 5 | inspect during implementation |
| scripts: `build_bar_matrix`, `oracle_pattern_scan`, `mc_cpr_l0_residual_harness`, `xauusd_excel_feature_state_trace`, `session_filter_funnel_probe`, `tools/xau_chart/xau_10d_features` | call `mt5_server_to_utc` | 3 after migration (**would double-convert**) | drop the conversion; the scan enforces it |
| `tests/conftest.py:41-91` | in-process clock mocks | 4 | keep; plus §13 inheritance |

**Classification:** FACT (grep-verified sites) · **Confidence:** High for listed sites; scripts beyond the grep are UNVERIFIED until the §7 scan runs · **Status:** PARTIAL

## 15. Minimum migration (ordered)
1. **Freeze the contract (no behaviour change):**
   - `docs/governance/CORPUS_CLOCK_CONTRACT.md`
   - `docs/governance/corpus_clock_contract.schema.json`
   - clock registry schema 2.0.0 + `clock_kinds`
   - `market_calendar` config block on all configs carrying `feature_pipeline` (hash-neutral, not `params`)
   - impact manifest `CH-corpus-clock-contract-v1`
2. **`clock_contract.py` + `market_calendar.py`** (pure functions, scalar twins), with the parity test against `broker_clock` over the full corpus.
3. **SSOT.** `AdmittedCorpus.clock` / `clock_state`. `frame()`, `records()` and the CandleLoader stream emit UTC `timestamp` + `source_timestamp`. The clock gate moves inside the load.
4. **Consumers.** Migrate every row of §14 classes 2 and 3. Remove the per-module conversions and redefine `session_timestamp_basis` (§8). Replace the guard.
5. **Derived windows.** Lineage + inheritance (§13).
6. **Live.** `tickdb_adapter` normalizes through the contract (paper rail only, F-073).
7. **Tooling.** Charts/TV forensic/xau_chart use `source_timestamp` where they compare with broker-time screenshots.

No other systems are touched. The schema dimension and vector order are unchanged.

**Classification:** DESIGN · **Confidence:** Medium-High (large blast radius, by user choice) · **Status:** PASS

## 16. Acceptance tests (`tests/test_corpus_clock_contract.py`)
- **A.** XAUUSD raw `2026-01-15 10:00` → `08:00` UTC; `2026-07-15 10:00` → `07:00`. Full corpus equals `broker_clock` (0 mismatches).
- **B.** Binance `BNBUSDT_M5` UTC → values unchanged, `clock_state=canonical_utc`.
- **C.** DST: the US spring and fall transition weeks, plus the US/EU mismatch weeks (2025-03-10..27, 2025-10-27..31), convert correctly. Sunday ambiguous/nonexistent instants raise.
- **D.** Synthetic broker on `Europe/London` with crypto calendar UTC, and XAUUSD with calendar NY-17:00. Sessions follow the session/calendar contract, not the corpus zone.
- **E.** A second `to_canonical_utc` raises. The static scan finds no conversion primitive outside the boundary (with a negative control).
- **F.** A replay window inherits the parent clock (sha-linked). A window under the pytest UTC tree is still MT5 (regression for §13).
- **G.** `provenance()` dataset_id/sha and the clock block come from the same `AdmittedCorpus`. A sha mismatch invalidates the clock.
- **H (regression).** The XAUUSD feature vector is **bit-identical** to the current pin: hour/session already UTC under v7; dow, HTF and PDH come from the calendar = old broker grid. HTF parent OHLC groups are identical. Only timestamp labels move.

**Classification:** DESIGN · **Confidence:** High · **Status:** PASS

## 17. Implementation discipline
**Response.** The contract is frozen first (§15 step 1). Then the minimum code. Then tests are updated to the frozen semantics. Each currently failing test is re-read: if it encodes broker-time or legacy-identity behaviour, it is updated or given its explicit identity. Correct current behaviour is never reverted to get green. **Decided:** the sweep/retrace certification tests inject the legacy keys for the FM they certify, and FM-090..093 / FM-096 certification is checked and added if missing.

**Classification:** DESIGN · **Status:** PASS (process)

## 18. Re-run plan and expected outcome
| Group | n | Expected |
|---|---:|---|
| Clock guard (H_ingestion ×7, resample parity ×3, dataset_integrity ×2, heavy ×13) | 25 | **fixed**: identity normalization for UTC; windows inherit MT5 |
| Session/hour assertions (entry_chain ×5, tp1 ×2, warmup, hour cert ×2, session cert ×2) | 12 | re-read each. Certification tests take the legacy arm explicitly or move to UTC semantics. **Entry-chain/tp1 trade expectations re-measured**, because `score_time` becoming UTC can move trades (reported, not hidden) |
| Sweep | 7 | fixed by explicit identity |
| Retrace | 2 | fixed by explicit identity |
| Unrelated baseline | 14 | **untouched**, reported |

Report as `fixed / remaining attributable / unrelated baseline`. Also run:
- the governance floor (`check_governance_invariants.py --all`): accept only the 8 baseline reds + 1 v9 red;
- `test_corpus_ssot.py`;
- an XAUUSD backtest before/after, with the trade diff explained.

**Classification:** DESIGN (outcomes predicted, not measured) · **Status:** PARTIAL until run

## 19. Final frozen contract (summary that goes into CORPUS_CLOCK_CONTRACT.md)
| Fact | Answer | Owner |
|---|---|---|
| Corpus identity | dataset_id or `sha256:<hex>` of bytes read | Corpus SSOT (F-119) |
| Broker/feed | `producer` block on the clock record; `UNKNOWN` allowed, never guessed | clock registry |
| Raw clock | `storage_basis` via clock kind | clock registry (`clock_kinds`) |
| Timezone | IANA `timezone` + `wall_offset` | clock kind |
| DST | `iana:<zone>` only, no seasonal offsets | clock kind |
| Canonical time | UTC, normalized once in the SSOT, `clock_state` guarded | `clock_contract.py` via SSOT |
| Session time | UTC windows / per-session IANA exchange windows | session config |
| Calendar | `market_calendar[asset_class]` {tz, day_start, week_start} | production config |
| Derived data | parent dataset/sha + window in UTC + inherited clock | SSOT sidecar |
| Unknown/unreviewed | refuse (`ClockProvenanceError`), never default to UTC | clock gate inside SSOT |
| Duplicate normalization | `clock_state` type guard + static scan + parity test | tests |

Records to write: finding **F-120** (or the next free id; check at write time), the CLAUDE.md row, the findings export, the completion manifest, the `assistant_project.md` SESSION LOG, and a memory note. No commit unless asked.

## Critical files
- **New:** `src/data_ingestion/clock_contract.py`, `src/features/market_calendar.py`, `tests/test_corpus_clock_contract.py`, `docs/governance/CORPUS_CLOCK_CONTRACT.md` (+ schema).
- **Edit:**
  - data ingestion: `corpus_store.py`, `clock_registry.py` (+ registry JSON 2.0.0)
  - features: `broker_clock.py` (delegating), `feature_pipeline.py`, `calendar_periods.py`, `parent_candle.py`
  - engine/runtime: `crt_engine_v2.py`, `backtest_v2.py`, `unified_replay_harness.py`, `tickdb_adapter.py`
  - research and other: `semantics/market/conditions.py`, the research rows of §14, `identity_spine.py`
  - scripts: the 6 conversion scripts
  - configs: all `feature_pipeline` configs (`market_calendar` + comment text)
  - schema: `dataset_identity.schema.json` (consistency only)
- **Reuse:**
  - `clock_registry.require_reviewed_clock` / `declare_in_process`
  - `broker_clock.parse_exchange_session_windows`
  - `dataset_integrity.session_calendar` asset classifier
  - `corpus_store._view` / `provenance`

## Verification
1. `tests/test_corpus_clock_contract.py` A–H green; full-corpus parity 47,275/47,275.
2. XAUUSD freeze-pin vector SHA unchanged (H). HTF parent OHLC identical to before.
3. Backtest (`backtest_v2.py --csv data/mt5/XAUUSD_M15.csv`) before/after: same bars, timestamps shifted to UTC. Any trade diff traced to the `score_time` fix.
4. The §18 groups re-run with the attribution table.
5. `test_corpus_ssot.py` green; governance floor = 8 baseline + 1 v9 only; `construction_protocol.py validate-completion` on the manifest.
