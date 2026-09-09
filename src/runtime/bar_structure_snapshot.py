"""bar_structure_snapshot.py — the v3 `BarStructureSnapshot`: one observation-only record per bar.

CH-v3-unified-market-structure-v1 (2026-08-29). SEM-035.

WHAT THIS IS
------------
The repository computes a rich structural vocabulary on every bar — 12 CRT states, a
calendar-true parent-CRT track (RANGE_C1 / MANIPULATION_C2 / DISTRIBUTION_C3), HTFState,
ObjectiveStatus, and 9 SMC primitives — and never records them together. This module emits one
flat JSONL record per bar carrying all of it, so the question "what did the whole structural
vocabulary say at this bar?" becomes answerable.

WHAT IS GENUINELY NEW (and what is merely joined)
-------------------------------------------------
Three things, exactly:

1. **ENGINE-authoritative CRT state.** `scripts/research/build_bar_matrix.py` already emits a
   per-bar CRT column, but it comes from `features.crt_state_resolver`. F-069 measured only
   88.16% agreement between the resolver and the engine, and F-086 measured the dwell gap
   directly (resolver RANGE 21,745 vs engine RANGE 35,159). This is the first per-bar engine
   state series with run identity.
2. **SMC Zone GEOMETRY.** Every `features.smc` detector already builds a full `Zone`
   (`_geometry.py:32` — high, low, formed_at_index, bullish, mitigated) and the `*_distance`
   wrapper immediately collapses it to one tanh scalar and discards it. Zone edges, age,
   polarity and containment are computed on every bar today and thrown away.
3. **Run-scoped identity.** `instrument` + `corpus_sha256` + `run_id` + a gapless `bar_index`
   over every bar INCLUDING warmup. This is precisely what `logs/crt_transitions.jsonl` lacks
   (empty instrument, no RESET record), which is why that stream is `CC-L3-GLOBAL-UNIDENTIFIED`
   and this one is not.

Everything else is JOINED from existing surfaces, never re-derived. If that delta ever shrinks
to zero, the right move is to extend `build_bar_matrix` instead of keeping this module.

OBSERVATION ONLY — the invariant this module exists under
---------------------------------------------------------
No value produced here reaches any decision path. Three independent reasons, in increasing
order of strength:

- `bar_structure_snapshot.enabled` defaults to **false** in every config.
- Emission happens **after** `CRTEngine.process_candle` has already returned. The emitter takes
  read-only views of engine/feed state and returns None; no caller consumes its output.
- Decision-neutrality is **proven, not asserted**: `tests/test_bar_structure_decision_neutrality.py`
  runs the same corpus with emission ON and OFF and requires a byte-identical trade ledger and
  event stream. That test is the gate, and softening it would void the claim.

Per CLAUDE.md §6.5 (Authority Ladder), observation earns *tunability*, never *authority*. A
context family may only influence a decision after `MC-CTXATTR-XAUUSD-M15-V1` produces holdout
evidence AND a separate authorized change program wires it in.

OUT-OF-VECTOR
-------------
This record adds ZERO canonical feature dimensions. `CANONICAL_FEATURES` stays a 48-tuple,
`SCHEMA_HASH` stays `f52bf5d3f2ae6ddb75e8a35e9c323e07`. Adding dimensions would break
`tests/test_feature_layer_freeze.py`'s XAUUSD `vector_sha256` pin and re-stale all six model
families (F-076). The snapshot is a sidecar; the vector is untouched.

KEY ORDER IS LOAD-BEARING
-------------------------
Records are emitted as `OrderedDict` with a fixed field order. `parquet_store._order_violation`
(`src/utils/parquet_store.py:620`) checks it, for the reason documented there: a reordered
flatten group yields a scrambled feature vector in `replay_memory_engine` with no error
anywhere. Do not sort these keys.

NULL SEMANTICS
--------------
`{f}_distance` is `0.0` and NEVER null — matching `features/smc/__init__.py`'s convention that
0.0 means *no structure exists*, not *zero distance*. Every other zone field is null iff
`{f}_present` is false.

`{f}_window_truncated` records that the trailing window was SATURATED (`len(window) >=
smc_max_window`), i.e. that older structure has scrolled out of view and a `False` presence
reading may be a window artifact rather than an absence of structure. Read it honestly: with
`smc_max_window = 100` it is False only for the first ~100 bars of a corpus and True for
everything after, so it is a warmup marker, NOT a per-bar exclusion criterion. The field that
actually measures boundary proximity is `{f}_age_bars` — a zone whose age approaches
`smc_window_len` is one scroll away from vanishing, and THAT is the quantity an attribution
program should condition on. Treating `_window_truncated` as an exclusion filter would drop
99.8% of the corpus while removing no bias; the SEM-036 contract records this explicitly under
`forbidden_metric_substitutions` so the mistake cannot be made quietly.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from features.parent_candle import ParentCandleBuilder
from features.smc.breaker import breaker_distance, find_active_breaker
from features.smc.choch import change_of_character
from features.smc.fvg import find_active_fvg, fvg_distance
from features.smc.levels import eqh_eql_distance, pdh_pdl_distance
from features.smc.mitigation import find_active_mitigation_block, mitigation_block_distance
from features.smc.order_block import (
    _find_break_events,
    find_active_order_block,
    order_block_distance,
)

logger = logging.getLogger("CRT.BarStructure")

SNAPSHOT_SCHEMA_VERSION = "1.0.0"
EMITTED_BY = "runtime.bar_structure_snapshot"

#: The four SMC families that resolve to a `Zone`. Order is fixed and load-bearing (see the
#: module docstring on key order) — it is the order the record's zone blocks appear in.
ZONE_FAMILIES = ("fvg", "order_block", "breaker", "mitigation")

#: The three zone families whose detection runs off `_find_break_events`. Sharing one
#: precomputed scan across them is a ~68% saving on the SMC cost of a full corpus (measured:
#: 208s -> 66s over 47,275 XAUUSD M15 bars), and is bit-identical by construction because
#: `_find_break_events` is pure. Pinned by `tests/test_smc_break_event_memo.py`.
BREAK_EVENT_FAMILIES = ("order_block", "breaker", "mitigation")


def _require(section: dict, key: str) -> Any:
    """Strict config accessor — CLAUDE.md §6.5 forbids silent defaults for new behavioural keys."""
    if key not in section:
        raise KeyError(
            f"bar_structure_snapshot.{key} is required (no silent default). "
            "Add it to the production config bar_structure_snapshot section."
        )
    return section[key]


@dataclass(frozen=True)
class SnapshotConfig:
    """Resolved `bar_structure_snapshot` config. Frozen: read once at construction so a config
    edit mid-run cannot change what a run emits (same discipline as `CRTEngine.__init__`'s gate
    flags)."""

    enabled: bool
    schema_version: str
    output_dir: str
    filename_suffix: str
    flush_every: int
    emit_on_warmup_bars: bool
    families: dict
    eqh_eql_tolerance_atr: float
    eqh_eql_max_swings: int
    memoize_break_events: bool

    @classmethod
    def from_prod_config(cls, version: Optional[str] = None) -> Optional["SnapshotConfig"]:
        """None when the section is absent (v2 and earlier) or `enabled` is false.

        Returning None rather than raising on an ABSENT section is deliberate and is the one
        place this module departs from strict fail-fast: v3 must stay loadable by every caller
        that still runs v2_htfcrt_2026_08, and an absent section there means "this config
        predates the snapshot", not "authoring error". A PRESENT-but-incomplete section still
        fails fast via `_require`.
        """
        from config_layer.production_config import get_prod_section

        try:
            section = get_prod_section("bar_structure_snapshot", version=version)
        except (RuntimeError, KeyError):
            return None
        if not bool(_require(section, "enabled")):
            return None
        smc = _require(section, "smc")
        if not isinstance(smc, dict):
            raise TypeError("bar_structure_snapshot.smc must be a mapping")
        families = _require(section, "families")
        if not isinstance(families, dict):
            raise TypeError("bar_structure_snapshot.families must be a mapping")
        declared = str(_require(section, "schema_version"))
        if declared != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"bar_structure_snapshot.schema_version={declared!r} does not match this "
                f"module's SNAPSHOT_SCHEMA_VERSION={SNAPSHOT_SCHEMA_VERSION!r}. A schema "
                "change is a governed edit, not a config typo."
            )
        return cls(
            enabled=True,
            schema_version=declared,
            output_dir=str(_require(section, "output_dir")),
            filename_suffix=str(_require(section, "filename_suffix")),
            flush_every=int(_require(section, "flush_every")),
            emit_on_warmup_bars=bool(_require(section, "emit_on_warmup_bars")),
            families=dict(families),
            eqh_eql_tolerance_atr=float(_require(smc, "eqh_eql_tolerance_atr")),
            eqh_eql_max_swings=int(_require(smc, "eqh_eql_max_swings")),
            memoize_break_events=bool(_require(smc, "memoize_break_events")),
        )


def corpus_sha256(path: "Path | str") -> str:
    """SHA-256 of the corpus file, so a record can never be silently re-attributed to a
    different corpus. Streamed — the XAUUSD M15 CSV is tens of MB."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _state_name(state: Any) -> Optional[str]:
    """Normalise a CRT state to its NAME, accepting either the enum or an already-`.name`d str.

    `BacktestRunner` reads `engine.state.current_state.name` into `prev_state`/`curr_state`
    (`backtest_v2.py:2287,:2297`) and passes strings, while a direct `EngineState` read yields
    the enum. Accepting both here means the record's state fields are the same strings either
    way — a silent `getattr(str, "name", None) -> None` would have written nulls into the very
    column the attribution program strata on.
    """
    if state is None:
        return None
    return getattr(state, "name", None) or str(state)


