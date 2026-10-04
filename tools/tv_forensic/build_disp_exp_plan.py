"""Build event-centered M15 shot plans for P-VSTATE-02 (Option A).

One plan, one preset per US-DST season. A single clock calibration cannot
span winter and summer (F-066). Live-market edges only. Does not loosen
frame_shot. Does not include RETEST.

    python tools/tv_forensic/build_disp_exp_plan.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
EVENTS = (
    ROOT
    / "results"
    / "htf_objective_shadow"
    / "two_year"
    / "off"
    / "run_20260816_074305_XAUUSD"
    / "XAUUSD_events.jsonl"
)
OUT = Path(__file__).resolve().parent / "plans" / "disp_exp_shot_plan.json"

WINDOW = 160
CONTEXT = 48
ELIGIBLE = {"DISPLACEMENT", "EXPANSION"}

# US DST (second Sunday March -> first Sunday November), years on this corpus.
_DST = (
    (datetime(2024, 3, 10), datetime(2024, 11, 3)),
    (datetime(2025, 3, 9), datetime(2025, 11, 2)),
    (datetime(2026, 3, 8), datetime(2026, 11, 1)),
)


def _in_us_dst(ts: datetime) -> bool:
    for start, end in _DST:
        if start <= ts < end:
            return True
    return False


def _season_key(ts: datetime) -> str:
    dst = _in_us_dst(ts)
    y = ts.year
    if dst:
        return f"summer_{y}"
    if ts.month >= 11:
        return f"winter_{y}_{str(y + 1)[2:]}"
    return f"winter_{y - 1}_{str(y)[2:]}"


def _strip(ts: str) -> str:
    return ts[:16]


def main() -> int:
    rows: list[dict] = []
    with CSV_PATH.open(encoding="utf-8") as fh:
        for i, rec in enumerate(csv.DictReader(fh)):
            rec["_i"] = i
            rec["_ts"] = rec["timestamp"][:19]
            rows.append(rec)
    by_ts = {r["_ts"]: r for r in rows}

    events: list[dict] = []
    with EVENTS.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("event") != "STATE_TRANSITION":
                continue
            if rec.get("state_to") not in ELIGIBLE:
                continue
            ts = str(rec["timestamp"]).replace("T", " ")[:19]
            row = by_ts.get(ts)
            if row is None:
                raise SystemExit(f"event timestamp not in corpus: {ts}")
            if row["_i"] < CONTEXT - 1:
                continue
            events.append({
                "ts": ts,
                "idx": row["_i"],
                "state_to": rec["state_to"],
                "dt": datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"),
            })
    events.sort(key=lambda e: e["idx"])

    windows: list[dict] = []
    i = 0
    n_bars = len(rows)
    while i < len(events):
        ev = events[i]
        start = max(0, ev["idx"] - (CONTEXT - 1))
        end = min(n_bars - 1, start + WINDOW - 1)
        if end - start + 1 < WINDOW:
            start = max(0, end - WINDOW + 1)
        group = []
        while i < len(events) and events[i]["idx"] <= end:
            group.append(events[i])
            i += 1
        windows.append({
            "start_i": start,
            "end_i": end,
            "events": group,
            "season": _season_key(group[0]["dt"]),
        })

    seasons: dict[str, list[dict]] = {}
    for w in windows:
        seasons.setdefault(w["season"], []).append(w)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    index = {"engine_csv": "data/mt5/XAUUSD_M15.csv", "seasons": {}}

    print(f"events packed: {len(events)}")
    print(f"windows: {len(windows)}")
    for season, wins in seasons.items():
        shots: dict = {}
        keys = []
        anchors = []
        for j, w in enumerate(wins):
            key = f"d2_{season}_{j:03d}"
            keys.append(key)
            n_disp = sum(1 for e in w["events"] if e["state_to"] == "DISPLACEMENT")
            n_exp = sum(1 for e in w["events"] if e["state_to"] == "EXPANSION")
            shots[key] = {
                "name": key,
                "symbol": "OANDA:XAUUSD",
                "interval": "15",
                "clock": "broker",
                "start": _strip(rows[w["start_i"]]["_ts"]),
                "end": _strip(rows[w["end_i"]]["_ts"]),
                "note": (
                    f"P-VSTATE-02 {season} tile {j + 1}/{len(wins)}. "
                    f"{w['end_i'] - w['start_i'] + 1} bars. "
                    f"DISP={n_disp} EXP={n_exp}. Live-market edges from "
                    f"data/mt5/XAUUSD_M15.csv. Do not loosen frame_shot."
                ),
            }
        flat = [e for w in wins for e in w["events"]]
        step = max(1, len(flat) // 8)
        seen: set[str] = set()
        for e in flat[::step][:8]:
            t = _strip(e["ts"])
            if t in seen:
                continue
            seen.add(t)
            anchors.append({
                "event": e["state_to"],
                "time": t,
                "status": "CURRENT",
                "detail": f"clock-anchor {season}",
            })
        plan = {
            "_clock": (
                f"Single US-DST season {season}. calibrate_clock runs once. "
                "Do not merge with another season (F-066)."
            ),
            "engine_csv": "data/mt5/XAUUSD_M15.csv",
            "presets": {
                season: {
                    "description": f"P-VSTATE-02 Option A {season}",
                    "shots": keys,
                }
            },
            "shots": shots,
            "engine_events": anchors,
            "engine_events_provenance": {
                "source_run": str(EVENTS.relative_to(ROOT).as_posix()),
                "status": "CURRENT",
                "note": "Clock anchors only. Item ground truth is the events JSONL.",
            },
        }
        dest = OUT.parent / f"disp_exp_{season}.json"
        dest.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        nd = sum(1 for e in flat if e["state_to"] == "DISPLACEMENT")
        ne = sum(1 for e in flat if e["state_to"] == "EXPANSION")
        print(f"  {season}: {len(wins)} shots  DISP={nd} EXP={ne}  -> {dest.name}")
        index["seasons"][season] = {
            "plan": str(dest.relative_to(ROOT).as_posix()),
            "preset": season,
            "n_shots": len(wins),
            "n_disp": nd,
            "n_exp": ne,
        }

    index_path = OUT.parent / "disp_exp_index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
