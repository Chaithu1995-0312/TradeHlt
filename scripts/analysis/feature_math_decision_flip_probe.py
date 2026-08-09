"""
feature_math_decision_flip_probe.py — Gate-2 Step 7c (READ-ONLY).

Answers the narrow causal question the score-drift probe could NOT: *does canonicalizing GD-001/GD-002
(body_ratio) change actual system DECISIONS, how often, and in which direction?* — measured at the REAL
`EngineRunner.run()` fusion/decision boundary (decision ∈ {execute, reject, HOLD}), not the intermediate
CRT score. No P&L (that is a separate causal layer).

Two branches per candle, identical in EVERYTHING except body_ratio (wick_size overridden too; only
body_ratio is consumed downstream, so GD-002 is captured jointly as GD-001's denominator):
    Branch B (canonical) = body_size / candle_range          (feature_pipeline value)
    Branch A (current)   = body_size / total_wick             (live_engine_hook.py:360-362)

Isolation of the adaptive controllers (DynamicThreshold / AcceptanceController / ConvergenceController /
ScoreNormalizer), so A and B see the SAME state at each candle:
  • ADAPTIVE (primary): one reference runner advances along the CANONICAL trajectory; at each candle A is
    evaluated on a deepcopy (same evolved state S_t), B commits. Faithful to the live adaptive boundary.
  • FROZEN (sensitivity): both branches run on deepcopies of the NEVER-advanced init runner → thresholds
    stay at config defaults (fusion 0.25, decision 0.55) → isolates the pure body_ratio→decision effect.

STRICTLY READ-ONLY: reads a CSV + the frozen config/pipeline; run()'s fail-open telemetry is silenced
(logging disabled, debug_mode off). Writes ONLY to reports/. Does NOT import/modify the 10 divergent sites
(it replicates live_engine_hook's arithmetic to build Branch A). Deterministic (no RNG in decision path).

Usage: python scripts/analysis/feature_math_decision_flip_probe.py [--symbol BNBUSDT] [--limit 0]
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

logging.disable(logging.CRITICAL)  # silence run() telemetry loggers (COLLECTOR / snapshots)

import pandas as pd  # noqa: E402

from config_layer.production_config import get_prod_metadata, PROD_VERSION  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from core.engine_runner import EngineRunner  # noqa: E402

# Feature-pipeline session encoding (features.feature_schema.SESSION_MAP): london=0, newyork=1,
# asian=2, overlap=3. The adapter (trap_validator) reads a DIFFERENT int map (0=asia,1=london,2=new_york),
# so we must pass the STRING session to the adapter, not the pipeline int (else london is misread as asia).
_PIPE_SESSION_STR = {0: "london", 1: "newyork", 2: "asia", 3: "overlap"}
# Reasons where the DECISION hinged on the SCORE (body_ratio-sensitive) vs a hard veto (zone/session/regime).
_SCORE_GATED_REASONS = {"low_score", "low_fusion_score", "all_conditions_met", "execute"}


def _merged_config() -> dict:
    md = get_prod_metadata()
    merged: dict = {}
    merged.update(md["engine_runner"])
    merged.update(md["decision_engine"])
    merged["fusion_engine"] = md["fusion_engine"]
    merged["ultron_risk_gate"] = md["ultron_risk_gate"]
    merged["execution_planner"] = md["execution_planner"]
    merged["debug_mode"] = False
    return merged


def _current_body_ratio_wick(o, h, l, c):
    """Replicate live_engine_hook.py:360-362 exactly (read-only reproduction)."""
    body = abs(c - o)
    tw = max(0.0, (h - l) - body)
    br = body / tw if tw > 1e-8 else 0.0
    return br, tw


def _build_input(row, body_ratio, wick_size):
    inp = {n: float(row[n]) for n in CANONICAL_FEATURES if n in row.index}
    inp["body_ratio"] = float(body_ratio)
    inp["wick_size"] = float(wick_size)
    inp["close"] = float(row["close"]); inp["high"] = float(row["high"])
    inp["low"] = float(row["low"]); inp["open"] = float(row["open"])
    inp["volume"] = float(row["volume"]); inp["atr"] = float(row["atr"])
    inp["timestamp"] = str(row.get("timestamp", ""))
    inp["session"] = _PIPE_SESSION_STR.get(int(row.get("session", -1)), "london")  # STRING (see note above)
    inp["_data_integrity"] = "real"
    # direction is identical for A/B (body_ratio doesn't set it); derive from trend_bias for realism.
    tb = float(row.get("trend_bias", 0.0))
    d = 1 if tb > 0 else (-1 if tb < 0 else 1)
    inp["direction"] = d; inp["signal_dir"] = d; inp["trade_direction"] = d
    return inp


def _install_zone_bypass():
    """Replicate backtest_v2's BACKTEST_BYPASS_ZONE_INVALID in-process (read-only CLASS-level monkeypatch).
    DecisionEngine:129 rejects with 'zone_gate_invalid' unless zone_gate['valid'] is True, but run()'s
    zone_result never sets that flag → it rejects EVERY candle. That gate is ORTHOGONAL to body_ratio
    (identical for A and B); bypassing it (as the backtest does) lets candles reach the score/p_win/rr/weak
    gates where body_ratio actually acts. CLASS-level (not instance) so deepcopy(runner) probes resolve
    `self` to the COPY's own dynamic-threshold state — instance patching would leak state across the A/B
    isolation via the captured closure."""
    from core.decision_engine import DecisionEngine
    if getattr(DecisionEngine, "_zone_bypassed", False):
        return
    orig = DecisionEngine.evaluate

    def patched(self, *args, **kwargs):
        if "zone_gate" in kwargs and isinstance(kwargs["zone_gate"], dict):
            kwargs["zone_gate"] = {**kwargs["zone_gate"], "valid": True}
        else:
            a = list(args)
            if len(a) >= 3 and isinstance(a[2], dict):
                a[2] = {**a[2], "valid": True}
                args = tuple(a)
        return orig(self, *args, **kwargs)

    DecisionEngine.evaluate = patched
    DecisionEngine._zone_bypassed = True


def _approve(res: dict) -> bool:
    dec = (res or {}).get("decision") or (res or {}).get("status", "")
    return str(dec).lower() == "execute"


def _stats(xs):
    if not xs:
        return {"n": 0}
    s = sorted(xs)
    return {"n": len(s), "median": statistics.median(s),
            "p95": s[min(len(s) - 1, int(0.95 * len(s)))], "max": s[-1]}


def _decile(score, sorted_scores):
    import bisect
    if not sorted_scores:
        return 0
    rank = bisect.bisect_left(sorted_scores, score)
    return min(9, int(10 * rank / len(sorted_scores)))  # 0..9


def run_probe(symbol: str, limit: int) -> dict:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    if limit:
        df = df.head(limit).copy()
    feat_df, _ = FeaturePipeline(df).run()

    _install_zone_bypass()             # zone gate is orthogonal to body_ratio; bypass like backtest
    cfg = _merged_config()
    runner_ref = EngineRunner(cfg)     # ADAPTIVE: advances along canonical (Branch B)
    runner_init = EngineRunner(cfg)    # FROZEN: never advanced (deepcopied per candle)
    ctx = {"instrument": symbol, "timeframe": "M15"}

    ev = []            # per-candle records (adaptive)
    for _, r in feat_df.iterrows():
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        canon_br = float(r["body_ratio"]); canon_ws = h - l
        cur_br, cur_ws = _current_body_ratio_wick(o, h, l, c)
        inA = _build_input(r, cur_br, cur_ws)
        inB = _build_input(r, canon_br, canon_ws)

        # ADAPTIVE: same evolved state S_t for A and B (probe = deepcopy before ref commits)
        probe = copy.deepcopy(runner_ref)
        resA = probe.run(inA, ctx)
        resB = runner_ref.run(inB, ctx)   # commits → advances S

        # FROZEN: both on a never-advanced init copy (fixed default thresholds)
        fa, fb = copy.deepcopy(runner_init), copy.deepcopy(runner_init)
        frA, frB = fa.run(inA, ctx), fb.run(inB, ctx)

        ev.append({
            "session": _PIPE_SESSION_STR.get(int(r.get("session", -1)), "unknown"),
            "regime": str((resB or {}).get("regime") or "unknown"),
            "apA": _approve(resA), "apB": _approve(resB),
            "scoreB": float((resB or {}).get("final_score", 0.0) or 0.0),
            "thrB": float((resB or {}).get("threshold_used", 0.0) or 0.0),
            "stageA": str((resA or {}).get("reject_stage") or "?"),
            "stageB": str((resB or {}).get("reject_stage") or "?"),
            "reasonA": str((resA or {}).get("reason") or "?"),
            "reasonB": str((resB or {}).get("reason") or "?"),
            "fr_apA": _approve(frA), "fr_apB": _approve(frB),
        })

    return _summarize(symbol, feat_df, ev)


def _summarize(symbol, feat_df, ev) -> dict:
    n = len(ev)
    sorted_scores = sorted(e["scoreB"] for e in ev)

    def block(apA_key, apB_key, tag):
        flips = [e for e in ev if e[apA_key] != e[apB_key]]
        add = sum(1 for e in flips if e[apB_key] and not e[apA_key])   # canonical executes, current rejects → ADD
        rem = sum(1 for e in flips if e[apA_key] and not e[apB_key])   # current executes, canonical rejects → REMOVE
        return {
            "tag": tag,
            "approve_current_A": sum(1 for e in ev if e[apA_key]),
            "approve_canonical_B": sum(1 for e in ev if e[apB_key]),
            "flips": len(flips), "flip_rate": len(flips) / n if n else 0.0,
            "canonicalizing_adds_trade": add, "canonicalizing_removes_trade": rem,
        }

    adaptive = block("apA", "apB", "adaptive")
    frozen = block("fr_apA", "fr_apB", "frozen")

    # Conditional denominator: SCORE-GATED candles — those where the decision actually hinged on the
    # fused SCORE (reason ∈ low_score/low_fusion_score/execute), i.e. they passed the body_ratio-INDEPENDENT
    # hard vetoes (zone-hard in-zone, session, engine-completeness, belief, regime/ultron). Body_ratio can
    # ONLY flip a decision within this set. The raw all-candle rate is diluted because the zone-hard gate +
    # session veto reject the vast majority regardless of body_ratio (and this harness evaluates every bar,
    # not just CRT-state-gated setups like the live spine).
    reachable = [e for e in ev
                 if e["reasonB"] in _SCORE_GATED_REASONS or e["reasonA"] in _SCORE_GATED_REASONS]
    ad_flips = [e for e in reachable if e["apA"] != e["apB"]]
    adaptive["score_gated_candles"] = len(reachable)
    adaptive["conditional_flip_rate"] = len(ad_flips) / len(reachable) if reachable else 0.0
    # hard-veto histogram (what absorbs body_ratio) — top reasons on the canonical branch
    _reasons: dict = {}
    for e in ev:
        _reasons[e["reasonB"]] = _reasons.get(e["reasonB"], 0) + 1
    adaptive["reasonB_histogram"] = dict(sorted(_reasons.items(), key=lambda kv: -kv[1])[:8])

    # among ADAPTIVE flips: distance-to-threshold + which gate produced the reject
    flips = [e for e in ev if e["apA"] != e["apB"]]
    dist_fusion = [abs(e["scoreB"] - 0.25) for e in flips]
    dist_decision = [abs(e["scoreB"] - e["thrB"]) for e in flips if e["thrB"] > 0]
    stage_bucket: dict = {}
    for e in flips:
        stg = e["stageB"] if not e["apB"] else e["stageA"]   # the rejecting branch's stage
        stage_bucket[stg] = stage_bucket.get(stg, 0) + 1

    def rate_by(keyfn):
        agg: dict = {}
        for e in ev:
            k = keyfn(e)
            a = agg.setdefault(k, [0, 0])
            a[1] += 1
            if e["apA"] != e["apB"]:
                a[0] += 1
        return {k: {"flips": v[0], "n": v[1], "rate": v[0] / v[1] if v[1] else 0.0}
                for k, v in sorted(agg.items())}

    by_decile = {}
    for e in ev:
        d = _decile(e["scoreB"], sorted_scores)
        a = by_decile.setdefault(d, [0, 0]); a[1] += 1
        if e["apA"] != e["apB"]:
            a[0] += 1
    by_decile = {f"d{k}": {"flips": v[0], "n": v[1], "rate": v[0] / v[1] if v[1] else 0.0}
                 for k, v in sorted(by_decile.items())}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "config_version": PROD_VERSION, "events": n,
        "gd_ids": ["GD-001", "GD-002"],
        "adaptive": adaptive, "frozen": frozen,
        "distance_to_threshold_among_adaptive_flips": {
            "abs_fusion_gap_final_minus_0.25": _stats(dist_fusion),
            "abs_decision_gap_final_minus_dyn": _stats(dist_decision),
        },
        "adaptive_flip_by_reject_stage": stage_bucket,
        "adaptive_flip_rate_by_regime": rate_by(lambda e: e["regime"]),
        "adaptive_flip_rate_by_session": rate_by(lambda e: e["session"]),
        "adaptive_flip_rate_by_score_decile": by_decile,
        "scope_caveat": ("Decision-flip at the REAL fusion/decision boundary. NO P&L. live-hook path is "
                         "F-010-unverified and backtests bypass it (F-037) → bounds potential impact only, "
                         "NOT a production-loss claim."),
    }


def _to_md(r: dict) -> str:
    ad, fr = r["adaptive"], r["frozen"]
    d = r["distance_to_threshold_among_adaptive_flips"]
    lines = [
        "# Feature-Math Decision-Flip Probe — GD-001/GD-002 (Gate-2 Step 7c)",
        "",
        f"_Generated {r['generated_at']} · {r['symbol']} · {r['config_version']} · {r['events']} events · read-only._",
        "",
        "Branch A = current (body/total_wick) vs Branch B = canonical (body/candle_range), all else fixed;"
        " decision = real EngineRunner.run() APPROVE(execute)/REJECT.",
        "",
        "## Decision flips",
        "| mode | approve A (current) | approve B (canonical) | flips | flip rate | canonicalizing ADDS | REMOVES |",
        "|---|---|---|---|---|---|---|",
        f"| adaptive (real boundary) | {ad['approve_current_A']} | {ad['approve_canonical_B']} | "
        f"**{ad['flips']}** | **{ad['flip_rate']:.3%}** | {ad['canonicalizing_adds_trade']} | {ad['canonicalizing_removes_trade']} |",
        f"| frozen (fixed thresholds) | {fr['approve_current_A']} | {fr['approve_canonical_B']} | "
        f"{fr['flips']} | {fr['flip_rate']:.3%} | {fr['canonicalizing_adds_trade']} | {fr['canonicalizing_removes_trade']} |",
        "",
        f"Distance-to-threshold among adaptive flips — |final−0.25| median {d['abs_fusion_gap_final_minus_0.25'].get('median',0):.4f} p95 {d['abs_fusion_gap_final_minus_0.25'].get('p95',0):.4f}; "
        f"|final−dyn| median {d['abs_decision_gap_final_minus_dyn'].get('median',0):.4f} p95 {d['abs_decision_gap_final_minus_dyn'].get('p95',0):.4f}",
        "",
        f"Flip by reject-stage: {r['adaptive_flip_by_reject_stage']}",
        f"Flip rate by regime: { {k: round(v['rate'],4) for k,v in r['adaptive_flip_rate_by_regime'].items()} }",
        f"Flip rate by session: { {k: round(v['rate'],4) for k,v in r['adaptive_flip_rate_by_session'].items()} }",
        f"Flip rate by score-decile: { {k: round(v['rate'],4) for k,v in r['adaptive_flip_rate_by_score_decile'].items()} }",
        "",
        f"> {r['scope_caveat']}",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate-2 Step 7c decision-flip probe (read-only).")
    ap.add_argument("--symbol", default="BNBUSDT")
    ap.add_argument("--limit", type=int, default=0, help="max raw candles (0 = all)")
    args = ap.parse_args()

    rep = run_probe(args.symbol, args.limit)
    out = _ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "feature-math-decision-flip-probe.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (out / "feature-math-decision-flip-probe.md").write_text(_to_md(rep), encoding="utf-8")
    ad, fr = rep["adaptive"], rep["frozen"]
    print(f"decision-flip probe → reports/feature-math-decision-flip-probe.{{json,md}}  ({rep['symbol']}, {rep['events']} events)")
    print(f"  ADAPTIVE flip rate {ad['flip_rate']:.3%}  ({ad['flips']} flips: +{ad['canonicalizing_adds_trade']} / -{ad['canonicalizing_removes_trade']})")
    print(f"  conditional (score-gated candles, n={ad['score_gated_candles']}): {ad['conditional_flip_rate']:.3%}")
    print(f"  reasonB histogram: {ad['reasonB_histogram']}")
    print(f"  FROZEN   flip rate {fr['flip_rate']:.3%}  ({fr['flips']} flips)")
    print(f"  approve current {ad['approve_current_A']} vs canonical {ad['approve_canonical_B']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
