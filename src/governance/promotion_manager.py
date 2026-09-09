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

    # Promote from an existing validation report (csv_paths required for re-validation)
    result = PromotionManager.promote_from_report(
        report_path="results/validation/approved/cfg_2026_03_24_001.json",
        version="v1_multi_2026_03",
        csv_paths={"EURUSD": "data/EURUSD_M15.csv", "GBPUSD": "data/GBPUSD_M15.csv"},
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path bootstrap — ensures src/ is importable when run as a script ────────
_SRC = Path(__file__).resolve().parent.parent   # src/governance/../../  → src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── Import project modules ──────────────────────────────────────────────────
try:
    from config_layer.config_validator import ConfigValidator
except ImportError as e:
    print(f"\n  IMPORT ERROR: {e}\n"
          "  Ensure config_validator.py is in src/config_layer/.\n")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# DIRECTORIES
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_REGISTRY_DIR: str = "configs/production"
PROMOTION_LOG_FILE:       str = "configs/promotion_log.jsonl"
VALIDATION_APPROVED_DIR:  str = "results/validation/approved"
VALIDATION_REJECTED_DIR:  str = "results/validation/rejected"

# Sentinel key that only full configs possess.
# A config missing this key is a sparse tuner-params-only file and must NOT
# be used as a base for merging or as ACTIVE_VERSION.
_FULL_CONFIG_SENTINEL: str = "engine_runner"

# Hardcoded fallback base — always the original fully-specified config.
# All promoted configs are merged ON TOP of this base so that every engine
# section (engine_runner, fusion_engine, llama_gate, …) is always present
# in the promoted file, even when the tuner only optimises the params section.
_BASE_VERSION_FALLBACK: str = "v1_multi_2026_03"


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
        csv_paths: dict,
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
        csv_paths : dict
            {instrument: csv_path} dict. Re-runs ConfigValidator on the report's
            params before promoting to guard against stale or tampered reports.
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

        # GAP-4 fix: enforce decision gate — never promote a non-APPROVE report.
        # The original code trusted the JSON on disk without checking this field.
        if report.get("decision") != "APPROVE":
            return PromotionManager._fail(
                f"Report decision is '{report.get('decision', 'MISSING')}' "
                f"(path: {report_path}) — only APPROVE reports can be promoted. "
                f"Re-run validation and check rejection reasons."
            )

        # GAP-4 fix: when csv_paths provided, re-run ConfigValidator to confirm
        # the report is still current (not stale from a previous config version).
        params = report.get("params", {})
        if not params:
            return PromotionManager._fail(
                "Report has no 'params' key — cannot re-validate. "
                "Promote from tuner checkpoint instead."
            )
        print(f"\n  Re-running ConfigValidator to verify report is current…")
        fresh_report = ConfigValidator.validate(
            params=params,
            csv_paths=csv_paths,
            config_id=f"{version}_re_validate",
        )
        if fresh_report.get("decision") != "APPROVE":
            return PromotionManager._fail(
                f"Re-validation FAILED — report may be stale or tampered. "
                f"Original decision: APPROVE. Fresh decision: {fresh_report.get('decision')}. "
                f"Warnings: {fresh_report.get('warnings', [])}. "
                f"Re-tune and re-validate before promoting."
            )
        print(f"  Re-validation passed — using fresh metrics for promotion.")
        report = fresh_report  # use freshly validated metrics

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
        """
        Load a production registry entry by version string.

        GAP-5 fix: validates the stored SHA-256 config_hash against the
        params dict on every load.  Raises RuntimeError on mismatch — the
        file may have been tampered with after promotion.
        """
        path = Path(registry_dir) / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(f"Version not found: {path}")
        with open(path) as f:
            data = json.load(f)

        # GAP-5 fix: integrity check — recompute hash and compare to stored value
        stored_hash = data.get("config_hash")
        params      = data.get("params")
        if stored_hash and params:
            actual_hash = PromotionManager._compute_config_hash(params)
            if actual_hash != stored_hash:
                raise RuntimeError(
                    f"Config integrity check FAILED for version '{version}': "
                    f"stored={stored_hash[:16]}… actual={actual_hash[:16]}…. "
                    f"The config file may have been modified after promotion. "
                    f"Re-promote from a validated checkpoint to restore integrity."
                )
        elif stored_hash and not params:
            print(
                f"  ⚠️  load_version: version '{version}' has a config_hash but no "
                f"'params' key — hash not validated (sparse config)."
            )

        return data

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _execute_promotion(report: dict, version: str, notes: str) -> dict:
        """Core promotion logic — writes to registry, logs event."""
        # GAP-4 safety backstop: _execute_promotion should only ever receive
        # APPROVE reports.  promote_from_tuner_checkpoint checks this before
        # calling; promote_from_report now also checks.  This guard catches any
        # direct callers that bypass those entry points.
        if report.get("decision") is not None and report.get("decision") != "APPROVE":
            return PromotionManager._fail(
                f"_execute_promotion safety gate: report decision='"
                f"{report.get('decision')}' is not APPROVE — promotion rejected."
            )
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
        # [trust-layer F5, 2026-06-10] This is the FULL std-dev of cross-instrument
        # fitness scores, logged as promotion telemetry (`validation_summary`). It is
        # distinct from ConfigValidator's `consistency_penalty` (= half this std, folded
        # into final_score as a penalty) — different role, not a duplicate computation.
        # Field name kept as-is: promotion_log.jsonl schema is load-bearing.
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
            "promoted_version":   version,
            "config_id":          config_id,
            "created_at":         datetime.now(timezone.utc).isoformat(),
            "promoted_at":        datetime.now(timezone.utc).isoformat(),
            "params":             params,
            "config_hash":        config_hash,
            "validation_summary": validation_summary,
            "notes":              notes,
            "schema_version":     "1.0",
        }

    @staticmethod
    def _load_full_base_config(
        registry_dir: Path | None = None,
    ) -> dict | None:
        """
        Load the best available FULL production config to use as a merge base.

        A "full" config is one that contains the _FULL_CONFIG_SENTINEL key
        (``engine_runner``).  Tuner-promoted sparse configs are intentionally
        excluded so they are never used as a base.

        Search order
        ────────────
        1. ``_BASE_VERSION_FALLBACK`` (``v1_multi_2026_03``) — the canonical
           baseline that always carries all engine sections.
        2. If that file is absent or is itself sparse, scan the registry for any
           other full config (most-recently-modified wins) to handle renamed bases.
        3. Return ``None`` if nothing suitable is found.

        Returns
        -------
        dict | None
            Parsed JSON of the full base config, or None if unavailable.
        """
        if registry_dir is None:
            registry_dir = Path(PRODUCTION_REGISTRY_DIR)

        # ── 1. Preferred fallback ──────────────────────────────────────────
        preferred = registry_dir / f"{_BASE_VERSION_FALLBACK}.json"
        if preferred.exists():
            # utf-8 explicit: production configs carry box-drawing/math glyphs in comments
            # that break Windows' cp1252 default (the trap this session hit repeatedly
            # elsewhere) -- bare open() here made this function unusable on Windows.
            with open(preferred, encoding="utf-8") as f:
                cfg = json.load(f)
            if _FULL_CONFIG_SENTINEL in cfg:
                return cfg
            print(f"  ⚠️  Base fallback {_BASE_VERSION_FALLBACK}.json is itself "
                  f"sparse (missing '{_FULL_CONFIG_SENTINEL}') — scanning registry …")

        # ── 2. Scan registry for any full config ──────────────────────────
        candidates = sorted(
            registry_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,       # newest first
        )
        for path in candidates:
            # Skip archived copies and the promotion log
            if "archived" in path.name or "promotion_log" in path.name:
                continue
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            if _FULL_CONFIG_SENTINEL in cfg:
                print(f"  ℹ️  Using {path.name} as merge base (fallback scan).")
                return cfg

        return None

    @staticmethod
    def _write_to_registry(entry: dict, version: str) -> dict:
        """
        Write the promoted config to disk and log the promotion event.

        MERGE STRATEGY (governance gap fix)
        ────────────────────────────────────
        Tuner checkpoints only contain the 5 ``params`` keys.
        ``_build_registry_entry()`` produces a sparse dict (no engine sections).
        Writing that sparse dict as the new ACTIVE_VERSION would break
        ``get_prod_section()`` for every engine on next import.

        Fix: load the full base config (``_load_full_base_config()``), clone it,
        then overlay only the metadata + params keys from ``entry``.  This
        guarantees every promoted file is a fully-specified config.

        Fallback: if no full base is available (first-ever run, corrupted
        registry), log a WARNING and write the sparse entry as before.
        """
        registry_dir = Path(PRODUCTION_REGISTRY_DIR)
        registry_dir.mkdir(parents=True, exist_ok=True)

        out_path = registry_dir / f"{version}.json"

        # ── Merge-into-base ───────────────────────────────────────────────
        # schema_version is intentionally excluded: _build_registry_entry()
        # hardcodes "1.0" but the full base config carries the correct value
        # ("1.3").  Inheriting it from the base avoids a silent downgrade.
        _METADATA_KEYS = (
            "version", "promoted_version", "config_id", "created_at", "promoted_at",
            "params", "config_hash", "validation_summary", "notes",
        )

        base_cfg = PromotionManager._load_full_base_config(registry_dir)
        if base_cfg is not None:
            # Deep clone base so we never mutate the loaded dict
            merged = json.loads(json.dumps(base_cfg))
            # Overlay only the promotion metadata — all engine sections are
            # inherited from base and remain intact.
            for key in _METADATA_KEYS:
                if key in entry:
                    merged[key] = entry[key]
            payload = merged
            print(f"  ℹ️  Merged promotion metadata into full base config "
                  f"({_BASE_VERSION_FALLBACK}) — all engine sections preserved.")
        else:
            # No full base available — sparse write with visible warning.
            payload = entry
            print(
                f"\n  ⚠️  WARNING: No full base config found "
                f"(expected '{_BASE_VERSION_FALLBACK}.json' with "
                f"'{_FULL_CONFIG_SENTINEL}' key).\n"
                f"     Promoting sparse config — get_prod_section() calls for "
                f"engine sections WILL FAIL until a full config is restored.\n"
            )

        if out_path.exists():
            # Archive the old version before overwriting
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_path = registry_dir / f"{version}_archived_{ts}.json"
            shutil.copy2(out_path, archive_path)
            print(f"  ℹ️  Existing version archived → {archive_path}")

        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)

        # Write ACTIVE_VERSION pointer — production_config.py resolves PROD_VERSION
        # from this file at import time so no manual code edit is required.
        active_version_path = registry_dir / "ACTIVE_VERSION"
        active_version_path.write_text(version + "\n", encoding="utf-8")

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

        print(f"\n  ✅ ACTIVE_VERSION pointer updated — PROD_VERSION auto-resolves on next import.")
        print(f"     configs/production/ACTIVE_VERSION → \"{version}\"")
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
    from_report_p.add_argument("--version", default=None,
                               help="Version label; defaults to config_id from the report")
    from_report_p.add_argument("--notes",   default="")
    from_report_p.add_argument("--data-dir", required=True,
                               help="Directory containing per-instrument CSV files (required for re-validation)")
    from_report_p.add_argument("--instruments", nargs="+",
                               default=["EURUSD", "GBPUSD", "BTCUSDT", "XAUUSD"],
                               help="Instruments to validate against (default: EURUSD GBPUSD BTCUSDT XAUUSD)")

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
        version = args.version
        if version is None:
            import json as _json
            with open(args.report) as _f:
                _rpt = _json.load(_f)
            version = _rpt.get("config_id")
            if not version:
                ap.error("--version is required: report contains no config_id to derive from")
            print(f"[promotion_manager] --version not supplied; using config_id '{version}' from report")
        data_dir = Path(args.data_dir)
        csv_paths = {}
        for inst in [i.upper() for i in args.instruments]:
            for candidate in [data_dir / f"{inst}_M15.csv", data_dir / f"{inst}.csv"]:
                if candidate.exists():
                    csv_paths[inst] = str(candidate)
                    break
        if not csv_paths:
            print(f"\n  ERROR: No CSV files found in {data_dir} for instruments {args.instruments}.\n")
            sys.exit(1)
        result = PromotionManager.promote_from_report(
            report_path=args.report,
            version=version,
            notes=args.notes,
            csv_paths=csv_paths,
        )
        sys.exit(0 if result.get("status") == "PROMOTED" else 1)

    else:
        ap.print_help()