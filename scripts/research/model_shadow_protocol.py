"""model_shadow_protocol.py — generalized shadow A/B for an optional model slot.

Generalizes scripts/research/bitnet_shadow_diagnostic.py (which stays in place,
unchanged, as the frozen BitNet-specific record) into a reusable protocol for
ANY earned-only optional slot (target-strategy-architecture.md §13 item7 / §6 —
BitNet / any future model must be shadow-measured before ΔG001 authority is
even considered, never folded into a threshold search blindly).

WHAT THIS IS
------------
The SAME OFF-vs-ON book-level comparison bitnet_shadow_diagnostic.py pioneered
(entry sets are NOT nested — a gate reject resets the CRT state machine, so
gate-ON is a divergent trajectory; compare at the BOOK level), parameterized on
(off_config, on_config, instruments, label) instead of hardcoded to BitNet, and
additionally reporting each book's gap to G001 via research.goal_alignment
(the Phase-F module) — using the honest, no-fabrication metric mapping (no
guessed trades_per_month unless --months is given, no R->% drawdown coercion).

WHAT THIS IS NOT
----------------
* Not a promotion mechanism. It prints a decision; it NEVER writes
  `use_bitnet` (or any other enable flag) back to a production config file.
  Enabling any slot on ACTIVE remains a human/governance act, always.
* Not model training or hyperparameter search — this measures ONE fixed
  config pair (off vs on), nothing is swept.

USAGE
-----
    python scripts/research/model_shadow_protocol.py \\
        --label bitnet_gate \\
        --off-config configs/research/research_config_spine_majors.json \\
        --on-config configs/research/research_config_spine_bitnet_shadow.json \\
        --instruments BNBUSDT ETHUSDT BTCUSDT SOLUSDT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from research.adapters.spine_signal_source import ProductionSpineSource, SpineEntry
from research.contracts import EdgeReport
from research.goal_alignment import goal_report_for_edge


def _rr(entry: SpineEntry) -> float:
    return float(entry.meta.get("backtest_pnl_rr_net", 0.0))


def _stats(entries: list[SpineEntry]) -> dict:
    n = len(entries)
    if n == 0:
        return {"n": 0, "expectancy_rr": None, "win_rate": None, "profit_factor": None}
    rrs = [_rr(e) for e in entries]
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    return {
        "n": n,
        "expectancy_rr": round(sum(rrs) / n, 4),
        "win_rate": round(len(wins) / n, 4),
        "profit_factor": (round(pf, 4) if pf != float("inf") else "inf"),
        "sum_rr": round(sum(rrs), 4),
    }


def _stats_to_edge_report(label: str, stats: dict) -> EdgeReport | None:
    """Best-effort EdgeReport shim so this diagnostic's book stats can reuse
    goal_report_for_edge — this diagnostic only measures n/win_rate/expectancy_rr,
    so every other EdgeReport field is an unused 0.0 placeholder (goal_alignment
    only reads win_rate/expectancy_rr/n)."""
    if stats["n"] == 0 or stats["win_rate"] is None:
        return None
    return EdgeReport(
        hypothesis=label, instruments=[], n=stats["n"], wins=0, losses=0,
        win_rate=stats["win_rate"],
        profit_factor=(stats["profit_factor"] if isinstance(stats["profit_factor"], (int, float)) else 0.0),
        expectancy_rr=stats["expectancy_rr"],
        mfe_p50=0.0, mfe_p90=0.0, mae_p50=0.0, mae_p90=0.0,
        median_time_to_failure=0.0, continuation_prob=0.0, max_drawdown_rr=0.0,
    )


def diagnose(off_config: str, on_config: str, instrument: str) -> dict:
    off_src = ProductionSpineSource(config_path=off_config)
    on_src = ProductionSpineSource(config_path=on_config)

    off = off_src.entries(instrument)
    on = on_src.entries(instrument)

    off_keys, on_keys = set(off), set(on)
    removed_keys = off_keys - on_keys
    added_keys = on_keys - off_keys

    off_book = [off[k] for k in sorted(off_keys)]
    on_book = [on[k] for k in sorted(on_keys)]
    removed = [off[k] for k in sorted(removed_keys)]
    added = [on[k] for k in sorted(added_keys)]

    s_off, s_on = _stats(off_book), _stats(on_book)
    s_removed, s_added = _stats(removed), _stats(added)

    book_delta = None
    if s_off["expectancy_rr"] is not None and s_on["expectancy_rr"] is not None:
        book_delta = round(s_on["expectancy_rr"] - s_off["expectancy_rr"], 4)

    if not removed_keys and not added_keys:
        verdict = "INERT"
    elif book_delta is None:
        verdict = "UNDETERMINED"
    elif book_delta > 1e-9:
        verdict = "HELPFUL"
    elif book_delta < -1e-9:
        verdict = "HARMFUL"
    else:
        verdict = "NEUTRAL"

    return {
        "instrument": instrument,
        "n_off": len(off), "n_on": len(on),
        "n_removed": len(removed_keys), "n_added": len(added_keys),
        "off_book": s_off, "on_book": s_on,
        "removed": s_removed, "added": s_added,
        "book_delta_expectancy": book_delta,
        "verdict": verdict,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Generalized model-slot shadow A/B (off-config vs on-config). "
                     "NEVER writes an enable flag — prints the ΔG001 decision and exits."
    )
    ap.add_argument("--label", required=True,
                     help="name of the slot under test, e.g. bitnet_gate (report/print only)")
    ap.add_argument("--off-config", required=True)
    ap.add_argument("--on-config", required=True)
    ap.add_argument("--instruments", nargs="+", required=True)
    ap.add_argument("--months", type=float, default=None,
                     help="optional observation window (months) for the trades_per_month "
                          "G001 criterion; omitted = that criterion SKIPs (no guess)")
    ap.add_argument("--out", default=None,
                     help="default: results/model_shadow/<label>_shadow_diagnostic.json")
    args = ap.parse_args(argv)

    out_path = Path(args.out) if args.out else Path(f"results/model_shadow/{args.label}_shadow_diagnostic.json")

    results = []
    pooled_off: list[SpineEntry] = []
    pooled_on: list[SpineEntry] = []
    for inst in args.instruments:
        print(f"[RUN] {args.label} | {inst}: OFF vs ON ...", flush=True)
        r = diagnose(args.off_config, args.on_config, inst)
        results.append(r)
        print(
            f"  {inst}: n_off={r['n_off']} n_on={r['n_on']} removed={r['n_removed']} "
            f"added={r['n_added']} | E_off={r['off_book']['expectancy_rr']} "
            f"E_on={r['on_book']['expectancy_rr']} delta={r['book_delta_expectancy']} "
            f"| {r['verdict']}", flush=True,
        )
        pooled_off.extend(ProductionSpineSource(config_path=args.off_config).entries(inst).values())
        pooled_on.extend(ProductionSpineSource(config_path=args.on_config).entries(inst).values())

    s_pool_off, s_pool_on = _stats(pooled_off), _stats(pooled_on)
    pool_delta = None
    if s_pool_off["expectancy_rr"] is not None and s_pool_on["expectancy_rr"] is not None:
        pool_delta = round(s_pool_on["expectancy_rr"] - s_pool_off["expectancy_rr"], 4)

    off_edge = _stats_to_edge_report(f"{args.label}_off", s_pool_off)
    on_edge = _stats_to_edge_report(f"{args.label}_on", s_pool_on)
    goal_reports = {
        "off": goal_report_for_edge(off_edge, args.months) if off_edge else None,
        "on":  goal_report_for_edge(on_edge, args.months) if on_edge else None,
    }

    report = {
        "kind": "model_shadow_protocol",
        "label": args.label,
        "off_config": args.off_config, "on_config": args.on_config,
        "scope": "research-authority-only (CLAUDE.md sec6.5) — this script NEVER writes an "
                 "enable flag to any production config; enabling a slot is a separate, "
                 "human governance act",
        "note": "Entry sets are NOT nested: an on-path reject resets the CRT state machine, "
                "so ON is a divergent trajectory (removed != added). Compare at BOOK level.",
        "per_instrument": results,
        "pooled": {"off_book": s_pool_off, "on_book": s_pool_on, "book_delta_expectancy": pool_delta},
        "goal_report": goal_reports,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n===== POOLED ({args.label}) =====")
    print(f"  E_off={s_pool_off['expectancy_rr']}  E_on={s_pool_on['expectancy_rr']}  delta={pool_delta}")
    if goal_reports["off"] is not None:
        print(f"  G001 gap OFF: {goal_reports['off']['decision']}  "
              f"failed={[c['name'] for c in goal_reports['off']['criteria'] if c['status']=='FAIL']}")
    if goal_reports["on"] is not None:
        print(f"  G001 gap ON:  {goal_reports['on']['decision']}  "
              f"failed={[c['name'] for c in goal_reports['on']['criteria'] if c['status']=='FAIL']}")
    print(f"\n[OK] wrote {out_path}")
    print("[SCOPE] No enable flag written. Enabling this slot on ACTIVE requires separate, "
          "human-approved promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
