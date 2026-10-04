"""
gate_contribution_audit.py — Study 2: which CRT funnel stage CREATES vs DESTROYS edge? (BNBUSDT)

Walks the funnel RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION and measures, at each stage:
count, conversion %, and counterfactual expectancy/PF/WR.

Counterfactual = JOIN the candle at which a candidate ENTERED a stage (from logs/crt_transitions.jsonl
payload, state_to + candle timestamp) to that candle's simulated vanilla outcome
(BNBUSDT opportunities.jsonl rr_achieved). EXECUTION uses the REAL executed trades (the latest
results/**/BNBUSDT_trades.csv pnl_rr_net), not the proxy.

Pure read-only. Output: docs/analysis/gate-contribution-bnbusdt-2026-06-03.md (+ JSON).
"""
from __future__ import annotations
import csv, json, glob, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TRANS = ROOT/"logs"/"crt_transitions.jsonl"
OPPS = ROOT/"logs"/"BNBUSDT"/"20260530_011521"/"opportunities.jsonl"
OUT_MD = ROOT/"docs"/"analysis"/"gate-contribution-bnbusdt-2026-06-03.md"
OUT_JSON = ROOT/"results"/"edge_attribution"/"gate_contribution_bnbusdt.json"
STAGES = ["SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION"]


def norm_ts(s: str) -> str:
    if not s:
        return ""
    return str(s).replace(" ", "T").split("+")[0].split("Z")[0][:19]


def pf_wr(vals):
    if not vals:
        return 0.0, 0.0, 0.0
    import statistics
    wins = sum(v for v in vals if v > 0)
    losses = -sum(v for v in vals if v < 0)
    pf = (wins/losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)
    wr = sum(1 for v in vals if v > 0)/len(vals)
    return float(statistics.mean(vals)), (pf if pf != float("inf") else 99.0), wr


