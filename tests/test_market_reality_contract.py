"""CH-htfcrt-parent-candle-smc-v1 (2026-08-15) — market_reality_contract.py tests.

This file previously had ZERO readers and ZERO tests (verified by grep before this program),
which is exactly how a duplicate top-level `authority` key silently dropped the WHO-layer
marker on every parse for however long it existed. These tests both (a) validate the real
contract file loads cleanly, and (b) adversarially prove the loader would have CAUGHT that
exact defect class had it existed when this module was written — a regression guard against
someone reintroducing the same collision.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.market_reality_contract import (          # noqa: E402
    MarketRealityContractError, load_market_reality_contract,
)

_REAL_PATH = Path(__file__).resolve().parents[1] / "configs" / "market_reality" / "market_reality_v1.yaml"


def test_real_contract_loads_cleanly():
    c = load_market_reality_contract()
    assert c.schema_version == "market_reality/v1"
    assert c.who_authority == "user_approved"
    assert c.enabled is False
    assert c.any_capability_granted() is False


def test_real_contract_has_no_duplicate_authority_key():
    """Direct regression guard for the 2026-08-15 defect: parse the raw file text and confirm
    `authority:` (the WHO-layer scalar) appears exactly once as a top-level key — the previous
    bug was a SECOND top-level `authority:` mapping later in the file silently winning."""
    text = _REAL_PATH.read_text(encoding="utf-8")
    top_level_authority_lines = [
        ln for ln in text.splitlines() if ln.startswith("authority:")
    ]
    assert len(top_level_authority_lines) == 1, (
        f"expected exactly one top-level 'authority:' key, found "
        f"{len(top_level_authority_lines)}: {top_level_authority_lines}"
    )
    assert "authority_capabilities:" in text


def test_dimensions_this_program_unblocked_carry_evidence():
    c = load_market_reality_contract()
    assert c.dimensions["imbalance"]["evidence"] == ["fvg_distance"]
    assert c.dimensions["multi_timeframe"]["evidence"] == ["pdh_distance", "pdl_distance"]
    assert c.dimensions["range_location"]["evidence"] == ["pdh_distance", "pdl_distance"]
    # auction_balance's core blocker (premium/discount) is NOT resolved -- evidence stays empty.
    assert c.dimensions["auction_balance"]["evidence"] == []


def test_every_dimension_and_derivation_stays_enabled_false():
    c = load_market_reality_contract()
    assert all(spec.get("enabled") is False for spec in c.dimensions.values())
    assert all(spec.get("enabled") is False for spec in c.temporal_derivations.values())


# ── adversarial: prove the loader catches the exact 2026-08-15 defect class ────────────────
def _write_variant(tmp_path: Path, mutate) -> Path:
    doc = yaml.safe_load(_REAL_PATH.read_text(encoding="utf-8"))
    mutate(doc)
    out = tmp_path / "variant.yaml"
    out.write_text(yaml.dump(doc, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return out


def test_loader_rejects_a_non_string_who_authority(tmp_path):
    """Simulates what a duplicate `authority:` mapping key collision would produce once
    yaml.safe_load resolves to the LAST occurrence: a dict where a string was expected."""
    def mutate(doc):
        doc["authority"] = {"may_emit_trade_decision": False}  # the collision shape
    path = _write_variant(tmp_path, mutate)
    with pytest.raises(MarketRealityContractError, match="authority"):
        load_market_reality_contract(path)


def test_loader_rejects_enabled_true():
    import tempfile
    doc = yaml.safe_load(_REAL_PATH.read_text(encoding="utf-8"))
    doc["enabled"] = True
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "variant.yaml"
        p.write_text(yaml.dump(doc, default_flow_style=False, sort_keys=False), encoding="utf-8")
        with pytest.raises(MarketRealityContractError, match="enabled"):
            load_market_reality_contract(p)


def test_loader_rejects_a_granted_capability(tmp_path):
    def mutate(doc):
        doc["authority_capabilities"]["may_emit_trade_decision"] = True
    path = _write_variant(tmp_path, mutate)
    with pytest.raises(MarketRealityContractError, match="capability"):
        load_market_reality_contract(path)


def test_loader_rejects_a_dimension_with_enabled_true(tmp_path):
    def mutate(doc):
        doc["dimensions"]["direction"]["enabled"] = True
    path = _write_variant(tmp_path, mutate)
    with pytest.raises(MarketRealityContractError, match="direction"):
        load_market_reality_contract(path)


def test_loader_rejects_missing_dimension_fields(tmp_path):
    def mutate(doc):
        del doc["dimensions"]["direction"]["confidence_policy"]
    path = _write_variant(tmp_path, mutate)
    with pytest.raises(MarketRealityContractError, match="direction"):
        load_market_reality_contract(path)


def test_loader_raises_on_missing_file(tmp_path):
    with pytest.raises(MarketRealityContractError, match="not found"):
        load_market_reality_contract(tmp_path / "does_not_exist.yaml")
