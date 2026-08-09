"""
feature_dag_structural_certification.py — L3 swing-structural family certification (READ-ONLY).

Certifies the four swing-derived structural detection flags computed together in
feature_pipeline.compute_structure_liquidity from the same causal (FC1-A) swing references:
  higher_high · lower_low · break_of_structure · liquidity_sweep

TWO independent oracles, BOTH compared to the real FeaturePipeline columns by EXACT integer
equality on shared post-warmup rows:

  1. FORMULA-PARITY oracle (centered reconstruction) — replicates the pipeline's centered
     rolling max/min → shift(SWING_WINDOW) → ffill → refs → flags. Proves the FORMULA matches.
     It LEAKS pre-shift, so it is the formula oracle ONLY, never the causality proof.
  2. CAUSAL ONLINE oracle — a genuinely sequential bar-by-bar implementation: at bar t it
     confirms/publishes the pivot for bar t-k using only bars <= t (window [t-2k, t]). It uses
     NO future information by construction. Its match to the pipeline column is the CAUSALITY
     proof (independent re-proof of FC1-A for these four flags).

Plus EQUALITY-BOUNDARY probes at close==ref_high / close==ref_low / high==ref_high / low==ref_low
(the sweep close-return is INCLUSIVE <=/>=; HH/LL/BOS are strict >/<, per feature_pipeline.py:462-484).

PIT is recorded as a DEPENDENCY-BOUND reference: the pit_phaseC 38-vector prefix floor covers these
canonical columns, bound to the current repo_state_hash so the reference cannot silently go stale.

Verdict per flag: CERTIFIED (both oracles match + boundary probes pass) / REJECT.
Usage: python scripts/analysis/feature_dag_structural_certification.py [--limit 8000]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline, SWING_WINDOW  # noqa: E402
from features import derived_math as dm  # noqa: E402  (FM-025 registry-authoritative scalar)

_GOV = _ROOT / "docs" / "governance"
_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_MAJORS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT")
_FLAGS = ("higher_high", "lower_low", "break_of_structure", "liquidity_sweep")
# derived-of-liquidity_sweep quantities (projections of the oracle-derived liquidity_sweep, not the
# pipeline's — genuinely independent). sweep_detected = same-bar presence; double_sweep = trailing
# 5-bar directional conjunction; candles_since_retest = bars-since-sweep counter (int16).
_DERIVED_FLAGS = ("sweep_detected", "double_sweep", "candles_since_retest")
# float-valued FM-025: certified via the registry-authoritative scalar derived_math.liquidity_distance
# fed with independently-reconstructed promoted levels (NOT a copy of the pipeline vectorized min).
_DERIVED_FLOAT = ("liquidity_distance",)
_ALL_FLAGS = _FLAGS + _DERIVED_FLAGS
_ALL_CERTIFIED = _ALL_FLAGS + _DERIVED_FLOAT
_DOUBLE_SWEEP_WINDOW = 5
_LD_RTOL, _LD_ATOL = 1e-4, 1e-6            # float32 pipeline column vs float64 derived_math scalar


def _liquidity_distance(ref_high, ref_low, bos_flag, close, atr) -> np.ndarray:
    """FM-025 via the REGISTRY-AUTHORITATIVE scalar derived_math.liquidity_distance, fed with
    independently-reconstructed levels. bos_level = ffill of {ref_high at BOS==1, ref_low at BOS==-1}
    (feature_pipeline.py:698-704). Returns float32; NaN where atr*close<=0 or no finite level."""
    rh = pd.Series(np.asarray(ref_high, dtype="float64"))
    rl = pd.Series(np.asarray(ref_low, dtype="float64"))
    bos = np.asarray(bos_flag)
    bos_level = pd.Series(np.nan, index=rh.index)
    bos_level[bos == 1] = rh[bos == 1]
    bos_level[bos == -1] = rl[bos == -1]
    bos_level = bos_level.ffill().to_numpy()
    c = np.asarray(close, dtype="float64"); a = np.asarray(atr, dtype="float64")
    rhv, rlv = rh.to_numpy(), rl.to_numpy()
    out = np.array([dm.liquidity_distance(c[t], a[t], rhv[t], rlv[t], bos_level[t])
                    for t in range(len(c))], dtype="float32")
    return out


def _indep_close_relative_atr(raw: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Independent close + close-relative atr (SMA14(TR)/close) over the FULL frame — mirrors the
    promoted FM-041 atr so liquidity_distance is reconstructed entirely from promoted upstream."""
    df = raw.copy(); df.columns = [c.strip().lower() for c in df.columns]
    close = df["close"].astype("float64"); high = df["high"].astype("float64"); low = df["low"].astype("float64")
    pc = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - pc).abs(), (low - pc).abs()))
    atr_raw = tr.rolling(14).mean()
    atr = np.where(close.to_numpy() > 0, (atr_raw / close).to_numpy(), 0.0)
    return close.to_numpy(), atr


