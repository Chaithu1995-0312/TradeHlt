"""
Phase 4 — THE KEYSTONE: rebuild ≡ daemon (anti-divergence doctrine).

The same deal+order stream driven through the rebuild path (one batch call) and the daemon
path (incremental per-position calls) MUST produce byte-identical `episodes.jsonl` and
`features.jsonl`. If this test stays green forever, the two entry points cannot grow two
truths — replayability is preserved. Both paths go through `shared_pipeline`; only the
chunking differs.
"""
from __future__ import annotations

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

_DAY = (1_700_000_000 // 86400) * 86400


def _pos(pid, entry_t, exit_t, entry_px, exit_px, sl):
    deals = [
        make_deal(pid, pid * 10 + 1, entry=DEAL_ENTRY_IN, deal_type=DEAL_TYPE_BUY,
                  volume=1.0, price=entry_px, t=entry_t),
        make_deal(pid, pid * 10 + 2, entry=DEAL_ENTRY_OUT, deal_type=DEAL_TYPE_SELL,
                  volume=1.0, price=exit_px, t=exit_t, profit=exit_px - entry_px),
    ]
    return deals, {"position_id": pid, "sl": sl}


def _provider():
    bars, t = [], _DAY + 7 * 3600
    while t <= _DAY + 15 * 3600:
        bars.append(make_bar(t, 100.0, 102.0, 99.0, 101.0))
        t += M15
    return FixtureProvider({"EURUSD": bars})


def _read_bytes(root, kind):
    files = sorted(root.glob(f"{kind}/*/*/*/{kind}.jsonl"))
    return b"".join(f.read_bytes() for f in files)


def test_rebuild_equals_daemon_byte_identical(tmp_path):
    # two positions, A closes before B (same UTC day -> same partition).
    a_deals, a_ord = _pos(3000, _DAY + 9 * 3600, _DAY + 10 * 3600, 100.0, 110.0, 98.0)
    b_deals, b_ord = _pos(3001, _DAY + 12 * 3600, _DAY + 13 * 3600, 50.0, 55.0, 49.0)

    # ── rebuild path: one batch call with the full stream ──
    rebuild_root = tmp_path / "rebuild"
    process_closed_positions(
        a_deals + b_deals, orders=[a_ord, b_ord], candle_provider=_provider(),
        episode_writer=PartitionWriter(rebuild_root, "episodes"),
        feature_writer=PartitionWriter(rebuild_root, "features"),
        generated_by="rebuild.py",
    )

    # ── daemon path: two incremental ticks over the SAME total input ──
    daemon_root = tmp_path / "daemon"
    ep_w = PartitionWriter(daemon_root, "episodes")
    ft_w = PartitionWriter(daemon_root, "features")
    for deals, order in ((a_deals, a_ord), (b_deals, b_ord)):
        process_closed_positions(
            deals, orders=[order], candle_provider=_provider(),
            episode_writer=ep_w, feature_writer=ft_w, generated_by="daemon.py",
        )

    assert _read_bytes(rebuild_root, "episodes") == _read_bytes(daemon_root, "episodes")
    assert _read_bytes(rebuild_root, "features") == _read_bytes(daemon_root, "features")
    assert _read_bytes(rebuild_root, "episodes")        # non-empty (sanity)
