# -*- coding: utf-8 -*-
"""
phase_s_selection_effect.py — Phase S1: does the spine's RETEST selection carry edge under the
governing truth standard? (thin CLI driver)

Re-measures F-002's "+0.145R selection edge at RETEST→EXECUTION" — STALE (pre-intrabar, no cost) —
under the GOVERNING intrabar_fixed + 12bps, pooled BY EFFECT across crypto-6, decomposed by
reject-reason class. Consumes the RETEST_REPLAY telemetry wired in S0.

Pipeline per instrument: run the spine backtest (reuse execution_planner_replay) → harvest
RETEST_REPLAY (selected = accepted, rejected = not) → forward_walk(intrabar_fixed)+CostModel each
retest → per-instrument ΔE by reason class → pool the effect (w=min(n_sel,n_rej)) → stratified
permutation + OOS + sign-consistency. All gate math lives in research.selection_effect; this wires
config → harvest → disk.

Reason classes (research_config_phase_s.json): SESSION is the F-017-null / F-006b-dominant lever
(rejects are off-session by construction → cannot be session-matched, inherently confounded). The
SCORE/ZONE rejects are IN an allowed session → the GENUINE selection-skill classes. A pooled overall
ΔE>0 only counts if it survives in SCORE/ZONE, sign-consistent across instruments, and OOS.

Deterministic JSON body (no wall-clock); manifest written separately.
Doctrine: any positive ΔE is a PRE-REGISTERED OOS CANDIDATE, never an edge.

Usage: python scripts/research/phase_s_selection_effect.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.contracts import Signal                                  # noqa: E402
from research.costs import CostModel                                   # noqa: E402
from research.measurement.forward_walk import forward_walk            # noqa: E402
from research.selection_effect import (                                # noqa: E402
    delta_e, fold_reason, pooled_delta, seed_for, sign_consistency,
    stratified_permutation_p,
)
from runtime.backtest_v2 import CandleLoader                          # noqa: E402
from scripts.research.execution_planner_replay import (               # noqa: E402
    _load_replay, _norm_ts, _run_backtest,
)
from utils.console_safe import safe_print                            # noqa: E402

DEFAULT_CONFIG = "configs/research/research_config_phase_s.json"
CLASSES = ["ALL", "SESSION", "ZONE", "SCORE", "OTHER"]  # ALL = every rejected; others = folded


def _harvest(instrument: str, csv: str, out_root: Path, replay_cfg: dict, reason_classes: dict):
    """Run the spine backtest, forward-walk retests under governing truth, return per-record rows."""
    tel, _trd, metrics = _run_backtest(instrument, csv, out_root / "_run" / instrument)
    replay = _load_replay(tel)
    candles = list(CandleLoader(csv, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    idx = {_norm_ts(str(c.timestamp)): i for i, c in enumerate(candles)}
    cost = CostModel(float(replay_cfg["round_trip_bps"]))
    mf = int(replay_cfg["max_forward"])
    sl_m, tp_m = float(replay_cfg["sl_atr_mult"]), float(replay_cfg["tp_atr_mult"])
    rows = []  # (candle_index, accepted, reason_class, net_rr)
    for r in replay:
        i = idx.get(_norm_ts(r["timestamp"]))
        if i is None:
            continue
        atr = float(r["atr"])
        future = candles[i + 1: i + 1 + mf]
        if atr <= 0.0 or not future:
            continue
        sig = Signal(instrument=instrument, timestamp=candles[i].timestamp, entry_index=i,
                     direction=("long" if int(r["direction"]) == 1 else "short"),
                     entry=float(r["entry"]), sl_atr_mult=sl_m, tp_atr_mult=tp_m, atr=atr)
        o = forward_walk(sig, future, max_forward=mf, exit_model=replay_cfg["exit_model"])
        net = cost.net_rr(o.rr_achieved, float(r["entry"]), sl_m * atr)
        cls = fold_reason(r["reject_reason"], reason_classes) if not r["accepted"] else "ACCEPTED"
        rows.append((i, bool(r["accepted"]), cls, net))
    rows.sort(key=lambda x: x[0])  # chronological for OOS
    return rows, metrics.approved_trades


def _split(rows, cls):
    """selected net-RRs and rejected(class) net-RRs for one instrument."""
    sel = [r[3] for r in rows if r[1]]
    if cls == "ALL":
        rej = [r[3] for r in rows if not r[1]]
    else:
        rej = [r[3] for r in rows if not r[1] and r[2] == cls]
    return sel, rej


def _class_block(per_inst_rows: dict, cls: str, n_perm: int, oos_split: float) -> dict:
    groups, per_inst, oos_groups = [], {}, []
    for inst in sorted(per_inst_rows):
        rows = per_inst_rows[inst]
        sel, rej = _split(rows, cls)
        groups.append((sel, rej))
        per_inst[inst] = {"n_sel": len(sel), "n_rej": len(rej),
                          "dE": round(delta_e(sel, rej), 4) if (sel and rej) else None}
        cut = int(round(len(rows) * (1.0 - oos_split)))
        oos_groups.append(_split(rows[cut:], cls))
    pooled, _ = pooled_delta(groups)
    obs, p, n_used = stratified_permutation_p(groups, n_perm, seed_for("phase_s", cls))
    pooled_oos, _ = pooled_delta(oos_groups)
    pos, tot = sign_consistency([per_inst[i]["dE"] for i in per_inst
                                 if per_inst[i]["dE"] is not None])
    return {
        "pooled_dE": round(pooled, 4) if pooled == pooled else None,
        "p_value": round(p, 6),
        "pooled_dE_oos": round(pooled_oos, 4) if pooled_oos == pooled_oos else None,
        "n_instruments_used": n_used,
        "sign_consistency": f"{pos}/{tot}",
        "per_instrument": per_inst,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_s_selection_effect")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="results/research/phase_s")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    uni, rep, sigc, oos = cfg["universe"], cfg["replay"], cfg["significance"], cfg["oos"]
    reason_classes = cfg["reason_classes"]
    out_root = Path(args.out)
    data_dir = Path(uni["data_dir"])

    per_inst_rows: dict[str, list] = {}
    trust: dict[str, dict] = {}
    for inst in uni["instruments"]:
        csv = str(data_dir / f"{inst}_M15.csv")
        if not Path(csv).exists():
            safe_print(f"  skip {inst}: no CSV"); continue
        rows, approved = _harvest(inst, csv, out_root, rep, reason_classes)
        per_inst_rows[inst] = rows
        n_sel = sum(1 for r in rows if r[1])
        trust[inst] = {"approved_trades": approved, "selected": n_sel,
                       "rejected": len(rows) - n_sel, "selected_eq_approved": n_sel == approved}
        safe_print(f"  {inst}: retests={len(rows)} selected={n_sel} (approved={approved}) "
                   f"rejected={len(rows) - n_sel}")

    n_perm = int(sigc["n_permutations"])
    blocks = {cls: _class_block(per_inst_rows, cls, n_perm, float(oos["split"])) for cls in CLASSES}

    # Verdict: genuine selection skill must live in SCORE/ZONE (not SESSION), be significant,
    # sign-consistent (>= majority), and OOS-positive.
    def _survives(cls):
        b = blocks[cls]
        if b["pooled_dE"] is None or b["n_instruments_used"] == 0:
            return False
        pos, tot = (int(x) for x in b["sign_consistency"].split("/"))
        return (b["pooled_dE"] > 0 and b["p_value"] <= float(sigc["alpha"])
                and tot > 0 and pos / tot >= 0.5
                and (b["pooled_dE_oos"] or 0) > 0)
    skill_classes = [c for c in ("SCORE", "ZONE") if _survives(c)]
    session_only = (not skill_classes) and _survives("SESSION")
    verdict = ("SELECTION_SKILL_SURVIVES" if skill_classes else
               "SELECTION_IS_SESSION_ONLY" if session_only else
               "SELECTION_NULL")

    report = {
        "phase": "S1",
        "truth_standard": {"exit_model": rep["exit_model"], "round_trip_bps": rep["round_trip_bps"],
                           "sl_atr_mult": rep["sl_atr_mult"], "tp_atr_mult": rep["tp_atr_mult"],
                           "max_forward": rep["max_forward"], "n_permutations": n_perm,
                           "alpha": sigc["alpha"], "oos_split": oos["split"]},
        "instruments": sorted(per_inst_rows),
        "trust_gate": trust,
        "classes": blocks,
        "verdict": verdict,
        "skill_classes": skill_classes,
        "doctrine": "a survivor is a PRE-REGISTERED OOS CANDIDATE, never an edge",
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "phase_s_selection_effect.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    (out_root / "phase_s_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit(), "config": args.config}, sort_keys=True, indent=2),
        encoding="utf-8")
    _print(report)
    safe_print(f"\n-> {out_root / 'phase_s_selection_effect.json'}")
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print(report: dict) -> None:
    safe_print("\nPHASE S1 — RETEST selection effect (selected − rejected) under intrabar_fixed+12bps\n")
    safe_print("  ΔE>0 = selected retests beat rejected. SCORE/ZONE = genuine skill; "
               "SESSION = F-017-null lever.\n")
    hdr = f"| {'class':8s} | {'pooled ΔE':>10s} | {'perm_p':>7s} | {'ΔE OOS':>8s} | {'sign':>6s} | {'n_inst':>6s} |"
    sep = "|" + "-" * 10 + "|" + "-" * 12 + "|" + "-" * 9 + "|" + "-" * 10 + "|" + "-" * 8 + "|" + "-" * 8 + "|"
    safe_print(hdr); safe_print(sep)
    for cls in CLASSES:
        b = report["classes"][cls]
        dE = "n/a" if b["pooled_dE"] is None else f"{b['pooled_dE']:+.4f}"
        oos = "n/a" if b["pooled_dE_oos"] is None else f"{b['pooled_dE_oos']:+.4f}"
        safe_print(f"| {cls:8s} | {dE:>10s} | {b['p_value']:7.4f} | {oos:>8s} | "
                   f"{b['sign_consistency']:>6s} | {b['n_instruments_used']:6d} |")
    safe_print(sep)
    safe_print(f"\nVERDICT: {report['verdict']}  skill_classes={report['skill_classes'] or 'none'}")


if __name__ == "__main__":
    raise SystemExit(main())
