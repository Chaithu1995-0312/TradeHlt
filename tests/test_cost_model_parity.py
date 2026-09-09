"""SHA-parity floor for the `costs.cost_model` selector — CH-cost-model-broker-truth.

Load-bearing. `ResearchConfig.sha256()` is stamped into every EdgeReport, so a
config's hash IS the identity of the object a result measured. Adding a key to the
canonical dict unconditionally would silently re-identify every historical result.

The `entry_ttl` precedent (`config.py`, comment "sha-parity (load-bearing)") solves
this: a key enters `meaningful` ONLY when the JSON declares it. This test pins that
behaviour for `cost_model` so a future refactor cannot quietly drop the guard.

The pinned hashes below were captured from the pre-change code and are therefore a
genuine before/after comparison, not a self-fulfilling snapshot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from research.config import ResearchConfig  # noqa: E402

CONFIG_DIR = _ROOT / "configs" / "research"

#: config filename -> sha256, captured BEFORE `cost_model` existed.
#: Files absent from this map are not ResearchConfig documents (the directory also
#: holds phase-B grid specs and protocol registrations, which have never parsed).
PRE_CHANGE_SHA = {
    "research_config.json": "a7492591fabff6aa",
    "research_config_carry.json": "00687f8b87ab2325",
    "research_config_cross_sectional.json": "00687f8b87ab2325",
    "research_config_fx_metals.json": "09b422a71e7d07d8",
    "research_config_harvest.json": "00687f8b87ab2325",
    "research_config_htf_majors.json": "50cda22cc0c3162e",
    "research_config_m5_mtf_crypto.json": "e517905134a82d90",
    "research_config_m5_mtf_fx.json": "f79d1f6634644a21",
    "research_config_majors.json": "04f4ba1a948fd628",
    "research_config_phase_d.json": "2e8b46393c7844cf",
    "research_config_regime.json": "04f4ba1a948fd628",
    "research_config_regime_transition.json": "04f4ba1a948fd628",
    "research_config_shape_xauusd.json": "7cd2396d3da09fde",
    "research_config_spine.json": "5bb6754ba956ce08",
    "research_config_spine_bitnet_shadow.json": "c6a72dbeaccd5bac",
    "research_config_spine_dimfix_shadow.json": "c6a72dbeaccd5bac",
    "research_config_spine_fx_metals.json": "ccf284e958627e0a",
    "research_config_spine_htf_majors.json": "5e76150e49602e03",
    "research_config_spine_majors.json": "c6a72dbeaccd5bac",
    "research_config_spine_v3.json": "5bb6754ba956ce08",
    "research_config_spine_v3session_probe.json": "c6a72dbeaccd5bac",
    "research_config_spine_xauusd.json": "6a71557e9f4bc994",
    "research_config_weekly_sweep.json": "615d63ffaf8af12d",
}


def _load(name: str) -> ResearchConfig:
    return ResearchConfig.from_dict(
        json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))
    )


@pytest.mark.parametrize("name,expected", sorted(PRE_CHANGE_SHA.items()))
def test_existing_config_sha_is_byte_identical(name: str, expected: str):
    """No pre-existing config may change identity because a new key was added."""
    assert _load(name).sha256().startswith(expected), (
        f"{name}: config_sha256 drifted. Every EdgeReport stamped with the old hash "
        "would silently refer to a different measured object."
    )


def test_every_parsable_config_is_pinned():
    """A new ResearchConfig must be added to the map, not silently unguarded."""
    unpinned = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            ResearchConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (KeyError, ValueError, TypeError):
            continue  # not a ResearchConfig document
        if path.name not in PRE_CHANGE_SHA:
            unpinned.append(path.name)
    assert not unpinned, f"unpinned ResearchConfig files: {unpinned}"


def test_cost_model_defaults_to_flat_bps():
    assert _load("research_config.json").cost_model == "flat_bps"


def test_declaring_cost_model_changes_the_hash():
    """A config that opts in IS measuring a different object and must re-identify."""
    base = json.loads((CONFIG_DIR / "research_config.json").read_text(encoding="utf-8"))
    declared = json.loads(json.dumps(base))
    declared["costs"]["cost_model"] = "component_measured"
    assert ResearchConfig.from_dict(declared).sha256() != ResearchConfig.from_dict(base).sha256()
    assert ResearchConfig.from_dict(declared).cost_model == "component_measured"


def test_unknown_cost_model_is_rejected_not_silently_defaulted():
    base = json.loads((CONFIG_DIR / "research_config.json").read_text(encoding="utf-8"))
    base["costs"]["cost_model"] = "flat_12bps_everywhere"
    with pytest.raises(ValueError, match="cost_model"):
        ResearchConfig.from_dict(base)
