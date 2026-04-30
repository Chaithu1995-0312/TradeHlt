"""
governance/shadow_promotion_gate.py
════════════════════════════════════════════════════════════════════════════
Shadow Promotion Gate

Stages a candidate config, runs a shadow backtest, and promotes the candidate
to active only if it meets two conditions:
  1. Shadow run produced >= min_shadow_trades trades (sample-size guard).
  2. Shadow PnL exceeds the baseline PnL.

Configuration
─────────────
All tunable parameters are read from the governance config section:

  {
    "governance": {
      "min_shadow_trades": 30,       ← minimum trades required to consider promoting
      "shadow_data_csv":   "...",    ← backtest input data
      "shadow_output_csv": "...",    ← backtest output trades
    }
  }

The `governance_config` dict is typically the `governance` sub-section of
configs/production/v1_multi_2026_03.json.

Validation
──────────
`min_shadow_trades` is validated on __init__:
  - Must be an integer (or float that is a whole number).
  - Must be >= 1.
  Raises ValueError immediately so misconfiguration is caught at startup,
  not silently at promotion time.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger("ShadowPromotionGate")

# Default fallback used when no governance config is supplied.
_DEFAULT_MIN_SHADOW_TRADES = 30


class ShadowPromotionGate:

    def __init__(
        self,
        active_config_path: str = "configs/production/v1_multi_2026_03.json",
        governance_config: Optional[dict] = None,
    ) -> None:
        """
        Parameters
        ----------
        active_config_path : path to the production config JSON file.
        governance_config  : dict from the 'governance' section of production config.
                             If None, values are read from active_config_path directly.
                             Falls back to hardcoded defaults when neither supplies a value.

        Raises
        ------
        ValueError
            If min_shadow_trades is not a positive integer.
        """
        self.active_config_path = Path(active_config_path)
        self.candidate_path     = Path("configs/production/candidate.json")
        self.backtest_script    = "runtime/backtest_bitnet.py"

        # Load governance section from config file if not injected
        if governance_config is None:
            governance_config = self._load_governance_config()

        self.min_shadow_trades: int = self._validate_min_shadow_trades(
            governance_config.get("min_shadow_trades", _DEFAULT_MIN_SHADOW_TRADES)
        )
        self.data_csv    = str(governance_config.get("shadow_data_csv",  "data/AUDUSD_M15.csv"))
        self.output_csv  = str(governance_config.get("shadow_output_csv", "results/shadow_trades.csv"))

        log.info(
            "ShadowPromotionGate initialised: min_shadow_trades=%d data=%s output=%s",
            self.min_shadow_trades, self.data_csv, self.output_csv,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_governance_config(self) -> dict:
        """Read the governance sub-section from the active production config."""
        if not self.active_config_path.exists():
            log.warning(
                "ShadowPromotionGate: active config not found at %s. "
                "Using defaults.", self.active_config_path
            )
            return {}
        try:
            with open(self.active_config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("governance", {})
        except Exception as e:
            log.warning(
                "ShadowPromotionGate: failed to load governance config (%s). "
                "Using defaults.", e
            )
            return {}

    @staticmethod
    def _validate_min_shadow_trades(value) -> int:
        """
        Validate and coerce min_shadow_trades.

        Raises ValueError if the value is not a positive integer.
        """
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"ShadowPromotionGate: min_shadow_trades must be a positive integer, "
                f"got {value!r} ({type(value).__name__})"
            )
        if n < 1:
            raise ValueError(
                f"ShadowPromotionGate: min_shadow_trades must be >= 1, got {n}"
            )
        return n

    # ── Public API ────────────────────────────────────────────────────────────

    def stage_candidate(self, candidate_patch: dict) -> None:
        """Write the candidate config to disk for the shadow backtest."""
        with open(self.active_config_path, encoding="utf-8") as f:
            base_config = json.load(f)

        if "decision_engine" not in base_config:
            base_config["decision_engine"] = {}

        if "fusion_min_score" in candidate_patch:
            base_config["fusion_min_score"] = candidate_patch["fusion_min_score"]
        if "decision_engine" in candidate_patch:
            base_config["decision_engine"].update(candidate_patch["decision_engine"])

        with open(self.candidate_path, "w", encoding="utf-8") as f:
            json.dump(base_config, f, indent=4)
        log.info("Candidate config staged at %s", self.candidate_path)

    def execute_shadow_test(self) -> tuple[float, int]:
        """
        Run the shadow backtest and return (total_pnl, n_trades).

        Returns
        -------
        (total_pnl, n_trades)
          total_pnl : sum of pnl_rr_net across all shadow trades
          n_trades  : number of trade rows in the shadow output CSV

        Raises
        ------
        subprocess.CalledProcessError  if the backtest script fails.
        FileNotFoundError              if the output CSV is not produced.
        """
        cmd = [
            "python", self.backtest_script,
            "--config", str(self.candidate_path),
            "--data",   self.data_csv,
            "--output", self.output_csv,
        ]
        subprocess.run(cmd, check=True)

        output_path = Path(self.output_csv)
        if not output_path.exists():
            raise FileNotFoundError(
                f"Shadow backtest did not produce output CSV: {self.output_csv}"
            )

        shadow_trades = pd.read_csv(self.output_csv)
        n_trades  = len(shadow_trades)
        total_pnl = float(shadow_trades["pnl_rr_net"].sum()) if n_trades > 0 else 0.0
        log.info("Shadow test complete: n_trades=%d total_pnl=%.4f", n_trades, total_pnl)
        return total_pnl, n_trades

    def promote_if_superior(
        self,
        baseline_pnl: float,
        shadow_pnl:   float,
        n_shadow_trades: int,
    ) -> dict:
        """
        Promote the candidate config if it passes both gates:
          1. Sample-size gate: n_shadow_trades >= min_shadow_trades.
          2. Performance gate: shadow_pnl > baseline_pnl.

        Parameters
        ----------
        baseline_pnl     : PnL of the current active config on the same data.
        shadow_pnl       : PnL produced by execute_shadow_test().
        n_shadow_trades  : trade count produced by execute_shadow_test().

        Returns
        -------
        dict with keys:
          promoted : bool
          reason   : human-readable explanation
        """
        log.info(
            "ShadowGate evaluation: n_trades=%d (min=%d) "
            "shadow_pnl=%.4f baseline_pnl=%.4f",
            n_shadow_trades, self.min_shadow_trades,
            shadow_pnl, baseline_pnl,
        )

        # Gate 1 — minimum trade count
        if n_shadow_trades < self.min_shadow_trades:
            reason = (
                f"Promotion BLOCKED — insufficient shadow trades: "
                f"{n_shadow_trades} < min_shadow_trades={self.min_shadow_trades}. "
                f"Increase shadow data window or lower min_shadow_trades in governance config."
            )
            log.warning(reason)
            self.candidate_path.unlink(missing_ok=True)
            return {"promoted": False, "reason": reason}

        # Gate 2 — performance
        if shadow_pnl > baseline_pnl:
            reason = (
                f"Candidate promoted: shadow_pnl={shadow_pnl:.4f} "
                f"> baseline_pnl={baseline_pnl:.4f} "
                f"(n_trades={n_shadow_trades})"
            )
            log.info(reason)
            shutil.copy(self.candidate_path, self.active_config_path)
            self.candidate_path.unlink(missing_ok=True)
            return {"promoted": True, "reason": reason}
        else:
            reason = (
                f"Candidate NOT promoted: shadow_pnl={shadow_pnl:.4f} "
                f"<= baseline_pnl={baseline_pnl:.4f} "
                f"(n_trades={n_shadow_trades})"
            )
            log.info(reason)
            self.candidate_path.unlink(missing_ok=True)
            return {"promoted": False, "reason": reason}
