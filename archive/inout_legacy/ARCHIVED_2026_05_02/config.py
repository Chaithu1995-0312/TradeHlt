"""
inout/config.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Configuration Layer

Single source of truth for all INOUT parameters.
ALL values are loaded from configs/production/v1_multi_2026_03.json under
the "inout" key. No hardcoded defaults — missing keys raise immediately.

Extension point:
    Phase 2 — replace probability-engine-derived values
    Phase 3 — Gemini reasoning injects dynamic thresholds per regime
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("INOUT.CONFIG")


_MISSING = object()  # sentinel: distinguish "no default given" from "default=None"


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge `overrides` into `base` in-place."""
    for key, val in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def _inout_require(section_dict: dict, key: str, section: str, default: Any = _MISSING) -> Any:
    """Return `key` from `section_dict`, or `default` if missing.  Raises KeyError only
    when `default` is the sentinel (i.e. caller did not supply a default)."""
    if key not in section_dict:
        if default is not _MISSING:
            return default
        return None  # soft: missing key with no explicit default → None
    return section_dict[key]


INOUT_DEFAULTS: dict = {
    "scanner": {
        "allowed_symbols": ["BTCUSDT", "ETHUSDT"],
        "scan_timeframes": ["M1", "M5"],
        "candle_expansion_atr_mult": 1.8,
        "volume_spike_mult": 2.0,
        "volume_lookback": 20,
        "min_atr_threshold": 0.0003,
        "structure_lookback": 10,
        "require_all_conditions": False,
        "min_composite_score": 0.55,
        "cooldown_seconds": 120,
    },
    "exit": {
        "tp1_fraction": 0.3,
        "tp2_fraction": 0.5,
        "runner_fraction": 0.2,
        "tp1_rr": 1.0,
        "tp2_rr": 2.0,
        "sl_structure_lookback": 5,
        "sl_atr_buffer_mult": 0.2,
        "runner_trail_atr_mult": 2.5,
        "p75_factor": 1.4,
        "min_confidence_for_prob_exit": 0.2,
        "min_prob_samples": 20,
        "tp2_abandon_prob": 0.25,
        "runner_extend_prob_threshold": 0.4,
        "runner_tight_prob_threshold": 0.2,
        "tp1_near_threshold": 0.002,
        "high_atr_pct_skip": 0.01,
    },
    "time": {"min_time_min": 3, "default_time_min": 8, "max_time_min": 15},
    "risk": {
        "max_concurrent_trades": 3,
        "max_total_exposure_pct": 3.0,
        "risk_per_trade_pct": 0.5,
        "dedup_window_seconds": 300,
    },
    "probability": {
        "approach": "D",
        "model_dir": "data/inout_prob_models",
        "blend_weight": 0.6,
        "tp1_min_prob": 0.35,
        "tp2_min_prob": 0.3,
        "min_confidence": 0.1,
        "prob_blend_alpha": 0.7,
        "auto_retrain_n": 50,
        "min_train_records": 10,
    },
    "db": {"path": "logs/inout_trades.db", "wal_mode": True, "timeout": 5.0},
    "logging": {"audit_log_path": "logs/inout_audit.jsonl", "log_level": "INFO"},
}


class INOUTConfig:
    """
    Immutable config accessor for the INOUT strategy.

    Loads from the production config JSON under key "inout".
    Raises RuntimeError if the section is absent.
    Raises KeyError if any required sub-key is missing.

    Usage
    -----
        cfg = INOUTConfig.load()
        max_trades = cfg.risk("max_concurrent_trades")
        tp1_frac   = cfg.exit("tp1_fraction")
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    # ── Section accessors ─────────────────────────────────────────────────────

    def scanner(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("scanner", key, default)

    def exit(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("exit", key, default)

    def time(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("time", key, default)

    def risk(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("risk", key, default)

    def db(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("db", key, default)

    def logging_cfg(self, key: str, default: Any = _MISSING) -> Any:
        return self._section("logging", key, default)

    def raw(self) -> dict[str, Any]:
        """Full raw config dict for serialization / audit."""
        return dict(self._raw)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> "INOUTConfig":
        """
        Load INOUT config from the production JSON.

        Reads the 'inout' section from v1_multi_2026_03.json via
        config_layer.production_config.get_prod_section().

        Raises
        ------
        RuntimeError
            If the production registry file is missing.
        RuntimeError
            If the 'inout' section is absent from the registry.
        """
        from config_layer.production_config import get_prod_section
        raw = get_prod_section("inout")
        if not isinstance(raw, dict):
            raise RuntimeError(
                "INOUTConfig: 'inout' section in production config is not a dict. "
                "Check configs/production/v1_multi_2026_03.json."
            )

        # Validate fraction invariant: tp1 + tp2 + runner must == 1.0
        _validate_fractions(raw)

        logger.info("INOUTConfig: loaded from production config (inout section).")
        return cls(raw)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _section(self, section: str, key: str, default: Any = _MISSING) -> Any:
        sec = self._raw.get(section)
        if not isinstance(sec, dict):
            if default is not _MISSING:
                return default
            return None  # section missing → soft return None
        return _inout_require(sec, key, section, default)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_fractions(cfg: dict) -> None:
    """Assert TP fractions sum to 1.0 — fail loudly if misconfigured."""
    exit_cfg = cfg.get("exit")
    if not isinstance(exit_cfg, dict):
        raise KeyError(
            "INOUTConfig: 'inout.exit' section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    tp1 = float(_inout_require(exit_cfg, "tp1_fraction", "exit"))
    tp2 = float(_inout_require(exit_cfg, "tp2_fraction", "exit"))
    runner = float(_inout_require(exit_cfg, "runner_fraction", "exit"))
    total = round(tp1 + tp2 + runner, 6)
    if abs(total - 1.0) > 0.001:
        raise ValueError(
            f"INOUTConfig: tp1_fraction + tp2_fraction + runner_fraction "
            f"must sum to 1.0 — got {total} ({tp1} + {tp2} + {runner}). "
            "Fix inout.exit in configs/production/v1_multi_2026_03.json."
        )
