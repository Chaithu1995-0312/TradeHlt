"""
config_validator.py
═══════════════════════════════════════════════════════════════════════════════
CONFIG VALIDATION ENGINE — Hard rejection rules, auditable reports.

Purpose:
  Validates a candidate param dict BEFORE it can be promoted to production.
  Every config is scored, flagged, and stored — nothing disappears silently.

Architecture contract:
  - Uses ConfigBuilder.build() exclusively (no direct CRTConfig construction).
  - Runs multi-instrument backtests internally (reuses auto_tuner_multi workers).
  - Produces a structured ValidationReport for every candidate.
  - Stores APPROVE → results/validation/approved/
  - Stores REJECT  → results/validation/rejected/
  - Notifies user clearly when a config is rejected.

Hard rejection rules (non-negotiable):
  1. Any single instrument score < 0.20  → REJECT  (weak on one market)
  2. Score std_dev across instruments > 0.25 → REJECT  (unstable)
  3. Total trades (any instrument) < 30  → REJECT  (insufficient sample)
  4. Max drawdown (any instrument) > 0.35 → REJECT  (excessive risk)

Usage:
    from config_validator import ConfigValidator

    report = ConfigValidator.validate(
        params={
            "retest_depth_max": 0.30,
            "retest_atr_depth_fraction": 0.50,
            "body_ratio_min": 0.65,
            "atr_multiplier_min": 1.50,
            "expansion_atr_min_distance": 0.20,
        },
        csv_paths={
            "EURUSD":  "data/EURUSD_M15.csv",
            "GBPUSD":  "data/GBPUSD_M15.csv",
            "BTCUSDT": "data/BTCUSDT_M15.csv",
            "XAUUSD":  "data/XAUUSD_M15.csv",
        },
    )

    if report["decision"] == "APPROVE":
        print("Config approved — ready for promotion.")
    else:
        print(f"Rejected: {report['rejection_reasons']}")
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Import project modules ──────────────────────────────────────────────────
try:
    from auto_tuner_multi import (
        _run_single_instrument,
        fitness_single,
        fitness_multi,
        INSTRUMENT_PIP,
    )
    from config_builder import ConfigBuilder
    from backtest_v2 import BacktestConfig
except ImportError as e:
    print(f"\n  IMPORT ERROR: {e}\n"
          "  Ensure auto_tuner_multi.py, config_builder.py, backtest_v2.py "
          "are in the same directory.\n")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# HARD REJECTION THRESHOLDS  (non-negotiable — do not relax without reason)
# ─────────────────────────────────────────────────────────────────────────────

REJECT_INST_SCORE_MIN:    float = 0.20   # any instrument below this → reject
REJECT_STD_DEV_MAX:       float = 0.25   # cross-instrument instability limit
REJECT_TRADE_COUNT_MIN:   int   = 30     # statistical power floor
REJECT_MAX_DRAWDOWN_MAX:  float = 0.35   # maximum acceptable drawdown

# Soft warning thresholds (flagged but not auto-rejected)
WARN_INST_SCORE_MIN:  float = 0.35
WARN_TRADE_COUNT_MIN: int   = 50
WARN_DRAWDOWN_MAX:    float = 0.25


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION REPORT STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InstrumentResult:
    instrument:     str
    score:          float
    trades:         int
    win_rate:       float
    expectancy_rr:  float
    max_drawdown:   float
    total_pnl_rr:   float
    error:          Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    config_id:          str
    params:             dict
    created_at:         str
    instruments_tested: list

    # Aggregate metrics
    mean_score:           float = 0.0
    consistency_penalty:  float = 0.0
    final_score:          float = 0.0
    total_trades:         int   = 0
    max_drawdown_across:  float = 0.0

    # Per-instrument breakdown
    per_instrument: dict = field(default_factory=dict)

    # Flags
    flags: dict = field(default_factory=lambda: {
        "low_trade_count":    False,
        "high_drawdown":      False,
        "overfit_risk":       False,
        "instability":        False,
        "weak_instrument":    False,
    })

    # Outcome
    decision:          str  = "PENDING"   # "APPROVE" | "REJECT"
    rejection_reasons: list = field(default_factory=list)
    warnings:          list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "config_id":          self.config_id,
            "params":             self.params,
            "created_at":         self.created_at,
            "instruments_tested": self.instruments_tested,
            "metrics": {
                "mean_score":          round(self.mean_score, 4),
                "consistency_penalty": round(self.consistency_penalty, 4),
                "final_score":         round(self.final_score, 4),
                "total_trades":        self.total_trades,
                "max_drawdown_across": round(self.max_drawdown_across, 4),
            },
            "per_instrument":   self.per_instrument,
            "flags":            self.flags,
            "decision":         self.decision,
            "rejection_reasons": self.rejection_reasons,
            "warnings":         self.warnings,
        }


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

class ConfigValidator:
    """
    Validates a candidate param dict against multi-instrument backtests.

    All rejection rules are hard-coded and logged. Nothing fails silently.
    """

    RESULTS_BASE: str = "results/validation"

    @staticmethod
    def validate(
        params:           dict,
        csv_paths:        dict,           # {instrument: csv_path}
        output_dir:       str  = "results/validation/runs",
        use_llm:          bool = False,   # False for deterministic validation
        config_id:        Optional[str] = None,
    ) -> dict:
        """
        Run full multi-instrument validation for a candidate params dict.

        Parameters
        ----------
        params : dict
            Keys must be valid CRTConfig field names (validated by ConfigBuilder).
        csv_paths : dict
            {instrument_name: csv_file_path}
        output_dir : str
            Where per-instrument backtest artifacts are written.
        use_llm : bool
            If True, applies LLM gate in scoring (slower). Default False for
            deterministic production validation.
        config_id : str | None
            Optional identifier. Auto-generated UUID if not provided.

        Returns
        -------
        dict
            Serialisable ValidationReport dict.
        """
        if config_id is None:
            ts = datetime.utcnow().strftime("%Y_%m_%d_%H%M%S")
            config_id = f"cfg_{ts}_{uuid.uuid4().hex[:6]}"

        report = ValidationReport(
            config_id=config_id,
            params=params,
            created_at=datetime.utcnow().isoformat(),
            instruments_tested=list(csv_paths.keys()),
        )

        print(f"\n{'─'*60}")
        print(f"  CONFIG VALIDATOR  [{config_id}]")
        print(f"  Instruments: {', '.join(csv_paths.keys())}")
        print(f"  Params:")
        for k, v in params.items():
            print(f"    {k:<35} = {v}")
        print(f"{'─'*60}")

        # ── Step 1: Run per-instrument backtests ──────────────────────────
        instrument_scores: dict[str, float] = {}
        instrument_metrics: dict[str, dict] = {}

        for instrument, csv_path in csv_paths.items():
            if not Path(csv_path).exists():
                print(f"  ⚠️  {instrument}: CSV not found at {csv_path} — skipping")
                instrument_scores[instrument] = -999.0
                instrument_metrics[instrument] = {"error": "csv_not_found"}
                continue

            print(f"\n  ▶ {instrument} ...", end=" ", flush=True)
            t0 = time.perf_counter()

            metrics, _ = _run_single_instrument(
                params=params,
                csv_path=csv_path,
                instrument=instrument,
                base_bt_config=None,
                output_dir=output_dir,
            )
            score = fitness_single(metrics, use_llm=use_llm)

            elapsed = time.perf_counter() - t0
            instrument_scores[instrument] = score
            instrument_metrics[instrument] = metrics

            status = "✅" if score > 0.2 else "⚠️ " if score > -999 else "❌"
            print(
                f"{status} score={score:+.4f}  "
                f"trades={metrics.get('approved_trades', 0)}  "
                f"WR={metrics.get('win_rate', 0):.0%}  "
                f"exp={metrics.get('expectancy_rr', 0):+.3f}R  "
                f"dd={metrics.get('max_drawdown_pct', 0):.1%}  "
                f"t={elapsed:.1f}s"
            )

        # ── Step 2: Compute aggregate stats ──────────────────────────────
        final_score, consistency_penalty = fitness_multi(instrument_scores)

        valid_scores = [v for v in instrument_scores.values() if v > -999.0]
        mean_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

        total_trades = sum(
            m.get("approved_trades", 0)
            for m in instrument_metrics.values()
            if m.get("error") is None
        )
        max_drawdown_across = max(
            (m.get("max_drawdown_pct", 0.0) for m in instrument_metrics.values() if m.get("error") is None),
            default=0.0,
        )

        report.mean_score = mean_score
        report.consistency_penalty = consistency_penalty
        report.final_score = final_score
        report.total_trades = total_trades
        report.max_drawdown_across = max_drawdown_across

        # Build per_instrument summary
        for inst, metrics in instrument_metrics.items():
            report.per_instrument[inst] = {
                "score":         round(instrument_scores.get(inst, -999.0), 4),
                "trades":        metrics.get("approved_trades", 0),
                "win_rate":      round(metrics.get("win_rate", 0.0), 4),
                "expectancy_rr": round(metrics.get("expectancy_rr", 0.0), 4),
                "max_drawdown":  round(metrics.get("max_drawdown_pct", 0.0), 4),
                "total_pnl_rr":  round(metrics.get("total_pnl_rr_net", 0.0), 4),
                "error":         metrics.get("error"),
            }

        # ── Step 3: Apply hard rejection rules ───────────────────────────
        ConfigValidator._apply_rejection_rules(report, instrument_scores, instrument_metrics)

        # ── Step 4: Apply soft warnings ───────────────────────────────────
        ConfigValidator._apply_warnings(report, instrument_metrics)

        # ── Step 5: Save report ───────────────────────────────────────────
        ConfigValidator._save_report(report)

        # ── Step 6: Print decision ────────────────────────────────────────
        ConfigValidator._print_decision(report)

        return report.to_dict()

    # ── Hard rejection rules ──────────────────────────────────────────────

    @staticmethod
    def _apply_rejection_rules(
        report: ValidationReport,
        scores: dict,
        metrics: dict,
    ) -> None:
        reasons = []

        # Rule 1: Any instrument score < threshold
        weak = [
            f"{inst}(score={score:.3f})"
            for inst, score in scores.items()
            if score < REJECT_INST_SCORE_MIN and score > -999.0
        ]
        if weak:
            reasons.append(
                f"Weak per-instrument performance: {', '.join(weak)} "
                f"(min allowed: {REJECT_INST_SCORE_MIN})"
            )
            report.flags["weak_instrument"] = True

        # Rule 2: Cross-instrument instability
        valid_scores = [v for v in scores.values() if v > -999.0]
        if len(valid_scores) > 1:
            mean = sum(valid_scores) / len(valid_scores)
            variance = sum((s - mean) ** 2 for s in valid_scores) / len(valid_scores)
            std_dev = math.sqrt(variance)
            if std_dev > REJECT_STD_DEV_MAX:
                reasons.append(
                    f"High cross-instrument instability: std_dev={std_dev:.3f} "
                    f"(max allowed: {REJECT_STD_DEV_MAX})"
                )
                report.flags["instability"] = True

        # Rule 3: Insufficient trade count (per instrument)
        low_count = [
            f"{inst}(trades={m.get('approved_trades', 0)})"
            for inst, m in metrics.items()
            if m.get("error") is None and m.get("approved_trades", 0) < REJECT_TRADE_COUNT_MIN
        ]
        if low_count:
            reasons.append(
                f"Insufficient trades: {', '.join(low_count)} "
                f"(min: {REJECT_TRADE_COUNT_MIN})"
            )
            report.flags["low_trade_count"] = True

        # Rule 4: Excessive drawdown (per instrument)
        high_dd = [
            f"{inst}(dd={m.get('max_drawdown_pct', 0):.1%})"
            for inst, m in metrics.items()
            if m.get("error") is None and m.get("max_drawdown_pct", 0) > REJECT_MAX_DRAWDOWN_MAX
        ]
        if high_dd:
            reasons.append(
                f"Excessive drawdown: {', '.join(high_dd)} "
                f"(max allowed: {REJECT_MAX_DRAWDOWN_MAX:.0%})"
            )
            report.flags["high_drawdown"] = True

        # Rule 5: All instruments failed or no valid scores
        if not any(v > -999.0 for v in scores.values()):
            reasons.append("No instrument produced a valid score — all runs failed or had too few trades.")

        report.rejection_reasons = reasons
        report.decision = "REJECT" if reasons else "APPROVE"

    # ── Soft warnings ─────────────────────────────────────────────────────

    @staticmethod
    def _apply_warnings(report: ValidationReport, metrics: dict) -> None:
        warnings = []

        for inst, m in metrics.items():
            if m.get("error"):
                continue

            trades = m.get("approved_trades", 0)
            dd     = m.get("max_drawdown_pct", 0.0)

            if REJECT_TRADE_COUNT_MIN <= trades < WARN_TRADE_COUNT_MIN:
                warnings.append(
                    f"{inst}: low trade count ({trades}) — sample may be marginal."
                )
            if WARN_DRAWDOWN_MAX < dd <= REJECT_MAX_DRAWDOWN_MAX:
                warnings.append(
                    f"{inst}: elevated drawdown ({dd:.1%}) — monitor live performance."
                )

        report.warnings = warnings

    # ── Save report ───────────────────────────────────────────────────────

    @staticmethod
    def _save_report(report: ValidationReport) -> None:
        decision_folder = "approved" if report.decision == "APPROVE" else "rejected"
        out_dir = Path(ConfigValidator.RESULTS_BASE) / decision_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{report.config_id}.json"
        out_path = out_dir / filename

        with open(out_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        print(f"\n  Report saved → {out_path}")

    # ── Print decision ────────────────────────────────────────────────────

    @staticmethod
    def _print_decision(report: ValidationReport) -> None:
        W = 60
        print(f"\n{'═'*W}")

        if report.decision == "APPROVE":
            print(f"  ✅ CONFIG APPROVED   [{report.config_id}]")
            print(f"\n  Final score:        {report.final_score:+.4f}")
            print(f"  Consistency penalty:{report.consistency_penalty:.4f}")
            print(f"  Total trades:       {report.total_trades}")
            print(f"  Max drawdown:       {report.max_drawdown_across:.1%}")

            if report.warnings:
                print(f"\n  ⚠️  Warnings:")
                for w in report.warnings:
                    print(f"     - {w}")
        else:
            print(f"  ❌ CONFIG REJECTED   [{report.config_id}]")
            print(f"\n  Reason(s):")
            for r in report.rejection_reasons:
                print(f"     - {r}")

            print(f"\n  Per-instrument scores:")
            for inst, data in report.per_instrument.items():
                flag = " ← BELOW THRESHOLD" if data["score"] < REJECT_INST_SCORE_MIN and data["score"] > -999 else ""
                print(f"     {inst:<12} score={data['score']:>+.4f}  trades={data['trades']}{flag}")

        print(f"{'═'*W}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE: Validate the current PROD_PARAMS
# ─────────────────────────────────────────────────────────────────────────────

def validate_prod_params(
    csv_paths: Optional[dict] = None,
    use_llm: bool = False,
) -> dict:
    """
    Validate the current production params from production_config.py.

    A quick way to re-verify the live config against available data.
    """
    from production_config import PROD_PARAMS, PROD_VERSION

    if csv_paths is None:
        # Default to common M15 data paths
        csv_paths = {
            "EURUSD":  "data/EURUSD_M15.csv",
            "GBPUSD":  "data/GBPUSD_M15.csv",
            "BTCUSDT": "data/BTCUSDT_M15.csv",
            "XAUUSD":  "data/XAUUSD_M15.csv",
        }
        # Filter to only existing files
        csv_paths = {k: v for k, v in csv_paths.items() if Path(v).exists()}

    if not csv_paths:
        print("\n  ⚠️  No M15 data files found. Run build_m15_unified.py first.\n")
        return {}

    return ConfigValidator.validate(
        params=PROD_PARAMS,
        csv_paths=csv_paths,
        config_id=f"prod_validation_{PROD_VERSION}",
        use_llm=use_llm,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CRT Config Validator")
    ap.add_argument("--validate-prod", action="store_true",
                    help="Validate the current PROD_PARAMS")
    ap.add_argument("--data-dir", default="data",
                    help="Directory containing M15 CSVs")
    ap.add_argument("--instruments", nargs="+",
                    default=["EURUSD", "GBPUSD", "BTCUSDT", "XAUUSD"])
    ap.add_argument("--no-llm", action="store_true",
                    help="Disable LLM gate (default: off for validation)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    csv_paths = {}
    for inst in [i.upper() for i in args.instruments]:
        candidates = [
            data_dir / f"{inst}_M15.csv",
            data_dir / f"{inst}.csv",
        ]
        for c in candidates:
            if c.exists():
                csv_paths[inst] = str(c)
                break

    if not csv_paths:
        print(f"\n  ERROR: No M15 CSVs found in {data_dir} for {args.instruments}")
        sys.exit(1)

    if args.validate_prod:
        report = validate_prod_params(csv_paths=csv_paths, use_llm=not args.no_llm)
    else:
        # Default: validate current PROD_PARAMS
        report = validate_prod_params(csv_paths=csv_paths, use_llm=not args.no_llm)

    sys.exit(0 if report.get("decision") == "APPROVE" else 1)