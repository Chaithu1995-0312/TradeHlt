# -*- coding: utf-8 -*-
"""
qualify_cross_sectional.py — Program 5: cross-sectional relative-value (dispersion) — thin CLI.

Builds the 6-coin close panel, runs the pre-registered interpreter cohort + controls through
`research.cross_sectional.qualify` (which reuses the M4 permutation + Benjamini-Hochberg math
VERBATIM), and writes a deterministic report. It adds NO statistics and touches NO spine/config.

MEASURE-ONLY. The deterministic JSON body carries NO wall-clock (matches the edge_report
discipline); the run manifest (timestamp / git) is written separately.

Pre-registration (frozen design): docs/research-readiness/program-5-cross-sectional-preregistration.md

Usage:
    python scripts/research/qualify_cross_sectional.py
    python scripts/research/qualify_cross_sectional.py --out results/research
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.config import ResearchConfig                         # noqa: E402
from research.cross_sectional import (                             # noqa: E402
    CROSS_SECTIONAL_VERSION, Interpreter, XSQualConfig, load_panel, qualify,
)
from research.provenance import provenance_block                   # noqa: E402
from utils.console_safe import safe_print                          # noqa: E402

CONFIG = "configs/research/research_config_cross_sectional.json"


def _csv_map(cfg: ResearchConfig, instruments: list[str]) -> dict[str, str]:
    data_dir = Path(cfg.data_dir)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _print_table(report: dict) -> None:
    safe_print("\nQUALIFY-CROSS-SECTIONAL — dispersion (6 crypto majors, "
               "intrabar close-to-close, 12bps; alpha=%.2f)\n" % report["alpha"])
    header = (f"| {'Interpreter':14s} | {'kind':9s} | {'L':>5s} | {'H':>4s} | {'n':>6s} | "
              f"{'E(net)':>10s} | {'PF':>7s} | {'win_ctrl':19s} | {'p':>7s} | {'Verdict':11s} |")
    safe_print(header)
    safe_print("|" + "-" * (len(header) - 2) + "|")
    for name in sorted(report["interpreters"]):
        r = report["interpreters"][name]
        safe_print(
            f"| {name:14s} | {r['kind']:9s} | {r['L']:5d} | {r['H']:4d} | {r['n']:6d} | "
            f"{r['expectancy']:+10.6f} | {r['profit_factor']:7.3f} | {r['winning_control']:19s} | "
            f"{r['p_value']:7.4f} | {r['verdict']:11s} |")
    safe_print(f"\nPROMOTE: {report['promoted'] or 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualify_cross_sectional",
        description="Program 5: cross-sectional relative-value (dispersion) qualification")
    parser.add_argument("--out", default="results/research")
    parser.add_argument("--config", default=CONFIG)
    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = ResearchConfig.from_file(args.config)
    xs = raw["cross_sectional"]
    instruments = list(cfg.instruments)

    csv_map = _csv_map(cfg, instruments)
    missing = sorted(set(instruments) - set(csv_map))
    if missing:
        raise SystemExit(f"Missing data for {missing} (pattern {cfg.pattern} in {cfg.data_dir})")

    panel = load_panel(csv_map)
    interpreters = [Interpreter(i["name"], i["kind"], int(i["L"]), int(i["H"]))
                    for i in xs["interpreters"]]
    qcfg = XSQualConfig(
        k=int(xs["k"]),
        min_samples=cfg.q_min_samples,
        expectancy_min=cfg.q_expectancy_min,
        pf_min=cfg.q_pf_min,
        oos_split=cfg.q_oos_split,
        oos_retention_min=cfg.q_oos_retention_min,
        n_permutations=cfg.q_n_permutations,
        significance_alpha=cfg.q_significance_alpha,
        round_trip_bps=cfg.round_trip_bps,
        warmup=cfg.warmup,
    )

    result = qualify(panel, interpreters, qcfg)

    # Deterministic body — NO wall-clock; safe to byte-compare across runs.
    report = {
        "program": "program-5-cross-sectional",
        "cross_sectional_version": CROSS_SECTIONAL_VERSION,
        "config_path": args.config,
        "config_sha256": cfg.sha256(),
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        **result,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cross_sectional_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config_sha256": cfg.sha256(),
        "n_rebalances_total": result["n_rebalances_total"],
    }
    (out_dir / "cross_sectional_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_table(report)
    safe_print(f"\n-> {out_dir / 'cross_sectional_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
