"""
M10 / F-054-RD — retest_depth GATED production composition certification probe.

TARGET_FEATURE = retest_depth
TARGET_IDENTITY = GATED_PRODUCTION_COMPOSITION
COMPONENT_FORMULA_IDENTITY = FM-021  (on-gate kernel only — NOT the full series)

PRODUCTION_BEHAVIOR_CHANGED = NO
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

LEDGER = _ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
EVIDENCE = _ROOT / "docs" / "governance" / "fm021_retest_depth_certification-2026-07-14.json"
GATE_WINDOW = 10
GATE_BAND = 1.0  # near_fast_ema: |close-ema| <= GATE_BAND * atr * close


# ── Independent oracles (no pandas rolling; no derived_math as sole path) ────

def oracle_kernel_independent(close: float, ema_fast: float, atr: float) -> float:
    """Independent FM-021 kernel (scalar arithmetic only)."""
    if atr > 0 and close > 0:
        val = abs(close - ema_fast) / (atr * close)
        return min(1.0, max(0.0, val))
    return 0.0


def oracle_near_fast_ema(close: float, ema_fast: float, atr: float) -> bool:
    """INCLUSIVE band: |close - ema_fast| <= 1.0 * atr * close (pinned from pipeline)."""
    return abs(close - ema_fast) <= (GATE_BAND * atr * close)


def oracle_recent_sweep_online(liquidity_sweep: np.ndarray) -> np.ndarray:
    """Causal trailing window: any sweep in [t-(W-1), t], W=10, min_periods=1."""
    n = len(liquidity_sweep)
    out = np.zeros(n, dtype=bool)
    buf: deque[bool] = deque(maxlen=GATE_WINDOW)
    for t in range(n):
        buf.append(bool(liquidity_sweep[t] != 0))
        out[t] = any(buf)
    return out


def oracle_retest_flag(
    close: np.ndarray,
    ema_fast: np.ndarray,
    atr: np.ndarray,
    liquidity_sweep: np.ndarray,
) -> np.ndarray:
    recent = oracle_recent_sweep_online(liquidity_sweep)
    near = np.array(
        [oracle_near_fast_ema(float(c), float(e), float(a)) for c, e, a in zip(close, ema_fast, atr)],
        dtype=bool,
    )
    return (recent & near).astype(np.int8)


def oracle_canonical_retest_depth(
    close: np.ndarray,
    ema_fast: np.ndarray,
    atr: np.ndarray,
    liquidity_sweep: np.ndarray,
) -> np.ndarray:
    """
    Exact production ordering (feature_pipeline.py:648-653):
      1. where(flag==1 & atr>0 & close>0, abs(c-e)/(atr*c), 0.0)
      2. astype(float32)
      3. clip[0,1]
      4. astype(float32)
    Gate uses independent online reconstruction (not pipeline retest_flag column).
    """
    flag = oracle_retest_flag(close, ema_fast, atr, liquidity_sweep)
    n = len(close)
    raw = np.zeros(n, dtype=np.float64)
    for t in range(n):
        if flag[t] == 1 and atr[t] > 0 and close[t] > 0:
            raw[t] = abs(close[t] - ema_fast[t]) / (atr[t] * close[t])
        else:
            raw[t] = 0.0
    step1 = raw.astype(np.float32)
    step2 = np.clip(step1, 0.0, 1.0).astype(np.float32)
    return step2


# ── Checkpoint ───────────────────────────────────────────────────────────────

def resolve_frontier() -> dict:
    from collections import Counter

    events = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e.get("feature_name") or e.get("target_feature"):
            events.append(e)
    # live DAG (authoritative after M10 dep correction)
    from importlib.util import spec_from_file_location, module_from_spec

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
        cur["history"] += 1
    promoted = {
        f
        for f, s in explicit.items()
        if s.get("frontier_state") == "PROMOTED_PRODUCTION"
    }
    for f, s in explicit.items():
        deps = deps_of.get(f, s.get("deps", []))
        s["deps"] = deps  # live DAG contract
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
    rd = explicit["retest_depth"]
    return {
        "counts": dict(sorted(counts.items())),
        "retest_depth": rd,
        "ready": sorted(
            n for n, s in explicit.items() if s["effective_state"] == "READY_TO_CERTIFY"
        ),
        "ledger_bytes": len(LEDGER.read_bytes()),
        "ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
        "dag_deps": deps_of["retest_depth"],
        "dag_node": next(nd for nd in dag["nodes"] if nd["name"] == "retest_depth"),
    }


# ── Corpora ──────────────────────────────────────────────────────────────────

def synthetic_boundary_corpus() -> dict[str, np.ndarray]:
    """Hand-crafted series exercising gate/kernel boundaries (length 40)."""
    n = 40
    close = np.full(n, 100.0, dtype=np.float64)
    ema = np.full(n, 100.0, dtype=np.float64)
    atr = np.full(n, 0.01, dtype=np.float64)  # atr*close = 1.0
    sweep = np.zeros(n, dtype=np.int8)

    # t=5: sweep; near EMA → active
    sweep[5] = 1
    close[5] = 100.5  # |0.5| <= 1.0
    # t=14: last bar where sweep@5 is still in window [5..14] (10 bars: 5..14)
    close[14] = 100.5
    # t=15: sweep@5 falls out of window [6..15] → inactive unless new sweep
    close[15] = 100.5
    # t=20: sweep + outside band
    sweep[20] = 1
    close[20] = 102.0  # |2| > 1.0 → inactive
    # t=21: no new sweep, inside band → inactive (sweep@20 was outside so flag false;
    #       but recent_sweep still true for 10 bars after 20 — near must hold)
    close[21] = 100.3  # near true, recent true → ACTIVE
    # t=25: kernel > 1 before clip (need flag on): force near with large atr temporarily
    # Use atr=0.05 so band=5; set close=106 → |6| > 5? band=5; close=104.9 near; kernel=4.9/5=0.98
    atr[25] = 0.05
    sweep[25] = 1
    close[25] = 104.9  # |4.9| <= 5.0 near; kernel = 4.9/(0.05*104.9) ≈ 0.934
    # t=26: kernel would be >1 if ungated: close far but we need flag — expand atr for near
    atr[26] = 0.1
    sweep[26] = 1
    close[26] = 109.0  # |9| <= 10 near; kernel = 9/(0.1*109) ≈ 0.825
    # t=27: exact boundary |c-e| == atr*c  (100 vs 99, atr=0.01 → 1.0 == 1.0)
    atr[27] = 0.01
    sweep[27] = 1
    close[27] = 100.0
    ema[27] = 99.0  # near inclusive TRUE; kernel = 1.0
    # t=28: immediately outside |c-e| > atr*c
    close[28] = 100.0
    ema[28] = 98.9  # |1.1| > 1.0
    atr[28] = 0.01
    sweep[28] = 1
    # t=30: atr==0, flag would need sweep+near — near with atr=0: |c-e|<=0 only if equal
    sweep[30] = 1
    atr[30] = 0.0
    close[30] = 100.0
    ema[30] = 100.0  # near True (0<=0); but atr>0 gate fails → 0.0
    # t=31: exact EMA touch with active gate
    sweep[31] = 1
    atr[31] = 0.01
    close[31] = 100.0
    ema[31] = 100.0  # kernel 0

    return {
        "close": close,
        "ema_fast": ema,
        "atr": atr,
        "liquidity_sweep": sweep,
    }


def pipeline_retest_depth_from_arrays(
    close: np.ndarray,
    ema_fast: np.ndarray,
    atr: np.ndarray,
    liquidity_sweep: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reproduce pipeline vectors with pandas (reference production path)."""
    df = pd.DataFrame(
        {
            "close": close,
            "ema_fast": ema_fast,
            "atr": atr,
            "liquidity_sweep": liquidity_sweep,
        }
    )
    recent_sweep = (
        (df["liquidity_sweep"] != 0)
        .rolling(window=GATE_WINDOW, min_periods=1)
        .max()
        .astype(bool)
    )
    near_fast_ema = (df["close"] - df["ema_fast"]).abs() <= (
        GATE_BAND * df["atr"] * df["close"]
    )
    flag = (recent_sweep & near_fast_ema).astype(np.int8)
    rd = np.where(
        (flag == 1) & (df["atr"] > 0) & (df["close"] > 0),
        (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
        0.0,
    ).astype(np.float32)
    rd = np.clip(rd, 0.0, 1.0).astype(np.float32)
    return flag.to_numpy(), rd


def representative_ohlcv(n: int = 600, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = datetime(2024, 1, 1)
    price = 100.0
    rows = []
    for i in range(n):
        o = price
        c = price + float(rng.normal(0, 0.25))
        h = max(o, c) + abs(float(rng.normal(0, 0.15)))
        l = min(o, c) - abs(float(rng.normal(0, 0.15)))
        rows.append(
            dict(
                timestamp=t0 + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000.0,
            )
        )
        price = c
    return pd.DataFrame(rows)


# ── Battery ──────────────────────────────────────────────────────────────────

def _pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_battery() -> dict:
    from features import derived_math as dm
    from features.feature_pipeline import FeaturePipeline

    results: dict = {}
    all_ok = True

    # ── Gate property tests on synthetic ────────────────────────────────────
    corp = synthetic_boundary_corpus()
    c, e, a, s = corp["close"], corp["ema_fast"], corp["atr"], corp["liquidity_sweep"]
    flag_o = oracle_retest_flag(c, e, a, s)
    recent = oracle_recent_sweep_online(s)
    rd_o = oracle_canonical_retest_depth(c, e, a, s)
    flag_p, rd_p = pipeline_retest_depth_from_arrays(c, e, a, s)

    # 1 no sweep ever (prefix before first sweep)
    ok1 = (not recent[0]) and (flag_o[0] == 0) and (rd_o[0] == 0.0)
    # 2 sweep on current + near
    ok2 = flag_o[5] == 1
    # 3 sweep at t-9 relative: index 5 active at 14 (lag 9)
    ok3 = flag_o[14] == 1 and recent[14]
    # 4 sweep at t-10 relative: index 5 inactive at 15 (lag 10)
    ok4 = (not recent[15]) and flag_o[15] == 0
    # 5 recent sweep + outside EMA → inactive at t=20
    ok5 = flag_o[20] == 0 and recent[20]
    # 6 no recent + inside → inactive at t=0
    ok6 = flag_o[0] == 0 and oracle_near_fast_ema(float(c[0]), float(e[0]), float(a[0]))
    # 7/8 consecutive + separated covered by reconstruction match
    ok78 = bool(np.array_equal(flag_o, flag_p))
    # 9 exact boundary inclusive: |c-e| == atr*c → near TRUE
    ok9 = (
        flag_o[27] == 1
        and abs(abs(c[27] - e[27]) - (GATE_BAND * a[27] * c[27])) < 1e-12
    )
    # 10 immediately outside
    ok10 = flag_o[28] == 0

    gate_props = {
        "1_no_sweep_zero": _pass(ok1),
        "2_sweep_current_near_active": _pass(ok2),
        "3_sweep_lag9_active": _pass(ok3),
        "4_sweep_lag10_inactive": _pass(ok4),
        "5_recent_outside_inactive": _pass(ok5),
        "6_no_recent_inside_inactive": _pass(ok6),
        "7_8_recon_match_pipeline_flag": _pass(ok78),
        "9_exact_boundary_inclusive": _pass(ok9),
        "10_outside_boundary_inactive": _pass(ok10),
    }
    results["gate_semantics"] = gate_props
    all_ok &= all(v == "PASS" for v in gate_props.values())

    # ── Kernel semantics ────────────────────────────────────────────────────
    k_touch = oracle_kernel_independent(100.0, 100.0, 0.01)
    k_one = oracle_kernel_independent(100.0, 99.0, 0.01)  # |1|/(0.01*100)=1
    # >1 before clip: |close-ema|/(atr*close) = 3/(0.01*100)=3 → clip 1
    k_gt = oracle_kernel_independent(103.0, 100.0, 0.01)
    k_atr0 = oracle_kernel_independent(100.0, 99.0, 0.0)
    k_atr_neg = oracle_kernel_independent(100.0, 99.0, -1.0)
    k_close0 = oracle_kernel_independent(0.0, 0.0, 0.01)
    k_close_neg = oracle_kernel_independent(-1.0, 0.0, 0.01)
    # NaN paths AS-WIRED: match derived_math
    nan_ok = True
    for triple in [
        (float("nan"), 100.0, 0.01),
        (100.0, float("nan"), 0.01),
        (100.0, 99.0, float("nan")),
    ]:
        o = oracle_kernel_independent(*triple)
        d = dm.retest_depth(*triple)
        if math.isnan(o) or math.isnan(d):
            nan_ok &= math.isnan(o) and math.isnan(d)
        else:
            nan_ok &= abs(o - d) < 1e-12

    kernel_props = {
        "11_exact_ema_touch_zero": _pass(k_touch == 0.0),
        "12_kernel_exactly_1": _pass(abs(k_one - 1.0) < 1e-12),
        "13_kernel_gt1_clips_to_1": _pass(k_gt == 1.0),
        "14_atr_eq_0": _pass(k_atr0 == 0.0),
        "15_atr_lt_0": _pass(k_atr_neg == 0.0),
        "16_close_eq_0": _pass(k_close0 == 0.0),
        "17_close_lt_0": _pass(k_close_neg == 0.0),
        "18_19_20_nan_as_wired_parity": _pass(nan_ok),
        "component_vs_derived_math_active": _pass(
            all(
                abs(
                    oracle_kernel_independent(100 + i * 0.1, 100.0, 0.01)
                    - dm.retest_depth(100 + i * 0.1, 100.0, 0.01)
                )
                < 1e-12
                for i in range(15)
            )
        ),
    }
    results["kernel_semantics"] = kernel_props
    all_ok &= all(v == "PASS" for v in kernel_props.values())

    # ── Full emission ───────────────────────────────────────────────────────
    # 21 off-gate kernel>0 → 0
    # construct row: no sweep, close far from ema
    off_c = np.array([100.0, 105.0])
    off_e = np.array([100.0, 100.0])
    off_a = np.array([0.01, 0.01])
    off_s = np.array([0, 0], dtype=np.int8)
    off_rd = oracle_canonical_retest_depth(off_c, off_e, off_a, off_s)
    ungated = abs(105.0 - 100.0) / (0.01 * 105.0)
    ok21 = off_rd[1] == 0.0 and ungated > 0

    # 22 on-gate parity with FM-021
    on_mask = flag_o == 1
    ok22 = True
    for t in np.where(on_mask)[0]:
        k = oracle_kernel_independent(float(c[t]), float(e[t]), float(a[t]))
        if abs(float(rd_o[t]) - k) > 1e-5:  # float32
            ok22 = False

    # 24 domain
    ok24 = bool(np.all((rd_o >= 0.0) & (rd_o <= 1.0)))
    # 25 dtype
    ok25 = rd_o.dtype == np.float32
    # 26 no nan/inf on synthetic
    ok26 = bool(np.all(np.isfinite(rd_o)))
    # full series == pipeline reference
    ok33 = bool(np.allclose(rd_o, rd_p, rtol=0, atol=0))

    full_props = {
        "21_off_gate_zero_despite_kernel": _pass(ok21),
        "22_on_gate_fm021_parity": _pass(ok22),
        "23_off_gate_zero_contract": _pass(bool(np.all(rd_o[flag_o != 1] == 0.0))),
        "24_domain_01": _pass(ok24),
        "25_float32": _pass(ok25),
        "26_finite": _pass(ok26),
        "32_gate_parity_pipeline": _pass(ok78),
        "33_full_series_parity_pipeline_arrays": _pass(ok33),
    }
    results["full_emission"] = full_props
    all_ok &= all(v == "PASS" for v in full_props.values())

    # ── Temporal: prefix + future mutation + determinism ────────────────────
    n = len(c)
    cuts = [10, 20, 30]
    prefix_ok = True
    for cut in cuts:
        f1 = oracle_retest_flag(c[:cut], e[:cut], a[:cut], s[:cut])
        r1 = oracle_recent_sweep_online(s[:cut])
        d1 = oracle_canonical_retest_depth(c[:cut], e[:cut], a[:cut], s[:cut])
        if not (
            np.array_equal(f1, flag_o[:cut])
            and np.array_equal(r1, recent[:cut])
            and np.array_equal(d1, rd_o[:cut])
        ):
            prefix_ok = False

    fut_ok = True
    cut = 20
    base_d = oracle_canonical_retest_depth(c[: cut + 1], e[: cut + 1], a[: cut + 1], s[: cut + 1])
    c2, e2, a2, s2 = c.copy(), e.copy(), a.copy(), s.copy()
    c2[cut + 1 :] = 999.0
    s2[cut + 1 :] = 1
    mut_d = oracle_canonical_retest_depth(c2[: cut + 1], e2[: cut + 1], a2[: cut + 1], s2[: cut + 1])
    fut_ok = np.array_equal(base_d, mut_d)

    d_a = oracle_canonical_retest_depth(c, e, a, s)
    d_b = oracle_canonical_retest_depth(c, e, a, s)
    det_ok = np.array_equal(d_a, d_b)

    temporal = {
        "27_28_29_prefix_invariance": _pass(prefix_ok),
        "30_future_mutation": _pass(fut_ok),
        "31_determinism": _pass(det_ok),
    }
    results["temporal"] = temporal
    all_ok &= all(v == "PASS" for v in temporal.values())

    # ── Full FeaturePipeline pre-finalize parity (surviving rolling history) ─
    # Compare on the FULL frame after feature compute, BEFORE finalize() dropna.
    # Oracle reconstructed only from post-finalize rows would lose leading sweep
    # history and falsely break recent_sweep (not a production defect).
    df = representative_ohlcv()
    fp = FeaturePipeline(df)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_trend_features()
    fp.compute_volatility_regime()
    fp.compute_context()
    fp.compute_structure_liquidity()
    fp.compute_normalization()
    fp.compute_canonical_price_features()
    fp.compute_canonical_volatility_features()
    fp.compute_canonical_ema_features()
    fp.compute_canonical_trend_features()
    fp.compute_canonical_structure_features()
    fp.compute_canonical_temporal_features()
    full = fp.df
    need = ["close", "ema_fast", "atr", "liquidity_sweep", "retest_depth", "retest_flag"]
    missing = [k for k in need if k not in full.columns]
    if missing:
        results["pipeline_corpus"] = {"status": "FAIL", "missing": missing}
        all_ok = False
    else:
        # Restrict to rows with finite atr/close/ema (post-warmup comparable)
        finite = (
            np.isfinite(full["atr"].to_numpy(dtype=np.float64))
            & np.isfinite(full["close"].to_numpy(dtype=np.float64))
            & np.isfinite(full["ema_fast"].to_numpy(dtype=np.float64))
            & np.isfinite(full["retest_depth"].to_numpy(dtype=np.float64))
        )
        sub = full.loc[finite]
        cc = sub["close"].to_numpy(dtype=np.float64)
        ee = sub["ema_fast"].to_numpy(dtype=np.float64)
        aa = sub["atr"].to_numpy(dtype=np.float64)
        ss = sub["liquidity_sweep"].to_numpy()
        pipe_rd = sub["retest_depth"].to_numpy(dtype=np.float32)
        pipe_fl = sub["retest_flag"].to_numpy(dtype=np.int8)
        # Oracle must see FULL series history for rolling gate, then index into finite mask
        cc_f = full["close"].to_numpy(dtype=np.float64)
        ee_f = full["ema_fast"].to_numpy(dtype=np.float64)
        aa_f = full["atr"].to_numpy(dtype=np.float64)
        ss_f = full["liquidity_sweep"].to_numpy()
        # NaN atr/close: oracle treats atr>0 close>0 gate; match production on finite subset
        ora_rd_full = oracle_canonical_retest_depth(
            np.nan_to_num(cc_f, nan=0.0),
            np.nan_to_num(ee_f, nan=0.0),
            np.nan_to_num(aa_f, nan=0.0),
            np.nan_to_num(ss_f, nan=0).astype(np.int8),
        )
        ora_fl_full = oracle_retest_flag(
            np.nan_to_num(cc_f, nan=0.0),
            np.nan_to_num(ee_f, nan=0.0),
            np.nan_to_num(aa_f, nan=0.0),
            np.nan_to_num(ss_f, nan=0).astype(np.int8),
        )
        ora_rd = ora_rd_full[finite]
        ora_fl = ora_fl_full[finite]
        gate_eq = bool(np.array_equal(ora_fl, pipe_fl))
        series_eq = bool(np.allclose(ora_rd, pipe_rd, rtol=0, atol=0))
        act = ora_fl == 1
        comp_ok = True
        for t in np.where(act)[0]:
            if abs(
                float(ora_rd[t])
                - dm.retest_depth(float(cc[t]), float(ee[t]), float(aa[t]))
            ) > 1e-5:
                comp_ok = False
        off = ora_fl != 1
        off_ok = bool(np.all(ora_rd[off] == 0.0))
        # finalize survivorship contract on the pre-finalize emission:
        # off-flag bars have exactly 0.0 and retest_depth has no NaN (Phase 0)
        fin_ok = bool(
            (full["retest_depth"].isna().sum() == 0)
            and (((full["retest_flag"] != 1) & (full["retest_depth"] != 0.0)).sum() == 0)
        )
        corpus = {
            "35_synthetic_boundary_parity": _pass(ok33),
            "36_representative_corpus_series_parity": _pass(series_eq),
            "32_corpus_gate_parity": _pass(gate_eq),
            "34_active_row_derived_math": _pass(comp_ok),
            "21_corpus_off_gate_zero": _pass(off_ok),
            "23_off_gate_zero_no_nan": _pass(fin_ok),
            "n_rows": int(len(sub)),
            "flag_rate": float(act.mean()) if len(act) else 0.0,
            "max_abs_err": float(
                np.max(np.abs(ora_rd.astype(np.float64) - pipe_rd.astype(np.float64)))
            )
            if len(ora_rd)
            else 0.0,
        }
        results["pipeline_corpus"] = corpus
        all_ok &= all(
            corpus[k] == "PASS"
            for k in corpus
            if isinstance(corpus[k], str) and corpus[k] in ("PASS", "FAIL")
        )

    results["overall_verdict"] = "CERTIFIED" if all_ok else "REJECT"
    results["all_probes_pass"] = all_ok
    return results


def build_artifact(checkpoint: dict, battery: dict) -> dict:
    return {
        "_doc": "M10 / F-054-RD retest_depth GATED production composition certification.",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session": "M10",
        "program": "F-054-RD",
        "TARGET_FEATURE": "retest_depth",
        "TARGET_IDENTITY": "GATED_PRODUCTION_COMPOSITION",
        "COMPONENT_FORMULA_IDENTITY": "FM-021",
        "FORMULA_IDENTITY": (
            "canonical retest_depth has no standalone FM scalar identity for its full gated composition"
        ),
        "COMPOSITION_RELATION": (
            "canonical retest_depth uses FM-021 as its on-gate mathematical kernel only; "
            "FM-021 != full canonical series"
        ),
        "FULL_DEPENDENCIES": ["atr", "close", "ema_fast", "liquidity_sweep"],
        "GATE_WINDOW": 10,
        "GATE_WINDOW_SEMANTICS": "trailing causal, current bar included, min_periods=1",
        "NEAR_BAND": "abs(close-ema_fast) <= 1.0 * atr * close (INCLUSIVE)",
        "OFF_GATE_VALUE": 0.0,
        "CANONICAL_DTYPE": "float32",
        "CANONICAL_INDEX": 33,
        "EXACT_EMISSION_ORDERING": [
            "where(retest_flag==1 & atr>0 & close>0, abs(close-ema_fast)/(atr*close), 0.0)",
            "astype(float32)",
            "clip(0.0, 1.0)",
            "astype(float32)",
        ],
        "source_of_truth": "src/features/feature_pipeline.py:599-610,648-653",
        "checkpoint_start": {
            "frontier": checkpoint["counts"],
            "retest_depth": {
                "effective_state": checkpoint["retest_depth"]["effective_state"],
                "deps": checkpoint["dag_deps"],
                "blocking": checkpoint["retest_depth"].get("blocking_dependencies"),
            },
            "ledger_bytes": checkpoint["ledger_bytes"],
            "ledger_sha256": checkpoint["ledger_sha256"],
        },
        "dag_correction": {
            "before": ["atr", "ema_fast", "liquidity_sweep"],
            "after": checkpoint["dag_deps"],
            "mechanism": (
                "Authoritative _NODES in scripts/analysis/feature_dag_layers.py updated; "
                "live build_dag() supplies deps to resolver; historical SEEDED line NOT rewritten"
            ),
            "LEDGER_HISTORY_REWRITTEN": "NO",
        },
        "probes": battery,
        "PER_NODE_VERDICT": battery["overall_verdict"],
        "PRODUCTION_BEHAVIOR_CHANGED": "NO",
        "authority": (
            "research/governance only — descriptive certification; grants no runtime/production authority (§6.5)"
        ),
        "scope_boundary": (
            "retest_depth only. FM-021 formula/derived_math unchanged. No new FM-ID. "
            "No L4. No production math change."
        ),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("M10 / F-054-RD — retest_depth GATED COMPOSITION CERTIFICATION")
    print("=" * 72)

    print("\n--- Checkpoint ---")
    cp = resolve_frontier()
    print("FRONTIER", cp["counts"])
    print("retest_depth", cp["retest_depth"]["effective_state"], "deps", cp["dag_deps"])
    print("READY", cp["ready"])
    if cp["retest_depth"]["effective_state"] != "READY_TO_CERTIFY":
        print("REFUSED: not READY")
        return 2
    if sorted(cp["dag_deps"]) != ["atr", "close", "ema_fast", "liquidity_sweep"]:
        print("REFUSED: DAG deps not corrected:", cp["dag_deps"])
        return 2
    if cp["retest_depth"].get("blocking_dependencies"):
        print("REFUSED: blocking", cp["retest_depth"]["blocking_dependencies"])
        return 2

    print("\n--- Battery ---")
    battery = run_battery()
    for section, val in battery.items():
        if section in ("overall_verdict", "all_probes_pass"):
            continue
        if isinstance(val, dict):
            print(f"[{section}]")
            for k, v in val.items():
                if isinstance(v, str) and v in ("PASS", "FAIL"):
                    print(f"  {k:45s} {v}")
                elif k in ("n_rows", "flag_rate", "max_abs_err"):
                    print(f"  {k:45s} {v}")
    print("OVERALL", battery["overall_verdict"])
    if battery["overall_verdict"] != "CERTIFIED":
        return 3

    art = build_artifact(cp, battery)
    EVIDENCE.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
    sha = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    if not sha:
        print("REFUSED: empty SHA")
        return 4
    print(f"\nARTIFACT {EVIDENCE.relative_to(_ROOT)}")
    print(f"SHA256   {sha}")
    print("ALL PROBES PASS — retest_depth GATED COMPOSITION CERTIFIABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
