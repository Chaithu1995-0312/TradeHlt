"""
EXAMPLE_SERVICE.py
================================================================================
Golden reference service for the Tradelatest codebase.

This file is a *template* — not wired into production — that demonstrates every
convention new modules in `src/` are expected to follow:

    1. Fail-fast config load at module import     (see: ConfigValidator)
    2. `_require_*` strict accessor for config keys
    3. `from_prod_config` factory on any dataclass derived from config
    4. Named flow logger via `utils.logging_config.get_flow_logger`
    5. Optional-import guard for non-critical capabilities
    6. Fail-open external I/O with circuit breaker
    7. Structured decision-report return shape (decision / metrics / hard_failures / warnings)
    8. Absolute imports rooted at `src/`, alphabetised stdlib / third-party / internal
    9. Private helpers `_snake_case`; public API on a `PascalCase` class
   10. Zero magic numbers — every tunable flows from production JSON

Use this as the starting point when adding a new engine, gate, or validator.
Copy it into the appropriate `src/<subpackage>/` (see docs/CONVENTIONS.md §2)
and rename.
================================================================================
"""

from __future__ import annotations

# ── 1. Standard library (alphabetised) ──────────────────────────────────────
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 2. Path bootstrap (only if module is run as a script) ───────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 3. Internal imports (absolute, rooted at src/) ──────────────────────────
from config_layer.production_config import get_prod_section          # type: ignore
from utils.logging_config import get_flow_logger                      # type: ignore

# ── 4. Optional import guard — non-blocking capability ──────────────────────
try:
    from features.feature_monitor import FeatureMonitor               # type: ignore
    _MONITOR_AVAILABLE = True
except Exception:
    FeatureMonitor = None  # type: ignore
    _MONITOR_AVAILABLE = False


# ============================================================================
# LOGGER
# ============================================================================

logger = get_flow_logger("EXAMPLE_SERVICE")


# ============================================================================
# CONFIG LOAD — fail-fast at module import
# ============================================================================

def _load_example_cfg() -> dict:
    """Load the `example_service` section from production JSON. Raises if missing.

    NOTE: Replace `"example_service"` with the actual section name when copying
    this template into production.
    """
    try:
        cfg = get_prod_section("example_service")
        if not cfg:
            raise RuntimeError(
                "example_service section missing from production config JSON. "
                "Add it to configs/production/v1_multi_2026_03.json."
            )
        return cfg
    except ImportError as exc:
        raise RuntimeError(
            f"Failed to import production_config: {exc}. "
            "Cannot load example_service settings."
        ) from exc


