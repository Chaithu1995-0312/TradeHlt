#!/usr/bin/env python
"""sweep_structure_economic_probe.py — does the TT/FF structural gap survive real costs?

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim of promotion.

WHY THIS EXISTS
---------------
The prior TT/FF comparison measured uncapped, direction-normalized EXCURSION (how far price
reached), not a realized trading object. "TT median +0.55 ATR better than FF" answers "how far
did price travel"; it does not answer "could a trader have captured it after costs." This probe
builds the economic object: hold from next-bar-open to a fixed horizon (H=20/40/80), no SL/TP,
close out at the horizon, net the REAL measured broker cost.

THE OBJECT
----------
Per SWEEP decision, per horizon H:
    entry     = open[bar_index+1]                         (matches every prior probe's convention)
    exit      = close[bar_index+H]                         (direction-normalized: hold to H, no TP/SL)
    gross_R   = direction_sign * (exit - entry) / live_atr  (ATR-normalized, the basis used
                                                              throughout this investigation)
    cost_R    = ComponentCostModel.cost_r(..., exit_kind="TIMEOUT", nights_held=0) / live_atr
    net_R     = gross_R - cost_R
`live_atr` is `engine.live_context.live_atr` at the DECISION bar (envelope_bar.parquet),
matching every prior excursion computation in this investigation -- never the canonical
close-relative `atr` (the F-072 trap, verified against source repeatedly this session).

COST MODEL: SEM-015 `research.costs.ComponentCostModel`, built from the MEASURED
xauusd_mt5_cost_calibration manifest (half_spread=$0.045, commission=$0.04, entry_slippage
PROXY_FROM_STOP=$0.09 [no MARKET fills were captured historically, F-082], stop_slippage=$0.09).
`exit_kind="TIMEOUT"` because this object holds to a fixed horizon with NO stop or take-profit
order at all -- `_STOP_EXITS` never fires, so the model correctly charges only spread+commission
on the exit leg, not stop slippage (which would misrepresent an order type that never existed
in this object).

SWAP EXCLUDED BY DESIGN (nights_held=0 always), not by omission. The calibration's swap sidecar
IS measured (long -$0.56/oz/night debit, short +$0.38/oz/night credit) and horizons up to 80
bars (20h M15) can span a broker rollover. F-034 (this repo's own finding) is explicit that
carry is a SEPARATE payoff from directional edge and must not be netted into it ("letting
overnight financing subsidise a losing entry conflates two different payoffs"). Rather than
approximate rollover-crossing timing (a new source of error for a small, separate-payoff cost),
this probe states the scope limitation plainly: net_R here is directional cost only, and may
UNDERSTATE true cost for LONG positions whose horizon crosses a rollover (the model itself
never nets in the SHORT credit either, per the same F-034 discipline -- so this is a one-sided,
conservative-in-one-direction omission, not a two-sided cancellation).

REUSE. `ComponentCostModel` from `research.costs` (SEM-015, unmodified). Corpus loading from
`p001_excursion_probe.load_corpus`. MFE_R/MAE_R (uncapped direction-normalized excursion) are
NOT recomputed -- they already exist per decision per horizon in `excursion.parquet` as
`fav_exc`/`adv_exc`; this probe reads them rather than re-deriving them a second way.

USAGE
    venv/Scripts/python.exe scripts/analysis/sweep_structure_economic_probe.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from research.costs import ComponentCostModel, UnmeasuredCostError  # noqa: E402

_P001 = ROOT / "scripts" / "analysis" / "p001_excursion_probe.py"
_spec = importlib.util.spec_from_file_location("p001_excursion_probe", _P001)
p001 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p001)

HORIZONS = (20, 40, 80)
MANIFEST_PATH = (
    ROOT / "results/research/xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)


def load_cost_model() -> ComponentCostModel:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return ComponentCostModel.from_manifest(
        manifest, instrument="XAUUSD", source=f"{MANIFEST_PATH.name}",
    )


def close_at_horizon(corpus: list[dict], bar_index: int, direction: str, atr: float,
                     horizon: int) -> Optional[float]:
    """gross_R for a hold-to-horizon, no-TP/SL object. None if the window is truncated."""
    future = corpus[bar_index + 1: bar_index + 1 + horizon]
    if len(future) < horizon:
        return None
    entry = corpus[bar_index + 1]["open"]
    exit_price = future[-1]["close"]
    sign = 1.0 if direction == "LONG" else -1.0
    return sign * (exit_price - entry) / atr


def cell(r: dict) -> str:
    return ("T" if r["breaker_present"] else "F") + ("T" if r["ob_present"] else "F")


def pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas_full")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--out", default="results/decision_atlas_full/sweep_structure_economic_probe.json")
    args = ap.parse_args()

    try:
        cost_model = load_cost_model()
    except UnmeasuredCostError as exc:
        print(f"FATAL: cost calibration not usable -- {exc}")
        return 1
    print(f"cost model provenance: {json.dumps(cost_model.provenance(), indent=2)}")

    import pyarrow.parquet as pq
    atlas = Path(ROOT / args.atlas)
    lf = pq.read_table(atlas / "sweep_liquidity_fact.parquet").to_pylist()
    dec_by_id = {d["decision_id"]: d for d in pq.read_table(atlas / "transition_decision.parquet").to_pylist()}
    atr_by_bar = {b["bar_index"]: b["live_atr"] for b in pq.read_table(atlas / "envelope_bar.parquet").to_pylist()}
    exc_by_dh = {(e["decision_id"], e["horizon"]): e
                 for e in pq.read_table(atlas / "excursion.parquet").to_pylist()}
    corpus = p001.load_corpus(ROOT / args.csv)

    for r in lf:
        r["cell"] = cell(r)
        r["direction"] = dec_by_id[r["decision_id"]]["direction"]

    results: dict[str, dict] = {}
    for H in HORIZONS:
        by_cell: dict[str, list[dict]] = {}
        for r in lf:
            atr = atr_by_bar.get(r["bar_index"])
            if not atr:
                continue
            gross = close_at_horizon(corpus, r["bar_index"], r["direction"], atr, H)
            if gross is None:
                continue
            direction = "long" if r["direction"] == "LONG" else "short"
            cost_price = cost_model.cost_price(exit_kind="TIMEOUT", direction=direction, nights_held=0)
            cost_r = cost_price / atr
            net = gross - cost_r
            exc = exc_by_dh.get((r["decision_id"], H)) or {}
            by_cell.setdefault(r["cell"], []).append({
                "gross_R": gross, "cost_R": cost_r, "net_R": net,
                "mfe_R": exc.get("fav_exc"), "mae_R": exc.get("adv_exc"),
                "cost_over_atr": cost_r,  # same value; ATR is the normalizer, named for clarity
            })
        cellsum = {}
        for cname, rows in by_cell.items():
            gross = [x["gross_R"] for x in rows]
            net = [x["net_R"] for x in rows]
            costr = [x["cost_R"] for x in rows]
            mfe = [x["mfe_R"] for x in rows if x["mfe_R"] is not None]
            mae = [x["mae_R"] for x in rows if x["mae_R"] is not None]
            cellsum[cname] = {
                "n": len(rows),
                "gross_mean": round(st.mean(gross), 4), "gross_median": round(st.median(gross), 4),
                "gross_p75": round(pct(gross, 75), 4), "gross_p90": round(pct(gross, 90), 4),
                "net_mean": round(st.mean(net), 4), "net_median": round(st.median(net), 4),
                "net_p75": round(pct(net, 75), 4), "net_p90": round(pct(net, 90), 4),
                "cost_R_mean": round(st.mean(costr), 4), "cost_R_median": round(st.median(costr), 4),
                "mfe_R_median": round(st.median(mfe), 4) if mfe else None,
                "mae_R_median": round(st.median(mae), 4) if mae else None,
                "win_rate_net": round(sum(1 for x in net if x > 0) / len(net), 4),
            }
        results[f"H{H}"] = cellsum

    artifact = {
        "probe_id": "SWEEP-STRUCTURE-ECON-01",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "cost_model_provenance": cost_model.provenance(),
        "swap_excluded_note": (
            "nights_held=0 always -- swap/carry excluded by design per F-034 (separate payoff "
            "from directional edge), not by omission. May understate cost for LONG positions "
            "whose horizon crosses a rollover boundary."
        ),
        "object_note": (
            "Hold from next-bar open to fixed horizon close, no SL/TP. gross_R/net_R are NOT "
            "the same object as mfe_R/adv_R (uncapped max excursion) -- reported side by side, "
            "never conflated."
        ),
        "results": results,
    }
    p001.assert_no_claim_keys(artifact)

    out = ROOT / args.out
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for H in HORIZONS:
        print(f"\n=== H={H} ===")
        print(f"{'cell':6s} {'n':>5s} {'gross_med':>10s} {'net_med':>9s} {'net_p75':>8s} "
              f"{'net_p90':>8s} {'cost_R':>8s} {'win%':>6s} {'mfe_med':>8s} {'mae_med':>8s}")
        for cname in ("FF", "TF", "FT", "TT"):
            c = results[f"H{H}"].get(cname)
            if not c:
                continue
            print(f"{cname:6s} {c['n']:5d} {c['gross_median']:10.4f} {c['net_median']:9.4f} "
                  f"{c['net_p75']:8.4f} {c['net_p90']:8.4f} {c['cost_R_median']:8.4f} "
                  f"{100*c['win_rate_net']:6.1f} {c['mfe_R_median'] or 0:8.4f} "
                  f"{c['mae_R_median'] or 0:8.4f}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
