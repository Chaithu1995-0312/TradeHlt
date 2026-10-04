# Cross-family run join — interpreter schema addition (DRAFT)

> Status: **DRAFT** — schema + join tests only. No `InterpreterReading` / `observe()` wiring in this change.
> Approved direction (2026-09-16): Option 1 (canonical `run_id` everywhere) + Option 2 (`(instrument, bar_ts)` secondary).
> F-101: join by **recorded alias only**; never collapse mint sites by clock arithmetic.
> Related: `docs/implementation_plan/cost-model-identity-stamping.md` (cost identity — separate),
> `src/runtime/backtest_v2.py` `_canonical_run_id` (UTC `run_YYYYMMDD_HHMMSS`),
> `src/runtime/layer_trace.py` `mint_run_id` / `preexisting_run_ids`.

## 1. Gap (locked)

No family carries a link to another family's `run_id`.

| Family | `run_id` | `bar_ts` / equivalent | `instrument` |
|---|---|---|---|
| Layer-trace | yes (`lt_…`, also embedded in `trace_id`) | `bar_ts` | yes |
| Interpreter | **no** | `observation_time` (also in `trace_id` HHMMSS) | **nullable** (`ctx.get(..., "UNKNOWN")` in adapter only) |
| Opportunity | yes (scan-pass; not yet `_canonical_run_id`) | `timestamp` | yes |

Shared today across all three: **bar time only**. Everything else is family-specific.
The three `trace_id` meanings stay distinct — this draft adds a **separate** link field.

## 2. Decision

**Primary join:** recorded `run_id` (same string on all artifacts of one session/pass).
**Secondary join:** `(instrument, bar_ts)` with family field aliases:
- layer-trace `bar_ts`
- interpreter `observation_time`
- opportunity `timestamp`

**Not in scope here:** changing any `trace_id` format; Option 3 `correlation_id`; implementing CH-cost-model opportunity stamp (noted as dependency).

## 3. Proposed interpreter schema addition

### 3.1 `InterpreterReading` (additive fields)

```python
@dataclass
class InterpreterReading:
    events: list[InterpreterEvent]
    confidence: float
    trace_id: str                 # UNCHANGED family meaning: {NAME}-v{version}-{YYYYMMDD-HHMMSS}
    observation_time: datetime    # UNCHANGED: last bar ts
    schema_version: str = SCHEMA_VERSION
    unknowns: list[str] = field(default_factory=list)
    failure_conditions: dict = field(default_factory=dict)
    # --- DRAFT ADDITIONS (provenance / join keys; NOT decision inputs) ---
    run_id: str = ""              # required non-empty at validate-time once wiring lands
    instrument: str = ""          # required non-empty; never "UNKNOWN" once wiring lands
```

**Contract notes (must land with wiring, not with this draft alone):**

1. **Provenance only** — same class as `trace_id` in `Signal.meta`. Identity-blind detect/fusion must not branch on `run_id` / `instrument` / `name` / `family`.
2. **Purity** — `observe(window, features, ctx)` remains a pure function of `(window, features, ctx)`. `run_id` and `instrument` are read from `ctx` (fail-closed), never wall-clock.
3. **Frozen-surface conflict** — `contract.py` currently says "do not extend the contract surface". This draft **is** a governed surface extension; wiring requires an explicit contract-version bump (`SCHEMA_VERSION`) and topic-doc update.
4. **Adapter today** — `instrument = ctx.get("instrument", "UNKNOWN")` on `Signal` only. Target: stamp non-nullable `instrument` + `run_id` on the **reading**, then copy both into `Signal.meta` (and keep `Signal.instrument` populated from the reading, not a soft default).

### 3.2 `ctx` keys (wiring checklist — not implemented in this draft)

| Key | Rule |
|---|---|
| `ctx["instrument"]` | required non-empty str |
| `ctx["run_id"]` | required non-empty str — the **recorded** run id for this session (prefer layer-trace `run_id` / backtest `_canonical_run_id` as stamped; do not mint a fourth id inside the interpreter) |

