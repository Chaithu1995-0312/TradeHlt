"""
Test floor for configs/formulas/market_crt_states.yaml:threshold_refs and its validator,
features.registry.validate_crt_threshold_refs -- Phase D of the "CRT single source of truth"
plan (2026-08-31 session).

Phase D adds `threshold_refs:` alongside the existing `thresholds:` block -- NAMES, never
values, following structure_profiles.yaml's doctrine. This floor proves three things:
  1. The real file validates clean (non-trivial: mutation-tested, not just a happy-path check).
  2. `thresholds:` itself is BYTE-IDENTICAL to before this phase -- the addition changed nothing
     the resolver actually reads, only added a new, unconsumed, purely declarative section.
  3. The classification counts match what was actually measured against
     src/features/crt_state_resolver.py source (12 crtconfig_duplicate(_dead), N resolver_only,
     N dead_unconsumed, N name_alias_documented) -- pinned so a future edit that silently
     reclassifies a key is visible as a number moving.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from features.registry import (  # noqa: E402
    _load_market_crt_states,
    validate_crt_threshold_refs,
)

# Hand-transcribed at authorship time (2026-08-31) from the SAME market_crt_states.yaml this
# floor validates, BEFORE the threshold_refs section existed -- i.e. the `thresholds:` block's
# literal values, as read once and never re-derived from the live file.
#
# UPDATED same day (Phase E1): retest_depth_max 0.08 -> 0.15, a real, user-authorized value
# change, not drift. Measured inert for the resolver BEFORE this edit
# (scripts/research/e1_retest_depth_max_probe.py: byte-identical agreement/RETEST recall at
# 0.08/0.15/0.25) -- aligns YAML to the live production value. This test's own docstring said to
# update the snapshot in the same turn as any real Phase E value change, with the finding cited;
# doing so here.
_THRESHOLDS_SNAPSHOT = {
    "sweep_geometry": "htf_range",
    "range_atr_period": 14,
    "body_ratio_min": 0.65,
    "atr_multiplier_min": 1.0,
    "atr_min_displacement": 1.2,
    "expansion_atr_min_distance": 0.3,
    "expansion_atr_is_relative": True,
    "continuous_disp_to_expansion": False,
    "retest_depth_max": 0.15,
    "retest_atr_depth_fraction": 0.5,
    "max_sweep_age_candles": 20,
    "max_displacement_age_candles": 3,
    "max_expansion_age_candles": 495,
    "max_expansion_age_hours": 124,
    "score_threshold": 0.45,
    "soft_conf_max_candles": 3,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "lifecycle": {
        "htf_reset_enabled": True,
        "htf_candles_per_range": 4,
        "htf_protect_states": ["EXPANSION", "RETEST"],
        "htf_protect_execution": True,
        "gap_reset_enabled": True,
        "gap_reset_minutes": 120,
        "shadow_on_htf_displacement_reset": True,
        "pending_displacement_ttl_candles": 4,
    },
}


@pytest.fixture(scope="module")
def doc():
    return _load_market_crt_states(_REPO)


def test_thresholds_block_is_byte_identical_to_pre_phase_d(doc):
    """The whole point of Phase D: adding threshold_refs must not change one digit of what the
    resolver actually reads."""
    assert doc["thresholds"] == _THRESHOLDS_SNAPSHOT


def test_validator_accepts_the_real_file_clean(doc):
    assert validate_crt_threshold_refs(doc) == []


def test_every_thresholds_key_has_exactly_one_refs_entry(doc):
    scalar_keys = {k for k in doc["thresholds"] if k != "lifecycle"}
    lifecycle_keys = {f"lifecycle.{k}" for k in doc["thresholds"]["lifecycle"]}
    expected = scalar_keys | lifecycle_keys
    actual = set(doc["threshold_refs"]["refs"])
    assert actual == expected
    assert len(expected) == 26


def test_classification_counts_match_the_measured_source_audit(doc):
    """Pinned against crt_state_resolver.py source, verified by direct grep this session --
    not re-derived here, just pinned so a future silent reclassification is visible."""
    from collections import Counter
    refs = doc["threshold_refs"]["refs"]
    counts = Counter(v["kind"] for v in refs.values())
    assert counts["crtconfig_duplicate"] == 11
    assert counts["crtconfig_duplicate_dead"] == 1
    assert counts["name_alias_documented"] == 3
    assert counts["resolver_only"] == 8
    assert counts["dead_unconsumed"] == 3
    assert sum(counts.values()) == 26


def test_consumed_flags_match_the_verified_grep_audit(doc):
    """The `consumed` bool per entry, as independently verified against
    src/features/crt_state_resolver.py this session (grep for thr.get(<key>, ...) /
    self._lifecycle[<key>] occurrences)."""
    refs = doc["threshold_refs"]["refs"]
    unconsumed = {k for k, v in refs.items() if v["consumed"] is False}
    assert unconsumed == {
        "retest_atr_depth_fraction",
        "max_displacement_age_candles",
        "rsi_overbought",
        "rsi_oversold",
    }


# ── Mutation tests: prove the validator actually rejects, not just accepts ──────────────────

def test_rejects_a_missing_entry(doc):
    import copy
    d = copy.deepcopy(doc)
    del d["threshold_refs"]["refs"]["body_ratio_min"]
    problems = validate_crt_threshold_refs(d)
    assert any("missing entries" in p and "body_ratio_min" in p for p in problems)


def test_rejects_a_fabricated_crtconfig_ref(doc):
    import copy
    d = copy.deepcopy(doc)
    d["threshold_refs"]["refs"]["body_ratio_min"]["ref"] = "not_a_real_field"
    problems = validate_crt_threshold_refs(d)
    assert any("not a real CRTConfig field" in p for p in problems)


def test_rejects_a_ref_on_a_resolver_only_entry(doc):
    import copy
    d = copy.deepcopy(doc)
    d["threshold_refs"]["refs"]["sweep_geometry"]["ref"] = "body_ratio_min"
    problems = validate_crt_threshold_refs(d)
    assert any("must not carry a ref" in p for p in problems)


def test_rejects_an_invalid_kind(doc):
    import copy
    d = copy.deepcopy(doc)
    d["threshold_refs"]["refs"]["sweep_geometry"]["kind"] = "made_up_kind"
    problems = validate_crt_threshold_refs(d)
    assert any("not one of" in p for p in problems)


def test_encoding_footgun_is_handled():
    """market_crt_states.yaml contains non-ASCII bytes; plain open()+yaml.safe_load dies on
    Windows cp1252. _load_market_crt_states must force utf-8 -- this test just proves it doesn't
    raise, since the fixture above already exercises the real file."""
    d = _load_market_crt_states(_REPO)
    assert isinstance(d, dict)


def test_no_arg_call_resolves_repo_root_from_file_location_not_cwd():
    """CORRECTED 2026-08-31 (Phase E0 / CR-3): _load_market_crt_states used to default to
    Path(".") -- correct only when the caller's cwd happens to be the repo root. Every OTHER test
    in this floor passes _REPO explicitly, so that no-arg path was the untested (and broken) one.
    Fixed to compute repo root from this module's own __file__, matching the established pattern
    in features/registry/_loader.py's _ONTOLOGY_PATH. Proven here by actually changing cwd away
    from the repo root and confirming the no-arg call still resolves correctly."""
    import os
    prev_cwd = os.getcwd()
    try:
        os.chdir(_REPO.parent)  # anywhere that is NOT the repo root
        d = _load_market_crt_states()  # no repo_root argument
        assert "threshold_refs" in d
        assert validate_crt_threshold_refs() == []  # no-arg call too
    finally:
        os.chdir(prev_cwd)
