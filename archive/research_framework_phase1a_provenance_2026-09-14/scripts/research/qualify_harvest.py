# -*- coding: utf-8 -*-
"""
qualify_harvest.py — Program 6b: carry HARVEST (funding cashflow + price/basis) — thin CLI.

Builds the 6-coin spot+perp panel and runs the pre-registered harvest cohort through
`research.cross_sectional.qualify_harvest` (reuses the M4 permutation + Benjamini-Hochberg math + the
verdict ladder VERBATIM; adds the `cash` zero benchmark). The measured object is the cashflow a
market-neutral long-low/short-high perp basket accrues (± basis convergence) net of costs.

AUTHORITY SEPARATION: tradeable `harvest_full` interpreters are the ONLY promotion surface; the
funding-only twins are DIAGNOSTIC-only (separate appendix, never PROMOTE, never in BH).

MEASURE-ONLY. Deterministic JSON body (no wall-clock); run manifest written separately.

Pre-registration (frozen design): docs/research-readiness/program-6b-carry-harvest-preregistration.md

Usage:
    python scripts/research/qualify_harvest.py
    python scripts/research/qualify_harvest.py --out results/research
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
    CROSS_SECTIONAL_VERSION, HarvestSpec, XSQualConfig, load_panel, qualify_harvest,
)
from research.provenance import provenance_block                   # noqa: E402
from utils.console_safe import safe_print                          # noqa: E402

CONFIG = "configs/research/research_config_harvest.json"


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


def _row(name: str, r: dict) -> str:
    return (f"| {name:20s} | {r['L']:5d} | {r['H']:5d} | {r['n']:6d} | "
            f"{r['expectancy']:+11.6f} | {r['funding_income']:+11.6f} | {r['profit_factor']:7.3f} | "
            f"{r['winning_control']:19s} | {r['p_value']:7.4f} | {r['verdict']:19s} |")


def _print_tables(report: dict) -> None:
    safe_print("\nQUALIFY-HARVEST — carry cashflow harvest (6 crypto majors, 12bps; alpha=%.2f)\n"
               % report["alpha"])
    head = (f"| {'Interpreter':20s} | {'L':>5s} | {'H':>5s} | {'n':>6s} | {'E(net)':>11s} | "
            f"{'fund_inc':>11s} | {'PF':>7s} | {'win_ctrl':19s} | {'p':>7s} | {'Verdict':19s} |")

    safe_print("== TRADEABLE (harvest_full — the only promotion surface) ==")
    safe_print(head)
    safe_print("|" + "-" * (len(head) - 2) + "|")
    for name in sorted(report["interpreters"]):
        safe_print(_row(name, report["interpreters"][name]))
    safe_print(f"\nPROMOTE: {report['promoted'] or 'none'}")

    safe_print("\n== DIAGNOSTIC APPENDIX (funding-only — NOT tradeable, cannot promote) ==")
    safe_print(head)
    safe_print("|" + "-" * (len(head) - 2) + "|")
    for name in sorted(report["diagnostics"]):
        safe_print(_row(name, report["diagnostics"][name]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualify_harvest",
        description="Program 6b: carry HARVEST (funding cashflow + price/basis)")
    parser.add_argument("--out", default="results/research")
    parser.add_argument("--config", default=CONFIG)
    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = ResearchConfig.from_file(args.config)
    hv = raw["harvest"]
    perp_dir = raw["universe"]["perp_dir"]
    instruments = list(cfg.instruments)

    csv_map = _csv_map(cfg, instruments)
    missing = sorted(set(instruments) - set(csv_map))
    if missing:
        raise SystemExit(f"Missing data for {missing} (pattern {cfg.pattern} in {cfg.data_dir})")

    panel = load_panel(csv_map, perp_dir=perp_dir)
    specs = [HarvestSpec(s["name"], int(s["L"]), int(s["H"]), bool(s["include_price"]))
             for s in hv["specs"]]
    qcfg = XSQualConfig(
        k=int(hv["k"]),
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

    result = qualify_harvest(panel, specs, qcfg)

    report = {
        "program": "program-6b-carry-harvest",
        "cross_sectional_version": CROSS_SECTIONAL_VERSION,
        "config_path": args.config,
        "config_sha256": cfg.sha256(),
        "perp_dir": perp_dir,
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        **result,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "harvest_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config_sha256": cfg.sha256(),
        "n_rebalances_total": result["n_rebalances_total"],
    }
    (out_dir / "harvest_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")

    _print_tables(report)
    safe_print(f"\n-> {out_dir / 'harvest_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
