"""Stage-1 dual-engine adapters: regime / trap / breakout (A1-A3).

These three wrap the module-level functions in ``core.engine_runner``
(``detect_regime``, ``trap_engine``, ``breakout_engine``) that the live spine
calls at :839 and :953-954. All three read ``engine_runner.dual_engine``.

STRICTNESS NOTE (deliberate divergence from the wrapped engines)
---------------------------------------------------------------
The production functions read features with ``features.get(name)`` wrapped in
``_safe_float(..., 0.0)`` — a **missing feature silently becomes 0.0**, which
would make an offline observation quietly wrong rather than loudly broken.
These adapters therefore require their input keys STRICTLY before delegating.
The engines' own config reads are already strict (``_cfg_require``).

This is observation only: the wrapped functions are called unmodified, so the
numbers are the production numbers. Authority: research only (CLAUDE.md §6.5).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.engine_runner import breakout_engine, detect_regime, trap_engine
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext, require_feature_keys


class _DualEngineAdapterBase:
    """Shared strict plumbing for the three dual-engine voters."""

    #: feature keys the wrapped engine actually reads (subclass must set)
    FEATURE_KEYS: tuple[str, ...] = ()
    #: engine_runner.dual_engine keys the wrapped engine requires (subclass must set)
    DUAL_KEYS: tuple[str, ...] = ()

    def __init__(self, *, contract: ModelContract, prod_config: dict[str, Any]):
        self.contract = contract
        er = require_section(prod_config, "engine_runner")
        dual = require_key(er, "dual_engine", path="engine_runner")
        if not isinstance(dual, Mapping):
            raise KeyError(
                "engine_runner.dual_engine must be a mapping, "
                f"got {type(dual).__name__}"
            )
        # Fail fast on every key the wrapped engine will require, at construction
        # time rather than on the first bar.
        for key in self.DUAL_KEYS:
            require_key(dual, key, path="engine_runner.dual_engine")
        self._dual_cfg = dict(dual)

        self.config_sections_read = ["engine_runner"]
        self.config_keys_read = [
            f"engine_runner.dual_engine.{k}" for k in self.DUAL_KEYS
        ]
        self.artifact_info = {
            "path": None,
            "serve": self.contract.entry_point,
            "dual_engine_thresholds": {
                k: self._dual_cfg[k] for k in self.DUAL_KEYS
            },
            "strict_feature_keys": list(self.FEATURE_KEYS),
            "note": (
                "adapter requires feature keys strictly; the wrapped engine "
                "itself would silently default a missing feature to 0.0"
            ),
        }

    def _require(self, features: Mapping[str, float]) -> dict[str, float]:
        require_feature_keys(features, self.FEATURE_KEYS)
        return {k: float(features[k]) for k in self.FEATURE_KEYS}


class RegimeAdapter(_DualEngineAdapterBase):
    """MIAR §3.12 — What market regime currently exists?"""

    FEATURE_KEYS = ("ema_spread", "momentum_score", "volatility_ratio")
    DUAL_KEYS = (
        "trend_strength_threshold",
        "momentum_threshold",
        "range_volatility_threshold",
    )

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        feat = self._require(bar.features)
        label = detect_regime(dict(bar.features), self._dual_cfg)
        if not isinstance(label, str):
            raise TypeError(
                f"detect_regime must return str, got {type(label).__name__}"
            )
        # No "score" key: a regime label is not a score (R6 contract rule —
        # do not synthesise a numeric the model does not emit). The raw inputs
        # and thresholds are emitted so degeneracy (F-061) is directly visible.
        return {
            "regime": label,
            "ema_spread": feat["ema_spread"],
            "momentum_score": feat["momentum_score"],
            "volatility_ratio": feat["volatility_ratio"],
            "trend_strength_threshold": float(
                self._dual_cfg["trend_strength_threshold"]
            ),
            "momentum_threshold": float(self._dual_cfg["momentum_threshold"]),
            "range_volatility_threshold": float(
                self._dual_cfg["range_volatility_threshold"]
            ),
            "semantic": "regime_label",
        }


class TrapAdapter(_DualEngineAdapterBase):
    """MIAR §3.10 — Is trap / deception pressure present?"""

    FEATURE_KEYS = ("sweep_detected", "disp_strength", "trend_bias")
    DUAL_KEYS = ("trap_min_score",)

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        self._require(bar.features)
        native = trap_engine(dict(bar.features), self._dual_cfg)
        if not isinstance(native, dict):
            raise TypeError(
                f"trap_engine must return dict, got {type(native).__name__}"
            )
        return _flatten_meta(native)


class BreakoutAdapter(_DualEngineAdapterBase):
    """MIAR §3.11 — Is breakout-style pressure present?"""

    FEATURE_KEYS = ("trend_bias", "momentum_score", "ema_spread")
    DUAL_KEYS = ("breakout_min_score",)

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        self._require(bar.features)
        native = breakout_engine(dict(bar.features), self._dual_cfg)
        if not isinstance(native, dict):
            raise TypeError(
                f"breakout_engine must return dict, got {type(native).__name__}"
            )
        return _flatten_meta(native)


def _flatten_meta(native: dict[str, Any]) -> dict[str, Any]:
    """Lift the engines' nested ``meta`` dict to ``meta_*`` scalars for CSV.

    Pure reshaping of values the engine already returned — no new quantities.
    """
    out: dict[str, Any] = {}
    for k, v in native.items():
        if k == "meta" and isinstance(v, Mapping):
            for mk, mv in v.items():
                out[f"meta_{mk}"] = mv
        else:
            out[k] = v
    return out


def build_dual_adapter(
    model_id: str, *, contract: ModelContract, prod_config: dict[str, Any]
) -> _DualEngineAdapterBase:
    table: dict[str, type[_DualEngineAdapterBase]] = {
        "regime": RegimeAdapter,
        "trap": TrapAdapter,
        "breakout": BreakoutAdapter,
    }
    if model_id not in table:
        raise KeyError(
            f"build_dual_adapter: unknown model_id={model_id!r}; "
            f"known={sorted(table)}"
        )
    return table[model_id](contract=contract, prod_config=prod_config)


__all__: Sequence[str] = (
    "RegimeAdapter",
    "TrapAdapter",
    "BreakoutAdapter",
    "build_dual_adapter",
)
