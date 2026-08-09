"""
feature_math_drift_probe.py — Gate-2 differential probe (READ-ONLY).

Measures the real output drift of the two Gate-2-eligible grandfather divergences (GD-001 `body_ratio`,
GD-002 `wick_size`) — the ONLY pins that are `same_quantity` + `non_equivalent` + `decision_reachable`
in Matrix v1 (docs/analysis/feature-math-divergence-adjudication.md). Built AFTER the matrix froze; it
targets the VERIFIED consumer chain, not an assumed one:

    live_engine_hook `_build_ohlcv_and_auxiliary` (body/total_wick)  →  features["body_ratio"]
      →  crt_engine.compute  →  scoring_engine.compute_scores  s_breakout (:40)  →  CRT score  →  fusion

The current (live-hook) formula and the canonical one:
    canonical  body_ratio = body_size / candle_range     (candle_range = high - low)          ∈ [0,1]
    current    body_ratio = body_size / total_wick        (total_wick  = (high-low) - body)   ≥ canonical, can exceed 1
Because candle_range = total_wick + body_size ≥ total_wick, the current form is ALWAYS ≥ canonical →
it systematically INFLATES s_breakout. This probe quantifies that on a real corpus.

STRICTLY READ-ONLY: reads a CSV + the frozen feature pipeline, drives the real `crt_engine.compute`
twice per bar (canonical vs current body_ratio, all else held fixed), and writes ONLY to reports/.
It does NOT import or modify live_engine_hook — it replicates that file's exact arithmetic to compare.

SCOPE CAVEAT (E-001): the CRT-score delta is the NECESSARY channel to a fusion APPROVE/REJECT flip
(body_ratio's only downstream path). A full end-to-end fusion flip additionally depends on the other
three engines + threshold; and the live-hook path is F-010-unverified (backtests bypass it). So a
measured CRT-score-flip rate BOUNDS potential impact — it is NOT a production-loss claim.

Usage: python scripts/analysis/feature_math_drift_probe.py [--symbol BNBUSDT] [--limit 30000]
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
from engines import crt_engine  # noqa: E402

_TOL = 1e-9


def _current_body_ratio_and_wick(open_, high, low, close):
    """Replicate live_engine_hook.py:360-362 EXACTLY (read-only reproduction, not an import)."""
    body_size = abs(close - open_)
    wick_size = max(0.0, (high - low) - body_size)         # = total_wick (NON-canonical)
    body_ratio = body_size / wick_size if wick_size > 1e-8 else 0.0
    return body_ratio, wick_size


def _crt_score(feat_row: dict, body_ratio: float) -> float:
    features = {
        "body_ratio": body_ratio,
        "disp_strength": feat_row["disp_strength"],
        "atr": feat_row["atr"],
        "retest_depth": feat_row["retest_depth"],
        "candles_since_retest": int(feat_row.get("candles_since_retest", 0)),
        "sweep_detected": bool(feat_row.get("sweep_detected", 0)),
        "double_sweep": bool(feat_row.get("double_sweep", 0)),
    }
    return float(crt_engine.compute("drift_probe", features, {"score_component_weights": [0.35, 0.25, 0.20, 0.20]}).get("score", 0.0))


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    xs_sorted = sorted(xs)
    p = lambda q: xs_sorted[min(len(xs_sorted) - 1, int(q * len(xs_sorted)))]
    return {"n": len(xs), "mean": statistics.fmean(xs), "median": statistics.median(xs),
            "p95": p(0.95), "max": xs_sorted[-1]}


def run_probe(symbol: str, limit: int) -> dict:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    if limit:
        df = df.head(limit).copy()
    feat_df, _ = FeaturePipeline(df).run()

    n = 0
    value_differ = 0
    bound_violations = 0            # current body_ratio > 1.0 (impossible for canonical)
    current_ge_canonical = 0        # directional inflation check
    br_deltas: list[float] = []     # current - canonical (body_ratio)
    ws_deltas: list[float] = []     # current - canonical (wick_size)
    score_differ = 0
    score_deltas: list[float] = []  # current_score - canonical_score
    score_up = 0                    # current inflates the CRT score

    for _, r in feat_df.iterrows():
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        canonical_br = float(r["body_ratio"])
        canonical_ws = h - l
        current_br, current_ws = _current_body_ratio_and_wick(o, h, l, c)
        n += 1
        d_br = current_br - canonical_br
        br_deltas.append(abs(d_br)); ws_deltas.append(abs(current_ws - canonical_ws))
        if abs(d_br) > _TOL:
            value_differ += 1
        if current_br > canonical_br - _TOL:
            current_ge_canonical += 1
        if current_br > 1.0 + _TOL:
            bound_violations += 1
        s_can = _crt_score(r, canonical_br)
        s_cur = _crt_score(r, current_br)
        ds = s_cur - s_can
        score_deltas.append(abs(ds))
        if abs(ds) > _TOL:
            score_differ += 1
        if ds > _TOL:
            score_up += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "bars": n,
        "gd_ids": ["GD-001", "GD-002"],
        "value_drift": {
            "bars_differ": value_differ, "differ_rate": value_differ / n if n else 0.0,
            "current_ge_canonical_rate": current_ge_canonical / n if n else 0.0,
            "bound_violations_gt1": bound_violations,
            "bound_violation_rate": bound_violations / n if n else 0.0,
            "abs_body_ratio_delta": _stats(br_deltas),
            "abs_wick_size_delta": _stats(ws_deltas),
        },
        "crt_score_drift": {
            "bars_score_differ": score_differ, "score_differ_rate": score_differ / n if n else 0.0,
            "score_inflated_rate": score_up / n if n else 0.0,
            "abs_score_delta": _stats(score_deltas),
        },
        "scope_caveat": ("CRT-score delta is the necessary channel to a fusion flip; live-hook path is "
                         "F-010-unverified and backtests bypass it (F-037). Bounds potential impact only."),
    }


def _to_md(rep: dict) -> str:
    v, s = rep["value_drift"], rep["crt_score_drift"]
    return "\n".join([
        f"# Feature-Math Drift Probe — GD-001/GD-002 (Matrix v2 measurement)",
        "",
        f"_Generated {rep['generated_at']} · symbol {rep['symbol']} · {rep['bars']} bars · read-only._",
        "",
        "## Value drift (canonical body/candle_range vs current body/total_wick)",
        f"- bars where the two differ: **{v['bars_differ']}** ({v['differ_rate']:.1%})",
        f"- current ≥ canonical (systematic inflation): **{v['current_ge_canonical_rate']:.1%}**",
        f"- current body_ratio > 1.0 (bound violation, impossible for canonical): **{v['bound_violations_gt1']}** ({v['bound_violation_rate']:.2%})",
        f"- |Δ body_ratio|: mean {v['abs_body_ratio_delta'].get('mean',0):.4f} · median {v['abs_body_ratio_delta'].get('median',0):.4f} · p95 {v['abs_body_ratio_delta'].get('p95',0):.4f} · max {v['abs_body_ratio_delta'].get('max',0):.4f}",
        "",
        "## CRT-score drift (real crt_engine.compute, canonical vs current body_ratio, all else fixed)",
        f"- bars where the CRT score changes: **{s['bars_score_differ']}** ({s['score_differ_rate']:.1%})",
        f"- CRT score inflated by the current formula: **{s['score_inflated_rate']:.1%}**",
        f"- |Δ CRT score|: mean {s['abs_score_delta'].get('mean',0):.4f} · median {s['abs_score_delta'].get('median',0):.4f} · p95 {s['abs_score_delta'].get('p95',0):.4f} · max {s['abs_score_delta'].get('max',0):.4f}",
        "",
        f"> {rep['scope_caveat']}",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate-2 feature-math drift probe (read-only).")
    ap.add_argument("--symbol", default="BNBUSDT")
    ap.add_argument("--limit", type=int, default=30000, help="max bars (0 = all)")
    args = ap.parse_args()

    rep = run_probe(args.symbol, args.limit)
    out = _ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "feature-math-drift-probe.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (out / "feature-math-drift-probe.md").write_text(_to_md(rep), encoding="utf-8")
    v, s = rep["value_drift"], rep["crt_score_drift"]
    print(f"drift probe → reports/feature-math-drift-probe.{{json,md}}  ({rep['symbol']}, {rep['bars']} bars)")
    print(f"  value differ {v['differ_rate']:.1%} · current≥canonical {v['current_ge_canonical_rate']:.1%} · "
          f">1 violations {v['bound_violations_gt1']} ({v['bound_violation_rate']:.2%})")
    print(f"  CRT-score differ {s['score_differ_rate']:.1%} · inflated {s['score_inflated_rate']:.1%} · "
          f"|Δscore| p95 {s['abs_score_delta'].get('p95',0):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
