"""htf_objective_gate_shadow.py — P-HTF-01: attributed OFF-vs-ON ledger for
`parent_crt.objective_gate` (Stage 3 / F-078, HTFState + ObjectiveStatus).

WHAT THIS IS
------------
Follows the OFF-vs-ON book-comparison pattern of
scripts/research/model_shadow_protocol.py (itself generalized from
bitnet_shadow_diagnostic.py), but drives the REAL `backtest_v2` CRT ledger
instead of `ProductionSpineSource`, because the artifact this measures
(`XAUUSD_events.jsonl` / `XAUUSD_crt_telemetry.jsonl` reject-reason
attribution) only exists on the backtest ledger, not the research spine
adapter.

Two arms (OFF = v2_htfcrt_2026_08, ON = v2_htfcrt_objgate_shadow_2026_08 —
identical except `parent_crt.objective_gate.enabled: true`), each run on up
to two scopes:

  * one_month — data/XAUUSD_M15.csv (2,116 bars), the exact corpus the prior
    Grok session (2026-08-16) used for the parent-bias wiring check. Directly
    comparable to results/htfcrt_1month_parent_wired/run_20260816_011239_XAUUSD.
  * two_year  — data/mt5/XAUUSD_M15.csv (47,275 bars, Phase-1 frozen
    candidate), the only scope with a countable RETEST population — one_month
    has n=2 RETEST, which cannot power a gate comparison on its own.

Entry sets are NOT nested: a gate reject calls `reset_to_range`, so the ON
trajectory diverges from OFF the moment it fires (same caveat as
model_shadow_protocol.py). This script compares at the LEDGER level (event
counts, funnel, reject-reason histograms, aggregate G001), not per-trade.

WHAT THIS IS NOT
----------------
* Not a promotion mechanism. Never writes `objective_gate.enabled` to any
  ACTIVE config. `configs/production/ACTIVE_VERSION` is never touched.
* Not a sweep — one fixed OFF/ON config pair per scope, nothing tuned.

USAGE
-----
    venv\\Scripts\\python.exe scripts/research/htf_objective_gate_shadow.py \\
        --scope both

Internal (each arm runs as its own subprocess so `PROD_VERSION` — bound by
value into `runtime.backtest_v2` at import time via
`from config_layer.production_config import PROD_VERSION` — can differ
per arm without cross-contamination):

    venv\\Scripts\\python.exe scripts/research/htf_objective_gate_shadow.py \\
        --_run-arm --version <cfg> --csv <path> --output <dir> [--one-month]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

OFF_VERSION_DEFAULT = "v2_htfcrt_2026_08"
ON_VERSION_DEFAULT = "v2_htfcrt_objgate_shadow_2026_08"
ONE_MONTH_CSV = "data/XAUUSD_M15.csv"
TWO_YEAR_CSV = "data/mt5/XAUUSD_M15.csv"
OBJECTIVE_REASON_PREFIX = "Against parent-timeframe objective"
BIAS_REASON_PREFIX = "Against parent-timeframe bias"


# ─────────────────────────────────────────────────────────────────────────
# Internal arm runner — executed as its OWN subprocess (see USAGE above).
# ─────────────────────────────────────────────────────────────────────────

def _run_arm(version: str, csv_path: str, output: str, instrument: str, one_month: bool) -> None:
    # Patch PROD_VERSION on the production_config MODULE before backtest_v2
    # does `from config_layer.production_config import PROD_VERSION` — that
    # import statement binds the value at import time, so the patch must land
    # first (same requirement documented at backtest_v2.py:3167-3175's own
    # --config-override path, which patches the module attribute for the
    # same reason, though only for logging there).
    import config_layer.production_config as pc
    pc.PROD_VERSION = version

    import runtime.backtest_v2 as bt

    if bt.PROD_VERSION != version:
        raise RuntimeError(
            f"PROD_VERSION patch did not take: backtest_v2.PROD_VERSION="
            f"{bt.PROD_VERSION!r}, expected {version!r}. The import order in "
            f"this function was changed — patch config_layer.production_config."
            f"PROD_VERSION strictly before `import runtime.backtest_v2`."
        )

    if one_month:
        # Scope this process only. The Phase-1 XAUUSD guard
        # (data_ingestion.xauusd_phase1_candidate.guard_xauusd_csv_path)
        # rewrites any XAUUSD_M15* path to the 2-year frozen candidate —
        # correct default behavior, identity-patched here (subprocess-local,
        # production guard on disk is untouched) so the one-month scope can
        # stream data/XAUUSD_M15.csv as-is, same technique the prior Grok
        # session used for results/htfcrt_1month/run_20260816_005200_XAUUSD.
        bt.guard_xauusd_csv_path = lambda fp, instrument="", **kw: str(fp)

    sys.argv = [
        "backtest_v2.py",
        "--csv", csv_path,
        "--instrument", instrument,
        "--output", output,
    ]
    bt.main()


# ─────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────

def _find_run_dir(output_base: Path, instrument: str) -> Path:
    candidates = sorted(output_base.glob(f"run_*_{instrument}"))
    if not candidates:
        raise RuntimeError(f"No run_*_{instrument} directory found under {output_base}")
    return candidates[-1]


def _run_one_arm_subprocess(
    python_exe: str, version: str, csv_path: str, output: Path, instrument: str, one_month: bool,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_exe, str(Path(__file__).resolve()),
        "--_run-arm",
        "--version", version,
        "--csv", csv_path,
        "--output", str(output),
        "--instrument", instrument,
    ]
    if one_month:
        cmd.append("--one-month")
    print(f"[RUN] version={version} csv={csv_path} -> {output}", flush=True)
    proc = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Arm failed (version={version}, csv={csv_path}, rc={proc.returncode}).\n"
            f"--- stdout (tail) ---\n{proc.stdout[-4000:]}\n"
            f"--- stderr (tail) ---\n{proc.stderr[-4000:]}"
        )
    return _find_run_dir(output, instrument)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _reason_bucket(reason: str) -> str:
    """Collapse timestamp/id-suffixed reasons into a stable bucket for counting."""
    if reason.startswith(OBJECTIVE_REASON_PREFIX):
        return reason  # "Against parent-timeframe objective (<status>)" — keep status
    if reason.startswith(BIAS_REASON_PREFIX):
        return reason  # "Against parent-timeframe bias (<direction>)" — keep direction
    if reason.startswith("HTF changed"):
        return "HTF changed"
    if reason.startswith("1.618 extension hit"):
        return "1.618 extension hit"
    if reason.startswith("50% retrace hit"):
        return "50% retrace hit"
    if reason.startswith("Session gap detected"):
        return "Session gap detected"
    if ":" in reason:
        return reason.split(":", 1)[0]
    return reason


def _attribute(run_dir: Path, instrument: str) -> dict:
    summary = json.loads((run_dir / f"{instrument}_summary.json").read_text(encoding="utf-8"))
    events = _load_jsonl(run_dir / f"{instrument}_events.jsonl")
    telemetry = _load_jsonl(run_dir / f"{instrument}_crt_telemetry.jsonl")

    filter_rejected_reasons = Counter(
        _reason_bucket(e["reason"]) for e in events if e.get("event") == "FILTER_REJECTED"
    )
    reset_reasons = Counter(
        _reason_bucket(e["reason"]) for e in events if e.get("event") == "RESET"
    )
    retest_replay_rejects = Counter(
        r.get("reject_reason", "<accepted>")
        for r in telemetry
        if r.get("kind") == "RETEST_REPLAY"
    )

    return {
        "run_dir": str(run_dir),
        "total_setups": summary.get("total_setups"),
        "approved_trades": summary.get("approved_trades"),
        "rejected_trades": summary.get("rejected_trades"),
        "win_rate": summary.get("win_rate"),
        "avg_rr_net": summary.get("avg_rr_net"),
        "total_pnl_rr_net": summary.get("total_pnl_rr_net"),
        "funnel_counts": summary.get("funnel_counts") or summary.get("state_distribution"),
        "n_events": len(events),
        "filter_rejected_reasons": dict(filter_rejected_reasons),
        "reset_reasons": dict(reset_reasons),
        "retest_replay_reject_reasons": dict(retest_replay_rejects),
        "goal_report": (summary.get("distribution") or {}).get("goal_report"),
        "_raw_events": events,
    }


def _event_line_diff(off_events: list[dict], on_events: list[dict]) -> dict:
    off_lines = [json.dumps(e, sort_keys=True) for e in off_events]
    on_lines = [json.dumps(e, sort_keys=True) for e in on_events]
    n = min(len(off_lines), len(on_lines))
    differing = [
        {"index": i, "off": off_events[i], "on": on_events[i]}
        for i in range(n) if off_lines[i] != on_lines[i]
    ]
    return {
        "n_off": len(off_lines),
        "n_on": len(on_lines),
        "same_length": len(off_lines) == len(on_lines),
        "n_differing_lines": len(differing),
        "differing_lines": differing[:50],  # cap — full arrays live in the per-arm ledgers
    }


def _verdict(off: dict, on: dict, diff: dict) -> str:
    off_trades = off["approved_trades"] or 0
    on_trades = on["approved_trades"] or 0
    objective_fired = any(
        k.startswith(OBJECTIVE_REASON_PREFIX) for k in on["filter_rejected_reasons"]
    )
    if not objective_fired:
        return "NOT_REACHED (objective elif never fired on the ON arm — vacuous comparison)"
    if off_trades == 0 and on_trades == 0:
        if diff["n_differing_lines"] == 0:
            return "INERT (gate reachable, no reject fired, ledger byte-identical)"
        return "NOT_MEASURABLE (gate fired on the ON arm; 0 trades on both arms so no economic delta exists to measure)"
    off_e = off.get("avg_rr_net") or 0.0
    on_e = on.get("avg_rr_net") or 0.0
    delta = round(on_e - off_e, 4)
    if off_trades != on_trades:
        return f"UNDETERMINED (trade count changed {off_trades}->{on_trades}; book-level, not per-trade nested — read the full ledger)"
    if delta > 1e-9:
        return f"HELPFUL (avg_rr_net delta={delta:+.4f})"
    if delta < -1e-9:
        return f"HARMFUL (avg_rr_net delta={delta:+.4f})"
    return f"NEUTRAL (avg_rr_net delta={delta:+.4f})"


def _run_scope(python_exe: str, scope: str, csv_path: str, off_version: str, on_version: str, out_root: Path) -> dict:
    instrument = "XAUUSD"
    one_month = scope == "one_month"
    off_dir = _run_one_arm_subprocess(python_exe, off_version, csv_path, out_root / scope / "off", instrument, one_month)
    on_dir = _run_one_arm_subprocess(python_exe, on_version, csv_path, out_root / scope / "on", instrument, one_month)

    off = _attribute(off_dir, instrument)
    on = _attribute(on_dir, instrument)
    diff = _event_line_diff(off.pop("_raw_events"), on.pop("_raw_events"))
    verdict = _verdict(off, on, diff)

    result = {
        "scope": scope,
        "csv": csv_path,
        "off_version": off_version,
        "on_version": on_version,
        "off": off,
        "on": on,
        "event_diff": diff,
        "verdict": verdict,
    }
    print(
        f"[{scope}] off_trades={off['approved_trades']} on_trades={on['approved_trades']} "
        f"events_diff={diff['n_differing_lines']}/{diff['n_off']} | {verdict}",
        flush=True,
    )
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--_run-arm", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--version")
    ap.add_argument("--csv")
    ap.add_argument("--output")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--one-month", action="store_true", default=False)
    ap.add_argument("--scope", choices=["one_month", "two_year", "both"], default="both")
    ap.add_argument("--off-version", default=OFF_VERSION_DEFAULT)
    ap.add_argument("--on-version", default=ON_VERSION_DEFAULT)
    ap.add_argument("--one-month-csv", default=ONE_MONTH_CSV)
    ap.add_argument("--two-year-csv", default=TWO_YEAR_CSV)
    ap.add_argument("--out", default="results/htf_objective_shadow")
    ap.add_argument("--python-exe", default=str(_ROOT / "venv" / "Scripts" / "python.exe"))
    args = ap.parse_args(argv)

    if args._run_arm:
        if not (args.version and args.csv and args.output):
            ap.error("--_run-arm requires --version, --csv, --output")
        _run_arm(args.version, args.csv, args.output, args.instrument, args.one_month)
        return 0

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    scopes = ["one_month", "two_year"] if args.scope == "both" else [args.scope]
    csv_by_scope = {"one_month": args.one_month_csv, "two_year": args.two_year_csv}

    results = {}
    for scope in scopes:
        results[scope] = _run_scope(
            args.python_exe, scope, csv_by_scope[scope], args.off_version, args.on_version, out_root,
        )

    report = {
        "kind": "htf_objective_gate_shadow",
        "label": "P-HTF-01",
        "scope": "research-authority-only (CLAUDE.md sec6.5) — this script NEVER writes "
                 "objective_gate.enabled to any production config; enabling the gate on "
                 "ACTIVE_VERSION is a separate, human-approved governance act",
        "note": "Entry sets are NOT nested: a gate reject calls reset_to_range on the ON arm, "
                "so ON is a divergent trajectory the moment the objective elif fires. Compare "
                "at ledger/book level (model_shadow_protocol.py precedent), not per-trade.",
        "pre_registration": {
            "one_month": "gate ordering (zone -> parent-bias elif -> objective elif -> else "
                         "{session filter}) means Jul 20 17:00 is consumed by parent-bias "
                         "before the objective elif is ever reached; Jul 15 22:30 has bias=NONE "
                         "so the objective elif fires and its FILTER_REJECTED reason flips from "
                         "off_session:OFF_SESSION to 'Against parent-timeframe objective (NONE)'. "
                         "Predicted: 0 trades both arms, exactly 1 differing event line.",
        },
        "results": results,
    }
    out_path = out_root / "report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] wrote {out_path}")
    print("[SCOPE] No enable flag written. Enabling parent_crt.objective_gate on ACTIVE_VERSION "
          "requires separate, human-approved promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
