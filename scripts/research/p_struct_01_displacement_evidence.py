#!/usr/bin/env python3
"""P-STRUCT-01 — CRT DISPLACEMENT evidence table (not a fingerprint).

Population: STATE_TRANSITION state_to=DISPLACEMENT only.
Grounded: direction (companion SWEEP event), after_sweep (VALID_TRANSITIONS).
Derivable: age_since_sweep_bars / continuation_age_bars, classed UNKNOWN_N.
Observable: FM-062/063 numeric values only if an official join file is supplied.
Forbidden: after_range, high_volume, against_ema, deep_retracement, parent-CRT/SMC.

UNKNOWN_N is data. The extractor never invents a threshold or a class.
The column set grows only by an authoritative join of an already-declared
quantity, or by an explicit ontology-contract change. Observed counts
are not an enrichment path.

    venv\\Scripts\\python.exe scripts/research/p_struct_01_displacement_evidence.py \\
        --events <events.jsonl> --out-dir results/p_struct_01
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from config_layer.state_identity import CRTState, VALID_TRANSITIONS  # noqa: E402

DEFAULT_EVENTS = (
    ROOT
    / "results"
    / "htf_objective_shadow"
    / "two_year"
    / "off"
    / "run_20260816_074305_XAUUSD"
    / "XAUUSD_events.jsonl"
)
DEFAULT_CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"

NODE_ID = "P-STRUCT-01"
ENGINE_STATE = CRTState.DISPLACEMENT.name
UNKNOWN_N = "UNKNOWN_N"
ABSENT = "ABSENT"

# Legal predecessors of DISPLACEMENT, derived — not a local edge list.
LEGAL_DISP_PREDECESSORS: frozenset[str] = frozenset(
    src.name
    for src, dests in VALID_TRANSITIONS.items()
    if CRTState.DISPLACEMENT in dests
)

# Grows only by official join or an explicit contract (CH-PSTRUCT-04 added
# volume_participation as identity(FM-063)). Histograms do not extend this.
ROW_KEYS: tuple[str, ...] = (
    "timestamp",
    "engine_state",
    "direction",
    "direction_source",
    "predecessor_state",
    "after_sweep",
    "age_since_sweep_bars",
    "age_since_sweep_class",
    "continuation_successor",
    "continuation_age_bars",
    "continuation_age_class",
    "volume_ratio",
    "volume_spike",
    "volume_join_status",
    "volume_participation",
    "crt_wire",
    "crt_wire_gate",
)

# SEM-013: identity of FM-063 official states. Not high_volume. Not a CRTState.
FM063_PARTICIPATION: dict[int, str] = {0: "NoSpike", 1: "VolumeSpike"}
CRT_WIRE_STATE = "DISPLACEMENT"
CRT_WIRE_MODE = "ANNOTATION_ONLY"
CRT_WIRE_GATE = "UNUSED"

FORBIDDEN_OUTPUT_KEYS: frozenset[str] = frozenset(
    {
        "after_range",
        "high_volume",
        "against_ema",
        "with_ema",
        "deep_retracement",
        "fingerprint",
        "immediate",
        "delayed",
        "parent_state",
        "htf_state",
        "order_block",
        "fvg",
    }
)

EXPLICITLY_EXCLUDED: tuple[str, ...] = (
    "after_range",
    "CRT high-volume classification",
    "against_ema",
    "deep_retracement",
    "parent-CRT / SMC dimensions",
)


class IllegalPredecessor(SystemExit):
    """A RANGE→DISPLACEMENT (or any non-legal) hop is not an after_range class."""


def _norm_ts(ts: object) -> str:
    if ts is None:
        raise ValueError("timestamp is required (join is never by candle_index)")
    s = str(ts).replace("T", " ").replace("Z", "")
    if "." in s:
        s = s.split(".", 1)[0]
    return s[:19]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def load_volume_join(path: Path | None) -> dict[str, dict[str, Any]] | None:
    """Official FM-062/063 values only. Never compute volume / SMA here."""
    if path is None:
        return None
    by_ts: dict[str, dict[str, Any]] = {}
    for rec in load_jsonl(path):
        by_ts[_norm_ts(rec["timestamp"])] = rec
    return by_ts


def official_volume_by_ts(csv_path: Path) -> dict[str, dict[str, Any]]:
    """FM-062/063 from FeaturePipeline.run() only. No local volume formula."""
    import pandas as pd
    from features.feature_pipeline import FeaturePipeline

    if not csv_path.is_file():
        raise SystemExit(f"official-pipeline CSV missing: {csv_path}")
    df = pd.read_csv(csv_path)
    enriched, _vectors = FeaturePipeline(df).run()
    missing = [c for c in ("timestamp", "volume_ratio", "volume_spike") if c not in enriched.columns]
    if missing:
        raise SystemExit(
            f"FeaturePipeline did not emit {missing} — refuse local substitute"
        )
    out: dict[str, dict[str, Any]] = {}
    for rec in enriched[["timestamp", "volume_ratio", "volume_spike"]].to_dict("records"):
        ratio = rec["volume_ratio"]
        spike = rec["volume_spike"]
        out[_norm_ts(rec["timestamp"])] = {
            "timestamp": _norm_ts(rec["timestamp"]),
            "volume_ratio": None if ratio != ratio else float(ratio),
            "volume_spike": None if spike != spike else int(spike),
        }
    return out


def write_volume_join_jsonl(by_ts: dict[str, dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for ts in sorted(by_ts):
            fh.write(json.dumps(by_ts[ts], separators=(",", ":")) + "\n")
    return path


def _assert_row_legal(row: dict[str, Any]) -> None:
    extra = set(row) - set(ROW_KEYS)
    if extra:
        raise SystemExit(f"undeclared evidence column(s): {sorted(extra)}")
    hit = set(row) & FORBIDDEN_OUTPUT_KEYS
    if hit:
        raise SystemExit(f"forbidden evidence key(s): {sorted(hit)}")
    if row.get("age_since_sweep_class") != UNKNOWN_N:
        raise SystemExit("age_since_sweep_class must be UNKNOWN_N")
    if row.get("crt_wire_gate") != CRT_WIRE_GATE:
        raise SystemExit("crt_wire_gate must be UNUSED")
    if row.get("continuation_successor") == "EXPANSION":
        if row.get("continuation_age_class") != UNKNOWN_N:
            raise SystemExit("continuation to EXPANSION must stay UNKNOWN_N")
    elif row.get("continuation_age_class") != ABSENT:
        raise SystemExit("non-EXPANSION continuation class must be ABSENT")
    if "high_volume" in row:
        raise SystemExit("high_volume is not a legal column")


def _episode_successor(
    events: list[dict[str, Any]],
    disp_event_index: int,
    disp_idx: int,
) -> tuple[str, int | None]:
    """Leave-event of THIS displacement only.

    A later episode's DISPLACEMENT→EXPANSION must not be stolen. RESET
    from DISPLACEMENT is the common leave (dest RANGE); it is not EXPANSION.
    """
    for later in events[disp_event_index + 1 :]:
        kind = later.get("event")
        later_from = later.get("state_from")
        later_to = later.get("state_to")
        later_idx = later.get("candle_index")
        if kind == "STATE_TRANSITION" and later_to == ENGINE_STATE:
            return "NONE", None
        if kind == "STATE_TRANSITION" and later_from == ENGINE_STATE:
            if later_to == "EXPANSION" and later_idx is not None:
                return "EXPANSION", int(later_idx) - disp_idx
            return later_to or "NONE", None
        if kind == "RESET" and later_from == ENGINE_STATE:
            return "RANGE", None
    return "NONE", None


def extract_rows(
    events: list[dict[str, Any]],
    volume_by_ts: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    transitions = [e for e in events if e.get("event") == "STATE_TRANSITION"]
    sweep_dir_by_ts: dict[str, str] = {}
    for ev in events:
        if ev.get("event") != "SWEEP":
            continue
        direction = ev.get("direction")
        if direction in ("LONG", "SHORT"):
            sweep_dir_by_ts[_norm_ts(ev["timestamp"])] = direction

    sweep_entries = [e for e in transitions if e.get("state_to") == "SWEEP"]
    skip_sweep_to_expansion = sum(
        1
        for e in transitions
        if e.get("state_from") == "SWEEP" and e.get("state_to") == "EXPANSION"
    )

    rows: list[dict[str, Any]] = []
    for ev_i, ev in enumerate(events):
        if ev.get("event") != "STATE_TRANSITION" or ev.get("state_to") != ENGINE_STATE:
            continue
        predecessor = ev.get("state_from")
        if predecessor not in LEGAL_DISP_PREDECESSORS:
            raise IllegalPredecessor(
                f"ILLEGAL_PREDECESSOR: {predecessor} -> {ENGINE_STATE} "
                f"at {ev.get('timestamp')} (not after_range; not a class)"
            )
        disp_idx = ev.get("candle_index")
        if disp_idx is None:
            raise SystemExit(f"DISPLACEMENT missing candle_index at {ev.get('timestamp')}")

        pred_sweep = None
        for entry in sweep_entries:
            idx = entry.get("candle_index")
            if idx is None:
                continue
            if idx <= disp_idx:
                pred_sweep = entry
            else:
                break
        if pred_sweep is None:
            raise SystemExit(
                f"missing predecessor SWEEP entry for DISPLACEMENT at {ev.get('timestamp')}"
            )

        age = int(disp_idx) - int(pred_sweep["candle_index"])
        sweep_ts = _norm_ts(pred_sweep["timestamp"])
        direction = sweep_dir_by_ts.get(sweep_ts)
        direction_source = "SWEEP_EVENT" if direction is not None else "UNJOINED"

        successor_to, continuation_age = _episode_successor(events, ev_i, int(disp_idx))

        ts = _norm_ts(ev["timestamp"])
        volume_ratio = None
        volume_spike = None
        if volume_by_ts is None:
            volume_join_status = "NOT_JOINED"
        elif ts not in volume_by_ts:
            volume_join_status = "MISSING_AT_TIMESTAMP"
        else:
            vol = volume_by_ts[ts]
            volume_ratio = vol.get("volume_ratio")
            volume_spike = vol.get("volume_spike")
            volume_join_status = "JOINED"

        if volume_join_status == "JOINED" and volume_spike is not None:
            try:
                spike_i = int(volume_spike)
            except (TypeError, ValueError):
                raise SystemExit(f"FM-063 volume_spike not int-like at {ts}: {volume_spike!r}")
            if spike_i not in FM063_PARTICIPATION:
                raise SystemExit(
                    f"FM-063 volume_spike={spike_i} is not an official 0/1 state at {ts}"
                )
            volume_participation = FM063_PARTICIPATION[spike_i]
        else:
            volume_participation = "UNJOINED"

        if volume_participation in FM063_PARTICIPATION.values():
            crt_wire = f"{CRT_WIRE_STATE}:{volume_participation}:{CRT_WIRE_MODE}"
        else:
            crt_wire = "UNJOINED"

        row = {
            "timestamp": ts,
            "engine_state": ENGINE_STATE,
            "direction": direction,
            "direction_source": direction_source,
            "predecessor_state": predecessor,
            "after_sweep": predecessor == "SWEEP",
            "age_since_sweep_bars": age,
            "age_since_sweep_class": UNKNOWN_N,
            "continuation_successor": successor_to,
            "continuation_age_bars": continuation_age,
            "continuation_age_class": UNKNOWN_N if successor_to == "EXPANSION" else ABSENT,
            "volume_ratio": volume_ratio,
            "volume_spike": volume_spike,
            "volume_join_status": volume_join_status,
            "volume_participation": volume_participation,
            "crt_wire": crt_wire,
            "crt_wire_gate": CRT_WIRE_GATE,
        }
        _assert_row_legal(row)
        rows.append(row)

    rollup = _rollup(rows, skip_sweep_to_expansion=skip_sweep_to_expansion)
    return rows, rollup


def _coincidence(rows: list[dict[str, Any]], *keys: str) -> dict[str, int]:
    """Counts of already-declared columns. Cells are not classes."""
    counts: Counter[tuple[str, ...]] = Counter(
        tuple(str(r[k]) for k in keys) for r in rows
    )
    return {"|".join(k): int(n) for k, n in sorted(counts.items())}


def _rollup(rows: list[dict[str, Any]], *, skip_sweep_to_expansion: int) -> dict[str, Any]:
    dirs = Counter(str(r["direction"]) for r in rows)
    preds = Counter(str(r["predecessor_state"]) for r in rows)
    succ = Counter(str(r["continuation_successor"]) for r in rows)
    ages = Counter(int(r["age_since_sweep_bars"]) for r in rows)
    join = Counter(str(r["volume_join_status"]) for r in rows)
    age_class = Counter(str(r["age_since_sweep_class"]) for r in rows)
    cont_class = Counter(str(r["continuation_age_class"]) for r in rows)
    joined_ratios = [
        float(r["volume_ratio"])
        for r in rows
        if r["volume_join_status"] == "JOINED" and r["volume_ratio"] is not None
    ]
    spike_vals = Counter(
        str(int(r["volume_spike"]))
        for r in rows
        if r["volume_join_status"] == "JOINED" and r["volume_spike"] is not None
    )
    return {
        "node": NODE_ID,
        "population": "CRT DISPLACEMENT STATE_TRANSITION",
        "n": len(rows),
        "direction": dict(dirs),
        "predecessor_state": dict(preds),
        "after_sweep_true": sum(1 for r in rows if r["after_sweep"] is True),
        "age_since_sweep_bars": {
            "min": min(ages) if ages else None,
            "max": max(ages) if ages else None,
            "counts": {str(k): ages[k] for k in sorted(ages)},
        },
        "age_since_sweep_class": dict(age_class),
        "continuation_successor": dict(succ),
        "continuation_age_class": dict(cont_class),
        "volume_join_status": dict(join),
        "volume_ratio_numeric": {
            "n": len(joined_ratios),
            "min": min(joined_ratios) if joined_ratios else None,
            "max": max(joined_ratios) if joined_ratios else None,
        },
        "volume_spike_raw_counts": dict(spike_vals),
        "volume_participation": dict(
            Counter(str(r["volume_participation"]) for r in rows)
        ),
        "crt_wire": dict(Counter(str(r["crt_wire"]) for r in rows)),
        "crt_wire_gate": dict(Counter(str(r["crt_wire_gate"]) for r in rows)),
        "sweep_to_expansion_skips_excluded": skip_sweep_to_expansion,
        "explicitly_excluded": list(EXPLICITLY_EXCLUDED),
        "legal_disp_predecessors": sorted(LEGAL_DISP_PREDECESSORS),
        "coincidence_declared_columns": {
            "authority": "CH-PSTRUCT-05",
            "economic_claims_allowed": False,
            "classes_minted": False,
            "direction_x_volume_participation": _coincidence(
                rows, "direction", "volume_participation"
            ),
            "volume_participation_x_continuation_successor": _coincidence(
                rows, "volume_participation", "continuation_successor"
            ),
            "direction_x_continuation_successor": _coincidence(
                rows, "direction", "continuation_successor"
            ),
        },
        "claims": "none",
        "not": [
            "six-axis fingerprint",
            "ontology promotion",
            "economic claim",
            "P-VSTATE-02 score",
        ],
    }


def write_outputs(
    rows: list[dict[str, Any]],
    rollup: dict[str, Any],
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / "rows.jsonl"
    rollup_path = out_dir / "rollup.json"
    with rows_path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    rollup_path.write_text(
        json.dumps(rollup, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return rows_path, rollup_path


def render_observation(rollup: dict[str, Any], *, events_path: Path) -> str:
    """Observation prose. Interprets counts. Does not mint a class."""
    n = rollup["n"]
    dirs = rollup["direction"]
    ages = rollup["age_since_sweep_bars"]
    succ = rollup["continuation_successor"]
    join = rollup["volume_join_status"]
    lines = [
        "# P-STRUCT-01 first observation",
        "",
        "> Evidence table only. Not a fingerprint. Not a finding. Not G001.",
        "> `UNKNOWN_N` is still `UNKNOWN_N` after these counts.",
        "",
        f"- Source: `{events_path.as_posix()}`",
        f"- Population n = **{n}** CRT `DISPLACEMENT` transitions",
        f"- Direction (SWEEP-event join): {dirs}",
        f"- Predecessor: {rollup['predecessor_state']}",
        f"- `after_sweep=true`: {rollup['after_sweep_true']} / {n}",
        f"- Age since sweep (bars, numeric only): min={ages['min']} max={ages['max']}",
        f"- Age class: {rollup['age_since_sweep_class']}  (must be UNKNOWN_N)",
        f"- Continuation successor: {succ}",
        f"- Continuation class: {rollup['continuation_age_class']}",
        f"- Volume join: {join}",
        f"- FM-062 volume_ratio numeric: {rollup.get('volume_ratio_numeric')}",
        f"- FM-063 volume_spike raw counts (not high_volume): "
        f"{rollup.get('volume_spike_raw_counts')}",
        f"- SEM-013 volume_participation (identity of FM-063): "
        f"{rollup.get('volume_participation')}",
        f"- CH-PSTRUCT-05 coincidence (declared columns only): "
        f"{rollup.get('coincidence_declared_columns')}",
        f"- `SWEEP→EXPANSION` skips excluded from the table: "
        f"{rollup['sweep_to_expansion_skips_excluded']}",
        "",
        "An interpreter may say the modal bar-age is common. It may not say",
        "that age is a defining displacement class. FM-062/063 stay numeric",
        "or absent; they are not `high_volume`. A join does not mint a class.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="P-STRUCT-01 CRT DISPLACEMENT evidence table (no fingerprint)."
    )
    ap.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "p_struct_01")
    ap.add_argument(
        "--volume-jsonl",
        type=Path,
        default=None,
        help="Pre-emitted official FM-062/063 values. Never computed here.",
    )
    ap.add_argument(
        "--join-official-pipeline",
        action="store_true",
        help="Join FM-062/063 from FeaturePipeline.run() on --csv. No local formula.",
    )
    ap.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="OHLCV used only with --join-official-pipeline (default: 2-year MT5 file).",
    )
    ap.add_argument(
        "--observation",
        type=Path,
        default=None,
        help="Optional markdown observation path (reports/...).",
    )
    args = ap.parse_args(argv)

    if not args.events.is_file():
        raise SystemExit(f"events file missing: {args.events}")
    if args.join_official_pipeline and args.volume_jsonl is not None:
        raise SystemExit("use either --join-official-pipeline or --volume-jsonl, not both")

    events = load_jsonl(args.events)
    if args.join_official_pipeline:
        volume_by_ts = official_volume_by_ts(args.csv)
        write_volume_join_jsonl(
            volume_by_ts, args.out_dir / "official_volume_join.jsonl"
        )
    else:
        volume_by_ts = load_volume_join(args.volume_jsonl)
    rows, rollup = extract_rows(events, volume_by_ts=volume_by_ts)
    rows_path, rollup_path = write_outputs(rows, rollup, args.out_dir)
    print(f"rows {len(rows)} -> {rows_path}")
    print(f"rollup -> {rollup_path}")
    if args.observation is not None:
        args.observation.parent.mkdir(parents=True, exist_ok=True)
        args.observation.write_text(
            render_observation(rollup, events_path=args.events),
            encoding="utf-8",
            newline="\n",
        )
        print(f"observation -> {args.observation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