def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises if `key` is missing from `cfg`.

    Mirrors `_validator_require` in `config_validator.py` and `_require_lg`
    in `llama_gate.py`. Every required config value goes through this.
    """
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from example_service section. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


# Module-level load — failure here prevents import → fail-fast by design.
_CFG = _load_example_cfg()

_MIN_SAMPLES:      int   = int(_require(_CFG, "min_samples"))
_MAX_LATENCY_MS:   int   = int(_require(_CFG, "max_latency_ms"))
_SCORE_THRESHOLD:  float = float(_require(_CFG, "score_threshold"))
_WEIGHTS:          dict  = dict(_require(_CFG, "weights"))


# ============================================================================
# DATA MODEL — dataclass + from_prod_config factory
# ============================================================================

@dataclass
class ExampleServiceConfig:
    """Value object derived from production JSON — passed into the service.

    Prefer a dataclass over passing a raw dict: gives type checking, IDE help,
    and a single place to add `from_prod_config` normalisation.
    """
    min_samples:     int
    max_latency_ms:  int
    score_threshold: float
    weights:         Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "ExampleServiceConfig":
        """Canonical config → dataclass bridge. Every field comes from JSON."""
        return cls(
            min_samples     = int(_require(prod_cfg, "min_samples")),
            max_latency_ms  = int(_require(prod_cfg, "max_latency_ms")),
            score_threshold = float(_require(prod_cfg, "score_threshold")),
            weights         = dict(_require(prod_cfg, "weights")),
        )


# ============================================================================
# CIRCUIT BREAKER — fail-open wrapper for any external I/O
# ============================================================================

class _CircuitBreaker:
    """Minimal fail-open breaker. Mirrors the pattern in llama_gate.py.

    After `fail_count_disable` consecutive failures the breaker opens and the
    wrapped call returns the neutral value without invoking the upstream.
    """

    def __init__(self, fail_count_disable: int = 10):
        self._fail_count_disable = fail_count_disable
        self._fails = 0
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def record_failure(self) -> None:
        self._fails += 1
        if self._fails > self._fail_count_disable and not self._open:
            self._open = True
            logger.warning("Circuit breaker OPEN after %d failures", self._fails)

    def record_success(self) -> None:
        if self._fails or self._open:
            logger.info("Circuit breaker reset after recovery")
        self._fails = 0
        self._open = False


# ============================================================================
# PUBLIC API
# ============================================================================

class ExampleService:
    """
    Reference service — computes a weighted score over a metrics dict and
    returns a structured decision report.

    Parameters
    ----------
    config : ExampleServiceConfig | None
        Optional override; if `None`, loads from production JSON.
    monitor : FeatureMonitor | None
        Optional drift monitor; degrades gracefully if unavailable.
    """

    def __init__(
        self,
        config: Optional[ExampleServiceConfig] = None,
        monitor: Optional["FeatureMonitor"] = None,    # forward-ref string for optional import
    ) -> None:
        self._cfg = config or ExampleServiceConfig.from_prod_config(_CFG)
        self._breaker = _CircuitBreaker(fail_count_disable=10)
        self._monitor = monitor if (_MONITOR_AVAILABLE and monitor is not None) else None
        logger.info(
            "ExampleService initialised | min_samples=%d score_threshold=%.3f monitor=%s",
            self._cfg.min_samples, self._cfg.score_threshold,
            "on" if self._monitor else "off",
        )

    # ── Public methods ─────────────────────────────────────────────────────

    def evaluate(
        self,
        metrics: Dict[str, float],
        *,
        entity_id: str = "unnamed",
    ) -> Dict[str, Any]:
        """
        Evaluate `metrics` against configured gates and return a decision report.

        Returns
        -------
        dict
            {
              "decision":      "APPROVE" | "REJECT",
              "entity_id":     str,
              "evaluated_at":  ISO-8601 UTC timestamp,
              "metrics":       {"final_score": float, ...},
              "hard_failures": list[str],
              "warnings":      list[str],
            }
        """
        # ── 1. Early rejection on empty input ──
        if not metrics:
            return self._reject(entity_id, ["No metrics provided -- nothing to evaluate."])

        # ── 2. Sample-count hard gate ──
        sample_count = int(metrics.get("samples", 0))
        if sample_count < self._cfg.min_samples:
            return self._reject(
                entity_id,
                [f"samples={sample_count} < min_samples={self._cfg.min_samples}"],
            )

        # ── 3. Core computation ──
        try:
            final_score = self._compute_score(metrics)
        except Exception as exc:
            logger.exception("Score computation failed for entity_id=%s", entity_id)
            return self._reject(entity_id, [f"Score computation error: {exc}"])

        # ── 4. Optional drift observation (non-blocking) ──
        warnings: List[str] = []
        if self._monitor is not None:
            try:
                drift = self._monitor.observe(metrics)
                if drift.get("z_max", 0.0) > 3.0:
                    warnings.append(f"Hard drift detected: z={drift['z_max']:.2f}")
                elif drift.get("z_max", 0.0) > 2.5:
                    logger.debug("Soft drift: z=%.2f", drift["z_max"])
            except Exception as exc:
                logger.warning("Drift observation failed (non-blocking): %s", exc)

        # ── 5. Score gate ──
        if final_score < self._cfg.score_threshold:
            return self._reject(
                entity_id,
                [f"final_score={final_score:.3f} < threshold={self._cfg.score_threshold:.3f}"],
                warnings=warnings,
                final_score=final_score,
            )

        # ── 6. Structured APPROVE ──
        return self._approve(entity_id, final_score, warnings)

    # ── Private helpers ────────────────────────────────────────────────────

    def _compute_score(self, metrics: Dict[str, float]) -> float:
        """Weighted mean of known metric components.

        Unknown weight keys are silently skipped (forward-compatible).
        """
        total_weight = 0.0
        total_value  = 0.0
        for key, weight in self._cfg.weights.items():
            if key in metrics:
                total_value  += float(metrics[key]) * float(weight)
                total_weight += float(weight)
        if total_weight <= 0.0:
            raise ValueError("No configured weight keys matched the provided metrics")
        return total_value / total_weight

    def _approve(
        self,
        entity_id: str,
        final_score: float,
        warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "decision":      "APPROVE",
            "entity_id":     entity_id,
            "evaluated_at":  datetime.now(timezone.utc).isoformat(),
            "metrics":       {"final_score": final_score},
            "hard_failures": [],
            "warnings":      warnings,
        }

    def _reject(
        self,
        entity_id: str,
        hard_failures: List[str],
        *,
        warnings: Optional[List[str]] = None,
        final_score: float = 0.0,
    ) -> Dict[str, Any]:
        return {
            "decision":      "REJECT",
            "entity_id":     entity_id,
            "evaluated_at":  datetime.now(timezone.utc).isoformat(),
            "metrics":       {"final_score": final_score},
            "hard_failures": list(hard_failures),
            "warnings":      list(warnings or []),
        }


# ============================================================================
# CLI (optional) — thin wrapper; never define logic here, only import from src/
# ============================================================================

def _main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run ExampleService over a metrics JSON file.")
    parser.add_argument("metrics_json", help="Path to a JSON file of metrics.")
    parser.add_argument("--entity-id", default="cli")
    args = parser.parse_args(argv)

    with open(args.metrics_json, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)

    report = ExampleService().evaluate(metrics, entity_id=args.entity_id)
    print(json.dumps(report, indent=2))
    return 0 if report["decision"] == "APPROVE" else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))


# ============================================================================
# MODULE REGISTRATION NOTES
# ============================================================================
#
# 1. Choose the correct subpackage per docs/CONVENTIONS.md §2:
#      - Scoring engine   → src/engines/
#      - Decision kernel  → src/core/
#      - Validator        → src/config_layer/
#      - Governance gate  → src/governance/
#
# 2. Add the new config section to configs/production/v1_multi_2026_03.json:
#      "example_service": {
#          "min_samples":     10,
#          "max_latency_ms":  500,
#          "score_threshold": 0.25,
#          "weights": {"a": 0.4, "b": 0.3, "c": 0.3}
#      }
#    Then re-hash: `python scripts/maintenance/_compute_hash.py`.
#
# 3. Register in the consuming orchestrator:
#      - For an engine: add to EXPECTED_ENGINES in core/engine_runner.py
#      - For a validator: call from promotion_manager or live_engine_hook
#
# 4. Add tests in tests/:
#      - Happy path APPROVE
#      - Each hard_failure branch
#      - Circuit-breaker open → neutral return (if using external I/O)
#      - Optional-dep absent path (_MONITOR_AVAILABLE = False)
#
# 5. Bump the production config version and promote via:
#      python src/governance/promotion_manager.py promote \
#        --checkpoint results/tuner/checkpoint_multi.json \
#        --version   v2_<label>_<YYYY_MM> \
#        --data-dir  data/
# ============================================================================
