"""Pure cross-family join helpers (layer-trace / interpreter / opportunity).

DRAFT support for docs/implementation_plan/cross-family-run-join.md.

- Primary key: recorded run_id (exact string match, or via alias_map).
- Secondary key: (instrument, bar_ts) with per-family field aliases.
- F-101: never invent equality by clock arithmetic; alias_map must be recorded evidence
  (e.g. layer_trace.preexisting_run_ids values), not recomputed timestamps.

No I/O. No economic claims. Does not mutate family trace_id meanings.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("bar timestamp is None")
    s = str(value)
    # Accept ISO-8601; strip trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def normalize_run_id(run_id: str, alias_map: Optional[Mapping[str, str]] = None) -> str:
    """Map a recorded run_id through an alias table to a canonical key.

    alias_map values are the preferred canonical ids; keys are aliases.
    If run_id is a key, return alias_map[run_id]; if it is already a value, return it;
    otherwise return run_id unchanged.
    """
    rid = (run_id or "").strip()
    if not rid:
        return ""
    if not alias_map:
        return rid
    if rid in alias_map:
        return str(alias_map[rid]).strip()
    # also accept being already canonical
    canon = {str(v).strip() for v in alias_map.values()}
    if rid in canon:
        return rid
    return rid


def build_alias_map_from_preexisting(preexisting_run_ids: Mapping[str, Any]) -> dict[str, str]:
    """Invert layer_trace.preexisting_run_ids into alias -> preferred.

    Preferred = the layer_trace emitter run_id must be supplied by the caller separately;
    this helper only returns {alias_value: alias_value} identity pairs so tests can
    extend with preferred. For join tests we treat every recorded value as joinable
    to every other when grouped under one preferred key by the caller.
    """
    out: dict[str, str] = {}
    for _src, val in (preexisting_run_ids or {}).items():
        s = str(val).strip()
        if s:
            out[s] = s
    return out


def layer_trace_bar_key(row: Mapping[str, Any]) -> tuple[str, datetime]:
    return str(row.get("instrument") or "").strip(), _as_dt(row.get("bar_ts"))


def interpreter_bar_key(row: Mapping[str, Any]) -> tuple[str, datetime]:
    return str(row.get("instrument") or "").strip(), _as_dt(row.get("observation_time"))


def opportunity_bar_key(row: Mapping[str, Any]) -> tuple[str, datetime]:
    return str(row.get("instrument") or "").strip(), _as_dt(row.get("timestamp"))


def index_by_run_id(
    rows: Iterable[Mapping[str, Any]],
    *,
    run_id_field: str = "run_id",
    alias_map: Optional[Mapping[str, str]] = None,
) -> dict[str, list[Mapping[str, Any]]]:
    out: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        rid = normalize_run_id(str(row.get(run_id_field) or ""), alias_map)
        if not rid:
            continue
        out.setdefault(rid, []).append(row)
    return out


def index_by_bar(
    rows: Iterable[Mapping[str, Any]],
    *,
    key_fn,
) -> dict[tuple[str, datetime], list[Mapping[str, Any]]]:
    out: dict[tuple[str, datetime], list[Mapping[str, Any]]] = {}
    for row in rows:
        inst, ts = key_fn(row)
        if not inst:
            continue
        out.setdefault((inst, ts), []).append(row)
    return out


def join_on_run_id(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    left_run_field: str = "run_id",
    right_run_field: str = "run_id",
    alias_map: Optional[Mapping[str, str]] = None,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Primary join: exact recorded run_id (after alias normalization)."""
    right_idx = index_by_run_id(right, run_id_field=right_run_field, alias_map=alias_map)
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for lrow in left:
        rid = normalize_run_id(str(lrow.get(left_run_field) or ""), alias_map)
        if not rid:
            continue
        for rrow in right_idx.get(rid, []):
            pairs.append((lrow, rrow))
    return pairs


def join_on_instrument_bar(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    left_key_fn,
    right_key_fn,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Secondary join: (instrument, bar timestamp) with family-specific key functions."""
    right_idx = index_by_bar(right, key_fn=right_key_fn)
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for lrow in left:
        key = left_key_fn(lrow)
        if not key[0]:
            continue
        for rrow in right_idx.get(key, []):
            pairs.append((lrow, rrow))
    return pairs


def join_families(
    *,
    layer_trace: Sequence[Mapping[str, Any]],
    interpreters: Sequence[Mapping[str, Any]],
    opportunities: Sequence[Mapping[str, Any]],
    alias_map: Optional[Mapping[str, str]] = None,
) -> dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]]:
    """Return all three directed pair joins (primary run_id, with bar fallback unused here).

    Callers that need fallback should use join_on_instrument_bar when primary is empty
    for a given left row — see tests for the explicit fallback pattern.
    """
    return {
        "layer_trace_to_interpreter": join_on_run_id(
            layer_trace, interpreters, alias_map=alias_map
        ),
        "layer_trace_to_opportunity": join_on_run_id(
            layer_trace, opportunities, alias_map=alias_map
        ),
        "interpreter_to_opportunity": join_on_run_id(
            interpreters, opportunities, alias_map=alias_map
        ),
    }
