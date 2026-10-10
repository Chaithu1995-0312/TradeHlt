"""
outcome_policy_pilot.py
Pilot: does the previous completed CRT opportunity's outcome carry information
about the next opportunity's direction?  (direction-selection mode only)

Read-only analysis over FROZEN trade lists produced by backtest_v2.py. No engine
code runs here. Policies (pre-registered):
  A reverse after loss   : after a loss the next signal must be the opposite direction
  B continue after win   : after a win  the next signal must be the same direction
  C opposite controls    : after a win reverse, after a loss retain
  D baseline             : take every signal
A branch a policy does not name takes any signal. The first opportunity is taken.
Win = net R > 0, loss = net R <= 0. The conditioning chain runs over ALL frozen
opportunities (each classified by its own as-if-taken outcome); windows only
bucket the candidate: open = Monday, middle = Tue-Thu, close = Friday (file/UTC time).

Usage:
    python scripts/analysis/outcome_policy_pilot.py \
        --trades m15=results/.../m15_trades.csv h1=results/.../h1_trades.csv \
        --cutoff 2025-05-22 --floor 3 --out results/outcome_policy_pilot
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as st
from datetime import datetime
from pathlib import Path

POLICIES = ("A", "B", "C", "D")
WINDOWS = ("open", "middle", "close", "all")
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
         9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.16, 14: 2.145, 15: 2.131}


def load(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["trade_id"], "dir": r["direction"],
                "opened": datetime.fromisoformat(r["opened_at"]),
                "closed": datetime.fromisoformat(r["closed_at"]),
                "net": float(r["pnl_rr_net"]), "raw": float(r["pnl_rr_raw"]),
                "cost_pips": float(r["slippage_pips"]) + float(r["spread_pips"]),
                "exit": r["exit_reason"],
            })
    rows.sort(key=lambda x: x["opened"])
    for a, b in zip(rows, rows[1:]):
        assert a["closed"] < b["opened"], "overlapping trades: previous would still be open"
    return rows


def window_of(ts: datetime) -> str:
    wd = ts.weekday()
    return "open" if wd == 0 else "close" if wd == 4 else "middle"


def allowed(policy: str, prev: dict | None, cand: dict) -> bool:
    if prev is None or policy == "D":
        return True
    prev_win = prev["net"] > 0
    same = cand["dir"] == prev["dir"]
    if policy == "A":
        return True if prev_win else (not same)
    if policy == "B":
        return same if prev_win else True
    if policy == "C":
        return (not same) if prev_win else same
    raise ValueError(policy)


def taken(rows: list[dict], policy: str) -> list[dict]:
    out = []
    for i, cand in enumerate(rows):
        prev = rows[i - 1] if i > 0 else None
        if allowed(policy, prev, cand):
            out.append(cand)
    return out


def metrics(sel: list[dict]) -> dict:
    n = len(sel)
    if n == 0:
        return {"n": 0}
    net = [x["net"] for x in sel]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v <= 0]
    peak = cum = dd = 0.0
    for v in net:
        cum += v
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    m = st.mean(net)
    ci = None
    if n >= 2:
        se = st.stdev(net) / math.sqrt(n)
        t = _T975.get(n - 1, 1.96)
        ci = (round(m - t * se, 2), round(m + t * se, 2))
    return {
        "n": n, "exp": round(m, 3), "ci95": ci,
        "pf": ("inf" if not losses and wins else round(sum(wins) / abs(sum(losses)), 2) if losses and wins else 0.0),
        "wr": round(len(wins) / n, 3), "dd": round(dd, 2),
        "cost_r": round(st.mean(x["raw"] - x["net"] for x in sel), 3),
        "cost_pips": round(st.mean(x["cost_pips"] for x in sel), 1),
    }


def fmt(m: dict) -> str:
    if m["n"] == 0:
        return "| 0 | - | - | - | - | - | - |"
    ci = f"[{m['ci95'][0]}, {m['ci95'][1]}]" if m["ci95"] else "n/a"
    return f"| {m['n']} | {m['exp']:+.3f} {ci} | {m['pf']} | {m['wr']:.0%} | {m['dd']} | {m['cost_r']} | {m['cost_pips']} |"


def table(rows: list[dict]) -> str:
    lines = ["| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for p in POLICIES:
        sel_all = taken(rows, p)
        for w in WINDOWS:
            sel = sel_all if w == "all" else [x for x in sel_all if window_of(x["opened"]) == w]
            lines.append(f"| {p} | {w} " + fmt(metrics(sel)))
    return "\n".join(lines)


def fisher_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]]."""
    def pmf(x: int) -> float:
        return math.comb(a + b, x) * math.comb(c + d, a + c - x) / math.comb(a + b + c + d, a + c)
    obs = pmf(a)
    lo, hi = max(0, a + c - (c + d)), min(a + b, a + c)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= obs + 1e-12))


