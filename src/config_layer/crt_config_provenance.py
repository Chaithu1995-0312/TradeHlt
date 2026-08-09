"""CRTConfig construction provenance — P1 OBSERVE (F-057 class).

Side registry keyed by id(cfg). Does not mutate CRTConfig (frozen, may hold dicts).
Grants no fail-closed product authority — that is P2.

Protocol: docs/governance/CRT_CONFIG_CONSTRUCTION_PROTOCOL.md
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from config_layer.state_identity import CRTConfig

logger = logging.getLogger("CRT.config_provenance")

# Cap observe log so long processes cannot grow unbounded.
_MAX_OBSERVE_EVENTS = 5000


class ConstructionMode(str, Enum):
    """How a CRTConfig instance was obtained."""

    PRODUCTION_MERGED = "PRODUCTION_MERGED"
    ROUTER_BASE = "ROUTER_BASE"
    EXPLICIT = "EXPLICIT"
    SCHEMA = "SCHEMA"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CRTConfigProvenance:
    mode: ConstructionMode
    instrument: Optional[str] = None
    version: Optional[str] = None
    override_keys: tuple[str, ...] = ()
    stamped_utc: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "instrument": self.instrument,
            "version": self.version,
            "override_keys": list(self.override_keys),
            "stamped_utc": self.stamped_utc,
            "note": self.note,
        }


# id(cfg) → provenance  (CRTConfig not hashable when nested dicts present)
_registry: dict[int, CRTConfigProvenance] = {}
_observe_log: list[dict[str, Any]] = []
_lock = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(cfg: CRTConfig) -> tuple:
    """Stable threshold fingerprint for loader comparison (not full equality)."""
    return (
        float(cfg.body_ratio_min),
        float(cfg.atr_multiplier_min),
        float(cfg.expansion_atr_min_distance),
        float(cfg.retest_depth_max),
        float(cfg.retest_atr_depth_fraction),
        float(cfg.atr_min_displacement),
    )


def stamp(
    cfg: CRTConfig,
    mode: ConstructionMode,
    *,
    instrument: Optional[str] = None,
    version: Optional[str] = None,
    override_keys: Optional[list[str] | tuple[str, ...]] = None,
    note: str = "",
    log: bool = True,
) -> CRTConfigProvenance:
    """Record provenance for a CRTConfig instance (observe-only)."""
    prov = CRTConfigProvenance(
        mode=mode,
        instrument=instrument,
        version=version,
        override_keys=tuple(sorted(override_keys or ())),
        stamped_utc=_utc_now(),
        note=note,
    )
    with _lock:
        _registry[id(cfg)] = prov
        event = {
            "event": "CRT_CONFIG_STAMP",
            **prov.to_dict(),
            "fingerprint": list(fingerprint(cfg)),
        }
        _observe_log.append(event)
        if len(_observe_log) > _MAX_OBSERVE_EVENTS:
            del _observe_log[: len(_observe_log) - _MAX_OBSERVE_EVENTS]

    if log:
        level = logging.WARNING if mode == ConstructionMode.ROUTER_BASE else logging.DEBUG
        logger.log(
            level,
            "CRTConfig stamped mode=%s instrument=%s version=%s overrides=%s fp=%s",
            mode.value,
            instrument,
            version,
            prov.override_keys,
            fingerprint(cfg),
        )
        if mode == ConstructionMode.ROUTER_BASE:
            logger.warning(
                "F-057 observe: ROUTER_BASE CRTConfig is NOT production-merged. "
                "For live-equivalent thresholds use load_prod_config_from_registry. "
                "instrument=%s fp=%s",
                instrument,
                fingerprint(cfg),
            )
    return prov


def get_provenance(cfg: CRTConfig) -> CRTConfigProvenance:
    """Return provenance or UNKNOWN if never stamped (this process)."""
    with _lock:
        return _registry.get(
            id(cfg),
            CRTConfigProvenance(
                mode=ConstructionMode.UNKNOWN,
                stamped_utc="",
                note="no stamp in this process",
            ),
        )


def clear_registry() -> None:
    """Test helper — clear stamps and observe log."""
    with _lock:
        _registry.clear()
        _observe_log.clear()


def observe_log_snapshot() -> list[dict[str, Any]]:
    with _lock:
        return list(_observe_log)


# Product entry points (BacktestRunner, etc.) accept these without allow_router_base.
PRODUCT_ADMISSIBLE_MODES: frozenset[ConstructionMode] = frozenset(
    {
        ConstructionMode.PRODUCTION_MERGED,
        ConstructionMode.EXPLICIT,
    }
)


def require_mode(
    cfg: CRTConfig,
    allowed: set[ConstructionMode] | frozenset[ConstructionMode],
    *,
    context: str = "",
    fail_closed: bool | None = None,
) -> ConstructionMode:
    """Check construction mode against *allowed*.

    * fail_closed=None (default): raise if CRT_CONFIG_STRICT=1, else warn (P1).
    * fail_closed=True: always raise on mismatch (P2 product paths).
    * fail_closed=False: warn only.
    """
    prov = get_provenance(cfg)
    mode = prov.mode
    if mode in allowed:
        return mode

    msg = (
        f"CRTConfig mode {mode.value} not in {[m.value for m in allowed]} "
        f"context={context!r} instrument={prov.instrument!r}. "
        f"Use load_prod_config_from_registry for PRODUCTION_MERGED, "
        f"mark_explicit()/from_existing for EXPLICIT tests, or "
        f"allow_router_crt_config=True only when ROUTER_BASE is intentional."
    )
    if fail_closed is None:
        fail_closed = os.environ.get("CRT_CONFIG_STRICT", "").strip() in (
            "1", "true", "TRUE", "yes",
        )
    if fail_closed:
        raise RuntimeError(f"F-057 product gate: {msg}")
    logger.warning("F-057 observe (non-strict): %s", msg)
    return mode


def assert_product_crt_config(
    cfg: CRTConfig,
    *,
    context: str,
    allow_router_base: bool = False,
) -> ConstructionMode:
    """P2 fail-closed for product entry points (BacktestRunner, etc.).

    Allows PRODUCTION_MERGED and EXPLICIT always.
    Allows ROUTER_BASE only when allow_router_base=True (escape hatch).
    Rejects SCHEMA and UNKNOWN always on product paths.
    """
    allowed: set[ConstructionMode] = set(PRODUCT_ADMISSIBLE_MODES)
    if allow_router_base:
        allowed.add(ConstructionMode.ROUTER_BASE)
    return require_mode(cfg, allowed, context=context, fail_closed=True)


def mark_explicit(
    cfg: CRTConfig,
    *,
    instrument: Optional[str] = None,
    note: str = "caller-marked EXPLICIT (test/A-B/injected)",
) -> CRTConfig:
    """Stamp an existing CRTConfig as EXPLICIT (tests / intentional inject). Returns cfg."""
    stamp(
        cfg,
        ConstructionMode.EXPLICIT,
        instrument=instrument,
        note=note,
        log=False,
    )
    return cfg


def schema_fingerprint() -> tuple:
    return fingerprint(CRTConfig())


def compare_surfaces(instrument: str, version: Optional[str] = None) -> dict[str, Any]:
    """Live three-way fingerprint for census / multi-agent checks."""
    from config_layer.config_builder import ConfigBuilder
    from config_layer.production_config import get_active_version, load_prod_config_from_registry

    ver = version or get_active_version()
    schema = CRTConfig()
    router = ConfigBuilder.build(instrument)
    prod = load_prod_config_from_registry(ver, instrument)
    return {
        "instrument": instrument,
        "version": ver,
        "schema": {
            "mode": ConstructionMode.SCHEMA.value,
            "fp": list(fingerprint(schema)),
            "body_ratio_min": schema.body_ratio_min,
            "expansion_atr_min_distance": schema.expansion_atr_min_distance,
        },
        "router_base": {
            "mode": get_provenance(router).mode.value,
            "fp": list(fingerprint(router)),
            "body_ratio_min": router.body_ratio_min,
            "expansion_atr_min_distance": router.expansion_atr_min_distance,
        },
        "production_merged": {
            "mode": get_provenance(prod).mode.value,
            "fp": list(fingerprint(prod)),
            "body_ratio_min": prod.body_ratio_min,
            "expansion_atr_min_distance": prod.expansion_atr_min_distance,
        },
        "router_equals_prod": fingerprint(router) == fingerprint(prod),
        "schema_equals_prod": fingerprint(schema) == fingerprint(prod),
    }
