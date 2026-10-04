# -*- coding: utf-8 -*-
"""verify_m5_resample_parity.py — Program-9 corpus-level resampler validation (M1 gate).

STRONG end-to-end check of the M5 ladder: for every Program-9 symbol, `resample(M5, rule)`
for rule in {M15, H1, H4} must EXACTLY reproduce the independently-FETCHED on-disk file
(data/binance/{SYM}_{rule}.csv or data/mt5/{SYM}_{rule}.csv) over the coverage
INTERSECTION (fetched trailing row dropped — the resampler never emits the in-progress
bucket; provider ladders have different depths: MT5 M5 retention ~270d vs 2yr M15/H1/H4).
OHLC must match exactly; volume within rel 1e-8 (Decimal-exact in the resampler).

MEASURE-ONLY: writes results/research/m5_mtf/resample_parity.json. Program 9's M2 Stage-1
run is gated on this report being all-PASS (docs/research/preregistration-program-9.md).

Usage:
    python scripts/research/verify_m5_resample_parity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.resample import resample                                  # noqa: E402
from utils.console_safe import safe_print                               # noqa: E402

GROUPS = {
    "binance": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"],
    "mt5": ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD", "XAUUSD"],
}
RULES = ("M15", "H1", "H4")
VOL_REL_TOL = 1e-8

OUT_DIR = _ROOT / "results" / "research" / "m5_mtf"


def _load(path: Path, symbol: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(str(path), symbol).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _compare(resampled: list, fetched: list) -> dict:
    """STRICT 1:1 comparison over the coverage INTERSECTION.

    The fetched trailing row is dropped (the resampler never emits the in-progress
    bucket), then both series are sliced to the overlapping window — provider ladders
    can have different depths (MT5 M5 retention ~270d vs 2yr M15/H1/H4; F-027 fetch
    boundary). Inside the overlap the match must be exact: same timestamps, exact OHLC,
    volume within rel 1e-8."""
    ref = fetched[:-1]                      # resampler drops the trailing bucket
    if not resampled or not ref:
        return {"status": "FAIL", "reason": "empty series"}
    lo = max(resampled[0].timestamp, ref[0].timestamp)
    hi = min(resampled[-1].timestamp, ref[-1].timestamp)
    if lo > hi:
        return {"status": "FAIL", "reason": f"no coverage overlap ({lo} > {hi})"}
    resampled = [c for c in resampled if lo <= c.timestamp <= hi]
    ref = [c for c in ref if lo <= c.timestamp <= hi]
    if len(resampled) != len(ref):
        return {"status": "FAIL",
                "reason": f"row count in overlap {len(resampled)} != {len(ref)}",
                "rows_resampled": len(resampled), "rows_fetched": len(ref)}
    for i, (a, b) in enumerate(zip(resampled, ref)):
        if a.timestamp != b.timestamp:
            return {"status": "FAIL", "reason": f"timestamp mismatch at row {i}: {a.timestamp} != {b.timestamp}"}
        for field in ("open", "high", "low", "close"):
            va, vb = float(getattr(a, field)), float(getattr(b, field))
            if va != vb:
                return {"status": "FAIL",
                        "reason": f"{field} mismatch at row {i} ({a.timestamp}): {va!r} != {vb!r}"}
        va, vb = float(a.volume), float(b.volume)
        denom = max(abs(va), abs(vb), 1e-12)
        if abs(va - vb) / denom > VOL_REL_TOL:
            return {"status": "FAIL",
                    "reason": f"volume mismatch at row {i} ({a.timestamp}): {va!r} vs {vb!r}"}
    return {"status": "PASS", "rows": len(resampled),
            "overlap": [str(lo), str(hi)]}


def main() -> int:
    report: dict = {"vol_rel_tol": VOL_REL_TOL, "groups": {}}
    n_fail = 0
    for group, symbols in GROUPS.items():
        gdir = _ROOT / "data" / group
        gres: dict = {}
        for sym in symbols:
            m5_path = gdir / f"{sym}_M5.csv"
            if not m5_path.exists():
                gres[sym] = {"status": "SKIP", "reason": f"missing {m5_path}"}
                continue
            m5 = _load(m5_path, sym)
            per_rule: dict = {}
            for rule in RULES:
                ref_path = gdir / f"{sym}_{rule}.csv"
                if not ref_path.exists():
                    per_rule[rule] = {"status": "SKIP", "reason": f"missing {ref_path}"}
                    continue
                res = _compare(resample(m5, rule), _load(ref_path, sym))
                per_rule[rule] = res
                if res["status"] == "FAIL":
                    n_fail += 1
                safe_print(f"  {group}/{sym} M5->{rule}: {res['status']}"
                           + (f" ({res.get('reason', '')})" if res["status"] != "PASS" else f" rows={res['rows']}"))
            gres[sym] = per_rule
        report["groups"][group] = gres
    report["verdict"] = "PASS" if n_fail == 0 else "FAIL"
    report["n_fail"] = n_fail

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "resample_parity.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    safe_print(f"verdict={report['verdict']} n_fail={n_fail} -> {out}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
