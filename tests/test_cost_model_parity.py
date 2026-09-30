"""SHA-parity floor for the `costs.cost_model` selector — CH-cost-model-broker-truth.

Load-bearing. `ResearchConfig.sha256()` is stamped into every EdgeReport, so a
config's hash IS the identity of the object a result measured. Adding a key to the
canonical dict unconditionally would silently re-identify every historical result.

The `entry_ttl` precedent (`config.py`, comment "sha-parity (load-bearing)") solves
this: a key enters `meaningful` ONLY when the JSON declares it. This test pins that
behaviour for `cost_model` so a future refactor cannot quietly drop the guard.

The pinned hashes below were captured from the pre-change code and are therefore a
genuine before/after comparison, not a self-fulfilling snapshot.

RE-IDENTIFICATION 2026-09-29 (EPIC-84, user decision "re-pin new hashes"): EPIC-84 makes
`costs.cost_model` and `job_kind` required keys, and L-E's `ResearchConfig` puts
`cost_model` into the canonical dict unconditionally. Once every file declares
`cost_model: flat_bps`, every research config gets a NEW identity. The user chose to
accept that rather than keep `flat_bps` hash-neutral. PRE_CHANGE_SHA is kept below as the
historical identity (what results produced before this date were stamped with);
POST_DECLARATION_SHA is the live identity from here on. No tracked file referenced the
old hashes at the time of the change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402
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

#: config filename -> sha256 prefix after the EPIC-84 declaration commit (2026-09-29).
POST_DECLARATION_SHA = {
    "research_config.json": "bf0d5a7e324549ac",
    "research_config_carry.json": "1c1a943ce10ef79e",
    "research_config_cross_sectional.json": "1c1a943ce10ef79e",
    "research_config_fx_metals.json": "2a32eff219488ae9",
    "research_config_harvest.json": "1c1a943ce10ef79e",
    "research_config_htf_majors.json": "c0a00b03c66099ef",
    "research_config_m5_mtf_crypto.json": "19d437f6bf84207b",
    "research_config_m5_mtf_fx.json": "03ef6cc166bd0ea9",
    "research_config_majors.json": "5bdd533152f96904",
    "research_config_phase_d.json": "c5faed5b309485d5",
    "research_config_regime.json": "5bdd533152f96904",
    "research_config_regime_transition.json": "5bdd533152f96904",
    "research_config_shape_xauusd.json": "1ebbed94b6bedf8c",
    "research_config_spine.json": "70817e6a3d04201c",
    "research_config_spine_bitnet_shadow.json": "c85afe021618c7a3",
    "research_config_spine_dimfix_shadow.json": "c85afe021618c7a3",
    "research_config_spine_fx_metals.json": "72046475d47d727b",
    "research_config_spine_htf_majors.json": "5e24da6973d2f358",
    "research_config_spine_majors.json": "c85afe021618c7a3",
    "research_config_spine_v3.json": "70817e6a3d04201c",
    "research_config_spine_v3session_probe.json": "c85afe021618c7a3",
    "research_config_spine_xauusd.json": "a9adde808c1ffdb8",
    "research_config_weekly_sweep.json": "1ab43b24ab95ec5a",
}


def _load(name: str) -> ResearchConfig:
    return ResearchConfig.from_dict(
        json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))
    )


def _with_declarations(raw: dict) -> dict:
    """The literals that run today, injected because this lane does not edit JSON."""
    out = json.loads(json.dumps(raw))
    out["job_kind"] = "unspecified"
    out.setdefault("costs", {})
    out["costs"]["cost_model"] = out["costs"].get("cost_model", "flat_bps")
    return out


@pytest.mark.parametrize("name,expected", sorted(POST_DECLARATION_SHA.items()))
def test_declared_config_sha_is_pinned(name: str, expected: str):
    """Every declared research config parses and carries its pinned identity."""
    assert _load(name).sha256()[:16] == expected, name


def test_every_historical_identity_was_reidentified():
    """The 2026-09-29 re-pin is deliberate: no config keeps its pre-EPIC-84 identity."""
    assert set(PRE_CHANGE_SHA) == set(POST_DECLARATION_SHA)
    for name, old in PRE_CHANGE_SHA.items():
        assert POST_DECLARATION_SHA[name] != old, name


def test_every_parsable_config_is_pinned():
    """Exactly the pinned configs (plus xauusd_month, which declared every key before
    EPIC-84 and was never pinned) parse; nothing else in the directory does."""
    parsed = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            ResearchConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (ConfigKeyMissingError, ValueError, TypeError, KeyError):
            continue
        parsed.append(path.name)
    assert parsed == sorted([*POST_DECLARATION_SHA, "research_config_xauusd_month.json"]), parsed


@pytest.mark.parametrize("key_path", [("costs", "cost_model"), ("job_kind",)])
def test_missing_declaration_fails_closed(key_path):
    """A config that omits cost_model or job_kind is refused, never defaulted."""
    raw = json.loads((CONFIG_DIR / "research_config.json").read_text(encoding="utf-8"))
    parent = raw
    for k in key_path[:-1]:
        parent = parent[k]
    del parent[key_path[-1]]
    with pytest.raises(ConfigKeyMissingError) as ei:
        ResearchConfig.from_dict(raw)
    assert key_path[-1] in ei.value.missing


def test_declaring_cost_model_changes_the_hash():
    """A config that opts in IS measuring a different object and must re-identify."""
    raw = json.loads((CONFIG_DIR / "research_config.json").read_text(encoding="utf-8"))
    base = _with_declarations(raw)
    declared = json.loads(json.dumps(base))
    declared["costs"]["cost_model"] = "component_measured"
    declared["costs"]["cost_model_manifest_path"] = (
        "results/research/xauusd_mt5_cost_calibration/manifest_LATEST.json"
    )
    assert ResearchConfig.from_dict(declared).sha256() != ResearchConfig.from_dict(base).sha256()
    assert ResearchConfig.from_dict(declared).cost_model == "component_measured"


def test_unknown_cost_model_is_rejected_not_silently_defaulted():
    base = _with_declarations(
        json.loads((CONFIG_DIR / "research_config.json").read_text(encoding="utf-8"))
    )
    base["costs"]["cost_model"] = "flat_12bps_everywhere"
    with pytest.raises(ValueError, match="cost_model"):
        ResearchConfig.from_dict(base)
