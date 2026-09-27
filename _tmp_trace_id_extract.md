======================================================================
docs\implementation_plan\using-trace-id-i-need-elegant-seahorse.md exists=True size=10733
# Look up a whole run by `run_id`, and everything about one bar by `trace_id`

## Context

The user wants two ways into backtest results:

- **`--run-id X`**: everything that happened in one run, grouped by layer (L0–L9), plus events,
  telemetry and trades.
- **`--trace-id X`**: every recorded observation for one bar of one run, across all outputs, so
  they can dig into any single result.

Measured facts this plan rests on (2026-09-16, read-only):

- **One run's outputs are scattered.** `results/run_20260916_101942_XAUUSD/` (folder named in
  local time) holds trades/events/telemetry/summary whose `run_id` is `run_20260916_044942` (UTC).
  The config dump lives in `logs/config_dumps/`. `layer_trace` writes to its own
  `output_dir` (`results/layer_trace_h2/`) under a fourth ID, `lt_20260915_165314_XAUUSD`. It
  records `runtime.ReportWriter.run_id=run_20260915_222314`, and that folder exists — so aliases
  can be linked by exact recorded strings, never by time arithmetic.
- **Each output numbers bars differently.** Checked on three trades and 19 rejections against the
  raw XAUUSD CSV:

  | Output | Bar field | Relation to raw CSV row (0-based) |
  |---|---|---|
  | `layer_trace` | `bar_idx` | equal (source: `candle_idx - 1`) |
  | `bar_structure`, `crt_construction` | `bar_index` | equal by source (`bar_index=candle_idx - 1`); confirm in tests |
  | `bar_matrix` / `features.parquet` | `_pos` | equal |
  | `trades.csv` | `candle_idx` | row + 1 |
  | `events.jsonl` | `candle_index` | engine counter, row − 62 on this corpus (not a rule) |

  **The timestamp is the only key every output shares.** That is why
  `trace_id = {run_id}:{instrument}:{bar_ts}` (the format `layer_trace` already writes) is the
  right bar key.
- `query_trace.py` already has: family globs, fail-closed projection selection, `--run-dir`
  scoping, and `assert_view_lineage` (refuses mixed `run_id`/`corpus_sha256`). Reuse all of it.

User decisions: read-only query tool first (no backtest code change); keep
`run_id:instrument:bar_ts`; also plan switching `layer_trace` on in a shadow config.

Task class: Phase A `OBSERVATION_ONLY` tooling; Phase B `OBSERVATION_ONLY` + a new shadow config
(active config and `ACTIVE_VERSION` untouched).

## Phase A — `query_trace.py` lookups (read-only)

### A1. New families
- `scripts/maintenance/jsonl_to_parquet.py` `FAMILY_DEFAULTS`: add
  `"_layer_trace.jsonl": ("layer", None)` so a run's spans can be converted to Parquet,
  partitioned by layer.
- `scripts/analysis/query_trace.py` `FAMILY_GLOBS`: add `layer_trace`
  (`results/**/*_layer_trace.parquet`, `logs/**/…`) and `trades`
  (`results/**/*_trades.csv`, canonical CSV, not a projection → add to
  `_NON_PROJECTION_FAMILIES`, admissible if the file has a `run_id` column).
- `src/utils/duckdb_query.py` `open_views`: if the path ends in `.csv`, use
  `read_csv_auto(...)` instead of `read_parquet(...)`. Small additive branch; cover in
  `tests/test_duckdb_query.py`.

### A2. Run resolver: `resolve_run(run_id) -> RunBundle`
In `query_trace.py`, next to `discover_projections`:
- Scan the family globs plus `logs/config_dumps/*_config.json` and `results/**/_summary.json`.
  Read only the `run_id` that each artifact records: first JSONL line, distinct `run_id` on the
  Parquet/CSV view, the summary key, the config-dump key.
- **Aliases, by recorded evidence only:**
  (a) `layer_trace.preexisting_run_ids` values;
  (b) files in the same `run_*` folder whose recorded `run_id` differs from the folder name
  (e.g. folder `run_20260916_101942` ↔ content `run_20260916_044942`), marked
  `link=colocated`.
  Never convert clock bases (F-101).
- `RunBundle = {query_id, linked_ids[{id, source, link}], identity{…from layer_trace or config
  dump: active_version, config_hash, schema_hash, corpus_sha256, code_sha, tree_dirty},
  artifacts{family: path}}`.
- Zero matches → exit 1 `RUN NOT FOUND`. Two unlinked bundles for one ID → refuse
  (existing `AmbiguousRunError`).
- Then reuse `select_projections` + `open_views` + `assert_view_lineage`, scoped to the bundle's
  paths. Extend `assert_view_lineage` so the alias set counts as one run.

### A3. `--run-id X`: run card
Sections, each printed with its source path and row count:
1. **Identity**: the linked IDs and identity block.
2. **Layers**: `layer_trace` grouped by `layer, plane, module, status` with counts, plus
   `--layer L3` / `--status REJECT` filters that list the matching spans. Without a
   `layer_trace` artifact: `layers: NOT RECORDED (layer_trace disabled for this run)` — a
   distinct state, never an empty table (F-079 silent-gap class).
3. **Events** by `event`; **telemetry** by `kind`.
4. **Trades and rejections**, each with its ready-to-paste `trace_id`, built from `opened_at` /
   the event `timestamp`.

### A4. `--trace-id RUN:INSTR:TS`: bar dossier
- Parse with `split(":", 2)`, because the timestamp itself contains `:`. Resolve the run
  (A2). Convert the timestamp to a raw CSV row from the run's corpus, and refuse if the
  corpus `sha256` differs from `identity.corpus_sha256`.
- Pull each output with the key that works for it:

  | Section | Key used |
  |---|---|
  | Layers (`layer_trace`) | `trace_id` equality (also checks `bar_idx == row`) |
  | Bar structure / CRT construction | `bar_index == row` |
  | Events | `timestamp == ts` |
  | Telemetry with `timestamp` | `timestamp == ts` |
  | Telemetry with only `candle_index` | translate via the same run's events (`candle_index ↔ timestamp`); if no event exists at that bar → `UNRESOLVED (no engine index anchor)` |
  | Episodes alive (`CANDIDATE_LIFECYCLE`) | `first_seen_idx ≤ i ≤ last_seen_idx` in engine numbering; basis checked in A6 before shown, else `UNVERIFIED` |
  | Trades | `opened_at == ts` or `closed_at == ts` |
  | Features (`bar_matrix_features`) | `timestamp`, only if `corpus_sha256` **and** `schema_hash` match the run, otherwise `REFUSED` with both hashes |
  | Research labels (`clean_labels`) | `timestamp`, labelled research cost world (not comparable to `pnl_rr_net`) |

- Every section prints exactly one of: `N rows` · `0 rows (key=…)` · `NOT RECORDED` ·
  `REFUSED (reason)` · `UNRESOLVED` · `UNVERIFIED`.
- Options: `--window N` (±N bars, same keys), `--json` (dossier as JSON for LLM use),
  `--section layers,events,…`.
- **Forbidden joins stay refused:** never shows `events.state_to` next to
  `crt_state_resolved` as the same thing (F-069, `CC-L3-FORBIDDEN-JOIN`). They are printed as two
  labelled rows.

### A5. Docs and registration (same turn)
- Module docstring USAGE block. `docs/research/parquet_evidence_layer.md` and
  `docs/reference/schemas.md` get a short "run_id / trace_id lookup" section with the bar-number
  table above.
- `query_trace.py` is already registered in SITS; re-run
  `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`
  only if the census flags a change.
- Governance: change class expected `TRACE_OBSERVATION_JOIN` (confirm against
  `docs/governance/change_contracts.json`) → impact manifest
  `docs/governance/build_manifests/CH-run-trace-lookup.impact.json` → `validate-impact` before
  editing → `validate-completion` after. SESSION LOG in `assistant_project.md`.

### A6. Tests: `tests/test_query_trace.py` (extend)
Build small fixtures in `tmp_path`: a run folder with `trades.csv`/`events`/`telemetry`, a
`layer_trace` file listing preexisting IDs, and a 20-row corpus.
- `resolve_run` links folder ↔ content ↔ `layer_trace` IDs from recorded strings only; an
  unrelated run with a timestamp 5h30m away is **not** linked.
- The `trace_id` parse survives `:` inside the timestamp.
- Each bar-number mapping in the table (trades +1, `layer_trace` equal, events via timestamp).
- Section states: missing `layer_trace` → `NOT RECORDED`; feature schema mismatch → `REFUSED`;
  telemetry with no event anchor → `UNRESOLVED`.
- A corpus `sha256` mismatch refuses the dossier.
- `bar_structure.bar_index == layer_trace.bar_idx` on the same bar.

## Phase B — switch `layer_trace` on in a shadow config (separate change, after A)

