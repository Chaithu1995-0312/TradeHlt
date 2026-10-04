"""Pin: occupancy_series_identity is named as L3 series lineage, not a PK rewrite.

CH-occupancy-series-identity (2026-09-05). Reads the frozen identity contract.
Does not persist, serve, or recompute occupancy. FROZEN v1.0.0 must survive.
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_IDENTITY = _REPO / "docs" / "governance" / "CANONICAL_LAYER_IDENTITY_CONTRACT.md"
_PRESERVE = _REPO / "docs" / "governance" / "STORAGE_PRESERVATION_CONTRACT.md"
_PHYSICAL = _REPO / "docs" / "governance" / "PHYSICAL_STORAGE_ARCHITECTURE.md"


def _identity() -> str:
    return _IDENTITY.read_text(encoding="utf-8")


def test_frozen_v1_marker_survives() -> None:
    text = _identity()
    assert "FROZEN v1.0.0" in text
    assert "LAYER_IDENTITY_STATUS = CLOSED" in text


def test_occupancy_series_identity_is_named() -> None:
    text = _identity()
    assert "occupancy_series_identity" in text
    assert "### 7.4.1 Occupancy series identity" in text
    for token in ("producer_id", "topology_id", "track_id", "corpus_sha256", "run_id"):
        assert token in text.split("### 7.4.1 Occupancy series identity", 1)[1].split("### 7.5 Payload", 1)[0]


def test_bar_occupancy_pk_unchanged() -> None:
    """§7.2 table still owns the bar PK; constructor_id must not appear there."""
    text = _identity()
    start = text.index("### 7.2 Occupancy primary key")
    end = text.index("### 7.3 Transition-event primary key")
    section = text[start:end]
    assert "`producer_id`" in section
    assert "`topology_id`" in section
    assert "`track_id`" in section
    assert "L0 PK" in section
    assert "constructor_id" not in section
    assert "config_hash" not in section
    assert "run_id" not in section


def test_constructor_id_is_lineage_not_pk() -> None:
    text = _identity()
    assert "`constructor_id` is not a bar occupancy PK component" in text
    assert "never a bar-occupancy PK component" in text


def test_subordinate_contracts_name_the_series() -> None:
    preserve = _PRESERVE.read_text(encoding="utf-8")
    physical = _PHYSICAL.read_text(encoding="utf-8")
    assert "occupancy_series_identity" in preserve or "Occupancy series identity" in preserve
    assert "occupancy_series_identity" in physical
    assert "FROZEN v1.0.0" in preserve
    assert "FROZEN v1.0.0" in physical
    assert "CH-occupancy-series-identity" in preserve
    assert "CH-occupancy-series-identity" in physical
