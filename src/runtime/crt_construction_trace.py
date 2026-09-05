"""crt_construction_trace.py — the v4 `CRTConstructionTrace`: engine vs ontology, per bar.

CH-v4-dual-construction-crt-trace-2026-08-30. SEM-TBD (allocate via Semantic OS before
promotion; not yet registered — see module docstring "AUTHORITY" section).

WHAT THIS IS
------------
`crt_engine_v2.py` (the EXECUTION authority) and `configs/formulas/market_crt_states.yaml` +
`features/crt_state_resolver.py` (the declarative MEANING layer) independently construct a CRT
state for every bar, and disagree substantially: F-069 measured 88.16% agreement as a one-off
study; F-086 measured the dwell gap directly (resolver RANGE 21,745 vs engine RANGE 35,159).
Neither number is a per-bar record — both are corpus-level aggregates from offline replay
scripts. This module emits one flat JSONL record per bar carrying BOTH constructions' answers,
plus the engine's own threshold-level gate trace for that bar, so "where and why do execution
and meaning diverge" becomes a query instead of a research program.

WHAT IS GENUINELY NEW (and what is merely joined)
-------------------------------------------------
1. **Per-bar identity for the comparison.** Every prior measurement (F-069, F-086,
   `scripts/research/run_crt_state_on_mt5_xauusd.py`) is a corpus-level aggregate. This is the
   first per-bar record with run identity, joinable to `v3`'s `bar_structure_snapshot` by
   `run_id` + `bar_index`.
2. **NOTHING else is new code.** The ontology label is JOINED from `CRTStateResolver.resolve()`
   (unmodified, called with `injection="none"` — see RISK 1 below). The gate detail is JOINED
   from `CRTBaselineTraceHooks` (`runtime/crt_baseline_trace.py`), an EXISTING, already-decision-
   neutral, already-tested (`tests/test_crt_baseline_trace.py`) engine facility that has existed
   since before this module and was previously only reachable from one-off analysis scripts
   (`scripts/analysis/xauusd_crt_baseline_trace.py`). This module is a JOIN + persistence layer
   over two already-built read paths, not a new construction.

OBSERVATION ONLY — the invariant this module exists under
---------------------------------------------------------
- `crt_construction_trace.enabled` defaults to **false** in every config.
- The resolver call and the baseline-trace read both happen AFTER `CRTEngine.process_candle`
  has already returned for this bar. Nothing produced here is consumed by the backtest loop.
- `engine.baseline_trace` attachment is itself decision-neutral by the PRE-EXISTING contract at
  `crt_baseline_trace.py`'s own docstring: "Does NOT recompute features, re-evaluate guards, or
  mutate CRT control flow." This module inherits that guarantee rather than re-proving it, but
  see `tests/test_crt_construction_trace.py::test_decision_neutrality_full_corpus` for the
  parity re-proof anyway (same discipline as `bar_structure_snapshot`).

RISK 1 — INJECTION MUST STAY OFF (load-bearing)
------------------------------------------------
`CRTStateResolver.resolve()` accepts `engine_state_to=` / `engine_reset=` kwargs, documented
"Research-shadow only" — they inject the ENGINE's answer into the resolver's decision. F-069
records that the historical instrument ran with unconditional injection and produced 64-99%
"agreement" figures that "never measured configuration alone." This module NEVER passes either
kwarg (`_ONTOLOGY_INJECTION = "none"`, asserted in `__init__`). If agreement ever reads far above
F-069's 88.16% baseline on the same corpus, injection has leaked back in — treat that as a defect
in this module, not a finding about the ontology.

RISK 2 — RESOLVER EXECUTION/RESOLUTION ARE EXPECTED-ZERO
-----------------------------------------------------------
`market_crt_states.yaml`'s own header: the shadow resolver's EXECUTION gate fail-closes without
a risk-score feature, which the canonical pipeline vector does not carry. So `ontology_state`
will show 0 EXECUTION/RESOLUTION bars on any corpus, and every engine EXECUTION/RESOLUTION bar
will read as a disagreement. This is EXPECTED per the ontology's own documented limitation, not
a defect this module or a future reader should "discover" as a finding.

RISK 3 — 9 ONTOLOGY STATES vs 12 ENGINE STATES
-------------------------------------------------
`market_crt_states.yaml` defines 9 M15 states. `state_identity.py`'s `CRTState` enum carries 12
(F-075 added 3 parent-CRT states — RANGE_C1/MANIPULATION_C2/DISTRIBUTION_C3 — as a declared
DISJOINT sub-graph on a separate HTF track, already present in `v3`'s `parent_crt_state` field).
`agree` compares `engine_state` only against the 9 M15 states; parent-CRT is out of scope here
by construction, not by omission.

AUTHORITY
---------
Per CLAUDE.md §6.5 Authority Ladder: this module grants **information**, never economic value,
never production authority, never architecture justification. Per §6.6: it introduces no new
market quantity — both constructions it joins already exist and are independently authoritative
within their own scope; this module changes neither's meaning. A SEM id for the JOIN itself
(not for either construction) should be allocated through the Semantic OS registry before any
downstream program cites this stream as evidence — deliberately left unregistered pending that.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("CRT.ConstructionTrace")

TRACE_SCHEMA_VERSION = "1.0.0"
EMITTED_BY = "runtime.crt_construction_trace"

#: The 9 M15 CRT states `market_crt_states.yaml` defines. Frozen here rather than read from the
#: resolver at emit time so a value outside this set is loud (a KeyError from `.remove`-style
#: strict checks would be a schema drift signal, not silently absorbed).
ONTOLOGY_M15_STATES = frozenset(
    {"RANGE", "SWEEP", "DISPLACEMENT", "SHADOW_PENDING", "EXPANSION",
     "RETEST", "EXECUTION", "RESOLUTION", "EXPIRED"}
)

#: Hard-pinned — see module docstring RISK 1. Never override from a caller.
_ONTOLOGY_INJECTION = "none"


def _require(section: dict, key: str) -> Any:
    """Strict config accessor — CLAUDE.md §6.5 forbids silent defaults for new behavioural keys."""
    if key not in section:
        raise KeyError(
            f"crt_construction_trace.{key} is required (no silent default). "
            "Add it to the production config crt_construction_trace section."
        )
    return section[key]


@dataclass(frozen=True)
class ConstructionTraceConfig:
    """Resolved `crt_construction_trace` config. Frozen: read once at construction."""

    enabled: bool
    schema_version: str
    output_dir: str
    filename_suffix: str
    flush_every: int
    ontology_source: str
    record_engine_gates: bool
    emit_on_warmup_bars: bool

    @classmethod
    def from_prod_config(cls, version: Optional[str] = None) -> Optional["ConstructionTraceConfig"]:
        """None when the section is absent (v3 and earlier) or `enabled` is false.

        Mirrors `bar_structure_snapshot.SnapshotConfig.from_prod_config`'s discipline exactly:
        absent section -> None (predates this feature), present-but-incomplete -> fail fast.
        """
        from config_layer.production_config import get_prod_section

        try:
            section = get_prod_section("crt_construction_trace", version=version)
        except (RuntimeError, KeyError):
            return None
        if not bool(_require(section, "enabled")):
            return None
        declared = str(_require(section, "schema_version"))
        if declared != TRACE_SCHEMA_VERSION:
            raise ValueError(
                f"crt_construction_trace.schema_version={declared!r} does not match this "
                f"module's TRACE_SCHEMA_VERSION={TRACE_SCHEMA_VERSION!r}. A schema change is "
                "a governed edit, not a config typo."
            )
        injection = str(_require(section, "injection"))
        if injection != _ONTOLOGY_INJECTION:
            raise ValueError(
                f"crt_construction_trace.injection={injection!r} is not allowed — this module "
                f"hard-pins {_ONTOLOGY_INJECTION!r} (see module docstring RISK 1). The config "
                "key exists so intent is legible in the JSON, not to make injection selectable."
            )
        return cls(
            enabled=True,
            schema_version=declared,
            output_dir=str(_require(section, "output_dir")),
            filename_suffix=str(_require(section, "filename_suffix")),
            flush_every=int(_require(section, "flush_every")),
            ontology_source=str(_require(section, "ontology_source")),
            record_engine_gates=bool(_require(section, "record_engine_gates")),
            emit_on_warmup_bars=bool(_require(section, "emit_on_warmup_bars")),
        )


def _state_name(state: Any) -> Optional[str]:
    """Normalise a CRT state to its NAME. Mirrors `bar_structure_snapshot._state_name` exactly
    so the two modules agree on how a state prints regardless of enum-vs-str input."""
    if state is None:
        return None
    return getattr(state, "name", None) or str(state)


class ConstructionTraceEmitter:
    """Streaming per-bar dual-construction record writer. One instance per run per instrument.

    Owns a `CRTStateResolver` (constructed once; NEVER passed injection kwargs at call time —
    see module docstring RISK 1) and, when `record_engine_gates` is true, a
    `CRTBaselineTraceHooks` that the caller must attach to `engine.baseline_trace` and enable
    before each `process_candle()` call this module will trace.
    """

    def __init__(
        self,
        cfg: ConstructionTraceConfig,
        *,
        run_id: str,
        instrument: str,
        timeframe: str,
        corpus_path: str,
        corpus_hash: str,
        config_version: str,
        config_hash: str,
        ontology_version: Any,
    ) -> None:
        from features.crt_state_resolver import CRTStateResolver

        self.cfg = cfg
        self._resolver = CRTStateResolver(config_path=cfg.ontology_source)
        self._path = Path(cfg.output_dir) / f"{instrument}{cfg.filename_suffix}"
        self._identity = OrderedDict(
            [
                ("schema_version", cfg.schema_version),
                ("run_id", run_id),
                ("instrument", instrument),
                ("timeframe", timeframe),
                ("corpus_path", corpus_path),
                ("corpus_sha256", corpus_hash),
                ("config_version", config_version),
                ("config_hash", config_hash),
                ("ontology_source", cfg.ontology_source),
                ("ontology_version", ontology_version),
            ]
        )
        self._buffer: list = []
        self._rows = 0
        self._agree_count = 0
        self._compared_count = 0

    # ---- path / stats --------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows

    @property
    def agreement_rate(self) -> Optional[float]:
        """Running agreement over M15-scoped comparisons only (RISK 3). None until any exist."""
        if self._compared_count == 0:
            return None
        return self._agree_count / self._compared_count

    # ---- baseline-trace hook factory ------------------------------------------------------

    def new_gate_hooks(self):
        """A fresh `CRTBaselineTraceHooks`, or None if `record_engine_gates` is false.

        Caller attaches the result to `engine.baseline_trace` and toggles `.enabled` per bar
        (mirrors the established pattern in `scripts/analysis/xauusd_crt_baseline_trace.py`).
        A caller that never calls this and never attaches anything is unaffected — the engine's
        own `self.baseline_trace` defaults to None regardless of this module's existence.
        """
        if not self.cfg.record_engine_gates:
            return None
        from runtime.crt_baseline_trace import CRTBaselineTraceHooks

        hooks = CRTBaselineTraceHooks()
        hooks.enabled = True
        return hooks

    # ---- emission --------------------------------------------------------------------------

    def emit_warmup(self, bar_index: int, timestamp) -> None:
        """Identity-only row for a warmup bar, so `bar_index` stays gapless (mirrors
        `bar_structure_snapshot.emit_warmup`'s reasoning)."""
        if not self.cfg.enabled or not self.cfg.emit_on_warmup_bars:
            return
        rec = OrderedDict(self._identity)
        rec["bar_index"] = int(bar_index)
        rec["timestamp"] = timestamp.isoformat() if timestamp is not None else None
        rec["emitted_by"] = EMITTED_BY
        rec["phase"] = "WARMUP"
        rec["engine_state_before"] = None
        rec["engine_state_after"] = None
        rec["engine_action"] = None
        rec["engine_reason"] = None
        rec["ontology_state"] = None
        rec["agree"] = None
        rec["divergence_pair"] = None
        rec["engine_gates"] = None
        self._write(rec)

    def emit(
        self,
        *,
        bar_index: int,
        timestamp,
        htf_id: Optional[str],
        engine_state_before,
        engine_state_after,
        engine_action: Optional[str],
        engine_reason: Optional[str],
        feature_dict: Optional[dict],
        gate_hooks,
    ) -> None:
        """Build and write the full record for one processed bar.

        Called AFTER `CRTEngine.process_candle` has returned. `feature_dict` is the canonical
        vector as a name->value mapping for THIS bar, or None on a lookup miss (the ontology
        side is then recorded as `ontology_state=None`,
        `divergence_pair="ENGINE:X|ONTO:NO_FEATURES"` rather than silently skipped — a missing
        feature row is itself information, not a gap to paper over).
        """
        if not self.cfg.enabled:
            return

        eng_before = _state_name(engine_state_before)
        eng_after = _state_name(engine_state_after)

        onto_reason = "NO_FEATURES"
        if feature_dict is None:
            onto_state = None
        else:
            # Never let a resolver failure (schema drift, an unexpected corpus, a future
            # predicate-validation error) take the backtest down with it -- this is an
            # observation sidecar, same discipline as `_build_bar_structure_emitter`
            # ("Construction failure NEVER breaks a backtest"). Degrades to
            # `ontology_state=None` (recorded via `divergence_pair`), never re-raises.
            try:
                onto_state = self._resolver.resolve(
                    feature_dict, timestamp=timestamp, htf_id=htf_id
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "CRTStateResolver.resolve() failed at bar_index=%s (recorded as "
                    "ontology_state=None, backtest unaffected): %s", bar_index, exc,
                )
                onto_state = None
                onto_reason = "RESOLVER_ERROR"

        rec = OrderedDict(self._identity)
        rec["bar_index"] = int(bar_index)
        rec["timestamp"] = timestamp.isoformat() if timestamp is not None else None
        rec["emitted_by"] = EMITTED_BY
        rec["phase"] = "LIVE"
        rec["engine_state_before"] = eng_before
        rec["engine_state_after"] = eng_after
        rec["engine_action"] = engine_action
        rec["engine_reason"] = engine_reason
        rec["ontology_state"] = onto_state

        # ---- comparison (RISK 3: engine state must be one of the 9 M15 states to count) ----
        if onto_state is None:
            rec["agree"] = None
            rec["divergence_pair"] = f"ENGINE:{eng_after}|ONTO:{onto_reason}"
        elif eng_after not in ONTOLOGY_M15_STATES:
            # Parent-CRT / out-of-vocabulary engine state — not comparable (RISK 3), not a
            # disagreement. Recorded, not silently dropped.
            rec["agree"] = None
            rec["divergence_pair"] = f"ENGINE:{eng_after}|ONTO:{onto_state}|OUT_OF_SCOPE"
        else:
            agree = eng_after == onto_state
            rec["agree"] = agree
            rec["divergence_pair"] = None if agree else f"ENGINE:{eng_after}|ONTO:{onto_state}"
            self._compared_count += 1
            if agree:
                self._agree_count += 1

        # ---- engine gate detail (RISK: cost -- measured separately, see verification) ----
        if gate_hooks is not None and self.cfg.record_engine_gates:
            from runtime.crt_baseline_trace import _jsonable

            rec["engine_gates"] = [
                _jsonable(dataclasses.asdict(g)) for g in gate_hooks.guards
            ]
        else:
            rec["engine_gates"] = None

        self._write(rec)

    # ---- io ------------------------------------------------------------------------------

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
            "agreement_rate": self.agreement_rate,
            "compared_count": self._compared_count,
        }
