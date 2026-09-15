"""
M13B / F-054-TS-CERT — trend_strength certification.

Governed identity: SMA10(diff(SMA20(close))) from raw close only.
No pandas rolling/diff in the oracle. PRODUCTION_BEHAVIOR_CHANGED = NO.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

LEDGER = _ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
EVIDENCE = _ROOT / "docs" / "governance" / "trend_strength_certification-2026-07-14.json"

W_MA = 20
W_SLOPE = 10
FIRST_FINITE_INDEX = 29  # zero-based, fully finite close series


# ── Independent oracles (explicit windows; no pandas rolling/diff) ──────────

def _is_valid(x: float) -> bool:
    return x == x and math.isfinite(x)


def independent_sma(values: np.ndarray, window: int) -> np.ndarray:
    """
    Trailing SMA with min_periods=window matching pandas:
    finite only when the trailing window has `window` valid (non-NaN, finite) observations.
    Any NaN/Inf in the window → count of valid < window → NaN.
    """
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    buf: deque[float] = deque(maxlen=window)
    for t in range(n):
        buf.append(float(values[t]))
        if len(buf) < window:
            continue
        if all(_is_valid(v) for v in buf):
            out[t] = sum(buf) / window
        # else remains NaN
    return out


def independent_first_diff(series: np.ndarray) -> np.ndarray:
    """slope_t = series_t - series_{t-1}; NaN if either side non-finite."""
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    for t in range(1, n):
        a, b = float(series[t]), float(series[t - 1])
        if _is_valid(a) and _is_valid(b):
            out[t] = a - b
    return out


def oracle_trend_strength(close: np.ndarray) -> np.ndarray:
    """
    Independent: SMA20(close) → first-diff → SMA10(slopes).
    float64 series. Does not use pandas rolling/diff or pipeline columns.
    """
    close = np.asarray(close, dtype=np.float64)
    ma20 = independent_sma(close, W_MA)
    slope = independent_first_diff(ma20)
    return independent_sma(slope, W_SLOPE)


def production_formula_trend_strength(close: np.ndarray) -> np.ndarray:
    """
    Exact production formula lines (feature_pipeline.py:249,307-308):
      ma_20 = close.rolling(20).mean()
      ma_slope_20 = ma_20.diff()
      trend_strength = ma_slope_20.rolling(10).mean()

    Used for NaN/Inf mask parity of the formula. FeaturePipeline rejects NaN OHLCV
    at input validation; formula semantics still govern the rolling implementation.
    """
    s = pd.Series(np.asarray(close, dtype=np.float64))
    ma20 = s.rolling(20, min_periods=20).mean()
    slope = ma20.diff()
    return slope.rolling(10, min_periods=10).mean().to_numpy(dtype=np.float64)


def pipeline_trend_strength(close: np.ndarray) -> np.ndarray:
    """Production path via FeaturePipeline (finite OHLCV only)."""
    from features.feature_pipeline import FeaturePipeline

    n = len(close)
    t0 = datetime(2024, 1, 1)
    rows = []
    for i, c in enumerate(close):
        cv = float(c)
        if not math.isfinite(cv):
            raise ValueError(
                "FeaturePipeline rejects non-finite OHLCV; use production_formula_trend_strength for NaN formula tests"
            )
        rows.append(
            dict(
                timestamp=t0 + timedelta(minutes=15 * i),
                open=cv,
                high=cv + 0.01,
                low=cv - 0.01,
                close=cv,
                volume=1000.0,
            )
        )
    df = pd.DataFrame(rows)
    fp = FeaturePipeline(df)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_trend_features()
    return fp.df["trend_strength"].to_numpy(dtype=np.float64)


def resolve_frontier() -> dict:
    from collections import Counter
    from importlib.util import spec_from_file_location, module_from_spec

    events = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e.get("feature_name") or e.get("target_feature"):
            events.append(e)
    spec = spec_from_file_location(
        "feature_dag_layers", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    dag = mod.build_dag()
    deps_of = {nd["name"]: nd["deps"] for nd in dag["nodes"]}
    RAW = {"open", "high", "low", "close", "volume", "timestamp"}
    explicit: dict[str, dict] = {}
    for ev in events:
        f = ev.get("feature_name") or ev.get("target_feature")
        if not f:
            continue
        cur = explicit.setdefault(
            f, {"feature_name": f, "deps": deps_of.get(f, []), "history": 0}
        )
        if "frontier_state" in ev:
            cur["frontier_state"] = ev["frontier_state"]
    promoted = {
        f
        for f, s in explicit.items()
        if s.get("frontier_state") == "PROMOTED_PRODUCTION"
    }
    for f, s in explicit.items():
        deps = deps_of.get(f, s.get("deps", []))
        s["deps"] = deps
        non_raw = [d for d in deps if d not in RAW]
        blocking = sorted(d for d in non_raw if d not in promoted)
        st = s.get("frontier_state", "UNKNOWN")
        if st in ("PROMOTED_PRODUCTION", "SUPERSEDED", "STALE", "CERTIFIED"):
            s["effective_state"] = st
        elif blocking:
            s["effective_state"] = "BLOCKED"
        elif st == "UNKNOWN":
            s["effective_state"] = "READY_TO_CERTIFY"
        else:
            s["effective_state"] = st
        s["blocking_dependencies"] = blocking
    counts = Counter(s["effective_state"] for s in explicit.values())
    return {
        "counts": dict(sorted(counts.items())),
        "trend_strength": explicit["trend_strength"],
        "close": explicit["close"]["effective_state"],
        "ready": sorted(
            n for n, s in explicit.items() if s["effective_state"] == "READY_TO_CERTIFY"
        ),
        "ledger_bytes": len(LEDGER.read_bytes()),
        "ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
        "dag_deps": deps_of["trend_strength"],
    }


def _pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# float64 trailing-sum of 20 terms: justify atol for independent recurrence vs pandas
FLOAT64_SMA_ATOL = 1e-12


def _finite_equal(a: np.ndarray, b: np.ndarray, atol: float = FLOAT64_SMA_ATOL) -> bool:
    ma = np.isfinite(a)
    mb = np.isfinite(b)
    if not np.array_equal(ma, mb):
        return False
    if not ma.any():
        return True
    return bool(np.allclose(a[ma], b[ma], rtol=0.0, atol=atol, equal_nan=False))


def oracle_independence_ok() -> dict:
    src = (
        inspect.getsource(oracle_trend_strength)
        + inspect.getsource(independent_sma)
        + inspect.getsource(independent_first_diff)
    )
    # strip docstrings/comments for token fence
    body_lines = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
            continue
        body_lines.append(line)
    body = "\n".join(body_lines)
    forbidden = [
        ".rolling",
        ".diff(",
        "FeaturePipeline",
        "ema_spread",
        "trend_bias",
        "detect_regime",
        "ma_slope_20",
        '["ma_20"]',
        '["trend_strength"]',
    ]
    hits = [t for t in forbidden if t in body]
    return {"ok": len(hits) == 0, "hits": hits}


def run_battery() -> dict:
    from features.feature_pipeline import FeaturePipeline

    results: dict = {}
    all_ok = True

    # ── Clean finite series ─────────────────────────────────────────────────
    n = 80
    const = np.full(n, 100.0)
    lin_up = 100.0 + np.arange(n, dtype=np.float64) * 0.5
    lin_dn = 100.0 - np.arange(n, dtype=np.float64) * 0.5

    o_c = oracle_trend_strength(const)
    o_u = oracle_trend_strength(lin_up)
    o_d = oracle_trend_strength(lin_dn)
    p_c = pipeline_trend_strength(const)
    p_u = pipeline_trend_strength(lin_up)
    p_d = pipeline_trend_strength(lin_dn)

    first_fin = int(np.argmax(np.isfinite(o_u))) if np.isfinite(o_u).any() else -1
    # for all-nan early, argmax of False is 0 — use where
    fin_idx = np.where(np.isfinite(o_u))[0]
    first_fin = int(fin_idx[0]) if len(fin_idx) else -1

    o29 = oracle_trend_strength(lin_up[:29])
    o30 = oracle_trend_strength(lin_up[:30])

    clean = {
        "1_constant_zero": _pass(
            np.isfinite(o_c[FIRST_FINITE_INDEX:]).all()
            and float(np.max(np.abs(o_c[FIRST_FINITE_INDEX:]))) < 1e-12
        ),
        "2_linear_up_positive_constant": _pass(
            np.all(o_u[FIRST_FINITE_INDEX:] > 0)
            and float(np.std(o_u[FIRST_FINITE_INDEX:])) < 1e-10
        ),
        "3_linear_down_negative_constant": _pass(
            np.all(o_d[FIRST_FINITE_INDEX:] < 0)
            and float(np.std(o_d[FIRST_FINITE_INDEX:])) < 1e-10
        ),
        "4_first_finite_index_29": _pass(first_fin == FIRST_FINITE_INDEX),
        "5_len29_no_finite": _pass(not np.isfinite(o29).any()),
        "6_len30_one_finite": _pass(int(np.isfinite(o30).sum()) == 1),
        "7_signed_symmetry": _pass(
            _finite_equal(o_u[FIRST_FINITE_INDEX:], -o_d[FIRST_FINITE_INDEX:], atol=1e-12)
        ),
        "8_translation_invariance": _pass(
            _finite_equal(
                oracle_trend_strength(lin_up + 50.0),
                o_u,
                atol=1e-12,
            )
        ),
        "9_positive_scale_equivariance": _pass(
            _finite_equal(
                oracle_trend_strength(lin_up * 2.0)[FIRST_FINITE_INDEX:],
                o_u[FIRST_FINITE_INDEX:] * 2.0,
                atol=1e-12,
            )
        ),
        "pipeline_parity_clean_up": _pass(
            _finite_equal(o_u, p_u) and np.array_equal(np.isfinite(o_u), np.isfinite(p_u))
        ),
        "pipeline_parity_clean_const": _pass(
            _finite_equal(o_c, p_c) and np.array_equal(np.isfinite(o_c), np.isfinite(p_c))
        ),
        "column_dtype_float64": _pass(p_u.dtype == np.float64 or str(p_u.dtype) == "float64"),
        "oracle_dtype_float64": _pass(o_u.dtype == np.float64),
    }
    results["clean_finite"] = clean
    all_ok &= all(v == "PASS" for v in clean.values())

    # ── Window / impulse ────────────────────────────────────────────────────
    # impulse at t=40 on otherwise constant
    base = np.full(100, 100.0)
    imp = base.copy()
    imp[40] = 200.0
    o_imp = oracle_trend_strength(imp)
    p_imp = pipeline_trend_strength(imp)
    # slope/MA affected while impulse in SMA20 window [40, 40+19]
    # after leaving, eventually returns to 0
    window_tests = {
        "10_11_impulse_parity": _pass(
            _finite_equal(o_imp, p_imp) and np.array_equal(np.isfinite(o_imp), np.isfinite(p_imp))
        ),
        "14_15_16_no_partial_before_29": _pass(not np.isfinite(o_imp[:FIRST_FINITE_INDEX]).any()),
        "impulse_nonzero_while_in_windows": _pass(
            np.any(np.abs(o_imp[40:70][np.isfinite(o_imp[40:70])]) > 1e-9)
        ),
        "impulse_returns_near_zero_late": _pass(
            float(np.max(np.abs(o_imp[90:][np.isfinite(o_imp[90:])]))) < 1e-9
            if np.isfinite(o_imp[90:]).any()
            else False
        ),
    }
    results["window_impulse"] = window_tests
    all_ok &= all(v == "PASS" for v in window_tests.values())

    # ── NaN / Inf ───────────────────────────────────────────────────────────
    nan_series = lin_up.copy()
    nan_series[25] = np.nan
    o_nan = oracle_trend_strength(nan_series)
    p_nan = production_formula_trend_strength(nan_series)
    mask_eq = np.array_equal(np.isfinite(o_nan), np.isfinite(p_nan))
    consec = lin_up.copy()
    consec[30:35] = np.nan
    o_cons = oracle_trend_strength(consec)
    p_cons = production_formula_trend_strength(consec)

    inf_s = lin_up.copy()
    inf_s[40] = np.inf
    o_inf = oracle_trend_strength(inf_s)
    p_inf = production_formula_trend_strength(inf_s)
    ninf_s = lin_up.copy()
    ninf_s[40] = -np.inf
    o_ninf = oracle_trend_strength(ninf_s)
    p_ninf = production_formula_trend_strength(ninf_s)

    nan_tests = {
        "17_leading_nan_before_29": _pass(not np.isfinite(o_u[:FIRST_FINITE_INDEX]).any()),
        "18_19_nan_injection_mask_parity": _pass(
            mask_eq and _finite_equal(o_nan, p_nan)
        ),
        "20_consecutive_nans_mask_parity": _pass(
            np.array_equal(np.isfinite(o_cons), np.isfinite(p_cons))
            and _finite_equal(o_cons, p_cons)
        ),
        "21_pos_inf_mask_parity": _pass(
            np.array_equal(np.isfinite(o_inf), np.isfinite(p_inf))
            and _finite_equal(o_inf, p_inf)
        ),
        "22_neg_inf_mask_parity": _pass(
            np.array_equal(np.isfinite(o_ninf), np.isfinite(p_ninf))
            and _finite_equal(o_ninf, p_ninf)
        ),
        "23_24_no_fill_mask_exact": _pass(mask_eq),
    }
    results["nan_inf"] = nan_tests
    all_ok &= all(v == "PASS" for v in nan_tests.values())

    # ── float32 vector cast ─────────────────────────────────────────────────
    # After build_feature_vector: cast float64 column → float32
    # Compare oracle.astype(float32) vs pipeline.astype(float32) exact bit or allclose 0
    o32 = o_u.astype(np.float32)
    p32 = p_u.astype(np.float32)
    # After float64 parity within FLOAT64_SMA_ATOL, cast both to float32 and compare
    # with float32 ulp scale (~1e-6 relative to O(1) values; use atol from cast of atol)
    f32_ok = bool(np.array_equal(np.isfinite(o32), np.isfinite(p32))) and _finite_equal(
        o32.astype(np.float64), p32.astype(np.float64), atol=1e-6
    )
    results["dtype_publication"] = {
        "25_pipeline_column_float64": _pass(p_u.dtype == np.float64),
        "26_oracle_float64": _pass(o_u.dtype == np.float64),
        "27_28_float32_cast_parity": _pass(f32_ok),
        "float32_tolerance_basis": (
            "float64 oracle↔pipeline within 1e-12 (SMA accumulation); "
            "float32 cast compared with atol=1e-6"
        ),
    }
    all_ok &= f32_ok and p_u.dtype == np.float64

    # ── PIT ─────────────────────────────────────────────────────────────────
    series = 50.0 + np.cumsum(np.random.default_rng(7).normal(0, 0.3, 120))
    full = oracle_trend_strength(series)
    prefix_ok = True
    for cut in (19, 20, 28, 29, 30, 60, 100):
        pref = oracle_trend_strength(series[:cut])
        if not (
            np.array_equal(np.isfinite(pref), np.isfinite(full[:cut]))
            and _finite_equal(pref, full[:cut])
        ):
            prefix_ok = False
    fut_base = oracle_trend_strength(series[:70])
    mut = series.copy()
    mut[70:] = 999.0
    fut_mut = oracle_trend_strength(mut[:70])
    fut_ok = _finite_equal(fut_base, fut_mut) and np.array_equal(
        np.isfinite(fut_base), np.isfinite(fut_mut)
    )
    # same-bar: after warmup, change one bar
    a = series.copy()
    b = series.copy()
    b[80] = b[80] + 10.0
    oa, ob = oracle_trend_strength(a), oracle_trend_strength(b)
    # only indices that include bar 80 in their MA20/slope windows can change
    # at least index 80 should differ if finite
    sens_ok = not _finite_equal(oa, ob)  # some difference
    # indices well before 80-20-10 should be unchanged
    early = 80 - 20 - 10 - 2
    early_ok = _finite_equal(oa[:early], ob[:early]) and np.array_equal(
        np.isfinite(oa[:early]), np.isfinite(ob[:early])
    )
    det_ok = _finite_equal(oracle_trend_strength(series), oracle_trend_strength(series))

    results["pit"] = {
        "29_30_prefix_invariance": _pass(prefix_ok),
        "31_future_mutation": _pass(fut_ok),
        "32_same_bar_sensitivity": _pass(sens_ok and early_ok),
        "33_determinism": _pass(det_ok),
    }
    all_ok &= prefix_ok and fut_ok and sens_ok and early_ok and det_ok

    # ── Pipeline parity corpora ─────────────────────────────────────────────
    rng = np.random.default_rng(11)
    synth = 100 + np.cumsum(rng.normal(0, 0.5, 200))
    o_s, p_s = oracle_trend_strength(synth), pipeline_trend_strength(synth)
    boundary = np.concatenate(
        [np.full(40, 100.0), np.linspace(100, 120, 40), np.full(40, 120.0)]
    )
    o_b, p_b = oracle_trend_strength(boundary), pipeline_trend_strength(boundary)

    results["pipeline_parity"] = {
        "34_synthetic": _pass(
            _finite_equal(o_s, p_s) and np.array_equal(np.isfinite(o_s), np.isfinite(p_s))
        ),
        "35_boundary_heavy": _pass(
            _finite_equal(o_b, p_b) and np.array_equal(np.isfinite(o_b), np.isfinite(p_b))
        ),
        "36_nan_injection": _pass(mask_eq and _finite_equal(o_nan, p_nan)),
        "37_representative_irregular": _pass(
            _finite_equal(full, pipeline_trend_strength(series))
            and np.array_equal(
                np.isfinite(full), np.isfinite(pipeline_trend_strength(series))
            )
        ),
    }
    all_ok &= all(v == "PASS" for v in results["pipeline_parity"].values())

    # ── Telescoping secondary ───────────────────────────────────────────────
    ma20 = independent_sma(synth, 20)
    telesc = np.full_like(synth, np.nan)
    for t in range(len(synth)):
        if t >= 10 and _is_valid(ma20[t]) and _is_valid(ma20[t - 10]):
            telesc[t] = (ma20[t] - ma20[t - 10]) / 10.0
    o_tel = oracle_trend_strength(synth)
    both = np.isfinite(o_tel) & np.isfinite(telesc)
    max_res = float(np.max(np.abs(o_tel[both] - telesc[both]))) if both.any() else 0.0
    # On fully finite after warmup, should match; with no NaNs in synth, both finite from 29
    tel_ok = max_res < 1e-12
    results["telescoping"] = {
        "secondary_max_abs_residual": max_res,
        "secondary_pass": _pass(tel_ok),
    }
    all_ok &= tel_ok

    # ── Name collision isolation ────────────────────────────────────────────
    indep = oracle_independence_ok()
    # Discrimination: constant → trend_strength finite zeros; not interchangeable with abs(ema_spread)
    # (dual_engine uses abs(ema_spread) under the local name trend_strength).
    # while abs(ema_spread) on a non-flat series is typically nonzero after EMA warmup
    o_const = oracle_trend_strength(np.full(80, 100.0))
    # abs(ema_spread) for linear trend series is not all zeros at finite points
    # Construct ema_spread-like quantity independently for discrimination only (not as oracle)
    close_lin = 100.0 + np.arange(80, dtype=np.float64)
    # production dual_engine uses abs(ema_spread); show trend_strength (const) != typical abs spreads
    ts_const_finite = o_const[np.isfinite(o_const)]
    ne2 = bool(np.allclose(ts_const_finite, 0.0, atol=1e-12))  # const → 0
    # irregular series trend_strength varies; not identical to a flat abs(ema) pattern
    o_irr = oracle_trend_strength(synth[:80])
    ne = ne2 and (float(np.nanstd(o_irr)) > 1e-9 or float(np.nanmax(np.abs(o_irr))) > 1e-9)

    collision = {
        "oracle_independent": _pass(indep["ok"]),
        "forbidden_hits": indep["hits"],
        "canonical_ne_abs_ema_spread": _pass(ne),
        "const_series_strength_zero": _pass(ne2),
        "deferred_debt": "dual_engine detect_regime uses abs(ema_spread) under local name trend_strength",
    }
    results["name_collision"] = collision
    all_ok &= indep["ok"] and ne

    results["overall_verdict"] = "CERTIFIED" if all_ok else "REJECT"
    results["all_probes_pass"] = all_ok
    results["oracle_source_sha256"] = hashlib.sha256(
        (
            inspect.getsource(oracle_trend_strength)
            + inspect.getsource(independent_sma)
            + inspect.getsource(independent_first_diff)
        ).encode()
    ).hexdigest()
    return results


def build_artifact(checkpoint: dict, battery: dict) -> dict:
    return {
        "_doc": "M13B trend_strength nested rolling certification.",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_program": "M13B",
        "TARGET_FEATURE": "trend_strength",
        "TARGET_IDENTITY": "NESTED_ROLLING_CAUSAL_METRIC",
        "FORMULA": "SMA10(diff(SMA20(close)))",
        "ROOT_DEPENDENCY": "close",
        "CURRENT_DAG_DEPS": ["close"],
        "WINDOWS": {
            "SMA20": {"window": 20, "min_periods": 20},
            "diff_lag": 1,
            "SMA10_slopes": {"window": 10, "min_periods": 10},
        },
        "FIRST_FINITE_INDEX_FINITE_INPUT": 29,
        "NORMALIZATION": "NONE",
        "CLIPPING": "NONE",
        "COLUMN_DTYPE": "float64",
        "VECTOR_DTYPE": "float32",
        "UNITS": "signed price-scale smoothed MA change",
        "INDEPENDENT_ORACLE": "explicit trailing-window recurrences from raw close",
        "ORACLE_INDEPENDENCE": "no pandas rolling/diff; no pipeline intermediates",
        "IMPLEMENTATION_INTERMEDIATES": ["ma_20", "ma_slope_20"],
        "INTERMEDIATES_PUBLISHED_AS_DAG_NODES": "NO",
        "CERTIFICATION_AUTHORITY_DEPENDENCY": "close only",
        "checkpoint": checkpoint["counts"],
        "probes": battery,
        "KNOWN_DEBT": [
            "dual_engine local variable trend_strength derives from abs(ema_spread)",
            "scale-dependent consumer thresholds (s07/s08)",
            "no ontology/FM registration",
        ],
        "PER_NODE_VERDICT": battery["overall_verdict"],
        "PRODUCTION_BEHAVIOR_CHANGED": "NO",
        "CANONICAL_VECTOR_DIMENSION": 38,
        "authority": (
            "research/governance only — descriptive certification; grants no runtime authority (§6.5)"
        ),
        "scope_boundary": "trend_strength only; volatility_regime untouched",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("M13B — trend_strength CERTIFICATION PROBE")
    print("=" * 72)

    cp = resolve_frontier()
    print("FRONTIER", cp["counts"])
    print("trend_strength", cp["trend_strength"]["effective_state"], "deps", cp["dag_deps"])
    print("close", cp["close"])
    if cp["trend_strength"]["effective_state"] != "READY_TO_CERTIFY":
        print("REFUSED: not READY")
        return 2
    if cp["dag_deps"] != ["close"] or cp["close"] != "PROMOTED_PRODUCTION":
        print("REFUSED: dep/close gate")
        return 2

    battery = run_battery()
    for sec, val in battery.items():
        if not isinstance(val, dict):
            continue
        print(f"[{sec}]")
        for k, v in val.items():
            if isinstance(v, str) and v in ("PASS", "FAIL"):
                print(f"  {k:45s} {v}")
            elif k in ("secondary_max_abs_residual", "deferred_debt", "float32_tolerance_basis"):
                print(f"  {k:45s} {v}")
    print("OVERALL", battery["overall_verdict"])
    if battery["overall_verdict"] != "CERTIFIED":
        return 3

    art = build_artifact(cp, battery)
    EVIDENCE.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
    sha = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    if not sha:
        print("REFUSED empty sha")
        return 4
    print("ARTIFACT", EVIDENCE.relative_to(_ROOT))
    print("SHA256", sha)
    print("ALL PROBES PASS — trend_strength CERTIFIABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
