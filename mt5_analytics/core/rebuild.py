"""
rebuild — explicit batch reconstruction (a THIN shell over shared_pipeline).

Scans an explicit MT5 history range and rewrites artifacts. **Never runs automatically**
(recovery ≠ replay). All real work happens in `shared_pipeline.process_closed_positions`;
this module only wires the MT5 reads + writers + provider. Run:

    python -m mt5_analytics.core.rebuild --from 2024-01-01 --to 2026-06-19
"""
from __future__ import annotations

import argparse
import datetime as _dt

from ..analytics_config import _require, load_config
from ..providers.mt5_provider import MT5CandleProvider
from ..storage.partition_writer import PartitionWriter
from .audit import append_audit
from .mt5_adapter import MT5Adapter
from .shared_pipeline import process_closed_positions


def run(date_from: _dt.datetime, date_to: _dt.datetime, *, cfg: "dict | None" = None):
    """Full-range rebuild. Returns the RunSummary."""
    cfg = cfg or load_config()
    artifact_root = str(_require(cfg, "artifact_root"))
    rebuild_id = _dt.datetime.now(_dt.timezone.utc).strftime("rebuild_%Y%m%dT%H%M%SZ")
    with MT5Adapter(server_utc_offset_hours=cfg.get("server_utc_offset_hours")) as adapter:
        deals = adapter.history_deals_get(date_from, date_to)
        orders = adapter.history_orders_get(date_from, date_to)
        summary = process_closed_positions(
            deals,
            orders=orders,
            candle_provider=MT5CandleProvider(adapter),
            episode_writer=PartitionWriter(artifact_root, "episodes"),
            feature_writer=PartitionWriter(artifact_root, "features"),
            cfg=cfg,
            source_history_window={
                "from": date_from.strftime("%Y-%m-%d"),
                "to": date_to.strftime("%Y-%m-%d"),
            },
            rebuild_id=rebuild_id,
            generated_by="rebuild.py",
        )
    append_audit("rebuild_run", summary.to_audit_dict(), cfg=cfg)
    return summary


def _parse_date(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc)


def main(argv: "list[str] | None" = None) -> None:
    ap = argparse.ArgumentParser(description="MT5 analytics batch rebuild")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD (UTC)")
    args = ap.parse_args(argv)
    summary = run(_parse_date(args.date_from), _parse_date(args.date_to))
    print(summary.to_audit_dict())


if __name__ == "__main__":
    main()
