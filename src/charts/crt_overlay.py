"""crt_overlay.py — INFRA-CPC-V1 A0 Layer V1: resolve a per-bar CRTState track.

AUTHORITY DISCIPLINE (INFRA-CPC-V1 §6, F-057):
    The state track MUST come from the spine run under the **ACTIVE_VERSION** config,
    loaded through the production registry path. A state stream produced under a
    different config version is NOT interchangeable and is never silently substituted;
    the caller gets `UNAVAILABLE` instead, and the legend says so.

WHY WE RUN `BacktestRunner` RATHER THAN DRIVING `CRTEngine` DIRECTLY:
    `ACTIVE_VERSION` today carries `parent_crt.enabled: true` (F-075), so the engine's
    bias gate needs a `ParentCRTFeed` threaded into `process_candle`. `BacktestRunner`
    already owns that wiring, plus `htf_candle_id` assignment. Hand-driving the engine
    would fork it. This mirrors `research.adapters.spine_signal_source.ProductionSpineSource`.

ALIGNMENT IS BY TIMESTAMP (three corrections, all measured — see `_bar_positions`):
    Events are joined to bars on their TIMESTAMP, never on `candle_index`. Getting here
    took three wrong answers, each of which rendered a plausible-looking chart:

    1. Assumed `candle_index` was 1-based over the corpus (shift −1). Scored 0 matches;
       the real shift is **+62** (the runner skips indicator warmup before feeding).
    2. Solved the shift from the data and demanded unanimity. Correct for
       STATE_TRANSITION (2,382 all at +62) but FALSE for the stream as a whole: 121 of
       2,887 RESETs sit at shift 0, every one a `"Session gap detected"` reset. The two
       event families do not share an index basis, so unanimity rejected everything.
    3. Timestamps are unique per bar and unambiguous. They are now the join key, and the
       shift survives only as a reported diagnostic (`index_shift_diagnostic`).

    The fail-closed guard earned its keep: at each wrong step it refused to colour bars
    rather than colouring them wrongly. (Same discipline as
    `tools/tv_forensic/capture_tv.py::calibrate_clock`.)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from charts.chart_series import CRT_UNAVAILABLE

log = logging.getLogger("charts.crt_overlay")

# Engine start state (EngineState.current_state default) — the track before the first
# transition is RANGE by construction, not by guess.
INITIAL_STATE = "RANGE"

CACHE_ROOT = Path("results/charts/_crt_cache")


@dataclass(frozen=True)
class CRTTrack:
    """Per-base-bar CRT state plus the provenance needed to trust (or distrust) it."""
    states: list[str]
    source: str                 # "RESOLVED:<version>" | "UNAVAILABLE:<reason>"
    version: Optional[str]
    transitions: int
    offset: Optional[int]

    @property
    def resolved(self) -> bool:
        return self.source.startswith("RESOLVED")


def unavailable(reason: str, n_bars: int) -> CRTTrack:
    """A track that honestly says nothing. Never fabricates a state."""
    return CRTTrack(
        states=[CRT_UNAVAILABLE] * n_bars,
        source=f"UNAVAILABLE:{reason}",
        version=None,
        transitions=0,
        offset=None,
    )


# Event kinds that move the machine's CURRENT state. Both are required.
#
# CORRECTED 2026-08-22 — the first implementation read STATE_TRANSITION only, and was
# WRONG. Measured on the XAUUSD run: `STATE_TRANSITION` into RANGE occurs **0** times;
# the machine returns to RANGE exclusively via `RESET` (1,798 resets carry a non-RANGE
# `state_from`: SWEEP 1393, DISPLACEMENT 257, EXPANSION 124, RETEST 20, RESOLUTION 3,
# EXECUTION 1). Reading transitions alone therefore forward-filled SWEEP/EXPANSION
# forever and rendered a chart on which the engine is essentially NEVER in RANGE —
# a pure artifact of the parser, and one that looked plausible.
_STATE_EVENTS = ("STATE_TRANSITION", "RESET")


def _parse_state_events(events_path: Path) -> list[tuple[int, str, datetime]]:
    """Extract (candle_index, state_to, timestamp) for every state-moving event.

    Preserves engine emission order (file position) so that when a RESET and a
    STATE_TRANSITION land on the SAME bar, the engine decides which state the bar ends
    in — rather than an arbitrary sort. `candle_index` is carried for DIAGNOSTICS ONLY;
    the join key is the timestamp (see `_bar_positions`).
    """
    rows: list[tuple[int, str, datetime]] = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not any(k in line for k in _STATE_EVENTS):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") not in _STATE_EVENTS:
                continue
            ci, st, ts = rec.get("candle_index"), rec.get("state_to"), rec.get("timestamp")
            if ci is None or not st or not ts:
                continue
            rows.append((int(ci), str(st), datetime.fromisoformat(str(ts))))
    return rows


def _bar_positions(
    events: Sequence[tuple[int, str, datetime]],
    base_ts: Sequence[datetime],
) -> list[tuple[int, str]]:
    """Map each event onto its base-bar position BY TIMESTAMP, preserving order.

    WHY TIMESTAMP AND NOT `candle_index` (measured 2026-08-22, XAUUSD /
    `v2_htfcrt_2026_08`): the two event families do not share an index basis. All 2,382
    STATE_TRANSITIONs sit at shift +62, and so do 2,766 RESETs — but **121 RESETs sit at
    shift 0**, and every one of them is a `"Session gap detected"` reset (99 at ~2,955
    min, i.e. weekends). So a single-offset model of this stream is FALSE, and demanding
    unanimity on it (as this module first did) rejected the whole track and rendered
    everything UNAVAILABLE.

    Timestamps carry no such ambiguity: they are unique per bar in the corpus and are
    what the event actually happened on. Fails closed if any event timestamp is absent
    from the base series — that is a wrong-corpus error, not an alignment detail.
    """
    if not events:
        raise ValueError("no state events to align")
    pos = {ts: i for i, ts in enumerate(base_ts)}
    out: list[tuple[int, str]] = []
    missing = 0
    for _ci, st, ts in events:
        i = pos.get(ts)
        if i is None:
            missing += 1
            continue
        out.append((i, st))
    if missing:
        raise ValueError(
            f"alignment failed closed: {missing}/{len(events)} event timestamps are "
            "absent from the base series (wrong corpus)."
        )
    return out


def index_shift_diagnostic(
    events: Sequence[tuple[int, str, datetime]],
    base_ts: Sequence[datetime],
) -> dict:
    """Report how `candle_index` relates to bar position. DIAGNOSTIC ONLY - never gates.

    Kept because the disagreement it surfaces is a real property of the event stream
    worth recording next to a chart (121 session-gap RESETs use a different index basis
    than everything else), but the render no longer depends on it.
    """
    pos = {ts: i for i, ts in enumerate(base_ts)}
    shifts: dict[int, int] = {}
    for ci, _st, ts in events:
        i = pos.get(ts)
        if i is not None:
            shifts[i - ci] = shifts.get(i - ci, 0) + 1
    if not shifts:
        return {"modal_shift": None, "agreement": None, "distinct_shifts": 0}
    modal = max(shifts, key=lambda k: shifts[k])
    total = sum(shifts.values())
    return {
        "modal_shift": modal,
        "agreement": round(shifts[modal] / total, 4),
        "distinct_shifts": len(shifts),
    }


def _forward_fill(placed: Sequence[tuple[int, str]], n_bars: int) -> list[str]:
    """Hold each state from its bar until the next event. Causal.

    `placed` is `(bar_position, state)` in engine emission order (from `_bar_positions`).
    Do NOT re-sort: same-bar RESET vs STATE_TRANSITION ordering is carried by emission
    order, and sorting would discard it. Positions are non-decreasing already because the
    engine emits chronologically.
    """
    states = [INITIAL_STATE] * n_bars
    cur = INITIAL_STATE
    ptr = 0
    for i in range(n_bars):
        while ptr < len(placed) and placed[ptr][0] <= i:
            cur = placed[ptr][1]
            ptr += 1
        states[i] = cur
    return states


def _find_events_file(out_dir: Path, instrument: str) -> Optional[Path]:
    """Newest `<INSTRUMENT>_events.jsonl` under a run-scoped subdir."""
    hits = sorted(out_dir.rglob(f"{instrument}_events.jsonl"),
                  key=lambda p: p.stat().st_mtime)
    return hits[-1] if hits else None


def run_spine_for_states(
    instrument: str,
    csv_path: str | Path,
    version: Optional[str] = None,
    out_root: str | Path = CACHE_ROOT,
) -> Path:
    """Run the real spine under `version` (default ACTIVE_VERSION); return events path.

    Reuses `ProductionSpineSource`'s established pattern: temporarily rebind the
    module-global `PROD_VERSION` in BOTH modules that read it, run, restore in `finally`.
    The governance pointer (`configs/production/ACTIVE_VERSION`) is never written.
    """
    import config_layer.production_config as _pc
    import runtime.backtest_v2 as _bt

    ver = version or _pc.get_active_version()
    out_dir = Path(out_root) / f"{instrument}__{ver}"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = _find_events_file(out_dir, instrument)
    if existing is not None:
        log.info("CRT overlay: reusing cached spine events %s", existing)
        return existing

    _pc_prev, _bt_prev = _pc.PROD_VERSION, _bt.PROD_VERSION
    _crt = logging.getLogger("CRT")
    _crt_prev = _crt.level
    _crt.setLevel(logging.ERROR)     # spine is deterministic; silence its per-bar noise
    try:
        _pc.PROD_VERSION = ver
        _bt.PROD_VERSION = ver
        crt_cfg = _pc.load_prod_config_from_registry(ver, instrument)
        cfg = _bt.BacktestConfig.from_prod_config(
            instrument=instrument,
            pip_size=_bt.MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001),
            crt_config=crt_cfg,
        )
        loader = _bt.CandleLoader(str(csv_path), instrument)
        runner = _bt.BacktestRunner(cfg, csv_path=str(csv_path),
                                    overrides={"_chart_overlay": "1"})
        runner.run(loader.stream(), loader.count(), str(out_dir))
    finally:
        _pc.PROD_VERSION = _pc_prev
        _bt.PROD_VERSION = _bt_prev
        _crt.setLevel(_crt_prev)

    events = _find_events_file(out_dir, instrument)
    if events is None:
        raise FileNotFoundError(
            f"spine run produced no {instrument}_events.jsonl under {out_dir}")
    return events


def resolve_states(
    instrument: str,
    csv_path: str | Path,
    base_ts: Sequence[datetime],
    version: Optional[str] = None,
) -> CRTTrack:
    """Resolve the per-base-bar CRT track, degrading honestly on any failure."""
    try:
        import config_layer.production_config as _pc
        ver = version or _pc.get_active_version()
    except Exception as exc:                                     # noqa: BLE001
        return unavailable(f"ACTIVE_VERSION unresolved ({exc})", len(base_ts))

    try:
        events = run_spine_for_states(instrument, csv_path, ver)
    except Exception as exc:                                     # noqa: BLE001
        log.warning("CRT overlay: spine run failed (%s)", exc)
        return unavailable(f"spine run failed ({type(exc).__name__}: {exc})", len(base_ts))

    try:
        evs = _parse_state_events(events)
        placed = _bar_positions(evs, base_ts)
        states = _forward_fill(placed, len(base_ts))
        diag = index_shift_diagnostic(evs, base_ts)
    except Exception as exc:                                     # noqa: BLE001
        log.warning("CRT overlay: alignment failed (%s)", exc)
        return unavailable(f"alignment failed ({exc})", len(base_ts))

    return CRTTrack(
        states=states,
        source=f"RESOLVED:{ver}",
        version=ver,
        transitions=len(evs),
        offset=diag.get("modal_shift"),
    )
