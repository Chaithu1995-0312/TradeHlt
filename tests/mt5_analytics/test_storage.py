"""
Phase 1 storage tests — idempotency, manifest determinism, provenance.

Proves the artifact substrate is replayable and crash-safe: re-writing the same
episodes never duplicates, and the manifest sha256 is byte-stable across re-runs.
"""
from __future__ import annotations

from mt5_analytics.engines.position_reconstructor import reconstruct_position_episodes
from mt5_analytics.storage.manifest_builder import build_manifest, records_sha256
from mt5_analytics.storage.partition_writer import PartitionWriter
from utils.jsonl_writer import read_jsonl  # type: ignore


def _episodes(deal):
    deals = [
        deal.make(900, 1, entry=deal.IN, deal_type=deal.BUY, volume=1.0, price=100.0, t=deal.base),
        deal.make(900, 2, entry=deal.OUT, deal_type=deal.SELL, volume=1.0, price=110.0,
                  t=deal.base + 60, profit=10.0),
    ]
    return [e.to_dict() for e in reconstruct_position_episodes(deals)]


def test_partition_layout_and_write(tmp_path, deal):
    recs = _episodes(deal)
    pw = PartitionWriter(tmp_path, "episodes")
    summary = pw.write(recs, schema_version="1.0", generated_by="test")
    assert summary["written"] == 1
    assert summary["skipped_duplicates"] == 0
    # exit_time 2023-11-14T... -> partition dir <root>/episodes/2023/11/14/episodes.jsonl
    part = next(tmp_path.glob("episodes/*/*/*/episodes.jsonl"))
    assert read_jsonl(part)[0]["episode_id"] == recs[0]["episode_id"]
    assert part.parent.joinpath("manifest.json").exists()


def test_idempotent_rewrite_skips_duplicates(tmp_path, deal):
    recs = _episodes(deal)
    pw = PartitionWriter(tmp_path, "episodes")
    pw.write(recs, generated_by="test")
    summary2 = pw.write(recs, generated_by="test")  # second run: same input
    assert summary2["written"] == 0
    assert summary2["skipped_duplicates"] == 1
    part = next(tmp_path.glob("episodes/*/*/*/episodes.jsonl"))
    assert len(read_jsonl(part)) == 1  # NOT duplicated


def test_manifest_determinism_and_provenance(deal):
    recs = _episodes(deal)
    m1 = build_manifest(recs, schema_version="1.0",
                        source_history_window={"from": "2023-11-01", "to": "2023-11-30"},
                        rebuild_id="rb-1", generated_by="rebuild.py")
    m2 = build_manifest(list(reversed(recs)), schema_version="1.0",
                        source_history_window={"from": "2023-11-01", "to": "2023-11-30"},
                        rebuild_id="rb-1", generated_by="rebuild.py")
    # sha256 is order-independent (sorted by episode_id) and stable.
    assert m1["sha256"] == m2["sha256"] == records_sha256(recs)
    # provenance fields present.
    for key in ("engine_versions", "engine_registry_hash", "source_history_window",
                "rebuild_id", "generated_by", "python_version", "timestamp_utc"):
        assert key in m1
    assert m1["source_history_window"] == {"from": "2023-11-01", "to": "2023-11-30"}
    assert m1["records"] == 1
