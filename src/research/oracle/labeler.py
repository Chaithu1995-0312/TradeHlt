"""labeler.py — Stage 1 of the profitable-entry oracle program (SEM-018).

Simulates a hypothetical trade at EVERY bar, in BOTH directions, under the production
Entry/SL/TP1/TP2 geometry (SEM-017), and records what it would have realised. The label
set is the cartesian product of

    bars  x  {long, short}  x  {disp_bar, fixed_atr}  x  {production, optimistic}

so ~47,200 bars produce ~378,000 labelled units on XAUUSD M15.

WHAT THIS IS FOR
----------------
Detaching measurement from detection. Every prior program here labelled only the bars a
detector selected, which tied statistical power to detector throughput and repeatedly
produced samples too small to conclude anything. This labels the bars the detector never
looked at too.

WHAT IT IS NOT
--------------
Selecting bars by their realised outcome is lookahead BY CONSTRUCTION. These labels
describe the past; they are not an edge and cannot become one without being evaluated as
a forward rule on a partition that did not select them. That constraint is recorded on
SEM-018 as a validation rule, not left to a report's caveats.

LABELS ARE DERIVED, NEVER READ
------------------------------
`y_R` comes from `multi_tp_walk` at source. Reading an outcome or rr field off
`opportunities.jsonl` or a trade ledger is forbidden — that stream is a detection stream
and is not self-consistent.

COST IS PROPORTIONAL TO R, SO GEOMETRY MOVES IT
-----------------------------------------------
`ComponentCostModel.cost_r` is `cost_price / risk_distance`. The `disp_bar` geometry
produces bar-local (tight) stops, so it pays several times more cost in R than the
`fixed_atr` geometry does for the same broker. Both gross and net are therefore carried
on every row: net is the honest definition of "profitable", but a net figure dominated by
a tight stop describes the geometry, not the market.

Usage:
    python -m research.oracle.labeler --instrument XAUUSD --timeframe M15
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import get_prod_section  # noqa: E402
from research.costs import ComponentCostModel  # noqa: E402
from research.measurement.forward_walk import AdverseFill  # noqa: E402
from research.oracle.multi_tp_walk import (  # noqa: E402
    TIE_BREAK_OPTIMISTIC,
    TIE_BREAK_PRODUCTION,
    multi_tp_walk,
)

SL_GEOM_DISP_BAR = "disp_bar"
SL_GEOM_FIXED_ATR = "fixed_atr"
SL_GEOMETRIES = (SL_GEOM_DISP_BAR, SL_GEOM_FIXED_ATR)
TIE_BREAKS = (TIE_BREAK_PRODUCTION, TIE_BREAK_OPTIMISTIC)

# The PRIMARY arm. The other three are declared robustness arms, not three extra shots at
# significance — see the program's multiplicity declaration.
PRIMARY_ARM = (SL_GEOM_DISP_BAR, TIE_BREAK_PRODUCTION)


@dataclass(frozen=True)
class Bar:
    """Forward bar fed to the walk kernel."""

    high: float
    low: float
    close: float
    open: float
    index: int


def _tp1_multiplier(crt_cfg: dict, intent: str) -> float:
    """`crt_engine.tp1_atr_multiplier_<intent>`, falling back to the base key.

    Mirrors `ExecutionEngine.build_trade`'s getattr lookup. Despite the key name these
    are R-multiples of `risk_dist`, not ATR multiples.
    """
    key = f"tp1_atr_multiplier_{intent}"
    if key in crt_cfg:
        return float(crt_cfg[key])
    return float(crt_cfg["tp1_atr_multiplier"])


def _nights_held(entry_ts, exit_ts) -> int:
    """Calendar-date boundaries crossed between entry and exit, as a declared proxy.

    The broker's true rollover hour is not recorded anywhere in this repository, so this
    counts stamped date changes instead. Declared as a proxy rather than presented as a
    measurement; the count of affected trades is reported in the manifest so the
    assumption is visible rather than buried.
    """
    if entry_ts is None or exit_ts is None:
        return 0
    return max(0, (exit_ts.date() - entry_ts.date()).days)


def label_corpus(
    matrix: pd.DataFrame,
    raw: pd.DataFrame,
    *,
    cost_model: ComponentCostModel,
    adverse_fill: AdverseFill | None,
    max_forward: int = 40,
    sl_atr_buffer: float = 0.2,
    tp2_mult: float = 2.0,
    fixed_sl_atr_mult: float = 1.0,
    partial_fraction: float = 0.5,
    trail_fraction: float = 0.5,
    crt_cfg: dict | None = None,
    charge_swap: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Label every (bar, direction, sl_geom, tie_break) unit. Returns (labels, stats)."""
    t0 = time.time()
    crt_cfg = crt_cfg or {}

    bars = [
        Bar(high=float(h), low=float(lo), close=float(c), open=float(o), index=int(i))
        for h, lo, c, o, i in zip(
            raw["high"], raw["low"], raw["close"], raw["open"], raw["_pos"]
        )
    ]
    ts_by_pos = list(raw["timestamp"])
    n_raw = len(bars)

    pos_list = matrix["_pos"].astype(int).tolist()
    close_list = matrix["close"].astype(float).tolist()
    atr_abs_list = matrix["atr_abs"].astype(float).tolist()
    intent_list = matrix["trade_intent"].tolist()

    tp1_cache = {i: _tp1_multiplier(crt_cfg, i) for i in set(intent_list)}

    out_rows = []
    rejects = Counter()
    swap_nights = Counter()

    for row_i, p in enumerate(pos_list):
        # A unit needs a full forward window; a truncated one is a different measurement.
        if p + max_forward >= n_raw:
            rejects["insufficient_forward_window"] += 1
            continue
        entry = close_list[row_i]
        atr_abs = atr_abs_list[row_i]
        if not (atr_abs > 0):
            rejects["non_positive_atr"] += 1
            continue
        tp1_mult = tp1_cache[intent_list[row_i]]
        bar_t = bars[p]
        future = bars[p + 1 : p + 1 + max_forward]
        entry_ts = ts_by_pos[p]

        for direction in ("long", "short"):
            is_long = direction == "long"
            for geom in SL_GEOMETRIES:
                if geom == SL_GEOM_DISP_BAR:
                    # Bar t acts as the displacement candle: the same construction
                    # `build_trade` uses, with this bar standing in for the one a CRT
                    # sequence would have supplied.
                    sl = (bar_t.low - sl_atr_buffer * atr_abs) if is_long else (
                        bar_t.high + sl_atr_buffer * atr_abs)
                else:
                    sl = (entry - fixed_sl_atr_mult * atr_abs) if is_long else (
                        entry + fixed_sl_atr_mult * atr_abs)

                # The engine's inverted-SL guard: it returns None rather than trading.
                if (is_long and sl >= entry) or ((not is_long) and sl <= entry):
                    rejects[f"inverted_sl_{geom}_{direction}"] += 1
                    continue
                risk = abs(entry - sl)
                tp1 = entry + (1 if is_long else -1) * tp1_mult * risk
                tp2 = entry + (1 if is_long else -1) * tp2_mult * risk

                for tie in TIE_BREAKS:
                    o = multi_tp_walk(
                        entry, direction, sl, tp1, tp2, future,
                        partial_fraction=partial_fraction,
                        tie_break=tie,
                        trail_fraction=trail_fraction,
                        max_forward=max_forward,
                        adverse_fill=adverse_fill,
                        entry_index=p,
                    )
                    nights = 0
                    if charge_swap:
                        exit_ts = ts_by_pos[min(p + o.duration_candles, n_raw - 1)]
                        nights = _nights_held(entry_ts, exit_ts)
                        swap_nights[nights] += 1
                    cost_r = cost_model.cost_r(
                        entry, risk, exit_kind=o.exit_kind,
                        direction=direction, nights_held=nights,
                    )
                    y_net = o.rr_gross - cost_r
                    out_rows.append({
                        "_pos": p,
                        "timestamp": entry_ts,
                        "direction": direction,
                        "sl_geom": geom,
                        "tie_break": tie,
                        "intent": intent_list[row_i],
                        "entry": entry,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "risk_distance": risk,
                        "tp1_mult": tp1_mult,
                        "outcome": o.outcome,
                        "exit_kind": o.exit_kind,
                        "y_R_gross": o.rr_gross,
                        "cost_r": round(cost_r, 6),
                        "y_R_net": round(y_net, 6),
                        "y_win": int(y_net > 0),
                        "y_win_gross": int(o.rr_gross > 0),
                        "duration_candles": o.duration_candles,
                        "reached_tp1": int(o.reached_tp1),
                        "bars_to_tp1": o.bars_to_tp1,
                        "mfe": o.mfe,
                        "mae": o.mae,
                        "gapped_stop": int(o.gapped_stop),
                        "nights_held": nights,
                    })

    labels = pd.DataFrame(out_rows)
    stats = {
        "units": len(labels),
        "bars_labelled": labels["_pos"].nunique() if len(labels) else 0,
        "rejects": dict(rejects),
        "elapsed_seconds": round(time.time() - t0, 1),
        "swap_nights_distribution": dict(swap_nights),
    }
    return labels, stats


