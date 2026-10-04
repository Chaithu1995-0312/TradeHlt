"""parent_crt_feed.py — streaming adapter that closes F-075's caller gap.

Composes `features.parent_candle.ParentCandleBuilder` (calendar-true closed parents)
with `config_layer.parent_crt.ParentCRTTrack` (C1/C2/C3) so a backtest (or any
child-candle loop) can pass `ParentCRTTrack.bias` into
`CRTEngine.process_candle(..., parent_state=)`.

WHY THIS MODULE EXISTS HERE (runtime, not config_layer / features)
------------------------------------------------------------------
`parent_crt.py` must not import `features` (config_layer sits below features).
`parent_candle.py` must not own the 3-candle classifier (isolation: the track
reimplements parent-scale geometry so an M15-engine change cannot perturb it).
The *caller* is the backtest loop — this adapter lives next to that caller.

NO-LOOKAHEAD: `push` only advances the track when `ParentCandleBuilder.push`
returns True (a parent just CLOSED). `bias` is therefore a function of already-
closed parents only. The in-progress H4/D1/W1/MN1 accumulator is never read.

CONFIG: `from_prod_config()` is fail-fast (CLAUDE.md §6.5). A missing
`parent_crt` key is an authoring error. `enabled:false` returns None so
`process_candle` keeps its default `parent_state=None` (byte-identical on
v2_multi_2026_04). `bias_gate_mode` other than `reject_on_mismatch` is
rejected — that is the only mode the engine implements.
"""

from __future__ import annotations

import logging
from typing import Optional

from config_layer.htf_state import (
    HTFState,
    HTFStateThresholds,
    Objective,
    ObjectiveStatus,
    classify_htf_state,
    resolve_objective,
)
from config_layer.parent_crt import ParentCRTTrack
from config_layer.production_config import get_prod_section
from config_layer.state_identity import CRTState, Direction
from features.parent_candle import ParentCandleBuilder, SUPPORTED_RULES

logger = logging.getLogger("CRT.ParentFeed")

_IMPLEMENTED_BIAS_MODE = "reject_on_mismatch"


def _require(section: dict, key: str) -> object:
    if key not in section:
        raise KeyError(
            f"parent_crt.{key} is required (no silent default). "
            "Add it to the production config parent_crt section."
        )
    return section[key]


class ParentCRTFeed:
    """One instance per instrument / parent timeframe. Push every child candle
    (including warmup); read `.bias` / `.htf_state` / `.objective` after `push`."""

    def __init__(self, rule: str, thresholds: HTFStateThresholds) -> None:
        if rule not in SUPPORTED_RULES:
            raise ValueError(
                f"ParentCRTFeed: unsupported parent timeframe {rule!r} "
                f"(expected one of {sorted(SUPPORTED_RULES)})"
            )
        self._rule = rule
        self._thresholds = thresholds
        self._builder = ParentCandleBuilder(rule, keep=3)
        self._track = ParentCRTTrack()
        self._prev_parent = None
        self._htf_state = HTFState.UNKNOWN
        self._objective = Objective(ObjectiveStatus.NONE, Direction.NONE)

    @property
    def rule(self) -> str:
        return self._rule

    @property
    def bias(self) -> Direction:
        return self._track.bias

    @property
    def state(self) -> CRTState:
        return self._track.state

    @property
    def track(self) -> ParentCRTTrack:
        return self._track

    @property
    def htf_state(self) -> HTFState:
        return self._htf_state

    @property
    def objective(self) -> Objective:
        return self._objective

    @property
    def last_range_ratio(self) -> Optional[float]:
        """The parent range ratio `curr_range / prev_range` behind the CURRENT `htf_state`,
        or None before two parents have closed.

        OBSERVATION ONLY (CH-v3-unified-market-structure-v1). `classify_htf_state` computes
        this ratio at `htf_state.py:96` and returns only the enum, so the magnitude that
        decided ACCUMULATION vs DISTRIBUTION vs EXPANSION is otherwise unrecoverable
        downstream. Pure and derived — it reads `parent_history` (the same two already-closed
        parents `push` passed to `classify_htf_state`) and stores no new state, so no decision
        path can observe it and nothing here can drift from the classifier. The `prev_range > 0`
        fallback deliberately mirrors `htf_state.py:96` exactly rather than returning None, so
        the emitted value always equals the ratio the classifier actually used.
        """
        hist = self._builder.parent_history
        if len(hist) < 2:
            return None
        prev, curr = hist[-2], hist[-1]
        prev_range = prev.high - prev.low
        return (curr.high - curr.low) / prev_range if prev_range > 0 else 1.0

    def push(self, candle) -> bool:
        """Feed one child candle. Returns True iff a parent just closed and the
        track advanced on that closed parent."""
        closed = self._builder.push(candle)
        if not closed:
            return False
        parent = self._builder.parent_candle
        if parent is None:  # pragma: no cover — push True always appends history
            raise RuntimeError("ParentCRTFeed: builder reported a close with no parent_candle")
        if self._prev_parent is not None:
            self._htf_state = classify_htf_state(
                self._prev_parent, parent, self._thresholds
            )
        else:
            self._htf_state = HTFState.UNKNOWN
        prev = self._track.state
        self._track.on_parent_close(parent)
        self._objective = resolve_objective(
            self._track.bias, self._track.range, parent.close
        )
        self._prev_parent = parent
        if self._track.state != prev:
            logger.info(
                "parent_crt %s %s -> %s bias=%s htf=%s obj=%s ts=%s",
                self._rule, prev.name, self._track.state.name,
                self._track.bias.value, self._htf_state.value,
                self._objective.status.value, parent.timestamp,
            )
        return True

    @classmethod
    def from_prod_config(cls) -> Optional["ParentCRTFeed"]:
        """None when `parent_crt.enabled` is false. Raises on missing/illegal keys."""
        section = get_prod_section("parent_crt")
        enabled = bool(_require(section, "enabled"))
        timeframe = str(_require(section, "timeframe"))
        mode = str(_require(section, "bias_gate_mode"))
        if mode != _IMPLEMENTED_BIAS_MODE:
            raise ValueError(
                f"parent_crt.bias_gate_mode={mode!r} is not implemented "
                f"(only {_IMPLEMENTED_BIAS_MODE!r} exists on CRTEngine.process_candle)"
            )
        if timeframe not in SUPPORTED_RULES:
            raise ValueError(
                f"parent_crt.timeframe={timeframe!r} is not a parent rule "
                f"(expected one of {sorted(SUPPORTED_RULES)})"
            )
        htf_cfg = _require(section, "htf_state")
        if not isinstance(htf_cfg, dict):
            raise TypeError("parent_crt.htf_state must be a mapping")
        thresholds = HTFStateThresholds(
            expansion_min_range_ratio=float(
                _require(htf_cfg, "expansion_min_range_ratio")
            ),
            accumulation_max_range_ratio=float(
                _require(htf_cfg, "accumulation_max_range_ratio")
            ),
            distribution_min_range_ratio=float(
                _require(htf_cfg, "distribution_min_range_ratio")
            ),
        )
        obj_cfg = _require(section, "objective_gate")
        if not isinstance(obj_cfg, dict):
            raise TypeError("parent_crt.objective_gate must be a mapping")
        obj_mode = str(_require(obj_cfg, "mode"))
        _require(obj_cfg, "enabled")
        if obj_mode != "allow_exists_only":
            raise ValueError(
                f"parent_crt.objective_gate.mode={obj_mode!r} is not implemented "
                "(only 'allow_exists_only' exists)"
            )
        if not enabled:
            return None
        return cls(timeframe, thresholds)
