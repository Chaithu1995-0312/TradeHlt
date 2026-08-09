"""
HistoricalZoneMapper — every-bar (or batch) zone cluster assignment.

P1a: pure feature-dict mapping. Does NOT import CRT, EngineRunner, Fusion, or
DecisionEngine. Reuses engines.zone_cluster_score.score_zone_cluster so scores
match the EngineRunner hard zone stage under identical knobs + registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from features.feature_schema import CANONICAL_FEATURE_DIM, CANONICAL_FEATURES
from engines.live_engine import BitNetZoneGate
from engines.zone_cluster_score import score_zone_cluster

SCHEMA_VERSION = "zone_map_v1"


def _require(section: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in section:
        raise KeyError(
            f"Required key '{key}' missing from {path}. "
            f"Declare it in production engine_runner (no silent defaults)."
        )
    return section[key]


@dataclass(frozen=True)
class ZoneMapConfig:
    """Strict knobs for historical zone mapping (mirrors engine_runner zone surface)."""

    registry_path: str
    zone_cluster_threshold: float
    top_k: int
    cluster_min_n: int
    cluster_spread_max: float
    zone_min_samples: int = 50
    execution_mode: str = "normal"

    @classmethod
    def from_prod_engine_runner(cls) -> "ZoneMapConfig":
        """Load knobs from active production engine_runner (fail-closed)."""
        from config_layer.production_config import get_prod_section

        er = get_prod_section("engine_runner")
        zg = _require(er, "zone_gate", "engine_runner")
        if not isinstance(zg, Mapping):
            raise TypeError("engine_runner.zone_gate must be a mapping")
        return cls(
            registry_path=str(_require(er, "zone_registry_path", "engine_runner")),
            zone_cluster_threshold=float(
                _require(er, "zone_cluster_threshold", "engine_runner")
            ),
            top_k=int(_require(zg, "top_k", "engine_runner.zone_gate")),
            cluster_min_n=int(_require(zg, "cluster_min_n", "engine_runner.zone_gate")),
            cluster_spread_max=float(
                _require(zg, "cluster_spread_max", "engine_runner.zone_gate")
            ),
            zone_min_samples=int(_require(er, "zone_min_samples", "engine_runner")),
            execution_mode=str(
                _require(er, "zone_gate_execution_mode", "engine_runner")
            ),
        )


class HistoricalZoneMapper:
    """Map feature dicts → zone cluster assignment records (hard path only)."""

    def __init__(self, config: ZoneMapConfig):
        self.config = config
        # Explicit instance — avoid get_zone_gate singleton cross-test pollution.
        self._zone_gate = BitNetZoneGate(
            zone_path=config.registry_path,
            config={
                "zone_min_samples": config.zone_min_samples,
                "zone_gate_top_k": config.top_k,
            },
        )
        self._registry_sha256 = _file_sha256(config.registry_path)

    def map_row(
        self,
        features: Mapping[str, Any],
        *,
        timestamp: Optional[str] = None,
        bar_index: Optional[int] = None,
        instrument: str = "",
    ) -> dict:
        """Score one TRADE_OPENED-shaped (or any-bar) feature dict."""
        feat = dict(features)
        scored = score_zone_cluster(
            feat,
            self._zone_gate,
            zone_cluster_threshold=self.config.zone_cluster_threshold,
            cluster_min_n=self.config.cluster_min_n,
            cluster_spread_max=self.config.cluster_spread_max,
            execution_mode=self.config.execution_mode,
            zone_debug_config=None,
        )
        tops = [float(x) for x in (scored.get("top_scores") or [])]
        best_sc = (
            float(scored["best_zone_score"])
            if scored.get("best_zone_score") is not None
            else (tops[0] if tops else 0.0)
        )
        second_sc = tops[1] if len(tops) > 1 else 0.0
        # Boundary proximity: small margin ⇒ competitive top-2 zones (near Voronoi edge).
        margin = best_sc - second_sc
        return {
            "timestamp": timestamp if timestamp is not None else str(feat.get("timestamp", "")),
            "instrument": instrument,
            "bar_index": bar_index if bar_index is not None else -1,
            "best_zone_id": scored.get("best_zone_id"),
            "best_zone_score": best_sc,
            "second_best_score": second_sc,
            "margin_best_second": margin,
            "top_scores": tops,
            "cluster_score": float(scored["cluster_score"]),
            "passed_cluster_threshold": bool(scored["passed"]),
            "zone_cluster_threshold": float(self.config.zone_cluster_threshold),
            "registry_sha256": self._registry_sha256,
            "feature_schema_dim": CANONICAL_FEATURE_DIM,
            "schema_version": SCHEMA_VERSION,
        }

    def map_frame(
        self,
        rows: Sequence[Mapping[str, Any]],
        *,
        timestamps: Optional[Sequence[str]] = None,
        instrument: str = "",
    ) -> list[dict]:
        """
        Map a batch of feature dicts (one record per row).

        Does not run FeaturePipeline — caller supplies canonical feature dicts.
        """
        if timestamps is not None and len(timestamps) != len(rows):
            raise ValueError(
                f"timestamps length {len(timestamps)} != rows length {len(rows)}"
            )
        out: list[dict] = []
        for i, row in enumerate(rows):
            ts = timestamps[i] if timestamps is not None else None
            out.append(
                self.map_row(
                    row,
                    timestamp=ts,
                    bar_index=i,
                    instrument=instrument,
                )
            )
        return out


def _file_sha256(path: str) -> str:
    import hashlib

    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_neutral_feature_dict(**overrides: Any) -> dict:
    """
    TRADE_OPENED-shaped synthetic feature dict: all CANONICAL_FEATURES present.

    Defaults are finite, adapter-friendly values; override for diversity.
    """
    base = {name: 0.0 for name in CANONICAL_FEATURES}
    base.update(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "volume_ratio": 1.0,
            "ema_fast": 100.2,
            "ema_slow": 100.0,
            "ema_spread": 0.2,
            "momentum_score": 0.1,
            "atr": 0.5,
            "volatility_ratio": 1.0,
            "rsi_14": 50.0,
            "body_ratio": 0.5,
            "disp_strength": 0.3,
            "retest_depth": 0.4,
            "session": 1.0,  # london (canonical int)
            "hour_of_day": 10.0,
        }
    )
    base.update(overrides)
    return base
