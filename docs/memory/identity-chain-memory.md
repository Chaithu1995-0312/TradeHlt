# Identity Chain Memory (navigation)

> **Last generation:** 2026-09-23
> **Code-first:** `src/governance/identity_spine.py` + `src/governance/identity_chain.py` +
> `src/governance/measurement_basis.py` on conflict.
> **Changes:** `CH-identity-chain-closure-v1` (Phase 3 closed identity chain) →
> `CH-oracle-join-spine` (join identity, I8) → `CH-measurement-basis-declaration` (declared
> measurement basis + comparator, I9). Governance-only — `production_behavior_changed: NO`
> throughout. No decision-path, ontology-runtime, registry, or trading-math change.

## Purpose

Index the canonical bar-clock join layer that lets one bar of one run be traced,
by a single stable identity, across every observation-only stream that describes it:
the Spine journal (`trades.csv`), engine telemetry (`crt_telemetry.jsonl`), layer-trace
(L8), the Oracle labeler (`labels.csv`), and the bar-clock bridge (`bar_identity.jsonl`)
itself. A second layer, added 2026-09-23, answers the question the join alone cannot:
once two rows are known to be the SAME bar, were they measured under the SAME ruler
(cost model, tie-break, stop reference)? **Joinable is not comparable** — that gap is
`measurement_basis.py` / invariant I9.

## The problem this closes

Before this change, five streams named the same bar five different ways —
`bar_index` / `engine_candle_index` / `bar_idx` / `_pos` / `candle_index` /
`candle_open` for the position, and `timestamp` / `bar_ts` / `opened_at` /
`first_seen_ts` for the clock. Joins across layers were partial or silently wrong.
This is the identity-layer instance of the repository's recurring "skipped ≠ absent"
failure class (F-056, F-079, F-083, F-085): a join that quietly used the wrong key
looked identical to a join that used the right one.

## Responsibilities

- Declare the **one** canonical bar clock: frozen PK `(instrument, timeframe,
  bar_open_ts, corpus_sha256)`, `bar_open_ts` normalized to UTC `%Y-%m-%d %H:%M:%S`.
- Declare the alias spec (`INDEX_ALIASES`, `BAR_TS_ALIASES`) — every known synonym for
  bar position and bar timestamp across the five streams, in ONE place.
- Declare which joins are legal: `ALLOW_JOIN_BAR_OPEN_TS` only. `DENY_RAW_INDEX`
  (index-to-index across streams) and `DENY_POSITION_JOIN` (position-to-position) are
  explicit refusals, not omissions — the same fail-closed shape as the `CC-*` claim
  catalog's forbidden-join rule (§6.7).
- Declare the id-mint authority table (`ID_MINTS`) — who mints `run_id` / `trade_id` /
  `execution_intent_id`, so nothing is re-minted or collapsed. Trade-ID fork resolved
  as **Option A**: engine `CRT-{seq:04d}` stays the row `trade_id`; the journal uuid is
  a *derived* `execution_intent_id` (`TradeIdentityV1.new(alert_id=trade_id)`), 1:1, not
  a second identity.
- Mechanically verify the chain is actually closed via 9 invariants (`identity_chain.py`),
  exposed through a report-only CLI (`scripts/governance/identity_chain_check.py`).
- Declare the **measurement basis** vocabulary (`measurement_basis.py`) — 5 closed axes
  (`walk_kernel`/`cost_model_id`/`fill_model_id`/`tie_break`/`reference_level`) plus an
  alias table that canonicalises every known spelling of the same model onto ONE member,
  and a `can_compare()` comparator that is STRICTER than the pre-existing
  `identity.tokens.L5_BASIS` 3-axis equality — L5 equality alone cannot see a `tie_break`
  or `reference_level` mismatch, both of which measurably move the outcome number.

## Runtime role

**Observation-only, additive.** Not on the decision path. The bridge emitter writes a
per-run sidecar in `backtest_v2` post-run; the checker is a separate, later CLI step.
Nothing here computes a market quantity — it verifies identity joins only.

## The 9 invariants

