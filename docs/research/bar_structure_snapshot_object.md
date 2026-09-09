# Object: BarStructureSnapshot (SEM-035)

**Frozen 2026-08-29.** Change `CH-v3-unified-market-structure-v1`. Code
`src/runtime/bar_structure_snapshot.py`. Config section `bar_structure_snapshot` on
`v3_unified_market_structure_2026_09` (default **off**).

Observation only. Grants no authority (CLAUDE.md §6.5): observation earns *tunability*, never
*authority*.

---

## What the object is

One flat JSONL record per bar carrying the whole declared structural vocabulary at that bar:

| Block | Fields | Content |
|---|---|---|
| Identity | 17 | `run_id`, `instrument`, `corpus_sha256`, `config_version`, `feature_schema_hash`, `bar_index`, `timestamp_basis`, `phase`, … |
| Bar | 6 | OHLCV + `atr_abs` (**absolute** price units, not the close-relative FM-041 `atr`) |
| CRT | 20 | `crt_state_before/after`, action, reject reason, direction, range refs, sweep, displacement / retest indices, TTL, trade-open |
| Parent CRT | 8 | `parent_crt_state` ∈ {RANGE_C1, MANIPULATION_C2, DISTRIBUTION_C3}, bias, range refs, `parent_closed_this_bar` |
| HTF | 3 | `htf_state`, `htf_range_ratio`, thresholds |
| Objective | 6 | status, direction, target, invalidate-at, **plus the gate's own enabled/mode** |
| SMC zones | 4 × 11 | FVG / order block / breaker / mitigation: present, polarity, high, low, mid, formation index, age, width in ATR, inside, distance, window-truncated |
| Levels | 12 | PDH/PDL price + distance + day stamp; EQH/EQL presence + distance |
| CHoCH | 4 | value, **basis**, and the two canonical inputs it was derived from |

122 fields on a `LIVE` record, 23 on a `WARMUP` record. Machine contract:
[`docs/governance/bar_structure_snapshot_schema.json`](../governance/bar_structure_snapshot_schema.json).

## What is genuinely new — and what is only joined

Three things. Saying so explicitly is what stops this becoming a second source of truth:

1. **The CRT state is the ENGINE's.** `scripts/research/build_bar_matrix.py` already emits a
   per-bar CRT column, but from `features.crt_state_resolver`. F-069 measured 88.16% agreement;
   F-086 measured the dwell gap (resolver RANGE 21,745 vs engine 35,159). Joining the two on
   bar index stays `CC-L3-FORBIDDEN-JOIN`.
2. **Zone geometry.** Every `features.smc` detector builds a full `Zone` (`_geometry.py:32`) and
   the `*_distance` wrapper immediately collapses it to one tanh scalar. Edges, formation index,
   age, polarity and containment were computed on every bar and discarded.
3. **Run-scoped identity** — `instrument` + `corpus_sha256` + `run_id` + a gapless `bar_index`.

Everything else is joined from existing surfaces. If that delta reaches zero, extend
`build_bar_matrix` and delete this module rather than maintain two per-bar surfaces.

## Observation only — why the claim holds

- `bar_structure_snapshot.enabled` is **false** by default on v3.
- Emission happens **after** `CRTEngine.process_candle` returns; `emit()` returns `None`; no
  caller consumes its output; it mutates neither the engine state nor the result dict.
- **Proven, not asserted:** `scripts/analysis/v3_config_parity.py` runs the full XAUUSD corpus
  with emission ON and OFF and requires a byte-identical ledger. Measured: `events.jsonl` and
  `crt_telemetry.jsonl` byte-identical, **all 86 trade columns identical**, summary identical,
  while the ON arm wrote 47,275 rows (non-vacuity).

The same harness proves requirement 9 against `v2_htfcrt_2026_08`: identical on everything
except the `config_version` stamp, which *must* differ — a ledger recording the same version for
two different configs would be a provenance defect.

## Out of vector

Adds **zero** canonical dimensions. `CANONICAL_FEATURES` stays 48, `SCHEMA_HASH`
`f52bf5d3f2ae6ddb75e8a35e9c323e07`, `FEATURE_ORDER_HASH` `160c96c52b198a16`. Adding dimensions
would break the XAUUSD `vector_sha256` freeze pin and re-stale all six model families (F-076).

## Null semantics (the part most likely to be misread)

- `{f}_distance` is a float, **never null**. Exactly `0.0` means **no structure exists** — the
  `features.smc` convention — not zero distance.
- Every other `{f}_*` field is null **iff** `{f}_present` is false. No third state.
- `{f}_width_atr` is null (not 0.0) when `atr_abs <= 0`: an undefined width, the opposite of the
  distance convention.
- Parent / HTF / objective are all null when `parent_crt.enabled` is false. Null is "not
  observed" — never 0, never a default enum member.
- `{f}_window_truncated` is **window saturation**, true for all but the first ~100 bars. It is a
  warmup marker, **not** an exclusion criterion; `{f}_age_bars` against `smc_window_len` is what
  measures boundary proximity. Listed under the contract's `forbidden_metric_substitutions`.

## Identity is what the claim class rests on

`logs/crt_transitions.jsonl` cannot answer "what state was the engine in at bar i?" — it is
`CC-L3-GLOBAL-UNIDENTIFIED` because of an empty `instrument` and no RESET record. This stream
can, and `CC-CTX-RUN-SCOPED-OBSERVATION` grounds it — but only because the grounding check
verifies identity presence, one-run/one-corpus, and a **gapless** `0..N-1` index.

That check earned itself on its first real run: it refused the stream for a **one-bar hole at
index 77**, the backtest's initialisation bar, which `continue`s before the emit site. No unit
test in this program caught it. The sibling `CC-CTX-NOT-DECISION` refuses, always, the claim
that any of this influenced a trade.

## Cost

`_find_break_events` re-runs `detect_causal_swings(bars[:i], k)` per interior position, and
order-block / breaker / mitigation each called it independently — the same scan three times per
bar. Measured 4.39 ms/bar (≈208 s per corpus), ≈142 s of it duplication. The three detectors
now take an optional precomputed result, pinned bit-identical over 1,785 comparisons
(1,136 non-trivial) plus a mutation check that a *wrong* event list changes the answer, so the
equality assertions cannot pass vacuously.

## Storage

JSONL is the **system of record**; parquet is a regenerable projection and never a second
authority (`CC-PARQUET-PROJECTION`). Measured on XAUUSD: 173.5 MB JSONL → ~7.4 MB parquet
(zstd), partitioned by `crt_state_after` into the seven observed states plus a `__null__`
partition for warmup rows, `verify_projection` clean on all 47,275 rows. A projection that fails
verification is deleted rather than shipped.

## Not

Not `features.market_context.MarketContext` (a Layer-4 semantic-state grouping at a different
layer, already consumed by `build_bar_matrix`). Not the `crt_baseline_trace` bar record. Not a
`build_bar_matrix` row. Not `logs/crt_transitions.jsonl`. Not part of `CANONICAL_FEATURES`.

## Measured by

[`MC-CTXATTR-XAUUSD-M15-V1`](../../configs/research/measurement_contracts/instances/MC-CTXATTR-XAUUSD-M15-V1.json)
→ SEM-036 → [F-097](../current-findings.md).
