"""CRT resolver link/variant binding -- behavioral floor.

A link is a config-level switch, DEFAULT OFF, that makes one piece of
built-but-unconsumed resolver capability reachable. "Declared in a registry" is
not the same as "disableable"; these tests exercise the actual BINDING -- that a
tagged `when:` clause is filtered out when its link is off and present when it
is on, and that the per-variant requirement set moves with it.

The load-bearing test here is
``test_typo_in_a_disabled_links_clause_still_raises``: predicate validation must
run on the UNFILTERED config. If it did not, a typo inside a disabled link's
clause would stay hidden until someone enabled it -- reintroducing the exact
silent-gap class (skipped check indistinguishable from absent check) that this
whole program exists to close.

Authority: research/governance only. Grants nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import (  # noqa: E402
    ConfigLoadError,
    CRTStateResolver,
    PredicateValidationError,
)

STATES_YAML = ROOT / "configs" / "formulas" / "market_crt_states.yaml"
LINKS_YAML = ROOT / "configs" / "formulas" / "crt_resolver_links.yaml"


def _write(tmp_path: Path, name: str, obj) -> Path:
    out = tmp_path / name
    out.write_text(yaml.dump(obj, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return out


def _states_cfg():
    return yaml.safe_load(STATES_YAML.read_text(encoding="utf-8"))


def _links_cfg():
    return yaml.safe_load(LINKS_YAML.read_text(encoding="utf-8"))


def _state(cfg, name):
    for s in cfg["states"]:
        if s["name"] == name:
            return s
    raise KeyError(name)


def _resolver(tmp_path, states, links_registry, **kw):
    """`links_registry` is the REGISTRY file contents; `links=` in **kw is the
    enabled-link set passed to the resolver. Distinct things, distinct names."""
    return CRTStateResolver(
        config_path=_write(tmp_path, "states.yaml", states),
        links_config_path=_write(tmp_path, "links.yaml", links_registry),
        **kw,
    )


# -- Shipped registry ---------------------------------------------------------
def test_default_is_every_link_off():
    r = CRTStateResolver()
    assert r.enabled_links == frozenset()
    assert r.variant_id is None


def test_base_variant_enables_nothing():
    r = CRTStateResolver(variant="base")
    assert r.variant_id == "base"
    assert r.enabled_links == frozenset()


def test_base_variant_is_behaviourally_the_default():
    """`base` must be the untouched shipped config, or it is not a baseline."""
    a, b = CRTStateResolver(), CRTStateResolver(variant="base")
    assert a.required_when_features == b.required_when_features
    for sd_a, sd_b in zip(a._config["states"], b._config["states"]):
        assert sd_a.get("when") == sd_b.get("when")


def test_shipped_when_blocks_survive_filtering_unchanged():
    """With no links enabled, filtering must be a provable no-op against the
    raw YAML -- otherwise the mechanism itself changed behaviour."""
    raw = {s["name"]: (s.get("when") or {}) for s in _states_cfg()["states"]}
    got = {s["name"]: (s.get("when") or {}) for s in CRTStateResolver()._config["states"]}
    assert raw == got


def test_shipped_registry_declares_no_canonical_variant():
    """Zero canonical variants during the wiring phase. Flipping one is a
    governance event with a written justification, not a config edit."""
    canon = [
        vid for vid, spec in (_links_cfg().get("variants") or {}).items()
        if (spec or {}).get("canonical")
    ]
    assert canon == [], f"variants marked canonical during the wiring phase: {canon}"


def test_shipped_registry_respects_the_variant_cap():
    reg = _links_cfg()
    cap = int(reg["max_live_variants"])
    n = len(reg.get("variants") or {})
    assert n <= cap, f"{n} live variants exceeds the declared cap of {cap}"


def test_every_link_carries_a_substantive_rationale():
    for lid, spec in (_links_cfg().get("links") or {}).items():
        assert len((spec or {}).get("rationale", "").strip()) > 40, (
            f"{lid}: rationale must say what the comparison tests"
        )


def test_link_status_matches_actual_clause_binding():
    """Two-sided: a `bound` link must have >=1 tagged clause; a `declared` link
    must have none. Flipping status without doing the binding goes red."""
    reg = _links_cfg()
    states = _states_cfg()
    tagged: dict[str, int] = {}
    for sd in states["states"]:
        for clause in (sd.get("when") or {}).values():
            if isinstance(clause, dict) and clause.get("link"):
                tagged[clause["link"]] = tagged.get(clause["link"], 0) + 1
    for lid, spec in (reg.get("links") or {}).items():
        status = (spec or {}).get("status")
        n = tagged.get(lid, 0)
        if status == "bound":
            assert n >= 1, f"{lid} is status:bound but tags no clause"
        elif status == "declared":
            assert n == 0, f"{lid} is status:declared but already tags {n} clause(s)"
        else:
            pytest.fail(f"{lid}: status must be 'declared' or 'bound', got {status!r}")


# -- Binding behaviour --------------------------------------------------------
def _tagged_states(link_id="LINK-001"):
    """Shipped config with one EXTRA link-tagged clause on RANGE."""
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["volume_spike"] = {
        "states": ["NoSpike"], "link": link_id,
    }
    return cfg


def test_tagged_clause_is_absent_when_its_link_is_off(tmp_path):
    r = _resolver(tmp_path, _tagged_states(), _links_cfg())
    assert "volume_spike" not in _state(r._config, "RANGE")["when"]
    assert "volume_spike" not in r.required_when_features


def test_tagged_clause_is_present_when_its_link_is_on(tmp_path):
    r = _resolver(tmp_path, _tagged_states(), _links_cfg(), links=["LINK-001"])
    assert _state(r._config, "RANGE")["when"]["volume_spike"] == ["NoSpike"]
    assert "volume_spike" in r.required_when_features


def test_requirement_set_moves_with_the_link_set(tmp_path):
    """The set is computed AFTER filtering, so it is variant-dependent. A set
    frozen before link resolution would be wrong for some variants."""
    off = _resolver(tmp_path, _tagged_states(), _links_cfg())
    on = _resolver(tmp_path, _tagged_states(), _links_cfg(), links=["LINK-001"])
    assert on.required_when_features - off.required_when_features == {"volume_spike"}
    assert len(on.required_when_features) == len(off.required_when_features) + 1


def test_untagged_clauses_are_baseline_and_always_present(tmp_path):
    for links in ([], ["LINK-001"]):
        r = _resolver(tmp_path, _tagged_states(), _links_cfg(), links=links)
        assert "liquidity_sweep" in _state(r._config, "RANGE")["when"]


def test_variant_resolves_to_its_declared_link_set(tmp_path):
    reg = _links_cfg()
    reg["variants"]["choch_only"] = {
        "canonical": False, "links": ["LINK-001"],
        "rationale": "synthetic single-link variant for the binding floor",
    }
    r = _resolver(tmp_path, _tagged_states(), reg, variant="choch_only")
    assert r.enabled_links == frozenset({"LINK-001"})
    assert "volume_spike" in r.required_when_features


# -- Validation runs UNFILTERED (the load-bearing guard) ----------------------
def test_typo_in_a_disabled_links_clause_still_raises(tmp_path):
    """THE point of validating before filtering. A bad state name inside a
    clause whose link is OFF must still fail at construction."""
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["volume_spike"] = {
        "states": ["NoSuchState"], "link": "LINK-001",
    }
    with pytest.raises(PredicateValidationError, match="NoSuchState"):
        _resolver(tmp_path, cfg, _links_cfg())          # link OFF -- must still raise


def test_unknown_feature_in_a_disabled_links_clause_still_raises(tmp_path):
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["not_a_feature"] = {
        "states": ["NoSpike"], "link": "LINK-001",
    }
    with pytest.raises(PredicateValidationError, match="not_a_feature"):
        _resolver(tmp_path, cfg, _links_cfg())


def test_clause_naming_an_unknown_link_raises(tmp_path):
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["volume_spike"] = {
        "states": ["NoSpike"], "link": "LINK-999",
    }
    with pytest.raises(PredicateValidationError, match="LINK-999"):
        _resolver(tmp_path, cfg, _links_cfg())


@pytest.mark.parametrize("bad", [
    {"states": [], "link": "LINK-001"},      # empty states
    {"states": ["NoSpike"]},                  # missing link id
    {"link": "LINK-001"},                     # missing states
    "NoSpike",                                # bare string, not a list
])
def test_malformed_clause_raises_rather_than_being_ignored(tmp_path, bad):
    """A malformed clause must never be silently treated as 'no predicate'."""
    cfg = _states_cfg()
    _state(cfg, "RANGE")["when"]["volume_spike"] = bad
    with pytest.raises(PredicateValidationError):
        _resolver(tmp_path, cfg, _links_cfg())


# -- Resolution errors --------------------------------------------------------
def test_unknown_variant_raises(tmp_path):
    with pytest.raises(ConfigLoadError, match="unknown variant"):
        _resolver(tmp_path, _states_cfg(), _links_cfg(), variant="nope")


def test_unknown_link_id_raises(tmp_path):
    with pytest.raises(ConfigLoadError, match="unknown link id"):
        _resolver(tmp_path, _states_cfg(), _links_cfg(), links=["LINK-404"])


def test_variant_and_links_together_raise(tmp_path):
    """Their precedence is undeclared, so accepting both would invent one."""
    with pytest.raises(ConfigLoadError, match="not both"):
        _resolver(tmp_path, _states_cfg(), _links_cfg(),
                  variant="base", links=["LINK-001"])


def test_variant_naming_an_unknown_link_raises(tmp_path):
    reg = _links_cfg()
    reg["variants"]["broken"] = {
        "canonical": False, "links": ["LINK-404"], "rationale": "x" * 50,
    }
    with pytest.raises(ConfigLoadError, match="unknown link id"):
        _resolver(tmp_path, _states_cfg(), reg, variant="broken")


def test_absent_registry_is_legitimate_but_malformed_one_is_not(tmp_path):
    """The resolver predates links; a missing registry means 'no links'."""
    states = _write(tmp_path, "states.yaml", _states_cfg())
    r = CRTStateResolver(config_path=states, links_config_path=tmp_path / "nope.yaml")
    assert r.enabled_links == frozenset()

    bad = _write(tmp_path, "bad.yaml", {"links": ["not", "a", "mapping"]})
    with pytest.raises(ConfigLoadError, match="must be a mapping"):
        CRTStateResolver(config_path=states, links_config_path=bad)
