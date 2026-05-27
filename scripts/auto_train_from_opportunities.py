"""
auto_train_from_opportunities.py
================================
Nightly Pipeline-B orchestrator. Runs the full unbiased training loop:

  1. scripts/research/opportunity_scanner.py on each instrument
  2. Per instrument: compress JSONL to LLM-ready summary
  3. Per instrument: scripts/training/phase5_calibration.py --train
     (each instrument gets its own model + calibration report)
  4. (optional) LLM hypertuning round-trip — currently stubbed; wired only when
     a suggestions file is supplied via --llm-suggestions
  5. (optional) all-instruments merged log for cross-instrument retrospective
  6. promote via core.model_registry.promote_gaussian() if Phase-5 approved
     and --promote-if-approved is set

Default: --per-instrument (True). Use --no-per-instrument to revert to the old
single merged-model behaviour.

Designed to be called from Task Scheduler / cron with no interactive input.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOG = logging.getLogger("AutoTrain")


def _run(cmd: list[str]) -> int:
    _LOG.info("→ %s", " ".join(cmd))
    return subprocess.call(cmd, cwd=_REPO_ROOT)


def _scan_instrument(data_dir: Path, instrument: str, output_dir: Path,
                     max_forward_candles: int, warmup_candles: int,
                     trail_mult: float = 0.5,
                     run_id: str = "") -> Path | None:
    csv_path = data_dir / f"{instrument}_M15.csv"
    if not csv_path.exists():
        _LOG.warning("Skip %s: %s not found", instrument, csv_path)
        return None
    scanner = _REPO_ROOT / "scripts" / "research" / "opportunity_scanner.py"
    rc = _run([
        sys.executable, str(scanner),
        "--csv", str(csv_path),
        "--instrument", instrument,
        "--max-forward-candles", str(max_forward_candles),
        "--warmup-candles", str(warmup_candles),
        "--output-dir", str(output_dir),
        "--trail-mult", str(trail_mult),
        "--run-id", run_id,
    ])
    if rc != 0:
        _LOG.error("Scanner failed for %s (rc=%d)", instrument, rc)
        return None
    # Run-scoped output path: {output_dir}/{instrument}/{run_id}/opportunities.jsonl
    return output_dir / instrument / run_id / "opportunities.jsonl"


def _merge_logs(paths: list[Path], merged_path: Path) -> Path:
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8") as out:
        for p in paths:
            with p.open("r", encoding="utf-8") as fh:
                shutil.copyfileobj(fh, out)
    return merged_path


def _compress(opp_path: Path, summary_path: "Path | None", instrument: str = "") -> int:
    compress_script = _REPO_ROOT / "scripts" / "analysis" / "compress_logs_for_llm.py"
    cmd = [
        sys.executable, str(compress_script),
        "--logs", str(opp_path),
    ]
    if summary_path is not None:
        cmd += ["--output", str(summary_path)]
    if instrument:
        cmd += ["--instrument", instrument]
    return _run(cmd)


def _train_instrument(opp_path: Path, instrument: str, version: str,
                      results_dir: Path, base_dir: Path,
                      extra_args: list[str]) -> int:
    """Run phase5_calibration for a single instrument's opportunity log.
    Report goes to results_dir/{instrument}/p5_calibration_{version}.json.
    """
    phase5 = _REPO_ROOT / "scripts" / "training" / "phase5_calibration.py"
    (results_dir / instrument).mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(phase5),
        "--opportunities", str(opp_path),
        "--version", version,
        "--instrument", instrument,
        "--base", str(base_dir),
        "--train",
    ] + extra_args
    return _run(cmd)


def _train_merged(merged_path: Path, version: str, base_dir: Path,
                  extra_args: list[str]) -> int:
    """Legacy: run phase5_calibration on the merged all-instruments log."""
    phase5 = _REPO_ROOT / "scripts" / "training" / "phase5_calibration.py"
    cmd = [
        sys.executable, str(phase5),
        "--opportunities", str(merged_path),
        "--version", version,
        "--base", str(base_dir),
        "--train",
    ] + extra_args
    return _run(cmd)


def _refresh_zones(opp_path: Path, instrument: str, version: str, run_id: str,
                   extra_args: list[str] | None = None) -> int:
    """Re-cluster opportunities into a fresh zone registry and promote via
    core.model_registry. Wraps scripts/research/discover_zones.py — mirrors
    the shape of _train_instrument()."""
    discover = _REPO_ROOT / "scripts" / "research" / "discover_zones.py"
    cmd = [
        sys.executable, str(discover),
        "--instrument", instrument,
        "--run-id", run_id,
        "--opportunities", str(opp_path),
        "--version", version,
    ] + list(extra_args or [])
    return _run(cmd)


def _emit_integrity(event: str, severity: str, payload: dict) -> None:
    """Emit one integrity event; never raises (matches bitnet/* fallback pattern)."""
    try:
        from utils.integrity_events import emit_integrity_event  # type: ignore
    except Exception:  # pragma: no cover — keeps orchestrator running on import failure
        return
    try:
        emit_integrity_event(event, severity, "auto_train", payload)
    except Exception:  # pragma: no cover
        return


def _maybe_promote(version: str, instrument: str) -> None:
    try:
        from core.model_registry import promote_gaussian  # type: ignore
    except Exception as exc:
        _LOG.error("Promotion import failed for %s: %s", version, exc)
        _emit_integrity(
            "PROMOTION_EXCEPTION", "CRITICAL",
            {"version": version, "instrument": instrument, "stage": "import", "error": str(exc)},
        )
        return
    try:
        ok, reason = promote_gaussian(version, instrument=instrument)
    except Exception as exc:
        _LOG.exception("Promotion crashed for %s", version)
        _emit_integrity(
            "PROMOTION_EXCEPTION", "CRITICAL",
            {"version": version, "instrument": instrument,
             "stage": "promote_gaussian", "error": str(exc)},
        )
        return
    _LOG.info("Promotion attempt for %s (%s): ok=%s reason=%s",
              version, instrument, ok, reason)
    if not ok:
        _emit_integrity(
            "PROMOTION_FAILED", "CRITICAL",
            {"version": version, "instrument": instrument, "reason": reason},
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--instruments", nargs="+",
                    default=["EURUSD", "GBPUSD", "AUDUSD", "USDJPY",
                             "EURCAD", "XAUUSD", "BTCUSDT", "ETHUSDT"])
    ap.add_argument("--output-logs", type=Path, default=Path("logs"))
    ap.add_argument("--results-dir", type=Path, default=Path("results"),
                    help="Base directory for per-instrument calibration reports "
                         "(default: results/). Reports go to results/{instrument}/.")
    ap.add_argument("--model-version", default=None,
                    help="Defaults to v5_auto_<UTC date>")
    ap.add_argument("--max-forward-candles", type=int, default=40)
    ap.add_argument("--warmup-candles", type=int, default=30)
    ap.add_argument("--trail-mult", type=float, default=0.5,
                    help="Trailing stop multiple forwarded to opportunity_scanner.py "
                         "(default=0.5; 0.5R trail populates all 4 Gaussian classes)")
    ap.add_argument("--per-instrument", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="Train a separate model per instrument (default: True). "
                         "--no-per-instrument merges all instruments and trains once "
                         "(legacy behaviour).")
    ap.add_argument("--promote-if-approved", action="store_true",
                    help="Call promote_gaussian() if phase5 returns success")
    ap.add_argument("--no-promote", action="store_true",
                    help="Force promotion off even when --promote-if-approved is set")
    ap.add_argument("--refresh-zones", action="store_true",
                    help="After phase5 succeeds for an instrument, re-cluster its "
                         "opportunities into a fresh zone registry via "
                         "scripts/research/discover_zones.py. Independent of "
                         "Gaussian promotion outcome.")
    ap.add_argument("--zones-extra", nargs="*", default=[],
                    help="Extra args forwarded verbatim to discover_zones.py "
                         "(e.g. --n-clusters 12  --subsample 5)")
    ap.add_argument("--phase5-extra", nargs="*", default=[],
                    help="Extra args forwarded verbatim to phase5_calibration.py "
                         "(e.g. --tradenet  or  --feature-subset retest_depth,...)")
    ap.add_argument("--run-id", default=None,
                    help="Shared run identifier for this pipeline run. "
                         "Auto-generates YYYYMMDD_HHMMSS if not provided. "
                         "Scopes all outputs to {dir}/{instrument}/{run_id}/.")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    sys.path.insert(0, str(_REPO_ROOT / "src"))

    run_id     = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    version    = args.model_version or f"v5_auto_{time.strftime('%Y%m%d')}"
    _LOG.info("Pipeline run_id=%s  version=%s", run_id, version)
    output_dir = args.output_logs
    output_dir.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    # base_dir: phase5 uses it as root for both models/ and results/
    base_dir = _REPO_ROOT

    # ── 1. Scan all instruments ───────────────────────────────────────────────
    scanned: list[tuple[str, Path]] = []   # (instrument, opp_path)
    for instr in args.instruments:
        p = _scan_instrument(
            args.data_dir, instr, output_dir,
            args.max_forward_candles, args.warmup_candles,
            trail_mult=args.trail_mult,
            run_id=run_id,
        )
        if p is not None and p.exists():
            scanned.append((instr, p))

    if not scanned:
        _LOG.error("No opportunity logs produced — aborting.")
        return 1

    instrs_done   = [i for i, _ in scanned]
    per_instr_paths = [p for _, p in scanned]

    # ── 2. Per-instrument compress + train (default path) ────────────────────
    results_summary: list[dict] = []

    if args.per_instrument:
        for instr, opp_path in scanned:
            # 2a. Compress (per-coin summary) — output auto-resolves from JSONL run_header
            rc_compress = _compress(opp_path, None, instrument=instr)
            if rc_compress != 0:
                _LOG.warning("Log compression failed for %s — continuing.", instr)

            # 2b. Train (per-coin model; report → results/{instr}/{run_id}/)
            rc_train = _train_instrument(
                opp_path, instr, version, args.results_dir, base_dir,
                args.phase5_extra or [],
            )
            # Report path mirrors what phase5 writes (run-scoped)
            report = str(args.results_dir / instr / run_id / f"p5_calibration_{version}.json")
            entry = {
                "instrument":    instr,
                "run_id":        run_id,
                "opportunities": str(opp_path),
                "report":        report,
                "rc":            rc_train,
            }
            results_summary.append(entry)
            if rc_train == 0:
                _LOG.info("✓ %s: phase5 complete", instr)
                print(f"OUTPUT:report:{entry['report']}")
            else:
                _LOG.error("✗ %s: phase5 failed (rc=%d) — continuing other instruments.",
                           instr, rc_train)

        # 2c. Merged log (analysis / LLM retrospective only — not used for training)
        merged_path = output_dir / f"opportunities_merged_{version}.jsonl"
        _merge_logs(per_instr_paths, merged_path)
        _LOG.info("All-instrument merged log -> %s", merged_path)

    else:
        # ── Legacy: merge all then train once ────────────────────────────────
        merged_path = output_dir / f"opportunities_merged_{version}.jsonl"
        _merge_logs(per_instr_paths, merged_path)
        _LOG.info("Merged %d files -> %s", len(per_instr_paths), merged_path)

        summary_path = output_dir / f"compressed_{version}.json"
        if _compress(merged_path, summary_path) != 0:
            _LOG.warning("Log compression failed — continuing without summary.")

        rc = _train_merged(merged_path, version, base_dir, args.phase5_extra or [])
        if rc != 0:
            _LOG.error("Phase-5 calibration failed (rc=%d).", rc)
            return rc

        results_summary = [{
            "instrument": "MERGED",
            "opportunities": str(merged_path),
            "compressed":    str(summary_path),
            "rc":            rc,
        }]

    # ── 3. (LLM hypertuning round-trip wired through scripts/groq_bridge/.
    #        Trigger manually: prepare_retrospective.py + ingest_response.py)

    # ── 4. Promote ───────────────────────────────────────────────────────────
    if args.promote_if_approved and not args.no_promote:
        for entry in results_summary:
            if entry["rc"] != 0:
                continue
            promo_version = version if entry["instrument"] == "MERGED" else version
            # MERGED bundles are tagged as a synthetic instrument key so the active
            # pointer doesn't collide with single-instrument runs.
            promo_instrument = (
                "MERGED" if entry["instrument"] == "MERGED" else entry["instrument"]
            )
            try:
                _maybe_promote(promo_version, promo_instrument)
            except Exception as exc:
                _LOG.error("Promotion for %s raised: %s", entry["instrument"], exc)

    # ── 5. Refresh zone registry (per-instrument only — MERGED has no run_id) ─
    if args.refresh_zones:
        for entry in results_summary:
            if entry["rc"] != 0 or entry["instrument"] == "MERGED":
                continue
            try:
                rc_zones = _refresh_zones(
                    Path(entry["opportunities"]),
                    entry["instrument"],
                    version,
                    entry["run_id"],
                    args.zones_extra or [],
                )
            except Exception as exc:
                _LOG.error("Zone refresh for %s raised: %s", entry["instrument"], exc)
                continue
            if rc_zones == 0:
                _LOG.info("✓ %s: zone refresh complete", entry["instrument"])
            else:
                _LOG.error("✗ %s: zone refresh failed (rc=%d)",
                           entry["instrument"], rc_zones)
                _emit_integrity(
                    "ZONE_REFRESH_FAILED", "ERROR",
                    {"instrument": entry["instrument"], "version": version,
                     "run_id": entry["run_id"], "rc": rc_zones},
                )

    # ── Final summary ────────────────────────────────────────────────────────
    any_failure = any(e["rc"] != 0 for e in results_summary)
    summary_payload = {
        "run_id":                 run_id,
        "version":                version,
        "per_instrument":         args.per_instrument,
        "instruments_attempted":  args.instruments,
        "instruments_scanned":    instrs_done,
        "per_instrument_results": results_summary,
    }
    print(json.dumps(summary_payload, indent=2))
    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
