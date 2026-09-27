#!/usr/bin/env python
"""setup_grid_s4.py — STORY-83.12 (WP-L). The first S4 grid: sl_anchor x target_policy, TTL on.

WHAT THIS RUNS (user decision 2026-09-28, setup-overlay-spec-2026-09.md §10 Q8)
---------------------------------------------------------------------------
First grid = sl_anchor {displacement, sweep_extreme} x target_policy {fixed_r, structural_tp2},
trade_ttl_candles ON for every arm, everything else at v5's default. `decider` and the K23
F1/F2 keys (retrace_reset_pct, session_window_basis) are explicitly OUT of this first grid
(separate axes, per Q8) -- decider stays "engine" (Q4/§5, "resolver" raises NotImplementedError,
STORY-83.11b).

TTL VALUE: 20 candles (5h). This is a first-pass exploratory choice, not a tuned value -- §10 Q3a
left N unspecified ("start at a placeholder ... until a real value is chosen via the S4 grid or a
direct decision"). 20 was picked from F-024 (winners mature median 6 / p90 18 M15 bars), so it is
a generous timeout that should mostly bind on trades that would otherwise run very long, not a
claim about the right value. UNVERIFIED as a good choice; report it plainly.

EACH ARM: ExperimentSpec.kind="comparison" (§7.2). Runs in its own isolated config root
(src/utils/isolated_config_root.py, the proven v3/v5-parity mechanism) pinned to
v5_htfcrt_sot_dual_k23_2026_09 with sl_anchor + the new `setup` section mutated per arm.
No arm shares an output directory. ACTIVE_VERSION is never touched (S5 boundary, spec §7.4).

CORPUS: per CLAUDE.md's 2026-09-28 hard constraint (feedback_parity_checks_short_date_window.md)
and this spec's own §7.2 standing rule ("time-range subset first, full corpus after"), this
driver defaults to the SHORT-WINDOW fixture. --full-corpus opts into the real 47k-bar XAUUSD_M15
run and is NOT the default; a caller must ask for it explicitly.

RANKING GATE (§7.3, kept not changed): money-basis fields (net %, max DD, trade count, win rate)
are compared across ALL arms -- they don't depend on reference_level. R-basis fields are compared
ONLY within one reference_level (one sl_anchor), via governance.measurement_basis.can_compare,
called never re-implemented. Each arm's Basis is built from the SAME constants backtest_v2.py
stamps on every trade row (SL_ANCHOR_REFERENCE_LEVEL, BACKTEST_WALK_KERNEL, ENGINE_FILL_MODEL_ID,
BACKTEST_COST_MODEL_ID, TIE_BREAK_PRODUCTION/TIE_BREAK_CLOSE_ONLY per exit_model) -- not
re-derived from a guess, and cross-checked against a real trade row's stamped basis when the arm
has at least one trade (fail loudly if they ever disagree).

AUTHORITY: NONE (CLAUDE.md §6.5 Authority Ladder). This script produces information only; it
grants no production authority, no promotion, no G001 claim.

USAGE
    python scripts/research/setup_grid_s4.py                    # short-window fixture (default)
    python scripts/research/setup_grid_s4.py --full-corpus       # the real 47k-bar corpus
    python scripts/research/setup_grid_s4.py --ttl 30            # override the TTL candidate
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.isolated_config_root import build_config_root, run_backtest  # noqa: E402
from governance.measurement_basis import (  # noqa: E402
    Basis, can_compare, ALLOW_SAME_BASIS,
)

V5 = "v5_htfcrt_sot_dual_k23_2026_09"
INSTRUMENT = "XAUUSD"
SHORT_WINDOW_CORPUS = "data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv"
FULL_CORPUS = "data/mt5/XAUUSD_M15.csv"

# Mirrors backtest_v2.py's own constants exactly (not re-derived -- imported would create an
# import-order/circular-import risk since backtest_v2 is heavy; these four are frozen strings,
# not computed, so a literal copy here is the same value, verified against source at :166-186).
BACKTEST_WALK_KERNEL = "backtest_ledger"
BACKTEST_COST_MODEL_ID = "backtest_g1g2_v2"
ENGINE_FILL_MODEL_ID = "engine_intrabar"
SL_ANCHOR_REFERENCE_LEVEL = {"displacement": "displacement_extreme", "sweep_extreme": "sweep_extreme"}
TIE_BREAK_PRODUCTION = "production"
TIE_BREAK_CLOSE_ONLY = "close_only_no_tiebreak"

SL_ANCHORS = ("displacement", "sweep_extreme")
TARGET_POLICIES = ("fixed_r", "structural_tp2")


def arm_basis(sl_anchor: str, exit_model: str) -> Basis:
    tie_break = TIE_BREAK_PRODUCTION if exit_model == "intrabar_touch" else TIE_BREAK_CLOSE_ONLY
    return Basis(
        walk_kernel=BACKTEST_WALK_KERNEL,
        cost_model_id=BACKTEST_COST_MODEL_ID,
        fill_model_id=ENGINE_FILL_MODEL_ID,
        tie_break=tie_break,
        reference_level=SL_ANCHOR_REFERENCE_LEVEL[sl_anchor],
    )


def cross_check_basis_against_trades(expected: Basis, trades_csv: Path) -> None:
    """Fail loudly if a real trade row's stamped basis disagrees with the computed one."""
    if not trades_csv.exists():
        return
    with open(trades_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return
    r = rows[0]
    for axis in ("walk_kernel", "cost_model_id", "fill_model_id", "tie_break", "reference_level"):
        stamped = r.get(axis)
        expect = getattr(expected, axis)
        if stamped and stamped != expect:
            raise RuntimeError(
                f"basis mismatch: computed {axis}={expect!r} but trade row stamps {stamped!r} "
                f"({trades_csv}) -- the constants above have drifted from backtest_v2.py, fix them"
            )


def run_arm(tmp: Path, sl_anchor: str, target_policy: str, ttl: int, corpus_rel: str) -> dict:
    name = f"{sl_anchor}__{target_policy}"
    root = tmp / name
    equity_basis: dict = {}

    def mutate(cfg: dict) -> None:
        cfg.setdefault("backtest", {})["sl_anchor"] = sl_anchor
        cfg["setup"] = {"target_policy": target_policy, "trade_ttl_candles": ttl}
        # §7.3 required "equity basis" field -- read back, not guessed. Every arm shares this
        # value by construction (mutate never touches sizing), which is what Q5's fixed-ruler
        # rule requires; recorded per-arm anyway so the report proves it rather than assuming it.
        equity_basis["risk_pct_per_trade"] = cfg["backtest"].get("risk_pct_per_trade")
        equity_basis["sizing_mode"] = cfg["backtest"].get("sizing_mode")
        equity_basis["per_trade_investment_inr"] = cfg["backtest"].get("per_trade_investment_inr")

    build_config_root(REPO, root, V5, mutate_config=mutate)
    run_dir = run_backtest(REPO, root, corpus_rel, INSTRUMENT)

    summary_path = run_dir / f"{INSTRUMENT}_summary.json"
    trades_path = run_dir / f"{INSTRUMENT}_trades.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    exit_model = "intrabar_touch"  # v5's crt_engine.exit_model (verified at write time)
    basis = arm_basis(sl_anchor, exit_model)
    cross_check_basis_against_trades(basis, trades_path)

    return {
        "arm": name,
        "sl_anchor": sl_anchor,
        "target_policy": target_policy,
        "trade_ttl_candles": ttl,
        "decider": "engine",
        "basis": basis.as_dict(),
        "approved_trades": summary.get("approved_trades"),
        "rejected_trades": summary.get("rejected_trades"),
        "total_setups": summary.get("total_setups"),
        "win_rate": summary.get("win_rate"),
        "total_return_pct": summary.get("total_return_pct"),
        "annualized_return_pct": summary.get("annualized_return_pct"),
        "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "max_drawdown_rr": summary.get("max_drawdown_rr"),
        "total_pnl_rr_net": summary.get("total_pnl_rr_net"),
        "avg_rr_net": summary.get("avg_rr_net"),
        "equity_basis": equity_basis,
        "config_version": summary.get("config_version"),
        "target_policy_stamped": summary.get("target_policy"),
        "trade_ttl_candles_stamped": summary.get("trade_ttl_candles"),
        "run_dir": str(run_dir),
    }


def build_report(arms: list[dict]) -> dict:
    comparisons = []
    for i, a in enumerate(arms):
        for b in arms[i + 1:]:
            ba = Basis(**a["basis"])
            bb = Basis(**b["basis"])
            verdict, rationale = can_compare(ba, bb)
            comparisons.append({
                "a": a["arm"], "b": b["arm"], "verdict": verdict, "rationale": rationale,
            })
    money_ranked = sorted(
        arms, key=lambda a: (a["total_return_pct"] if a["total_return_pct"] is not None else float("-inf")),
        reverse=True,
    )
    r_groups: dict[str, list[dict]] = {}
    for a in arms:
        r_groups.setdefault(a["sl_anchor"], []).append(a)
    r_ranked = {
        k: sorted(v, key=lambda a: (a["total_pnl_rr_net"] if a["total_pnl_rr_net"] is not None else float("-inf")), reverse=True)
        for k, v in r_groups.items()
    }
    return {
        "authority": "NONE",
        "experiment_kind": "comparison",
        "arms": arms,
        "pairwise_basis_comparisons": comparisons,
        "money_basis_ranking_all_arms": [a["arm"] for a in money_ranked],
        "r_basis_ranking_within_anchor": {k: [a["arm"] for a in v] for k, v in r_ranked.items()},
        "caveats": [
            "trade_ttl_candles=20 is a first-pass exploratory value (F-024-informed), not tuned",
            "R-basis ranking is valid ONLY within one sl_anchor (reference_level differs across anchors -- can_compare DENY expected there, see pairwise_basis_comparisons)",
            "no economic claim: authority NONE, this is a comparison arm, not a promotion input",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full-corpus", action="store_true",
                     help="Run the real 47k-bar XAUUSD_M15 corpus instead of the short-window fixture (default). NOT the default -- explicit opt-in only.")
    ap.add_argument("--ttl", type=int, default=20, help="trade_ttl_candles for every arm (default 20, see module docstring)")
    ap.add_argument("--out", default=None, help="Output dir (default: results/setup_grid_s4/<ts>)")
    args = ap.parse_args()

    corpus_rel = FULL_CORPUS if args.full_corpus else SHORT_WINDOW_CORPUS
    if not (REPO / corpus_rel).exists():
        raise SystemExit(f"corpus not found: {corpus_rel}")

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) if args.out else (REPO / "results" / "setup_grid_s4" / ts)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="setup_grid_s4_") as tmp_s:
        tmp = Path(tmp_s)
        arms = []
        for sl_anchor in SL_ANCHORS:
            for target_policy in TARGET_POLICIES:
                print(f"[arm] sl_anchor={sl_anchor} target_policy={target_policy} ttl={args.ttl} corpus={corpus_rel}")
                arms.append(run_arm(tmp, sl_anchor, target_policy, args.ttl, corpus_rel))

    report = build_report(arms)
    report["corpus"] = corpus_rel
    report["generated_at"] = ts
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[report] {report_path}")
    for a in arms:
        print(f"  {a['arm']:30s} trades={a['approved_trades']!s:>4} "
              f"net%={a['total_return_pct']!s:>8} rr_net={a['total_pnl_rr_net']!s:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
