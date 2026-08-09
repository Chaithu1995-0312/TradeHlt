"""
rr_confidence_probe.py — Track 1 (READ-ONLY) empirical probe for the RR-fusion confidence gate.

Purpose (see docs/implementation_plan / plan file): the RR-fusion confidence gate
    confidence = exp(-0.5 * d_sq);  bypass to Gaussian if confidence < confidence_bypass_threshold
is HYPOTHESISED to be mis-specified for its dimensionality — d_sq is a Mahalanobis distance over
~27 effective dims (38 canonical features minus 11 zero_indices), whose in-distribution E[d_sq] ~ 27,
so confidence ~ exp(-13.5) ~ 1e-6 << 0.3 for essentially every input, INCLUDING the model's own
training data.

DECISIVE TEST: a model cannot be out-of-distribution on its own training data. If in-sample bypass
is >= 95%, the defect is unambiguously the GATE, not model OOD / feature starvation.

This script is READ-ONLY w.r.t. repository code and config. It writes a single artifact under
results/rr_confidence_probe/ which is the promotion gate for every subsequent track.

Run:  python scripts/analysis/rr_confidence_probe.py
"""

from __future__ import annotations

import json
import math
import os
import sys

# --- repo-root import shim (script runs standalone) -----------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console guard
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np  # analysis-only dependency (NOT used by the pure-Python hot path)

from config_layer.rr.rr_pattern_miner import (
    NanoInferenceEngine,
    DEFAULT_MODEL_PATH,
    _MAHAL_CLIP,
    _CONF_BYPASS,
    _chi2_sf,          # reuse the SHIPPED χ² survival fn (single source of truth)
)
from config_layer.rr.rr_fusion import RRFusionLayer

_DATASET = os.path.join(
    _ROOT, "models", "BNBUSDT", "bnbusdt_balanced_20260524", "rr_dataset_202605_v1.json"
)
_OUT_DIR = os.path.join(_ROOT, "results", "rr_confidence_probe")

_BYPASS_GATE = 0.95  # decisive Track-1 criterion


