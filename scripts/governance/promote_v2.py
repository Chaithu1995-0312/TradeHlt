"""
promote_v2.py — thin CLI wrapper for the multi-strategy governance promotion.

Usage:
    python scripts/governance/promote_v2.py [--dry-run] [--version V]

Steps:
    1. MultiStrategyValidator.validate()  — backtest all 10 strategies
    2. Write ValidationReport to results/validation/{approved|rejected}/
    3. PromotionManager.promote_from_report()  — push to configs/production/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from governance.multi_strategy_validator import MultiStrategyValidator
from governance.promotion_manager import PromotionManager


CSV_PATHS = {
    "EURUSD": str(_ROOT / "data" / "EURUSD_M15.csv"),
    "GBPUSD": str(_ROOT / "data" / "GBPUSD_M15.csv"),
    "AUDUSD": str(_ROOT / "data" / "AUDUSD_M15.csv"),
}

_W = 60


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote 10-strategy v2 config")
    parser.add_argument("--version", default="v2_multi_2026_04",
                        help="Production version label (default: v2_multi_2026_04)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate only — do not write to production registry")
    parser.add_argument("--config-id", default="multi_strategy_v2_2026_05",
                        help="Config ID label for the validation report")
    args = parser.parse_args()

    print(f"\n{'='*_W}")
    print(f"  MULTI-STRATEGY GOVERNANCE PROMOTION")
    print(f"  Version: {args.version}")
    print(f"  Dry-run: {args.dry_run}")
    print(f"{'='*_W}\n")

    # Step 1 — Validate
    validator = MultiStrategyValidator()
    report = validator.validate(csv_paths=CSV_PATHS, config_id=args.config_id)

    decision     = report.get("decision", "REJECT")
    hard_failures = report.get("hard_failures", [])
    warnings     = report.get("warnings", [])
    metrics      = report.get("metrics", {})

    print(f"\n  Decision:      {decision}")
    print(f"  Mean score:    {metrics.get('mean_score', 0.0):.4f}")
    print(f"  Total trades:  {metrics.get('total_trades', 0)}")
    print(f"  Portfolio WR:  {metrics.get('portfolio_win_rate', 0.0):.1%}")
    if hard_failures:
        print(f"\n  Hard failures ({len(hard_failures)}):")
        for f in hard_failures:
            print(f"    - {f}")
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"    - {w}")

    # Step 2 — Write report to disk
    out_dir = _ROOT / "results" / "validation" / (
        "approved" if decision == "APPROVE" else "rejected"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"{args.config_id}_{ts}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  Report written: {out}")

    if decision != "APPROVE":
        print("\n  Promotion BLOCKED — validation did not APPROVE.")
        sys.exit(1)

    if args.dry_run:
        print("\n  DRY-RUN — skipping promotion registry write.")
        sys.exit(0)

    # Step 3 — Promote
    result = PromotionManager.promote_from_report(
        report_path=str(out),
        version=args.version,
        notes=f"Automated 10-strategy promotion — {ts}",
    )
    status = result.get("status", "unknown")
    print(f"\n  Promotion status: {status}")
    if status == "promoted":
        print(f"  Registry entry:   {result.get('registry_path')}")
        print(f"  Config hash:      {result.get('config_hash', '')[:16]}...")
    else:
        print(f"  Reason: {result.get('reason', '')}")
    print(f"\n{'='*_W}\n")


if __name__ == "__main__":
    main()
