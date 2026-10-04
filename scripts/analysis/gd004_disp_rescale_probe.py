"""
gd004_disp_rescale_probe.py — GD-004 identity-closure characterization probe (READ-ONLY).

Characterizes the AS-WIRED quantity behind lint pin GD-004 before its registry closure:

    scoring_engine.compute_scores:31   disp_strength = move / atr
    sole caller crt_engine.compute:23  move = features["disp_strength"]   (pipeline FM-020)
                                       atr  = features["atr"]             (pipeline, close-relative)

Static adjudication (this probe is the empirical check):
    pipeline atr      = atr_14_raw / close                      (feature_pipeline.py:511-515)
    FM-020            = clip(body_size / (atr * close), 0, 3)   = body_size / atr_14_raw
    AS-WIRED quantity = FM-020 / atr_rel                        = body_size * close / atr_14_raw^2
    FM-028            = candle_range / atr_abs                  (crt_engine_v2.py:1355 family)

So the as-wired quantity is a THIRD identity — neither FM-020 nor FM-028 — slated for
registration as FM-029 `disp_strength_atr_rescale`. This probe records, on a real corpus:

  1. ATR-unit verification: pipeline `atr` column == atr-relative (atr_14_raw/close), i.e. the
     value crt_engine.compute receives via CANONICAL_FEATURES index 13 (backtest_v2.py:2132-2141;
     setdefault never fires because "atr" is canonical).
  2. The as-wired value distribution and the fraction saturating min(x/2, 1) at 1.0 in
     s_breakout (scoring_engine.py:40) — how much information the term actually carries.
  3. Non-equivalence rates vs FM-020 and vs FM-028 (identity-adjudication evidence).

STRICTLY READ-ONLY w.r.t. code/config; writes only the probe artifact under docs/governance/.

Usage: python scripts/analysis/gd004_disp_rescale_probe.py [--symbol BNBUSDT] [--limit 30000]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402

_TOL = 1e-9
_REL_TOL = 1e-4          # float32 pipeline columns vs float64 recomputation
_SAT_CAP = 2.0           # s_breakout uses min(disp_strength / 2.0, 1.0) → saturates at x >= 2.0


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    xs_sorted = sorted(xs)
    p = lambda q: xs_sorted[min(len(xs_sorted) - 1, int(q * len(xs_sorted)))]
    return {"n": len(xs), "min": xs_sorted[0], "p05": p(0.05), "median": statistics.median(xs),
            "mean": statistics.fmean(xs), "p95": p(0.95), "max": xs_sorted[-1]}


def run_probe(symbol: str, limit: int) -> dict:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    if limit:
        df = df.head(limit).copy()
    feat_df, _ = FeaturePipeline(df).run()

    n = 0
    atr_unit_matches = 0            # atr column == recomputed atr_14_raw/close (unit check)
    atr_unit_checked = 0
    as_wired_vals: list[float] = []
    fm020_vals: list[float] = []
    fm028_vals: list[float] = []
    atr_rel_vals: list[float] = []
    saturated = 0                   # as-wired >= 2.0 → min(x/2, 1) pins at 1.0
    zero_gate = 0                   # atr <= 0 → local formula returns 0.0
    eq_fm020 = 0                    # |as_wired - FM-020| within tol (identity check)
    eq_fm028 = 0                    # |as_wired - FM-028| within tol (identity check)

    # Recompute atr_14_raw exactly as feature_pipeline.py:271-275 (TR rolling-14 mean) to verify
    # the unit of the shipped `atr` column without relying on intermediate columns surviving.
    tr1 = feat_df["high"] - feat_df["low"]
    tr2 = (feat_df["high"] - feat_df["close"].shift(1)).abs()
    tr3 = (feat_df["low"] - feat_df["close"].shift(1)).abs()
    atr_raw_recomputed = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

    for i, (_, r) in enumerate(feat_df.iterrows()):
        close = float(r["close"])
        atr_rel = float(r["atr"])
        fm020 = float(r["disp_strength"])
        n += 1

        raw = atr_raw_recomputed.iloc[i]
        if pd.notna(raw) and close > 0:
            atr_unit_checked += 1
            expected_rel = float(raw) / close
            if abs(atr_rel - expected_rel) <= _REL_TOL * max(1.0, abs(expected_rel)):
                atr_unit_matches += 1

        if atr_rel > 0:
            as_wired = fm020 / atr_rel                      # scoring_engine.py:31 as wired
            atr_abs = atr_rel * close
            fm028 = (float(r["high"]) - float(r["low"])) / atr_abs if atr_abs > 0 else 0.0
        else:
            as_wired = 0.0
            fm028 = 0.0
            zero_gate += 1

        as_wired_vals.append(as_wired)
        fm020_vals.append(fm020)
        fm028_vals.append(fm028)
        atr_rel_vals.append(atr_rel)
        if as_wired >= _SAT_CAP - _TOL:
            saturated += 1
        if abs(as_wired - fm020) <= _TOL * max(1.0, abs(fm020)):
            eq_fm020 += 1
        if abs(as_wired - fm028) <= _REL_TOL * max(1.0, abs(fm028)):
            eq_fm028 += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "bars": n,
        "gd_id": "GD-004",
        "site": "scoring_engine.py:31 disp_strength = move/atr; caller crt_engine.py:23 move=features['disp_strength']",
        "atr_unit_verification": {
            "assumption": "pipeline atr column is close-relative (atr_14_raw / close), feature_pipeline.py:511-515",
            "bars_checked": atr_unit_checked,
            "bars_matching": atr_unit_matches,
            "match_rate": atr_unit_matches / atr_unit_checked if atr_unit_checked else 0.0,
            "atr_column_distribution": _stats(atr_rel_vals),
        },
        "as_wired_quantity": {
            "formula": "FM-020 / atr_rel  ==  body_size * close / atr_14_raw^2",
            "distribution": _stats(as_wired_vals),
            "s_breakout_saturation": {
                "cap": _SAT_CAP,
                "bars_saturated": saturated,
                "saturation_rate": saturated / n if n else 0.0,
                "note": "fraction of bars where min(x/2,1)=1.0 — above this the term carries zero information",
            },
            "atr_zero_gate_bars": zero_gate,
        },
        "identity_adjudication": {
            "fm020_distribution": _stats(fm020_vals),
            "fm028_distribution": _stats(fm028_vals),
            "equals_fm020_rate": eq_fm020 / n if n else 0.0,
            "equals_fm028_rate": eq_fm028 / n if n else 0.0,
            "verdict_criterion": "both rates ~0 ⇒ genuinely new quantity (register FM-029); "
                                 "either ~1 ⇒ STOP, adjudication wrong",
        },
        "scope_caveat": ("Characterization only — feeds the FM-029 ontology note and the GD-004 "
                         "retirement fields. Backtests run gate-OFF (F-037) and run() never "
                         "executes (F-048), so no production-loss claim."),
    }


def _to_md(rep: dict) -> str:
    a, w, i = rep["atr_unit_verification"], rep["as_wired_quantity"], rep["identity_adjudication"]
    sat = w["s_breakout_saturation"]
    return "\n".join([
        "# GD-004 disp_strength rescale probe (identity-closure characterization)",
        "",
        f"_Generated {rep['generated_at']} · symbol {rep['symbol']} · {rep['bars']} bars · read-only._",
        "",
        f"Site: `{rep['site']}`",
        "",
        "## ATR-unit verification",
        f"- pipeline `atr` == atr_14_raw/close on **{a['match_rate']:.1%}** of {a['bars_checked']} checkable bars",
        f"- atr column: median {a['atr_column_distribution'].get('median', 0):.6f} · p95 {a['atr_column_distribution'].get('p95', 0):.6f}",
        "",
        "## As-wired quantity (FM-020 / atr_rel)",
        f"- distribution: median {w['distribution'].get('median', 0):.2f} · mean {w['distribution'].get('mean', 0):.2f} · p95 {w['distribution'].get('p95', 0):.2f}",
        f"- s_breakout saturation (x ≥ {sat['cap']}): **{sat['saturation_rate']:.1%}** of bars",
        "",
        "## Identity adjudication",
        f"- equals FM-020: {i['equals_fm020_rate']:.2%} · equals FM-028: {i['equals_fm028_rate']:.2%}",
        f"- criterion: {i['verdict_criterion']}",
        "",
        f"> {rep['scope_caveat']}",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="GD-004 disp_strength rescale probe (read-only).")
    ap.add_argument("--symbol", default="BNBUSDT")
    ap.add_argument("--limit", type=int, default=30000, help="max bars (0 = all)")
    args = ap.parse_args()

    rep = run_probe(args.symbol, args.limit)
    out_dir = _ROOT / "docs" / "governance"
    stem = "gd004_disp_rescale_probe-2026-07-11"
    (out_dir / f"{stem}.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(_to_md(rep), encoding="utf-8")
    a, w, i = rep["atr_unit_verification"], rep["as_wired_quantity"], rep["identity_adjudication"]
    print(f"probe → docs/governance/{stem}.{{json,md}}  ({rep['symbol']}, {rep['bars']} bars)")
    print(f"  atr-unit match {a['match_rate']:.1%} · saturation {w['s_breakout_saturation']['saturation_rate']:.1%}")
    print(f"  equals FM-020 {i['equals_fm020_rate']:.2%} · equals FM-028 {i['equals_fm028_rate']:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
