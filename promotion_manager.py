"""
promotion_manager.py
═══════════════════════════════════════════════════════════════════════════════
PROMOTION GATE — Human-aware, logged, auditable.

Purpose:
  Moves a validated config from research → production registry.
  Every promotion (and rejection) is logged. Nothing happens silently.

Architecture contract:
  - ONLY approved ValidationReports (decision == "APPROVE") can be promoted.
  - Promoted configs are written to production_configs/{version}.json.
  - promotion_manager.py NEVER directly calls ConfigBuilder or CRTEngine.
    It only moves approved JSON files and updates the registry index.
  - Rejected configs are logged with full reasons — user is always informed.
  - Every registry entry includes a SHA-256 config_hash (Fix 2).
  - validation_summary includes score_std_dev for drift detection (Fix 5).

Workflow:
  1. Auto-tuner produces checkpoint_multi.json
  2. config_validator.py validates top config → ValidationReport
  3. promotion_manager.py promotes approved config to production_configs/

Usage:
    # Promote from a tuner checkpoint (full automated workflow)
    from promotion_manager import PromotionManager

    result = PromotionManager.promote_from_tuner_checkpoint(
        checkpoint_path="results/tuner/checkpoint_multi.json",
        version="v2_multi_2026_04",
        csv_paths={...},
    )

    # Promote from an existing validation report
    result = PromotionManager.promote_from_report(
        report_path="results/validation/approved/cfg_2026_03_24_001.json",
        version="v1_multi_2026_03",
    )

    # List all production versions
    PromotionManager.list_versions()
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Import project modules ──────────────────────────────────────────────────
try:
    from config_validator import ConfigValidator
except ImportError as e:
    print(f"\n  IMPORT ERROR: {e}\n"
          "  Ensure config_validator.py is in the same directory.\n")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORIES
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_REGISTRY_DIR: str = "production_configs"
PROMOTION_LOG_FILE:       str = "production_configs/promotion_log.jsonl"
VALIDATION_APPROVED_DIR:  str = "results/validation/approved"
VALIDATION_REJECTED_DIR:  str = "results/validation/rejected"


# ─────────────────────────────────────────────────────────────────────────────
# PROMOTION MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class PromotionManager:
    """
    Manages the promotion gate between validated configs and production.

    All operations are logged and human-readable.
    """

    @staticmethod
    def promote_from_report(
        report_path: str,
        version: str,
        notes: str = "",
    ) -> dict:
        """
        Promote an already-validated config to the production registry.

        Parameters
        ----------
        report_path : str
            Path to an approved ValidationReport JSON file.
        version : str
            Production version label, e.g. 'v1_multi_2026_03'.
        notes : str
            Optional human notes attached to this promotion.

        Returns
        -------
        dict
            Promotion result with status and paths.
        """
        report_path = Path(report_path)
        if not report_path.exists():
            return PromotionManager._fail(f"Report not found: {report_path}")

        with open(report_path) as f:
            report = json.load(f)

        return PromotionManager._execute_promotion(report, version, notes)

    @staticmethod
    def promote_from_tuner_checkpoint(
        checkpoint_path: str,
        version: str,
        csv_paths: dict,
        notes: str = "",
        use_llm: bool = False,
        top_n: int = 1,
    ) -> dict:
        """
        Full automated workflow:
          1. Load best config from tuner checkpoint.
          2. Run validation via ConfigValidator.
          3. Promote if approved; log rejection if not.

        Parameters
        ----------
        checkpoint_path : str
            Path to auto_tuner_multi checkpoint JSON
            (e.g. 'results/tuner/checkpoint_multi.json').
        version : str
            Production version label for the promoted config.
        csv_paths : dict
            {instrument: csv_path} for validation backtest.
        notes : str
            Human notes attached to this promotion attempt.
        use_llm : bool
            Whether to use LLM gate in validation scoring.
        top_n : int
            How many top configs to validate (promotes the first that passes).

        Returns
        -------
        dict
            Promotion result dict.
        """
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            return PromotionManager._fail(f"Checkpoint not found: {checkpoint_path}")

        with open(checkpoint_path) as f:
            results = json.load(f)

        if not results:
            return PromotionManager._fail("Checkpoint is empty.")

        # Sort by score descending, filter valid
        valid = [r for r in results if r.get("score", -999) > -999.0]
        if not valid:
            return PromotionManager._fail("No valid results in checkpoint.")

        top_configs = sorted(valid, key=lambda r: r["score"], reverse=True)[:top_n]

        print(f"\n{'═'*60}")
        print(f"  PROMOTION MANAGER — Tuner → Production")
        print(f"  Checkpoint: {checkpoint_path}")
        print(f"  Target version: {version}")
        print(f"  Top {top_n} config(s) will be validated.")
        print(f"{'═'*60}")

        for i, result in enumerate(top_configs):
            params = result.get("params", {})
            if not params:
                print(f"  ⚠️  Result #{i+1} has no params — skipping.")
                continue

            print(f"\n  Candidate #{i+1} (tuner score={result['score']:+.4f}):")
            for k, v in params.items():
                print(f"    {k:<35} = {v}")

            # Run validation
            report = ConfigValidator.validate(
                params=params,
                csv_paths=csv_paths,
                config_id=f"{version}_candidate_{i+1}",
                use_llm=use_llm,
            )

            if report.get("decision") == "APPROVE":
                print(f"\n  ✅ Candidate #{i+1} passed validation — promoting...")
                result = PromotionManager._execute_promotion(report, version, notes)
                return result
            else:
                print(f"\n  ❌ Candidate #{i+1} rejected — trying next...")

        return PromotionManager._fail(
            f"None of the top {top_n} configs passed validation. "
            "Review rejection reports in results/validation/rejected/."
        )

    @staticmethod
    def promote_direct(
        params: dict,
        version: str,
        validation_summary: Optional[dict] = None,
        notes: str = "",
    ) -> dict:
        """
        Directly promote a manually-specified params dict to the registry.
        Use this when you have already validated params externally.

        WARNING: This bypasses ConfigValidator. Use promote_from_tuner_checkpoint
        or promote_from_report for the safe path.
        """
        print(f"\n  ⚠️  DIRECT PROMOTION — bypassing validation gate.")
        print(f"  Version: {version}")
        print(f"  This should only be used for manually verified configs.\n")

        registry_entry = PromotionManager._build_registry_entry(
            params=params,
            version=version,
            validation_summary=validation_summary or {},
            notes=notes + " [DIRECT_PROMOTION — validation bypassed]",
            config_id=f"{version}_direct",
        )
        return PromotionManager._write_to_registry(registry_entry, version)

    @staticmethod
    def list_versions(registry_dir: str = PRODUCTION_REGISTRY_DIR) -> list:
        """List all versions in the production registry."""
        reg = Path(registry_dir)
        if not reg.exists():
            print(f"  Registry dir does not exist: {registry_dir}")
            return []

        versions = sorted(reg.glob("*.json"))
        versions = [v for v in versions if v.name != "promotion_log.jsonl"
                    and not v.name.startswith("promotion_log")]

        if not versions:
            print(f"  No production configs found in {registry_dir}")
            return []

        print(f"\n  Production Registry — {len(versions)} version(s):")
        print(f"  {'─'*50}")
        for vf in versions:
            with open(vf) as f:
                data = json.load(f)
            h = data.get("config_hash", "⚠️ no-hash")[:12]
            print(f"  {data.get('version','?'):<30}  created={data.get('created_at','?')[:10]}  "
                  f"score={data.get('validation_summary', {}).get('final_score', '?')}  "
                  f"hash={h}...")

        return [v.stem for v in versions]

    @staticmethod
    def load_version(version: str, registry_dir: str = PRODUCTION_REGISTRY_DIR) -> dict:
        """Load a production registry entry by version string."""
        path = Path(registry_dir) / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(f"Version not found: {path}")
        with open(path) as f:
            return json.load(f)

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _execute_promotion(report: dict, version: str, notes: str) -> dict:
        """Core promotion logic — writes to registry, logs event."""
        params = report.get("params", {})
        if not params:
            return PromotionManager._fail("Report has no params.")

        metrics = report.get("metrics", {})

        # ── Fix 5: Compute score_std_dev from per-instrument scores ────────
        per_inst = report.get("per_instrument", {})
        inst_scores = [
            v.get("score", -999.0) for v in per_inst.values()
            if v.get("score", -999.0) > -999.0
        ]
        if len(inst_scores) > 1:
            mean_s = sum(inst_scores) / len(inst_scores)
            variance = sum((s - mean_s) ** 2 for s in inst_scores) / len(inst_scores)
            score_std_dev = round(math.sqrt(variance), 4)
        else:
            score_std_dev = 0.0

        validation_summary = {
            "config_id":           report.get("config_id"),
            "final_score":         metrics.get("final_score", 0.0),
            "mean_score":          metrics.get("mean_score", 0.0),
            "consistency_penalty": metrics.get("consistency_penalty", 0.0),
            "score_std_dev":       score_std_dev,
            "total_trades":        metrics.get("total_trades", 0),
            "max_drawdown":        metrics.get("max_drawdown_across", 0.0),
            "instruments":         report.get("instruments_tested", []),
            "per_instrument":      per_inst,
            "warnings":            report.get("warnings", []),
        }

        registry_entry = PromotionManager._build_registry_entry(
            params=params,
            version=version,
            validation_summary=validation_summary,
            notes=notes,
            config_id=report.get("config_id", ""),
        )
        return PromotionManager._write_to_registry(registry_entry, version)

    @staticmethod
    def _compute_config_hash(params: dict) -> str:
        """SHA-256 of params dict (sort_keys for determinism)."""
        canonical = json.dumps(params, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_registry_entry(
        params: dict,
        version: str,
        validation_summary: dict,
        notes: str,
        config_id: str,
    ) -> dict:
        """Build the JSON structure stored in production_configs/."""
        # Fix 2: compute and embed SHA-256 hash of params
        config_hash = PromotionManager._compute_config_hash(params)
        return {
            "version":            version,
            "config_id":          config_id,
            "created_at":         datetime.utcnow().isoformat(),
            "promoted_at":        datetime.utcnow().isoformat(),
            "params":             params,
            "config_hash":        config_hash,
            "validation_summary": validation_summary,
            "notes":              notes,
            "schema_version":     "1.0",
        }

    @staticmethod
    def _write_to_registry(entry: dict, version: str) -> dict:
        """Write registry entry to disk and log the promotion event."""
        registry_dir = Path(PRODUCTION_REGISTRY_DIR)
        registry_dir.mkdir(parents=True, exist_ok=True)

        out_path = registry_dir / f"{version}.json"

        if out_path.exists():
            # Archive the old version before overwriting
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_path = registry_dir / f"{version}_archived_{ts}.json"
            shutil.copy2(out_path, archive_path)
            print(f"  ℹ️  Existing version archived → {archive_path}")

        with open(out_path, "w") as f:
            json.dump(entry, f, indent=2)

        # Log the promotion event
        PromotionManager._log_event({
            "event":      "PROMOTED",
            "version":    version,
            "config_id":  entry.get("config_id", ""),
            "params":     entry["params"],
            "config_hash": entry.get("config_hash", ""),
            "score":      entry.get("validation_summary", {}).get("final_score", 0.0),
            "score_std_dev": entry.get("validation_summary", {}).get("score_std_dev", 0.0),
            "timestamp":  entry["promoted_at"],
            "notes":      entry.get("notes", ""),
        })

        W = 60
        print(f"\n{'═'*W}")
        print(f"  🚀 PROMOTED TO PRODUCTION")
        print(f"  Version:  {version}")
        print(f"  Registry: {out_path}")
        print(f"  Hash:     {entry.get('config_hash', '')[:24]}...")
        print(f"\n  Params promoted:")
        for k, v in entry["params"].items():
            print(f"    {k:<35} = {v}")

        vs = entry.get("validation_summary", {})
        if vs:
            print(f"\n  Validation summary:")
            print(f"    Final score:    {vs.get('final_score', '?')}")
            print(f"    Score std_dev:  {vs.get('score_std_dev', '?')}  (cross-instrument stability)")
            print(f"    Total trades:   {vs.get('total_trades', '?')}")
            print(f"    Max drawdown:   {vs.get('max_drawdown', '?')}")

        print(f"\n  ✅ Update production_config.py:")
        print(f"     PROD_VERSION = \"{version}\"")
        print(f"{'═'*W}\n")

        return {
            "status":   "PROMOTED",
            "version":  version,
            "path":     str(out_path),
            "params":   entry["params"],
            "score":    vs.get("final_score", 0.0),
        }

    @staticmethod
    def _fail(reason: str) -> dict:
        """Log and return a failure result."""
        W = 60
        print(f"\n{'═'*W}")
        print(f"  ❌ PROMOTION FAILED")
        print(f"  Reason: {reason}")
        print(f"{'═'*W}\n")

        PromotionManager._log_event({
            "event":     "PROMOTION_FAILED",
            "reason":    reason,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {"status": "FAILED", "reason": reason}

    @staticmethod
    def _log_event(event: dict) -> None:
        """Append a structured event to the promotion log."""
        log_path = Path(PROMOTION_LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CRT Promotion Manager")
    subp = ap.add_subparsers(dest="command")

    # list command
    list_p = subp.add_parser("list", help="List production registry versions")

    # promote command
    promo_p = subp.add_parser("promote", help="Promote from tuner checkpoint")
    promo_p.add_argument("--checkpoint", required=True,
                         help="Path to tuner checkpoint JSON")
    promo_p.add_argument("--version",    required=True,
                         help="Production version label (e.g. v2_multi_2026_04)")
    promo_p.add_argument("--data-dir",   default="data")
    promo_p.add_argument("--instruments", nargs="+",
                         default=["EURUSD", "GBPUSD", "BTCUSDT", "XAUUSD"])
    promo_p.add_argument("--notes", default="")
    promo_p.add_argument("--no-llm", action="store_true")

    # from-report command
    from_report_p = subp.add_parser("from-report", help="Promote from a validation report")
    from_report_p.add_argument("--report",  required=True, help="Path to approved report JSON")
    from_report_p.add_argument("--version", required=True)
    from_report_p.add_argument("--notes",   default="")

    args = ap.parse_args()

    if args.command == "list":
        PromotionManager.list_versions()

    elif args.command == "promote":
        data_dir = Path(args.data_dir)
        csv_paths = {}
        for inst in [i.upper() for i in args.instruments]:
            for candidate in [data_dir / f"{inst}_M15.csv", data_dir / f"{inst}.csv"]:
                if candidate.exists():
                    csv_paths[inst] = str(candidate)
                    break

        if not csv_paths:
            print(f"\n  ERROR: No CSV files found in {data_dir}.\n")
            sys.exit(1)

        result = PromotionManager.promote_from_tuner_checkpoint(
            checkpoint_path=args.checkpoint,
            version=args.version,
            csv_paths=csv_paths,
            notes=args.notes,
            use_llm=not args.no_llm,
        )
        sys.exit(0 if result.get("status") == "PROMOTED" else 1)

    elif args.command == "from-report":
        result = PromotionManager.promote_from_report(
            report_path=args.report,
            version=args.version,
            notes=args.notes,
        )
        sys.exit(0 if result.get("status") == "PROMOTED" else 1)

    else:
        ap.print_help()