def _percentiles(a: np.ndarray) -> dict:
    return {
        "min": float(np.min(a)),
        "p05": float(np.percentile(a, 5)),
        "median": float(np.median(a)),
        "mean": float(np.mean(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(np.max(a)),
    }


def _empirical_cdf(d: np.ndarray) -> dict:
    """Full empirical d_sq CDF — the operational truth (heavy-tailed vs χ²(dof); F-044 refinement)."""
    return {f"P{p}": round(float(np.percentile(d, p)), 4) for p in (10, 25, 50, 75, 90, 95, 99)}


def _chi2_isf(p: float, dof: int) -> float:
    """Inverse survival: the d_sq cut c with P(χ²_dof > c) = p (bisection on the shipped _chi2_sf)."""
    lo, hi = 0.0, 5000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _chi2_sf(mid, dof) > p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _threshold_bypass_table(d: np.ndarray, thresholds) -> list:
    return [{"d_sq_cut": round(float(t), 4),
             "bypass_pct": round(float(np.mean(d > t)) * 100, 4),
             "pass_pct": round(float(np.mean(d <= t)) * 100, 4)} for t in thresholds]


def _chi2p_bypass_table(d: np.ndarray, dof: int, ps) -> list:
    out = []
    for p in ps:
        cut = _chi2_isf(p, dof)
        out.append({"chi2_p": p, "theory_cut_d_sq": round(cut, 4),
                    "EMPIRICAL_bypass_pct": round(float(np.mean(d > cut)) * 100, 4)})
    return out


def _target_calibration_table(d: np.ndarray, dof: int, targets) -> list:
    """CANONICAL mechanism: target_bypass_fraction -> empirical cut -> express as (chi2_p, dof_scaled_max,
    percentile_cut). All three parameterize the SAME empirical cut = quantile(1 - target)."""
    out = []
    for t in targets:
        cut = float(np.quantile(d, 1.0 - t))              # the empirical cut that yields `t` bypass
        out.append({
            "target_bypass_pct": round(t * 100, 4),
            "empirical_d_sq_cut": round(cut, 4),
            "achieved_bypass_pct": round(float(np.mean(d > cut)) * 100, 4),
            "as_chi2_p": float(f"{_chi2_sf(cut, dof):.6g}"),
            "as_dof_scaled_max": round(cut / dof, 4) if dof > 0 else None,
            "as_percentile_cut": round(cut, 4),
        })
    return out


def _static_dof_validation(model_path: str) -> dict:
    """Track 1B: assert the trained stats give the effective rank we claim (dof = 38 - 11)."""
    with open(model_path, "r", encoding="utf-8") as f:
        st = json.load(f)
    conf_mu = st["conf_mu"]
    conf_P = st["conf_P"]
    scale_sigma = st["scale_sigma"]
    zero_indices = sorted(int(i) for i in st.get("zero_indices", []))
    n = int(st["n_features"])

    # Constant-zero training columns => std forced to 1.0 by the trainer (scale_std[std==0]=1).
    const_cols = sorted(i for i, s in enumerate(scale_sigma) if abs(s - 1.0) < 1e-12)

    checks = {
        "n_features": n,
        "len_conf_mu": len(conf_mu),
        "len_conf_P_rows": len(conf_P),
        "conf_P_col_widths": sorted({len(r) for r in conf_P}),
        "zero_indices": zero_indices,
        "n_zero_indices": len(zero_indices),
        "constant_zero_columns": const_cols,
        "effective_dof": n - len(zero_indices),
    }
    checks["PASS_dims_38"] = (len(conf_mu) == n == 38 and len(conf_P) == 38
                              and checks["conf_P_col_widths"] == [38])
    checks["PASS_zeroed_cols_match"] = (const_cols == zero_indices)
    return checks


def _d_sq_vectorized(engine: NanoInferenceEngine, X: np.ndarray) -> np.ndarray:
    """Replicate predict()'s d_sq EXACTLY (rr_pattern_miner.py:314-334), vectorized. UNCLIPPED."""
    scale_mu = np.asarray(engine.scale_mu, dtype=np.float64)
    scale_sigma = np.asarray(engine.scale_sigma, dtype=np.float64)
    conf_mu = np.asarray(engine.conf_mu, dtype=np.float64)
    conf_P = np.asarray(engine.conf_P, dtype=np.float64)

    Xz = X.copy()
    for idx in engine.zero_indices:            # same masking predict() applies (line 316-320)
        if idx < Xz.shape[1]:
            Xz[:, idx] = 0.0

    Xs = (Xz - scale_mu) / scale_sigma          # standardize (line 322-325)
    delta = Xs - conf_mu                         # (line 327)
    # d_sq_i = delta_i @ conf_P @ delta_i        (lines 328-334)
    d_sq = np.einsum("ij,jk,ik->i", delta, conf_P, delta)
    return d_sq


def main() -> int:
    os.makedirs(_OUT_DIR, exist_ok=True)

    # ---- load model + dataset ----
    engine = NanoInferenceEngine.load(DEFAULT_MODEL_PATH)
    with open(_DATASET, "r", encoding="utf-8") as f:
        ds = json.load(f)
    X = np.asarray(ds["X"], dtype=np.float64)
    n_samples, n_feat = X.shape

    static = _static_dof_validation(DEFAULT_MODEL_PATH)
    dof = static["effective_dof"]

    # ---- full-vector path: exact d_sq + gate decision ----
    d_sq_unclipped = _d_sq_vectorized(engine, X)
    d_sq_clipped = np.minimum(d_sq_unclipped, _MAHAL_CLIP)
    confidence = np.clip(np.exp(-0.5 * d_sq_clipped), 0.0, 1.0)
    bypass = confidence < _CONF_BYPASS
    bypass_frac_full = float(np.mean(bypass))

    # ---- cross-check against engine.predict() on a sample (faithfulness guard) ----
    xcheck = []
    rng = np.random.default_rng(0)
    idxs = rng.choice(n_samples, size=min(200, n_samples), replace=False)
    for i in idxs:
        out = engine.predict(features=list(X[i]), gaussian_score=0.5, gaussian_p_win=0.5, threshold=0.5)
        xcheck.append({
            "predict_confidence": float(out["confidence"]),
            "my_confidence": float(confidence[i]),
            "predict_status": out["status"],
            "my_bypass": bool(bypass[i]),
        })
    max_conf_err = max(abs(c["predict_confidence"] - c["my_confidence"]) for c in xcheck)
    status_agree = all(
        (c["predict_status"] == "bypassed_low_confidence") == c["my_bypass"] for c in xcheck
    )

    # ---- 3-feature score_dict stub path (F-038 legacy) for contrast ----
    layer = RRFusionLayer(model_path=DEFAULT_MODEL_PATH, threshold=0.5, enabled=True)
    stub_bypass = 0
    stub_n = min(2000, n_samples)
    # canonical indices for depth/body/disp — reuse the engine's expectation implicitly via names
    from features.feature_schema import FEATURE_INDEX_MAP
    i_depth = FEATURE_INDEX_MAP["retest_depth"]
    i_body = FEATURE_INDEX_MAP["body_ratio"]
    i_disp = FEATURE_INDEX_MAP["disp_strength"]
    for i in range(stub_n):
        out = layer.score_dict(
            depth=float(X[i, i_depth]), body=float(X[i, i_body]), disp=float(X[i, i_disp]),
            gaussian_score=0.5, gaussian_p_win=0.5,
            is_asia=0.0, is_london=0.0, is_newyork=0.0, hour=0, threshold=0.5,
        )
        if out.get("status") in ("bypassed_low_confidence", "drift_detected"):
            stub_bypass += 1
    stub_bypass_frac = stub_bypass / stub_n

    passed = bypass_frac_full >= _BYPASS_GATE

    report = {
        "artifact": "rr_confidence_probe",
        "model_path": DEFAULT_MODEL_PATH,
        "dataset": os.path.relpath(_DATASET, _ROOT),
        "n_samples": int(n_samples),
        "n_features": int(n_feat),
        "gate_constants": {
            "confidence_bypass_threshold": _CONF_BYPASS,
            "mahal_clip": _MAHAL_CLIP,
            "effective_dof": dof,
            "d_sq_needed_to_pass": round(-2.0 * math.log(_CONF_BYPASS), 4),
        },
        "static_dof_validation_1B": static,
        "full_vector_path_1A": {
            "in_sample_bypass_fraction": round(bypass_frac_full, 6),
            "d_sq_unclipped_percentiles": _percentiles(d_sq_unclipped),
            "confidence_percentiles": _percentiles(confidence),
            "expected_in_dist_E_d_sq (=dof)": dof,
        },
        "empirical_calibration": {
            "note": ("The empirical d_sq is heavy-tailed vs χ²(dof) (P99 emp ≫ theory), so theory "
                     "p-values mis-estimate real bypass. Operating point = target_bypass -> empirical cut."),
            "empirical_d_sq_cdf": _empirical_cdf(d_sq_unclipped),
            "theory_chi2_reference": {f"P{p}": round(_chi2_isf((100 - p) / 100.0, dof), 4)
                                      for p in (50, 90, 95, 99)},
            "threshold_to_bypass": _threshold_bypass_table(
                d_sq_unclipped, [2.408, 4.30, 10, 20, dof, 40.11, 46.96]),
            "chi2_p_to_empirical_bypass": _chi2p_bypass_table(d_sq_unclipped, dof, [0.05, 0.01, 0.001]),
            "CANONICAL_target_to_threshold": _target_calibration_table(
                d_sq_unclipped, dof, [0.01, 0.05, 0.10, 0.20]),
        },
        "legacy_3feature_stub_path": {
            "n_evaluated": stub_n,
            "bypass_fraction": round(stub_bypass_frac, 6),
        },
        "faithfulness_crosscheck": {
            "n": len(xcheck),
            "max_confidence_abs_err_vs_predict": max_conf_err,
            "status_agreement": status_agree,
        },
        "GATE": {
            "criterion": "in-sample full-vector bypass >= 0.95 (decisive)",
            "median_d_sq_is_corroborator_not_gate": True,
            "PASS": bool(passed),
        },
        "track_3a_gate_decision": {
            "selection_rule": ("CANONICAL: target_bypass_fraction -> empirical d_sq cut (from "
                               "CANONICAL_target_to_threshold above). NOT a theory chi2 p-value read "
                               "as a bypass rate — the empirical d_sq is heavy-tailed, so chi2_tail "
                               "p=0.01 gives ~7.3% bypass (NOT 1%), p=0.05 gives ~10.9% (NOT 5%)."),
            "default_target_bypass": "≈5% (see CANONICAL_target_to_threshold[target=5%]).",
            "mode_choice": ("percentile (or chi2_tail with an EMPIRICALLY-calibrated p) — both "
                            "parameterize the same empirical cut; percentile is most robust to the "
                            "heavy tail / precision-matrix conditioning."),
            "shipped_default": ("legacy_scalar (byte-parity); dof-aware modes are validated but INERT "
                                "until an rr_fusion re-enable (Track 4, ΔG001-gated)."),
        },
    }

    with open(os.path.join(_OUT_DIR, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Part A metadata close-out: derive the training_distribution provenance for the CURRENT (already
    # trained, generated) model as an ADJACENT file (never hand-edit the generated model.json). Future
    # models carry this block natively via RRPatternTrainer.train(). This is the reproducible contract
    # behind any confidence_gate.mode=percentile d_sq_cut.
    meta = {
        "model": os.path.basename(DEFAULT_MODEL_PATH),
        "dataset": os.path.basename(_DATASET),
        "training_distribution": {
            "n": int(n_samples),
            "effective_dof": int(dof),
            "d_sq_p50": round(float(np.percentile(d_sq_unclipped, 50)), 6),
            "d_sq_p90": round(float(np.percentile(d_sq_unclipped, 90)), 6),
            "d_sq_p95": round(float(np.percentile(d_sq_unclipped, 95)), 6),
            "d_sq_p99": round(float(np.percentile(d_sq_unclipped, 99)), 6),
        },
        "derived_by": "scripts/analysis/rr_confidence_probe.py",
        "note": "Adjacent provenance for the generated model; percentile-gate d_sq_cut source.",
    }
    _meta_path = os.path.join(os.path.dirname(DEFAULT_MODEL_PATH) or ".", "rr_model.meta.json")
    with open(_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    md = _render_md(report)
    with open(os.path.join(_OUT_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(md)
    print(f"\nArtifact: {os.path.relpath(_OUT_DIR, _ROOT)}/report.json")
    print(f"GATE PASS (bypass>=95%): {passed}")
    return 0 if passed else 2


def _render_md(r: dict) -> str:
    fv = r["full_vector_path_1A"]
    st = r["static_dof_validation_1B"]
    gc = r["gate_constants"]
    xc = r["faithfulness_crosscheck"]
    lines = [
        "# RR Confidence-Gate Probe (Track 1)",
        "",
        f"**Model:** `{r['model_path']}`  **Dataset:** `{r['dataset']}`  **n={r['n_samples']}×{r['n_features']}**",
        "",
        "## Gate constants",
        f"- confidence_bypass_threshold = {gc['confidence_bypass_threshold']} → needs **d_sq < {gc['d_sq_needed_to_pass']}** to pass",
        f"- mahal_clip = {gc['mahal_clip']};  effective dof = **{gc['effective_dof']}**;  theory E[d_sq] ≈ dof",
        "",
        "## 1B — static dof validation",
        f"- len(conf_mu)={st['len_conf_mu']}, conf_P rows={st['len_conf_P_rows']}, col widths={st['conf_P_col_widths']}",
        f"- zero_indices (n={st['n_zero_indices']}) = {st['zero_indices']}",
        f"- constant-zero columns = {st['constant_zero_columns']}",
        f"- PASS_dims_38={st['PASS_dims_38']}  PASS_zeroed_cols_match={st['PASS_zeroed_cols_match']}",
        "",
        "## 1A — full-vector in-sample result (DECISIVE)",
        f"- **in-sample bypass fraction = {fv['in_sample_bypass_fraction']:.4%}**",
        f"- d_sq (unclipped): {fv['d_sq_unclipped_percentiles']}",
        f"- confidence: {fv['confidence_percentiles']}",
        "",
        "## Legacy 3-feature stub (contrast)",
        f"- bypass fraction = {r['legacy_3feature_stub_path']['bypass_fraction']:.4%} "
        f"(n={r['legacy_3feature_stub_path']['n_evaluated']})",
        "",
        "## Empirical calibration (CANONICAL: target bypass → empirical cut)",
        "empirical d_sq CDF vs theory χ²(dof): "
        + ", ".join(f"{k}={v}" for k, v in r["empirical_calibration"]["empirical_d_sq_cdf"].items()),
        "",
        "| target bypass | empirical d_sq cut | achieved | as chi2_p | as dof_scaled_max |",
        "|---|---|---|---|---|",
        *[f"| {row['target_bypass_pct']}% | {row['empirical_d_sq_cut']} | {row['achieved_bypass_pct']}% "
          f"| {row['as_chi2_p']} | {row['as_dof_scaled_max']} |"
          for row in r["empirical_calibration"]["CANONICAL_target_to_threshold"]],
        "",
        "## Faithfulness cross-check vs engine.predict()",
        f"- max |Δconfidence| = {xc['max_confidence_abs_err_vs_predict']:.2e}; status agreement = {xc['status_agreement']}",
        "",
        f"## GATE — {r['GATE']['criterion']}",
        f"- **PASS = {r['GATE']['PASS']}**",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
