"""Retrospective specimen: Run1 CRT path replay under declared schema (READ-ONLY measurement)."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"D:\Tradelatest")
TRADES = ROOT / "results" / "run_20260916_225925_XAUUSD" / "XAUUSD_trades.csv"
CORPUS = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
OUT = ROOT / "multi_llm" / "bridge_layer" / "retrospective_profit_window_CRT0003_intrabar_fixed.json"
CONFIG_ID = "v2_htfcrt_2026_08"
COST_MODEL_RUN1 = "backtest_g1g2_v2"  # as stamped on Run1 trades
FLAT_BPS = 12.0


@dataclass
class Bar:
    index: int
    timestamp: str
    open: float
    high: float
    low: float
    close: float


def load_bars():
    bars = []
    with CORPUS.open(newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            bars.append(
                Bar(
                    i,
                    row["timestamp"],
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                )
            )
    return bars


def load_trades():
    with TRADES.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def intrabar_fixed_walk(direction: str, entry: float, sl: float, tp: float, future_bars, max_forward=40):
    """Mirror forward_walk exit_model=intrabar_fixed (fixed SL/TP, wick touch, SL-before-TP)."""
    direction = direction.lower()
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError("non-positive risk")
    for i, bar in enumerate(future_bars[:max_forward]):
        high, low = bar.high, bar.low
        if direction == "long":
            sl_hit = low <= sl
            tp_hit = high >= tp
        else:
            sl_hit = high >= sl
            tp_hit = low <= tp
        if sl_hit and tp_hit:
            # conservative: SL wins
            fill = sl
            rr = ((fill - entry) if direction == "long" else (entry - fill)) / risk
            return {
                "path_outcome": "SL",
                "barrier_first": "SL_TIEBREAK",
                "bars_held": i + 1,
                "exit_bar_idx": bar.index,
                "exit_ts": bar.timestamp,
                "exit_price": fill,
                "gross_R": rr,
                "mfe_price": (high - entry) if direction == "long" else (entry - low),
            }
        if sl_hit:
            fill = sl
            rr = ((fill - entry) if direction == "long" else (entry - fill)) / risk
            return {
                "path_outcome": "SL",
                "barrier_first": "SL",
                "bars_held": i + 1,
                "exit_bar_idx": bar.index,
                "exit_ts": bar.timestamp,
                "exit_price": fill,
                "gross_R": rr,
            }
        if tp_hit:
            fill = tp
            rr = ((fill - entry) if direction == "long" else (entry - fill)) / risk
            return {
                "path_outcome": "TP",
                "barrier_first": "TP",
                "bars_held": i + 1,
                "exit_bar_idx": bar.index,
                "exit_ts": bar.timestamp,
                "exit_price": fill,
                "gross_R": rr,
            }
    last = future_bars[min(len(future_bars), max_forward) - 1] if future_bars else None
    if last is None:
        return {"path_outcome": "NO_BARS", "bars_held": 0, "gross_R": 0.0}
    # timeout at close
    close = last.close
    rr = ((close - entry) if direction == "long" else (entry - close)) / risk
    return {
        "path_outcome": "TIMEOUT",
        "barrier_first": "NONE",
        "bars_held": min(len(future_bars), max_forward),
        "exit_bar_idx": last.index,
        "exit_ts": last.timestamp,
        "exit_price": close,
        "gross_R": rr,
    }


def flat12_cost_r(entry: float, risk: float) -> float:
    return ((FLAT_BPS / 10_000.0) * entry) / risk


def main():
    bars = load_bars()
    by_ts = {b.timestamp: b for b in bars}
    trades = load_trades()
    results = []

    for t in trades:
        tid = t["trade_id"]
        direction = t["direction"]
        entry = float(t["entry_raw"])
        sl = float(t["sl"])
        tp1 = float(t["tp1"])
        tp2 = float(t["tp2"])
        opened = t["opened_at"].replace("T", " ")
        # normalize
        if len(opened) == 19:
            pass
        birth = by_ts.get(opened)
        if birth is None:
            # try without seconds variants
            results.append({"trade_id": tid, "error": f"birth ts not found: {opened}"})
            continue

        future = [b for b in bars if b.index > birth.index]
        risk = abs(entry - sl)

        # Entry-bar forensic (NOT part of forward_walk authority; reported separately)
        if direction.upper() == "LONG":
            entry_sl = birth.low <= sl
            entry_tp1 = birth.high >= tp1
            entry_tp2 = birth.high >= tp2
        else:
            entry_sl = birth.high >= sl
            entry_tp1 = birth.low <= tp1
            entry_tp2 = birth.low <= tp2

        walks = {}
        for label, tp in (("tp1", tp1), ("tp2", tp2)):
            w = intrabar_fixed_walk(direction, entry, sl, tp, future)
            cost_flat = flat12_cost_r(entry, risk)
            w = dict(w)
            w["tp_used"] = tp
            w["tp_label"] = label
            w["cost_R_flat_12bps"] = cost_flat
            w["net_R_flat_12bps"] = w["gross_R"] - cost_flat
            walks[label] = w

        results.append(
            {
                "trade_id": tid,
                "direction": direction,
                "entry_raw": entry,
                "entry_fill_run1": float(t["entry_fill"]),
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "risk_distance": risk,
                "birth_bar_idx": birth.index,
                "birth_ts": birth.timestamp,
                "birth_ohlc": {
                    "o": birth.open,
                    "h": birth.high,
                    "l": birth.low,
                    "c": birth.close,
                },
                "birth_close_gt_entry": birth.close > entry if direction.upper() == "LONG" else birth.close < entry,
                "entry_bar_forensic_touches": {
                    "sl": entry_sl,
                    "tp1": entry_tp1,
                    "tp2": entry_tp2,
                    "note": "forward_walk excludes entry bar; if entry included, SL-before-TP would apply on simultaneous touch",
                },
                "run1_ledger": {
                    "exit_reason": t["exit_reason"],
                    "opened_at": t["opened_at"],
                    "closed_at": t["closed_at"],
                    "duration_candles": int(float(t["duration_candles"])),
                    "pnl_rr_raw": float(t["pnl_rr_raw"]),
                    "pnl_rr_net": float(t["pnl_rr_net"]),
                    "cost_model_id": t["cost_model_id"],
                    "exit_fill": float(t["exit_fill"]),
                },
                "forward_walk_intrabar_fixed": walks,
            }
        )

    # Pick: prefer TP path with y_R_net > 0 under flat_12bps using tp2 (Run1 exit), else tp1
    pick = None
    for r in results:
        if "error" in r:
            continue
        for label in ("tp2", "tp1"):
            w = r["forward_walk_intrabar_fixed"][label]
            if w["path_outcome"] == "TP" and w["net_R_flat_12bps"] > 0:
                pick = (r, label, w)
                break
        if pick:
            break
    # fallback: Run1 ledger net > 0
    if pick is None:
        for r in results:
            if r.get("run1_ledger", {}).get("pnl_rr_net", -999) > 0:
                pick = (r, "tp2", r["forward_walk_intrabar_fixed"]["tp2"])
                break

    chosen, tp_label, walk = pick
    # hold window: birth -> exit inclusive
    start_idx = chosen["birth_bar_idx"]
    end_idx = walk["exit_bar_idx"]
    window_bars = [b for b in bars if start_idx <= b.index <= end_idx]

    # optional capital stamp (INR) — informational only; PnL reported in R
    capital = {
        "currency": "INR",
        "total_capital_inr": 100000,
        "per_trade_investment_inr": 10000,
        "sizing_mode": "fixed_investment_inr",
        "note": "Capital stamp from config capital_management; specimen PnL is in R-net, not currency",
    }

    artifact = {
        "artifact_type": "retrospective_specimen_measurement_pick",
        "economic_claims_allowed": False,
        "disclaimer": (
            "RETROSPECTIVE SPECIMEN / MEASUREMENT PICK ONLY. "
            "No edge claim. Not a live order recommendation. "
            "Not trading education. economic_claims_allowed remains false."
        ),
        "approach": "A_replay_known_Run1_trades",
        "active_config": CONFIG_ID,
        "geometry_source": "Run1 opportunity geometry (XAUUSD_trades.csv CRT build_trade levels)",
        "exit_family": "intrabar_fixed_sl_tp",
        "exit_authority": "forward_walk.exit_model=intrabar_fixed (oracle / MC-JOINT)",
        "modifications": [
            "use tp2 as single TP for research single-TP contract (Run1 exit_reason=TP2); tp1 also walked for comparison"
        ],
        "cost_models_reported": {
            "primary_research_flat": {
                "cost_model_id": "flat_12bps",
                "round_trip_bps": FLAT_BPS,
                "source": "src/research/costs.py DEFAULT_COST_MODEL",
            },
            "run1_ledger": {
                "cost_model_id": COST_MODEL_RUN1,
                "source": "results/run_20260916_225925_XAUUSD/XAUUSD_trades.csv stamped field",
            },
        },
        "picked_trade_id": chosen["trade_id"],
        "time_range": {
            "start_ts": chosen["birth_ts"],
            "end_ts": walk["exit_ts"],
            "start_bar_idx": start_idx,
            "end_bar_idx": end_idx,
            "bars_held_post_entry": walk["bars_held"],
            "inclusive": True,
        },
        "placement": {
            "direction": chosen["direction"],
            "entry": chosen["entry_raw"],
            "sl": chosen["sl"],
            "tp": walk["tp_used"],
            "tp_label": tp_label,
            "tp1_also": chosen["tp1"],
            "tp2_schema": chosen["tp2"],
            "source": "Run1 CRT-0003 trades.csv geometry (entry=retest close; SL/TP from crt_engine v2_htfcrt_2026_08)",
        },
        "path": {
            "barrier_hit_first": walk["barrier_first"],
            "path_outcome": walk["path_outcome"],
            "bars_held": walk["bars_held"],
            "gross_R": round(walk["gross_R"], 6),
            "cost_R_flat_12bps": round(walk["cost_R_flat_12bps"], 6),
            "net_R_flat_12bps": round(walk["net_R_flat_12bps"], 6),
            "run1_ledger_gross_R": chosen["run1_ledger"]["pnl_rr_raw"],
            "run1_ledger_net_R": chosen["run1_ledger"]["pnl_rr_net"],
            "run1_ledger_cost_model_id": chosen["run1_ledger"]["cost_model_id"],
            "pnl_unit": "R",
        },
        "birth_note": {
            "birth_close_gt_entry": chosen["birth_close_gt_entry"],
            "birth_ohlc": chosen["birth_ohlc"],
            "entry_bar_forensic_touches": chosen["entry_bar_forensic_touches"],
            "path_authority": "forward_walk excludes birth/entry bar; first evaluated bar is birth_idx+1",
        },
        "capital_stamp_optional": capital,
        "all_run1_replay": results,
        "window_bars": [
            {
                "bar_idx": b.index,
                "timestamp": b.timestamp,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
            }
            for b in window_bars
        ],
        "sources": {
            "trades": str(TRADES),
            "corpus": str(CORPUS),
            "forward_walk": "src/research/measurement/forward_walk.py",
            "costs": "src/research/costs.py",
            "config": f"configs/production/{CONFIG_ID}.json",
            "run_folder": "results/run_20260916_225925_XAUUSD",
        },
        "generated_at_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S Asia/Calcutta"),
    }

    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT),
        "picked": chosen["trade_id"],
        "range": artifact["time_range"],
        "path": artifact["path"],
        "modifications": artifact["modifications"],
        "summary_table": [
            {
                "id": r["trade_id"],
                "birth_close_gt_entry": r.get("birth_close_gt_entry"),
                "tp1_outcome": r.get("forward_walk_intrabar_fixed", {}).get("tp1", {}).get("path_outcome"),
                "tp1_gross": r.get("forward_walk_intrabar_fixed", {}).get("tp1", {}).get("gross_R"),
                "tp1_net_flat12": r.get("forward_walk_intrabar_fixed", {}).get("tp1", {}).get("net_R_flat_12bps"),
                "tp2_outcome": r.get("forward_walk_intrabar_fixed", {}).get("tp2", {}).get("path_outcome"),
                "tp2_gross": r.get("forward_walk_intrabar_fixed", {}).get("tp2", {}).get("gross_R"),
                "tp2_net_flat12": r.get("forward_walk_intrabar_fixed", {}).get("tp2", {}).get("net_R_flat_12bps"),
                "run1_net": r.get("run1_ledger", {}).get("pnl_rr_net"),
                "run1_exit": r.get("run1_ledger", {}).get("exit_reason"),
            }
            for r in results if "error" not in r
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