- New shadow config cloned from the active `v2_htfcrt_2026_08` with only a `layer_trace` section
  added (`enabled: true`, `output_dir` = results root, so the file lands next to that run's
  outputs). Top-level section → hash-neutral. `ACTIVE_VERSION` untouched, not promoted. Written
  by hand following the F-055 shadow pattern; **never** through `PromotionManager.promote_*`
  (memory: v1-base landmine).
- **The owed tracing on/off check:** XAUUSD backtest with the active config vs the shadow config
  → `trades.csv` and `events.jsonl` byte-identical after removing `run_id`; rejection set
  identical. Any difference = tracing is not observation-only → stop and report.
- Then `jsonl_to_parquet.py` on the new `layer_trace` file, and `query_trace.py --run-id` /
  `--trace-id CRT-0001's trace` end to end.
- Change class and impact manifest of its own (`CH-layer-trace-shadow-enable`).

## Out of scope (recorded, not done)
- Making the backtest mint one `run_id` and write `trace_id` onto events, telemetry and trades
  (fixes F-101 at the source; a later `src/` change).
- Cost stamp and intent-schema work: separate approved or pending changes. The dossier simply
  shows their columns once they exist.
- Any config promotion, `ACTIVE_VERSION` change, or G001 claim.

## Verification
1. Preflight: `git status --porcelain`; `venv/Scripts/python.exe -c "import sys;print(sys.prefix)"`.
2. `venv/Scripts/python.exe -m pytest -q tests/test_query_trace.py tests/test_duckdb_query.py tests/test_layer_trace.py tests/test_parquet_store.py`.
3. Real data, read-only:
   - `venv/Scripts/python.exe scripts/maintenance/jsonl_to_parquet.py` on
     `results/layer_trace_h2/XAUUSD_layer_trace.jsonl`, and on the events/telemetry of
     `results/run_20260915_222314_XAUUSD`;
   - `query_trace.py --run-id run_20260915_222314` → must link `lt_20260915_165314_XAUUSD`, show
     L0–L8 counts matching the measured 47,197 L4 / 47,178 L3 PASS / 19 L3 REJECT / 3 L5/L6/L8,
     and L7 `NOT_REACHED`;
   - `query_trace.py --trace-id lt_20260915_165314_XAUUSD:XAUUSD:2024-11-12T15:30:00` → L3/L4/L5/L6/L8
     spans, the TRADE_OPENED event, trade `CRT-0001` (`candle_idx` 11427), features row
     `_pos` 11426 or `REFUSED` with both schema hashes.
   - `query_trace.py --run-id run_20260916_044942` → layers `NOT RECORDED`, trades with trace_ids.
4. `python scripts/maintenance/check_governance_invariants.py --all` — no new failures beyond the
   pre-existing baseline captured in step 1.
5. `construction_protocol.py validate-completion` on the manifest, then `check`.

