"""
bar_semantic_tracker.py
=======================
Versioned, append-only **bar-level semantic journal** for training / eval
pipelines. Designed so a later LLM can *explain* what happened bar-by-bar
without re-deriving CRT state or inventing reasons.

Design rules (careful, non-negotiable)
--------------------------------------
1. **Stable vocabulary.** ``kind`` and ``reason_code`` are closed enums for a
   given ``SCHEMA_VERSION``. Do not invent free-text codes mid-run.
2. **Meaning over noise.** Default mode writes *interesting* bars fully
   (state change, sweep, label accept/skip, exception). Quiet RANGE ticks are
   summarized by heartbeats — not 47k identical lines — unless
   ``every_bar=True``.
3. **Narrative seed, not prose essay.** Each event carries a one-sentence
   ``narrative`` in present-tense observational English for LLM grounding.
   The LLM must not invent a different cause than ``reason_code``.
4. **No authority.** Journal is observational. Never a promotion gate, never
   a live decision input.
5. **Deterministic fields first.** Numbers/enums first; narrative is derived
   from them by templates (no model call here).
6. **Append-only JSONL.** One object per line; safe to stream-tail.

Schema version
--------------
``bar_semantic.v1`` — if fields/kinds change incompatibly, bump the version
and keep a reader that can still parse v1 for history.

LLM consumption contract
------------------------
Given a journal slice, an explainer should answer:
  * What was the CRT state and did it change?
  * Was this bar a training-unit candidate? Why / why not?
  * If labeled, what exit geometry and y_rr resulted?
  * Where is the pipeline in wall-clock progress?

Do **not** treat ``narrative`` as ground truth superior to ``reason_code``;
narrative is a rendering of the structured fields.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TextIO


SCHEMA_VERSION = "bar_semantic.v1"
TRACKER_ID = "training.bar_semantic_tracker"


class Kind(str, Enum):
    """Closed set of journal event kinds (v1)."""

    PHASE_START = "PHASE_START"
    PHASE_END = "PHASE_END"
    PROGRESS = "PROGRESS"
    WARMUP = "WARMUP"
    CRT_TICK = "CRT_TICK"              # quiet bar (only if every_bar)
    STATE_TRANSITION = "STATE_TRANSITION"
    SWEEP_CANDIDATE = "SWEEP_CANDIDATE"
    LABEL_ACCEPTED = "LABEL_ACCEPTED"
    LABEL_SKIPPED = "LABEL_SKIPPED"
    HOLDOUT = "HOLDOUT"
    CRT_EXCEPTION = "CRT_EXCEPTION"
    FEATURE_MISS = "FEATURE_MISS"
    EVAL_SCORE = "EVAL_SCORE"          # optional per-bar eval (interesting only)
    NOTE = "NOTE"                      # free structured note (still needs reason_code)


class ReasonCode(str, Enum):
    """Closed set of machine reason codes (v1). Narrative must not contradict these."""

    # lifecycle
    PHASE_BEGIN = "phase_begin"
    PHASE_COMPLETE = "phase_complete"
    HEARTBEAT = "heartbeat"
    # stream
    WARMUP_SKIP = "warmup_skip"
    CRT_OK = "crt_ok"
    CRT_ERROR = "crt_error"
    STATE_CHANGED = "state_changed"
    # candidate / label path
    SWEEP_DETECTED = "sweep_detected"
    NO_DIRECTION = "no_direction"
    IN_HOLDOUT_WINDOW = "in_holdout_window"
    TS_NOT_IN_RAW = "ts_not_in_raw"
    IDX_OOB = "idx_oob"
    NO_FEATURES = "no_features"
    FEATURE_CAST_FAIL = "feature_cast_fail"
    FORWARD_WALK_FAIL = "forward_walk_fail"
    LABEL_OK = "label_ok"
    NOT_SWEEP = "not_sweep"
    # eval
    SCORE_OK = "score_ok"
    SCORE_FAIL = "score_fail"
    # misc
    OPERATOR_NOTE = "operator_note"


# Templates: reason_code → narrative skeleton. {fields} filled from event payload.
_NARRATIVE_TEMPLATES: dict[ReasonCode, str] = {
    ReasonCode.PHASE_BEGIN: (
        "Phase {phase} started for {instrument} (run_id={run_id})."
    ),
    ReasonCode.PHASE_COMPLETE: (
        "Phase {phase} finished: streamed={n_streamed}, units={n_units}, "
        "skips={n_skips}, elapsed_s={elapsed_s:.1f}."
    ),
    ReasonCode.HEARTBEAT: (
        "Progress {pct:.1f}% — bar {bar_index}/{total_bars} @ {timestamp}; "
        "rate={rate_bps:.1f} bars/s; ETA {eta_s:.0f}s; "
        "units={n_units}, state={crt_state}."
    ),
    ReasonCode.WARMUP_SKIP: (
        "Bar {bar_index} @ {timestamp} still in CRT warmup "
        "({n_streamed}/{warmup_n}); no labeling."
    ),
    ReasonCode.CRT_OK: (
        "Bar {bar_index} @ {timestamp}: CRT tick, state={crt_state} "
        "(prev={crt_state_prev})."
    ),
    ReasonCode.CRT_ERROR: (
        "Bar {bar_index} @ {timestamp}: CRT process_candle raised "
        "{error_type}: {error_msg}."
    ),
    ReasonCode.STATE_CHANGED: (
        "Bar {bar_index} @ {timestamp}: CRT state {crt_state_prev} → {crt_state}"
        "{event_clause}."
    ),
    ReasonCode.SWEEP_DETECTED: (
        "Bar {bar_index} @ {timestamp}: SWEEP candidate direction={direction}, "
        "state={crt_state}; evaluating label path."
    ),
    ReasonCode.NO_DIRECTION: (
        "Bar {bar_index} @ {timestamp}: SWEEP seen but direction unresolved; "
        "skipped for training."
    ),
    ReasonCode.IN_HOLDOUT_WINDOW: (
        "Bar {bar_index} @ {timestamp}: SWEEP in holdout/eval window "
        "(ts≥{holdout_start}); excluded from train labels."
    ),
    ReasonCode.TS_NOT_IN_RAW: (
        "Bar @ {timestamp}: timestamp not found in raw OHLCV index map; skipped."
    ),
    ReasonCode.IDX_OOB: (
        "Bar {bar_index}: index out of bounds for forward_walk future slice; skipped."
    ),
    ReasonCode.NO_FEATURES: (
        "Bar {bar_index} @ {timestamp}: no FeaturePipeline row for timestamp; skipped."
    ),
    ReasonCode.FEATURE_CAST_FAIL: (
        "Bar {bar_index} @ {timestamp}: canonical feature cast failed; skipped."
    ),
    ReasonCode.FORWARD_WALK_FAIL: (
        "Bar {bar_index} @ {timestamp}: forward_walk({exit_model}) failed "
        "({error_type}); skipped."
    ),
    ReasonCode.LABEL_OK: (
        "Bar {bar_index} @ {timestamp}: labeled train unit direction={direction}, "
        "y_rr={y_rr:.4f} (gross={rr_gross:.4f}), exit={exit_reason}, "
        "entry={entry:.4f}, atr_abs={atr_abs:.6f}."
    ),
    ReasonCode.NOT_SWEEP: (
        "Bar {bar_index} @ {timestamp}: no SWEEP; state={crt_state}; observe only."
    ),
    ReasonCode.SCORE_OK: (
        "Bar {bar_index} @ {timestamp}: eval score={score:.4f}, "
        "expected_rr={expected_rr:.4f}."
    ),
    ReasonCode.SCORE_FAIL: (
        "Bar {bar_index} @ {timestamp}: eval score failed ({error_type})."
    ),
    ReasonCode.OPERATOR_NOTE: "{note}",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _render_narrative(reason: ReasonCode, fields: dict[str, Any]) -> str:
    tmpl = _NARRATIVE_TEMPLATES.get(reason, "{reason_code}")
    # Safe defaults so missing keys do not crash the journal
    base: dict[str, Any] = {
        "phase": "?",
        "instrument": "?",
        "run_id": "?",
        "bar_index": -1,
        "total_bars": 0,
        "timestamp": "?",
        "pct": 0.0,
        "rate_bps": 0.0,
        "eta_s": 0.0,
        "n_units": 0,
        "n_streamed": 0,
        "n_skips": 0,
        "elapsed_s": 0.0,
        "warmup_n": 0,
        "crt_state": "?",
        "crt_state_prev": "?",
        "event_clause": "",
        "direction": "?",
        "holdout_start": "?",
        "exit_model": "?",
        "error_type": "?",
        "error_msg": "?",
        "y_rr": 0.0,
        "rr_gross": 0.0,
        "exit_reason": "?",
        "entry": 0.0,
        "atr_abs": 0.0,
        "score": 0.0,
        "expected_rr": 0.0,
        "note": "",
        "reason_code": reason.value,
    }
    base.update({k: v for k, v in fields.items() if v is not None})
    # event_clause convenience
    if base.get("crt_event"):
        base["event_clause"] = f", crt_event={base['crt_event']}"
    try:
        return tmpl.format(**base)
    except Exception:
        return f"{reason.value}: { {k: base.get(k) for k in ('bar_index','timestamp','crt_state')} }"


@dataclass
class BarSemanticTracker:
    """Append-only JSONL journal + stdout heartbeats for one pipeline run."""

    run_id: str
    instrument: str
    path: Path
    total_bars: int = 0
    every_bar: bool = False
    heartbeat_every: int = 500
    phase: str = "init"
    # internal
    _fh: Optional[TextIO] = field(default=None, repr=False)
    _t0: float = field(default_factory=time.perf_counter, repr=False)
    _n_streamed: int = 0
    _n_units: int = 0
    _n_events: int = 0
    _skip_counts: Counter = field(default_factory=Counter)
    _kind_counts: Counter = field(default_factory=Counter)
    _last_state: Optional[str] = None
    _closed: bool = False

    def open(self) -> "BarSemanticTracker":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self._t0 = time.perf_counter()
        self.emit(
            Kind.PHASE_START,
            ReasonCode.PHASE_BEGIN,
            bar_index=-1,
            timestamp=None,
            extra={"phase": self.phase},
        )
        return self

    def set_phase(self, phase: str) -> None:
        if phase == self.phase:
            return
        # close previous phase mark
        self.emit(
            Kind.PHASE_END,
            ReasonCode.PHASE_COMPLETE,
            bar_index=self._n_streamed - 1 if self._n_streamed else -1,
            timestamp=None,
            extra={
                "phase": self.phase,
                "n_streamed": self._n_streamed,
                "n_units": self._n_units,
                "n_skips": int(sum(self._skip_counts.values())),
                "elapsed_s": time.perf_counter() - self._t0,
            },
        )
        self.phase = phase
        self.emit(
            Kind.PHASE_START,
            ReasonCode.PHASE_BEGIN,
            bar_index=self._n_streamed - 1 if self._n_streamed else -1,
            timestamp=None,
            extra={"phase": self.phase},
        )

    def close(self) -> dict:
        if not self._closed:
            self.emit(
                Kind.PHASE_END,
                ReasonCode.PHASE_COMPLETE,
                bar_index=self._n_streamed - 1 if self._n_streamed else -1,
                timestamp=None,
                extra={
                    "phase": self.phase,
                    "n_streamed": self._n_streamed,
                    "n_units": self._n_units,
                    "n_skips": int(sum(self._skip_counts.values())),
                    "elapsed_s": time.perf_counter() - self._t0,
                },
            )
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None
            self._closed = True
        return self.summary()

    def summary(self) -> dict:
        elapsed = time.perf_counter() - self._t0
        return {
            "schema_version": SCHEMA_VERSION,
            "tracker_id": TRACKER_ID,
            "run_id": self.run_id,
            "instrument": self.instrument,
            "path": str(self.path).replace("\\", "/"),
            "phase": self.phase,
            "n_streamed": self._n_streamed,
            "n_units": self._n_units,
            "n_events": self._n_events,
            "skip_counts": dict(self._skip_counts),
            "kind_counts": dict(self._kind_counts),
            "elapsed_s": elapsed,
            "rate_bars_per_s": (self._n_streamed / elapsed) if elapsed > 0 else 0.0,
            "every_bar": self.every_bar,
            "heartbeat_every": self.heartbeat_every,
            "total_bars": self.total_bars,
        }

    # ── core emit ───────────────────────────────────────────────────────
    def emit(
        self,
        kind: Kind,
        reason: ReasonCode,
        *,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str] = None,
        crt_state_prev: Optional[str] = None,
        crt_event: Optional[str] = None,
        direction: Optional[str] = None,
        action: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        force: bool = False,
    ) -> dict:
        """Write one semantic event. Returns the event dict."""
        if self._closed or self._fh is None:
            raise RuntimeError("BarSemanticTracker is closed")

        elapsed = time.perf_counter() - self._t0
        rate = (self._n_streamed / elapsed) if elapsed > 0 and self._n_streamed else 0.0
        remaining = max(self.total_bars - self._n_streamed, 0)
        eta = (remaining / rate) if rate > 0 else 0.0
        pct = (
            100.0 * self._n_streamed / self.total_bars if self.total_bars > 0 else 0.0
        )

        fields: dict[str, Any] = {
            "phase": self.phase,
            "instrument": self.instrument,
            "run_id": self.run_id,
            "bar_index": bar_index,
            "total_bars": self.total_bars,
            "timestamp": str(timestamp) if timestamp is not None else None,
            "pct": pct,
            "rate_bps": rate,
            "eta_s": eta,
            "n_units": self._n_units,
            "n_streamed": self._n_streamed,
            "n_skips": int(sum(self._skip_counts.values())),
            "elapsed_s": elapsed,
            "crt_state": crt_state,
            "crt_state_prev": crt_state_prev if crt_state_prev is not None else self._last_state,
            "crt_event": crt_event,
            "direction": direction,
        }
        if extra:
            fields.update(extra)

        narrative = _render_narrative(reason, fields)

        event = {
            "schema_version": SCHEMA_VERSION,
            "tracker_id": TRACKER_ID,
            "run_id": self.run_id,
            "instrument": self.instrument,
            "phase": self.phase,
            "wall_utc": _utc_now(),
            "kind": kind.value,
            "reason_code": reason.value,
            "bar_index": bar_index,
            "timestamp": str(timestamp) if timestamp is not None else None,
            "crt_state_prev": fields.get("crt_state_prev"),
            "crt_state": crt_state,
            "crt_event": crt_event,
            "direction": direction,
            "action": action or _default_action(kind),
            "narrative": narrative,
            "progress": {
                "n_streamed": self._n_streamed,
                "total_bars": self.total_bars,
                "pct": round(pct, 3),
                "rate_bars_per_s": round(rate, 3),
                "eta_s": round(eta, 1),
                "n_units": self._n_units,
                "elapsed_s": round(elapsed, 2),
            },
            "payload": {k: v for k, v in (extra or {}).items() if k not in fields},
        }
        # Keep payload copy of label fields when present
        for k in (
            "y_rr", "rr_gross", "exit_reason", "entry", "atr_abs",
            "score", "expected_rr", "warmup_n", "holdout_start",
            "exit_model", "error_type", "error_msg", "note",
            "sl_atr_mult", "tp_atr_mult",
        ):
            if k in fields and fields[k] is not None and k not in event["payload"]:
                event["payload"][k] = fields[k]

        line = json.dumps(event, default=str, ensure_ascii=False)
        self._fh.write(line + "\n")
        self._n_events += 1
        self._kind_counts[kind.value] += 1

        # Heartbeat kinds also go to stdout (operator visibility)
        if kind in (Kind.PROGRESS, Kind.PHASE_START, Kind.PHASE_END, Kind.NOTE):
            print(f"[BAR_SEM] {narrative}", flush=True)
        elif kind in (Kind.LABEL_ACCEPTED, Kind.CRT_EXCEPTION) or force:
            print(f"[BAR_SEM] {narrative}", flush=True)

        if crt_state is not None:
            self._last_state = crt_state
        return event

    # ── high-level helpers used by train_gaussian_xauusd ────────────────
    def on_streamed_bar(
        self,
        *,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str],
        crt_event: Optional[str],
        is_warmup: bool,
        warmup_n: int,
    ) -> None:
        """Call once per streamed candle after CRT (or during warmup)."""
        self._n_streamed += 1
        prev = self._last_state

        if is_warmup:
            # Only journal warmup sparsely: first, every heartbeat, last handled by progress
            if self._n_streamed == 1 or self._n_streamed % self.heartbeat_every == 0:
                self.emit(
                    Kind.WARMUP,
                    ReasonCode.WARMUP_SKIP,
                    bar_index=bar_index,
                    timestamp=timestamp,
                    crt_state=crt_state,
                    crt_state_prev=prev,
                    extra={"warmup_n": warmup_n, "n_streamed": self._n_streamed},
                )
            self._maybe_heartbeat(bar_index, timestamp, crt_state)
            return

        # State transition = always interesting
        if crt_state is not None and prev is not None and crt_state != prev:
            self.emit(
                Kind.STATE_TRANSITION,
                ReasonCode.STATE_CHANGED,
                bar_index=bar_index,
                timestamp=timestamp,
                crt_state=crt_state,
                crt_state_prev=prev,
                crt_event=crt_event,
                action="observe",
            )
        elif self.every_bar:
            self.emit(
                Kind.CRT_TICK,
                ReasonCode.CRT_OK,
                bar_index=bar_index,
                timestamp=timestamp,
                crt_state=crt_state,
                crt_state_prev=prev,
                crt_event=crt_event,
                action="observe",
            )
        else:
            if crt_state is not None:
                self._last_state = crt_state

        self._maybe_heartbeat(bar_index, timestamp, crt_state)

    def on_sweep_candidate(
        self,
        *,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str],
        direction: Optional[str],
    ) -> None:
        self.emit(
            Kind.SWEEP_CANDIDATE,
            ReasonCode.SWEEP_DETECTED,
            bar_index=bar_index,
            timestamp=timestamp,
            crt_state=crt_state,
            direction=direction,
            action="evaluate_label",
        )

    def on_label_skip(
        self,
        reason: ReasonCode,
        *,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str] = None,
        direction: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        self._skip_counts[reason.value] += 1
        kind = Kind.HOLDOUT if reason == ReasonCode.IN_HOLDOUT_WINDOW else Kind.LABEL_SKIPPED
        self.emit(
            kind,
            reason,
            bar_index=bar_index,
            timestamp=timestamp,
            crt_state=crt_state,
            direction=direction,
            action="skip",
            extra=extra,
        )

    def on_label_accepted(
        self,
        *,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str],
        direction: str,
        y_rr: float,
        rr_gross: float,
        exit_reason: str,
        entry: float,
        atr_abs: float,
        sl_atr_mult: float,
        tp_atr_mult: float,
    ) -> None:
        self._n_units += 1
        self.emit(
            Kind.LABEL_ACCEPTED,
            ReasonCode.LABEL_OK,
            bar_index=bar_index,
            timestamp=timestamp,
            crt_state=crt_state,
            direction=direction,
            action="label",
            extra={
                "y_rr": y_rr,
                "rr_gross": rr_gross,
                "exit_reason": exit_reason,
                "entry": entry,
                "atr_abs": atr_abs,
                "sl_atr_mult": sl_atr_mult,
                "tp_atr_mult": tp_atr_mult,
            },
        )

    def on_crt_exception(
        self,
        *,
        bar_index: int,
        timestamp: Any,
        error: BaseException,
    ) -> None:
        self._skip_counts[ReasonCode.CRT_ERROR.value] += 1
        self.emit(
            Kind.CRT_EXCEPTION,
            ReasonCode.CRT_ERROR,
            bar_index=bar_index,
            timestamp=timestamp,
            action="skip",
            extra={
                "error_type": type(error).__name__,
                "error_msg": str(error)[:300],
            },
            force=True,
        )

    def _maybe_heartbeat(
        self,
        bar_index: int,
        timestamp: Any,
        crt_state: Optional[str],
    ) -> None:
        if self.heartbeat_every <= 0:
            return
        if self._n_streamed % self.heartbeat_every != 0:
            return
        # Prefer stream ordinal for progress (candle.index is often 0/unset on loaders).
        stream_i = max(self._n_streamed - 1, 0)
        self.emit(
            Kind.PROGRESS,
            ReasonCode.HEARTBEAT,
            bar_index=stream_i if (bar_index is None or bar_index <= 0) else bar_index,
            timestamp=timestamp,
            crt_state=crt_state,
            action="progress",
            force=True,
            extra={
                "stream_ordinal": stream_i,
                "candle_index_field": bar_index,
            },
        )


def _default_action(kind: Kind) -> str:
    return {
        Kind.PHASE_START: "lifecycle",
        Kind.PHASE_END: "lifecycle",
        Kind.PROGRESS: "progress",
        Kind.WARMUP: "skip",
        Kind.CRT_TICK: "observe",
        Kind.STATE_TRANSITION: "observe",
        Kind.SWEEP_CANDIDATE: "evaluate_label",
        Kind.LABEL_ACCEPTED: "label",
        Kind.LABEL_SKIPPED: "skip",
        Kind.HOLDOUT: "skip",
        Kind.CRT_EXCEPTION: "skip",
        Kind.FEATURE_MISS: "skip",
        Kind.EVAL_SCORE: "score",
        Kind.NOTE: "note",
    }.get(kind, "observe")
