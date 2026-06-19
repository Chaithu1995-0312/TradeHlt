"""
coverage — the permanent broker-semantics ledger (Phase 5.6C/D/G).

Reads MT5 deal history (read-only), characterizes which reconstruction patterns reality
has exercised, and persists four artifacts under `<report_root>/reality/`:
  • deal_coverage.json   — per-run counts + maturity score
  • coverage_gaps.json   — {validated, missing} vs EXPECTED_PATTERNS
  • deal_coverage.md     — human view
  • broker_semantics.json — MONOTONIC per-broker capability map (OR-merged every run)

Observed semantics become permanently documented; missing ones stay explicit until a real
trade exercises them. As real history accrues, this becomes a broker-specific semantic DB.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

from ..analytics_config import _require, load_config
from ..engines.deal_characterizer import (
    EXPECTED_PATTERNS,
    broker_capabilities,
    characterize_deal_stream,
    coverage_gaps,
    coverage_score,
    to_markdown,
)


def coverage_report(deals) -> dict:
    """Pure: counts + gaps + maturity score for a deal stream."""
    counts = characterize_deal_stream(deals)
    return {"counts": counts, "gaps": coverage_gaps(counts),
            "score": coverage_score(counts)}


def _merge_broker_semantics(path: Path, broker_key: str, counts: dict) -> dict:
    """Monotonic OR-merge: once a pattern is observed True for a broker, it stays True."""
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    caps = dict(existing.get(broker_key, {}))
    observed = broker_capabilities(counts)
    for p in EXPECTED_PATTERNS:
        caps[p] = bool(caps.get(p, False) or observed.get(p, False))
    existing[broker_key] = caps
    return existing


def run(date_from: _dt.datetime, date_to: _dt.datetime, *, cfg: "dict | None" = None) -> dict:
    """Live wrapper: read deals, characterize, persist the four artifacts + audit line."""
    from .audit import append_audit
    from .mt5_adapter import MT5Adapter

    cfg = cfg or load_config()
    reality = Path(str(_require(cfg, "report_root"))) / "reality"
    reality.mkdir(parents=True, exist_ok=True)

    with MT5Adapter(server_utc_offset_hours=cfg.get("server_utc_offset_hours")) as adapter:
        deals = adapter.history_deals_get(date_from, date_to)
        info = adapter.account_info()

    rep = coverage_report(deals)
    counts, gaps, score = rep["counts"], rep["gaps"], rep["score"]

    (reality / "deal_coverage.json").write_text(
        json.dumps({**counts, **score}, indent=2, sort_keys=True), encoding="utf-8")
    (reality / "coverage_gaps.json").write_text(
        json.dumps(gaps, indent=2, sort_keys=True), encoding="utf-8")
    (reality / "deal_coverage.md").write_text(to_markdown(counts), encoding="utf-8")

    broker_key = f"{info.get('company', '?')}|{info.get('server', '?')}"
    bs_path = reality / "broker_semantics.json"
    bs_path.write_text(
        json.dumps(_merge_broker_semantics(bs_path, broker_key, counts),
                   indent=2, sort_keys=True), encoding="utf-8")

    append_audit("coverage_run", {**counts, **score, "broker": broker_key}, cfg=cfg)
    return rep


def _parse_date(s: str) -> _dt.datetime:
    return _dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="MT5 broker-semantics coverage")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD (UTC)")
    args = ap.parse_args(argv)
    rep = run(_parse_date(args.date_from), _parse_date(args.date_to))
    print(to_markdown(rep["counts"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
