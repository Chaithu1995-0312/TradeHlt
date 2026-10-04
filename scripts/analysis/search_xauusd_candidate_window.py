# -*- coding: utf-8 -*-
"""Find smallest trailing XAUUSD window with >= N CRT RETEST candidates.

Candidate definition (default): STATE_TRANSITION with state_to == RETEST.
These are retest opportunities; they may still be session-filtered (0 trades).

Uses BACKTEST_ENGINE_GATE=0 by default (faster CRT path; admission filters still apply).

Writes:
  results/runtime_benchmarks/window_search_xauusd/window_search_report.json
  data/XAUUSD_W<first>-to-<last>.csv slices (guard-safe names under data/)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_SHA256,
    guard_xauusd_csv_path,
)

INSTRUMENT = "XAUUSD"
OUT_ROOT = ROOT / "results" / "runtime_benchmarks" / "window_search_xauusd"
DATA = ROOT / "data"


def export_trailing_months(df: pd.DataFrame, last_ts, months: int) -> tuple[Path, int, pd.Timestamp, pd.Timestamp]:
    cutoff = last_ts - pd.DateOffset(months=months)
    w = df[df["timestamp"] >= cutoff].reset_index(drop=True)
    first, last = w["timestamp"].min(), w["timestamp"].max()
    name = f"XAUUSD_W{first.date()}-to-{last.date()}.csv"
    path = DATA / name
    w.to_csv(path, index=False)
    return path, len(w), first, last


def count_candidates(events_path: Path) -> dict:
    n_retest = 0
    n_filter = 0
    n_exec = 0
    n_trade = 0
    retest_ts: list[str] = []
    filter_reasons: Counter = Counter()
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        ev = e.get("event") or e.get("kind")
        if ev == "STATE_TRANSITION":
            to = e.get("state_to")
            if to == "RETEST":
                n_retest += 1
                retest_ts.append(str(e.get("timestamp")))
            if to == "EXECUTION":
                n_exec += 1
        if ev == "FILTER_REJECTED":
            n_filter += 1
            filter_reasons[str(e.get("reason"))] += 1
        if ev in ("TRADE_OPENED", "TRADE_OPEN"):
            n_trade += 1
    return {
        "n_retest": n_retest,
        "n_filter_rejected": n_filter,
        "n_execution": n_exec,
        "n_trade_opened": n_trade,
        "retest_timestamps": retest_ts,
        "filter_reasons": dict(filter_reasons),
        "n_candidates": n_retest,
    }


def run_window(df: pd.DataFrame, last_ts, months: int, gate: str = "0") -> dict:
    path, nrows, first, last = export_trailing_months(df, last_ts, months)
    out_dir = OUT_ROOT / f"trail_{months}m_gate{gate}"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["BACKTEST_ENGINE_GATE"] = gate
    cmd = [
        sys.executable,
        str(ROOT / "src" / "runtime" / "backtest_v2.py"),
        "--csv",
        str(path),
        "--instrument",
        INSTRUMENT,
        "--output",
        str(out_dir),
        "--scorer",
        "calibrated",
    ]
    console = out_dir / "console.txt"
    t0 = time.perf_counter()
    with console.open("w", encoding="utf-8") as cf:
        proc = subprocess.run(cmd, env=env, stdout=cf, stderr=subprocess.STDOUT, cwd=str(ROOT))
    elapsed = time.perf_counter() - t0
    runs = sorted(out_dir.glob("run_*"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return {
            "months": months,
            "ok": False,
            "elapsed_s": round(elapsed, 2),
            "exit": proc.returncode,
            "error": "no run dir",
        }
    run_dir = runs[-1]
    events = run_dir / f"{INSTRUMENT}_events.jsonl"
    summary = json.loads((run_dir / f"{INSTRUMENT}_summary.json").read_text(encoding="utf-8"))
    c = count_candidates(events)
    rec = {
        "months": months,
        "ok": True,
        "exit": proc.returncode,
        "elapsed_s": round(elapsed, 2),
        "csv_path": path.relative_to(ROOT).as_posix(),
        "csv_rows": nrows,
        "first_ts": str(first),
        "last_ts": str(last),
        "run_dir": run_dir.relative_to(ROOT).as_posix(),
        "approved_trades": summary.get("approved_trades"),
        "total_setups": summary.get("total_setups"),
        "n_retest": c["n_retest"],
        "n_filter_rejected": c["n_filter_rejected"],
        "n_execution": c["n_execution"],
        "n_trade_opened": c["n_trade_opened"],
        "n_candidates": c["n_candidates"],
        "filter_reasons": c["filter_reasons"],
        "retest_timestamps": c["retest_timestamps"],
        "under_120s": elapsed < 120.0,
    }
    slim = {k: v for k, v in rec.items() if k != "retest_timestamps"}
    print(json.dumps(slim, indent=2), flush=True)
    print("  retests:", c["retest_timestamps"], flush=True)
    return rec


def densest_span(retest_ts: list[str], n: int) -> dict | None:
    if len(retest_ts) < n:
        return None
    ts = pd.to_datetime(retest_ts)
    best = None
    for i in range(len(ts) - n + 1):
        span_days = (ts[i + n - 1] - ts[i]).total_seconds() / 86400.0
        if best is None or span_days < best[0]:
            best = (span_days, ts[i], ts[i + n - 1])
    assert best is not None
    return {
        "n": n,
        "span_days": round(best[0], 2),
        "first_retest": str(best[1]),
        "last_retest": str(best[2]),
        "note": (
            "Calendar span between first and last of N densest retests only. "
            "A runnable backtest window still needs pre-history (warmup + CRT state build-up) "
            "before the first retest."
        ),
    }


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    src = guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)
    df = pd.read_csv(src, parse_dates=["timestamp"])
    last_ts = df["timestamp"].max()
    print(
        f"corpus rows={len(df)} end={last_ts} parent_sha={PHASE1_SHA256[:16]}…",
        flush=True,
    )

    results: list[dict] = []
    # Expand trailing months until >=10 candidates or wall-clock too long
    for m in (2, 3, 4, 5, 6, 8, 10, 12, 15, 18):
        rec = run_window(df, last_ts, m, gate="0")
        results.append(rec)
        if rec.get("ok") and int(rec.get("n_candidates") or 0) >= 10:
            print(f"STOP: months={m} n_candidates={rec['n_candidates']}", flush=True)
            break
        if float(rec.get("elapsed_s") or 0) > 180:
            print(
                f"STOP: months={m} wall {rec['elapsed_s']}s > 180s expansion cap",
                flush=True,
            )
            break

    eligible = [r for r in results if r.get("ok") and int(r.get("n_candidates") or 0) >= 5]
    report: dict = {
        "candidate_definition": (
            "STATE_TRANSITION with state_to==RETEST "
            "(CRT retest opportunity; may still be FILTER_REJECTED by session)"
        ),
        "gate": "BACKTEST_ENGINE_GATE=0",
        "time_budget": "prefer under_120s wall clock per arm",
        "target_candidates": "5-10",
        "corpus": "data/mt5/XAUUSD_M15.csv via guard (PHASE1 frozen)",
        "trailing_search": [
            {k: v for k, v in r.items() if k != "retest_timestamps"} for r in results
        ],
        "retest_lists": {
            str(r["months"]): r.get("retest_timestamps") for r in results if r.get("ok")
        },
    }

    if eligible:
        # Prefer enough candidates, then fewer rows, then faster
        def score(r: dict) -> tuple:
            n = int(r["n_candidates"])
            # band: 5-10 preferred over >>10 if still meeting minimum
            band = 0 if 5 <= n <= 10 else (1 if n > 10 else 2)
            return (band, r["csv_rows"], r["elapsed_s"])

        best = min(eligible, key=score)
        report["recommended_trailing_window"] = {
            k: v for k, v in best.items() if k != "retest_timestamps"
        }
        for n in (5, 8, 10):
            span = densest_span(best.get("retest_timestamps") or [], n)
            if span:
                report[f"densest_span_for_{n}_retests"] = span

        # Also recommend smallest trailing that hits each threshold
        for thr in (5, 8, 10):
            hits = [
                r
                for r in results
                if r.get("ok") and int(r.get("n_candidates") or 0) >= thr
            ]
            if hits:
                h = min(hits, key=lambda r: (r["csv_rows"], r["elapsed_s"]))
                report[f"smallest_trailing_ge_{thr}"] = {
                    k: v for k, v in h.items() if k != "retest_timestamps"
                }
    else:
        report["recommended_trailing_window"] = None
        report["note"] = "No trailing window in search hit >=5 RETEST candidates"

    outp = OUT_ROOT / "window_search_report.json"
    outp.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print("REPORT", outp, flush=True)
    # human summary
    print("--- SUMMARY ---", flush=True)
    for r in results:
        if not r.get("ok"):
            print(f"  {r['months']}m FAIL {r}", flush=True)
            continue
        print(
            f"  {r['months']:>2}m  rows={r['csv_rows']:<6}  "
            f"candidates(RETEST)={r['n_candidates']:<3}  "
            f"filter={r['n_filter_rejected']:<3}  trades={r['approved_trades']:<3}  "
            f"time={r['elapsed_s']:.1f}s  under_2m={r['under_120s']}",
            flush=True,
        )
    rec = report.get("recommended_trailing_window")
    if rec:
        print(
            f"RECOMMENDED: trailing {rec['months']}m | rows={rec['csv_rows']} | "
            f"candidates={rec['n_candidates']} | {rec['elapsed_s']}s | {rec['csv_path']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
