"""
Phase 2b schema tests — episode identity + timestamp normalization.

`episode_id` must be deterministic and unique-per-lifetime so it can serve as the
dedup/idempotency key for every layer above reconstruction.
"""
from __future__ import annotations

from mt5_analytics.schemas.position_episode_v1_0 import (
    SCHEMA_VERSION,
    make_episode_id,
    to_iso_utc,
)


def test_to_iso_utc_epoch_and_iso_agree():
    epoch = 1_700_000_000
    iso = to_iso_utc(epoch)
    assert iso.endswith("Z") and "T" in iso
    # Feeding the produced ISO back must be idempotent.
    assert to_iso_utc(iso) == iso


def test_to_iso_utc_normalizes_offset():
    assert to_iso_utc("2023-11-14T22:13:20+00:00") == "2023-11-14T22:13:20Z"


def test_make_episode_id_deterministic():
    a = make_episode_id(700, "2023-11-14T22:13:20Z", [1, 2, 3])
    b = make_episode_id(700, "2023-11-14T22:13:20Z", [3, 2, 1])  # ticket order irrelevant
    assert a == b
    assert a.startswith("700:")


def test_make_episode_id_distinguishes_lifetimes():
    # Same position_id, different entry times / deal sets -> different analytical ids.
    first = make_episode_id(700, "2023-11-14T22:13:20Z", [1, 2])
    second = make_episode_id(700, "2023-11-14T22:23:20Z", [3, 4])
    assert first != second


def test_schema_version_constant():
    assert SCHEMA_VERSION == "1.0"