def _zone_block(
    name: str,
    zone: Any,
    distance: float,
    close: float,
    atr_abs: float,
    bar_index: int,
    window_truncated: bool,
) -> "OrderedDict[str, Any]":
    """The uniform 11-field sub-record for one Zone family. See the module docstring on null
    semantics: `{f}_distance` is never null; everything else is null iff not present."""
    present = zone is not None
    if not present:
        return OrderedDict(
            [
                (f"{name}_present", False),
                (f"{name}_bullish", None),
                (f"{name}_high", None),
                (f"{name}_low", None),
                (f"{name}_mid", None),
                (f"{name}_formed_at_index", None),
                (f"{name}_age_bars", None),
                (f"{name}_width_atr", None),
                (f"{name}_inside", None),
                (f"{name}_distance", float(distance)),
                (f"{name}_window_truncated", bool(window_truncated)),
            ]
        )
    hi = float(zone.high)
    lo = float(zone.low)
    return OrderedDict(
        [
            (f"{name}_present", True),
            (f"{name}_bullish", bool(zone.bullish)),
            (f"{name}_high", hi),
            (f"{name}_low", lo),
            (f"{name}_mid", (hi + lo) / 2.0),
            (f"{name}_formed_at_index", int(zone.formed_at_index)),
            (f"{name}_age_bars", int(bar_index - zone.formed_at_index)),
            # width in ATR multiples; None (not 0.0) when ATR is degenerate, because a
            # zero-ATR width is UNDEFINED rather than "no width" — the opposite of the
            # *_distance convention, and the distinction matters to the attribution program.
            (f"{name}_width_atr", (hi - lo) / atr_abs if atr_abs and atr_abs > 0 else None),
            (f"{name}_inside", bool(lo <= close <= hi)),
            (f"{name}_distance", float(distance)),
            (f"{name}_window_truncated", bool(window_truncated)),
        ]
    )