======================================================================
src\runtime\layer_trace.py exists=True size=13294
"""layer_trace.py — the v5 `LayerProof`: one identity-bearing record per (bar, layer) touched.

WHAT THIS IS
------------
Every layer of the candle-walk (L0 corpus admission through L8 runtime ledger; L7 execution is
never reached on the backtest rail — see module docstring `NOT_REACHED`) already produces its own
answer, but no stream carries one `run_id` + `trace_id` across all of them. `bar_structure_snapshot`
(v3) and `crt_construction_trace` (v4) each mint their OWN `run_id` from `ReportWriter.run_id`,
which is itself a THIRD independently-minted identifier distinct from `utils.logging_config.RUN_ID`
(naive local time, import-time) and the per-run config-dump id (`datetime.now(timezone.utc)`,
minted later in `BacktestRunner.__init__`) — three separately-minted, non-cross-referenced run
identifiers already exist in one backtest run. This module does NOT collapse those three (that is
a separate, approved behaviour-change decision — see the module's own identity block below, which
records `preexisting_run_ids` precisely so the question stays measurable rather than assumed fixed).

This module mints its OWN canonical `run_id` (one per `LayerTraceEmitter` instance, i.e. one per
run) and a `trace_id` per bar (`f"{run_id}:{instrument}:{bar_ts_isoformat}"`), and writes one flat
JSONL row per (bar, layer) any caller chooses to report on. It does not replace `bar_structure_
snapshot` or `crt_construction_trace` — it is the cross-layer identity spine those two streams
lack, following the exact "JOIN, do not re-derive" discipline both already establish.

OBSERVATION ONLY — the invariant this module exists under
-----------------------------------------------------------
- `layer_trace.enabled` defaults to **false** (absent section = predates this feature, same
  discipline as `SnapshotConfig.from_prod_config` / `ConstructionTraceConfig.from_prod_config`).
- Every `emit()` call happens AFTER the layer's own decision is already final. Nothing produced
  here is read back into `EngineRunner`, `FusionEngine`, `DecisionEngine`, or the CRT state
  machine. `emit()` returns None; no caller consumes a value from it.
- Decision-neutrality must be proven the same way `bar_structure_snapshot`'s sibling parity harness
  proves it (`scripts/analysis/v3_config_parity.py`: run with tracing ON vs OFF, byte-identical
  trade ledger) — that full-corpus run has NOT been executed yet for this module (tracked as plan
  follow-up, not claimed here). `tests/test_layer_trace.py` pins the emitter's unit-level contract
  (identity on every record, fixed vocabularies, disabled=no-op) in the meantime. Do not cite a
  test file here that does not exist — `crt_construction_trace.py`'s docstring already documents
  one instance of that exact mistake (its "CORRECTED 2026-09-05" note), and `bar_structure_
  snapshot.py`'s own docstring currently repeats it (cites `tests/test_bar_structure_decision_
  neutrality.py`, which does not exist in this tree — flagged, not yet fixed, see plan W-Review).

WHY L7 IS `NOT_REACHED`, NOT MISSING
-------------------------------------
`runtime.backtest_v2` never imports `config_layer.execution_planner` or `core.ultron_risk_gate`
(verified: only `runtime.live_engine_hook` and `runtime.live_rail_orchestrator` import
`UltronRiskGate`; only `live_engine_hook` and `research.model_runners.adapters.execution_plan`
import `ExecutionPlannerV1_2`). A backtest run's `LayerProof` rows for `layer="L7"` are therefore
ALWAYS `status="NOT_REACHED"`, emitted once per run (not per bar) so the plane split is legible in
the data, not just in a docstring.

AUTHORITY
---------
Per CLAUDE.md §6.5 Authority Ladder: this module grants **information**, never economic value,
never production authority. It introduces no new market quantity — every field is either an
identity/provenance value or a JOIN against an existing decision surface.
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("CRT.LayerTrace")

TRACE_SCHEMA_VERSION = "1.0.0"
EMITTED_BY = "runtime.layer_trace"

#: The four planes a layer belongs to (plan §9). Fixed vocabulary — a `plane` outside this set
#: is a construction error in the caller, not a new plane to silently accept.
PLANES = frozenset({"observation", "evidence", "execution", "measurement"})

#: The ten layers of the candle walk (targetschema.txt L0-L9, corrected per plan §1-2).
LAYERS = frozenset({"L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"})

#: Fixed status vocabulary. `NOT_REACHED` is a first-class status, never a missing row.
STATUSES = frozenset({"PASS", "REJECT", "NOT_REACHED", "EXCEPTION", "UNVERIFIED"})

LAYER_PLANE = {
    "L0": "observation", "L1": "observation", "L2": "observation",
    "L3": "observation", "L4": "observation",
    "L5": "evidence", "L6": "evidence",
    "L7": "execution",
    "L8": "observation",  # runtime ledger — trade birth on the backtest rail; not execution-plane
    "L9": "measurement",
}


def _require(section: dict, key: str) -> Any:
    """Strict config accessor — CLAUDE.md §6.5 forbids silent defaults for new behavioural keys."""
    if key not in section:
        raise KeyError(
            f"layer_trace.{key} is required (no silent default). "
            "Add it to the production config layer_trace section."
        )
    return section[key]


@dataclass(frozen=True)
class LayerTraceConfig:
    """Resolved `layer_trace` config. Frozen: read once at construction."""

    enabled: bool
    schema_version: str
    output_dir: str
    filename_suffix: str
    flush_every: int

    @classmethod
    def from_prod_config(cls, version: Optional[str] = None) -> Optional["LayerTraceConfig"]:
        """None when the section is absent (every config as of this module's introduction) or
        `enabled` is false. Mirrors `SnapshotConfig.from_prod_config` / `ConstructionTraceConfig.
        from_prod_config` exactly: absent section -> None, present-but-incomplete -> fail fast."""
        from config_layer.production_config import get_prod_section

        try:
            section = get_prod_section("layer_trace", version=version)
        except (RuntimeError, KeyError):
            return None
        if not bool(_require(section, "enabled")):
            return None
        declared = str(_require(section, "schema_version"))
        if declared != TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"layer_trace.schema_version={declared!r} does not match this module's "
                f"TRACE_SCHEMA_VERSION={TRACE_SCHEMA_VERSION!r}. A schema change is a governed "
                "edit, not a config typo."
            )
        return cls(
            enabled=True,
            schema_version=declared,
            output_dir=str(_require(section, "output_dir")),
            filename_suffix=str(_require(section, "filename_suffix")),
            flush_every=int(_require(section, "flush_every")),
        )


def mint_run_id(instrument: str, minted_at_utc) -> str:
    """Canonical `run_id`, minted exactly once per run. UTC, unlike two of the three pre-existing
    ids (`utils.logging_config.RUN_ID` and `ReportWriter`'s self-generated fallback are both naive
    local time — see module docstring). Format kept parallel to the pre-existing ids so it reads
    as "the same kind of thing", not a fourth incompatible scheme.
    """
    return f"lt_{minted_at_utc.strftime('%Y%m%d_%H%M%S')}_{instrument}"


def make_trace_id(run_id: str, instrument: str, bar_timestamp) -> str:
    return f"{run_id}:{instrument}:{bar_timestamp.isoformat()}"


class LayerTraceEmitter:
    """Streaming per-(bar, layer) proof writer. One instance per run.

    Unlike `BarStructureEmitter`/`ConstructionTraceEmitter` (one record per bar), this emitter
    writes 0..N records per bar — one `emit()` call per layer a caller chooses to report on for
    that bar. A bar with no calls contributes no rows (sparse by design: most layers are only
    interesting at state-change or rejection boundaries, and the caller decides that, not this
    module).
    """

    def __init__(
        self,
        cfg: LayerTraceConfig,
        *,
        run_id: str,
        instrument: str,
        timeframe: str,
        active_version: str,
        config_hash: str,
        schema_hash: str,
        dataset_id: str,
        corpus_path: str,
        corpus_rows: int,
        corpus_sha256: str,
        code_sha: str,
        tree_dirty: bool,
        rail: str,
        preexisting_run_ids: dict,
    ) -> None:
        self.cfg = cfg
        self.run_id = run_id
        self._path = Path(cfg.output_dir) / f"{instrument}{cfg.filename_suffix}"
        self._identity = OrderedDict(
            [
                ("schema_version", cfg.schema_version),
                ("run_id", run_id),
                ("rail", rail),
                ("instrument", instrument),
                ("timeframe", timeframe),
                ("active_version", active_version),
                ("config_hash", config_hash),
                ("schema_hash", schema_hash),
                ("dataset_id", dataset_id),
                ("corpus_path", corpus_path),
                ("corpus_rows", int(corpus_rows)),
                ("corpus_sha256", corpus_sha256),
                ("code_sha", code_sha),
                ("tree_dirty", bool(tree_dirty)),
                # H1 evidence: the pre-existing ids this run ALSO minted, captured at their own
                # mint sites by the caller. Never collapsed here — see module docstring.
                ("preexisting_run_ids", dict(preexisting_run_ids)),
            ]
        )
        self._buffer: list = []
        self._rows = 0

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows

    def emit(
        self,
        *,
        trace_id: str,
        bar_idx: int,
        bar_ts,
        layer: str,
        module: str,
        status: str,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
        artifact_path: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Write one proof row. Called AFTER the named layer's own decision is already final —
        this is a read-only observation of a result already produced elsewhere, never a
        computation of it.
        """
        if not self.cfg.enabled:
            return
        if layer not in LAYERS:
            raise ValueError(f"layer_trace.emit: unknown layer {layer!r} (expected one of {sorted(LAYERS)})")
        if status not in STATUSES:
            raise ValueError(f"layer_trace.emit: unknown status {status!r} (expected one of {sorted(STATUSES)})")

        rec = OrderedDict(self._identity)
        rec["trace_id"] = trace_id
        rec["span_id"] = f"{trace_id}:{layer}"
        rec["bar_idx"] = int(bar_idx)
        rec["bar_ts"] = bar_ts.isoformat() if bar_ts is not None else None
        rec["emitted_by"] = EMITTED_BY
        rec["plane"] = LAYER_PLANE[layer]
        rec["layer"] = layer
        rec["module"] = module
        rec["status"] = status
        rec["input_hash"] = input_hash
        rec["output_hash"] = output_hash
        rec["artifact_path"] = artifact_path
        rec["note"] = note
        self._write(rec)

    def emit_not_reached_once(self, *, layer: str, module: str, note: str) -> None:
        """One run-scoped row (bar_idx=-1) recording that a layer/plane was never reached on this
        rail — e.g. L7 on the backtest rail (module docstring). Distinguishes "this plane does not
        exist on this rail" from "this bar had nothing to say about it"."""
        if not self.cfg.enabled:
            return
        rec = OrderedDict(self._identity)
        rec["trace_id"] = f"{self.run_id}:RUN_SCOPED"
        rec["span_id"] = f"{self.run_id}:RUN_SCOPED:{layer}"
        rec["bar_idx"] = -1
        rec["bar_ts"] = None
        rec["emitted_by"] = EMITTED_BY
        rec["plane"] = LAYER_PLANE[layer]
        rec["layer"] = layer
        rec["module"] = module
        rec["status"] = "NOT_REACHED"
        rec["input_hash"] = None
        rec["output_hash"] = None
        rec["artifact_path"] = None
        rec["note"] = note
        self._write(rec)

    def _write(self, rec: "OrderedDict[str, Any]") -> None:
        self._buffer.append(rec)
        self._rows += 1
        if len(self._buffer) >= self.cfg.flush_every:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as fh:
            for rec in self._buffer:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._buffer.clear()

    def close(self) -> dict:
        """Flush and return a small run manifest."""
        self.flush()
        return {
            "path": str(self._path),
            "rows": self._rows,
            "schema_version": self.cfg.schema_version,
            "identity": dict(self._identity),
        }

======================================================================
src\interpreters\contract.py exists=True size=8624
"""
contract.py — the Interpreter Contract (frozen Schema 1.0).

An **Interpreter** is an event/feature producer (Level 4): it OBSERVES a window and
emits `InterpreterEvent`s + a reading-level confidence. It is a different economic
object from a research `Hypothesis` (which emits trades). Interpreters feed FUSION;
they are MEASURED by being bridged to a `Hypothesis` (see `adapter.py`) and run
through the existing `forward_walk` + `QualificationGate` — there is NO new oracle.

Hard invariants (frozen — do not extend the contract surface):
  • Pure / deterministic / no-lookahead: `observe(window, …)` is a pure function of
    `window` (which ends at the current bar). Same window → identical reading,
    including `trace_id` and `observation_time` (both derived from the last bar —
    never wall-clock).
  • Identity-blind boundary: downstream (adapter/fusion) consumes only
    events / confidence / strength / unknowns — never `name`/`family`/`meta` or the
    concrete class. `meta` is OPAQUE telemetry, forbidden for any decision.
  • Core required (`observe`/events/`confidence`), rest defaulted by
    `BaseInterpreter` (`unknowns=[]`, `failure_conditions={}`, `version()="1.0"`,
    `explain()` telemetry-only). The base VALIDATES every reading (never trust
    subclasses): confidence & strength ∈ [0,1], `kind` ∈ EventKind, `direction` ∈
    {Direction, None}, non-empty trace_id, present observation_time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from config_layer.crt_engine_v2 import Candle, Direction   # reuse frozen enum/value-object

logger = logging.getLogger("CRT.Interpreter")

# The CONTRACT version — distinct from an interpreter's implementation `version()`.
# Bump only when the reading/event shape changes; many implementation versions
# (PNF-v7, Wyckoff-v3) conform to one schema.
SCHEMA_VERSION = "1.0"


class EventKind(Enum):
    """Contract-level event taxonomy (drift guard — no stringly-typed kinds).
    Future interpreters extend this enum (+ a test); `BaseInterpreter` rejects any
    non-member kind. `OBSERVATION` = a non-directional context reading."""
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    SPRING = "SPRING"
    CATAPULT = "CATAPULT"
    OBSERVATION = "OBSERVATION"
    # Plan 5 — Point & Figure (the designed extension point; +a test in test_point_and_figure).
    DOUBLE_TOP_BREAKOUT = "DOUBLE_TOP_BREAKOUT"
    DOUBLE_BOTTOM_BREAKDOWN = "DOUBLE_BOTTOM_BREAKDOWN"


class InterpreterError(ValueError):
    """Raised when an interpreter produces a reading that violates the contract."""


@dataclass(frozen=True)
class InterpreterEvent:
    """One observation event. `confidence` = how sure; `strength` = how powerful
    (orthogonal). Entry geometry is optional — present only on directional events
    the adapter can turn into a trade Signal. `meta` is OPAQUE (telemetry only)."""
    kind: EventKind
    confidence: float
    strength: float
    direction: Optional[Direction] = None
    entry: Optional[float] = None
    sl_atr_mult: Optional[float] = None
    tp_atr_mult: Optional[float] = None
    atr: Optional[float] = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_directional(self) -> bool:
        """True iff this event carries a full directional trade geometry (so the
        adapter can emit a Signal). Non-directional events feed fusion as context."""
        return (
            self.direction is not None and self.entry is not None
            and self.sl_atr_mult is not None and self.tp_atr_mult is not None
            and self.atr is not None
        )


@dataclass(frozen=True)
class InterpreterReading:
    """The pure output of `observe()`. Carries the owner's five capabilities as
    fields (events/confidence/unknowns/failure_conditions) + provenance."""
    events: list[InterpreterEvent]
    confidence: float
    trace_id: str                 # hierarchical: {NAME}-v{version}-{YYYYMMDD-HHMMSS}
    observation_time: datetime    # window's LAST bar timestamp (deterministic)
    schema_version: str = SCHEMA_VERSION
    unknowns: list[str] = field(default_factory=list)
    failure_conditions: dict = field(default_factory=dict)


@runtime_checkable
class Interpreter(Protocol):
    """Behavior-agnostic plugin contract. Mirrors the research `Hypothesis` purity."""
    name: str
    family: str
    economic_rationale: str

    def observe(self, window: Sequence[Candle], features: dict, ctx: dict) -> InterpreterReading: ...

    def explain(self) -> dict: ...   # telemetry/explainability ONLY — never a decision input


def _require_unit(value: float, label: str) -> None:
    if not (0.0 <= float(value) <= 1.0):
        raise InterpreterError(f"{label}={value} outside [0,1]")


class BaseInterpreter:
    """Reduce boilerplate + enforce the contract. Subclasses implement `_observe`
    returning `(events, confidence)`; the base wraps it into a validated, provenance-
    stamped `InterpreterReading`. `unknowns`/`failure_conditions`/`version`/`explain`
    are overridable hooks with safe defaults (Q3: core-required, rest-defaulted)."""

    name: str = "base"
    family: str = "base"
    economic_rationale: str = ""
    schema_version: str = SCHEMA_VERSION

    # ── hooks (override as needed) ───────────────────────────────────────────
    def version(self) -> str:
        """Implementation version (distinct from `schema_version`). Default '1.0'."""
        return "1.0"

    def _observe(self, window: Sequence[Candle], features: dict,
                 ctx: dict) -> Tuple[list[InterpreterEvent], float]:
        raise NotImplementedError

    def unknowns(self, window: Sequence[Candle], features: dict, ctx: dict) -> list[str]:
        return []

    def failure_conditions(self, window: Sequence[Candle], features: dict, ctx: dict) -> dict:
        return {}

    def explain(self) -> dict:
        """Telemetry-only narration. NEVER consumed by adapter/fusion/decision."""
        return {"observation": "", "reasoning": "", "unknowns": []}

    # ── final pipeline (do not override) ─────────────────────────────────────
    def _trace_id(self, ts: datetime) -> str:
        # Deterministic from the bar time (no mutable counter) → same window yields
        # the same trace_id (replay-safe). seq component = the bar's HHMMSS.
        return f"{self.name.upper()}-v{self.version()}-{ts.strftime('%Y%m%d-%H%M%S')}"

    def observe(self, window: Sequence[Candle], features: dict, ctx: dict) -> InterpreterReading:
        if not window:
            raise InterpreterError(f"{self.name}: empty window — cannot observe")
        events, confidence = self._observe(window, features, ctx)
        ts = window[-1].timestamp     # deterministic, last bar — never wall-clock
        reading = InterpreterReading(
            events=list(events),
            confidence=float(confidence),
            trace_id=self._trace_id(ts),
            observation_time=ts,
            schema_version=self.schema_version,
            unknowns=list(self.unknowns(window, features, ctx)),
            failure_conditions=dict(self.failure_conditions(window, features, ctx)),
        )
        self._validate(reading)
        return reading

    def _validate(self, reading: InterpreterReading) -> None:
        """The contract's teeth — never trust subclasses."""
        _require_unit(reading.confidence, "reading.confidence")
        if not reading.trace_id:
            raise InterpreterError("empty trace_id")
        if reading.observation_time is None:
            raise InterpreterError("missing observation_time")
        for ev in reading.events:
            if not isinstance(ev.kind, EventKind):
                raise InterpreterError(f"event.kind not an EventKind: {ev.kind!r}")
            if ev.direction is not None and not isinstance(ev.direction, Direction):
                raise InterpreterError(f"event.direction not Direction|None: {ev.direction!r}")
            _require_unit(ev.confidence, "event.confidence")
            _require_unit(ev.strength, "event.strength")

======================================================================
src\runtime\crt_baseline_trace.py exists=True size=16286
"""
crt_baseline_trace.py — optional, behavior-preserving CRT baseline observation.

Default-off. When disabled / hooks is None, CRT takes no extra work beyond a
single attribute check at instrumented points.

Does NOT recompute features, re-evaluate guards, or mutate CRT control flow.
Authority: research/governance observation only (§6.5).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

TRACE_SCHEMA_VERSION = "1.0.0"


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, bool)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return {"__nonfinite__": True, "repr": repr(v)}
        return v
    if hasattr(v, "name"):  # Enum
        try:
            return v.name
        except Exception:
            pass
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            pass
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return _jsonable(asdict(v))
    return repr(v)


@dataclass
class OperandRec:
    name: str
    runtime_value: Any
    source_class: str
    source_name: str
    source_location: str
    feature_id: Optional[str] = None
    formula_id: Optional[str] = None
    config_key: Optional[str] = None
    provenance_status: str = "PROVEN"


@dataclass
class ThresholdRec:
    name: str
    runtime_value: Any
    config_key: Optional[str]
    config_source: str
    read_location: str


@dataclass
class GuardRec:
    evaluation_order: int
    guard_id: str
    guard_name: str
    source_location: str
    from_state: str
    candidate_to_state: str
    operands: list[OperandRec] = field(default_factory=list)
    operator: str = ""
    thresholds: list[ThresholdRec] = field(default_factory=list)
    result: bool = False
    short_circuit_status: str = "NONE"
    failure_reason: Optional[str] = None


class CRTBaselineTraceHooks:
    """Attached to CRTEngine / StateMachine when tracing is active for a bar."""

    def __init__(self) -> None:
        self.enabled: bool = False
        self._guard_order: int = 0
        self.guards: list[GuardRec] = []
        self.events_at_start: int = 0
        self.state_before: Optional[str] = None
        self.state_after: Optional[str] = None
        self.snapshot_before: dict = {}
        self.snapshot_after: dict = {}
        self.action: dict = {}
        self.crt_inputs: list[dict] = []
        self.config_reads: list[dict] = []
        self.warnings: list[str] = []
        self.exceptions: list[str] = []

    def reset_bar(self) -> None:
        self._guard_order = 0
        self.guards = []
 
--- excerpts ---
--- around L331 ---
328|    ]
329|
330|    return {
331|        "trace_identity": identity,
332|        "raw_bar": raw_bar,
333|        "canonical_features": canonical_features,
334|        "crt_inputs": {"inputs": hooks.crt_inputs},
======================================================================
docs\topics\interpreter-contract.md exists=True size=7259
# Topic: Interpreter Contract Layer (Level 4)

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-06-14 · Updated: 2026-06-14 (Plan 4: MA-cross reference + e2e chain proof) · Status: living

## In plain language
The Interpreter Contract is the frozen interface every future market interpreter (P&F, Wyckoff,
Market Profile, Order Flow, …) must satisfy *before* it ships — so a new interpreter becomes an
**experiment measured against G001**, not a belief. An **Interpreter** is an *event/feature
producer*: it observes a window and emits events + confidence/strength that feed **fusion**. It is
a different economic object from a research **Hypothesis** (which emits *trades*). To be measured,
an interpreter is bridged to a `Hypothesis` by an adapter and run through the **existing**
`forward_walk` + `QualificationGate` — there is deliberately **no new oracle** (reuse, not rebuild).

**Frozen hard invariants:** pure · deterministic · no-lookahead · **identity-blind** (fusion never
knows P&F-ness — only events/confidence/strength/unknowns) · `explain()` telemetry-only · `meta`
opaque/forbidden-for-decisions · `schema_version` (contract) ≠ `version()` (implementation).

## Code covered
- [`src/interpreters/contract.py`](../../src/interpreters/contract.py) — `EventKind` enum;
  `InterpreterEvent` (kind/direction(`Optional[Direction]`)/confidence/strength/geometry/opaque
  `meta`); `InterpreterReading` (events/confidence/unknowns/failure_conditions/trace_id/
  observation_time/schema_version); `Interpreter` Protocol (`observe`+`explain`); `BaseInterpreter`
  (core-required + defaulted hooks + strict `_validate`).
- [`src/interpreters/adapter.py`](../../src/interpreters/adapter.py) — `InterpreterHypothesis`: the
  identity-blind bridge that wraps any `Interpreter` as a research `Hypothesis` (`detect()` → Signals
  from directional events only). Mirrors `hypotheses/spine_hypothesis.py`.
- [`src/interpreters/reference.py`](../../src/interpreters/reference.py) — `NullInterpreter` +
  `ConstantDirectionInterpreter` (proof-of-contract stubs) + `MovingAverageCrossInterpreter`
  (Plan 4 — simplest *realistic* reference; reuses `indicators.sma`/`atr`). NONE are real edges.
- [`scripts/research/qualify_interpreter.py`](../../scripts/research/qualify_interpreter.py) —
  thin driver (`--interpreter {ma_cross,pnf}`): register adapted interpreter → `HypothesisRunner` +
  `QualificationGate` on real data → print `EdgeReport` + verdict + Δ-vs-control table (via the
  independent `metrics_oracle`) + first-N provenance lines (chain observability).
- [`src/interpreters/point_and_figure.py`](../../src/interpreters/point_and_figure.py) — **PNF-v1**
  (Plan 5), the FIRST real interpreter: double-top / double-bottom on an ATR-fraction box grid.
  Shadow-measured → **REJECT** (F-028; FROZEN). Extends `EventKind` with `DOUBLE_TOP_BREAKOUT` /
  `DOUBLE_BOTTOM_BREAKDOWN` (the designed extension point).
- [`src/research/contracts.py`](../../src/research/contracts.py) (`Hypothesis`, `Signal`) — the
  adapter target (frozen; never edited). `forward_walk` + `qualification.py` — the reused oracle.

## Ins / Outs
- **Ins:** a `window: Sequence[Candle]` (+ `features`, `ctx{instrument}`); reuses the frozen
  `Direction` enum + `Candle` from `config_layer/crt_engine_v2.py`.
- **Outs:** `InterpreterReading` (the pure `observe()` result); via the adapter, research `Signal`s
  carrying provenance (`trace_id`, confidence, strength) in `Signal.meta` → `forward_walk` →
  `Outcome` → `EdgeReport`.

## Entry points & validations
- **Reached via:** `InterpreterHypothesis(interp)` → `HypothesisRunner` / `forward_walk` (measurement)
  — the same path `SpineHypothesis` uses. (Live fusion integration is a LATER plan.)
- **Validated by:** `BaseInterpreter._validate` (confidence/strength ∈ [0,1], `kind` ∈ EventKind,
  `direction` ∈ {Direction, None}, non-empty trace_id, present observation_time) + the existing
  7-gate `QualificationGate` once measured.

## Tests
- [`tests/interpreters/test_interpreter_contract.py`](../../tests/interpreters/test_interpreter_contract.py)
  — conformance/guards, determinism + observation_time-from-last-bar, `test_fusion_is_identity_blind`,
  and the KEY adapter → `forward_walk` → `EdgeReport` round-trip.
- [`tests/interpreters/test_reference_ma_cross.py`](../../tests/interpreters/test_reference_ma_cross.py)
  — MA-cross unit (cross detection, bounded conf/strength, purity). [Plan 4]
- [`tests/interpreters/test_reference_interpreter_e2e.py`](../../tests/interpreters/test_reference_interpreter_e2e.py)
  — END-TO-END chain proof on real BNBUSDT data (chain runs, verdict ≠ PROMOTE, sha256-deterministic). [Plan 4]
- [`tests/interpreters/test_invariant_guards.py`](../../tests/interpreters/test_invariant_guards.py)
  — `explain()` inert + `meta` opaque (the two strongest contract invariants). [Plan 4]
- [`tests/test_metrics_v2.py`](../../tests/test_metrics_v2.py) — Metrics Oracle V3 (efficiency /
  symbol-attribution / concentration) parity (bundled in Plan 3).

## Fits in architecture
Level 4 (Interpreters) in the owner's hierarchy: Truth → Goal → Metrics → **Oracle → Interpreter
Contract** → Adapter → forward_walk → QualificationGate → EdgeReport → (later) Fusion. Sits beside
the research [Edge Discovery Program](../../src/research/) and reuses its measurement spine.

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-14 — contract creep. Owner froze the surface: no `InterpreterOracle`, no extra
  fields beyond the agreed set; next step is to PROVE with the reference interpreter, not extend.
- **Challenges:** 2026-06-14 — honoring the frozen pure-`detect` invariant while giving the owner's
  observe/events/confidence/unknowns/failure surface → resolved as one pure `observe()→reading`,
  capabilities as reading fields + Base defaults; `trace_id`/`observation_time` derived from the last
  bar (deterministic, replay-safe), never wall-clock.
- **Blockers:** none.
- **Ambiguities:** 2026-06-14 — `Direction.NONE` vs `Optional[Direction]` → reused the frozen
  `Direction` enum + `None` for non-directional (no shared-enum edit).
- **Enhancements:** 2026-06-14 — Plan 4 DONE (MA cross → REJECT, chain proven). **Plan 5 DONE:
  PNF-v1 (P&F double-top/bottom) = first REAL interpreter, shadow-measured on BNBUSDT → n=8554,
  PF 0.528, E −0.4538, verdict REJECT, worse than random (Δexpectancy −0.039). Recorded F-028 +
  FROZEN in the Funding-Ledger falsified-interpreters list — reopen only via a NEW ontology, never a
  box/reversal sweep.** Next: Plan 6 fusion experiments (gated on honest verdicts, not alpha).
- **Need more info:** whether ANY interpreter improves G001 — two falsified so far (MA cross, P&F);
  the chain reliably rejects weak producers, which is the point.

======================================================================
src\interpreters\adapter.py exists=True size=3046
"""
adapter.py — the ONLY bridge from an Interpreter to the research measurement stack.

`InterpreterHypothesis` wraps any `Interpreter` as a research `Hypothesis` (implements
`detect() -> list[Signal]`), so an interpreter is measured by the UNCHANGED
`forward_walk` + `QualificationGate` (the reused oracle) — no parallel measurement
code, no `InterpreterOracle`. Mirrors `hypotheses/spine_hypothesis.py`.

IDENTITY-BLIND (frozen invariant): `detect()` builds Signals from ONLY the reading's
directional events (direction + entry geometry). It never branches on the interpreter's
identity/type or on `event.meta`. `name`/`family`/`economic_rationale` are carried as
labels for qualification telemetry (the M4.7 rationale gate), not as decision inputs.
Confidence/strength/trace_id ride along in `Signal.meta` as provenance only.
"""

from __future__ import annotations

from typing import Sequence

from research.contracts import Signal

from interpreters.contract import Interpreter


class InterpreterHypothesis:
    """Adapt one `Interpreter` to the `Hypothesis` Protocol (behavior-agnostic)."""

    def __init__(self, interpreter: Interpreter, *, family: str = "interpreter"):
        self._interp = interpreter
        # Labels for the research registry / M4.7 rationale gate (telemetry, not
        # decisions). Reading them here does not violate identity-blindness, which is
        # about detect()'s SIGNAL logic — that uses only events (see below).
        self.name = f"interp:{getattr(interpreter, 'name', 'unknown')}"
        self.family = family
        self.economic_rationale = getattr(interpreter, "economic_rationale", "")

    def detect(self, window: Sequence, features: dict, ctx: dict) -> list[Signal]:
        if not window:
            return []
        bar = window[-1]
        idx = getattr(bar, "index", None)
        if idx is None:
            return []

        reading = self._interp.observe(window, features, ctx)
        instrument = ctx.get("instrument", "UNKNOWN")

        signals: list[Signal] = []
        for ev in reading.events:
            # Identity-blind: only directional events with full geometry become trades.
            if not ev.is_directional:
                continue
            signals.append(Signal(
                instrument=instrument,
                timestamp=bar.timestamp,
                entry_index=idx,
                direction=ev.direction.value.lower(),   # Direction enum → "long"/"short"
                entry=float(ev.entry),
                sl_atr_mult=float(ev.sl_atr_mult),
                tp_atr_mult=float(ev.tp_atr_mult),
                atr=float(ev.atr),
                meta={                                    # provenance only (telemetry)
                    "event_kind": ev.kind.value,
                    "confidence": ev.confidence,
                    "strength": ev.strength,
                    "trace_id": reading.trace_id,
                    "schema_version": reading.schema_version,
                },
            ))
        return signals

======================================================================
tests\test_layer_trace.py exists=True size=6919
"""LayerTraceEmitter (runtime.layer_trace): record shape, identity, and emit-contract floors.

Unit-level floors on the emitter in isolation, mirroring `tests/test_bar_structure_snapshot.py`'s
structure. This is NOT the full-corpus decision-neutrality proof (that requires running
`BacktestRunner` twice — tracing ON vs OFF — against a real corpus and diffing the trade ledger;
see the module's own docstring for why that is a separate, not-yet-built artifact). What this file
DOES pin, at the unit level, backs the decision-neutrality CLAIM without yet being the full proof:

  - `emit()` / `emit_not_reached_once()` never raise on a well-formed call and return None;
  - a disabled emitter (`enabled=False`) writes nothing, so a config predating this feature is a
    complete no-op;
  - every record carries the identity block (`run_id`/`trace_id`/`span_id`) required to join rows
    across layers, which is this module's entire reason to exist (plan §5 item 1);
  - `layer`/`status`/`plane` are drawn from fixed vocabularies, not free strings, so a caller typo
    fails loudly at `emit()` time rather than writing a silently-uncomparable row.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.layer_trace import (  # noqa: E402
    LAYER_PLANE,
    LAYERS,
    PLANES,
    STATUSES,
    TRACE_SCHEMA_VERSION,
    LayerTraceConfig,
    LayerTraceEmitter,
    make_trace_id,
    mint_run_id,
)


def _cfg(tmp: Path, *, enabled: bool = True) -> LayerTraceConfig:
    return LayerTraceConfig(
        enabled=enabled,
        schema_version=TRACE_SCHEMA_VERSION,
        output_dir=str(tmp),
        filename_suffix="_layer_trace.jsonl",
        flush_every=50,
    )


def _emitter(tmp: Path, *, enabled: bool = True, run_id: str = "test_run") -> LayerTraceEmitter:
    return LayerTraceEmitter(
        _cfg(tmp, enabled=enabled),
        run_id=run_id,
        instrument="XAUUSD",
        timeframe="M15",
        active_version="v2_htfcrt_2026_08",
        config_hash="7de09f62",
        schema_hash="f52bf5d3",
        dataset_id="",
        corpus_path="data/mt5/XAUUSD_M15.csv",
        corpus_rows=47275,
        corpus_sha256="0" * 64,
        code_sha="deadbeef",
        tree_dirty=True,
        rail="backtest",
        preexisting_run_ids={
            "utils.logging_config.RUN_ID": "20260101_000000",
            "runtime.ReportWriter.run_id": "run_20260101_000000",
        },
    )


def _bar_ts(i: int):
    return datetime(2025, 1, 1, tzinfo=timezone.utc).replace(minute=(i * 15) % 60)


# ---- identity / minting -----------------------------------------------------------------

def test_mint_run_id_is_utc_and_distinguishable_from_preexisting_ids():
    rid = mint_run_id("XAUUSD", datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    assert rid == "lt_20260101_120000_XAUUSD"


def test_make_trace_id_is_deterministic_for_the_same_bar():
    ts = _bar_ts(5)
    a = make_trace_id("lt_run", "XAUUSD", ts)
    b = make_trace_id("lt_run", "XAUUSD", ts)
    assert a == b
    assert a == f"lt_run:XAUUSD:{ts.isoformat()}"


# ---- vocabularies -------------------------------------------------------------------------

def test_layer_plane_covers_every_declared_layer():
    assert set(LAYER_PLANE.keys()) == LAYERS
    assert set(LAYER_PLANE.values()) <= PLANES


def test_emit_rejects_unknown_layer(tmp_path):
    em = _emitter(tmp_path)
    with pytest.raises(ValueError):
        em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L99", module="x", status="PASS")


def test_emit_rejects_unknown_status(tmp_path):
    em = _emitter(tmp_path)
    with pytest.raises(ValueError):
        em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L3", module="x", status="MAYBE")


# ---- emit contract ------------------------------------------------------------------------

def test_emit_returns_none_and_writes_one_row(tmp_path):
    em = _emitter(tmp_path)
    result = em.emit(
        trace_id="lt_run:XAUUSD:t0", bar_idx=0, bar_ts=_bar_ts(0),
        layer="L3", module="config_layer.crt_engine_v2", status="PASS",
    )
    assert result is None
    manifest = em.close()
    assert manifest["rows"] == 1


def test_disabled_emitter_writes_nothing(tmp_path):
    em = _emitter(tmp_path, enabled=False)
    em.emit(trace_id="t", bar_idx=0, bar_ts=_bar_ts(0), layer="L3", module="x", status="PASS")
    em.emit_not_reached_once(layer="L7", module="x", note="n/a")
    manifest = em.close()
    assert manifest["rows"] == 0
    assert not Path(manifest["path"]).exists()


def test_emit_not_reached_once_is_run_scoped_not_bar_scoped(tmp_path):
    em = _emitter(tmp_path)
    em.emit_not_reached_once(layer="L7", module="x", note="unreachable on this rail")
    manifest = em.close()
    rows = [json.loads(l) for l in Path(manifest["path"]).read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["bar_idx"] == -1
    assert rows[0]["status"] == "NOT_REACHED"
    assert rows[0]["plane"] == "execution"


# ---- identity on every record --------------------------------------------------------------

def test_every_record_carries_the_full_identity_block(tmp_path):
    em = _emitter(tmp_path, run_id="lt_20260101_000000_XAUUSD")
    tid = make_trace_id(em.run_id, "XAUUSD", _bar_ts(1))
    em.emit(trace_id=tid, bar_idx=1, bar_ts=_bar_ts(1), layer="L5", module="core.engine_runner", status="PASS")
    manifest = em.close()
    rows = [json.loads(l) for l in Path(manifest["path"]).read_text(encoding="utf-8").splitlines()]
    row = rows[0]
    for key in ("run_id", "trace_id", "span_id", "instrument", "active_version",
                "config_hash", "schema_hash", "corpus_sha256", "code_sha", "tree_dirty",
                "preexisting_run_ids"):
        assert key in row, f"missing identity field {key!r}"
    assert row["run_id"] == "lt_20260101_000000_XAUUSD"
    assert row["trace_id"] == tid
    assert row["span_id"] == f"{tid}:L5"
    # H1 evidence: the pre-existing ids are captured, never silently collapsed to this module's own.
    assert row["preexisting_run_ids"]["utils.logging_config.RUN_ID"] == "20260101_000000"
    assert row["run_id"] != row["preexisting_run_ids"]["utils.logging_config.RUN_ID"]


def test_from_prod_config_returns_none_when_section_absent(monkeypatch):
    """Absent `layer_trace` section = predates this feature (mirrors `SnapshotConfig.
    from_prod_config` / `ConstructionTraceConfig.from_prod_config` exactly)."""
    import config_layer.production_config as prod_cfg

    def _raise(*a, **k):
        raise KeyError("layer_trace")

    monkeypatch.setattr(prod_cfg, "get_prod_section", _raise)
    assert LayerTraceConfig.from_prod_config() is None

======================================================================
tests\test_run_linkage_traces.py exists=True size=11009
"""Floor for the analysis-grain records in run_linkage_registry.json (CH-analysis-trace-linkage).

Two record types live under each instrument alongside the run_id keys:

    _analyses  AN-*  question + claims. Stable across re-measurement.
    _traces    TR-*  one immutable evidence assembly (runs consumed + artifact sha256s).

AN 1-N TR. A re-measurement mints a new TR against the same AN, which is the thing a reused
run_id cannot express (the 2026-09-10 census rebuild inherited run_20260909_202201's id ten
hours after that run was minted).

The load-bearing rule is `test_every_claim_names_a_registered_surface`. The superseded coding-LLM
context pack already carried `claim_protocol.refuse_unnamed_surface: true`, but it could not be
enforced: surfaces lived in the registry keyed by run while claims lived in prose. Co-locating
them turns that rule into a set-membership test -- which is how the `atr_tercile` and `t1_t3`
citations in `withdrawn_claims` were caught.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "governance" / "run_linkage_registry.json"

ANALYSES_KEY = "_analyses"
TRACES_KEY = "_traces"

# schema_bridge.surfaces mixes surface status tokens with plain run booleans
# (rebuild_completed, join_logic_fixed_for_future_rebuild). A naive membership test would
# accept `surface: rebuild_completed`, so only string status tokens count as surfaces.
# VALID admits a claim; INVALIDATED is a named refusal, not a silent pass -- before the
# 2026-09-10 surfaces_ruling this set had one token that meant two things (see
# CH-f069-epoch-scope: run_20260909_202201 marked all 8 CREATE surfaces VALID while the
# context pack's forbidden_inferences forbade three of them, and nothing enforced the
# ruling on the machine-readable side).
VALID_SURFACE_TOKENS = {"VALID"}
INVALIDATED_SURFACE_TOKENS = {"INVALIDATED"}
SURFACE_STATUS_TOKENS = VALID_SURFACE_TOKENS | INVALIDATED_SURFACE_TOKENS


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _instruments(reg: dict) -> dict[str, dict]:
    return {k: v for k, v in reg.items() if not k.startswith("_") and isinstance(v, dict)}


def _analyses(reg: dict):
    """Yield (instrument, analysis_id, analysis)."""
    for inst, block in _instruments(reg).items():
        for an_id, an in (block.get(ANALYSES_KEY) or {}).items():
            yield inst, an_id, an


def _traces(reg: dict):
    """Yield (instrument, trace_id, trace)."""
    for inst, block in _instruments(reg).items():
        for tr_id, tr in (block.get(TRACES_KEY) or {}).items():
            yield inst, tr_id, tr


def _run_records(block: dict) -> dict[str, dict]:
    return {k: v for k, v in block.items() if not k.startswith("_") and isinstance(v, dict)}


def _surfaces_for_run(block: dict, run_id: str) -> dict:
    run = _run_records(block).get(run_id) or {}
    bridge = run.get("schema_bridge") or {}
    return bridge.get("surfaces") or {}


def _is_superseded(trace: dict) -> bool:
    return str(trace.get("status", "")).upper() == "SUPERSEDED"


def test_registry_parses_and_reserved_keys_are_not_run_ids():
    reg = _registry()
    for inst, block in _instruments(reg).items():
        for reserved in (ANALYSES_KEY, TRACES_KEY):
            assert reserved.startswith("_"), reserved
        # resolve_artifacts does a keyed run_id lookup; a reserved key must never look like one.
        for key in block:
            if key.startswith("_"):
                assert not key.startswith("run_"), f"{inst}.{key} shadows a run_id"


def test_every_claim_names_a_registered_surface():
    """A claim may only cite a surface some run actually registers, as '<run_id>#<surface>'."""
    reg = _registry()
    checked = 0
    for inst, an_id, an in _analyses(reg):
        block = reg[inst]
        for claim in an.get("claims") or []:
            ref = claim.get("surface")
            assert ref, f"{an_id}.{claim.get('id')} names no surface"
            assert "#" in ref, f"{an_id}.{claim['id']} surface must be '<run_id>#<surface>': {ref}"
            run_id, _, surface = ref.partition("#")
            surfaces = _surfaces_for_run(block, run_id)
            assert surfaces, f"{an_id}.{claim['id']} cites {run_id}, which registers no surfaces"
            assert surface in surfaces, (
                f"{an_id}.{claim['id']} cites unregistered surface {surface!r} on {run_id}"
            )
            value = surfaces[surface]
            assert isinstance(value, str) and value in SURFACE_STATUS_TOKENS, (
                f"{an_id}.{claim['id']} cites {surface!r}, which is not a surface status token "
                f"(got {value!r}) -- booleans in schema_bridge.surfaces are run properties"
            )
            assert value in VALID_SURFACE_TOKENS, (
                f"REFUSED: {an_id}.{claim['id']} cites {run_id}#{surface}, which is "
                f"INVALIDATED -- a claim may not rest on an invalidated surface. See "
                f"{run_id}'s surfaces_ruling for why."
            )
            checked += 1
    assert checked, "no claims found to validate"


def test_claims_reference_a_trace_bound_to_the_same_analysis():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = (reg[inst].get(TRACES_KEY) or {})
        for claim in an.get("claims") or []:
            tr_id = claim.get("trace")
            assert tr_id, f"{an_id}.{claim.get('id')} cites no trace"
            assert tr_id in traces, f"{an_id}.{claim['id']} cites unknown trace {tr_id}"
            assert traces[tr_id].get("analysis_id") == an_id, (
                f"{tr_id} does not back-link to {an_id}"
            )


def test_claim_rests_on_artifacts_present_in_its_trace():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = reg[inst].get(TRACES_KEY) or {}
        for claim in an.get("claims") or []:
            trace = traces[claim["trace"]]
            known = {a["id"] for a in trace.get("artifacts") or []}
            for art_id in claim.get("rests_on") or []:
                assert art_id in known, (
                    f"{an_id}.{claim['id']} rests on {art_id}, absent from {claim['trace']}"
                )


def test_analysis_and_trace_backlinks_agree_both_ways():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        traces = reg[inst].get(TRACES_KEY) or {}
        declared = set(an.get("traces") or [])
        assert declared, f"{an_id} declares no traces"
        for tr_id in declared:
            assert tr_id in traces, f"{an_id} declares unknown trace {tr_id}"
        backlinked = {t for t, tr in traces.items() if tr.get("analysis_id") == an_id}
        assert declared == backlinked, (
            f"{an_id}.traces {sorted(declared)} != traces back-linking to it {sorted(backlinked)}"
        )


def test_every_consumed_run_declares_its_id_basis():
    """analysis run_ids are UTC, backtest run-dir ids are local IST; sorting by id inverts them."""
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        if _is_superseded(tr):
            continue
        consumed = tr.get("consumes_runs") or []
        assert consumed, f"{tr_id} consumes no runs"
        for entry in consumed:
            assert entry.get("id_basis") in {"UTC", "IST"}, (
                f"{tr_id} run {entry.get('run_id')} declares no id_basis"
            )
            assert isinstance(entry.get("registered"), bool), (
                f"{tr_id} run {entry.get('run_id')} does not say whether it is registered"
            )


def test_traces_declare_a_clock_basis_and_ordering_key():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        assert tr.get("clock_basis") == "UTC", f"{tr_id} must declare clock_basis UTC"
        assert tr.get("ordering_key") == "generated_at_utc", (
            f"{tr_id} must order by generated_at_utc, never by run_id"
        )


def test_artifacts_are_content_bound_and_run_attribution_is_honest():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        block = reg[inst]
        runs = _run_records(block)
        for art in tr.get("artifacts") or []:
            assert art.get("path"), f"{tr_id} artifact {art.get('id')} has no path"
            sha = art.get("sha256")
            assert sha, f"{tr_id}.{art['id']} is not content-bound"
            if sha != "UNRECOVERABLE":
                assert len(sha) == 64, f"{tr_id}.{art['id']} sha256 malformed"
                assert art.get("generated_at_utc"), (
                    f"{tr_id}.{art['id']} has no generated_at_utc"
                )
            # produced_by_run must be null (honestly unscoped) or a real run in this instrument.
            owner = art.get("produced_by_run", "__missing__")
            assert owner != "__missing__", (
                f"{tr_id}.{art['id']} must state produced_by_run (null is a valid answer)"
            )
            if owner is not None:
                assert owner in runs, f"{tr_id}.{art['id']} claims unknown run {owner}"


def test_superseded_traces_keep_their_supersession_link():
    reg = _registry()
    for inst, tr_id, tr in _traces(reg):
        if not _is_superseded(tr):
            continue
        assert tr.get("superseded_by"), f"{tr_id} is SUPERSEDED with no successor"
        assert tr["superseded_by"] in (reg[inst].get(TRACES_KEY) or {}), (
            f"{tr_id} superseded by unknown trace"
        )
        assert tr.get("analysis_id"), f"{tr_id} must stay bound to its analysis"


def test_withdrawn_claims_are_retained_with_a_reason():
    """Append-discipline (CLAUDE.md 6.2 rule 4): a retracted claim is kept, never deleted."""
    reg = _registry()
    allowed = {"NO_SURFACE", "FORBIDDEN", "SUPERSEDED", "INVALIDATED"}
    for inst, an_id, an in _analyses(reg):
        for w in an.get("withdrawn_claims") or []:
            assert w.get("statement"), f"{an_id} withdrawn entry has no statement"
            assert w.get("reason") in allowed, (
                f"{an_id} withdrawal reason {w.get('reason')!r} not in {sorted(allowed)}"
            )


def test_analyses_carry_no_authority():
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        assert an.get("authority") == "none", f"{an_id} must not claim authority"
        assert an.get("economic_claims_allowed") is False, (
            f"{an_id} must not enable economic claims"
        )


@pytest.mark.parametrize("bad", ["rebuild_completed", "join_logic_fixed_for_future_rebuild"])
def test_boolean_run_properties_are_not_valid_surfaces(bad):
    """Guards the filter: these live in schema_bridge.surfaces but are not surfaces."""
    reg = _registry()
    for inst, an_id, an in _analyses(reg):
        for claim in an.get("claims") or []:
            assert not claim.get("surface", "").endswith(f"#{bad}"), (
                f"{an_id}.{claim['id']} cites run property {bad!r} as a surface"
            )

======================================================================
backtest_v2.py trace_id contexts
--- L2638 ---
2634|            # `validate_dataset`/`CandleLoader`, batch `FeaturePipeline` build) — recorded once
2635|            # here rather than re-asserted every bar.
2636|            _lt_run_scoped_id = f"{_layer_trace.run_id}:RUN_SCOPED"
2637|            _layer_trace.emit(
2638|                trace_id=_lt_run_scoped_id, bar_idx=-1, bar_ts=None,
2639|                layer="L0", module="data_ingestion.ohlcv_schema+dataset_integrity+corpus_gate",
2640|                status="PASS",
2641|                artifact_path=str(self.csv_path or ""),
2642|                note=f"corpus admitted for this run: {self.cfg.instrument} rows≈{getattr(self, 'total_candles', 'UNKNOWN')}",
2643|            )
--- L2645 ---
2641|                artifact_path=str(self.csv_path or ""),
2642|                note=f"corpus admitted for this run: {self.cfg.instrument} rows≈{getattr(self, 'total_candles', 'UNKNOWN')}",
2643|            )
2644|            _layer_trace.emit(
2645|                trace_id=_lt_run_scoped_id, bar_idx=-1, bar_ts=None,
2646|                layer="L1", module="features.feature_pipeline",
2647|                status=("PASS" if self.feature_vectors is not None else "NOT_REACHED"),
2648|                note=(
2649|                    "FeaturePipeline built (batch, whole corpus, in __init__)"
2650|                    if self.feature_vectors is not None else
--- L2990 ---
2986|            # Same placement discipline as `_bar_structure`/`_construction_trace` immediately
2987|            # above: AFTER `process_candle` has returned, decision already final. Reads only
2988|            # values already computed for this bar (`result`, `parent_state`, `parent_objective`,
2989|            # `parent_feed`) — no new computation.
2990|            _lt_trace_id = None
2991|            if _layer_trace is not None:
2992|                from runtime.layer_trace import make_trace_id as _lt_make_trace_id
2993|
2994|                _lt_trace_id = _lt_make_trace_id(
2995|                    _layer_trace.run_id, self.cfg.instrument, candle.timestamp
--- L2992 ---
2988|            # values already computed for this bar (`result`, `parent_state`, `parent_objective`,
2989|            # `parent_feed`) — no new computation.
2990|            _lt_trace_id = None
2991|            if _layer_trace is not None:
2992|                from runtime.layer_trace import make_trace_id as _lt_make_trace_id
2993|
2994|                _lt_trace_id = _lt_make_trace_id(
2995|                    _layer_trace.run_id, self.cfg.instrument, candle.timestamp
2996|                )
2997|                _lt_action = result.get("action", "NONE")
--- L2994 ---
2990|            _lt_trace_id = None
2991|            if _layer_trace is not None:
2992|                from runtime.layer_trace import make_trace_id as _lt_make_trace_id
2993|
2994|                _lt_trace_id = _lt_make_trace_id(
2995|                    _layer_trace.run_id, self.cfg.instrument, candle.timestamp
2996|                )
2997|                _lt_action = result.get("action", "NONE")
2998|                _lt_rejected = ("REJECTED" in _lt_action) or (_lt_action == "NONE" and bool(result.get("reason")))
2999|                _lt_status = "REJECT" if _lt_rejected else "PASS"
--- L3001 ---
2997|                _lt_action = result.get("action", "NONE")
2998|                _lt_rejected = ("REJECTED" in _lt_action) or (_lt_action == "NONE" and bool(result.get("reason")))
2999|                _lt_status = "REJECT" if _lt_rejected else "PASS"
3000|                _layer_trace.emit(
3001|                    trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3002|                    layer="L3", module="config_layer.crt_engine_v2", status=_lt_status,
3003|                    output_hash=curr_state,
3004|                    note=f"action={_lt_action} reason={result.get('reason')} transition={prev_state}->{curr_state}",
3005|                )
3006|                _layer_trace.emit(
--- L3007 ---
3003|                    output_hash=curr_state,
3004|                    note=f"action={_lt_action} reason={result.get('reason')} transition={prev_state}->{curr_state}",
3005|                )
3006|                _layer_trace.emit(
3007|                    trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3008|                    layer="L4", module="runtime.parent_crt_feed+config_layer.htf_state",
3009|                    status=("PASS" if parent_feed is not None else "NOT_REACHED"),
3010|                    output_hash=(getattr(parent_state, "name", None) if parent_state is not None else None),
3011|                    note=(
3012|                        f"htf_state={getattr(parent_feed.htf_state, 'name', None)} "
--- L3036 ---
3032|                # ── layer_trace: L8 (runtime ledger — trade birth on the backtest rail) ──
3033|                # Placed at the TOP of this block, so it reflects `engine.state.active_trade`
3034|                # as CRTEngine.process_candle built it, before any of this block's own
3035|                # bookkeeping runs. Read-only; contributes nothing back into `_trade`.
3036|                if _layer_trace is not None and _lt_trace_id is not None:
3037|                    _lt_at = engine.state.active_trade
3038|                    _layer_trace.emit(
3039|                        trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3040|                        layer="L8", module="config_layer.crt_engine_v2.Trade", status="PASS",
3041|                        output_hash=getattr(_lt_at, "id", None),
--- L3039 ---
3035|                # bookkeeping runs. Read-only; contributes nothing back into `_trade`.
3036|                if _layer_trace is not None and _lt_trace_id is not None:
3037|                    _lt_at = engine.state.active_trade
3038|                    _layer_trace.emit(
3039|                        trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3040|                        layer="L8", module="config_layer.crt_engine_v2.Trade", status="PASS",
3041|                        output_hash=getattr(_lt_at, "id", None),
3042|                        note=(
3043|                            f"birth_site=crt_engine_v2.TRADE_OPENED direction={getattr(getattr(_lt_at, 'direction', None), 'name', None)} "
3044|                            f"entry={getattr(_lt_at, 'entry_price', None)} sl={getattr(_lt_at, 'sl_price', None)} "
--- L3300 ---
3296|                                f"engine_runner:{_stage}:{_reason}", candle.timestamp
3297|                            )
3298|                            state_path = []
3299|                        # ── layer_trace: L5/L6 (EngineRunner evidence + fusion/decision) ──
3300|                        if _layer_trace is not None and _lt_trace_id is not None:
3301|                            _layer_trace.emit(
3302|                                trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3303|                                layer="L5", module="core.engine_runner.EngineRunner",
3304|                                status=("REJECT" if _engine_vetoed else "PASS"),
3305|                                output_hash=str(_decision) or None,
--- L3302 ---
3298|                            state_path = []
3299|                        # ── layer_trace: L5/L6 (EngineRunner evidence + fusion/decision) ──
3300|                        if _layer_trace is not None and _lt_trace_id is not None:
3301|                            _layer_trace.emit(
3302|                                trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3303|                                layer="L5", module="core.engine_runner.EngineRunner",
3304|                                status=("REJECT" if _engine_vetoed else "PASS"),
3305|                                output_hash=str(_decision) or None,
3306|                                note=f"stage={_stage} reason={_reason} bypass_zone={_bypass_zone}",
3307|                            )
--- L3309 ---
3305|                                output_hash=str(_decision) or None,
3306|                                note=f"stage={_stage} reason={_reason} bypass_zone={_bypass_zone}",
3307|                            )
3308|                            _layer_trace.emit(
3309|                                trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3310|                                layer="L6", module="core.fusion_engine+core.decision_engine",
3311|                                status=("REJECT" if _engine_vetoed else "PASS"),
3312|                                output_hash=None,
3313|                                note=f"veto_mode=post_commit engine_gate_enabled=true decision={_decision}",
3314|                            )
--- L3323 ---
3319|                        # `_engine_vetoed` stays False on this path (see the caller's `if not
3320|                        # _p5_rejected and not _drift_vetoed and not _engine_vetoed:` below) —
3321|                        # this row is the ONLY record of that fact; nothing else distinguishes
3322|                        # "engine approved" from "engine never ran due to an exception".
3323|                        if _layer_trace is not None and _lt_trace_id is not None:
3324|                            _layer_trace.emit(
3325|                                trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3326|                                layer="L5", module="core.engine_runner.EngineRunner",
3327|                                status="EXCEPTION",
3328|                                note=f"fail-soft: {type(_er_exc).__name__}: {_er_exc} — trade allowed through unvetoed",
--- L3325 ---
3321|                        # this row is the ONLY record of that fact; nothing else distinguishes
3322|                        # "engine approved" from "engine never ran due to an exception".
3323|                        if _layer_trace is not None and _lt_trace_id is not None:
3324|                            _layer_trace.emit(
3325|                                trace_id=_lt_trace_id, bar_idx=candle_idx - 1, bar_ts=candle.timestamp,
3326|                                layer="L5", module="core.engine_runner.EngineRunner",
3327|                                status="EXCEPTION",
3328|                                note=f"fail-soft: {type(_er_exc).__name__}: {_er_exc} — trade allowed through unvetoed",
3329|                            )
3330|
======================================================================
schemas.md
125|    meta: Mapping[str, Any]                               # OPAQUE telemetry; never a decision input
126|
127|@dataclass(frozen=True)
128|class InterpreterReading:
129|    events: list[InterpreterEvent]; confidence: float
130|    trace_id: str                       # {NAME}-v{version}-{YYYYMMDD-HHMMSS} (deterministic)
131|    observation_time: datetime          # window's last bar ts (never wall-clock)
132|    schema_version: str = "1.0"; unknowns: list[str] = []; failure_conditions: dict = {}
133|
134|@runtime_checkable class Interpreter(Protocol):  # name/family/economic_rationale + observe()+explain()
135|class BaseInterpreter:  # subclass _observe()->(events,confidence); base validates + stamps provenance
136|```
137|