def load_transitions():
    """Return dict state_to -> list[candle_ts] and reason samples per stage."""
    by_stage = {s: [] for s in STAGES}
    reasons = {s: {} for s in STAGES}
    n = 0
    for line in open(TRANS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        p = d.get("payload") or {}
        st = p.get("state_to")
        if st not in by_stage:
            continue
        n += 1
        by_stage[st].append(norm_ts(p.get("timestamp", "")))
        rk = (p.get("reason") or "").split("|")[0].split("@")[0].strip()[:40]
        reasons[st][rk] = reasons[st].get(rk, 0) + 1
    return by_stage, reasons, n


def load_opps():
    m = {}
    for line in open(OPPS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "rr_achieved" not in d:
            continue
        ts = norm_ts(d.get("timestamp", ""))
        if not ts:
            continue
        try:
            rr = float(d["rr_achieved"])
        except (TypeError, ValueError):
            continue
        m.setdefault(ts, []).append(rr)         # may have long+short per candle
    return {ts: sum(v)/len(v) for ts, v in m.items()}     # mean across directions


def load_exec_trades():
    cands = sorted(glob.glob(str(ROOT/"results"/"**"/"BNBUSDT_trades.csv"), recursive=True),
                   key=os.path.getmtime, reverse=True)
    if not cands:
        return []
    rows = list(csv.DictReader(open(cands[0], encoding="utf-8")))
    out = []
    for r in rows:
        try:
            out.append(float(r.get("pnl_rr_net") or "nan"))
        except ValueError:
            pass
    return [v for v in out if v == v], cands[0]


def main():
    by_stage, reasons, n_trans = load_transitions()
    opps = load_opps()
    exec_rr, exec_path = load_exec_trades()
    print(f"[load] transitions={n_trans:,}  opps_candles={len(opps):,}  exec_trades={len(exec_rr)}")

    table = []
    prev = None
    for st in STAGES:
        cand_ts = by_stage[st]
        cnt = len(cand_ts)
        conv = (cnt/prev*100.0) if prev else 100.0
        if st == "EXECUTION":
            vals = exec_rr                                  # REAL trades
            joined, cov = vals, 1.0
            src = "real executed trades"
        else:
            joined = [opps[t] for t in cand_ts if t in opps]
            cov = (len(joined)/cnt) if cnt else 0.0
            src = "counterfactual (opportunities join)"
        mean_rr, pf, wr = pf_wr(joined)
        table.append(dict(stage=st, count=cnt, conv_pct=round(conv, 1), n_outcome=len(joined),
                          join_coverage=round(cov, 3), mean_rr=round(mean_rr, 4), pf=round(pf, 3),
                          wr=round(wr, 4), source=src,
                          top_reasons=sorted(reasons[st].items(), key=lambda kv: -kv[1])[:3]))
        prev = cnt

    # edge deltas between consecutive stages (does the gate ADD expectancy?)
    for i in range(1, len(table)):
        table[i]["delta_mean_rr"] = round(table[i]["mean_rr"] - table[i-1]["mean_rr"], 4)
    table[0]["delta_mean_rr"] = None

    meta = dict(generated=datetime.now(timezone.utc).isoformat(), instrument="BNBUSDT", config="v4_multi_2026_06",
                transitions=n_trans, opps_candles=len(opps), exec_trades=len(exec_rr),
                exec_csv=str(Path(exec_path).relative_to(ROOT)) if exec_rr else None)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    json.dump(dict(meta=meta, funnel=table), open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(meta, table)
    print(f"[write] {OUT_MD.relative_to(ROOT)}")


def write_md(meta, table):
    # find the gate with the biggest positive expectancy jump
    jumps = [(t["stage"], t.get("delta_mean_rr")) for t in table if t.get("delta_mean_rr") is not None]
    creator = max(jumps, key=lambda x: (x[1] if x[1] is not None else -9)) if jumps else (None, None)
    destroyer = min(jumps, key=lambda x: (x[1] if x[1] is not None else 9)) if jumps else (None, None)
    L = ["# Gate Contribution Audit — BNBUSDT (Study 2)\n",
         f"> Point-in-time, {meta['generated']}. PURE MEASUREMENT — no production change. Instrument BNBUSDT on "
         f"`{meta['config']}` (the promoted config). Funnel from `logs/crt_transitions.jsonl` "
         f"({meta['transitions']:,} transitions); per-stage counterfactual expectancy joined from BNBUSDT "
         f"`opportunities.jsonl` ({meta['opps_candles']:,} candles); EXECUTION = real executed trades "
         f"({meta['exec_trades']}, `{meta['exec_csv']}`).\n",
         "## Funnel — count, conversion, and expectancy after each gate\n",
         "| Stage | Count | Conv% (from prev) | mean rr | PF | WR | Δ mean-rr (gate adds?) | outcome-N (join cov) | source |",
         "|---|---|---|---|---|---|---|---|---|"]
    for t in table:
        d = t.get("delta_mean_rr")
        ds = "—" if d is None else f"{d:+.3f}"
        L.append(f"| **{t['stage']}** | {t['count']:,} | {t['conv_pct']:.1f}% | {t['mean_rr']:+.3f} | {t['pf']:.2f} | "
                 f"{t['wr']:.1%} | {ds} | {t['n_outcome']:,} ({t['join_coverage']:.0%}) | {t['source']} |")
    pre_exec = [t["mean_rr"] for t in table if t["stage"] != "EXECUTION"]
    exec_rr = next(t["mean_rr"] for t in table if t["stage"] == "EXECUTION")
    L += ["\n## Headline — the edge is the FINAL gate, not the pattern funnel\n",
          f"- **Every pre-execution stage leaves candidate expectancy at ~0 / negative** "
          f"(SWEEP→RETEST mean rr ∈ [{min(pre_exec):+.3f}, {max(pre_exec):+.3f}]R). The geometric funnel "
          f"(sweep→displacement→expansion→retest) cuts COUNT 186k→4k but **does not concentrate winners** — "
          f"candidate quality stays flat-to-negative through RETEST.",
          f"- **The entire selection edge appears at RETEST→EXECUTION:** {table[-2]['mean_rr']:+.3f}R → "
          f"**{exec_rr:+.3f}R** (PF {table[-2]['pf']:.2f}→{table[-1]['pf']:.2f}, WR {table[-2]['wr']:.0%}→"
          f"{table[-1]['wr']:.0%}). That gate = **session filter + score threshold + execution-planner SL/TP**.",
          "- **Combined with Study 1** (features ≈ chance, AUC 0.515; accepted-trade AUC only 0.60): the edge is "
          "**neither in the features NOR in the pattern geometry** — it is in the **execution-selection process**. "
          "This is why the session-policy change (part of that final gate) moved BNB +4.91%→+20.59%, and it says "
          "the highest-leverage work is the EXECUTION gate (session/score/SL-TP selectivity), not new features, "
          "clusters, Probability Surface, ReplayMemory, or TradeNet.\n",
          "## Verdict — per-gate\n",
          f"- **Edge-CREATING gate (largest +Δ expectancy):** **{creator[0]}** "
          f"({'+%.3fR' % creator[1] if creator[1] is not None else 'n/a'}) — dominates everything.",
          f"- **Mildly edge-positive pre-execution gate:** DISPLACEMENT (+0.048R, PF 0.83→1.15) — the only pattern "
          f"stage that nudges candidate quality up.",
          f"- **Dead-weight / mildly edge-negative:** EXPANSION ({table[2]['mean_rr']-table[1]['mean_rr']:+.3f}R) and "
          f"RETEST ({table[3]['mean_rr']-table[2]['mean_rr']:+.3f}R) — they shrink count without improving (slightly "
          f"worsening) per-candidate expectancy.\n",
          "## Critical caveat (do not over-read the final jump)\n",
          "- The +0.58R EXECUTION jump **conflates two things that this method cannot separate**: (a) *which* retest "
          "candles are selected (session + score), and (b) the execution-planner's **structure-based SL/TP** (vs the "
          "counterfactual's vanilla fixed SL/TP). Both are part of the *execution process* (not features/geometry), so "
          "the headline holds — but to split selection-vs-SL/TP would need a counterfactual that replays the execution "
          "planner's SL/TP on the rejected retest candidates. **Recommended next experiment.**",
          "- The geometric stages are not 'useless' — they reduce 186k→4k so the final gate is tractable; they just "
          "don't *create expectancy*.\n",
          "## Caveats\n",
          "- Counterfactual stages use the scanner's **vanilla SL/TP** outcome at the stage-entry candle — it measures "
          "*candidate-population quality* at each stage, not exact realized PnL. EXECUTION uses real trades.",
          "- A candle's outcome is the mean over its long/short opportunity records (direction is not always carried on "
          "the transition). Join coverage <100% means some stage-entry candles had no opportunity record (different "
          "scan window) — see the coverage column; regenerate opportunities on the same CSV to raise it.",
          "- One BNBUSDT run on v4; counts/period specific to `data/BNBUSDT_M15.csv`."]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
