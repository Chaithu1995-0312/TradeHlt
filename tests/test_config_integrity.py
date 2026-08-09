"""
tests/test_config_integrity.py
==============================
Unit tests for the governance guards (src/governance/config_integrity.py) that
catch the `deepdeektry` failure classes: stale validation evidence + ungoverned
active config. Fixture-based (tmp_path) — they assert the guard LOGIC, not the
live registry state (running the guard against real configs/production is a
governance *audit*, done separately).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = str(Path(__file__).parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from governance.config_integrity import (
    params_fingerprint,
    validation_summary_is_fresh,
    active_version_is_governed,
)


# ── validation_summary freshness ────────────────────────────────────────────

def _cfg(params, fingerprint):
    return {"params": params, "validation_summary": {"params_fingerprint": fingerprint}}


def test_fresh_summary_passes():
    p = {"body_ratio_min": 0.3, "retest_depth_max": 0.8}
    assert validation_summary_is_fresh(_cfg(p, params_fingerprint(p))) is True


def test_stale_summary_fails():
    """Params edited after validation → fingerprint no longer matches (the
    deepdeektry bug: summary describes old params)."""
    old = {"body_ratio_min": 0.65, "retest_depth_max": 0.2}
    new = {"body_ratio_min": 0.3, "retest_depth_max": 0.8}
    assert validation_summary_is_fresh(_cfg(new, params_fingerprint(old))) is False


def test_missing_fingerprint_fails():
    p = {"body_ratio_min": 0.3}
    assert validation_summary_is_fresh({"params": p, "validation_summary": {}}) is False
    assert validation_summary_is_fresh({"params": p}) is False


# ── governed-active ──────────────────────────────────────────────────────────

def _registry(tmp_path, active, promoted_versions):
    (tmp_path / "ACTIVE_VERSION").write_text(active, encoding="utf-8")
    with (tmp_path / "promotion_log.jsonl").open("w", encoding="utf-8") as fh:
        for v in promoted_versions:
            fh.write(json.dumps({"event": "PROMOTED", "version": v}) + "\n")
    return tmp_path


def test_governed_active_passes(tmp_path):
    rd = _registry(tmp_path, "v3_multi_2026_06", ["v2_multi_2026_04", "v3_multi_2026_06"])
    ok, _ = active_version_is_governed(rd)
    assert ok is True


def test_ungoverned_active_fails(tmp_path):
    """Active version has no PROMOTED entry (bypassed the gate)."""
    rd = _registry(tmp_path, "v2_multi_2026_04 - deepdeektry", ["v2_multi_2026_04"])
    ok, reason = active_version_is_governed(rd)
    assert ok is False
    # The space in the key is itself disqualifying (naming hygiene).
    assert "clean key" in reason or "no PROMOTED" in reason


def test_clean_key_required(tmp_path):
    rd = _registry(tmp_path, "v3 with spaces", ["v3 with spaces"])
    ok, reason = active_version_is_governed(rd)
    assert ok is False and "clean key" in reason


def test_no_promotion_log_fails(tmp_path):
    (tmp_path / "ACTIVE_VERSION").write_text("v3_multi_2026_06", encoding="utf-8")
    ok, reason = active_version_is_governed(tmp_path)
    assert ok is False and "promotion_log" in reason
