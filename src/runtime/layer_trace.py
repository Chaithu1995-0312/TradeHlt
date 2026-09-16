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
- `layer_trace.enabled` defaults to **true** (2026-09-16 user decision): absent section uses
  module DEFAULTS (still observation-only). Present section with `enabled: false` opts out.
  Present-but-incomplete still fails fast via `_require` (no silent partial config).
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

# Default-ON values when the production config has no `layer_trace` section (user 2026-09-16).
# A PRESENT section must still declare every key explicitly — these are NOT silent fills for a
# half-written section.
DEFAULT_OUTPUT_DIR = "results/layer_trace"
DEFAULT_FILENAME_SUFFIX = "_layer_trace.jsonl"
DEFAULT_FLUSH_EVERY = 200


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
        """Default ON (2026-09-16).

        - Absent `layer_trace` section → enabled with module DEFAULT_* (observation-only).
        - Present + `enabled: false` → None (explicit opt-out).
        - Present + `enabled: true` → every key required via `_require` (fail fast on incomplete).
        """
        from config_layer.production_config import get_prod_section

        try:
            section = get_prod_section("layer_trace", version=version)
        except (RuntimeError, KeyError):
            return cls(
                enabled=True,
                schema_version=TRACE_SCHEMA_VERSION,
                output_dir=DEFAULT_OUTPUT_DIR,
                filename_suffix=DEFAULT_FILENAME_SUFFIX,
                flush_every=DEFAULT_FLUSH_EVERY,
            )
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