class BarStructureEmitter:
    """Streaming per-bar snapshot writer. One instance per run per instrument.

    Streaming, not batch: the trailing `Candle` window and the D1 `ParentCandleBuilder` are
    built incrementally in chronological order, exactly as `FeaturePipeline.compute_smc_features`
    (`feature_pipeline.py:1206-1310`) does, so bar `i` can only ever see bars `<= i`. There is
    no lookahead path even in principle.
    """

    def __init__(
        self,
        cfg: SnapshotConfig,
        *,
        run_id: str,
        instrument: str,
        timeframe: str,
        corpus_path: str,
        corpus_hash: str,
        config_version: str,
        config_hash: str,
        swing_window: int,
        smc_max_window: int,
        timestamp_basis: str,
        objective_gate_enabled: bool,
        objective_gate_mode: str,
        parent_timeframe: Optional[str],
        htf_thresholds: Optional[dict],
        feature_schema_version: str,
        feature_schema_hash: str,
    ) -> None:
        self.cfg = cfg
        self._k = int(swing_window)
        self._max_window = int(smc_max_window)
        self._window: list = []
        self._d1 = ParentCandleBuilder("D1", keep=2)
        self._buffer: list = []
        self._rows = 0
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
                ("feature_schema_version", feature_schema_version),
                ("feature_schema_hash", feature_schema_hash),
            ]
        )
        self._timestamp_basis = timestamp_basis
        self._objective_gate_enabled = objective_gate_enabled
        self._objective_gate_mode = objective_gate_mode
        self._parent_timeframe = parent_timeframe
        self._htf_thresholds = htf_thresholds
        self._parent_closed_this_bar = False

    # ---- path / stats --------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def rows_written(self) -> int:
        return self._rows

    # ---- ingestion -----------------------------------------------------------------------

    def note_parent_closed(self, closed: bool) -> None:
        """Record whether a parent candle closed on this bar.

        `BacktestRunner` discards `ParentCRTFeed.push`'s return value; this captures it so the
        record can distinguish "the parent state changed on this bar" from "it is unchanged and
        carried forward". Purely a note — nothing reads it back into a decision.
        """
        self._parent_closed_this_bar = bool(closed)

    def _advance_window(self, candle) -> None:
        self._window.append(candle)
        if len(self._window) > self._max_window:
            self._window = self._window[-self._max_window :]
        self._d1.push(candle)

    def emit_warmup(self, candle, bar_index: int) -> None:
        """Identity + bar block only, for bars consumed before the engine starts.

        Emitted so `bar_index` is a GAPLESS 0..N-1 occupancy series. That gaplessness is what
        lets this stream carry `CC-CTX-RUN-SCOPED-OBSERVATION`: a stream with a coverage hole
        cannot support "the state at bar i was X" for arbitrary i, which is the failure mode
        that makes `logs/crt_transitions.jsonl` unidentified. The SMC window is still advanced
        so that post-warmup zone detection sees the same history the pipeline would have seen.
        """
        if not self.cfg.enabled:
            return
        self._advance_window(candle)
        if not self.cfg.emit_on_warmup_bars:
            return
        rec = OrderedDict(self._identity)
        rec["bar_index"] = int(bar_index)
        rec["engine_candle_index"] = None
        rec["timestamp"] = candle.timestamp.isoformat()
        rec["timestamp_basis"] = self._timestamp_basis
        rec["htf_candle_id"] = None
        rec["emitted_by"] = EMITTED_BY
        rec["phase"] = "WARMUP"
        rec["open"] = float(candle.open)
        rec["high"] = float(candle.high)
        rec["low"] = float(candle.low)
        rec["close"] = float(candle.close)
        rec["volume"] = float(candle.volume)
        rec["atr_abs"] = None
        self._write(rec)

    def emit(
        self,
        *,
        candle,
        bar_index: int,
        engine_state,
        result: dict,
        prev_state,
        curr_state,
        htf_candle_id: Optional[str],
        parent_feed,
        break_of_structure: Optional[float] = None,
        trend_bias: Optional[float] = None,
    ) -> None:
        """Build and write the full record for one processed bar.

        Called AFTER `CRTEngine.process_candle` has returned. Every argument is read-only; this
        method returns None and no caller consumes a value from it.
        """
        if not self.cfg.enabled:
            return
        self._advance_window(candle)
        close = float(candle.close)
        atr_abs = float(getattr(engine_state, "atr_abs", 0.0) or 0.0)

        rec = OrderedDict(self._identity)
        rec["bar_index"] = int(bar_index)
        rec["engine_candle_index"] = result.get("candle_index")
        rec["timestamp"] = candle.timestamp.isoformat()
        rec["timestamp_basis"] = self._timestamp_basis
        rec["htf_candle_id"] = htf_candle_id
        rec["emitted_by"] = EMITTED_BY
        rec["phase"] = "LIVE"

        # ---- bar block ----
        rec["open"] = float(candle.open)
        rec["high"] = float(candle.high)
        rec["low"] = float(candle.low)
        rec["close"] = close
        rec["volume"] = float(candle.volume)
        rec["atr_abs"] = atr_abs

        # ---- CRT block (ENGINE-authoritative; see module docstring item 1) ----
        rec.update(self._crt_block(engine_state, result, prev_state, curr_state))

        # ---- parent CRT / HTF / objective ----
        rec.update(self._parent_block(parent_feed))

        # ---- SMC ----
        rec.update(self._smc_block(close, atr_abs, bar_index, break_of_structure, trend_bias))

        self._write(rec)

    # ---- block builders -------------------------------------------------------------------

    def _crt_block(self, st, result: dict, prev_state, curr_state) -> "OrderedDict[str, Any]":
        """Field accessors follow `crt_baseline_trace.snapshot_engine_state:196` verbatim rather
        than re-deriving attribute paths off `EngineState`."""
        ar = getattr(st, "active_range", None)
        se = getattr(st, "sweep_event", None)
        dc = getattr(st, "displacement_candle", None)
        rc = getattr(st, "retest_candle", None)
        direction = getattr(st, "direction", None)
        out: "OrderedDict[str, Any]" = OrderedDict()
        before = _state_name(prev_state)
        after = _state_name(curr_state)
        out["crt_state_before"] = before
        out["crt_state_after"] = after
        out["crt_state_changed"] = before != after
        out["crt_action"] = result.get("action", "NONE")
        # Fix (2026-08-30): the engine's per-bar result dict has never carried a
        # "reject_reason" key -- RESET populates "reason" (crt_engine_v2.py:2893) and,
        # as of this fix, every FILTER_REJECTED branch does too. "reject_reason" only
        # ever existed on the separate RETEST_REPLAY telemetry record (:771), a different
        # stream this field never actually read from. Read the key that is really there.
        out["crt_reject_reason"] = result.get("reason")
        out["crt_direction"] = getattr(direction, "name", None)
        out["crt_range_h_ref"] = getattr(ar, "h_ref", None) if ar is not None else None
        out["crt_range_l_ref"] = getattr(ar, "l_ref", None) if ar is not None else None
        out["crt_range_size"] = getattr(ar, "size", None) if ar is not None else None
        out["crt_range_session"] = getattr(ar, "session", None) if ar is not None else None
        out["crt_range_htf_id"] = getattr(ar, "htf_candle_id", None) if ar is not None else None
        out["crt_sweep_price"] = getattr(se, "price", None) if se is not None else None
        out["crt_sweep_candle_index"] = (
            getattr(se, "candle_index", None) if se is not None else None
        )
        out["crt_sweep_double_confirmed"] = (
            getattr(se, "double_confirmed", None) if se is not None else None
        )
        out["crt_displacement_candle_index"] = getattr(dc, "index", None) if dc is not None else None
        out["crt_retest_candle_index"] = getattr(rc, "index", None) if rc is not None else None
        out["crt_pending_displacement_ttl"] = getattr(st, "pending_displacement_ttl", None)
        out["crt_htf_remaining_candles"] = getattr(st, "htf_remaining_candles", None)
        out["crt_evaluating_soft_conf"] = getattr(st, "evaluating_soft_conf", None)
        out["crt_trade_open"] = bool(getattr(st, "active_trade", None))
        return out

    def _parent_block(self, feed) -> "OrderedDict[str, Any]":
        """All-null when `parent_crt.enabled` is false — `ParentCRTFeed.from_prod_config`
        returns None in that case, and a null is the honest reading (not observed), never 0."""
        out: "OrderedDict[str, Any]" = OrderedDict()
        out["parent_timeframe"] = self._parent_timeframe
        out["parent_enabled"] = feed is not None
        if feed is None:
            for key in (
                "parent_crt_state",
                "parent_bias",
                "parent_range_h_ref",
                "parent_range_l_ref",
                "parent_closed_this_bar",
                "parent_last_close_ts",
                "htf_state",
                "htf_range_ratio",
                "objective_status",
                "objective_direction",
                "objective_target",
                "objective_invalidate_at",
            ):
                out[key] = None
        else:
            rng = getattr(feed.track, "range", None)
            last_parent = feed._builder.parent_candle  # read-only; no public accessor exists
            obj = feed.objective
            out["parent_crt_state"] = getattr(feed.state, "name", None)
            out["parent_bias"] = getattr(feed.bias, "name", None)
            out["parent_range_h_ref"] = getattr(rng, "h_ref", None) if rng is not None else None
            out["parent_range_l_ref"] = getattr(rng, "l_ref", None) if rng is not None else None
            out["parent_closed_this_bar"] = self._parent_closed_this_bar
            out["parent_last_close_ts"] = (
                last_parent.timestamp.isoformat() if last_parent is not None else None
            )
            out["htf_state"] = getattr(feed.htf_state, "name", None)
            out["htf_range_ratio"] = feed.last_range_ratio
            out["objective_status"] = getattr(obj.status, "name", None)
            out["objective_direction"] = getattr(obj.direction, "name", None)
            out["objective_target"] = getattr(obj, "target", None)
            out["objective_invalidate_at"] = getattr(obj, "invalidate_at", None)
        out["htf_thresholds"] = self._htf_thresholds
        # Emitted alongside the status on purpose: it makes every record self-describing about
        # whether the objective was merely OBSERVED or actually ACTING. On v2/v3 the gate is
        # disabled, so the objective family is inert and the DATA says so (F-078) rather than
        # only a docstring.
        out["objective_gate_enabled"] = self._objective_gate_enabled
        out["objective_gate_mode"] = self._objective_gate_mode
        # Reset after consumption so a bar with no parent close cannot inherit the previous
        # bar's True.
        self._parent_closed_this_bar = False
        return out

    def _smc_block(
        self,
        close: float,
        atr_abs: float,
        bar_index: int,
        break_of_structure: Optional[float],
        trend_bias: Optional[float],
    ) -> "OrderedDict[str, Any]":
        win = self._window
        k = self._k
        # Window SATURATION, not "too short to look": once the trailing window is full, older
        # structure scrolls out and a False presence reading may be a boundary artifact. True
        # for all but the first ~smc_max_window bars, so it marks warmup, not a filterable
        # subset -- see the module docstring, and use `{f}_age_bars` against `smc_window_len`
        # for real boundary proximity.
        truncated = len(win) >= self._max_window
        out: "OrderedDict[str, Any]" = OrderedDict()
        out["smc_window_len"] = len(win)
        out["smc_max_window"] = self._max_window
        out["smc_swing_window"] = k

        if len(win) < 3:
            for fam in ZONE_FAMILIES:
                out.update(_zone_block(fam, None, 0.0, close, atr_abs, bar_index, truncated))
            out.update(self._level_block(close, atr_abs, empty=True))
            out.update(self._choch_block(break_of_structure, trend_bias))
            return out

        events = _find_break_events(win, k) if self.cfg.memoize_break_events else None

        fvg_zone = find_active_fvg(win)
        out.update(
            _zone_block("fvg", fvg_zone, fvg_distance(win, atr_abs), close, atr_abs, bar_index, truncated)
        )

        ob_zone = find_active_order_block(win, k, events)
        out.update(
            _zone_block(
                "order_block",
                ob_zone,
                order_block_distance(win, k, atr_abs, events),
                close,
                atr_abs,
                bar_index,
                truncated,
            )
        )

        brk_zone = find_active_breaker(win, k, events)
        out.update(
            _zone_block(
                "breaker",
                brk_zone,
                breaker_distance(win, k, atr_abs, events),
                close,
                atr_abs,
                bar_index,
                truncated,
            )
        )

        mit_zone = find_active_mitigation_block(win, k, events)
        out.update(
            _zone_block(
                "mitigation",
                mit_zone,
                mitigation_block_distance(win, k, atr_abs, events),
                close,
                atr_abs,
                bar_index,
                truncated,
            )
        )

        out.update(self._level_block(close, atr_abs, empty=False))
        out.update(self._choch_block(break_of_structure, trend_bias))
        return out

    def _level_block(self, close: float, atr_abs: float, *, empty: bool) -> "OrderedDict[str, Any]":
        hist = self._d1.parent_history
        if empty:
            pdh_d = pdl_d = eqh_d = eql_d = 0.0
            prev_day = None
        else:
            pdh_d, pdl_d = pdh_pdl_distance(close, hist, atr_abs)
            eqh_d, eql_d = eqh_eql_distance(
                self._window,
                self._k,
                atr_abs,
                tolerance_atr=self.cfg.eqh_eql_tolerance_atr,
                max_swings=self.cfg.eqh_eql_max_swings,
            )
            prev_day = hist[-1] if hist else None
        out: "OrderedDict[str, Any]" = OrderedDict()
        out["pdh_present"] = prev_day is not None
        out["pdh_price"] = float(prev_day.high) if prev_day is not None else None
        out["pdh_distance"] = float(pdh_d)
        out["pdl_present"] = prev_day is not None
        out["pdl_price"] = float(prev_day.low) if prev_day is not None else None
        out["pdl_distance"] = float(pdl_d)
        out["pdh_pdl_day_ts"] = prev_day.timestamp.isoformat() if prev_day is not None else None
        # EQH/EQL presence is INFERRED from a non-zero distance: `eqh_eql_distance` returns
        # exactly 0.0 when no cluster exists (`levels.py:66-67`), matching the *_distance
        # convention. Not re-deriving the cluster here keeps this module a pure consumer of the
        # canonical detector rather than a second implementation of it.
        out["eqh_present"] = bool(eqh_d != 0.0)
        out["eqh_distance"] = float(eqh_d)
        out["eql_present"] = bool(eql_d != 0.0)
        out["eql_distance"] = float(eql_d)
        return out

    def _choch_block(self, bos: Optional[float], tb: Optional[float]) -> "OrderedDict[str, Any]":
        """CHoCH is JOINED from the canonical pipeline columns, never re-derived here.

        `change_of_character` (`smc/choch.py:20`) is pure algebra over `break_of_structure`
        (FM-057) and `trend_bias` (FM-054), both canonical pipeline columns. When the caller
        cannot supply them the value is null and `choch_basis` says so — it is NOT silently
        computed from a locally-invented BOS, which would fork from the canonical feature and
        reopen the ontology's BOS/CHoCH detection-state-machine exclusion
        (`market_ontology.yaml:32`).
        """
        out: "OrderedDict[str, Any]" = OrderedDict()
        if bos is None or tb is None:
            out["choch_value"] = None
            out["choch_basis"] = "UNAVAILABLE_NO_PIPELINE_COLUMNS"
            out["break_of_structure"] = None
            out["trend_bias"] = None
        else:
            out["choch_value"] = float(change_of_character(float(bos), float(tb)))
            out["choch_basis"] = "PIPELINE_FM057_FM054"
            out["break_of_structure"] = float(bos)
            out["trend_bias"] = float(tb)
        return out

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
        }
