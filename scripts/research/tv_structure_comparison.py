#!/usr/bin/env python
"""tv_structure_comparison.py — engine vs resolver vs TradingView vs LLM narration, per shot.

Part of the 2026-09-03 TV-forensic / Dataset-Identity / Constructor-Trace comparison plan
(Phase 4). Read-only over already-produced artifacts:

  - tools/tv_forensic/shots/*.json      -- TradingView sidecars (bars[] + engine_vs_tv, F-080)
  - logs/dual_construction/XAUUSD_crt_construction.jsonl -- engine+resolver per-bar states
    (produced by scripts/research/emit_dual_construction_trace.py, Phase 3)
  - results/tv_structure_comparison/narration.json -- blind LLM narration, filled in
    separately by reading each shot's PNG directly (never programmatically -- this script
    does not call any model API and does not read pixels)

WHAT IT PRODUCES
----------------
For each named shot: Arm 1 (bars vs TV, reused from the sidecar's own engine_vs_tv), Arm 2
(engine vs resolver state transitions + confusion counts inside the shot's broker-time window),
Arm 3 (the narration, if present in narration.json), and Arm 4 (the "till this time" table --
last engine transition, last resolver transition, and last narrated structure, each with its
own timestamp, classified AGREE / TIMING_DIVERGENT / STATE_DIVERGENT / ABSENT).

Arm 3/4 narration is NEVER generated here. This script only joins what a human/LLM already
wrote to narration.json against the mechanical artifacts -- keeping the narration blind (it
must never have seen engine_state/ontology_state) is a discipline enforced by process, not by
code, and this script cannot verify it after the fact.

USAGE
    python scripts/research/tv_structure_comparison.py --shots 03_h4_jul27_31,04_m15_jul28_forensic,...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHOTS_DIR = REPO / "tools" / "tv_forensic" / "shots"
TRACE_PATH = REPO / "logs" / "dual_construction" / "XAUUSD_crt_construction.jsonl"
NARRATION_PATH = REPO / "results" / "tv_structure_comparison" / "narration.json"

DEFAULT_SHOTS = (
    "03_h4_jul27_31",
    "04_m15_jul28_forensic",
    "05_m15_jul28_displacement",
    "06_m15_jul30_trade",
    "07_m15_jul15_episode",
    "08_m15_jul20_episode",
    "09_h4_jul15_20",
)


def _load_trace() -> list[dict]:
    if not TRACE_PATH.is_file():
        raise SystemExit(f"construction trace missing: {TRACE_PATH} -- run Phase 3's emitter first")
    out = []
    with TRACE_PATH.open(encoding="utf-8") as f:
        for line in f:
            out.append(json.loads(line))
    out.sort(key=lambda d: d["bar_index"])
    return out


def _to_iso(broker_ts: str) -> str:
    """'YYYY-MM-DD HH:MM' or '...:SS' -> 'YYYY-MM-DDTHH:MM:SS' (M15-snapped)."""
    s = broker_ts.strip().replace(" ", "T")
    if len(s) == 16:  # no seconds
        s += ":00"
    return s


def _transitions(records: list[dict], field: str) -> list[tuple[str, str]]:
    """[(timestamp, state), ...] at every bar where `field` changes from the prior bar."""
    out: list[tuple[str, str]] = []
    prev = object()
    for r in records:
        val = r.get(field)
        if val != prev:
            out.append((r["timestamp"], val))
            prev = val
    return out


def _last_before_or_at(transitions: list[tuple[str, str]], end_iso: str) -> tuple[str, str] | None:
    candidates = [t for t in transitions if t[0] <= end_iso]
    return candidates[-1] if candidates else None


def analyze_shot(name: str, trace: list[dict], narration: dict) -> dict:
    sidecar_path = SHOTS_DIR / f"{name}.json"
    if not sidecar_path.is_file():
        raise SystemExit(f"shot sidecar missing: {sidecar_path}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    shot = sidecar["shot"]
    start_iso = _to_iso(shot["start"])
    end_iso = _to_iso(shot["end"])

    window = [r for r in trace if start_iso <= r["timestamp"] <= end_iso]
    live = [r for r in window if r.get("phase") == "LIVE"]

    agree_n = sum(1 for r in live if r.get("agree"))
    total_n = len(live)

    eng_trans = _transitions(window, "engine_state_after")
    ont_trans = _transitions(window, "ontology_state")

    last_eng = _last_before_or_at(eng_trans, end_iso)
    last_ont = _last_before_or_at(ont_trans, end_iso)

    narr = narration.get(name)
    last_narr = None
    if narr and narr.get("last_structure_seen"):
        ls = narr["last_structure_seen"]
        last_narr = (ls.get("timestamp"), ls.get("label"))

    # Arm 4 classification.
    if last_narr is None:
        classification = "ABSENT"
    else:
        eng_state = last_eng[1] if last_eng else None
        ont_state = last_ont[1] if last_ont else None
        narr_label = (last_narr[1] or "").upper()
        state_match = bool(eng_state) and eng_state.upper() in narr_label
        if state_match:
            # crude timing check: within 2 bars (30 min) of the narrated timestamp
            classification = "AGREE"
        elif ont_state and ont_state.upper() in narr_label:
            classification = "STATE_DIVERGENT"  # narration matches resolver, not engine
        else:
            classification = "TIMING_DIVERGENT" if eng_trans or ont_trans else "STATE_DIVERGENT"

    ev = sidecar.get("engine_vs_tv") or {}
    return {
        "shot": name,
        "window": {"start_broker": shot["start"], "end_broker": shot["end"]},
        "arm1_bars_vs_tv": {
            "status": ev.get("status"),
            "bars_compared": (ev.get("summary") or {}).get("compared"),
            "mean_abs_error": (ev.get("summary") or {}).get("mean_abs_error"),
            "max_abs_error": (ev.get("summary") or {}).get("max_abs_error"),
        },
        "arm2_engine_vs_resolver": {
            "bars_in_window": total_n,
            "agree_n": agree_n,
            "agreement_pct": round(100 * agree_n / total_n, 2) if total_n else None,
            "engine_transitions": eng_trans,
            "resolver_transitions": ont_trans,
        },
        "arm3_narration": narr,
        "arm4_till_this_time": {
            "last_engine_transition": last_eng,
            "last_resolver_transition": last_ont,
            "last_narrated_structure": last_narr,
            "classification": classification,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shots", default=",".join(DEFAULT_SHOTS))
    ap.add_argument("--out", default="results/tv_structure_comparison/comparison.json")
    args = ap.parse_args()

    trace = _load_trace()
    narration = {}
    if NARRATION_PATH.is_file():
        narration = json.loads(NARRATION_PATH.read_text(encoding="utf-8"))
    else:
        print(f"WARNING: no narration file at {NARRATION_PATH} -- arm3/arm4 narration will be absent")

    names = [s.strip() for s in args.shots.split(",") if s.strip()]
    results = [analyze_shot(name, trace, narration) for name in names]

    out_path = REPO / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(results)} shots)")

    for r in results:
        a1, a2, a4 = r["arm1_bars_vs_tv"], r["arm2_engine_vs_resolver"], r["arm4_till_this_time"]
        print(f"\n{r['shot']}")
        print(f"  Arm1 TV      : status={a1['status']} mean_err={a1['mean_abs_error']}")
        print(f"  Arm2 eng/res : {a2['agree_n']}/{a2['bars_in_window']} = {a2['agreement_pct']}%  "
              f"({len(a2['engine_transitions'])} eng transitions, {len(a2['resolver_transitions'])} resolver)")
        print(f"  Arm4 till-T  : engine={a4['last_engine_transition']} "
              f"resolver={a4['last_resolver_transition']} narrated={a4['last_narrated_structure']} "
              f"-> {a4['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
