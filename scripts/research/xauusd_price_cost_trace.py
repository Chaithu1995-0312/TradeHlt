#!/usr/bin/env python3
"""
xauusd_price_cost_trace.py
==========================
Trace **price movement** vs **cost ledger** for XAUUSD economic units.

Reads E0 units + E1 ledger (train geometry available). Builds a cost-decomposition
ledger and a short human report with walk-through case studies.

Cost models compared (pre-registered v1 vs legacy v0):
  * flat 12 bps: cost_R = 0.0012 * entry / risk_distance
  * fixed USD RT 0.40 (v1 primary): cost_R = 0.40 / risk_distance
  * sensitivity: 0.20 / 0.80 USD (diagnostic)

Authority: RESEARCH_ONLY — observation of geometry, not economic promote.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from research.xau_metals_protocol import (  # noqa: E402
    cost_r_fixed_usd,
    cost_r_flat_bps,
    protocol_sha256,
)


def _sha(p: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _stats(xs: list[float]) -> dict:
    a = np.asarray(xs, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "p50": float(np.median(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
        "min": float(a.min()),
        "max": float(a.max()),
    }


def load_units_ledger(
    units_path: Path, ledger_path: Path
) -> tuple[list[dict], list[dict]]:
    units = {}
    for line in units_path.open(encoding="utf-8"):
        u = json.loads(line)
        units[(u["timestamp"], u["direction"])] = u
    rows = []
    for line in ledger_path.open(encoding="utf-8"):
        r = json.loads(line)
        u = units.get((r["timestamp"], r["direction"]), {})
        entry = u.get("train_entry")
        atr = u.get("train_atr_abs")
        if entry is None or atr is None or float(atr) <= 0:
            continue  # OOS without train geometry skipped for decomp
        entry = float(entry)
        atr = float(atr)
        sl = float(u.get("train_sl_atr_mult") or 1.0)
        tp = float(u.get("train_tp_atr_mult") or 1.0)
        risk = sl * atr
        gross = float(r["gross_rr"])
        direction = r["direction"]
        if direction == "long":
            sl_px, tp_px = entry - risk, entry + risk
        else:
            sl_px, tp_px = entry + risk, entry - risk
        c12 = cost_r_flat_bps(entry, atr, sl_atr_mult=sl, round_trip_bps=12.0)
        c20 = cost_r_fixed_usd(entry, atr, sl_atr_mult=sl, usd_round_trip=0.20)
        c40 = cost_r_fixed_usd(entry, atr, sl_atr_mult=sl, usd_round_trip=0.40)
        c80 = cost_r_fixed_usd(entry, atr, sl_atr_mult=sl, usd_round_trip=0.80)
        rows.append(
            {
                "timestamp": r["timestamp"],
                "split": r["split"],
                "direction": direction,
                "exit_reason": r.get("exit_reason"),
                "score": r.get("score"),
                "bar_index": r.get("bar_index"),
                "entry": entry,
                "atr_abs": atr,
                "sl_atr_mult": sl,
                "tp_atr_mult": tp,
                "risk_distance_usd": risk,
                "sl_price": sl_px,
                "tp_price": tp_px,
                "gross_rr": gross,
                "price_move_usd": gross * risk,
                "cost_usd_12bps": (12.0 / 10_000.0) * entry,
                "cost_usd_fixed_0p40": 0.40,
                "cost_r_12bps": c12,
                "cost_r_usd0p20": c20,
                "cost_r_usd0p40": c40,
                "cost_r_usd0p80": c80,
                "net_r_12bps": gross - c12,
                "net_r_usd0p20": gross - c20,
                "net_r_usd0p40": gross - c40,
                "net_r_usd0p80": gross - c80,
                "ledger_net_rr_v0": float(r["net_rr"]),
            }
        )
    return list(units.values()), rows


def case_walk(ts: str, direction: str, entry: float, atr: float) -> dict:
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk

    path = guard_xauusd_csv_path("data/mt5/XAUUSD_M15.csv", "XAUUSD")
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    ts_p = pd.Timestamp(ts)
    matches = df.index[df["timestamp"] == ts_p].tolist()
    if not matches:
        return {"error": f"ts not found {ts}"}
    idx = int(matches[0])

    class Bar:
        def __init__(self, i: int, row: Any):
            self.index = i
            self.timestamp = row["timestamp"].to_pydatetime()
            self.open = float(row["open"])
            self.high = float(row["high"])
            self.low = float(row["low"])
            self.close = float(row["close"])

    bars = [Bar(i, df.iloc[i]) for i in range(len(df))]
    risk = atr
    if direction == "long":
        sl_px, tp_px = entry - risk, entry + risk
    else:
        sl_px, tp_px = entry + risk, entry - risk
    sig = Signal(
        instrument="XAUUSD",
        timestamp=bars[idx].timestamp,
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=1.0,
        tp_atr_mult=1.0,
        atr=atr,
        meta={},
    )
    out = forward_walk(
        sig, bars[idx + 1 :], max_forward=40, exit_model="intrabar_fixed"
    )
    path_bars = []
    for j, b in enumerate(bars[idx + 1 : idx + 1 + max(out.duration_candles, 1)]):
        path_bars.append(
            {
                "offset": j + 1,
                "timestamp": str(b.timestamp),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
            }
        )
        if j + 1 >= out.duration_candles:
            break
    c12 = cost_r_flat_bps(entry, atr, sl_atr_mult=1.0, round_trip_bps=12.0)
    c40 = cost_r_fixed_usd(entry, atr, sl_atr_mult=1.0, usd_round_trip=0.40)
    return {
        "timestamp": ts,
        "direction": direction,
        "entry": entry,
        "atr_abs": atr,
        "risk_distance_usd": risk,
        "sl_price": sl_px,
        "tp_price": tp_px,
        "outcome": out.outcome,
        "gross_rr": out.rr_achieved,
        "duration_candles": out.duration_candles,
        "mfe_usd": out.mfe,
        "mae_usd": out.mae,
        "price_move_usd": out.rr_achieved * risk,
        "cost_usd_12bps": (12.0 / 10_000.0) * entry,
        "cost_usd_fixed_0p40": 0.40,
        "cost_r_12bps": c12,
        "cost_r_usd0p40": c40,
        "net_r_12bps": out.rr_achieved - c12,
        "net_r_usd0p40": out.rr_achieved - c40,
        "path": path_bars,
    }


def main() -> int:
    units_path = ROOT / "results/gaussian_xauusd_econ/units_LATEST.jsonl"
    ledger_path = ROOT / "results/gaussian_xauusd_econ/ledger_LATEST.jsonl"
    out_dir = ROOT / "results/gaussian_xauusd_econ/price_cost_trace"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not units_path.exists() or not ledger_path.exists():
        print("ERROR: need E0 units + E1 ledger", file=sys.stderr)
        return 2

    _, rows = load_units_ledger(units_path, ledger_path)
    print(f"n_rows_with_geometry={len(rows)} (train LABEL_ACCEPTED)")

    tp = [r for r in rows if r["exit_reason"] == "TP_HIT"]
    sl = [r for r in rows if r["exit_reason"] == "SL_HIT"]

    summary = {
        "title": "XAUUSD price movement vs cost ledger trace",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "authority": "RESEARCH_ONLY — geometry/cost decomposition; not economic promote",
        "n_units": len(rows),
        "exit_counts": dict(Counter(r["exit_reason"] for r in rows)),
        "price": {
            "risk_distance_usd": _stats([r["risk_distance_usd"] for r in rows]),
            "price_move_usd": _stats([r["price_move_usd"] for r in rows]),
            "gross_rr": _stats([r["gross_rr"] for r in rows]),
        },
        "cost_r": {
            "flat_12bps": {
                **_stats([r["cost_r_12bps"] for r in rows]),
                "frac_gt_1": float(np.mean([r["cost_r_12bps"] > 1 for r in rows])),
            },
            "usd_0p20": {
                **_stats([r["cost_r_usd0p20"] for r in rows]),
                "frac_gt_1": float(np.mean([r["cost_r_usd0p20"] > 1 for r in rows])),
            },
            "usd_0p40_v1_primary": {
                **_stats([r["cost_r_usd0p40"] for r in rows]),
                "frac_gt_1": float(np.mean([r["cost_r_usd0p40"] > 1 for r in rows])),
            },
            "usd_0p80": {
                **_stats([r["cost_r_usd0p80"] for r in rows]),
                "frac_gt_1": float(np.mean([r["cost_r_usd0p80"] > 1 for r in rows])),
            },
        },
        "net_r": {
            "v0_12bps": _stats([r["net_r_12bps"] for r in rows]),
            "v1_usd0p40": _stats([r["net_r_usd0p40"] for r in rows]),
        },
        "tp_hit": {
            "n": len(tp),
            "mean_price_move_usd": float(np.mean([r["price_move_usd"] for r in tp]))
            if tp
            else None,
            "frac_net_neg_12bps": float(np.mean([r["net_r_12bps"] < 0 for r in tp]))
            if tp
            else None,
            "frac_net_neg_usd0p40": float(np.mean([r["net_r_usd0p40"] < 0 for r in tp]))
            if tp
            else None,
        },
        "sl_hit": {
            "n": len(sl),
            "mean_price_move_usd": float(np.mean([r["price_move_usd"] for r in sl]))
            if sl
            else None,
        },
        "identity": {
            "ledger_net_matches_12bps_recompute": bool(
                np.allclose(
                    [r["ledger_net_rr_v0"] for r in rows],
                    [r["net_r_12bps"] for r in rows],
                    rtol=0,
                    atol=1e-9,
                )
            )
        },
        "protocol_v1_sha256": protocol_sha256(),
        "inputs": {
            "units": str(units_path).replace("\\", "/"),
            "units_sha256": _sha(units_path),
            "ledger": str(ledger_path).replace("\\", "/"),
            "ledger_sha256": _sha(ledger_path),
        },
    }

    # Case studies: worst 12bps TP, median TP, one SL
    worst_tp = min(tp, key=lambda r: r["net_r_12bps"]) if tp else None
    mid_tp = sorted(tp, key=lambda r: r["atr_abs"])[len(tp) // 2] if tp else None
    one_sl = sl[0] if sl else None
    cases = []
    for label, r in (
        ("worst_tp_under_12bps", worst_tp),
        ("median_atr_tp", mid_tp),
        ("example_sl", one_sl),
    ):
        if r is None:
            continue
        walk = case_walk(r["timestamp"], r["direction"], r["entry"], r["atr_abs"])
        walk["case_id"] = label
        cases.append(walk)

    summary = {**summary, "case_studies": cases}

    # Write cost ledger CSV/JSONL
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cost_jsonl = out_dir / f"cost_ledger_{ts}.jsonl"
    with cost_jsonl.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    latest = out_dir / "cost_ledger_LATEST.jsonl"
    latest.write_text(cost_jsonl.read_text(encoding="utf-8"), encoding="utf-8")

    # CSV for spreadsheet
    cost_csv = out_dir / f"cost_ledger_{ts}.csv"
    pd.DataFrame(rows).to_csv(cost_csv, index=False)

    man_path = out_dir / f"price_cost_trace_manifest_{ts}.json"
    latest_man = out_dir / "price_cost_trace_LATEST.json"
    summary["outputs"] = {
        "cost_ledger_jsonl": str(cost_jsonl).replace("\\", "/"),
        "cost_ledger_csv": str(cost_csv).replace("\\", "/"),
        "cost_ledger_sha256": _sha(cost_jsonl),
    }
    for p in (man_path, latest_man):
        p.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # Human markdown report
    md = out_dir / "PRICE_COST_TRACE.md"
    md.write_text(_render_md(summary, cases), encoding="utf-8")

    print("--- PRICE / COST TRACE DONE ---")
    print(f"n={len(rows)} TP={len(tp)} SL={len(sl)}")
    print(
        f"mean gross_R={summary['price']['gross_rr']['mean']:.4f} "
        f"mean net_12bps={summary['net_r']['v0_12bps']['mean']:.4f} "
        f"mean net_usd0.40={summary['net_r']['v1_usd0p40']['mean']:.4f}"
    )
    print(
        f"TP frac net<0: 12bps={summary['tp_hit']['frac_net_neg_12bps']:.3f} "
        f"usd0.40={summary['tp_hit']['frac_net_neg_usd0p40']:.3f}"
    )
    print(f"ledger: {cost_jsonl}")
    print(f"report: {md}")
    return 0


def _render_md(summary: dict, cases: list[dict]) -> str:
    lines = [
        "# XAUUSD — Price movement & cost ledger trace",
        "",
        f"**Generated:** {summary['timestamp_utc']}",
        f"**Authority:** {summary['authority']}",
        "",
        "## Identity chain",
        "",
        "```text",
        "entry @ close",
        "  → SL/TP = entry ± 1·ATR  (risk_distance = ATR)",
        "  → forward_walk(intrabar_fixed): first touch SL or TP",
        "  → gross_R ∈ {+1, −1} typically (fixed 1R geometry)",
        "  → price_move_usd = gross_R × risk_distance",
        "  → cost_R = cost_usd / risk_distance",
        "  → net_R = gross_R − cost_R",
        "```",
        "",
        "## Population (train LABEL_ACCEPTED with geometry)",
        "",
        f"- n = **{summary['n_units']}**",
        f"- exits = `{summary['exit_counts']}`",
        "",
        "### Price",
        "",
        f"- risk_distance (USD): mean **{summary['price']['risk_distance_usd']['mean']:.3f}**, "
        f"p50 **{summary['price']['risk_distance_usd']['p50']:.3f}**",
        f"- price_move_usd: mean **{summary['price']['price_move_usd']['mean']:.3f}**",
        f"- gross_R: mean **{summary['price']['gross_rr']['mean']:.4f}** "
        f"(p50 {summary['price']['gross_rr']['p50']})",
        "",
        "### Cost in R units",
        "",
        "| Model | mean cost_R | p50 | frac cost_R>1 |",
        "|---|---:|---:|---:|",
    ]
    for key, label in (
        ("flat_12bps", "v0 flat 12 bps"),
        ("usd_0p40_v1_primary", "v1 fixed $0.40 RT"),
        ("usd_0p20", "sens $0.20 RT"),
        ("usd_0p80", "sens $0.80 RT"),
    ):
        c = summary["cost_r"][key]
        lines.append(
            f"| {label} | {c['mean']:.4f} | {c['p50']:.4f} | {c['frac_gt_1']:.1%} |"
        )
    lines += [
        "",
        "### Net R",
        "",
        f"- **v0 (12 bps):** mean **{summary['net_r']['v0_12bps']['mean']:.4f}**",
        f"- **v1 ($0.40):** mean **{summary['net_r']['v1_usd0p40']['mean']:.4f}**",
        "",
        "### TP_HIT paths",
        "",
        f"- n = {summary['tp_hit']['n']}",
        f"- mean favorable price move ≈ **{summary['tp_hit']['mean_price_move_usd']:.3f} USD**",
        f"- fraction still net-negative under 12 bps: "
        f"**{summary['tp_hit']['frac_net_neg_12bps']:.1%}**",
        f"- fraction net-negative under $0.40: "
        f"**{summary['tp_hit']['frac_net_neg_usd0p40']:.1%}**",
        "",
        "## Case studies (price path)",
        "",
    ]
    for c in cases:
        lines += [
            f"### {c.get('case_id', 'case')}: {c['timestamp']} {c['direction']}",
            "",
            f"- entry **{c['entry']:.2f}** · ATR **{c['atr_abs']:.4f}** · "
            f"SL **{c['sl_price']:.2f}** · TP **{c['tp_price']:.2f}**",
            f"- outcome **{c['outcome']}** in **{c['duration_candles']}** bars · "
            f"gross_R **{c['gross_rr']}** · price_move **{c['price_move_usd']:.4f} USD**",
            f"- cost USD: 12bps=**{c['cost_usd_12bps']:.4f}** vs fixed=**0.40**",
            f"- cost_R: 12bps=**{c['cost_r_12bps']:.4f}** · $0.40=**{c['cost_r_usd0p40']:.4f}**",
            f"- net_R: 12bps=**{c['net_r_12bps']:.4f}** · $0.40=**{c['net_r_usd0p40']:.4f}**",
            "",
            "| +bar | timestamp | O | H | L | C |",
            "|---:|---|---:|---:|---:|---:|",
        ]
        for b in c.get("path") or []:
            lines.append(
                f"| {b['offset']} | {b['timestamp']} | {b['open']:.2f} | "
                f"{b['high']:.2f} | {b['low']:.2f} | {b['close']:.2f} |"
            )
        lines.append("")
    lines += [
        "## Read this correctly",
        "",
        "1. **Price movement** under fixed 1R geometry is mostly ±risk_distance USD.",
        "2. **Cost ledger** converts a dollar (or bps) cost into R by dividing by risk.",
        "3. Under **12 bps on gold**, small ATR ⇒ huge cost_R ⇒ many TP paths lose net.",
        "4. Under **v1 $0.40 RT**, cost_R is almost always << 1 on this sample "
        f"(frac>1 = {summary['cost_r']['usd_0p40_v1_primary']['frac_gt_1']:.2%}).",
        "5. This does **not** by itself prove edge under v1 — only that v0 cost "
        "was structurally hostile. Full v1 needs RETEST entry re-stream + M4.",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
