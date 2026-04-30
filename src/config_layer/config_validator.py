"""
config_validator.py
================================================================================
Config Validation Gate -- Phase 1 + Phase 5 quality enforcement.

Purpose:
  Validates a candidate params dict by running a per-instrument backtest and
  scoring against quality gates. Only approved ValidationReports can be
  promoted via promotion_manager.py.

Architecture:
  params dict -> CRTConfig -> BacktestRunner (per instrument) ->
  per-instrument metrics -> fitness score -> quality gates -> APPROVE / REJECT

Quality Gates (Phase 5):
  1. Min trade count per instrument   (HARD gate)
  2. Max drawdown per instrument      (HARD gate)
  3. Min win rate                     (SOFT warning)
  4. Min expectancy                   (SOFT warning)
  5. Cross-instrument score std_dev   (SOFT warning -- consistency)

Usage:
    from config_validator import ConfigValidator

    report = ConfigValidator.validate(
        params={"body_ratio_min": 0.65, "retest_depth_max": 0.3, ...},
        csv_paths={"EURUSD": "data/EURUSD_M15.csv"},
        config_id="v2_candidate_001",
    )
    if report["decision"] == "APPROVE":
        # safe to promote
================================================================================
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Path setup --------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

def _load_validator_cfg() -> dict:
    """Load config_validator section from production JSON. Raises if missing."""
    try:
        from config_layer.production_config import get_prod_section
        cfg = get_prod_section("config_validator")
        if not cfg:
            raise RuntimeError(
                "config_validator section missing from production config JSON. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        return cfg
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import production_config: {exc}. "
            "Cannot load config_validator settings."
        ) from exc


def _validator_require(cfg: dict, key: str) -> object:
    """Strict accessor for validator config — raises if key absent."""
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from config_validator section. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


# Load validator config at module init — fail fast if JSON is misconfigured
_VALIDATOR_CFG = _load_validator_cfg()

_GATE_MIN_TRADES_PER_INSTRUMENT: int   = int(_validator_require(_VALIDATOR_CFG, "min_trades_per_instrument"))
_GATE_MAX_DRAWDOWN_PCT:          float = float(_validator_require(_VALIDATOR_CFG, "max_drawdown_pct"))
_GATE_MIN_WIN_RATE:              float = float(_validator_require(_VALIDATOR_CFG, "min_win_rate"))
_GATE_MIN_EXPECTANCY:            float = float(_validator_require(_VALIDATOR_CFG, "min_expectancy"))
_GATE_SCORE_THRESHOLD:           float = float(_validator_require(_VALIDATOR_CFG, "score_threshold"))
_GATE_MAX_SCORE_STD_DEV:         float = float(_validator_require(_VALIDATOR_CFG, "max_score_std_dev"))
_TRADE_COUNT_TARGET:             int   = int(_validator_require(_VALIDATOR_CFG, "trade_count_target"))
_FITNESS_WEIGHTS:                dict  = dict(_validator_require(_VALIDATOR_CFG, "fitness_weights"))


# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _params_to_crt_config(params: dict):
    """Map a flat params dict to CRTConfig, ignoring unknown keys."""
    from config_layer.crt_engine_v2 import CRTConfig
    known = {f.name for f in CRTConfig.__dataclass_fields__.values()
             if f.name not in ("session_windows", "conf_weights", "sizing_bands")}
    kwargs = {k: v for k, v in params.items() if k in known}
    return CRTConfig(**kwargs)


def _fitness_score(
    win_rate: float,
    expectancy_rr: float,
    trade_count: int,
    max_drawdown_pct: float,
    weights: dict = _FITNESS_WEIGHTS,
    count_target: int = _TRADE_COUNT_TARGET,
) -> float:
    """
    Compute a [0, 1]-ish fitness score from backtest metrics.
    Lower drawdown is better. Higher expectancy, win_rate, trade_count -> better.
    """
    exp_norm   = _clamp((expectancy_rr + 2.0) / 4.0)      # [-2, +2] -> [0, 1]
    wr_norm    = _clamp(win_rate)
    count_norm = _clamp(trade_count / count_target)
    dd_norm    = _clamp(1.0 - max_drawdown_pct)            # lower DD is better

    return (
        weights.get("expectancy_rr",    0.5) * exp_norm
        + weights.get("win_rate",       0.2) * wr_norm
        + weights.get("trade_count_norm", 0.2) * count_norm
        + weights.get("drawdown",       0.1) * dd_norm
    )


def _run_instrument(
    instrument: str,
    csv_path: str,
    crt_config,
    warmup: int | None = None,
) -> dict:
    """Run a single-instrument backtest and return a metrics dict."""
    try:
        from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
        cfg = BacktestConfig.from_prod_config(
            instrument=instrument,
            crt_config=crt_config,
        )
        # honour explicit warmup override (e.g. from CLI --warmup flag)
        if warmup is not None:
            cfg.warmup_candles = warmup
        loader = CandleLoader(str(csv_path), instrument)
        runner = BacktestRunner(cfg, csv_path=str(csv_path))
        m = runner.run(loader.stream(), loader.count(), output_dir="results/validation_tmp")

        n_trades   = m.approved_trades
        win_rate   = _safe(m.win_rate)
        exp_rr     = _safe(m.avg_rr_net)
        max_dd     = _safe(m.max_drawdown_pct)
        total_pnl  = _safe(m.total_pnl_rr_net)

        score = _fitness_score(win_rate, exp_rr, n_trades, max_dd)

        return {
            "score":          round(score, 4),
            "trades":         n_trades,
            "win_rate":       round(win_rate, 4),
            "expectancy_rr":  round(exp_rr, 4),
            "max_drawdown":   round(max_dd, 4),
            "total_pnl_rr":   round(total_pnl, 4),
            "error":          None,
        }

    except Exception as exc:
        return {
            "score":         -999.0,
            "trades":        0,
            "win_rate":      0.0,
            "expectancy_rr": 0.0,
            "max_drawdown":  1.0,
            "total_pnl_rr":  0.0,
            "error":         str(exc),
        }


def _aggregate_metrics(per_instrument: dict) -> dict:
    """Compute cross-instrument aggregate from per-instrument results."""
    valid = {k: v for k, v in per_instrument.items() if v.get("score", -999) > -999.0}
    if not valid:
        return {
            "final_score":         -999.0,
            "mean_score":          -999.0,
            "consistency_penalty": 0.0,
            "total_trades":        0,
            "max_drawdown_across": 1.0,
        }

    scores = [v["score"] for v in valid.values()]
    mean_s = sum(scores) / len(scores)

    # Consistency penalty: std-dev of scores across instruments
    if len(scores) > 1:
        var = sum((s - mean_s) ** 2 for s in scores) / len(scores)
        std = math.sqrt(var)
    else:
        std = 0.0

    consistency_penalty = round(std * 0.5, 4)   # half std-dev as penalty
    final_score         = round(max(0.0, mean_s - consistency_penalty), 4)
    total_trades        = sum(v["trades"] for v in valid.values())
    max_dd              = max(v["max_drawdown"] for v in valid.values())

    return {
        "final_score":         final_score,
        "mean_score":          round(mean_s, 4),
        "consistency_penalty": consistency_penalty,
        "total_trades":        total_trades,
        "max_drawdown_across": round(max_dd, 4),
    }


def _run_quality_gates(
    per_instrument: dict,
    metrics: dict,
    params: dict,
) -> tuple[str, list[str], list[str]]:
    """
    Apply quality gates.

    Returns
    -------
    (decision, hard_failures, warnings)
      decision: "APPROVE" | "REJECT"
      hard_failures: reasons for hard rejection
      warnings: soft-gate warnings
    """
    hard_failures: list[str] = []
    warnings:      list[str] = []

    # -- Hard gates --------------------------------------------------
    for inst, res in per_instrument.items():
        if res.get("error"):
            hard_failures.append(f"{inst}: backtest error -- {res['error']}")
            continue

        tc = res.get("trades", 0)
        if tc < _GATE_MIN_TRADES_PER_INSTRUMENT:
            hard_failures.append(
                f"{inst}: only {tc} trade(s) -- minimum is {_GATE_MIN_TRADES_PER_INSTRUMENT}."
            )

        dd = res.get("max_drawdown", 1.0)
        if dd > _GATE_MAX_DRAWDOWN_PCT:
            hard_failures.append(
                f"{inst}: drawdown {dd:.1%} exceeds hard limit {_GATE_MAX_DRAWDOWN_PCT:.0%}."
            )

    # Final score below APPROVE threshold
    final = metrics.get("final_score", -999.0)
    if final < _GATE_SCORE_THRESHOLD:
        hard_failures.append(
            f"Final fitness score {final:.4f} below approval threshold {_GATE_SCORE_THRESHOLD}."
        )

    # -- Soft gates (warnings only) -----------------------------------
    for inst, res in per_instrument.items():
        if res.get("error"):
            continue
        wr  = res.get("win_rate", 0.0)
        exp = res.get("expectancy_rr", 0.0)
        tc  = res.get("trades", 0)

        if wr < _GATE_MIN_WIN_RATE:
            warnings.append(f"{inst}: low win rate ({wr:.1%}).")
        if exp < _GATE_MIN_EXPECTANCY:
            warnings.append(f"{inst}: low expectancy ({exp:.3f}R).")
        if tc < _TRADE_COUNT_TARGET:
            warnings.append(
                f"{inst}: low trade count ({tc}) -- sample may be marginal."
            )

    # Consistency warning
    std_proxy = metrics.get("consistency_penalty", 0.0) * 2  # reverse penalty to std
    if std_proxy > _GATE_MAX_SCORE_STD_DEV:
        warnings.append(
            f"High cross-instrument score variance (std~{std_proxy:.3f}). "
            "Fitness may be instrument-specific, not general."
        )

    decision = "REJECT" if hard_failures else "APPROVE"
    return decision, hard_failures, warnings


# ============================================================================
# PUBLIC API
# ============================================================================

class ConfigValidator:
    """
    Validates a candidate config by running per-instrument backtests and
    applying quality gates.

    All methods are static -- no instance state needed.
    """

    @staticmethod
    def validate(
        params: dict,
        csv_paths: dict,
        config_id: str = "unnamed",
        use_llm: bool = False,
        warmup_candles: int = 30,
    ) -> dict:
        """
        Validate a params dict against all provided instrument CSVs.

        Parameters
        ----------
        params : dict
            CRTConfig-compatible parameter dict.
        csv_paths : dict
            {instrument_name: csv_file_path} mapping.
        config_id : str
            Human label for this validation run.
        use_llm : bool
            Reserved for future LLM gate integration (currently unused).
        warmup_candles : int
            Warmup candles for each backtest run.

        Returns
        -------
        dict
            ValidationReport:
            {
              "decision":           "APPROVE" | "REJECT",
              "config_id":          str,
              "validated_at":       ISO timestamp,
              "params":             dict,
              "metrics":            {final_score, mean_score, ...},
              "per_instrument":     {inst: {score, trades, ...}},
              "instruments_tested": [str, ...],
              "hard_failures":      [str, ...],
              "warnings":           [str, ...],
            }
        """
        if not csv_paths:
            return ConfigValidator._reject(
                config_id, params,
                hard_failures=["No CSV paths provided -- nothing to validate."],
            )

        # Build CRTConfig from params (unknown keys silently ignored)
        try:
            crt_config = _params_to_crt_config(params)
        except Exception as exc:
            return ConfigValidator._reject(
                config_id, params,
                hard_failures=[f"Failed to build CRTConfig from params: {exc}"],
            )

        W = 60
        print(f"\n{'='*W}")
        print(f"  CONFIG VALIDATOR -- {config_id}")
        print(f"  Instruments: {list(csv_paths.keys())}")
        print(f"{'='*W}")

        # -- Per-instrument backtest -----------------------------------
        per_instrument: dict = {}
        for inst, csv_path in csv_paths.items():
            if not Path(csv_path).exists():
                per_instrument[inst] = {
                    "score": -999.0, "trades": 0,
                    "win_rate": 0.0, "expectancy_rr": 0.0,
                    "max_drawdown": 1.0, "total_pnl_rr": 0.0,
                    "error": f"CSV not found: {csv_path}",
                }
                continue

            print(f"  Running {inst} ...")
            result = _run_instrument(inst, csv_path, crt_config, warmup=warmup_candles)
            per_instrument[inst] = result

            status = "OK" if result["error"] is None else f"ERROR: {result['error']}"
            print(
                f"    {inst}: score={result['score']:.4f}  trades={result['trades']}  "
                f"wr={result['win_rate']:.1%}  exp={result['expectancy_rr']:.3f}R  "
                f"dd={result['max_drawdown']:.1%}  [{status}]"
            )

        # -- Aggregate ------------------------------------------------
        metrics = _aggregate_metrics(per_instrument)

        # -- Quality gates --------------------------------------------
        decision, hard_failures, warnings = _run_quality_gates(
            per_instrument, metrics, params
        )

        # -- Print summary --------------------------------------------
        print(f"\n  Aggregate:")
        print(f"    Final score:    {metrics['final_score']:.4f}")
        print(f"    Mean score:     {metrics['mean_score']:.4f}")
        print(f"    Consistency (-): {metrics['consistency_penalty']:.4f}")
        print(f"    Total trades:    {metrics['total_trades']}")
        print(f"    Max drawdown:    {metrics['max_drawdown_across']:.1%}")

        if warnings:
            print(f"\n  Warnings ({len(warnings)}):")
            for w in warnings:
                print(f"    [!] {w}")
        if hard_failures:
            print(f"\n  Hard failures ({len(hard_failures)}):")
            for f_ in hard_failures:
                print(f"    [X] {f_}")

        icon = "[APPROVE]" if decision == "APPROVE" else "[REJECT]"
        print(f"\n  {icon} Decision: {decision}")
        print(f"{'='*W}\n")

        return {
            "decision":           decision,
            "config_id":          config_id,
            "validated_at":       datetime.now(timezone.utc).isoformat(),
            "params":             params,
            "metrics":            metrics,
            "per_instrument":     per_instrument,
            "instruments_tested": list(csv_paths.keys()),
            "hard_failures":      hard_failures,
            "warnings":           warnings,
        }

    @staticmethod
    def validate_production(
        version: Optional[str] = None,
        csv_paths: Optional[dict] = None,
    ) -> dict:
        """
        Validate the currently-active production config.
        Useful for regression checks after code changes.

        Parameters
        ----------
        version : str or None
            Production version to load. Defaults to PROD_VERSION.
        csv_paths : dict or None
            Override instrument CSV paths. Falls back to data/ directory.
        """
        from config_layer.production_config import PROD_VERSION, get_prod_metadata
        target_version = version or PROD_VERSION
        meta = get_prod_metadata()
        params = (meta or {}).get("params", {})

        if not params:
            return ConfigValidator._reject(
                target_version, {},
                hard_failures=[f"No params found for version '{target_version}'."],
            )

        if csv_paths is None:
            csv_paths = ConfigValidator._discover_csvs()

        return ConfigValidator.validate(
            params=params,
            csv_paths=csv_paths,
            config_id=f"prod_validation_{target_version}",
        )

    # -- Private helpers ----------------------------------------------

    @staticmethod
    def _reject(config_id: str, params: dict, hard_failures: list) -> dict:
        """Return an immediate rejection report without running any backtests."""
        print(f"\n  [REJECT] REJECTED ({config_id}): {hard_failures[0]}")
        return {
            "decision":           "REJECT",
            "config_id":          config_id,
            "validated_at":       datetime.now(timezone.utc).isoformat(),
            "params":             params,
            "metrics":            {
                "final_score": -999.0, "mean_score": -999.0,
                "consistency_penalty": 0.0,
                "total_trades": 0, "max_drawdown_across": 1.0,
            },
            "per_instrument":     {},
            "instruments_tested": [],
            "hard_failures":      hard_failures,
            "warnings":           [],
        }

    @staticmethod
    def _discover_csvs(data_dir: str = "data") -> dict:
        """Auto-discover instrument CSVs from a data directory."""
        p = Path(data_dir)
        if not p.exists():
            return {}
        csv_paths = {}
        for csv_file in sorted(p.glob("*.csv")):
            stem = csv_file.stem.upper()
            # Infer instrument from filename (e.g. EURUSD_M15 -> EURUSD)
            for inst in [
                "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD",
                "XAUUSD", "BTCUSDT", "ETHUSDT", "US30", "NAS100",
            ]:
                if inst in stem:
                    csv_paths[inst] = str(csv_file)
                    break
        return csv_paths


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CRT Config Validator")
    sub = ap.add_subparsers(dest="cmd")

    # validate-prod
    vp = sub.add_parser("validate-prod", help="Validate active production config")
    vp.add_argument("--data-dir", default="data", help="Directory with instrument CSVs")
    vp.add_argument("--version", default=None, help="Override production version")
    vp.add_argument("--output", default=None, help="Write report JSON to path")

    # validate-params
    vpf = sub.add_parser("validate-params", help="Validate a params JSON file")
    vpf.add_argument("--params", required=True, help="JSON file with params dict")
    vpf.add_argument("--data-dir", default="data")
    vpf.add_argument("--config-id", default="cli_validation")
    vpf.add_argument("--output", default=None)

    args = ap.parse_args()

    if args.cmd == "validate-prod":
        csv_paths = ConfigValidator._discover_csvs(args.data_dir)
        if not csv_paths:
            print(f"\nNo CSVs found in {args.data_dir}. Provide instrument CSVs.\n")
            sys.exit(1)
        report = ConfigValidator.validate_production(
            version=args.version, csv_paths=csv_paths
        )
    elif args.cmd == "validate-params":
        with open(args.params) as f:
            params = json.load(f)
        csv_paths = ConfigValidator._discover_csvs(args.data_dir)
        if not csv_paths:
            print(f"\nNo CSVs found in {args.data_dir}. Provide instrument CSVs.\n")
            sys.exit(1)
        report = ConfigValidator.validate(
            params=params, csv_paths=csv_paths, config_id=args.config_id
        )
    else:
        ap.print_help()
        sys.exit(0)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report written to {out}")

    sys.exit(0 if report.get("decision") == "APPROVE" else 1)
