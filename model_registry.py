"""
model_registry.py
═══════════════════════════════════════════════════════════════════════════════
Versioned model registry with promotion guard.

Every trained model is registered with its eval metrics and composite score.
A new model is ONLY promoted to "active" if it beats the current best by
at least PROMOTION_MARGIN — preventing noisy score fluctuations from
silently deploying a worse model.

Registry lives at models/registry.json.
Active model name lives at models/active.txt.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from evaluator import EvalResult

log = logging.getLogger("ModelRegistry")

MODELS_DIR       = Path("models")
REGISTRY_PATH    = MODELS_DIR / "registry.json"
ACTIVE_PATH      = MODELS_DIR / "active.txt"
PROMOTION_MARGIN = 0.02   # new model must beat current by this margin


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY ENTRY
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelEntry:
    name:            str
    composite_score: float
    accuracy:        float
    precision:       float
    recall:          float
    bucket_stats:    dict
    n_val_samples:   int
    trained_at:      str   # ISO timestamp
    promoted:        bool  = False


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ModelRegistry:

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "registry.json"
        self.act_path = models_dir / "active.txt"
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load(self) -> dict[str, dict]:
        if not self.reg_path.exists():
            return {}
        try:
            return json.loads(self.reg_path.read_text())
        except Exception as e:
            log.warning(f"Registry load failed: {e}. Starting fresh.")
            return {}

    def _save(self, reg: dict) -> None:
        self.reg_path.write_text(json.dumps(reg, indent=2))

    # ── Register ──────────────────────────────────────────────────────────────

    def register(self, model_name: str, eval_result: EvalResult) -> ModelEntry:
        """
        Add a trained + evaluated model to the registry.
        Does NOT promote automatically — call try_promote() separately.
        """
        reg  = self._load()
        entry = ModelEntry(
            name            = model_name,
            composite_score = round(eval_result.composite_score, 6),
            accuracy        = round(eval_result.accuracy,        4),
            precision       = round(eval_result.precision,       4),
            recall          = round(eval_result.recall,          4),
            bucket_stats    = eval_result.bucket_stats,
            n_val_samples   = eval_result.n_samples,
            trained_at      = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            promoted        = False,
        )
        reg[model_name] = asdict(entry)
        self._save(reg)
        log.info(f"Registered {model_name}  composite={entry.composite_score:.4f}")
        return entry

    # ── Promotion ─────────────────────────────────────────────────────────────

    def try_promote(self, model_name: str) -> tuple[bool, str]:
        """
        Promote model_name to active if it beats current best by PROMOTION_MARGIN.

        Returns (promoted: bool, reason: str)
        """
        reg = self._load()

        if model_name not in reg:
            return False, f"{model_name} not in registry"

        new_score = reg[model_name]["composite_score"]

        # Get current active model score
        current_name  = self.get_active()
        current_score = 0.0
        if current_name and current_name in reg:
            current_score = reg[current_name]["composite_score"]

        if new_score > current_score + PROMOTION_MARGIN:
            # Promote
            if current_name and current_name in reg:
                reg[current_name]["promoted"] = False
            reg[model_name]["promoted"] = True
            self._save(reg)
            self.act_path.write_text(model_name)
            reason = (
                f"promoted {model_name} (score={new_score:.4f}) "
                f"over {current_name or 'none'} (score={current_score:.4f}) "
                f"Δ={new_score - current_score:+.4f}"
            )
            log.info(reason)
            print(f"\n  ✅ PROMOTED: {reason}\n")
            return True, reason
        else:
            reason = (
                f"not promoted: {model_name} score={new_score:.4f} "
                f"vs active={current_score:.4f} "
                f"Δ={new_score - current_score:+.4f} < margin={PROMOTION_MARGIN}"
            )
            log.info(reason)
            print(f"\n  ⚠  NOT PROMOTED: {reason}\n")
            return False, reason

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_active(self) -> Optional[str]:
        """Return name of currently active model, or None."""
        if not self.act_path.exists():
            return None
        name = self.act_path.read_text().strip()
        return name if name else None

    def get_best(self) -> Optional[tuple[str, float]]:
        """Return (name, score) of highest-scoring registered model."""
        reg = self._load()
        if not reg:
            return None
        best = max(reg.items(), key=lambda kv: kv[1]["composite_score"])
        return best[0], best[1]["composite_score"]

    def list_all(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x["composite_score"], reverse=True)

    def print_leaderboard(self, n: int = 10) -> None:
        entries = self.list_all()[:n]
        active  = self.get_active()
        print(f"\n  {'─'*60}")
        print(f"  Model Leaderboard (top {n})")
        print(f"  {'─'*60}")
        print(f"  {'Name':<30} {'Score':>7}  {'Acc':>6}  {'Active'}")
        print(f"  {'─'*60}")
        for e in entries:
            flag = " ← ACTIVE" if e["name"] == active else ""
            print(
                f"  {e['name']:<30} {e['composite_score']:>7.4f}  "
                f"{e['accuracy']:>6.4f}  {flag}"
            )
        print(f"  {'─'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN MODEL REGISTRY  (versioned, never overwrites)
# ─────────────────────────────────────────────────────────────────────────────

class GaussianModelRegistry:
    """
    Versioned registry for Gaussian model bundles.

    Each entry stores:
      {version, feature_schema, metrics: {corr, calibration_error, timestamp}}

    NEVER overwrites — every save creates a new version entry.
    Rollback = promote any prior version name.
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "gaussian_registry.json"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.reg_path.exists():
            return {}
        try:
            return json.loads(self.reg_path.read_text())
        except Exception as e:
            log.warning(f"Gaussian registry load failed: {e}")
            return {}

    def _save(self, reg: dict) -> None:
        self.reg_path.write_text(json.dumps(reg, indent=2))

    def register_gaussian(
        self,
        version: str,
        model_file: str,
        feature_schema: list,
        metrics: dict,
    ) -> dict:
        reg = self._load()
        if version in reg:
            log.warning(f"Version {version} already exists — not overwriting")
            return reg[version]

        entry = {
            "version":        version,
            "model_file":     model_file,
            "feature_schema": feature_schema,
            "metrics": {
                "corr_expected_rr":  metrics.get("corr_expected_rr",  0.0),
                "calibration_error": metrics.get("calibration_error", 1.0),
                "n_train":           metrics.get("n_train",           0),
                "n_val":             metrics.get("n_val",             0),
            },
            "trained_at": metrics.get("trained_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            "active":     False,
        }
        reg[version] = entry
        self._save(reg)
        log.info(
            f"GaussianRegistry | registered {version} "
            f"corr={entry['metrics']['corr_expected_rr']:+.4f} "
            f"cal={entry['metrics']['calibration_error']:.4f}"
        )
        return entry

    def promote_gaussian(
        self,
        version: str,
        force: bool = False,
        max_regression: float = 0.01,
    ) -> tuple[bool, str]:
        """
        Promote a Gaussian version to active.

        FIX 3: Compares against current active model metrics.
        Blocks promotion if new model regresses by more than max_regression
        on corr_expected_rr (unless force=True).

        Parameters
        ----------
        version        : version to promote
        force          : bypass performance comparison (use for first deploy or testing)
        max_regression : max allowed corr decrease vs current active (default 0.01 = 1%)
        """
        reg = self._load()
        if version not in reg:
            return False, f"Version {version} not in Gaussian registry"

        new_metrics = reg[version].get("metrics", {})
        new_corr    = new_metrics.get("corr_expected_rr", 0.0)
        new_cal     = new_metrics.get("calibration_error", 1.0)

        current_active = self.get_active_gaussian()

        # First deployment — no comparison needed
        if current_active is None:
            reg[version]["active"] = True
            self._save(reg)
            reason = f"First Gaussian deployment: {version} (corr={new_corr:+.4f})"
            log.info(reason)
            return True, reason

        if current_active not in reg:
            reg[version]["active"] = True
            self._save(reg)
            reason = f"Promoted Gaussian {version} (current active not found in registry)"
            log.info(reason)
            return True, reason

        cur_metrics = reg[current_active].get("metrics", {})
        cur_corr    = cur_metrics.get("corr_expected_rr", 0.0)
        cur_cal     = cur_metrics.get("calibration_error", 1.0)

        if not force:
            # FIX 3: Block if new model regresses on correlation
            if new_corr < cur_corr - max_regression:
                reason = (
                    f"Gaussian promotion BLOCKED (FIX3): {version} corr={new_corr:+.4f} "
                    f"< current {current_active} corr={cur_corr:+.4f} - {max_regression} "
                    f"(regression={cur_corr - new_corr:.4f} > max_regression={max_regression}). "
                    f"Use force=True to override."
                )
                log.warning(reason)
                return False, reason

        # Deactivate current
        reg[current_active]["active"] = False
        reg[version]["active"] = True
        self._save(reg)
        reason = (
            f"Promoted Gaussian {version} (corr={new_corr:+.4f} cal={new_cal:.4f}) "
            f"over {current_active} (corr={cur_corr:+.4f} cal={cur_cal:.4f})"
        )
        log.info(reason)
        return True, reason

    def get_active_gaussian(self) -> Optional[str]:
        reg = self._load()
        for version, entry in reg.items():
            if entry.get("active", False):
                return version
        return None

    def list_gaussian(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x.get("trained_at", ""), reverse=True)

    def print_gaussian_leaderboard(self) -> None:
        entries = self.list_gaussian()
        active  = self.get_active_gaussian()
        print(f"\n  {'─'*65}")
        print(f"  Gaussian Model Leaderboard")
        print(f"  {'─'*65}")
        print(f"  {'Version':<30} {'Corr':>7}  {'CalErr':>7}  {'Active'}")
        print(f"  {'─'*65}")
        for e in entries:
            flag = " ← ACTIVE" if e.get("version") == active else ""
            m = e.get("metrics", {})
            print(
                f"  {e['version']:<30} "
                f"{m.get('corr_expected_rr', 0):>+7.4f}  "
                f"{m.get('calibration_error', 0):>7.4f}  {flag}"
            )
        print(f"  {'─'*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_registry = ModelRegistry()
_gaussian_registry = GaussianModelRegistry()


def register(model_name: str, eval_result: EvalResult) -> ModelEntry:
    return _registry.register(model_name, eval_result)


def try_promote(model_name: str) -> tuple[bool, str]:
    return _registry.try_promote(model_name)


def get_active() -> Optional[str]:
    return _registry.get_active()


def print_leaderboard(n: int = 10) -> None:
    _registry.print_leaderboard(n)


# Gaussian registry convenience functions
def register_gaussian(version: str, model_file: str, feature_schema: list, metrics: dict) -> dict:
    return _gaussian_registry.register_gaussian(version, model_file, feature_schema, metrics)


def promote_gaussian(version: str) -> tuple[bool, str]:
    return _gaussian_registry.promote_gaussian(version)


def get_active_gaussian() -> Optional[str]:
    return _gaussian_registry.get_active_gaussian()


def print_gaussian_leaderboard() -> None:
    _gaussian_registry.print_gaussian_leaderboard()
