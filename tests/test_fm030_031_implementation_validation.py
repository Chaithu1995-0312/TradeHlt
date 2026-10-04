"""Cheap floor over the FROZEN FM-030/031 implementation-validation record (2026-07-22).

DELIBERATELY CHEAP — runs in seconds, no backtest. The expensive evidence (ledger SHAs, regime-event
counts, entry-set nesting) was produced once and frozen into
`docs/governance/fm030_031_implementation_validation-2026-07-22.json`; re-running two 70k-bar
gate-ON backtests per CI invocation (~18 min) to re-derive it would be a poor trade.

What this floor asserts is the set of invariants that are cheap AND would actually rot:
  1. the frozen record still exists and still answers all four questions YES;
  2. the two production configs still differ in exactly ONE behavioral key;
  3. the active config still selects the LEGACY basis, and FM-030/031 are still inactive
     (registration is not activation — §6.5);
  4. the basis genuinely reaches the pipeline through the production PROD_VERSION path.

Explicitly NOT asserted: trade counts, PnL, expectancy. Those belong to the runtime suite (R-1/R-2);
pinning them here would build the false-green oracle the freeze pin's own `coverage` block warns
about.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ARTIFACT = ROOT / "docs" / "governance" / "fm030_031_implementation_validation-2026-07-22.json"
ACTIVE_CONFIG = ROOT / "configs" / "production" / "v2_multi_2026_04.json"
SHADOW_CONFIG = ROOT / "configs" / "production" / "v2_multi_dimfix_shadow_2026_07.json"
SHADOW_VERSION = "v2_multi_dimfix_shadow_2026_07"

LEGACY_LEDGER_SHA = "9bcba138775d41091fa7a04c2f2c0315dd55c7e6f7e8843dd6c3181ca9b7f8df"
CORRECTED_LEDGER_SHA = "9e28abef0176175868fa1d729d1e9a82238385d04661ebbc8a10599d0e69e63d"


@pytest.fixture(scope="module")
def record() -> dict:
    assert ARTIFACT.is_file(), f"frozen validation record missing: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# ── 1. the frozen record ────────────────────────────────────────────────────────────────────
def test_all_four_questions_answered_yes(record):
    qs = record["questions"]
    assert set(qs) == {
        "Q1_config_gated_path_executes",
        "Q2_legacy_path_byte_identical",
        "Q3_decision_surface_changes_as_expected",
        "Q4_ledger_differs_only_from_the_identity_change",
    }
    for name, q in qs.items():
        assert q["answer"] == "YES", f"{name} is not YES"
        assert q.get("method") and q.get("evidence"), f"{name} lacks method/evidence"


def test_recorded_ledger_shas(record):
    q2 = record["questions"]["Q2_legacy_path_byte_identical"]["evidence"]
    assert q2["ledger_sha256"] == LEGACY_LEDGER_SHA
    assert q2["identical_across_all_9_runs"] is True
    q4 = record["questions"]["Q4_ledger_differs_only_from_the_identity_change"]["evidence"]
    assert q4["corrected_ledger_sha256"] == CORRECTED_LEDGER_SHA
    assert q4["corrected_deterministic_across_3_runs"] is True


def test_regime_discrimination_recorded(record):
    """The heart of Q3: 1 event (constant) vs 7 (discriminating) over 70,080 candles."""
    ev = record["questions"]["Q3_decision_surface_changes_as_expected"]["evidence"]
    assert ev["legacy_regime_change_events"] == 1
    assert ev["corrected_regime_change_events"] > ev["legacy_regime_change_events"]
    assert ev["candles_per_run"] == 70080


def test_entry_sets_nest_and_crt_is_invariant(record):
    ev = record["questions"]["Q4_ledger_differs_only_from_the_identity_change"]["evidence"]
    assert ev["nested_corrected_subset_of_legacy"] is True
    assert ev["added"] == 0
    assert ev["n_legacy"] == ev["kept"] + ev["removed"]
    assert ev["surviving_trades_geometry_identical"] is True
    assert ev["total_setups_both_arms"] == 13


def test_economics_are_quarantined_and_powerless(record):
    """E-001 guard: the economic block must stay non-authoritative and must NOT claim a result."""
    econ = record["NON_AUTHORITATIVE_ECONOMICS"]
    assert econ["power"] == "INSUFFICIENT"
    assert econ["verdict"] == "INSUFFICIENT"
    assert econ["legacy"]["n"] < 30 and econ["corrected"]["n"] < 30


def test_record_grants_no_activation_authority(record):
    c = record["conclusion"]
    assert c["implementation_validated"] is True
    assert c["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"
    assert c["ACTIVATION_AUTHORITY"] == "NONE"
    assert c["active_config_basis"] == "atr_relative (legacy, unchanged)"


def test_falsified_assumption_is_preserved_not_deleted(record):
    """§6.2 rule 4 — the superseded claim stays on the record with its reason."""
    fa = record["falsified_design_assumption"]
    assert "NOT nested" in fa["claim"]
    assert fa["status"].startswith("FALSIFIED")
    assert fa["why_it_differed"]


# ── 2/3. live config invariants ─────────────────────────────────────────────────────────────
def _flatten(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def test_configs_differ_in_exactly_one_behavioral_key():
    a = _flatten(json.loads(ACTIVE_CONFIG.read_text(encoding="utf-8")))
    b = _flatten(json.loads(SHADOW_CONFIG.read_text(encoding="utf-8")))
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    behavioral = {k for k in diff if not k.rsplit(".", 1)[-1].startswith("_")}
    assert behavioral == {"feature_pipeline.normalization_basis"}, (
        f"shadow config drifted from the active config: {sorted(behavioral)}. It must isolate the "
        f"identity change — any second difference confounds the A/B."
    )
    assert a["feature_pipeline.normalization_basis"] == "atr_relative"
    assert b["feature_pipeline.normalization_basis"] == "atr_absolute"


def test_thresholds_not_recalibrated_in_shadow():
    """Recalibrating dual_engine in the corrected arm would confound identity with tuning."""
    a = _flatten(json.loads(ACTIVE_CONFIG.read_text(encoding="utf-8")))
    b = _flatten(json.loads(SHADOW_CONFIG.read_text(encoding="utf-8")))
    for k in [k for k in a if "dual_engine" in k]:
        assert a[k] == b[k], f"{k} differs between arms"


def test_corrected_identities_remain_inactive():
    """Registration is not activation (§6.5)."""
    from features.registry import load_ontology

    ont = load_ontology()
    for name in ("ema_spread_atr", "momentum_score_atr"):
        assert ont["derived_metrics"][name]["active"] is False


# ── 4. the basis reaches the pipeline through the PRODUCTION resolution path ────────────────
def test_basis_reaches_pipeline_via_prod_version_path():
    """The unit floor covers an INJECTED cfg dict. This covers the path the spine actually uses:
    `FeaturePipeline(df)` with cfg=None -> get_prod_section -> module-global PROD_VERSION, which
    ProductionSpineSource rebinds per run (spine_signal_source.py:152-173).
    """
    import config_layer.production_config as pc
    from features.feature_pipeline import FeaturePipeline

    csv = ROOT / "data" / "BNBUSDT_M15.csv"
    if not csv.is_file():
        pytest.skip(f"corpus absent: {csv}")
    df = pd.read_csv(csv).head(2000)

    prev = pc.PROD_VERSION
    try:
        out_legacy, _ = FeaturePipeline(df).run()          # active config == atr_relative
        pc.PROD_VERSION = SHADOW_VERSION
        out_corrected, _ = FeaturePipeline(df).run()       # cfg=None -> resolves the SHADOW config
    finally:
        pc.PROD_VERSION = prev

    med_legacy = float(np.nanmedian(np.abs(out_legacy["ema_spread"].to_numpy(np.float64))))
    med_corrected = float(np.nanmedian(np.abs(out_corrected["ema_spread"].to_numpy(np.float64))))

    # BNBUSDT close ~ 650, so legacy magnitudes are O(100s) and corrected are O(1).
    assert med_legacy > 50.0, f"legacy arm not price-scaled (median {med_legacy})"
    assert med_corrected < 5.0, (
        f"corrected arm median |ema_spread| = {med_corrected}; the shadow config's "
        f"normalization_basis did NOT reach the pipeline through the PROD_VERSION path"
    )