| Inv | Name | Proves |
|---|---|---|
| I1 | `telemetry_envelope_uniformity` | every telemetry record carries non-empty `run_id`/`instrument`/`timeframe`/`corpus_sha256` |
| I2 | `accepted_lifecycle_completeness` | every lifecycle row has `candidate_id`; ACCEPTED rows also carry `trade_id` + `bar_ts` |
| I3 | `bridge_monotonicity` | the bar clock never runs backwards (DECISION_DISTANCE bar_ts and bar-identity rows both) |
| I4 | `trade_lifecycle_bidirectional` | every `trades.csv` `candidate_id` maps to exactly one lifecycle row |
| I5 | `strict_accepted_resolution` | every `ACCEPTED.trade_id` resolves to BOTH `trades.csv` AND its L8 row, on the SAME `bar_open_ts` |
| I6 | `l8_set_closure` | the L8 trade_id set equals the ACCEPTED trade_id set — nothing missing, nothing extra |
| I5/I6 exemption (2026-09-27) | `_post_commit_vetoed` | an ACCEPTED trade_id with an L5 `REJECT` row (same run, same trade_id) was vetoed after CRT committed it (drift / Phase-5 / EngineRunner). It must be absent from BOTH trades.csv and L8. With no L5 evidence, the invariant still FAILs |
| I7 | `label_provenance` | labels carry `dataset_hash`/`label_run_id`/`label_generated_utc` + a parseable bar timestamp |
| I8 | `label_trace_resolution` | every label's `(lt_id, bar_open_ts)` resolves to an L3 layer-trace row under that SAME `lt_id`; `trace_id`'s embedded timestamp agrees with its own `bar_open_ts`; exactly one `lt_id` per file (`CH-oracle-join-spine`) |
| I9 | `basis_declaration` | every outcome-bearing row's 5-axis measurement basis is a REAL declaration (closed-vocabulary member, never blank/free-text/explicit-`UNSTAMPED`), and `can_compare` returns a named verdict — never crashes — on every pair of distinct bases actually present. Unlike I8, a file may legitimately hold SEVERAL distinct bases (labels.csv carries 4 arms) — I9 does not require one basis per file (`CH-measurement-basis-declaration`) |

## Verdict modes — SKIP vs strict (the operational contract)

`check_run(..., require_all=False)` (default): CLOSED iff no invariant FAILs. An
invariant whose input stream was not supplied is `SKIP`, and **SKIP passes**. This is
correct for partial, step-by-step wiring (e.g. telemetry-only), but a partial run and a
fully-verified run are **not distinguishable from the exit code alone**.

`check_run(..., require_all=True)` (CLI: `--require-all`): CLOSED iff every invariant is
`PASS`. A SKIP is a violation. **This is the only mode that proves the chain is closed
end to end.** Use it once all five inputs are expected to be present (a real
`results/run_*` directory, not a step-by-step wiring check).

The CLI summary line always discloses partiality explicitly (`PARTIAL — N of 9 skipped,
not verified`) even in default mode, so `identity chain: CLOSED` can never be misread as
"all nine verified" by glancing at the exit code alone.

## Entry points

| Entry | Symbol / path |
|---|---|
| Key hierarchy, aliases, join table | `src/governance/identity_spine.py` · `INDEX_ALIASES` / `BAR_TS_ALIASES` / `JOIN_TABLE` / `ID_MINTS` / `resolve_bar()` |
| Bar-clock bridge emitter | `src/runtime/bar_clock_bridge.py` · `BarClockBridgeEmitter` / `BarClockConfig` |
| 7-invariant checker | `src/governance/identity_chain.py` · `check_run()` |
| CLI | `scripts/governance/identity_chain_check.py` (SITS `SCR-487`) |
| Bridge wiring | `src/runtime/backtest_v2.py` (post-run emit) |
| Telemetry envelope + ACCEPTED fields | `src/config_layer/crt_engine_v2.py` |
| Layer-trace L8 `trade_id` | `src/runtime/layer_trace.py` |
| Labeler lineage columns | `src/research/oracle/labeler.py` |
| Join spine (`lt_id`/`trace_id`/`bar_open_ts`/`engine_state_after`, I8) | `scripts/research/build_bar_matrix.py` · `src/research/oracle/labeler.py` (inherits) · `src/governance/identity_chain.py` (I8) |
| Measurement basis vocabulary + comparator, I9 | `src/governance/measurement_basis.py` · `canonicalise()` / `Basis` / `can_compare()` / `require_comparable()` |
| Basis producers | `src/research/oracle/labeler.py` (labels.csv, 4 cols) · `src/runtime/backtest_v2.py` (trades.csv, 4 cols + `sl_refloored`) · `src/config_layer/crt_engine_v2.py` (`intrabar_exits` public property) · `src/research/provenance.py` (required `tie_break` param) |

## Exit points

| Exit | Artifact |
|---|---|
| Bar-clock bridge sidecar | `results/bar_clock/{instrument}_bar_identity.jsonl` |
| Checker verdict | stdout table + `CLOSED`/`VIOLATED` summary line, exit 0/1 |
| Build manifest | `docs/governance/build_manifests/CH-identity-chain-closure-v1.{impact,completion}.json` |
| Build manifest | `docs/governance/build_manifests/CH-oracle-join-spine.{impact,completion}.json` |
| Build manifest | `docs/governance/build_manifests/CH-measurement-basis-declaration.{impact,completion}.json` |
| Ontology node | `configs/formulas/market_ontology.yaml` SEM-038 (+ SEM-015/017/018 refined in place, v1→v2) |

## Important contracts

1. **Only `bar_open_ts` (the frozen PK) is a legal cross-stream join key.** Index-to-index
   and position-to-position joins are explicitly denied (`JOIN_TABLE`), not merely unused.