def transitions(rows: list[dict]) -> str:
    """Descriptive, all periods: next trade's win rate by previous outcome x direction relation."""
    cells = {}
    for prev, cand in zip(rows, rows[1:]):
        key = ("prev win" if prev["net"] > 0 else "prev loss", "same dir" if cand["dir"] == prev["dir"] else "reverse")
        cells.setdefault(key, []).append(cand["net"] > 0)
    lines = ["| Previous | Relation to previous direction | next trades | next wins |", "|---|---|---|---|"]
    for k in sorted(cells):
        lines.append(f"| {k[0]} | {k[1]} | {len(cells[k])} | {sum(cells[k])} |")
    for pv in ("prev loss", "prev win"):
        same, rev = cells.get((pv, "same dir"), []), cells.get((pv, "reverse"), [])
        if same and rev:
            p = fisher_p(sum(same), len(same) - sum(same), sum(rev), len(rev) - sum(rev))
            lines.append(f"\nFisher exact, {pv}: same-vs-reverse win rate {sum(same)}/{len(same)} vs {sum(rev)}/{len(rev)}, p = {p:.2f}")
    return "\n".join(lines)


def select(dev: list[dict], floor: int) -> tuple[str | None, dict]:
    base = metrics(taken(dev, "D"))
    info = {"D": base}
    best, best_exp = None, None
    for p in ("A", "B", "C"):
        m = metrics(taken(dev, p))
        info[p] = m
        if m["n"] >= floor and base["n"] and m["exp"] > base["exp"]:
            if best_exp is None or m["exp"] > best_exp:
                best, best_exp = p, m["exp"]
    return best, info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", nargs="+", required=True, help="label=path.csv ...")
    ap.add_argument("--cutoff", required=True, help="first hold-out date YYYY-MM-DD")
    ap.add_argument("--floor", type=int, required=True, help="min dev trades for a policy to be eligible")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cutoff = datetime.fromisoformat(a.cutoff)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    md, js = [], {}
    for item in a.trades:
        label, path = item.split("=", 1)
        sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        rows = load(path)
        dev = [r for r in rows if r["opened"] < cutoff]
        hold = [r for r in rows if r["opened"] >= cutoff]
        # conditioning chain is global; split only by candidate date
        dev_idx = {r["id"] for r in dev}
        def taken_in(period_ids, policy):
            return [r for r in taken(rows, policy) if r["id"] in period_ids]
        def table_period(ids, pols):
            lines = ["| Policy | Window | n | Net exp. R [95% CI] | PF | WR | MaxDD (R) | Cost (R/trade) | Cost (pips/trade) |",
                     "|---|---|---|---|---|---|---|---|---|"]
            for p in pols:
                s_all = taken_in(ids, p)
                for w in WINDOWS:
                    s = s_all if w == "all" else [x for x in s_all if window_of(x["opened"]) == w]
                    lines.append(f"| {p} | {w} " + fmt(metrics(s)))
            return "\n".join(lines)
        sel_info, sel_metrics = None, {}
        base = metrics(taken_in(dev_idx, "D"))
        best, best_exp = None, None
        for p in ("A", "B", "C"):
            m = metrics(taken_in(dev_idx, p)); sel_metrics[p] = m
            if m["n"] >= a.floor and base["n"] and m["exp"] > base["exp"] and (best_exp is None or m["exp"] > best_exp):
                best, best_exp = p, m["exp"]
        md.append(f"## {label}\nFrozen list: `{Path(path).name}` sha256 `{sha}`; opportunities {len(rows)} "
                  f"(development {len(dev)}, hold-out {len(hold)}); per-window opportunity counts "
                  f"(all periods): " + ", ".join(f"{w}={sum(1 for r in rows if window_of(r['opened'])==w)}" for w in ("open", "middle", "close")) + "\n")
        md.append(f"### Development period (< {a.cutoff}) — all policies\n" + table_period(dev_idx, POLICIES) + "\n")
        md.append(f"### Selection (pre-registered: eligible = A/B/C with dev n >= {a.floor} and dev expectancy > D's {base.get('exp')}; pick the highest)\n"
                  f"Selected: **{best or 'none'}**\n")
        if best:
            ids = {r["id"] for r in hold}
            md.append(f"### Hold-out (>= {a.cutoff}) — selected policy {best} vs D, evaluated once\n" + table_period(ids, (best, "D")) + "\n")
        else:
            md.append("### Hold-out: not opened (no policy selected; it stays untouched)\n")
        md.append("### Descriptive transitions (all opportunities, not used for selection)\n" + transitions(rows) + "\n")
        js[label] = {"sha256": sha, "n": len(rows), "dev": len(dev), "hold": len(hold), "selected": best, "dev_metrics": {"D": base, **sel_metrics}}
    (out / "tables.md").write_text("\n".join(md), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(js, indent=2), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
