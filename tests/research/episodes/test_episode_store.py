"""P1/P5 floors — serialization round-trip and canonical-identity preservation."""
from __future__ import annotations

import gzip
import json

import pytest

from research.episodes.builder import build_episode
from research.episodes.schema import Annotations, EntrySnapshot, EpisodeStep
from research.episodes.store import (
    from_dict,
    read_episodes,
    sizing_probe,
    to_dict,
    verify_corpus,
    write_episodes,
)


class Bar:
    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


@pytest.fixture
def candles():
    return [Bar(i, 100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(10)]


@pytest.fixture
def episode(candles):
    entry = EntrySnapshot(
        bar_index=0, timestamp="2026-01-01 00:00:00", direction="long",
        entry_price=100.0, sl_price=98.0, tp_price=104.0,
    )
    return build_episode(instrument="T", population="DETECTION_STREAM",
                         entry=entry, candles=candles, max_forward=5,
                         metadata={"diagnostics": {"outcome": "TP_HIT"}})


def test_round_trip_preserves_content_hash(episode):
    assert from_dict(to_dict(episode)).content_hash() == episode.content_hash()


def test_round_trip_preserves_all_fields(episode):
    back = from_dict(to_dict(episode))
    assert back.episode_id == episode.episode_id
    assert back.population == episode.population
    assert back.entry == episode.entry
    assert [s.obs for s in back.steps] == [s.obs for s in episode.steps]
    assert [s.derived for s in back.steps] == [s.derived for s in episode.steps]
    assert back.provenance == episode.provenance
    assert back.metadata == episode.metadata


def test_observation_only_storage_preserves_identity(episode):
    """The Derived cache is regenerable, so dropping it must not change the episode."""
    lean = to_dict(episode, cache_derived=False)
    assert all("derived" not in s for s in lean["steps"])
    assert from_dict(lean).content_hash() == episode.content_hash()


def test_derived_cache_is_rebuildable_from_observations(episode):
    lean = to_dict(episode, cache_derived=False)
    rebuilt = from_dict(lean, rebuild_derived=True)
    assert [s.derived for s in rebuilt.steps] == [s.derived for s in episode.steps]


def test_annotations_survive_round_trip(episode):
    annotated = type(episode)(
        episode_id=episode.episode_id, population=episode.population,
        instrument=episode.instrument, timeframe=episode.timeframe,
        entry=episode.entry,
        steps=[EpisodeStep(obs=s.obs, derived=s.derived,
                           annotations=Annotations(annotator_id="a1", regime="trend"))
               for s in episode.steps],
        provenance=episode.provenance, metadata=episode.metadata,
    )
    back = from_dict(to_dict(annotated))
    assert back.steps[0].annotations.regime == "trend"
    # Annotations are versioned interpretations — they must not move canonical identity.
    assert back.content_hash() == episode.content_hash()


def test_write_read_verify(tmp_path, episode):
    manifest = write_episodes([episode, episode], tmp_path)
    assert manifest["n_episodes"] == 2
    assert manifest["bytes_on_disk"] > 0
    assert manifest["backend"] == "gzip_jsonl_v1"

    back = list(read_episodes(manifest["path"]))
    assert len(back) == 2
    assert back[0].content_hash() == episode.content_hash()
    assert verify_corpus(manifest["path"])["ok"] is True


def test_read_respects_limit(tmp_path, episode):
    manifest = write_episodes([episode] * 5, tmp_path)
    assert len(list(read_episodes(manifest["path"], limit=2))) == 2


def test_verify_corpus_detects_tampering(tmp_path, episode):
    manifest = write_episodes([episode], tmp_path)
    path = manifest["path"]
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        d = json.loads(fh.read().strip())
    d["steps"][2]["obs"]["high"] = 999.0          # mutate an immutable observation
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps(d) + "\n")

    result = verify_corpus(path)
    assert result["ok"] is False
    assert result["n_mismatch"] == 1


def test_sizing_probe_reports_both_modes(episode):
    probe = sizing_probe([episode] * 20)
    assert probe["n_episodes"] == 20
    assert probe["mean_steps"] == 6.0
    assert probe["gz_bytes_observation_only"] < probe["gz_bytes_with_derived"]
    assert probe["gz_bytes_per_episode_observation_only"] > 0


def test_sizing_probe_handles_empty():
    assert sizing_probe([])["n"] == 0
