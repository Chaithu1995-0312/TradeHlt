#!/usr/bin/env python3
"""Daily market structure analysis for crypto (BTC/ETH) using opportunity logs."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import pandas as pd

def load_opportunities(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)

def analyse_daily(log_path: Path, output_csv: Path = None):
    daily = defaultdict(lambda: {
        "date": None,
        "long": 0, "short": 0,
        "tp_hits": 0, "sl_hits": 0, "timeouts": 0,
        "sum_rr": 0.0,
        "sweep": 0,
        "double_sweep": 0,
        "displacement": 0,      # disp_strength > 0.8
        "retest_depth_sum": 0.0,
        "retest_count": 0,
        "regime_sum": 0.0,
        "volatility_ratio_sum": 0.0,
        "trend_bias_sum": 0.0
    })

    for rec in load_opportunities(log_path):
        ts = datetime.fromisoformat(rec["timestamp"])
        date = ts.date()
        d = daily[date]
        d["date"] = date
        d["long" if rec["direction"] == "long" else "short"] += 1
        outcome = rec["outcome"]
        if outcome == "TP_HIT":
            d["tp_hits"] += 1
        elif outcome == "SL_HIT":
            d["sl_hits"] += 1
        else:
            d["timeouts"] += 1
        d["sum_rr"] += rec["rr_achieved"]

        feats = rec.get("features", {})
        if feats:
            if feats.get("sweep_detected", 0) > 0:
                d["sweep"] += 1
            if feats.get("double_sweep", 0) > 0:
                d["double_sweep"] += 1
            if feats.get("disp_strength", 0) > 0.8:
                d["displacement"] += 1
            retest = feats.get("retest_depth", 0)
            if retest > 0:
                d["retest_depth_sum"] += retest
                d["retest_count"] += 1
            d["regime_sum"] += feats.get("volatility_regime", 0)
            d["volatility_ratio_sum"] += feats.get("volatility_ratio", 0)
            d["trend_bias_sum"] += feats.get("trend_bias", 0)

    rows = []
    for date, d in sorted(daily.items()):
        total = d["long"] + d["short"]
        wins = d["tp_hits"]
        losses = d["sl_hits"]
        win_rate = wins / (wins + losses) if (wins+losses) > 0 else 0
        avg_rr = d["sum_rr"] / total if total > 0 else 0
        retest_avg = d["retest_depth_sum"] / d["retest_count"] if d["retest_count"] > 0 else 0
        regime_avg = d["regime_sum"] / total if total > 0 else 0
        vol_avg = d["volatility_ratio_sum"] / total if total > 0 else 0
        trend_avg = d["trend_bias_sum"] / total if total > 0 else 0

        rows.append({
            "date": date,
            "total_opps": total,
            "long": d["long"],
            "short": d["short"],
            "win_rate": round(win_rate, 3),
            "avg_rr": round(avg_rr, 3),
            "tp_hits": wins,
            "sl_hits": losses,
            "timeouts": d["timeouts"],
            "sweep_count": d["sweep"],
            "double_sweep": d["double_sweep"],
            "displacement_count": d["displacement"],
            "retest_avg_depth": round(retest_avg, 4),
            "avg_regime": round(regime_avg, 2),
            "avg_volatility_ratio": round(vol_avg, 3),
            "avg_trend_bias": round(trend_avg, 3)
        })
    df = pd.DataFrame(rows)
    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"Saved {len(df)} days to {output_csv}")
    return df

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--output", default="btc_daily_structure.csv")
    args = ap.parse_args()
    analyse_daily(Path(args.log), Path(args.output))