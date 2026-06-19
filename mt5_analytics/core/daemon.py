"""
daemon — live incremental tail (a THIN shell over shared_pipeline).

`tick()` is the single, testable iteration: read new deals since the checkpoint, run them
through the SAME `process_closed_positions` core the rebuild uses, advance the checkpoint.
`run()` is the polling loop. Incremental by `last_processed_time` ⇒ O(new deals). The
account snapshot is read for liveness only and never persisted (MT5 owns balance/equity).
"""
from __future__ import annotations

import datetime as _dt
import time

from ..analytics_config import _require, load_config
from ..providers.mt5_provider import MT5CandleProvider
from ..storage.partition_writer import PartitionWriter
from .audit import append_audit
from .checkpoint import load_checkpoint, save_checkpoint
from .mt5_adapter import MT5Adapter
from .shared_pipeline import process_closed_positions


_CHECKPOINT_PATH = "mt5_analytics/state/checkpoint.json"


def tick(adapter, *, cfg: dict, now: "_dt.datetime | None" = None):
    """One incremental iteration. Returns the RunSummary."""
    artifact_root = str(_require(cfg, "artifact_root"))
    cp_path = _CHECKPOINT_PATH
    cp = load_checkpoint(cp_path)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    date_from = _dt.datetime.fromtimestamp(cp.last_processed_time or 0,
                                           tz=_dt.timezone.utc)

    deals = adapter.history_deals_get(date_from, now)
    orders = adapter.history_orders_get(date_from, now)
    summary = process_closed_positions(
        deals,
        orders=orders,
        candle_provider=MT5CandleProvider(adapter),
        episode_writer=PartitionWriter(artifact_root, "episodes"),
        feature_writer=PartitionWriter(artifact_root, "features"),
        cfg=cfg,
        open_position_ids=adapter.open_position_ids(),
        generated_by="daemon.py",
    )

    if deals:
        cp.last_processed_time = max(int(d.get("time", 0)) for d in deals)
        cp.last_processed_ticket = max(int(d.get("ticket", 0)) for d in deals)
        save_checkpoint(cp, cp_path)
    append_audit("daemon_event", summary.to_audit_dict(), cfg=cfg)
    return summary


def run(poll_seconds: int = 30, cfg: "dict | None" = None) -> None:
    """Polling loop (blocks). Ctrl-C to stop."""
    cfg = cfg or load_config()
    with MT5Adapter(server_utc_offset_hours=cfg.get("server_utc_offset_hours")) as adapter:
        while True:
            tick(adapter, cfg=cfg)
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run()