2. **SKIP is not FAIL, but SKIP is not PASS either** — pick the verdict mode deliberately;
   do not read a bare `CLOSED` as proof of full coverage without checking for `PARTIAL`.
3. **No re-minting.** Engine `trade_id` and journal `execution_intent_id` are two names
   for a 1:1 derived relationship, never merged into one id or independently generated.
4. **Additive only.** New columns append; no existing column shifts position (`trades.csv`,
   L8 rows). This preserves every prior reader that indexes by position.
5. **No production authority.** No `ACTIVE_VERSION` change, no G001, no backfill of
   historic run hashes, no trading-math or decision-path change.
6. **Declared-equal is not actually-equal.** `identity.tokens.L5_BASIS`'s pre-existing 3-axis
   equality is INSUFFICIENT for comparability — `measurement_basis.can_compare()` is the
   stricter, authoritative comparator (5 axes); do not treat L5 equality alone as licensing
   a numeric comparison between two outcome-bearing rows.
7. **`canonicalise()` never guesses.** A blank, absent, or unrecognised spelling on any
   basis axis becomes `UNSTAMPED` — never inferred, never defaulted to a plausible value.
   `UNSTAMPED` is always a `can_compare` DENY.

## Reading order

1. This file.
2. `src/governance/identity_spine.py` (the alias spec + join table — read this before
   writing any code that joins two of these streams).
3. `src/governance/identity_chain.py` (the 9 invariants + verdict modes).
4. `src/governance/measurement_basis.py` (the 5-axis basis + `can_compare` — read this
   before writing any code that compares two outcome-bearing rows' numbers).
5. `scripts/governance/identity_chain_check.py` (CLI usage).
6. `governance-memory.md` for where this sits in the wider governance kitchen.

## Related documents

| Doc | Role |
|---|---|
| [`governance-memory.md`](governance-memory.md) | Parent governance domain memory |
| [`../architecture/run-identity-governance.md`](../architecture/run-identity-governance.md) | Predecessor: single traceable run identity (`CH-run-identity-range-folder-manifest`) |
| [`../reference/schemas.md`](../reference/schemas.md) | `bar_identity.jsonl` / join-spine / measurement-basis line schemas + additive column definitions (§9.18-§9.20) |
| [`../governance/build_manifests/CH-identity-chain-closure-v1.impact.json`](../governance/build_manifests/CH-identity-chain-closure-v1.impact.json) | Phase 3 closed identity chain change declaration |
| [`../governance/build_manifests/CH-oracle-join-spine.impact.json`](../governance/build_manifests/CH-oracle-join-spine.impact.json) | Join spine (C+D, I8) change declaration |
| [`../governance/build_manifests/CH-measurement-basis-declaration.impact.json`](../governance/build_manifests/CH-measurement-basis-declaration.impact.json) | Measurement basis declaration (I9) change declaration |

## Known coverage

| Scope | Status |
|---|---|
| `identity_spine.py` / `identity_chain.py` / `bar_clock_bridge.py` | Built + unit-tested (5 test files, 56 tests green as of the 2026-09-22 generation) |
| `identity_chain_check.py` | SITS-registered `SCR-487`, category `GOVERNANCE` |
| Invariant I5 against a real `results/run_*` execution | **TESTED 2026-09-27.** CORRECTED: UNTESTED -> the first real run (k23 `lt_20260924_194133`) FAILED I5/I6 on CRT-0024. That trade was vetoed post-commit by EngineRunner (`invalid_session:4.0`), but `backtest_v2` had already written its L8 row, so there were 28 L8 rows against 27 trades. Fixed: L8 is now written only after the gates, veto rows carry `trade_id`, and drift/P5 vetoes get L5 rows. Re-run `lt_20260926_185445`: I5/I6 PASS; ledger identical to the original apart from the random per-run ids |
| `docs/reference/schemas.md` `bar_identity.jsonl` line-schema entry | Added §9.18 (2026-09-22) |
| `CH-oracle-join-spine` (join spine C+D: `lt_id`/`trace_id`/`bar_open_ts`/`engine_state_after`, invariant I8) | Built + unit-tested (2 new/extended test files, 39/39 pass); real-corpus end-to-end run UNTESTED as of the 2026-09-22 generation |
| `CH-measurement-basis-declaration` (5-axis basis + `can_compare`, invariant I9) | Built + unit-tested (`test_measurement_basis.py` 42 tests + extensions across 5 test files, all green 2026-09-23); real-corpus end-to-end run UNTESTED |
| Parity — the DECLARE half (cost model / tie-break / stop geometry axes named + stamped) | **DONE** 2026-09-23 (`CH-measurement-basis-declaration`) |
| Parity — the UNIFY half (making the rulers agree, not merely naming them) | **NOT DONE** — deliberately deferred, breaking work that re-bases every existing outcome-bearing number in the repository (follow-up backlog) |

## Last generation timestamp

2026-09-23 (measurement basis declaration + I9 added same day)
