# -*- coding: utf-8 -*-
"""candle_state_report.py — consolidate Program 4b/4c/4d into one evidence table (incl. failures).

Reads the deterministic Stage-1 (transition_information.json) and Stage-2 (qualify_transitions.json)
artifacts and emits:
  * candle_state_results.csv  — every program × group row (Stage-1 stats + Stage-2 verdict), the
    user's "single consolidated evidence table covering every tested hypothesis, including failures."
  * EDGE_SUMMARY.md           — executive summary + Program-4 closure status.

Reporting only — no statistics, no gating. Run AFTER both gates.

Usage:
    python scripts/research/candle_state_report.py --in results/research/candle_state
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from utils.console_safe import safe_print   # noqa: E402

PROGRAMS = ("4b_vol_expansion", "4b_range_expansion", "4c_persistence", "4d_regime_transition")


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="candle_state_report")
    ap.add_argument("--in", dest="indir", default="results/research/candle_state")
    args = ap.parse_args(argv)
    d = Path(args.indir)

    stage1 = _load(d / "transition_information.json")
    stage2 = _load(d / "qualify_transitions.json")

    rows: list[dict] = []
    if stage1:
        for grp in ("crypto", "fx"):
            for prog in PROGRAMS:
                s = stage1["pooled"][grp][prog]
                rows.append({
                    "stage": "1_information",
                    "program": prog,
                    "group": grp,
                    "n": s["n_decision"],
                    "ig_k4": s["ig_curve"].get("4", ""),
                    "perm_p": s["decision_p_value"],
                    "half_life_bars": s["half_life"]["half_life_bars"],
                    "mi_retention": s["stability"]["retention"],
                    "stage1_pass": s["stage1_pass"],
                    "cross_market": stage1["cross_market"][prog],
                    "verdict": "",
                    "pf": "", "expectancy": "", "win_rate": "", "max_lose_streak": "",
                })
    if stage2:
        for grp, g in stage2["groups"].items():
            for scope, r in g["scopes"].items():
                v = r["verdict"]
                rep = r["reporting"]
                rows.append({
                    "stage": "2_economic",
                    "program": "compression_breakout",
                    "group": f"{grp}:{scope}",
                    "n": v["n"],
                    "ig_k4": "", "perm_p": v["p_value"], "half_life_bars": "",
                    "mi_retention": "",
                    "stage1_pass": "",
                    "cross_market": "",
                    "verdict": v["verdict"],
                    "pf": round(v["profit_factor"], 4),
                    "expectancy": round(v["expectancy_rr"], 4),
                    "win_rate": rep["win_rate"],
                    "max_lose_streak": rep["max_losing_streak"],
                })

    d.mkdir(parents=True, exist_ok=True)
    csv_path = d / "candle_state_results.csv"
    fields = ["stage", "program", "group", "n", "ig_k4", "perm_p", "half_life_bars",
              "mi_retention", "stage1_pass", "cross_market", "verdict", "pf", "expectancy",
              "win_rate", "max_lose_streak"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Executive summary + closure status.
    survivors = [p for p in PROGRAMS if stage1 and stage1["cross_market"][p] != "REJECTED"]
    promoted = []
    if stage2:
        for grp, g in stage2["groups"].items():
            for scope, r in g["scopes"].items():
                if r["verdict"]["verdict"] == "PROMOTE":
                    promoted.append(f"{grp}:{scope}")

    # Program-4 closure: every program is (Stage1 FAIL) or (Stage1 PASS + Stage2 FAIL→no PROMOTE).
    closure = bool(stage1 and stage2 and not promoted)

    lines = ["# Candle-State Transition Frontier — Evidence Summary (Program 4b/4c/4d)", ""]
    lines.append("> Non-directional information gate (Stage 1) + economic gate (Stage 2). "
                 "Authority: research/docs only. See docs/research/preregistration-program-4bcd.md.")
    lines.append("")
    lines.append("## Stage-1 cross-market verdicts")
    lines.append("")
    lines.append("| Program | crypto p | crypto half-life | crypto retention | fx p | cross-market |")
    lines.append("|---|---|---|---|---|---|")
    if stage1:
        for prog in PROGRAMS:
            c = stage1["pooled"]["crypto"][prog]
            fx = stage1["pooled"]["fx"][prog]
            lines.append(f"| {prog} | {c['decision_p_value']} | "
                         f"{c['half_life']['half_life_bars']} | {c['stability']['retention']} | "
                         f"{fx['decision_p_value']} | {stage1['cross_market'][prog]} |")
    lines += ["", f"**Stage-1 survivors (→ Stage 2):** {survivors or 'none'}", ""]
    lines.append("## Stage-2 economic verdicts (compression_breakout)")
    lines.append("")
    lines.append("| group:scope | n | PF | E(net) | WR | verdict |")
    lines.append("|---|---|---|---|---|---|")
    if stage2:
        for grp, g in stage2["groups"].items():
            for scope, r in g["scopes"].items():
                v = r["verdict"]
                lines.append(f"| {grp}:{scope} | {v['n']} | {round(v['profit_factor'],3)} | "
                             f"{round(v['expectancy_rr'],4)} | {r['reporting']['win_rate']} | "
                             f"{v['verdict']} |")
    lines += ["", f"**PROMOTE:** {promoted or 'none'}", ""]
    lines.append("## Program-4 closure")
    lines.append("")
    if closure:
        lines.append("**CLOSED.** Every program resolved to (Stage-1 FAIL) or "
                     "(Stage-1 PASS + Stage-2 FAIL). Per the pre-registered closure rule, no further "
                     "candle-state work may be promoted without new data, a new market domain, or a "
                     "new ontology (4e/4f/4g parameter variants = archaeology, out of bounds).")
    else:
        lines.append("Closure conditions NOT all met (a PROMOTE exists, or a stage is missing). "
                     "Program 4 remains OPEN.")
    (d / "EDGE_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    safe_print(f"-> {csv_path}")
    safe_print(f"-> {d / 'EDGE_SUMMARY.md'}")
    safe_print(f"Stage-1 survivors: {survivors or 'none'} | PROMOTE: {promoted or 'none'} | "
               f"closure={'CLOSED' if closure else 'OPEN'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
