"""R1-C trade-window selection (CLI). Thin wrapper over src/semantics/integration/select_window.py.

Reads ONLY the engine's own output of a plain full-corpus backtest (trades CSV + events.jsonl) and
never any Semantic OS verdict. Picks the smallest contiguous window with the widest trade-lifecycle
coverage, cuts it verbatim to data/mt5/XAUUSD_W<start>-to-<end>.csv, verifies by a plain backtest of
the slice that the engine reproduces the same trades, and writes a selection manifest.

    venv/Scripts/python.exe scripts/governance/semantic_os_trade_window.py --full-run <run dir>
    venv/Scripts/python.exe scripts/governance/semantic_os_trade_window.py          # runs the full backtest first
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    from semantics.integration import select_window as sw
    from semantics.integration.observe import plain_backtest, read_events
    from semantics.registry import active_config_value

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", default=str(ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    ap.add_argument("--full-run", default="", help="existing plain full-corpus run dir (else one is run)")
    ap.add_argument("--out", default=str(ROOT / "results" / "semantic_os_integration" / "r1c_scan"))
    ap.add_argument("--slice-dir", default=str(ROOT / "data" / "mt5"))
    ap.add_argument("--max-attempts", type=int, default=4)
    args = ap.parse_args(argv)

    corpus, out = Path(args.corpus).resolve(), Path(args.out)
    full = Path(args.full_run) if args.full_run else plain_backtest(corpus, out / "full")
    trades = sw.read_trades(next(full.glob("*_trades.csv")))
    stamps = sw.read_timestamps(corpus)
    sweeps = sw.founding_sweeps(read_events(full))
    warmup = int(active_config_value("backtest.warmup_candles"))
    htf = int(active_config_value("backtest.htf_candles_per_range"))

    attempts = []
    window = None
    for attempt in range(args.max_attempts):
        lead = warmup + htf * (2 ** (attempt + 1))
        grid = htf if str(active_config_value("backtest.htf_clock_basis")) == "count" else 1
        window = sw.choose_window(trades, stamps, sweeps, lead, grid=grid)
        if window is None:
            break
        expected = sw.window_trades(trades, window)
        slice_path = sw.write_slice(corpus, window.start_row, window.end_row, Path(args.slice_dir))
        try:
            slice_run = plain_backtest(slice_path, out / f"verify_{attempt}")
        except SystemExit as exc:
            # The backtest's own preflight refused the slice (e.g. clock provenance UNREVIEWED,
            # F-066). Record it and stop: no retry can fix a gate that needs a human declaration.
            attempts.append({"lead_bars": lead, "slice": str(slice_path), "bars": window.bars,
                             "expected_trades": [t.key() for t in expected], "reproduced": False,
                             "slice_rejected": f"backtest preflight exited {exc.code}; see the backtest log "
                                               "(clock provenance needs: scripts/governance/review_ohlcv_clocks.py --review)"})
            break
        got = sw.read_trades(next(slice_run.glob("*_trades.csv"))) if list(slice_run.glob("*_trades.csv")) else []
        same = [t.key() for t in got] == [t.key() for t in expected]
        attempts.append({"lead_bars": lead, "grid": grid, "start_row": window.start_row,
                         "slice": str(slice_path), "bars": window.bars,
                         "slice_run": str(slice_run), "expected_trades": [t.key() for t in expected],
                         "slice_trades": [t.key() for t in got], "reproduced": same,
                         "slice_satisfied": sw.satisfied(got)})
        if same:
            break

    manifest = json.loads((full / "run_manifest.json").read_text(encoding="utf-8"))
    result = {
        "experiment": "R1-C trade-exercising corpus selection (SEMANTIC_OS_V2_MEANING_PLANE.md §16)",
        "provenance": "engine output only (trades CSV + events.jsonl of a plain backtest); "
                      "no Semantic OS verdict, UNEXPLAINED row or contract disagreement was read",
        "source_corpus": {"path": str(corpus), "sha256": _sha256(corpus), "rows": len(stamps)},
        "config": {"active_version": manifest.get("fingerprint", {}).get("config_version"),
                   "config_hash": manifest.get("fingerprint", {}).get("config_hash"),
                   "entry_semantics": active_config_value("setup.entry_semantics")},
        "code_sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "full_run": str(full),
        "full_corpus_trades": len(trades),
        "full_corpus_satisfies": sw.satisfied(trades),
        "algorithm": {"module": "src/semantics/integration/select_window.py",
                      "doc": inspect.getdoc(sw), "hard": list(sw.HARD), "preference": list(sw.PREFERENCE)},
        "attempts": attempts,
    }
    if window is not None and attempts:
        chosen = attempts[-1]
        result["selected"] = {
            "slice": chosen["slice"], "slice_sha256": _sha256(Path(chosen["slice"])),
            "start": stamps[window.start_row].isoformat(), "end": stamps[window.end_row].isoformat(),
            "start_row": window.start_row, "end_row": window.end_row, "bars": window.bars,
            "trades": [t.__dict__ | {"opened_at": t.opened_at.isoformat(), "closed_at": t.closed_at.isoformat(),
                                     "lifecycle": sorted(t.lifecycle)} for t in sw.window_trades(trades, window)],
            "criteria_satisfied": window.satisfied,
            "criteria_unavailable": sw.unavailable(trades, window),
            "reproduced_on_slice": chosen["reproduced"],
            "slice_rejected": chosen.get("slice_rejected"),
        }
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in ("full_corpus_trades", "full_corpus_satisfies", "selected")},
                     indent=2, default=str))
    return 0 if result.get("selected", {}).get("reproduced_on_slice") else 2


if __name__ == "__main__":
    raise SystemExit(main())
