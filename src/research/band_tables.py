"""band_tables.py — strict loader + classifiers for configs/research/band_tables.json.

That file is DATA, not ontology (CLAUDE.md 6.6 — a partition of a stored float's axis is
not a market concept; SEM-037 / SEM-020 own the market meaning, this module owns the
arithmetic). Two table kinds exist and this module implements both, matching the shape
`test_band_tables.py` already pins:

  single_axis_interval  — a flat, ordered, half-open [lo,hi) partition of ONE value.
                           `classify()`. Used by BT-RR-STAGE1-V1 / BT-RR-ECON-V1.
  guarded_two_stage     — named guards over TWO inputs, evaluated in declared priority
                           order, THEN an interval partition of the surviving domain.
                           `classify_capture()`. Used by BT-CAPTURE-V1.

Config-First Doctrine (CLAUDE.md 6.5): every threshold a guard reads (epsilon,
unstable_threshold, violation_threshold) comes from the table's own `params`, never a
Python literal. A missing key is an error (`_require`), never a silent default.

Grounding note (CLAUDE.md 6.7 / the layered-outcome-ontology plan step 4): the RESULT of
`classify()` against BT-RR-ECON-V1 is exactly the claim CC-OPP-BAND-RESTATEMENT admits and
CC-OPP-BAND-NOT-ECONOMIC refuses any world-reading of. This module computes the number; it
grants no meaning beyond what those two claim classes already bound.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BAND_TABLES_PATH = _ROOT / "configs" / "research" / "band_tables.json"


class BandTableError(ValueError):
    """The band-table registry is malformed, or a lookup target does not exist.

    Fail closed — never fall back to a permissive default (the F-018 lesson).
    """


def load_band_table(table_id: str, *, path: Path = DEFAULT_BAND_TABLES_PATH) -> dict[str, Any]:
    """Load one table by id from the PRIMARY JSON registry. Strict: no default table.

    Raises BandTableError if the file is missing, malformed, or the id is unknown —
    a caller must name the table it wants, exactly as `load_ontology`/`load_catalog`
    never guess which section a caller meant.
    """
    if not path.exists():
        raise BandTableError(f"band-table registry missing: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tables = data.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise BandTableError(f"{path}: 'tables' must be a non-empty object")
    if table_id not in tables:
        raise BandTableError(
            f"unknown band table {table_id!r}; known: {sorted(tables)}")
    table = tables[table_id]
    _validate_table(table_id, table)
    return table


def _require(table: dict, key: str, table_id: str) -> Any:
    if key not in table:
        raise BandTableError(f"{table_id}: missing required key {key!r}")
    return table[key]


def _validate_table(table_id: str, table: dict) -> None:
    kind = _require(table, "table_kind", table_id)
    for key in ("axis", "unit", "cost_basis", "first_match_wins", "exhaustive",
                "mutually_exclusive", "bands"):
        _require(table, key, table_id)
    if not table["bands"]:
        raise BandTableError(f"{table_id}: bands must be non-empty")
    if kind == "guarded_two_stage":
        guards = _require(table, "guards", table_id)
        if not guards:
            raise BandTableError(f"{table_id}: guarded_two_stage table must declare guards")
        for g in guards:
            for key in ("name", "priority", "condition", "params"):
                if key not in g:
                    raise BandTableError(f"{table_id}: guard missing key {key!r}: {g}")
        priorities = [g["priority"] for g in guards]
        if priorities != sorted(priorities) or len(set(priorities)) != len(priorities):
            raise BandTableError(f"{table_id}: guard priorities must be unique and ascending")
    elif kind != "single_axis_interval":
        raise BandTableError(f"{table_id}: unknown table_kind {kind!r}")


# ---------------------------------------------------------------------------------------
# single_axis_interval
# ---------------------------------------------------------------------------------------


def classify(value: float, table: dict[str, Any]) -> str:
    """First-match-wins band name for `value` against a single_axis_interval table.

    Half-open [lo,hi) per band; lo/hi of None mean unbounded. NaN/Inf route to the
    table's declared `on_nan_or_inf` band name rather than raising — a band table
    must have somewhere to put an invalid value, per its own `domain` contract.
    """
    if table.get("table_kind") not in (None, "single_axis_interval"):
        raise BandTableError(
            f"classify() requires a single_axis_interval table, got {table.get('table_kind')!r} "
            "(use classify_capture() for guarded_two_stage)")
    if not math.isfinite(value):
        on_invalid = table.get("on_nan_or_inf")
        if not on_invalid:
            raise BandTableError("value is non-finite and table declares no on_nan_or_inf band")
        return on_invalid["band_name"]

    for band in table["bands"]:
        lo, hi = band["lo"], band["hi"]
        lo_ok = True if lo is None else (value >= lo if band["lo_inclusive"] else value > lo)
        hi_ok = True if hi is None else (value <= hi if band["hi_inclusive"] else value < hi)
        if lo_ok and hi_ok:
            return band["name"]
    raise BandTableError(
        f"value {value!r} matched no band — the table is not exhaustive (this is a data defect, "
        "not a caller error; the registry's own floor should have caught it)")


# ---------------------------------------------------------------------------------------
# guarded_two_stage (BT-CAPTURE-V1)
# ---------------------------------------------------------------------------------------


def classify_capture(mfe_r: float, rr_achieved: float, table: dict[str, Any]) -> tuple[str, float | None]:
    """(state_or_band_name, capture_value_or_None) for a guarded_two_stage table.

    Stage 1: the declared guards, in ascending `priority` order — the first whose
    condition holds wins and stage 2 is skipped, matching BT-CAPTURE-V1's own
    guard-order-was-an-evidence-based-decision note (UNDEFINED > UNSTABLE > NEGATIVE >
    VIOLATION). Every threshold a guard reads comes from that guard's own `params`.
    Stage 2: once every guard has passed, `capture = rr_achieved / mfe_r` is banded via
    `classify()` against the same table's `bands` list (an ordinary single-axis
    partition once the guards have removed every degenerate case).
    """
    if table.get("table_kind") != "guarded_two_stage":
        raise BandTableError(
            f"classify_capture() requires a guarded_two_stage table, got {table.get('table_kind')!r}")

    guards = sorted(table["guards"], key=lambda g: g["priority"])
    for guard in guards:
        name = guard["name"]
        params = guard["params"]
        if name == "CAPTURE_UNDEFINED":
            if mfe_r <= params["epsilon"]:
                return name, None
        elif name == "CAPTURE_UNSTABLE":
            eps = _guard_params(guards, "CAPTURE_UNDEFINED")["epsilon"]
            if eps < mfe_r < params["unstable_threshold"]:
                return name, None
        elif name == "CAPTURE_NEGATIVE":
            threshold = params.get("unstable_threshold",
                                    _guard_params(guards, "CAPTURE_UNSTABLE")["unstable_threshold"])
            if mfe_r >= threshold and rr_achieved < 0:
                return name, None
        elif name == "CAPTURE_VIOLATION":
            capture = rr_achieved / mfe_r
            if capture > params["violation_threshold"]:
                return name, capture
        else:
            raise BandTableError(f"unrecognised guard {name!r} — extend classify_capture()")

    capture = rr_achieved / mfe_r
    band_name = classify(capture, {**table, "table_kind": "single_axis_interval"})
    return band_name, capture


def _guard_params(guards: list[dict], name: str) -> dict:
    for g in guards:
        if g["name"] == name:
            return g["params"]
    raise BandTableError(f"guard {name!r} not declared — required by another guard's threshold reuse")
