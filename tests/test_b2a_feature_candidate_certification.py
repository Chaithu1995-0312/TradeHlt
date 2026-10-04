"""B2A candidate-formula certification floor — the durable gate that FM-030
`ema_spread_atr` / FM-031 `momentum_score_atr` remain mathematically and temporally
certifiable, and that the verdict stays CERTIFICATION-ONLY (never a function of any
downstream behavioral/decision/economic diagnostic).

Evidence twin: docs/governance/b2a_feature_candidate_certification-*.json (+ .LATEST.json).
This floor runs the synthetic arm on every pytest invocation.

Scope: certifies candidate FORMULA correctness only. A green floor grants NO authority to
activate, wire, recalibrate, retrain, or change production behavior (§6.5). PROMOTE means
eligible for fresh B2B downstream-impact evaluation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "b2a_feature_candidate_certification.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("b2a_feature_candidate_certification", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["b2a_feature_candidate_certification"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("B2A probe not present")
    return _load_probe()


@pytest.fixture(scope="module")
def synth(probe):
    return probe._synthetic()


# ── three-path reconstruction agreement ──────────────────────────────────────────

def test_three_path_reconstruction_agrees(probe, synth):
    arm = probe.certify_arm(synth, "floor_synthetic")
    for feat in ("ema_spread", "momentum_score"):
        f = arm[feat]
        assert f["agree_A_vs_B_linked_tight"], (
            f"{feat}: independent (A) vs linked-ATR (B) reconstruction disagree beyond float64 "
            f"tolerance (max_resid={f['max_resid_A_vs_B']:.2e}) — candidate FORMULA is wrong."
        )
        assert f["agree_A_vs_C_legacy_identity_f32"], (
            f"{feat}: candidate != legacy/close within float32 (max_resid={f['max_resid_A_vs_C']:.2e})."
        )
        assert f["three_path_agree"]
    # independent SMA14(TR) must equal the pipeline's stored atr_14_raw
    assert arm["atr_abs_independent_matches_pipeline_atr_14_raw"]


def test_scalar_vector_parity(probe, synth):
    arm = probe.certify_arm(synth, "floor_synthetic")
    assert arm["ema_spread"]["scalar_vector_parity"]
    assert arm["momentum_score"]["scalar_vector_parity"]


def test_nan_inf_discipline(probe, synth):
    arm = probe.certify_arm(synth, "floor_synthetic")
    for feat in ("ema_spread", "momentum_score"):
        assert arm[feat]["inf_count"] == 0
        assert arm[feat]["nan_discipline_ok"], (
            f"{feat}: candidate finite-mask != (atr_abs>0 & close>0) guard."
        )


# ── dimensional / scale invariance ───────────────────────────────────────────────

def test_candidate_scale_invariant_while_legacy_scales(probe, synth):
    scale = probe.scale_invariance(synth)
    for feat in ("cand_es", "cand_ms"):
        assert scale[feat]["scale_invariant"], (
            f"{feat}: NOT scale-invariant (err={scale[feat]['scale_invariance_error']:.2e})."
        )
        assert scale[feat]["scale_invariance_error"] < probe.SCALE_TOL
    # and the LEGACY defect must reproduce (~100x) — recorded as a non-authoritative diagnostic
    diag = probe.downstream_diagnostics(synth)["legacy_scale_defect"]
    for feat in ("ema_spread", "momentum_score"):
        assert diag[feat]["median_ratio_x100_over_x1"] > 50.0


# ── PIT / prefix invariance ──────────────────────────────────────────────────────

def test_candidate_prefix_invariant(probe, synth):
    pit = probe.candidate_prefix_invariance(synth, cuts=[0.5, 0.8], label="floor")
    assert pit["all_prefix_invariant"], (
        "candidate prefix-VARIANT — future dependence in the candidate reconstruction: "
        f"{[k for k, v in pit['per_feature'].items() if v['verdict'] != 'PREFIX_INVARIANT']}"
    )
    assert all(c["shared_rows"] > 100 for c in pit["cuts"])


# ── verdict is certification-only ────────────────────────────────────────────────

def test_verdict_token_and_promote_path(probe, synth):
    cert = {"evaluable": True, "three_path_agree": True, "scalar_vector_parity": True,
            "nan_discipline_ok": True, "scale_invariant": True, "pit_invariant": True,
            "inf_count": 0}
    assert probe.decide_verdict(cert) == "PROMOTE"
    assert probe.decide_verdict({**cert, "three_path_agree": False}) == "REJECT"
    assert probe.decide_verdict({**cert, "inf_count": 3}) == "REJECT"
    assert probe.decide_verdict({**cert, "evaluable": False}) == "INCONCLUSIVE"


def test_verdict_ignores_downstream_diagnostics(probe):
    """PROMOTE/REJECT must NOT be a function of any behavioral/decision/economic field —
    injecting downstream keys leaves the verdict unchanged (the contamination guard)."""
    cert = {"evaluable": True, "three_path_agree": True, "scalar_vector_parity": True,
            "nan_discipline_ok": True, "scale_invariant": True, "pit_invariant": True,
            "inf_count": 0}
    base = probe.decide_verdict(cert)
    for poison in ("threshold_crossing_disagreement", "rank_correlation", "distribution_shift",
                   "sign_disagreement", "economic_expectancy", "model_auc"):
        assert probe.decide_verdict({**cert, poison: 0.0}) == base
        assert probe.decide_verdict({**cert, poison: 1e9}) == base


def test_full_report_promotes_and_is_deterministic(probe):
    r1 = probe.build_report(limit=0, include_corpus=False)   # synthetic-only (corpus-independent)
    r2 = probe.build_report(limit=0, include_corpus=False)
    import json
    assert (json.dumps(r1["certification"]["per_feature"], sort_keys=True, default=str)
            == json.dumps(r2["certification"]["per_feature"], sort_keys=True, default=str))
    assert r1["certification"]["overall_verdict"] in {"PROMOTE", "REJECT", "INCONCLUSIVE"}
    for name, f in r1["certification"]["per_feature"].items():
        assert f["verdict"] == "PROMOTE", f"{name} regressed to {f['verdict']}"
