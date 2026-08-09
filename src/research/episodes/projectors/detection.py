"""DetectionProjector — opportunities.jsonl → DETECTION_STREAM episodes.

F-022 DISCIPLINE (the reason this projector exists at all): `opportunities.jsonl`
is a DETECTION STREAM, not a trade ledger — its `outcome`/`rr_achieved`/`mfe`/`mae`
are only ~36.8% self-consistent. This projector therefore takes ONLY the entry
GEOMETRY from the stream (timestamp, direction, entry, sl, tp) and routes every
stream label into `metadata.diagnostics`, where nothing downstream may read it as
truth. Canonical labels come from `PolicyEvaluator` re-walking the timeline.

Geometry extraction deliberately mirrors `research.clean_labels.builder._geometry`
so that the two builders select the IDENTICAL unit population — that identity is
what makes the P2 parity floor a real test rather than a comparison of two
differently-filtered samples.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from research.episodes.builder import _norm_ts, build_episode
from research.episodes.protocol import MAX_FORWARD
from research.episodes.schema import EntrySnapshot, OpportunityEpisode

POPULATION = "DETECTION_STREAM"

# Stream fields that may NEVER become canonical (protocol.FORBIDDEN_AS_CANONICAL).
_STREAM_DIAGNOSTIC_KEYS = ("outcome", "rr_achieved", "rr", "mfe", "mae", "exit_reason",
                           "duration", "duration_candles")


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _geometry(rec: dict) -> tuple[float, float, float | None, str] | None:
    """(entry, sl, tp, direction) or None. Mirrors clean_labels.builder._geometry."""
    if not all(k in rec for k in ("entry", "sl", "direction", "timestamp")):
        return None
    if not _finite(rec["entry"]) or not _finite(rec["sl"]):
        return None
    entry = float(rec["entry"])
    sl = float(rec["sl"])
    if abs(entry - sl) <= 0:
        return None
    direction = str(rec["direction"]).lower()
    if direction not in ("long", "short"):
        return None
    tp_raw = rec.get("tp", rec.get("tp1"))
    tp = float(tp_raw) if _finite(tp_raw) else None
    return entry, sl, tp, direction


def _diagnostics(rec: dict) -> dict[str, Any]:
    """Quarantine the stream's own labels. Diagnostic only — never primary (F-022)."""
    diag = {k: rec[k] for k in _STREAM_DIAGNOSTIC_KEYS if k in rec}
    diag["_warning"] = (
        "F-022: detection-stream labels are ~36.8% self-consistent. "
        "Never use as primary truth; derive labels via PolicyEvaluator."
    )
    return diag


def project_record(
    rec: dict,
    candles: Sequence,
    ts_to_idx: dict[str, int],
    *,
    instrument: str,
    max_forward: int = MAX_FORWARD,
    protocol_hash: str | None = None,
    cache_derived: bool = True,
    **build_kwargs: Any,
) -> tuple[OpportunityEpisode | None, str | None]:
    """Project one stream record. Returns (episode, skip_reason).

    Skip reasons use the same vocabulary as clean_labels' builder so the two
    funnels can be compared line for line.
    """
    geom = _geometry(rec)
    if geom is None:
        return None, "bad_geometry"
    entry_price, sl, tp, direction = geom

    ts = _norm_ts(rec["timestamp"])
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None, "no_candle_ts"
    if idx + 1 >= len(candles):
        return None, "no_future_bars"

    feats = rec.get("features")
    entry = EntrySnapshot(
        bar_index=idx,
        timestamp=ts,
        direction=direction,
        entry_price=entry_price,
        sl_price=sl,
        tp_price=tp,
        atr_entry=float(rec["atr"]) if _finite(rec.get("atr")) else None,
        engine_scores=rec.get("scores") if isinstance(rec.get("scores"), dict) else None,
        feature_vector=None,   # joined by bar_index on demand — not stored (substrate §7)
        generator_config=None,
    )

    metadata: dict[str, Any] = {
        "diagnostics": _diagnostics(rec),
        "has_stream_features": isinstance(feats, dict) and bool(feats),
    }

    try:
        ep = build_episode(
            instrument=instrument,
            population=POPULATION,
            entry=entry,
            candles=candles,
            max_forward=max_forward,
            metadata=metadata,
            cache_derived=cache_derived,
            protocol_hash=protocol_hash,
            **build_kwargs,
        )
    except ValueError as exc:
        return None, f"build_error:{type(exc).__name__}"
    return ep, None


def project_stream(
    records: Iterable[dict],
    candles: Sequence,
    ts_to_idx: dict[str, int],
    *,
    instrument: str,
    max_forward: int = MAX_FORWARD,
    max_units: int | None = None,
    protocol_hash: str | None = None,
    cache_derived: bool = True,
    **build_kwargs: Any,
) -> tuple[list[OpportunityEpisode], dict[str, int]]:
    """Project a whole stream. Returns (episodes, skip counts)."""
    episodes: list[OpportunityEpisode] = []
    skips: dict[str, int] = {}
    for rec in records:
        if max_units is not None and len(episodes) >= max_units:
            break
        if "entry" not in rec or "timestamp" not in rec:
            skips["not_opportunity"] = skips.get("not_opportunity", 0) + 1
            continue
        if rec.get("instrument") and str(rec["instrument"]) != instrument:
            skips["wrong_instrument"] = skips.get("wrong_instrument", 0) + 1
            continue
        ep, reason = project_record(
            rec, candles, ts_to_idx, instrument=instrument, max_forward=max_forward,
            protocol_hash=protocol_hash, cache_derived=cache_derived, **build_kwargs,
        )
        if reason is not None:
            key = reason.split(":")[0]
            skips[key] = skips.get(key, 0) + 1
            continue
        assert ep is not None
        episodes.append(ep)
    return episodes, skips