def _arm_summary(labels: pd.DataFrame) -> dict:
    out = {}
    for (geom, tie, direction), g in labels.groupby(["sl_geom", "tie_break", "direction"]):
        out[f"{geom}|{tie}|{direction}"] = {
            "n": int(len(g)),
            "base_rate_win_net": round(float(g["y_win"].mean()), 4),
            "base_rate_win_gross": round(float(g["y_win_gross"].mean()), 4),
            "mean_R_gross": round(float(g["y_R_gross"].mean()), 4),
            "mean_R_net": round(float(g["y_R_net"].mean()), 4),
            "mean_cost_r": round(float(g["cost_r"].mean()), 4),
            "outcome_mix": {k: int(v) for k, v in g["outcome"].value_counts().items()},
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--matrix-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--max-forward", type=int, default=40)
    ap.add_argument("--limit-bars", type=int, default=None, help="first N matrix rows (smoke)")
    ap.add_argument("--no-adverse-fill", action="store_true",
                    help="perfect stop fills; every stop books exactly -1R (diagnostic only)")
    args = ap.parse_args(argv)

    tag = f"{args.instrument}_{args.timeframe}"
    matrix_dir = Path(args.matrix_dir) if args.matrix_dir else (
        _ROOT / "results" / "research" / "bar_matrix" / tag)
    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT / "results" / "research" / "oracle_labels" / tag)
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix_csv = matrix_dir / "bar_matrix.csv"
    if not matrix_csv.exists():
        print(f"[FATAL] bar matrix not found: {matrix_csv}\n"
              f"        run scripts/research/build_bar_matrix.py first")
        return 2
    bm_manifest = json.loads((matrix_dir / "manifest.json").read_text(encoding="utf-8"))

    matrix = pd.read_csv(matrix_csv, parse_dates=["timestamp"])
    if args.limit_bars:
        matrix = matrix.head(args.limit_bars)
    raw = pd.read_csv(Path(bm_manifest["corpus_path"]), parse_dates=["timestamp"])
    raw["_pos"] = range(len(raw))

    crt_cfg = get_prod_section("crt_engine")
    ep_cfg = get_prod_section("execution_planner")
    slt_cfg = get_prod_section("sl_tp_comparison")

    manifest_glob = sorted(glob.glob(
        str(_ROOT / "results" / "research" / "xauusd_mt5_cost_calibration"
            / "*manifest_LATEST.json")))
    if not manifest_glob:
        print("[FATAL] no SEM-015 cost manifest found")
        return 2
    cost_manifest_path = manifest_glob[-1]
    cost_model = ComponentCostModel.from_manifest(
        json.loads(Path(cost_manifest_path).read_text(encoding="utf-8")),
        instrument=args.instrument, source=cost_manifest_path,
    )
    adverse = None if args.no_adverse_fill else AdverseFill(
        stop_slippage=cost_model.stop_slippage, model_gaps=True)

    labels, stats = label_corpus(
        matrix, raw,
        cost_model=cost_model,
        adverse_fill=adverse,
        max_forward=args.max_forward,
        sl_atr_buffer=float(crt_cfg["sl_atr_buffer"]),
        tp2_mult=float(crt_cfg["tp2_atr_multiplier"]),
        fixed_sl_atr_mult=float(slt_cfg["legacy_sl_atr_mult"]),
        partial_fraction=float(ep_cfg["partial_tp_fraction"]),
        trail_fraction=0.5,
        crt_cfg=crt_cfg,
    )

    labels.to_csv(out_dir / "labels.csv", index=False)
    arms = _arm_summary(labels)

    # EXECUTION MANIFEST: every declared knob reports whether it actually FIRED, not just
    # its configured value. A declared-but-unreached surface is invisible otherwise, which
    # is the failure class this program exists downstream of.
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "timeframe": args.timeframe,
        "declares": ["SEM-017 exit geometry", "SEM-018 oracle label"],
        "authority": "research_diagnostic_only",
        "economic_claims_allowed": False,
        "bar_matrix_manifest": bm_manifest,
        "geometry": {
            "sl_atr_buffer": float(crt_cfg["sl_atr_buffer"]),
            "tp2_atr_multiplier": float(crt_cfg["tp2_atr_multiplier"]),
            "tp1_multipliers_by_intent": {
                i: _tp1_multiplier(crt_cfg, i) for i in sorted(set(matrix["trade_intent"]))
            },
            "fixed_sl_atr_mult": float(slt_cfg["legacy_sl_atr_mult"]),
            "partial_tp_fraction": float(ep_cfg["partial_tp_fraction"]),
            "trail_fraction": 0.5,
            "max_forward": args.max_forward,
        },
        "cost_model": {
            "id": "CM-XAUUSD-COMPONENT-MEASURED-V1",
            "source": cost_manifest_path.replace("\\", "/"),
            "half_spread": cost_model.half_spread,
            "commission": cost_model.commission,
            "entry_slippage": cost_model.entry_slippage,
            "stop_slippage": cost_model.stop_slippage,
            "entry_slippage_basis": cost_model.entry_slippage_basis,
            "status": cost_model.status,
        },
        "adverse_fill": None if adverse is None else {
            "stop_slippage": adverse.stop_slippage, "model_gaps": adverse.model_gaps},
        "primary_arm": {"sl_geom": PRIMARY_ARM[0], "tie_break": PRIMARY_ARM[1]},
        "stats": stats,
        "arms": arms,
        "execution_evidence": {
            "adverse_fill_gap_events": int(labels["gapped_stop"].sum()),
            "trades_with_swap_nights": int((labels["nights_held"] > 0).sum()),
            "outcome_kinds_seen": sorted(labels["outcome"].unique().tolist()),
            "tie_break_divergence": _tie_break_divergence(labels),
        },
        "caveats": [
            "Labels select bars by their future. Stages 0-3 describe; only an untouched "
            "non-overlapping partition can support a forward claim.",
            "Adjacent labels overlap: effective independent n is about bars/max_forward, "
            "not the row count.",
            "cost_r is cost_price/risk_distance, so the tight-stopped disp_bar arm is far "
            "more cost-dominated than fixed_atr. Gross is carried on every row for this reason.",
            "nights_held counts stamped date boundaries as a declared proxy; the broker's "
            "true rollover hour is not recorded in this repository.",
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print(f"\n  labels -> {out_dir / 'labels.csv'}")
    print(f"  {stats['units']} units over {stats['bars_labelled']} bars "
          f"in {stats['elapsed_seconds']}s | rejects {stats['rejects']}")
    print(f"  gap fills {manifest['execution_evidence']['adverse_fill_gap_events']} | "
          f"swap-night trades {manifest['execution_evidence']['trades_with_swap_nights']}")
    print(f"  tie-break divergence: {manifest['execution_evidence']['tie_break_divergence']}")
    print("\n  ARM SUMMARY (base rates are what any pattern must beat)")
    for k in sorted(arms):
        a = arms[k]
        print(f"   {k:34s} n={a['n']:6d}  win_net={a['base_rate_win_net']:.3f}  "
              f"E_net={a['mean_R_net']:+.4f}R  E_gross={a['mean_R_gross']:+.4f}R  "
              f"cost={a['mean_cost_r']:.4f}R")
    return 0


def _tie_break_divergence(labels: pd.DataFrame) -> dict:
    """How often the two same-bar conventions actually disagree, and by how much.

    SEM-017's epistemic block asks exactly this question; answering it from the real
    corpus is what turns its candidate hypotheses into measured statements.
    """
    key = ["_pos", "direction", "sl_geom"]
    prod = labels[labels["tie_break"] == TIE_BREAK_PRODUCTION].set_index(key)
    opt = labels[labels["tie_break"] == TIE_BREAK_OPTIMISTIC].set_index(key)
    common = prod.index.intersection(opt.index)
    if len(common) == 0:
        return {"compared": 0}
    p, o = prod.loc[common], opt.loc[common]
    differ = (p["outcome"].values != o["outcome"].values)
    gap = (o["y_R_gross"].values - p["y_R_gross"].values)
    return {
        "compared": int(len(common)),
        "differing": int(differ.sum()),
        "differing_pct": round(100.0 * float(differ.mean()), 3),
        "mean_R_gap_all": round(float(gap.mean()), 5),
        "mean_R_gap_differing": round(float(gap[differ].mean()), 5) if differ.any() else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