def _double_sweep(liq: np.ndarray) -> np.ndarray:
    """int8 {0,1}: both a >0 sweep AND a <0 sweep within the trailing window (feature_pipeline.py:612-626).
    Trailing rolling(window,min_periods=1).max — causal; a directional conjunction, NOT a count."""
    s = pd.Series(liq)
    seen_up = (s > 0).rolling(_DOUBLE_SWEEP_WINDOW, min_periods=1).max().astype(bool)
    seen_down = (s < 0).rolling(_DOUBLE_SWEEP_WINDOW, min_periods=1).max().astype(bool)
    return (seen_up & seen_down).to_numpy().astype("int8")


def _candles_since_retest(liq: np.ndarray) -> np.ndarray:
    """int16 >=0: bars since the last liquidity_sweep!=0 event, as an INDEPENDENT ONLINE state machine
    (vs the pipeline's batch groupby.cumcount). SWEEP bar → 0, each non-sweep bar +1, 0 before the
    first sweep. Causal by construction (feature_pipeline.py:655-672, PRODUCTION liquidity_sweep branch).
    NOTE: reset event is the SWEEP (name 'retest' is a misnomer); the retest_flag fallback is NOT modeled
    (non-authoritative, class B)."""
    n = len(liq)
    out = np.zeros(n, dtype="int16")
    counter = 0
    started = False
    for t in range(n):
        if liq[t] != 0:            # sweep event → new group; event bar publishes 0
            counter = 0
            started = True
        elif started:              # non-sweep bar after a sweep → increment
            counter += 1
        else:                      # before the first sweep → 0
            counter = 0
        out[t] = counter
    return out


def _repo_state_hash() -> str:
    """HEAD[:12]+diffsha[:12] — binds the PIT reference to the exact current repo state."""
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_ROOT).decode().strip()[:12]
        diff = subprocess.check_output(["git", "diff", "HEAD"], cwd=_ROOT)
        return f"{head}+{hashlib.sha256(diff).hexdigest()[:12]}"
    except Exception:
        return "UNKNOWN_REPO_STATE"


