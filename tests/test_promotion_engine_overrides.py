"""
test_promotion_engine_overrides.py — promotion machinery carries engine-section overrides.

Tests the additive, backward-compatible extension that lets the governed promote path natively carry
crt_engine overrides (e.g. breakout_disp_threshold_overrides) — fixing the params-centric blind spot.
Pure-function tests only (no registry writes / no ACTIVE_VERSION flip).
"""
import hashlib
import json

import pytest

from governance.promotion_manager import PromotionManager

# Branch-lineage fencing (F-016): the promotion-engine crt_engine-override feature
# (_candidate_crt_engine / _build_registry_entry(crt_engine_overrides=...) / ODL-G3a
# merge-base fix) lives on a different code line; on `patch` the API is absent. Gate
# the feature-dependent tests with a documented capability probe (skip-with-reason, not
# silent hide) so they auto-activate where the feature exists. The two backward-compat
# tests below need no gate — they exercise the API present on every lineage.
requires_promo_overrides = pytest.mark.skipif(
    not hasattr(PromotionManager, "_candidate_crt_engine"),
    reason="requires promotion crt_engine-override feature (PromotionManager._candidate_crt_engine) — absent on the patch code line (F-016)",
)

_PARAMS = {"retest_depth_max": 0.8, "body_ratio_min": 0.3}
_OVR = {"breakout_disp_threshold": 1.5, "breakout_disp_threshold_overrides": {"BNBUSDT": 1.3}}


@requires_promo_overrides
def test_legacy_config_hash_is_params_only_and_unchanged():
    """load_version verifies config_hash == sha256(params); it MUST stay params-only."""
    entry = PromotionManager._build_registry_entry(
        _PARAMS, "vX", {"final_score": 1}, "n", "cid", crt_engine_overrides=_OVR)
    assert entry["config_hash"] == PromotionManager._compute_config_hash(_PARAMS)


@requires_promo_overrides
def test_config_hash_full_present_and_covers_overrides():
    with_ovr = PromotionManager._build_registry_entry(
        _PARAMS, "vX", {}, "n", "cid", crt_engine_overrides=_OVR)
    expected = hashlib.sha256(
        json.dumps({"params": _PARAMS, "crt_engine_overrides": _OVR}, sort_keys=True).encode()
    ).hexdigest()
    assert with_ovr["config_hash_full"] == expected


def test_no_override_entry_is_backward_compatible():
    """Without overrides the entry is unchanged (no config_hash_full key) — regression guard."""
    plain = PromotionManager._build_registry_entry(_PARAMS, "vX", {}, "n", "cid")
    assert "config_hash_full" not in plain
    assert plain["config_hash"] == PromotionManager._compute_config_hash(_PARAMS)


@requires_promo_overrides
def test_candidate_crt_engine_merges_base_then_overrides():
    """_candidate_crt_engine layers overrides on top of the base crt_engine section."""
    merged = PromotionManager._candidate_crt_engine(report_or_result=None, overrides=_OVR)
    assert merged is not None
    assert merged.get("breakout_disp_threshold_overrides") == {"BNBUSDT": 1.3}
    assert merged.get("breakout_disp_threshold") == 1.5


# ── ODL-G3a: merge-base selection (sentinel preferred; safe fallback) ─────────
def _write(p, obj):
    p.write_text(__import__("json").dumps(obj), encoding="utf-8")


@requires_promo_overrides
def test_merge_base_prefers_active_with_sentinel_even_if_not_v1_superset(tmp_path):
    """ODL-G3a fix: a full ACTIVE (has engine_runner) that PRUNED sections (not a v1 superset) is still
    chosen as base — the old superset guard wrongly rebased it onto v1."""
    _write(tmp_path / "v1_multi_2026_03.json",
           {"engine_runner": {}, "params": {}, "crt_engine": {}, "extra_section": {}, "config_id": "v1"})
    _write(tmp_path / "pruned.json",
           {"engine_runner": {}, "params": {}, "crt_engine": {}, "config_id": "pruned"})  # no extra_section
    (tmp_path / "ACTIVE_VERSION").write_text("pruned\n", encoding="utf-8")
    base = PromotionManager._load_full_base_config(tmp_path)
    assert base is not None and base.get("config_id") == "pruned"


def test_merge_base_falls_back_when_active_sparse(tmp_path):
    """ACTIVE without the engine_runner sentinel → fall back to a full baseline (never base on sparse)."""
    _write(tmp_path / "v1_multi_2026_03.json",
           {"engine_runner": {}, "params": {}, "config_id": "baseline_full"})
    _write(tmp_path / "sparse.json", {"params": {}, "config_id": "sparse"})  # no engine_runner
    (tmp_path / "ACTIVE_VERSION").write_text("sparse\n", encoding="utf-8")
    base = PromotionManager._load_full_base_config(tmp_path)
    assert base is not None and base.get("config_id") == "baseline_full"
