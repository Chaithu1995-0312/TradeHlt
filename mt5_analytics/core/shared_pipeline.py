"""
shared_pipeline — the ONE path (the third sacred boundary).

`process_closed_positions()` is the single core that both `rebuild.py` and `daemon.py`
terminate in; neither duplicates reconstruction or feature logic. This is the
anti-divergence boundary that guarantees `rebuild` and `daemon` cannot grow two truths —
the keystone `test_pipeline_parity` proves they produce byte-identical artifacts.

Everything external is INJECTED (candle provider, both partition writers) so the function
is pure-ish and fully testable with synthetic fixtures and no live terminal.
"""
from __future__ import annotations

import datetime as _dt
import logging
import time

from ..analytics_config import _require, load_config
from ..engines.features import feature_engine
from ..engines.features._bars import build_window
from ..engines.position_reconstructor import reconstruct_position_episodes
from ..registry.engine_registry import registry_hash
from ..schemas.feature_v1_0 import FEATURE_SCHEMA_VERSION
from ..schemas.position_episode_v1_0 import SCHEMA_VERSION as EPISODE_SCHEMA_VERSION
from ..schemas.run_summary_v1_0 import RunSummary

logger = logging.getLogger("mt5_analytics.shared_pipeline")

_M15 = 900


def _iso_to_epoch(iso: str) -> int:
    return int(
        _dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    )


def process_closed_positions(
    deals,
    *,
    orders=None,
    candle_provider,
    episode_writer,
    feature_writer,
    cfg: "dict | None" = None,
    open_position_ids=frozenset(),
    lookback_bars: "int | None" = None,
    source_history_window: "dict | None" = None,
    rebuild_id: str = "",
    generated_by: str = "",
) -> RunSummary:
    """Reconstruct → featurize → persist completed positions. The single pipeline core."""
    t0 = time.perf_counter()
    cfg = cfg or load_config()
    atr_period = int(_require(cfg, "atr_period"))
    tercile_window = int(_require(cfg, "regime_tercile_window"))
    if lookback_bars is None:
        lookback_bars = tercile_window + atr_period + 5

    summary = RunSummary(pipeline_version=registry_hash())

    episodes = reconstruct_position_episodes(
        deals, open_position_ids=open_position_ids
    )
    summary.episodes_seen = len(episodes)

    # position_id -> SL price (from history_orders_get); risk basis for realized R.
    sl_map: dict[int, float] = {}
    for o in orders or []:
        pid, sl = o.get("position_id"), o.get("sl")
        if pid is not None and sl:
            sl_map[int(pid)] = float(sl)

    episode_dicts: list[dict] = []
    feature_dicts: list[dict] = []

    for ep in episodes:
        episode_dicts.append(ep.to_dict())
        entry_epoch = _iso_to_epoch(ep.entry_time)
        exit_epoch = _iso_to_epoch(ep.exit_time)
        bars = candle_provider.get_window(
            ep.symbol, entry_epoch - lookback_bars * _M15, exit_epoch
        )
        window, entry_index = build_window(bars, entry_epoch)
        if not window:
            msg = f"no candles for episode {ep.episode_id} ({ep.symbol})"
            logger.warning("shared_pipeline: %s", msg)
            summary.warnings.append(msg)
            summary.episodes_skipped += 1
            continue
        record = feature_engine.compute(
            ep, window, entry_index, sl_price=sl_map.get(ep.position_id), cfg=cfg
        )
        feature_dicts.append(record)

    ep_res = episode_writer.write(
        episode_dicts,
        date_key="exit_time",
        schema_version=EPISODE_SCHEMA_VERSION,
        source_history_window=source_history_window,
        rebuild_id=rebuild_id,
        generated_by=generated_by,
    )
    ft_res = feature_writer.write(
        feature_dicts,
        date_key="exit_time",
        schema_version=FEATURE_SCHEMA_VERSION,
        source_history_window=source_history_window,
        rebuild_id=rebuild_id,
        generated_by=generated_by,
    )

    summary.episodes_written = ep_res["written"]
    summary.features_written = ft_res["written"]
    summary.duplicates_skipped = (
        ep_res["skipped_duplicates"] + ft_res["skipped_duplicates"]
    )
    summary.warning_count = len(summary.warnings)
    summary.anomaly_count = len(summary.anomalies)
    summary.duration_ms = (time.perf_counter() - t0) * 1000.0
    summary.episodes = episode_dicts
    return summary
