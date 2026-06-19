"""
Phase 6 — verification reconcile (MT5 truth ↔ artifacts).

Zero-trade PASS, happy-path PASS, and each corruption lever independently → FAIL.
"""
from __future__ import annotations

import json

from conftest import M15, make_bar, make_deal  # type: ignore

from mt5_analytics.analytics_config import load_config
from mt5_analytics.core.shared_pipeline import process_closed_positions
from mt5_analytics.core.verify import reconcile
from mt5_analytics.engines.position_reconstructor import (
    DEAL_ENTRY_IN,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BUY,
    DEAL_TYPE_SELL,
)
from mt5_analytics.providers.fixture_provider import FixtureProvider
from mt5_analytics.storage.partition_writer import PartitionWriter

_DAY = (1_700_000_000 // 86400) * 86400


def _build(root):
    """Run the pipeline for one closed position into `root`; return its deals."""
    entry_t, exit_t = _DAY + 9 * 3600, _DAY + 10 * 3600
    deals = [
        make_deal(2000, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY,
                  volume=1.0, price=100.0, t=entry_t),
        make_deal(2000, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL,
                  volume=1.0, price=110.0, t=exit_t, profit=10.0),
    ]
    orders = [{"position_id": 2000, "sl": 98.0}]
    bars, t = [], _DAY + 8 * 3600
    while t <= exit_t:
        bars.append(make_bar(t, 100.0, 102.0, 99.0, 101.0))
        t += M15
    process_closed_positions(
        deals, orders=orders, candle_provider=FixtureProvider({"EURUSD": bars}),
        episode_writer=PartitionWriter(root, "episodes"),
        feature_writer=PartitionWriter(root, "features"), generated_by="test",
    )
    return deals


def _episode_file(root):
    return next(root.glob("episodes/*/*/*/episodes.jsonl"))


def test_zero_trade_passes(tmp_path):
    rep = reconcile([], tmp_path)
    assert rep.status == "PASS"
    assert rep.mt5_positions == 0 and rep.artifact_episodes == 0


def test_balance_deposit_deal_ignored(tmp_path):
    # Reality regression (live demo run): a deposit deal is position_id=0, type=2,
    # volume=0, profit=<balance>. It must NOT count as a trade or pollute the P/L oracle.
    balance_deal = make_deal(0, 8798384121, entry=0, deal_type=2, volume=0.0,
                             price=0.0, t=_DAY, profit=100000.0, symbol="")
    rep = reconcile([balance_deal], tmp_path)
    assert rep.status == "PASS"
    assert rep.mt5_positions == 0 and rep.net_pnl_diff == 0.0


def test_happy_path_passes(tmp_path):
    deals = _build(tmp_path)
    rep = reconcile(deals, tmp_path)
    assert rep.status == "PASS", rep.discrepancies
    assert rep.mt5_positions == 1 and rep.artifact_episodes == 1
    assert rep.net_pnl_diff == 0.0 and rep.volume_diff == 0.0 and rep.manifests_ok


def test_tampered_pnl_fails(tmp_path):
    deals = _build(tmp_path)
    f = _episode_file(tmp_path)
    rec = json.loads(f.read_text().splitlines()[0])
    rec["net_pnl"] = rec["net_pnl"] + 5.0                     # corrupt the P/L
    f.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    rep = reconcile(deals, tmp_path)
    assert rep.status == "FAIL" and rep.net_pnl_diff > 0


def test_missing_record_fails(tmp_path):
    deals = _build(tmp_path)
    _episode_file(tmp_path).write_text("", encoding="utf-8")  # drop the episode
    rep = reconcile(deals, tmp_path)
    assert rep.status == "FAIL" and rep.missing


def test_duplicate_record_fails(tmp_path):
    deals = _build(tmp_path)
    f = _episode_file(tmp_path)
    line = f.read_text().splitlines()[0]
    f.write_text(line + "\n" + line + "\n", encoding="utf-8")  # duplicate
    rep = reconcile(deals, tmp_path)
    assert rep.status == "FAIL" and rep.duplicate


def test_tampered_manifest_fails(tmp_path):
    deals = _build(tmp_path)
    mf = _episode_file(tmp_path).parent / "manifest.json"
    m = json.loads(mf.read_text())
    m["sha256"] = "deadbeef"
    mf.write_text(json.dumps(m), encoding="utf-8")
    rep = reconcile(deals, tmp_path)
    assert rep.status == "FAIL" and rep.manifests_ok is False


def test_markdown_render(tmp_path):
    deals = _build(tmp_path)
    md = reconcile(deals, tmp_path).to_markdown()
    assert "**Status:**" in md and "MT5 positions" in md
