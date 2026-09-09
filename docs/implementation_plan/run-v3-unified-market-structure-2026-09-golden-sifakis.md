# v4 — Dual-Construction CRT Trace (engine ↔ ontology, per bar)

## Context

`v3_unified_market_structure_2026_09` records the **engine's** CRT state per bar
(`crt_engine_v2.py`, the execution authority). The repository *also* carries a completely
independent declarative construction — `configs/formulas/market_crt_states.yaml` +
`features/crt_state_resolver.py` — that describes what each state *means* as predicates over
declared feature states.

**These two disagree substantially and nobody can see where, per bar.** F-069 measured 88.16%
agreement as a one-off study; F-086 measured the dwell gap (resolver RANGE 21,745 vs engine
RANGE 35,159). Today that comparison exists only as offline scripts replaying a saved
`events.jsonl`.

**Goal:** make the comparison a first-class, configurable, per-bar artifact — engine state,
ontology state, and *why each construction arrived there* — so "where and why do the execution
authority and the semantic authority diverge?" becomes a query instead of a research project.

This is **observation-only**. It grants no authority (§6.5), changes no decision, and does not
make the JSON a semantic authority (§6.6 — the ontology YAML stays authority #1 for meaning).

### Decisions taken (user, this session)
1. **Separate parallel stream** — do not mutate v3's frozen `schema_version: 1.0.0` record or
   F-097's registered evidence artifact.
2. **Trace depth = labels + agreement + engine transition + gating threshold** — answers *why*
   they differ, not just *that* they differ.
3. **Config gates the comparison layer only** — ontology thresholds are NOT overridable from
   production JSON (that would invert §6.6 authority).

---

## Design

### New config section (hash-neutral)

`configs/production/v4_dual_construction_2026_09.json` = byte-copy of v3 + one new top-level
section. `params` untouched ⇒ **same `config_hash`**, same `_validate_override_keys` blindness
that made v3 hash-neutral.

```jsonc
"crt_construction_trace": {
  "enabled": false,                       // default OFF, like bar_structure_snapshot
  "authority": "OBSERVATION_ONLY",
  "decision_neutral": true,
  "output_dir": "logs/crt_construction",
  "filename_suffix": "_crt_construction.jsonl",
  "flush_every": 500,
  "ontology_source": "configs/formulas/market_crt_states.yaml",  // names it, never overrides it
  "injection": "none",                    // HARD-PINNED; see Risk 1
  "record_engine_gates": true,            // the try_* transition detail
  "emit_on_warmup_bars": true
}
```

### New module — `src/runtime/crt_construction_trace.py`

Mirror `bar_structure_snapshot.py`'s invariants verbatim (default-off, emitted **after**
`process_candle` returns, return value consumed by nothing) and `SweepTraceLogger`'s shape
(`__init__(run_id, instrument)` / `emit(...)` / `close()`, `sweep_trace_logger.py:176-360`).

One JSONL row per bar, keyed `run_id` + `bar_index` so it **joins 1:1 to the v3 snapshot**:

| group | fields |
|---|---|
| identity | `run_id`, `instrument`, `bar_index`, `timestamp`, `corpus_sha256`, `ontology_version` |
| engine | `engine_state_before`, `engine_state_after`, `engine_action`, `engine_reason` |
| ontology | `ontology_state`, `ontology_feature_states` (the 15 declared states), `ontology_predicate_hits` |
| comparison | `agree` (bool), `divergence_pair` (`"ENGINE:X\|ONTO:Y"`) |
| construction | `engine_gates[]` — per attempted `try_*`: `{fn, from, to, passed, gate, threshold, observed}` |

### Engine hook — additive, default-None sink

The 8 transition attempts (`crt_engine_v2.py`: `try_range_to_sweep` :1056,
`try_range_to_shadow_pending` :1068, `try_shadow_pending_to_expansion` :1081,
`try_sweep_to_displacement` :1107, `try_displacement_to_expansion` :1434,
`try_expansion_to_retest` :1606, `try_retest_to_execution` :1830,
`try_execution_to_resolution` :1840) each append one record to `self._construction_sink`
**only when that sink is not None**. Default `None` ⇒ zero allocation, zero behavior change.

This is the only production-code change, and it is the price of "which threshold gated it" —
`action["action"]`/`["reason"]` already tell us what *fired*, but say nothing about what was
*attempted and refused*, which is exactly where engine/ontology divergence lives.