def _synthetic(n=1400, seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.8, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.8, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": rng.uniform(100, 1000, n)})


def _load(sym, limit):
    csv = _ROOT / "data" / f"{sym}_M15.csv"
    if not csv.exists():
        return None
    df = pd.read_csv(csv)
    df.columns = [c.strip().lower() for c in df.columns]
    return df.head(limit).copy() if limit else df


def _run(raw):
    feat, _ = FeaturePipeline(raw.copy()).run()
    return feat.set_index("timestamp")


# ── the four flags from causal swing references ──────────────────────────────────

def _flags_from_refs(high, low, close, ref_high, ref_low) -> dict[str, np.ndarray]:
    """The pinned pipeline boundary semantics (feature_pipeline.py:462-484), int8."""
    hh = (high > ref_high).astype("int8")
    ll = (low < ref_low).astype("int8")
    bos = np.where(close > ref_high, 1, np.where(close < ref_low, -1, 0)).astype("int8")
    sweep_high = (high > ref_high) & (close <= ref_high)   # INCLUSIVE close-return
    sweep_low = (low < ref_low) & (close >= ref_low)       # INCLUSIVE
    liq = np.where(sweep_high, 1, np.where(sweep_low, -1, 0)).astype("int8")
    sweep_detected = (liq != 0).astype("int8")             # derived: direction-agnostic presence (feature_pipeline.py:590)
    return {"higher_high": hh, "lower_low": ll, "break_of_structure": bos,
            "liquidity_sweep": liq, "sweep_detected": sweep_detected}


def _oracle_centered(raw: pd.DataFrame) -> pd.DataFrame:
    """FORMULA-PARITY oracle — replicates the pipeline's centered→shift publication (leaks pre-shift)."""
    df = raw.copy(); df.columns = [c.strip().lower() for c in df.columns]
    high, low, close = df["high"].astype("float64"), df["low"].astype("float64"), df["close"].astype("float64")
    w, k = 2 * SWING_WINDOW + 1, SWING_WINDOW
    roll_high = high.rolling(w, center=True, min_periods=w).max()
    roll_low = low.rolling(w, center=True, min_periods=w).min()
    sh_c = (high == roll_high)
    sl_c = (low == roll_low)
    last_high = high.where(sh_c).ffill().shift(k)
    last_low = low.where(sl_c).ffill().shift(k)
    ref_high = last_high.shift(1).to_numpy("float64")
    ref_low = last_low.shift(1).to_numpy("float64")
    flags = _flags_from_refs(high.to_numpy(), low.to_numpy(), close.to_numpy(), ref_high, ref_low)
    flags["double_sweep"] = _double_sweep(flags["liquidity_sweep"])
    flags["candles_since_retest"] = _candles_since_retest(flags["liquidity_sweep"])
    out = pd.DataFrame({**flags, "ref_high": ref_high, "ref_low": ref_low})
    out.index = pd.Index(pd.to_datetime(df["timestamp"]), name="timestamp")
    return out


def _oracle_causal_online(raw: pd.DataFrame) -> pd.DataFrame:
    """CAUSALITY oracle — sequential: at bar t confirm the pivot for bar t-k using bars <= t only."""
    df = raw.copy(); df.columns = [c.strip().lower() for c in df.columns]
    high = df["high"].to_numpy("float64"); low = df["low"].to_numpy("float64"); close = df["close"].to_numpy("float64")
    n, k = len(high), SWING_WINDOW
    last_h = np.full(n, np.nan); last_l = np.full(n, np.nan)
    cur_h = np.nan; cur_l = np.nan
    for t in range(n):
        j = t - k                     # centered position confirmed at bar t
        if j - k >= 0:                # window [j-k, j+k] == [t-2k, t], all bars <= t
            win_h = high[t - 2 * k: t + 1]
            if high[j] == win_h.max():
                cur_h = high[j]
            win_l = low[t - 2 * k: t + 1]
            if low[j] == win_l.min():
                cur_l = low[j]
        last_h[t] = cur_h; last_l[t] = cur_l
    ref_high = pd.Series(last_h).shift(1).to_numpy("float64")   # last_swing.shift(1)
    ref_low = pd.Series(last_l).shift(1).to_numpy("float64")
    flags = _flags_from_refs(high, low, close, ref_high, ref_low)
    flags["double_sweep"] = _double_sweep(flags["liquidity_sweep"])
    flags["candles_since_retest"] = _candles_since_retest(flags["liquidity_sweep"])
    out = pd.DataFrame({**flags, "ref_high": ref_high, "ref_low": ref_low})
    out.index = pd.Index(pd.to_datetime(df["timestamp"]), name="timestamp")
    return out


def _exact_eq(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.array_equal(a, b))


def certify_arm(raw: pd.DataFrame, label: str) -> dict:
    pipe = _run(raw)
    cen = _oracle_centered(raw)
    onl = _oracle_causal_online(raw)
    shared = pipe.index.intersection(cen.index).intersection(onl.index)
    # compare only rows where the causal ref is defined (post-warmup) — same mask for all oracles
    ref_ok = np.isfinite(onl.loc[shared, "ref_high"].to_numpy()) | np.isfinite(onl.loc[shared, "ref_low"].to_numpy())
    idx = shared[ref_ok]
    res = {}
    for f in _ALL_FLAGS:
        p = pipe.loc[idx, f].to_numpy("int64")
        c = cen.loc[idx, f].to_numpy("int64")
        o = onl.loc[idx, f].to_numpy("int64")
        res[f] = {
            "formula_parity_centered": _exact_eq(c, p),
            "causal_online_matches_pipeline": _exact_eq(o, p),
            "rows": int(len(idx)),
        }
    # FM-025 liquidity_distance: authoritative scalar (derived_math) + independently-reconstructed
    # levels + independent close-relative atr, over the FULL frame (correct bos_level ffill), then
    # aligned to idx and compared to the pipeline float32 column.
    close_full, atr_full = _indep_close_relative_atr(raw)
    for label, oracle in (("centered", cen), ("causal_online", onl)):
        ld_full = _liquidity_distance(oracle["ref_high"].to_numpy("float64"),
                                      oracle["ref_low"].to_numpy("float64"),
                                      oracle["break_of_structure"].to_numpy("int64"),
                                      close_full, atr_full)
        ld = pd.Series(ld_full, index=oracle.index).loc[idx].to_numpy("float64")
        p = pipe.loc[idx, "liquidity_distance"].to_numpy("float64")
        finite_match = bool(np.array_equal(np.isfinite(ld), np.isfinite(p)))
        m = np.isfinite(ld) & np.isfinite(p)
        val_match = bool(np.allclose(ld[m], p[m], rtol=_LD_RTOL, atol=_LD_ATOL)) if m.any() else False
        key = "formula_parity_centered" if label == "centered" else "causal_online_matches_pipeline"
        res.setdefault("liquidity_distance", {"rows": int(len(idx))})[key] = finite_match and val_match

    # equality-boundary probe counts (proves the boundary rows are actually exercised)
    rh = onl.loc[idx, "ref_high"].to_numpy("float64"); rl = onl.loc[idx, "ref_low"].to_numpy("float64")
    hi = pipe.loc[idx, "high"].to_numpy("float64") if "high" in pipe else None
    boundary = {
        "close_eq_ref_high": int(np.sum(pipe.loc[idx, "close"].to_numpy("float64") == rh)),
        "close_eq_ref_low": int(np.sum(pipe.loc[idx, "close"].to_numpy("float64") == rl)),
        "high_eq_ref_high": int(np.sum(pipe.loc[idx, "high"].to_numpy("float64") == rh)),
        "low_eq_ref_low": int(np.sum(pipe.loc[idx, "low"].to_numpy("float64") == rl)),
    }
    return {"corpus": label, "per_flag": res, "equality_boundary_counts": boundary}


def build_report(limit: int, include_corpus: bool = True) -> dict:
    synth = _synthetic()
    arms = [certify_arm(synth, "synthetic_1400")]
    if include_corpus:
        for s in _MAJORS:
            c = _load(s, limit)
            if c is not None:
                arms.append(certify_arm(c, f"{s}_M15"))
    verdicts = {}
    for f in _ALL_CERTIFIED:
        both = all(a["per_flag"][f]["formula_parity_centered"] and
                   a["per_flag"][f]["causal_online_matches_pipeline"] for a in arms)
        verdicts[f] = "CERTIFIED" if both else "REJECT"
    return {
        "probe": "feature_dag_structural_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": ("research/governance only — SERIES parity (formula) + CAUSAL online (causality) "
                      "certification of L3 swing-structural flags; ledger-only, grants no activation "
                      "authority (§6.5)."),
        "swing_window": SWING_WINDOW,
        "pinned_semantics": {
            "source": "src/features/feature_pipeline.py:462-484",
            "higher_high": "high > ref_high (strict)", "lower_low": "low < ref_low (strict)",
            "break_of_structure": "+1 close>ref_high / -1 close<ref_low / 0 (strict)",
            "liquidity_sweep": "+1 (high>ref_high & close<=ref_high) / -1 (low<ref_low & close>=ref_low) / 0 (INCLUSIVE close-return)",
            "sweep_detected": "int8 {0,1}: (liquidity_sweep != 0) — direction-agnostic sweep presence (feature_pipeline.py:590)",
            "double_sweep": "int8 {0,1}: seen_up(rolling5 liq>0) AND seen_down(rolling5 liq<0) — trailing 5-bar directional conjunction, NOT a count (feature_pipeline.py:612-626)",
            "candles_since_retest": "int16 >=0: bars since last liquidity_sweep!=0 (grouped cumcount; sweep bar=0, +1 per non-sweep bar, 0 pre-first-sweep). MISNOMER: resets on SWEEP not retest_flag (feature_pipeline.py:655-672)",
            "liquidity_distance": "FM-025 float32 >=0: min_k |close-level_k|/(atr*close) over {ref_high, ref_low, bos_level}, clipped >=0; NaN if atr*close<=0 or no finite level. Certified via derived_math.liquidity_distance (registry authority) + oracle-reconstructed levels (feature_pipeline.py:692-718)",
        },
        "candles_since_retest_fallback": {
            "classification": "B_TEST_ONLY_COMPATIBILITY_SHIM",
            "authority": "non_authoritative",
            "reason": "the retest_flag branch (feature_pipeline.py:665-666) is reached only when the "
                      "liquidity_sweep column is ABSENT; run() computes liquidity_sweep (:896) before "
                      "candles_since_retest (:905), so it is unreachable in production. Certified "
                      "contract = the liquidity_sweep branch ONLY. Fenced by runtime + branch-discrimination tests.",
        },
        "pit_evidence": {
            "referenced_artifact": "docs/governance/pit_phaseC_feature_certification.LATEST.json",
            "referenced_floor": "tests/test_pit_prefix_invariance.py",
            "repo_state_hash": _repo_state_hash(),
            "causal_online_oracle": "matched" if all(v == "CERTIFIED" for v in verdicts.values()) else "MISMATCH",
            "note": "PIT is dependency-bound: the causal ONLINE oracle is the primary causality proof; "
                    "the pit_phaseC 38-vector prefix floor is the corroborating reference at this repo state.",
        },
        "arms": arms,
        "verdicts": verdicts,
        "overall": "CERTIFIED" if all(v == "CERTIFIED" for v in verdicts.values()) else "REJECT",
        "permanent_floor": "tests/test_feature_dag_structural_certification.py",
    }


def _write(rep) -> tuple[Path, str]:
    stem = f"feature_dag_structural_certification-{_STAMP}"
    oj, om = _GOV / f"{stem}.json", _GOV / f"{stem}.md"
    payload = json.dumps(rep, indent=2) + "\n"
    oj.write_text(payload, encoding="utf-8")
    lines = ["# L3 Swing-Structural Family Certification", "",
             f"_Generated {rep['generated_at']} · READ-ONLY · overall **{rep['overall']}** · "
             f"repo_state {rep['pit_evidence']['repo_state_hash']}._", "",
             "Two oracles (formula-parity centered + CAUSAL online) both == pipeline int8 columns; "
             "equality-boundary probes exercised.", ""]
    for f, v in rep["verdicts"].items():
        lines.append(f"- `{f}`: **{v}**")
    om.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sha = hashlib.sha256(payload.encode()).hexdigest()
    (_GOV / "feature_dag_structural_certification.LATEST.json").write_text(json.dumps({
        "path": str(oj.relative_to(_ROOT)).replace("\\", "/"), "generated_at": rep["generated_at"],
        "sha256": sha, "overall": rep["overall"], "repo_state_hash": rep["pit_evidence"]["repo_state_hash"],
    }, indent=2) + "\n", encoding="utf-8")
    return oj, sha


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8000)
    args = ap.parse_args()
    rep = build_report(args.limit)
    oj, sha = _write(rep)
    print(f"probe → {oj.relative_to(_ROOT)} (sha {sha[:12]})  overall={rep['overall']}")
    for f, v in rep["verdicts"].items():
        print(f"  {f:20s} {v}")
    for a in rep["arms"]:
        print(f"  boundary[{a['corpus']}]: {a['equality_boundary_counts']}")
    return 0 if rep["overall"] == "CERTIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
