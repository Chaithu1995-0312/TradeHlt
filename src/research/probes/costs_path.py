"""SEM-015 cost + TIMEOUT net-R path shared by economic probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from research.costs import ComponentCostModel
from research.probes.horizon import close_at_horizon

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = (
    _ROOT / "results/research/xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)


def load_cost_model(
    manifest_path: Path | None = None,
    instrument: str = "XAUUSD",
) -> ComponentCostModel:
    path = Path(manifest_path) if manifest_path is not None else DEFAULT_MANIFEST_PATH
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return ComponentCostModel.from_manifest(
        manifest, instrument=instrument, source=f"{path.name}",
    )


def net_r(
    corpus: list[dict],
    bar_index: int,
    direction: str,
    atr: float,
    cost_model: ComponentCostModel,
    horizon: int,
) -> Optional[float]:
    gross = close_at_horizon(corpus, bar_index, direction, atr, horizon)
    if gross is None:
        return None
    side = "long" if direction == "LONG" else "short"
    cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=side, nights_held=0) / atr
    return gross - cost_r