`BaseInterpreter.observe` (future):

```python
run_id = str(ctx.get("run_id") or "").strip()
instrument = str(ctx.get("instrument") or "").strip()
if not run_id:
    raise InterpreterError("ctx['run_id'] required (fail-closed; cross-family join key)")
if not instrument:
    raise InterpreterError("ctx['instrument'] required (fail-closed; cross-family join key)")
# ... existing observe ...
reading = InterpreterReading(..., run_id=run_id, instrument=instrument)
```

### 3.3 Call sites to update when wiring (inventory)

| Site | Today | Needed |
|---|---|---|
| `interpreters/contract.py` `InterpreterReading` / `_validate` / `observe` | no fields | add + fail-closed |
| `interpreters/adapter.py` | soft `UNKNOWN` | use `reading.instrument`; put `run_id` in `Signal.meta` |
| `scripts/research/qualify_interpreter.py` | preview `trace=` | pass `ctx[run_id, instrument]`; print both |
| Interpreter unit tests | construct readings without keys | supply fixtures |
| Any direct `InterpreterReading(...)` constructions | none found outside contract | grep again at wire time |

## 4. Opportunity / layer-trace (dependencies, not this draft)

| Family | Change | Status |
|---|---|---|
| Layer-trace | none | already has `run_id`, `instrument`, `bar_ts`; aliases in `preexisting_run_ids` |
| Opportunity | stamp `_canonical_run_id` (or rename alignment) on header + rows when CH-cost-model identity work lands | **deferred** — scanner `run_id` remains pass-scoped until then |
| Join via aliases | if opportunity still has scan `run_id` ≠ `lt_…`, join only when an alias map records the link (F-101) | helper supports `alias_map` |

## 5. Join table (target)

| From → To | Primary | Fallback |
|---|---|---|
| Layer-trace → Interpreter | `run_id` | `(instrument, bar_ts == observation_time)` |
| Layer-trace → Opportunity | `run_id` | `(instrument, bar_ts == timestamp)` |
| Interpreter → Opportunity | `run_id` | `(instrument, observation_time == timestamp)` |

## 6. Artifacts in this draft

| Path | Role |
|---|---|
| `docs/implementation_plan/cross-family-run-join.md` | this doc |
| `src/research/cross_family_join.py` | pure join helpers (no I/O) |
| `tests/test_cross_family_run_join.py` | fixture-based join tests (pass on helpers today) |

## 7. Explicitly not done

- No edit to `InterpreterReading` / `BaseInterpreter.observe` yet
- No opportunity `_canonical_run_id` propagation yet
- No `query_trace --trace-id` work
- No collapsing of `lt_…` vs `run_…` vs logging `RUN_ID` into one mint site

## 8. Next approval gate

Wire interpreter `ctx` → reading fields + bump `SCHEMA_VERSION` + update `docs/topics/interpreter-contract.md` + adapter meta. Keep opportunity alignment behind CH-cost-model / explicit alias map.


## 9. Last-ran time of `run_id` (added 2026-09-16)

Every recorded `run_id` should persist **when it last ran**:

| Store | Path | Role |
|---|---|---|
| Upsert map | `logs/index/run_id_last_ran.json` | `run_id → {last_ran_at, first_ran_at, ran_count, source, instrument, artifact_path, started_at}` |
| History | `logs/index/run_id_last_ran.jsonl` | one line per `record_run_last_ran` call |

API: `utils.run_id_last_ran.record_run_last_ran` / `get_run_last_ran`.

Producers (wired):
- `opportunity_scanner` — `run_footer.last_ran_at` + index upsert; `OUTPUT:last_ran_at`
- `backtest_v2` — after `write_all`, records `_canonical_run_id` and layer-trace `run_id` if present

This is **not** a join key substitute for `run_id`; it is audit/lookup metadata for "when did this run_id last execute".