### Resolver wiring — the load-bearing constraint

Call `CRTStateResolver.resolve(features, timestamp, htf_id=...)` per bar with the canonical
vector `backtest_v2` already builds (`:1889-1890`, indexed by `self.feature_ts_to_idx` `:1859`).

**Never pass `engine_state_to` or `engine_reset`.** Both are marked *"Research-shadow only"* in
`crt_state_resolver.py:434-442` and inject the engine's answer into the resolver. F-069 records
that the historical instrument ran with unconditional injection, producing 64–99% figures that
"never measured configuration alone." The existing sweep already pins `injection="none"`
(`crt_parity_sweep.py:228,247`) — match it.

### Classification stays offline

Do **not** move `classify_mismatch` / `aggregate_categories` / `CATEGORY_PRECEDENCE`
(`scripts/research/crt_parity_classifier.py:92,176,316`) into `src/` — §3.1 forbids production
logic in `scripts/`, and the inverse move would drag research taxonomy into the runtime. The
emitter records **raw facts**; an offline reader feeds them to the existing classifier.

---

## Risks / pre-declared expectations

1. **Injection must be OFF or the whole artifact is vacuous.** Enforce with a test asserting the
   resolver is constructed and called without those kwargs. Highest-severity risk here.
2. **Resolver EXECUTION/RESOLUTION will be 0 by construction.** `market_crt_states.yaml`'s own
   header: the shadow's EXECUTION gate fail-closes without a risk-score feature, which the
   pipeline vector does not carry. So those two states will show 100% disagreement — *expected,
   not a defect*. Pre-declare it, or it will be "discovered" as a false finding.
3. **9 vs 12 states.** The YAML defines 9 M15 states; F-075 added 3 parent states as a disjoint
   sub-graph. The comparison covers the 9 only; parent-CRT is already in the v3 snapshot.
4. **Cost.** Per-bar resolver + gate records on 47,275 bars. Measure before defaulting anything on.
5. **F-065 pre-existing:** `volume_spike` is declared in `feature_states` but referenced by no
   state's `when:` block. Do not fix silently — it is an OPEN finding.
6. **SEM id:** allocate through the Semantic OS registry; do **not** invent one (§6.7).

---

## Verification

1. **Decision neutrality (load-bearing).**
   `python scripts/analysis/v3_config_parity.py --instrument XAUUSD --keep` must stay **PASS**
   with `events.jsonl` 1,871,819 / `crt_telemetry.jsonl` 1,671,551 bytes — unchanged from today.
   Add v4 arms (trace OFF, trace ON) and require byte-identity across all of them.
2. **Same on the out-of-sample corpus** — `--csv data/XAUUSD_W2026-07-07-to-2026-08-06.csv`
   (89,388 / 80,718 bytes).
3. **Sink-None proof:** with `enabled:false`, assert `_construction_sink is None` and that no
   `logs/crt_construction/` file is created.
4. **Non-vacuity:** trace rows == corpus bars; `engine_gates` non-empty on ≥1 bar; both
   constructions produce ≥2 distinct states.
5. **Injection-off assertion** (Risk 1) and **agreement sanity**: overall agreement should land
   near F-069's 88.16% on the full corpus. A wildly higher number means injection leaked back in.
6. `pytest tests/test_bar_structure_snapshot.py` stays 11/11.

## Out of scope

No promotion, no `ACTIVE_VERSION` change, no ontology-threshold override, no findings-doc edit.
v3 and v4 both stay REGISTERED. Cleanup of `data/XAUUSD_W2026-07-07-to-2026-08-06.csv` and the
stale `test_bar_structure_decision_neutrality.py` doc reference remain separate open items.

---

## Prior work completed this session (context for the above)

v3 parity verified PASS on both corpora; two defects found and fixed:
- **`crt_reject_reason` was structurally unpopulatable** — snapshot read `result["reject_reason"]`,
  which nothing ever wrote. Fixed at 5 `FILTER_REJECTED` sites + the consumer. Now 0/19 bars
  missing a reason (was 19/19). Ledger byte-identical.
- **RANGE double-count documented** — `on_reset()` (`:580`) increments RANGE unconditionally, so
  `state_entry_counts["RANGE"]` means "entered-or-re-entered", not "distinct episodes".
  Comment only; counter behavior deliberately unchanged.
