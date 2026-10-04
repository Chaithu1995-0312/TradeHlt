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
    classify,
    coverage_gaps,
    coverage_score,
    reachable_patterns,
    to_markdown,
)
from ..engines.position_reconstructor import is_position_deal


def _account_type(margin_mode) -> str:
    return {0: "netting", 1: "exchange", 2: "hedging"}.get(int(margin_mode), str(margin_mode))


def coverage_report(deals, *, reachable: "set | None" = None) -> dict:
    """Pure: counts + gaps + maturity score. Account-aware when `reachable` is supplied."""
    counts = characterize_deal_stream(deals)
    return {
        "counts": counts,
        "gaps": coverage_gaps(counts, reachable),
        "score": coverage_score(counts, reachable),
        "classification": classify(counts, reachable) if reachable is not None else None,
    }


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

    # Account-aware reachability (Reality Classification): score against what THIS broker
    # can structurally emit, not against all conceivable patterns.
    margin_mode = info.get("margin_mode", 2)   # default hedging if unknown
    commission_charged = any(
        float(d.get("commission", 0.0) or 0.0) != 0.0 for d in deals if is_position_deal(d))
    reachable = reachable_patterns(margin_mode, commission_charged)

    rep = coverage_report(deals, reachable=reachable)
    counts, gaps, score = rep["counts"], rep["gaps"], rep["score"]

    (reality / "deal_coverage.json").write_text(
        json.dumps({**counts, **score, "account_type": _account_type(margin_mode),
                    "margin_mode": margin_mode, "reachable": sorted(reachable),
                    "classification": rep["classification"]},
                   indent=2, sort_keys=True), encoding="utf-8")
    (reality / "coverage_gaps.json").write_text(
        json.dumps(gaps, indent=2, sort_keys=True), encoding="utf-8")
    (reality / "deal_coverage.md").write_text(
        to_markdown(counts, reachable), encoding="utf-8")

    # Key by margin_mode too: a single broker (same company|server) exposes DIFFERENT
    # reachable semantics per account type (netting mm0 unlocks pyramid/INOUT/reopen that
    # hedging mm2 cannot emit). Merging them would falsely claim hedging observed INOUT.
    broker_key = f"{info.get('company', '?')}|{info.get('server', '?')}|mm{margin_mode}"
    bs_path = reality / "broker_semantics.json"
    merged = _merge_broker_semantics(bs_path, broker_key, counts)
    merged[broker_key]["_margin_mode"] = margin_mode   # account context (not a pattern)
    bs_path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")

    append_audit("coverage_run",
                 {**counts, **score, "broker": broker_key,
                  "account_type": _account_type(margin_mode)}, cfg=cfg)
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
