"""
ingest_live_outcomes.py
=======================
Pairs live alerts (logs/live_alerts.jsonl) with manually-supplied execution
outcomes to produce trainable records suitable for the Pipeline-B Gaussian
calibration path.

Why
---
Live mode never auto-executes — humans place the orders. The system only
emits alerts. Closing the feedback loop on live data requires ingesting the
outcomes back manually. This script reads:

  1. The alert log written by LiveEngine.process() — each alert carries
     {alert_id, features, direction, timestamp, ...}
  2. A user-supplied outcomes file (CSV or JSONL) keyed by alert_id with
     columns {alert_id, pnl_rr_net, exit_reason, win}

And emits a JSONL whose schema matches what
``TradeDataset.from_opportunities()`` already consumes (and what
``from_live_alerts()`` wraps), so no extra adapter is needed in
phase5_calibration.

Output schema (per line)
------------------------
{
  "timestamp":   <alert timestamp>,
  "instrument":  <symbol>,
  "direction":   "long" | "short",
  "features":    {<35 canonical keys>: float, ...},
  "rr_achieved": <float>,
  "outcome":     "WIN" | "LOSS" | "BREAKEVEN",
  "exit_reason": <str>,
  "alert_id":    <str>,
  "source":      "live_alerts"
}

CLI
---
python scripts/research/ingest_live_outcomes.py \
    --alert-log logs/live_alerts.jsonl \
    --outcomes  outcomes.csv \
    --output    logs/live_training.jsonl

The outcomes file may be CSV (header: alert_id,pnl_rr_net,exit_reason,win) or
JSONL with the same field names. Rows whose alert_id is not present in the
alert log are skipped with a WARNING. Alerts with no matching outcome are
skipped silently (they're presumed open / unplaced).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

_LOG = logging.getLogger("IngestLiveOutcomes")


def _load_alerts(path: Path) -> dict[str, dict]:
    """Read live_alerts.jsonl and index by alert_id. Records missing alert_id
    (decision='BLOCK' before snapshot, etc.) are skipped."""
    if not path.exists():
        raise FileNotFoundError(f"alert log not found: {path}")
    by_id: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            aid = rec.get("alert_id")
            if not aid:
                continue
            # Keep the latest record per alert_id (alerts may be rewritten on
            # status change inside one decision cycle).
            by_id[aid] = rec
    return by_id


def _load_outcomes(path: Path) -> list[dict]:
    """Accept CSV or JSONL — distinguish by suffix."""
    if not path.exists():
        raise FileNotFoundError(f"outcomes file not found: {path}")
    rows: list[dict] = []
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(dict(row))
    return rows


def _classify_outcome(pnl_rr_net: float) -> str:
    if pnl_rr_net > 0.05:
        return "WIN"
    if pnl_rr_net < -0.05:
        return "LOSS"
    return "BREAKEVEN"


def _merge(alert: dict, outcome: dict) -> dict | None:
    """Combine one alert + one outcome into a training-ready record."""
    feats = alert.get("features")
    if not isinstance(feats, dict) or not feats:
        return None  # alert never reached the snapshot stage — unusable
    try:
        rr = float(outcome.get("pnl_rr_net", outcome.get("rr_achieved", 0.0)))
    except (TypeError, ValueError):
        return None
    direction = str(alert.get("direction", "")).lower() or "long"
    return {
        "timestamp":   alert.get("candle_ts") or alert.get("timestamp"),
        "instrument":  alert.get("symbol", ""),
        "direction":   direction,
        "features":    feats,
        "rr_achieved": rr,
        "outcome":     str(outcome.get("outcome") or _classify_outcome(rr)),
        "exit_reason": str(outcome.get("exit_reason", "")),
        "alert_id":    alert.get("alert_id"),
        "source":      "live_alerts",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alert-log", type=Path, required=True,
                    help="Path to logs/live_alerts.jsonl produced by LiveEngine")
    ap.add_argument("--outcomes", type=Path, required=True,
                    help="CSV or JSONL with columns: alert_id, pnl_rr_net, "
                         "exit_reason, [win], [outcome]")
    ap.add_argument("--output", type=Path, required=True,
                    help="Output JSONL — compatible with "
                         "TradeDataset.from_live_alerts() / from_opportunities()")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    alerts = _load_alerts(args.alert_log)
    _LOG.info("Indexed %d alerts from %s", len(alerts), args.alert_log)

    outcomes = _load_outcomes(args.outcomes)
    _LOG.info("Loaded %d outcome rows from %s", len(outcomes), args.outcomes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    matched = unmatched = unusable = 0
    with args.output.open("w", encoding="utf-8") as out_fh:
        for row in outcomes:
            aid = row.get("alert_id")
            if not aid:
                continue
            alert = alerts.get(aid)
            if alert is None:
                _LOG.warning("Outcome alert_id=%s has no matching alert", aid)
                unmatched += 1
                continue
            rec = _merge(alert, row)
            if rec is None:
                unusable += 1
                continue
            out_fh.write(json.dumps(rec, default=str) + "\n")
            matched += 1

    _LOG.info(
        "Ingest complete: matched=%d unmatched=%d unusable=%d -> %s",
        matched, unmatched, unusable, args.output,
    )
    print(f"OUTPUT:training_jsonl:{args.output.resolve()}")
    return 0 if matched > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
