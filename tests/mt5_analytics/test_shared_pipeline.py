"""
Phase 4 — shared_pipeline end-to-end (deals+orders+fixture candles → artifacts).

Exercises the single core: reconstruct → featurize → persist, with everything injected.
"""
from __future__ import annotations

import json

from conftest import M15, make_bar, make_deal  # type: ignore

from mt5_analytics.core.shared_pipeline import process_closed_positions
from mt5_analytics.engines.position_reconstructor import (
    DEAL_ENTRY_IN,
    DEAL_ENTRY_OUT,
    DEAL_TYPE_BUY,
    DEAL_TYPE_SELL,
)
from mt5_analytics.providers.fixture_provider import FixtureProvider
from mt5_analytics.storage.partition_writer import PartitionWriter
from utils.jsonl_writer import read_jsonl  # type: ignore

_DAY = (1_700_000_000 // 86400) * 86400  # midnight UTC anchor


def _scenario():
    entry_t = _DAY + 9 * 3600
    exit_t = _DAY + 10 * 3600
    deals = [
        make_deal(2000, 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY,
                  volume=1.0, price=100.0, t=entry_t),
        make_deal(2000, 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL,
                  volume=1.0, price=110.0, t=exit_t, profit=10.0),
    ]
    orders = [{"position_id": 2000, "sl": 98.0}]   # risk = 2 -> realized_r = 5
    bars, t = [], _DAY + 8 * 3600
    while t <= exit_t:
        bars.append(make_bar(t, 100.0, 102.0, 99.0, 101.0))
        t += M15
    return deals, orders, FixtureProvider({"EURUSD": bars})


def _writers(root):
    return PartitionWriter(root, "episodes"), PartitionWriter(root, "features")


def test_pipeline_writes_episodes_and_features(tmp_path):
    deals, orders, provider = _scenario()
    ep_w, ft_w = _writers(tmp_path)
    summary = process_closed_positions(
        deals, orders=orders, candle_provider=provider,
        episode_writer=ep_w, feature_writer=ft_w, generated_by="test",
    )
    assert summary.episodes_seen == 1
    assert summary.episodes_written == 1
    assert summary.features_written == 1
    assert summary.pipeline_version              # non-empty registry hash
    assert summary.duration_ms >= 0.0

    feat_file = next(tmp_path.glob("features/*/*/*/features.jsonl"))
    rec = read_jsonl(feat_file)[0]
    assert rec["realized_r"] == 5.0              # (110-100)/2
    assert rec["risk_distance"] == 2.0


def test_pipeline_manifest_provenance(tmp_path):
    deals, orders, provider = _scenario()
    ep_w, ft_w = _writers(tmp_path)
    process_closed_positions(
        deals, orders=orders, candle_provider=provider,
        episode_writer=ep_w, feature_writer=ft_w,
        source_history_window={"from": "2023-11-01", "to": "2023-11-30"},
        rebuild_id="rb-1", generated_by="rebuild.py",
    )
    manifest = json.loads(next(tmp_path.glob("episodes/*/*/*/manifest.json")).read_text())
    for key in ("engine_registry_hash", "source_history_window", "rebuild_id",
                "generated_by", "python_version"):
        assert key in manifest
    assert manifest["generated_by"] == "rebuild.py"


def test_pipeline_idempotent(tmp_path):
    deals, orders, provider = _scenario()
    ep_w, ft_w = _writers(tmp_path)
    kw = dict(orders=orders, candle_provider=provider,
              episode_writer=ep_w, feature_writer=ft_w, generated_by="test")
    process_closed_positions(deals, **kw)
    second = process_closed_positions(deals, **kw)   # re-run same input
    assert second.episodes_written == 0
    assert second.features_written == 0
    assert second.duplicates_skipped >= 1
    assert len(read_jsonl(next(tmp_path.glob("episodes/*/*/*/episodes.jsonl")))) == 1
