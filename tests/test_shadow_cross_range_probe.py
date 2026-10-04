"""
Shadow cross-range restoration floor.

Behavioral tests for the OBSERVATION_ONLY probe at
scripts/analysis/shadow_cross_range_restoration_probe.py, per the "measure first, no
finding yet" decision on the CRT shadow-restoration investigation (plan file
continuation-context-crt-jazzy-avalanche.md).

Test 1 exercises the pure `bucket_shadow_cross_range` classifier in isolation with
concrete inputs and exact expected outputs (E-001: a test that can't fail isn't
enforcement). Test 2 validates the artifact schema + the probe's own runtime
self-consistency/sanity checks, but only runs against a real generated artifact
(skipped otherwise, matching test_soft_conf_ema_probe.py's convention).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "shadow_cross_range_restoration_probe.py"
_ARTIFACT = _REPO / "results" / "analysis" / "shadow_cross_range_restoration.LATEST.json"


def _load_probe():
    spec = importlib.util.spec_from_file_location("shadow_cross_range_restoration_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["shadow_cross_range_restoration_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("shadow_cross_range_restoration_probe.py not present")
    return _load_probe()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pure bucketing function -- exact, concrete cases (both-empty / one-empty /
#    equal / unequal), independent of the engine or any backtest run.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("shadow_source_htf,active_range_htf,expected", [
    (None, None, "UNKNOWN"),
    ("", "", "UNKNOWN"),
    ("XAUUSD-HTF-000015", None, "UNKNOWN"),
    ("XAUUSD-HTF-000015", "", "UNKNOWN"),
    (None, "XAUUSD-HTF-000016", "UNKNOWN"),
    ("", "XAUUSD-HTF-000016", "UNKNOWN"),
    ("XAUUSD-HTF-000015", "XAUUSD-HTF-000015", "SAME_RANGE"),
    ("XAUUSD-HTF-000015", "XAUUSD-HTF-000016", "CROSS_RANGE"),
    ("XAUUSD-HTF-000095", "XAUUSD-HTF-000096", "CROSS_RANGE"),
])
def test_bucket_shadow_cross_range(probe, shadow_source_htf, active_range_htf, expected):
    assert probe.bucket_shadow_cross_range(shadow_source_htf, active_range_htf) == expected


def test_bucket_never_folds_missing_id_into_same_range(probe):
    """A missing id on either side must never be silently classified as SAME_RANGE --
    that would hide the exact ambiguity this probe exists to surface."""
    assert probe.bucket_shadow_cross_range(None, None) != "SAME_RANGE"
    assert probe.bucket_shadow_cross_range("", "") != "SAME_RANGE"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Contingency table + self-consistency helpers -- pure functions, no engine.
# ─────────────────────────────────────────────────────────────────────────────

def _episode(bucket, outcome, **kw):
    base = {
        "candle_index": 0, "timestamp": "", "shadow_source_htf": "A",
        "active_range_htf": "A" if bucket == "SAME_RANGE" else "B",
        "shadow_cross_range": bucket, "shadow_formed_idx": 0, "direction": "LONG",
        "outcome": outcome, "reset_reason": None, "resolved_at_candle_index": None,
        "log_handler_cross_check": None,
    }
    base.update(kw)
    return base


def test_build_contingency_counts_each_episode_once(probe):
    episodes = [
        _episode("SAME_RANGE", "TRADE_OPENED"),
        _episode("SAME_RANGE", "TRADE_OPENED"),
        _episode("CROSS_RANGE", "INVERTED_STOP_REJECTED"),
        _episode("UNKNOWN", "RESET_BEFORE_EXECUTION"),
    ]
    table = probe._build_contingency(episodes)
    assert table["SAME_RANGE"]["TRADE_OPENED"] == 2
    assert table["CROSS_RANGE"]["INVERTED_STOP_REJECTED"] == 1
    assert table["UNKNOWN"]["RESET_BEFORE_EXECUTION"] == 1
    total = sum(sum(row.values()) for row in table.values())
    assert total == len(episodes)


def test_self_consistency_check_catches_injected_mismatch(probe):
    good = _episode("SAME_RANGE", "TRADE_OPENED")
    bad = _episode("SAME_RANGE", "TRADE_OPENED",
                    shadow_source_htf="X", active_range_htf="Y")  # bucket says SAME_RANGE but isn't
    result = probe._self_consistency_check([good, bad])
    assert result["n_mismatches"] == 1
    assert result["mismatches"][0]["live_bucket"] == "SAME_RANGE"
    assert result["mismatches"][0]["recomputed_bucket"] == "CROSS_RANGE"


def test_self_consistency_check_clean_on_correct_data(probe):
    episodes = [
        _episode("SAME_RANGE", "TRADE_OPENED"),
        _episode("CROSS_RANGE", "INVERTED_STOP_REJECTED"),
    ]
    result = probe._self_consistency_check(episodes)
    assert result["n_mismatches"] == 0


def test_known_n2_sanity_check_reproduces_from_matching_episodes(probe):
    episodes = [
        _episode("CROSS_RANGE", "INVERTED_STOP_REJECTED",
                 candle_index=65, shadow_formed_idx=62,
                 shadow_source_htf="XAUUSD-HTF-000015", active_range_htf="XAUUSD-HTF-000016",
                 direction="SHORT"),
        _episode("CROSS_RANGE", "TRADE_OPENED",
                 candle_index=384, shadow_formed_idx=381,
                 shadow_source_htf="XAUUSD-HTF-000095", active_range_htf="XAUUSD-HTF-000096",
                 direction="LONG"),
    ]
    result = probe._sanity_check_known_n2(episodes)
    assert result["reproduced"] is True


def test_known_n2_sanity_check_fails_when_episode_missing(probe):
    episodes = [
        _episode("CROSS_RANGE", "INVERTED_STOP_REJECTED",
                 candle_index=65, shadow_formed_idx=62,
                 shadow_source_htf="XAUUSD-HTF-000015", active_range_htf="XAUUSD-HTF-000016",
                 direction="SHORT"),
        # second known episode intentionally omitted
    ]
    result = probe._sanity_check_known_n2(episodes)
    assert result["reproduced"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Artifact schema -- only runs against a real generated artifact; skipped if absent.
# ─────────────────────────────────────────────────────────────────────────────

def test_artifact_schema_and_self_consistency():
    if not _ARTIFACT.exists():
        pytest.skip("probe artifact not yet generated")
    import json
    with open(_ARTIFACT, "r", encoding="utf-8") as f:
        art = json.load(f)

    for key in (
        "artifact", "instrument", "csv_path", "csv_sha256", "config_version",
        "provenance", "contingency_table", "n_restorations_total", "episodes",
        "self_consistency_check", "known_n2_sanity_check", "authority_disclaimer",
    ):
        assert key in art

    # every episode counted in the contingency table must come from `episodes`
    total_in_table = sum(
        sum(row.values()) for row in art["contingency_table"].values()
    )
    assert total_in_table == len(art["episodes"])

    # the artifact's own runtime self-check must be clean, or the artifact is
    # not trustworthy per the plan's completion criterion
    assert art["self_consistency_check"]["n_mismatches"] == 0
    assert art["known_n2_sanity_check"]["reproduced"] is True

    # this probe reports counts only -- never economic authority
    assert art["authority_disclaimer"]["economic_claims_allowed"] is False
