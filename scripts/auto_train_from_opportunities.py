"""
auto_train_from_opportunities.py
================================
Nightly Pipeline-B orchestrator. Runs the full unbiased training loop:

  1. scripts/research/opportunity_scanner.py on each instrument
  2. concatenate per-instrument JSONL files into one merged log
  3. scripts/analysis/compress_logs_for_llm.py to produce an LLM-ready summary
  4. (optional) LLM hypertuning round-trip — currently stubbed; wired only when
     a suggestions file is supplied via --llm-suggestions
  5. scripts/training/phase5_calibration.py --opportunities ... --train
  6. promote via core.model_registry.promote_gaussian() if Phase-5 approved
     and --promote-if-approved is set

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
                     max_forward_candles: int, warmup_candles: int) -> Path | None:
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
    ])
    if rc != 0:
        _LOG.error("Scanner failed for %s (rc=%d)", instrument, rc)
        return None
    return output_dir / f"opportunities_{instrument}.jsonl"


def _merge_logs(paths: list[Path], merged_path: Path) -> Path:
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8") as out:
        for p in paths:
            with p.open("r", encoding="utf-8") as fh:
                shutil.copyfileobj(fh, out)
    return merged_path


def _compress(merged_path: Path, summary_path: Path) -> int:
    compress_script = _REPO_ROOT / "scripts" / "analysis" / "compress_logs_for_llm.py"
    return _run([
        sys.executable, str(compress_script),
        "--logs", str(merged_path),
        "--output", str(summary_path),
    ])


def _train(merged_path: Path, version: str, extra_args: list[str]) -> int:
    phase5 = _REPO_ROOT / "scripts" / "training" / "phase5_calibration.py"
    cmd = [
        sys.executable, str(phase5),
        "--opportunities", str(merged_path),
        "--version", version,
        "--train",
    ] + extra_args
    return _run(cmd)


def _maybe_promote(version: str) -> None:
    from core.model_registry import promote_gaussian  # type: ignore
    ok, reason = promote_gaussian(version)
    _LOG.info("Promotion attempt for %s: ok=%s reason=%s", version, ok, reason)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--instruments", nargs="+",
                    default=["EURUSD", "GBPUSD", "AUDUSD", "USDJPY",
                             "EURCAD", "XAUUSD", "BTCUSDT", "ETHUSDT"])
    ap.add_argument("--output-logs", type=Path, default=Path("logs"))
    ap.add_argument("--model-version", default=None,
                    help="Defaults to v5_auto_<UTC date>")
    ap.add_argument("--max-forward-candles", type=int, default=40)
    ap.add_argument("--warmup-candles", type=int, default=30)
    ap.add_argument("--promote-if-approved", action="store_true",
                    help="Call promote_gaussian() if phase5 returns success")
    ap.add_argument("--no-promote", action="store_true",
                    help="Force promotion off even when --promote-if-approved is set")
    ap.add_argument("--phase5-extra", nargs="*", default=[],
                    help="Extra args forwarded verbatim to phase5_calibration.py "
                         "(e.g. --feature-subset retest_depth,...)")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    sys.path.insert(0, str(_REPO_ROOT / "src"))
    # Path side-effects above keep imports below resolvable.

    version = args.model_version or f"v5_auto_{time.strftime('%Y%m%d')}"
    output_dir = args.output_logs
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scan all instruments
    per_instr_paths: list[Path] = []
    for instr in args.instruments:
        p = _scan_instrument(
            args.data_dir, instr, output_dir,
            args.max_forward_candles, args.warmup_candles,
        )
        if p is not None and p.exists():
            per_instr_paths.append(p)

    if not per_instr_paths:
        _LOG.error("No opportunity logs produced — aborting.")
        return 1

    # 2. Merge
    merged_path = output_dir / f"opportunities_merged_{version}.jsonl"
    _merge_logs(per_instr_paths, merged_path)
    _LOG.info("Merged %d files -> %s", len(per_instr_paths), merged_path)

    # 3. Compress (best-effort; do not abort on failure)
    summary_path = output_dir / f"compressed_{version}.json"
    if _compress(merged_path, summary_path) != 0:
        _LOG.warning("Log compression failed — continuing without summary.")

    # 4. (LLM hypertuning round-trip is wired through scripts/groq_bridge/.
    #     Trigger it manually using prepare_retrospective.py + ingest_response.py
    #     with --apply-to-training. This orchestrator runs the deterministic
    #     training pass.)

    # 5. Train
    rc = _train(merged_path, version, args.phase5_extra)
    if rc != 0:
        _LOG.error("Phase-5 calibration failed (rc=%d).", rc)
        return rc

    # 6. Promote
    if args.promote_if_approved and not args.no_promote:
        try:
            _maybe_promote(version)
        except Exception as exc:
            _LOG.error("Promotion step raised: %s", exc)
            return 3

    summary_payload = {
        "version":   version,
        "instruments": args.instruments,
        "merged_log":  str(merged_path),
        "summary":     str(summary_path),
    }
    print(json.dumps(summary_payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
