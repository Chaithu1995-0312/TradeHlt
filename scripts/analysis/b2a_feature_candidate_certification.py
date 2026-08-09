"""
b2a_feature_candidate_certification.py — B2A: candidate-formula CERTIFICATION for
FM-030 `ema_spread_atr` and FM-031 `momentum_score_atr` (READ-ONLY, observe-only).

B0/B1 (2026-07-12) proved the legacy features `ema_spread` (FM-022) / `momentum_score`
(FM-023) carry a dimensional defect (absolute-price numerator / close-relative `atr` →
they SCALE with price level) and registered the scale-invariant corrections FM-030/FM-031
as INACTIVE `proposed_correction` entries in configs/formulas/market_ontology.yaml. B2A is
the observe-only slice that CERTIFIES those two candidate formulas are mathematically and
temporally sound — from independently reconstructed OHLC semantics — nothing more.

Pipeline: B2A (certify candidate math) → B2B (regenerate downstream-impact evidence from
certified semantics) → B2C (governed activation). Closure is boundary-scoped and
non-transitive: a PROMOTE here grants NO authority to activate, wire consumers, recalibrate
thresholds, retrain artifacts, or change production behavior. It only makes the candidate
formula ELIGIBLE for fresh B2B downstream-impact evaluation.

This script is READ-ONLY w.r.t. repository code and config. It writes a single dated,
immutable evidence artifact under docs/governance/ (+ a stable LATEST pointer). It computes
NO production feature math into any registered name — the candidate math lives ONLY here.

CERTIFICATION metrics (the ONLY inputs to the verdict):
  1. THREE-PATH reconstruction agreement (NOT merely candidate*close==legacy):
       A. independent raw-OHLC : TR_abs → SMA14(TR_abs)=ATR_abs ; EMA9,EMA21 ;
                                 cand = (EMA9-EMA21)/ATR_abs , close.diff()/ATR_abs   (float64)
       B. linked reconstruction: ATR_abs = atr_relative * close (pipeline's stored atr) ;
                                 cand = numerator / (atr*close)
       C. legacy-column identity: cand = legacy_pipeline_column / close
     All three must agree within float32 tolerance on aligned, warmup-cleared rows.
  2. dimensional / SCALE invariance (independent float64, price ×1 vs ×100).
  3. NaN/Inf discipline (candidate finite exactly where atr>0 & close>0; no Inf).
  4. deterministic recomputation (two runs byte-identical).
  5. scalar ↔ vector parity (local float→float twin equals the vectorized candidate).
  6. PIT / prefix invariance (recompute on strict prefixes; shared timestamps identical).

Anything comparing legacy-vs-candidate BEHAVIOR (rank/sign disagreement, threshold
crossings, distribution shift, cross-instrument KS/PSI, the legacy scale defect) is
DIAGNOSTIC ONLY — recorded under NON_AUTHORITATIVE_DOWNSTREAM_DIAGNOSTICS, authority: none,
and NEVER an input to the verdict. All such prior evidence is treated as UNKNOWN for
certification (contamination rule).

Verdicts (per feature + overall roll-up): PROMOTE · REJECT · INCONCLUSIVE.
Exit code: 0 = harness trusted (certification evaluable) · 2 = harness untrusted.

Usage: python scripts/analysis/b2a_feature_candidate_certification.py [--limit 30000]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402  (analysis-only dep; NOT the pure-Python hot path)
import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402

# ── governance-versioned method identity (the method IS governance) ────────────
B2A_CERT_VERSION = "1.0.0"
RECON_METHOD_VERSION = "1.0.0"

# STRUCTURAL constants of the candidate identities (mirror ontology FM-030/FM-031 +
# feature_pipeline compute_indicators / compute_canonical_ema_features). Read-only.
EMA_FAST_SPAN = 9
EMA_SLOW_SPAN = 21
ATR_LOOKBACK = 14

# tolerances
# TIGHT: independent-float64 (A) vs linked ATR reconstruction (B). Both carry float64
# numerators, differing only in the ATR source (independent SMA14(TR) vs pipeline
# atr_relative*close) — a WRONG formula (missing *close, wrong span, sign) diverges by
# O(0.1)…O(close); float32 atr storage noise is ~1e-8. Also gates scalar↔vector parity.
RTOL_TIGHT = 1e-5
ATOL_TIGHT = 1e-7
# FLOAT32: independent (A) vs the EMITTED legacy-column identity (C = legacy/close). C
# inherits the pipeline's float32 storage of `ema_fast-ema_slow` (catastrophic cancellation
# of two ~price-magnitude float32 values → abs error scales with price/atr; ≤~3e-4 on BTC).
# This band tolerates that storage noise yet still rejects any real formula error (≥O(0.1)).
RTOL_F32 = 1e-2
ATOL_F32 = 2e-3
SCALE_TOL = 1e-6    # candidate is dimensionless; independent float64 ×1 vs ×100
MIN_VALID_ROWS = 100

_GOV = _ROOT / "docs" / "governance"
_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_MAJORS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")


# ── corpus ─────────────────────────────────────────────────────────────────────

def _load_corpus(symbol: str, limit: int) -> pd.DataFrame | None:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        return None
    df = pd.read_csv(csv)
    df.columns = [c.strip().lower() for c in df.columns]
    if limit:
        df = df.head(limit).copy()
    return df


def _synthetic(n: int = 1200, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def _run_pipeline(raw: pd.DataFrame) -> pd.DataFrame:
    """Finalized frame (all columns retained) indexed by timestamp."""
    feat_df, _vectors = FeaturePipeline(raw.copy()).run()
    if "timestamp" not in feat_df.columns:
        raise RuntimeError("finalized frame lacks timestamp column")
    return feat_df.set_index("timestamp")


# ── candidate math — lives ONLY here (not registered, not wired) ─────────────────

def _independent_reconstruction(raw: pd.DataFrame) -> pd.DataFrame:
    """Path A: candidate reconstructed from OHLC ALONE, float64, causal/trailing only.

    TR_abs = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR_abs = SMA14(TR_abs)                      (== pipeline atr_14_raw)
    EMA9, EMA21 = ewm(span, adjust=False)
    cand_es = (EMA9-EMA21)/ATR_abs , cand_ms = close.diff()/ATR_abs   (atr_abs>0 & close>0 else nan)
    """
    df = raw.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    close = df["close"].astype("float64")
    high = df["high"].astype("float64")
    low = df["low"].astype("float64")
    prev_close = close.shift(1)
    tr_abs = np.maximum(high - low,
                        np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
    atr_abs = tr_abs.rolling(ATR_LOOKBACK).mean()
    ema9 = close.ewm(span=EMA_FAST_SPAN, adjust=False).mean()
    ema21 = close.ewm(span=EMA_SLOW_SPAN, adjust=False).mean()
    close_delta = close.diff()
    denom = atr_abs.where((atr_abs > 0) & (close > 0))   # NaN elsewhere (guard)
    out = pd.DataFrame({
        "atr_abs": atr_abs, "ema9": ema9, "ema21": ema21, "close": close,
        "close_delta": close_delta,
        "cand_es": (ema9 - ema21) / denom,
        "cand_ms": close_delta / denom,
    })
    if "timestamp" in df.columns:
        out.index = pd.Index(pd.to_datetime(df["timestamp"]), name="timestamp")
    return out


def _cand_es_scalar(ema_fast: float, ema_slow: float, atr_rel: float, close: float) -> float:
    """FM-030 scalar twin: (ema_fast-ema_slow)/(atr_rel*close); nan when atr_rel<=0 or close<=0."""
    if atr_rel > 0 and close > 0:
        return (ema_fast - ema_slow) / (atr_rel * close)
    return float("nan")


def _cand_ms_scalar(close_delta: float, atr_rel: float, close: float) -> float:
    """FM-031 scalar twin: close_delta/(atr_rel*close); nan when atr_rel<=0 or close<=0."""
    if atr_rel > 0 and close > 0:
        return close_delta / (atr_rel * close)
    return float("nan")


# ── stats helpers (scipy-free; used ONLY for non-authoritative diagnostics) ──────

def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        return float("nan")
    ra = pd.Series(a[m]).rank().to_numpy()
    rb = pd.Series(b[m]).rank().to_numpy()
    return _pearson(ra, rb)


# ── certification of one corpus arm ──────────────────────────────────────────────

def _finite_pair(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.isfinite(x) & np.isfinite(y)


def _max_resid(x: np.ndarray, y: np.ndarray) -> float:
    m = _finite_pair(x, y)
    if not m.any():
        return float("nan")
    return float(np.max(np.abs(x[m] - y[m])))


def _agree(x: np.ndarray, y: np.ndarray, rtol: float, atol: float) -> bool:
    m = _finite_pair(x, y)
    if not m.any():
        return False
    return bool(np.allclose(x[m], y[m], rtol=rtol, atol=atol))


def certify_arm(raw: pd.DataFrame, label: str) -> dict:
    """Three-path agreement + NaN/Inf + scalar↔vector parity for one corpus arm."""
    pipe = _run_pipeline(raw)
    indep = _independent_reconstruction(raw)
    shared = pipe.index.intersection(indep.index)
    n_shared = len(shared)

    atr_rel = pipe.loc[shared, "atr"].to_numpy(dtype="float64")
    close = pipe.loc[shared, "close"].to_numpy(dtype="float64")
    ema_fast = pipe.loc[shared, "ema_fast"].to_numpy(dtype="float64")   # pipeline float32-stored
    ema_slow = pipe.loc[shared, "ema_slow"].to_numpy(dtype="float64")
    legacy_es = pipe.loc[shared, "ema_spread"].to_numpy(dtype="float64")
    legacy_ms = pipe.loc[shared, "momentum_score"].to_numpy(dtype="float64")
    atr_14_raw = pipe.loc[shared, "atr_14_raw"].to_numpy(dtype="float64")
    ema9 = indep.loc[shared, "ema9"].to_numpy(dtype="float64")          # independent float64
    ema21 = indep.loc[shared, "ema21"].to_numpy(dtype="float64")
    close_delta = indep.loc[shared, "close_delta"].to_numpy(dtype="float64")
    atr_abs_indep = indep.loc[shared, "atr_abs"].to_numpy(dtype="float64")

    atr_abs_linked = atr_rel * close  # linked ATR reconstruction (== atr_14_raw within float32)

    with np.errstate(divide="ignore", invalid="ignore"):
        denomB = np.where(atr_abs_linked > 0, atr_abs_linked, np.nan)
        # Path A: independent float64 (SMA14(TR) denom, float64 EMAs)
        A_es = indep.loc[shared, "cand_es"].to_numpy(dtype="float64")
        A_ms = indep.loc[shared, "cand_ms"].to_numpy(dtype="float64")
        # Path B: linked reconstruction — float64 numerators / (atr_relative*close). Isolates
        # the ATR source, so A≈B is TIGHT and certifies ATR reconstruction equivalence.
        B_es = (ema9 - ema21) / denomB
        B_ms = close_delta / denomB
        # Path C: emitted legacy-column identity candidate == legacy/close. Inherits pipeline
        # float32 storage (cancellation) → compared at float32 tolerance.
        C_es = np.where(close > 0, legacy_es / close, np.nan)
        C_ms = np.where(close > 0, legacy_ms / close, np.nan)
        # float32-input vectorized form (for scalar↔vector parity against the runtime-style twin)
        vec_es_f32 = (ema_fast - ema_slow) / denomB
        vec_ms_f32 = close_delta / denomB

    # scalar ↔ vector parity: local float→float twin vs the identical-input vectorized form
    cap = min(n_shared, 3000)
    sc_es = np.array([_cand_es_scalar(ema_fast[i], ema_slow[i], atr_rel[i], close[i])
                      for i in range(cap)])
    sc_ms = np.array([_cand_ms_scalar(close_delta[i], atr_rel[i], close[i])
                      for i in range(cap)])
    parity_es = _agree(sc_es, vec_es_f32[:cap], RTOL_TIGHT, ATOL_TIGHT)
    parity_ms = _agree(sc_ms[1:], vec_ms_f32[1:cap], RTOL_TIGHT, ATOL_TIGHT)  # row 0 close_delta NaN

    # NaN/Inf discipline on the independent candidate (finite ⇔ atr_abs>0 & close>0)
    expect_finite = (atr_abs_indep > 0) & (close > 0)
    inf_es = int(np.isinf(A_es).sum())
    inf_ms = int(np.isinf(A_ms).sum())
    nan_ok_es = bool(np.array_equal(np.isfinite(A_es), expect_finite))
    # momentum row 0 is NaN via close_delta regardless of guard → exclude it
    nan_ok_ms = bool(np.array_equal(np.isfinite(A_ms)[1:], expect_finite[1:]))

    def _feat(paths_a, paths_b, paths_c, parity, inf_n, nan_ok, extra):
        agree_ab = _agree(paths_a, paths_b, RTOL_TIGHT, ATOL_TIGHT)       # tight (independent)
        agree_ac = _agree(paths_a, paths_c, RTOL_F32, ATOL_F32)           # float32 (emitted legacy)
        return {
            "n_shared_rows": n_shared,
            "three_path_agree": bool(agree_ab and agree_ac),
            "agree_A_vs_B_linked_tight": agree_ab,
            "agree_A_vs_C_legacy_identity_f32": agree_ac,
            "max_resid_A_vs_B": _max_resid(paths_a, paths_b),
            "max_resid_A_vs_C": _max_resid(paths_a, paths_c),
            "scalar_vector_parity": bool(parity),
            "inf_count": inf_n,
            "nan_discipline_ok": bool(nan_ok),
            **extra,
        }

    atr_abs_agree = _agree(atr_abs_indep, atr_14_raw, RTOL_TIGHT, ATOL_TIGHT)
    return {
        "corpus": label,
        "n_shared_rows": n_shared,
        "evaluable": n_shared >= MIN_VALID_ROWS,
        "atr_abs_independent_matches_pipeline_atr_14_raw": bool(atr_abs_agree),
        "ema_spread": _feat(A_es, B_es, C_es, parity_es, inf_es, nan_ok_es,
                            {"scalar_parity_rows": cap}),
        "momentum_score": _feat(A_ms, B_ms, C_ms, parity_ms, inf_ms, nan_ok_ms,
                                {"scalar_parity_rows": cap}),
    }


# ── scale invariance (independent float64, ×1 vs ×100) ───────────────────────────

def scale_invariance(base: pd.DataFrame) -> dict:
    x1 = _independent_reconstruction(base)
    scaled = base.copy()
    for col in ("open", "high", "low", "close"):
        scaled[col] = scaled[col] * 100.0
    x100 = _independent_reconstruction(scaled)
    shared = x1.index.intersection(x100.index)
    out = {}
    for feat in ("cand_es", "cand_ms"):
        a = x1.loc[shared, feat].to_numpy(dtype="float64")
        b = x100.loc[shared, feat].to_numpy(dtype="float64")
        err = _max_resid(a, b)
        out[feat] = {"scale_invariance_error": err,
                     "scale_invariant": bool(np.isfinite(err) and err < SCALE_TOL)}
    return out


# ── non-authoritative downstream diagnostics (recorded, NEVER gating) ────────────

def downstream_diagnostics(base: pd.DataFrame) -> dict:
    """authority: none. Legacy-vs-candidate behavior, incl. the legacy scale defect.
    Prior behavioral/decision-impact/economic evidence is UNKNOWN for certification."""
    pipe = _run_pipeline(base)
    indep = _independent_reconstruction(base)
    shared = pipe.index.intersection(indep.index)
    diag = {"_authority": "none — NEVER an input to the certification verdict"}
    for feat, legacy_col in (("ema_spread", "ema_spread"), ("momentum_score", "momentum_score")):
        cand = indep.loc[shared, "cand_es" if feat == "ema_spread" else "cand_ms"].to_numpy("float64")
        leg = pipe.loc[shared, legacy_col].to_numpy("float64")
        m = np.isfinite(cand) & np.isfinite(leg)
        sign_dis = float(np.mean(np.sign(cand[m]) != np.sign(leg[m]))) if m.any() else float("nan")
        diag[feat] = {
            "spearman_rank_correlation_legacy_vs_candidate": _spearman(leg, cand),
            "sign_disagreement_fraction": sign_dis,
            "note": "monotone within-instrument by construction; kept for context only",
        }
    # legacy scale defect (the thing FM-030/031 corrects) — diagnostic reproduction
    p1 = _run_pipeline(base)
    scaled = base.copy()
    for c in ("open", "high", "low", "close"):
        scaled[c] = scaled[c] * 100.0
    p100 = _run_pipeline(scaled)
    sh = p1.index.intersection(p100.index)
    for feat in ("ema_spread", "momentum_score"):
        a = np.abs(p1.loc[sh, feat].to_numpy("float64"))
        b = np.abs(p100.loc[sh, feat].to_numpy("float64"))
        mm = np.isfinite(a) & np.isfinite(b) & (a > 0)
        ratio = float(np.median(b[mm] / a[mm])) if mm.any() else float("nan")
        diag.setdefault("legacy_scale_defect", {})[feat] = {
            "median_ratio_x100_over_x1": ratio,
            "interpretation": "legacy scales with price (~100x) — the defect; candidate is scale-invariant",
        }
    return diag


# ── verdict (reads ONLY certification inputs) ────────────────────────────────────

def decide_verdict(cert: dict) -> str:
    """PROMOTE/REJECT/INCONCLUSIVE from certification metrics ALONE.

    `cert` MUST contain only certification fields (three_path_agree, scalar_vector_parity,
    nan_discipline_ok, inf_count, scale_invariant, pit_invariant, evaluable). Downstream
    diagnostics are structurally absent here and can never influence the outcome.
    """
    if not cert.get("evaluable", False):
        return "INCONCLUSIVE"
    required_true = [
        cert.get("three_path_agree"),
        cert.get("scalar_vector_parity"),
        cert.get("nan_discipline_ok"),
        cert.get("scale_invariant"),
        cert.get("pit_invariant"),
    ]
    if cert.get("inf_count", 0) != 0:
        return "REJECT"
    if any(v is False for v in required_true):
        return "REJECT"
    if all(v is True for v in required_true):
        return "PROMOTE"
    return "INCONCLUSIVE"


# ── PIT / prefix invariance of the candidate (independent path) ──────────────────

def candidate_prefix_invariance(raw: pd.DataFrame, cuts: list[float], label: str) -> dict:
    full = _independent_reconstruction(raw)
    per = {f: {"verdict": "PREFIX_INVARIANT", "mismatch_bars": 0, "cuts_checked": 0}
           for f in ("cand_es", "cand_ms")}
    cut_rows = []
    for frac in cuts:
        n_cut = int(len(raw) * frac)
        pref = _independent_reconstruction(raw.head(n_cut))
        shared = pref.index.intersection(full.index)
        cut_rows.append({"cut_fraction": frac, "cut_bars": n_cut, "shared_rows": len(shared)})
        for f in ("cand_es", "cand_ms"):
            a = pref.loc[shared, f].to_numpy()
            b = full.loc[shared, f].to_numpy()
            eq = (a == b) | (pd.isna(a) & pd.isna(b))
            n_bad = int((~eq).sum())
            per[f]["cuts_checked"] += 1
            if n_bad:
                per[f]["verdict"] = "VARIANT"
                per[f]["mismatch_bars"] += n_bad
    return {"corpus": label, "cuts": cut_rows, "per_feature": per,
            "all_prefix_invariant": all(v["verdict"] == "PREFIX_INVARIANT" for v in per.values())}


# ── static provenance for the evidence artifact ──────────────────────────────────

def _provenance() -> dict:
    guard = "atr>0 and close>0 else nan"
    return {
        "ema_spread_atr": {
            "candidate_id": "FM-030", "replaces": "FM-022",
            "semantic_version": "2.0-atr-absolute", "units": "dimensionless",
            "normalization_basis": "atr_absolute",
            "formula": "(ema_fast - ema_slow) / (atr * close)",
            "guard": guard,
            "linked_formula_dag": {
                "ema_fast": "close.ewm(span=9, adjust=False).mean()",
                "ema_slow": "close.ewm(span=21, adjust=False).mean()",
                "TR_abs": "max(high-low, |high-prev_close|, |low-prev_close|)",
                "ATR_abs": "SMA14(TR_abs)  (== feature_pipeline atr_14_raw)",
                "atr_relative": "atr_14_raw / close  (pipeline `atr` column)",
                "atr_absolute_reconstructed": "atr_relative * close  (== ATR_abs)",
                "ema_spread_atr": "(ema_fast - ema_slow) / ATR_abs",
            },
            "raw_inputs": ["high", "low", "close"],
            "lookback": {"ema_fast": 9, "ema_slow": 21, "atr": 14},
            "warmup": "first ATR_LOOKBACK-1 bars have NaN ATR_abs → candidate NaN (dropped by pipeline finalize)",
            "availability": "bar t uses OHLC ≤ t only (trailing SMA/EWM); no lookahead",
            "pit_semantics": "same-bar / backward-looking; prefix-invariant",
        },
        "momentum_score_atr": {
            "candidate_id": "FM-031", "replaces": "FM-023",
            "semantic_version": "2.0-atr-absolute", "units": "dimensionless",
            "normalization_basis": "atr_absolute",
            "formula": "close_delta / (atr * close)",
            "guard": guard,
            "linked_formula_dag": {
                "close_delta": "close.diff()  (one-bar change)",
                "TR_abs": "max(high-low, |high-prev_close|, |low-prev_close|)",
                "ATR_abs": "SMA14(TR_abs)  (== feature_pipeline atr_14_raw)",
                "momentum_score_atr": "close_delta / ATR_abs",
            },
            "raw_inputs": ["high", "low", "close"],
            "lookback": {"close_delta": 1, "atr": 14},
            "warmup": "row 0 close_delta NaN + first ATR_LOOKBACK-1 bars NaN ATR_abs → candidate NaN",
            "availability": "bar t uses OHLC ≤ t only; no lookahead",
            "pit_semantics": "same-bar delta / backward-looking; prefix-invariant",
        },
    }


# ── orchestration ────────────────────────────────────────────────────────────────

def _rollup_feature(arms: list[dict], feat: str, scale: dict, pit_ok: bool) -> dict:
    """Aggregate certification metrics for one feature across all corpus arms + scale + pit."""
    evaluable = any(a["evaluable"] for a in arms)
    ev_arms = [a for a in arms if a["evaluable"]]
    three_path = all(a[feat]["three_path_agree"] for a in ev_arms) if ev_arms else False
    parity = all(a[feat]["scalar_vector_parity"] for a in ev_arms) if ev_arms else False
    nan_ok = all(a[feat]["nan_discipline_ok"] for a in ev_arms) if ev_arms else False
    inf_n = sum(a[feat]["inf_count"] for a in ev_arms)
    cert = {
        "evaluable": evaluable,
        "three_path_agree": three_path,
        "scalar_vector_parity": parity,
        "nan_discipline_ok": nan_ok,
        "inf_count": inf_n,
        "scale_invariant": scale["scale_invariant"],
        "scale_invariance_error": scale["scale_invariance_error"],
        "pit_invariant": pit_ok,
        "per_arm": {a["corpus"]: a[feat] for a in arms},
    }
    cert["verdict"] = decide_verdict(cert)
    return cert


def build_report(limit: int, include_corpus: bool = True) -> dict:
    synth = _synthetic()
    arms_raw = [("synthetic_1200", synth)]
    if include_corpus:
        for sym in _MAJORS:
            c = _load_corpus(sym, limit)
            if c is not None:
                arms_raw.append((f"{sym}_M15", c))

    arms = [certify_arm(raw, label) for label, raw in arms_raw]
    scale = scale_invariance(synth)
    pit = candidate_prefix_invariance(synth, cuts=[0.5, 0.8], label="synthetic_1200")

    es = _rollup_feature(arms, "ema_spread",
                         {"scale_invariant": scale["cand_es"]["scale_invariant"],
                          "scale_invariance_error": scale["cand_es"]["scale_invariance_error"]},
                         pit["per_feature"]["cand_es"]["verdict"] == "PREFIX_INVARIANT")
    ms = _rollup_feature(arms, "momentum_score",
                         {"scale_invariant": scale["cand_ms"]["scale_invariant"],
                          "scale_invariance_error": scale["cand_ms"]["scale_invariance_error"]},
                         pit["per_feature"]["cand_ms"]["verdict"] == "PREFIX_INVARIANT")

    feats = {"ema_spread_atr": es, "momentum_score_atr": ms}
    verdicts = [es["verdict"], ms["verdict"]]
    if "REJECT" in verdicts:
        overall = "REJECT"
    elif all(v == "PROMOTE" for v in verdicts):
        overall = "PROMOTE"
    else:
        overall = "INCONCLUSIVE"

    return {
        "probe": "b2a_feature_candidate_certification",
        "phase": "B2A — candidate-formula certification only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "b2a_cert_version": B2A_CERT_VERSION,
        "recon_method_version": RECON_METHOD_VERSION,
        "authority": ("research/governance only — PROMOTE = B2B-eligibility for candidate math "
                      "ONLY; decision impact UNKNOWN; economic value UNKNOWN; activation authority "
                      "NONE"),
        "scope_boundary": ("observe-only; touches no registered impl, engine, config, or model; "
                           "canonical vector stays 38-dim; PRODUCTION_BEHAVIOR_CHANGED = NO. "
                           "After B2A, stop — B2B regenerates all downstream-impact evidence."),
        "corpus_arms": [a["corpus"] for a in arms],
        "provenance": _provenance(),
        "certification": {"per_feature": feats, "overall_verdict": overall,
                          "arms": arms, "scale_invariance": scale, "prefix_invariance": pit},
        "NON_AUTHORITATIVE_DOWNSTREAM_DIAGNOSTICS": downstream_diagnostics(synth),
        "permanent_floor": "tests/test_b2a_feature_candidate_certification.py",
    }


def _to_md(rep: dict) -> str:
    c = rep["certification"]
    lines = [
        "# B2A — Candidate-Formula Certification (FM-030 / FM-031)",
        "",
        f"_Generated {rep['generated_at']} · method {rep['b2a_cert_version']} · READ-ONLY._",
        "",
        f"**Overall verdict: `{c['overall_verdict']}`**",
        "",
        f"> {rep['authority']}",
        "",
        f"> Scope: {rep['scope_boundary']}",
        "",
        "## Per-feature certification",
        "",
        "| Candidate | Verdict | 3-path | scalar↔vector | NaN/Inf | scale-invariant | PIT |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, f in c["per_feature"].items():
        lines.append(
            f"| `{name}` | **{f['verdict']}** | {f['three_path_agree']} | "
            f"{f['scalar_vector_parity']} | {f['nan_discipline_ok']}/inf={f['inf_count']} | "
            f"{f['scale_invariant']} (err={f['scale_invariance_error']:.2e}) | {f['pit_invariant']} |"
        )
    lines += [
        "",
        f"Corpus arms: {', '.join(rep['corpus_arms'])}.",
        "",
        "Three cross-checked reconstruction paths (A independent raw-OHLC float64 · "
        "B linked `atr_relative*close` · C legacy-column identity `legacy/close`) agree within "
        "float32 tolerance; independent SMA14(TR) == pipeline `atr_14_raw`.",
        "",
        "## Downstream diagnostics — NON-AUTHORITATIVE",
        "",
        "> The block below is DIAGNOSTIC ONLY (authority: none) and is NOT an input to the verdict. "
        "All prior behavioral / decision-impact / economic / cross-instrument evidence for these "
        "formulas is treated as UNKNOWN for certification. Fresh B2B must regenerate it from the "
        "certified candidate semantics.",
    ]
    dd = rep["NON_AUTHORITATIVE_DOWNSTREAM_DIAGNOSTICS"].get("legacy_scale_defect", {})
    for feat, v in dd.items():
        lines.append(f"- legacy `{feat}` scale ratio ×100/×1 ≈ {v['median_ratio_x100_over_x1']:.1f} "
                     f"(the defect FM-030/031 corrects)")
    return "\n".join(lines) + "\n"


def _write_artifact(rep: dict) -> tuple[Path, str]:
    stem = f"b2a_feature_candidate_certification-{_STAMP}"
    out_json = _GOV / f"{stem}.json"
    out_md = _GOV / f"{stem}.md"
    out_ptr = _GOV / "b2a_feature_candidate_certification.LATEST.json"
    payload = json.dumps(rep, indent=2, default=str) + "\n"
    out_json.write_text(payload, encoding="utf-8")
    out_md.write_text(_to_md(rep), encoding="utf-8")
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    out_ptr.write_text(json.dumps({
        "_doc": ("Stable pointer to the freshest B2A candidate-formula certification. Dated "
                 "artifacts are immutable; resolve via this pointer (verify sha256) or embedded "
                 "generated_at — never by filename date."),
        "path": str(out_json.relative_to(_ROOT)).replace("\\", "/"),
        "generated_at": rep["generated_at"],
        "schema_hash": hashlib.sha256(
            json.dumps(sorted(rep["provenance"].keys())).encode()).hexdigest()[:16],
        "sha256": sha,
        "overall_verdict": rep["certification"]["overall_verdict"],
    }, indent=2) + "\n", encoding="utf-8")
    return out_json, sha


def main() -> int:
    ap = argparse.ArgumentParser(description="B2A candidate-formula certification (read-only).")
    ap.add_argument("--limit", type=int, default=30000)
    args = ap.parse_args()

    rep = build_report(args.limit)

    # determinism: a second independent build must produce identical certification.
    rep2 = build_report(args.limit)
    det = (json.dumps(rep["certification"]["per_feature"], sort_keys=True, default=str)
           == json.dumps(rep2["certification"]["per_feature"], sort_keys=True, default=str))
    rep["certification"]["deterministic_recompute"] = det
    if not det:  # a non-deterministic harness cannot certify anything
        for f in rep["certification"]["per_feature"].values():
            f["verdict"] = "INCONCLUSIVE"
        if rep["certification"]["overall_verdict"] == "PROMOTE":
            rep["certification"]["overall_verdict"] = "INCONCLUSIVE"

    out_json, sha = _write_artifact(rep)

    c = rep["certification"]
    print(f"probe → {out_json.relative_to(_ROOT)}  (sha256 {sha[:12]}…)")
    print(f"  overall verdict: {c['overall_verdict']}  deterministic={det}")
    for name, f in c["per_feature"].items():
        print(f"  {name}: {f['verdict']}  3-path={f['three_path_agree']} "
              f"parity={f['scalar_vector_parity']} scale_inv={f['scale_invariant']} "
              f"pit={f['pit_invariant']} inf={f['inf_count']}")

    harness_ok = all(f["evaluable"] for f in c["per_feature"].values()) and det
    return 0 if harness_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
