# -*- coding: utf-8 -*-
"""
bnbusdt_conditional_edge.py — READ-ONLY Simpson's-paradox / conditional-edge audit.

Tests whether the aggregate "no edge on BNBUSDT" hides a conditional pocket where a behavior
beats the random_uniform control on REALIZED NET EXPECTANCY. Strict discipline (lessons from
the adversarial audit):
  * realized net expectancy only — never the (low-power) opportunity profile
  * every bucket compared to random_uniform IN THE SAME BUCKET (never to zero)
  * Benjamini-Hochberg across ALL bucket tests (reused from qualification.py)
  * survivor requires bh_q<0.05 AND |ΔE|>0.05R (significance alone is not enough)
  * survivors (pos & neg) get a year_breakdown; consistency > magnitude
  * a survivor is a PRE-REGISTERED OOS CANDIDATE, never an edge.

Read-only: consumes existing trades.jsonl, writes only results/research/bnbusdt_conditional_edge.json.

Usage: python scripts/research/bnbusdt_conditional_edge.py
"""

import json
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.qualification import permutation_p_value   # noqa: E402  (reuse M4 machinery)
from utils.console_safe import safe_print                # noqa: E402

_HYPS = ("expansion_breakout", "mean_reversion")
_MIN_N = 50
_POWER_N = 100
_N_PERM = 2000
_Q = 0.05
_DELTA = 0.05            # economic effect-size floor (R)
_TREND_EPS = 0.1


def _load(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def _seed(*parts) -> int:
    import hashlib
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _atr_quartile_fn(control: list[dict]):
    atrs = sorted(r["atr"] for r in control)
    q = [atrs[int(len(atrs) * f)] for f in (0.25, 0.5, 0.75)]
    def fn(r):
        a = r["atr"]
        return "Q1" if a <= q[0] else "Q2" if a <= q[1] else "Q3" if a <= q[2] else "Q4"
    return fn


def _trend(r):
    t = r.get("trend_proxy", 0.0)
    return "up" if t > _TREND_EPS else "down" if t < -_TREND_EPS else "flat"


def _bh_qvalues(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values (monotone), aligned to the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, pvals[i] * m / rank)
        q[i] = round(prev, 6)
    return q


def _net(rows):
    return [r["rr_net_intrabar"] for r in rows]


def _bucket_cuts(records, atr_fn):
    yield "direction", lambda r: r["direction"]
    yield "atr_quartile", atr_fn
    yield "hour", lambda r: r["hour"]
    yield "day_of_week", lambda r: r["dow"]
    yield "month", lambda r: r["month"]
    yield "trend_proxy", _trend


def _year_breakdown(rows) -> dict:
    out = {}
    for y in ("2024", "2025", "2026"):
        yr = [r["rr_net_intrabar"] for r in rows if r["timestamp"][:4] == y]
        out[y] = {"n": len(yr), "expectancy": round(statistics.mean(yr), 4) if yr else None}
    return out


def main() -> int:
    ctrl = _load(_ROOT / "results/research/_controls/bnbusdt/random_uniform/trades.jsonl")
    atr_fn = _atr_quartile_fn(ctrl)

    all_tests = []
    survivor_rows = {}   # id -> hyp rows (for year_breakdown)
    for hyp in _HYPS:
        hrecs = _load(_ROOT / f"results/research/bnbusdt/{hyp}/trades.jsonl")
        for cut_name, key_fn in _bucket_cuts(hrecs, atr_fn):
            values = sorted({key_fn(r) for r in hrecs}, key=str)
            for v in values:
                hb = [r for r in hrecs if key_fn(r) == v]
                cb = [r for r in ctrl if key_fn(r) == v]
                if min(len(hb), len(cb)) < _MIN_N:
                    continue
                hr, cr = _net(hb), _net(cb)
                eh, ec = statistics.mean(hr), statistics.mean(cr)
                delta = eh - ec
                # two-sided p via the observed-direction one-sided permutation (reused fn).
                if delta >= 0:
                    p_one = permutation_p_value(hr, cr, _N_PERM, _seed(hyp, cut_name, v))
                else:
                    p_one = permutation_p_value(cr, hr, _N_PERM, _seed(hyp, cut_name, v))
                p_two = min(1.0, 2 * p_one)
                pooled_sd = statistics.pstdev(hr + cr) or 1.0
                all_tests.append({
                    "behavior": hyp, "bucket_name": cut_name, "bucket_value": str(v),
                    "n_hypothesis": len(hb), "n_control": len(cb),
                    "expectancy_hypothesis": round(eh, 4), "expectancy_control": round(ec, 4),
                    "delta_expectancy": round(delta, 4),
                    "effect_size_r": round(delta / pooled_sd, 4),
                    "p_raw": round(p_two, 6),
                    "power_warning": min(len(hb), len(cb)) < _POWER_N,
                })
                survivor_rows[(hyp, cut_name, str(v))] = hb

    qs = _bh_qvalues([t["p_raw"] for t in all_tests])
    for t, q in zip(all_tests, qs):
        t["bh_q"] = q

    pos, neg = [], []
    for t in all_tests:
        if t["bh_q"] < _Q and t["delta_expectancy"] > _DELTA:
            t2 = dict(t, year_breakdown=_year_breakdown(
                survivor_rows[(t["behavior"], t["bucket_name"], t["bucket_value"])]))
            pos.append(t2)
        elif t["bh_q"] < _Q and t["delta_expectancy"] < -_DELTA:
            t2 = dict(t, year_breakdown=_year_breakdown(
                survivor_rows[(t["behavior"], t["bucket_name"], t["bucket_value"])]))
            neg.append(t2)

    by_delta = sorted(all_tests, key=lambda t: t["delta_expectancy"])
    report = {
        "metadata": {
            "instrument": "BNBUSDT", "control": "random_uniform",
            "min_n": _MIN_N, "power_n": _POWER_N, "n_permutations": _N_PERM,
            "bh_alpha": _Q, "effect_size_floor_r": _DELTA,
            "axis": "realized_net_expectancy", "note": "opportunity-profile metrics NOT used",
        },
        "all_tests": all_tests,
        "bh_survivors": pos,
        "negative_survivors": neg,
        "largest_positive_deltas": by_delta[-10:][::-1],
        "largest_negative_deltas": by_delta[:10],
        "summary": {
            "number_of_tests": len(all_tests),
            "number_of_bh_survivors": len(pos),
            "number_of_negative_survivors": len(neg),
            "aggregate_world_A_survived_conditionally": len(pos) == 0,
            "reminder": "Any survivor is a PRE-REGISTERED OOS CANDIDATE, not evidence of an edge.",
        },
    }
    out = _ROOT / "results/research/bnbusdt_conditional_edge.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    s = report["summary"]
    safe_print(f"  tests={s['number_of_tests']}  bh_survivors={s['number_of_bh_survivors']}  "
               f"negative_survivors={s['number_of_negative_survivors']}  "
               f"conditional_world_A={s['aggregate_world_A_survived_conditionally']}")
    for t in pos:
        safe_print(f"  [+SURVIVOR] {t['behavior']} {t['bucket_name']}={t['bucket_value']} "
                   f"dE={t['delta_expectancy']:+.3f} q={t['bh_q']:.4f} "
                   f"(power_warning={t['power_warning']})")
    for t in neg:
        safe_print(f"  [-SURVIVOR] {t['behavior']} {t['bucket_name']}={t['bucket_value']} "
                   f"dE={t['delta_expectancy']:+.3f} q={t['bh_q']:.4f}")
    safe_print(f"\n  report -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
