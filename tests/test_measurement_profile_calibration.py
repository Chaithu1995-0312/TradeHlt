"""Measurement-profile calibration floor — CH-cost-model-broker-truth.

Two asymmetric guarantees:

  * `metals_mt5` carries a MEASURED broker calibration whose provenance resolves to
    a real manifest with a matching sha256 — a stored number nobody can trace is a
    comment, not evidence.
  * `crypto_majors` and `fx_majors` stay PENDING_CALIBRATION. No measured broker
    data exists for them, and inventing some is the exact failure the
    EPISTEMIC_INTEGRITY charter forbids ("write UNKNOWN, never invent").

Seeding values grants NO economic admissibility — only E-MT-00 PASS + E-MT-01
COMPLETE can (MEASUREMENT_CONTRACT.md section 2, E4). The profile stays DRAFT.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = _ROOT / "configs" / "research" / "measurement_contracts"


def _profile(name: str) -> dict:
    return json.loads((PROFILE_DIR / f"{name}.v1.json").read_text(encoding="utf-8"))


def _costs(name: str) -> dict:
    return _profile(name)["surface_defaults"]["costs"]


# ── metals: measured, traceable ──────────────────────────────────────────────

def test_metals_calibration_is_measured():
    cal = _costs("metals_mt5")["calibration"]
    assert cal["status"] == "MEASURED"
    assert cal["ontology_id"] == "SEM-015"
    assert cal["instrument"] == "XAUUSD"


def test_metals_provenance_manifest_exists_and_hash_matches():
    """A stored provenance hash that nobody recomputes is decoration."""
    cal = _costs("metals_mt5")["calibration"]
    manifest = _ROOT / cal["source_manifest"]
    assert manifest.is_file(), f"provenance manifest missing: {cal['source_manifest']}"
    actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert actual == cal["source_manifest_sha256"], (
        "calibration provenance hash does not match the manifest on disk"
    )


def test_metals_values_match_the_source_manifest():
    """The seeded numbers must be the measured ones, not drifted copies."""
    cal = _costs("metals_mt5")["calibration"]
    man = json.loads((_ROOT / cal["source_manifest"]).read_text(encoding="utf-8"))
    comp = man["c_per_side"]["components"]
    vals = cal["values_usd_per_oz"]
    assert vals["half_spread"] == pytest.approx(comp["half_spread_usd"])
    assert vals["commission"] == pytest.approx(abs(comp["commission_per_oz_usd"]))
    assert vals["stop_slippage"] == pytest.approx(comp["stop_slippage_usd"])


def test_metals_declares_entry_slippage_is_a_proxy_not_a_measurement():
    """MARKET slippage was INSUFFICIENT_DATA; the assumption must travel with it."""
    cal = _costs("metals_mt5")["calibration"]
    assert cal["entry_slippage_basis"] == "PROXY_FROM_STOP"
    assert cal["values_usd_per_oz"]["entry_slippage"] > 0.0, "never silently zero"


def test_metals_carries_its_weaknesses():
    caveats = " ".join(_costs("metals_mt5")["calibration"]["caveats"]).lower()
    assert "n=7" in caveats, "the small stop-fill sample must not be quietly dropped"
    assert "demo" in caveats, "demo-account provenance must be stated"
    assert "admissibility" in caveats or "e-mt-00" in caveats


def test_metals_leg_model_rejects_the_two_times_c_per_side_convention():
    leg = _costs("metals_mt5")["calibration"]["leg_model"].lower()
    assert "2 * c_per_side" in leg or "2*c_per_side" in leg
    assert "market order" in leg


# ── crypto / fx: honestly unmeasured ─────────────────────────────────────────

@pytest.mark.parametrize("name", ["crypto_majors", "fx_majors"])
def test_unmeasured_asset_classes_stay_pending(name: str):
    cal = _costs(name)["calibration"]
    assert cal["status"] == "PENDING_CALIBRATION", (
        f"{name} has no measured broker data; inventing values is forbidden"
    )
    assert cal["k"] is None and cal["values"] is None


# ── supersession is recorded, not silently overwritten ───────────────────────

def test_superseded_proxy_model_is_preserved():
    """CLAUDE.md 6.2 rule 4: mark superseded, never delete."""
    costs = _costs("metals_mt5")
    assert costs["cost_model_id"] == "component_measured.v1"
    formulas = " ".join(c["bps_or_formula"] for c in costs["components"])
    assert "DERIVED" in formulas, "the superseded volatility-proxy component must survive"
    assert "SUPERSEDED" in costs["legacy_note"]
    assert "UNK-COST-02" in costs["legacy_note"], "adjudication must stay traceable"


def test_seeding_did_not_promote_the_profile():
    """Calibration is not admissibility."""
    prof = _profile("metals_mt5")
    assert prof["lifecycle"] == "DRAFT"
    assert prof["profile_hash"] is None
    assert prof["unresolved_terms"], "DRAFT must still enumerate what blocks its freeze"
    terms = {t["term"] for t in prof["unresolved_terms"]}
    assert "costs.calibration" not in terms, "the seeded term is resolved"
    assert "pipeline_identity.engine_gate_mode" in terms, "other blockers must remain"
