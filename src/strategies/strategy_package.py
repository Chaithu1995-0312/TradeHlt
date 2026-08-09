"""
strategy_package.py
================================================================================
StrategyPackage — target-strategy-architecture.md §8 Strategy Registry, the
versioned view over "what we trade with": feature use + thresholds + model pins
+ risk + provenance.

This is a PROJECTION, never a second source of formula meaning (§8 "must
complement, not replace"). `.from_active_config()` reads the already-authoritative
production JSON sections (via `production_config.get_prod_section` /
`get_prod_metadata`) and the model registries (`core.model_registry`) — it does
not compute or invent any threshold. Changing a strategy's behavior still means
editing the production config and going through the promotion path (§13.5 /
§14.C "Promotion activates strategy version only via existing governance").

`features_used` defaults to the full `CANONICAL_FEATURES` schema because no
consumer in this codebase declares a used-subset yet (§14.C: "Schema for
strategy version" is a checklist item, not solved here) — a curated subset
requires a per-strategy feature-selection contract this repo doesn't have.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple

from config_layer.production_config import get_prod_metadata, get_prod_section, PROD_VERSION
from features.feature_schema import CANONICAL_FEATURES


@dataclass(frozen=True)
class StrategyPackage:
    """Versioned strategy package (target-strategy-architecture.md §8).

    A frozen, JSON-round-trippable value object. `thresholds`/`risk`/`model`
    are plain dicts (not further-typed dataclasses) because they are a direct
    projection of already-governed config sections — adding a parallel typed
    schema here would be a second source of truth for those fields.
    """

    name: str
    version: str
    features_used: Tuple[str, ...]
    thresholds: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    risk: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["features_used"] = list(self.features_used)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyPackage":
        d = dict(d)
        d["features_used"] = tuple(d.get("features_used") or ())
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def content_hash(self) -> str:
        """Stable sha256 over the package content (excludes nothing — the whole
        package, including provenance, is what gets stamped on a trade)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_active_config(
        cls,
        instrument: str,
        name: Optional[str] = None,
        version: Optional[str] = None,
    ) -> "StrategyPackage":
        """Project the ACTIVE production config + model registries into a
        StrategyPackage for `instrument`. Raises if a required section is
        missing (no silent default — CLAUDE.md §6.5).
        """
        meta = get_prod_metadata()
        params = get_prod_section("params")
        risk_cfg = get_prod_section("ultron_risk_gate")
        planner_cfg = get_prod_section("execution_planner")

        thresholds = {
            k: v for k, v in params.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }

        model = _resolve_model_pins(instrument)

        risk = {
            "max_risk_per_trade_pct": risk_cfg.get("max_risk_per_trade_pct"),
            "max_portfolio_risk_pct": risk_cfg.get("max_portfolio_risk_pct"),
            "max_trades_per_day":     risk_cfg.get("max_trades_per_day"),
            "max_daily_loss_pct":     risk_cfg.get("max_daily_loss_pct"),
            "min_rr_ratio":           risk_cfg.get("min_rr_ratio"),
            "risk_percent":           planner_cfg.get("risk_percent"),
        }

        provenance = {
            "parent_config":       PROD_VERSION,
            "config_hash":         meta.get("config_hash"),
            "config_id":           meta.get("config_id"),
            "promoted_at":         meta.get("promoted_at"),
            "instrument":          instrument,
        }

        return cls(
            name=name or f"active_{instrument.lower()}",
            version=version or PROD_VERSION,
            features_used=tuple(CANONICAL_FEATURES),
            thresholds=thresholds,
            model=model,
            risk=risk,
            provenance=provenance,
        )


def _resolve_model_pins(instrument: str) -> dict:
    """Best-effort model-pin resolution — a registry lookup failure (e.g. no
    active entry yet for this instrument/model family) degrades that single
    pin to None rather than failing the whole package projection; this mirrors
    the registries' own Optional[str] return contracts."""
    from core import model_registry as _mr

    def _safe(fn, *args):
        try:
            return fn(*args)
        except Exception:
            return None

    return {
        "gaussian_impl":     get_prod_section("engine_runner").get("gaussian_impl"),
        "gaussian_version":  _safe(_mr.get_active_version, instrument),
        "zone_gate_version": _safe(_mr.get_active_zone_gate),
        "rr_version":        _safe(_mr.get_active_rr),
        "tradenet_version":  _safe(_mr.get_active_tradenet_version, instrument),
        "bitnet":            None if not get_prod_section("crt_engine").get("use_bitnet") else "enabled",
    }
