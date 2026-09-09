"""
high_acceptance_gap_policy.py — Phase 3.5 Definition Repair: re-run the phase-1 acceptance kernel
under explicit GAP POLICIES (research, ontology-free).

WHY. Phase 1 defined acceptance over a forward window [i+1, i+N] as if bar i+1 always follows
bar i in a continuous auction. It does not. XAUUSD M15 has a 75-minute overnight break (23:45 ->
01:00) and a ~49-hour weekend break, and the Studies A/B/C census showed the rare-event
population is dominated by exactly that discontinuity: 25 of 30 acceptance events sit on the
23:45 last-bar-of-day slot (1.05% of the population), an acceptance rate of 5.03% there vs
0.0107% elsewhere = 471x, every one of them followed by a gap the market reopened above. The
metric was measuring the calendar, not the auction.

So the definition was UNDERSPECIFIED: it never declared what a forward window does at a session
break. This script makes the policy explicit and measures all three.

    POLICY_A_IGNORE_GAPS       phase-1 behaviour: bar i+1 follows bar i regardless of any break
                               (the implicit, undeclared status quo)
    POLICY_B_EXCLUDE_CROSSING  candidate is NOT EVALUATED if any bar in [i+1, i+N] is preceded by
                               a session break -- only windows inside one continuous session count
    POLICY_C_TERMINATE_AT_BREAK window ends at the first session break; effective horizon is
                               min(N, bars remaining in session). A candidate whose very next bar
                               is post-break has an EMPTY window and is not evaluated.

A session break is any inter-bar gap greater than the modal 15 minutes, which captures overnight,
weekend and holiday discontinuities without hardcoding a calendar.

READING IT. Policy B is only meaningful at short horizons: the corpus runs ~92 bars/session, so
by N>=100 essentially every window crosses a break and the eligible population collapses toward
zero. That collapse is itself the result and is reported rather than hidden. Policy C keeps every
mid-session candidate but shortens the window, so effective-horizon distributions are reported
alongside every count -- a shorter window makes acceptance mechanically EASIER, and a
`min_effective_bars` matched view is reported so that is not mistaken for a real increase.

Still descriptive: no classification, no trading meaning, no promotion authority.

PURE READ-ONLY over the phase-1 parquet. No production/src/config/spine change.

Outputs:
    results/research/high_acceptance/xauusd_m15_gap_policy.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "research" / "high_acceptance"
RAW_PARQUET = OUT_DIR / "xauusd_m15.parquet"
OUT_JSON = OUT_DIR / "xauusd_m15_gap_policy.json"

HORIZONS = [5, 10, 20, 50, 100, 250, 500]
MODAL_GAP_MIN = 15.0          # normal M15 bar spacing; anything larger is a discontinuity
LAST_SLOT = "23:45"           # the slot the Studies A/B/C census implicated
MATCHED_MIN_EFF = {5: 5, 10: 10, 20: 20, 50: 50, 100: 92, 250: 92, 500: 92}


def load_raw() -> pd.DataFrame:
    df = pd.read_parquet(RAW_PARQUET).sort_values("timestamp").reset_index(drop=True)
    gap = df["timestamp"].diff().dt.total_seconds().div(60)
    df["gap_before_min"] = gap
    df["is_break_before"] = (gap > MODAL_GAP_MIN).fillna(True)   # first bar opens a session
    df["session_id"] = df["is_break_before"].cumsum()
    df["slot"] = df["timestamp"].dt.strftime("%H:%M")
    return df


def gap_census(df: pd.DataFrame) -> dict:
    g = df["gap_before_min"].dropna()
    buckets = {
        "15_min_normal": int((g == 15).sum()),
        "30_to_60_min": int(((g > 15) & (g <= 60)).sum()),
        "75_min_overnight": int((g == 75).sum()),
        "over_60_under_1000_min": int(((g > 60) & (g < 1000) & (g != 75)).sum()),
        "over_1000_min_weekend_or_holiday": int((g >= 1000).sum()),
    }
    sizes = df.groupby("session_id").size()
    return {
        "modal_gap_min": MODAL_GAP_MIN,
        "gap_buckets": buckets,
        "n_breaks": int(df["is_break_before"].sum()),
        "n_sessions": int(df["session_id"].nunique()),
        "session_length_bars": {
            "median": float(sizes.median()), "mean": float(sizes.mean()),
            "min": int(sizes.min()), "max": int(sizes.max()),
        },
    }


def policy_a(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Phase-1 behaviour, reproduced here as the baseline arm."""
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    n_valid = len(df) - n
    if n_valid <= 0:
        return pd.DataFrame()
    win = np.lib.stride_tricks.sliding_window_view(low[1:], n)[:n_valid]
    cand_high = high[:n_valid]
    return pd.DataFrame({
        "candidate_index": np.arange(n_valid),
        "acceptance_score": win.min(axis=1) - cand_high,
        "effective_bars": n,
    })


def policy_b(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Exclude any candidate whose forward window crosses a session break."""
    base = policy_a(df, n)
    if base.empty:
        return base
    brk = df["is_break_before"].to_numpy()
    # window [i+1, i+n] crosses a break iff any of brk[i+1 .. i+n] is True
    csum = np.concatenate([[0], np.cumsum(brk)])
    idx = base["candidate_index"].to_numpy()
    crosses = (csum[idx + n + 1] - csum[idx + 1]) > 0
    return base.loc[~crosses].reset_index(drop=True)


def policy_c(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Terminate the window at the first session break; effective horizon = min(n, bars left)."""
    high, low = df["high"].to_numpy(), df["low"].to_numpy()
    sess = df["session_id"].to_numpy()
    # last index of each session
    last_of_session = pd.Series(np.arange(len(df))).groupby(sess).transform("max").to_numpy()

    rows_idx, scores, effs = [], [], []
    for i in range(len(df)):
        end = min(i + n, last_of_session[i])
        if end <= i:                       # next bar is post-break -> empty window
            continue
        w = low[i + 1:end + 1]
        rows_idx.append(i)
        scores.append(w.min() - high[i])
        effs.append(len(w))
    return pd.DataFrame({
        "candidate_index": np.array(rows_idx, dtype=int),
        "acceptance_score": np.array(scores, dtype=float),
        "effective_bars": np.array(effs, dtype=int),
    })


POLICIES = {
    "POLICY_A_IGNORE_GAPS": policy_a,
    "POLICY_B_EXCLUDE_CROSSING": policy_b,
    "POLICY_C_TERMINATE_AT_BREAK": policy_c,
}


def summarize(df: pd.DataFrame, res: pd.DataFrame, n: int, policy: str) -> dict:
    if res.empty:
        return {"n_evaluated": 0, "n_accepted": 0, "acceptance_rate": None,
                "note": "no candidate has a usable window at this horizon under this policy"}
    slots = df["slot"].to_numpy()[res["candidate_index"].to_numpy()]
    acc = res["acceptance_score"] > 0
    n_acc = int(acc.sum())
    out = {
        "n_evaluated": int(len(res)),
        "eligible_fraction_of_corpus": round(len(res) / (len(df) - n if len(df) > n else 1), 4),
        "n_accepted": n_acc,
        "acceptance_rate_pct": round(float(acc.mean()) * 100, 5),
        "n_accepted_on_last_slot": int((slots[acc.to_numpy()] == LAST_SLOT).sum()),
        "last_slot_share_of_accepted": (
            round(float((slots[acc.to_numpy()] == LAST_SLOT).mean()), 4) if n_acc else None
        ),
        "effective_bars": {
            "median": float(res["effective_bars"].median()),
            "mean": float(res["effective_bars"].mean()),
            "min": int(res["effective_bars"].min()),
        },
    }
    if policy == "POLICY_C_TERMINATE_AT_BREAK":
        keep = res[res["effective_bars"] >= MATCHED_MIN_EFF[n]]
        if len(keep):
            a2 = keep["acceptance_score"] > 0
            s2 = df["slot"].to_numpy()[keep["candidate_index"].to_numpy()]
            out["matched_min_effective_bars"] = {
                "min_effective_bars": MATCHED_MIN_EFF[n],
                "n_evaluated": int(len(keep)),
                "n_accepted": int(a2.sum()),
                "acceptance_rate_pct": round(float(a2.mean()) * 100, 5),
                "n_accepted_on_last_slot": int((s2[a2.to_numpy()] == LAST_SLOT).sum()),
            }
    return out


def persistence(df: pd.DataFrame, per_h: dict[int, pd.DataFrame]) -> dict:
    """0-7 persistent score over candidates evaluable at EVERY horizon under this policy."""
    common = None
    for n in HORIZONS:
        r = per_h[n]
        s = set(r["candidate_index"].tolist()) if not r.empty else set()
        common = s if common is None else (common & s)
    common = sorted(common or [])
    if not common:
        return {"n_candidates_all_horizons": 0, "score_histogram": {}, "n_score_ge_1": 0,
                "n_score_7": 0, "note": "no candidate is evaluable at every horizon under this policy"}
    score = np.zeros(len(common), dtype=int)
    pos = {c: k for k, c in enumerate(common)}
    for n in HORIZONS:
        r = per_h[n]
        sub = r[r["candidate_index"].isin(common)]
        idx = np.array([pos[c] for c in sub["candidate_index"]])
        score[idx] += (sub["acceptance_score"].to_numpy() > 0).astype(int)
    slots = df["slot"].to_numpy()[np.array(common)]
    ge1 = score >= 1
    return {
        "n_candidates_all_horizons": len(common),
        "score_histogram": {int(k): int(v) for k, v in zip(*np.unique(score, return_counts=True))},
        "n_score_ge_1": int(ge1.sum()),
        "n_score_7": int((score == 7).sum()),
        "n_score_ge_1_on_last_slot": int((slots[ge1] == LAST_SLOT).sum()),
        "last_slot_share_of_events": (
            round(float((slots[ge1] == LAST_SLOT).mean()), 4) if ge1.any() else None
        ),
    }


def main() -> None:
    df = load_raw()
    census = gap_census(df)

    results = {}
    for pname, fn in POLICIES.items():
        per_h = {n: fn(df, n) for n in HORIZONS}
        results[pname] = {
            "per_horizon": {str(n): summarize(df, per_h[n], n, pname) for n in HORIZONS},
            "persistence": persistence(df, per_h),
        }

    summary = {
        "gap_census": census,
        "last_slot": LAST_SLOT,
        "policies": {
            "POLICY_A_IGNORE_GAPS": "phase-1 status quo — bar i+1 follows bar i across any break",
            "POLICY_B_EXCLUDE_CROSSING": "candidate not evaluated if its window crosses a break",
            "POLICY_C_TERMINATE_AT_BREAK": "window ends at the first break; effective horizon = min(N, bars left in session)",
        },
        "results": results,
        "note": (
            "Definition repair, not a new measurement instrument. Descriptive only: no "
            "classification, no trading meaning, no promotion authority. Policy B's eligible "
            "population necessarily collapses at horizons approaching the ~92-bar session length; "
            "that collapse is a property of the corpus, reported rather than hidden."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str))

    print(f"gap census: {census['n_sessions']} sessions, {census['n_breaks']} breaks, "
          f"median session {census['session_length_bars']['median']:.0f} bars")
    print(f"  buckets: {census['gap_buckets']}")
    for pname in POLICIES:
        r = results[pname]
        print(f"\n=== {pname}")
        print(f"  {'N':>5} {'evaluated':>10} {'elig%':>7} {'accepted':>9} {'rate%':>9} {'@23:45':>7} {'share':>7}")
        for n in HORIZONS:
            s = r["per_horizon"][str(n)]
            if not s["n_evaluated"]:
                print(f"  {n:>5} {0:>10} {'--':>7} {'--':>9} {'--':>9} {'--':>7} {'--':>7}")
                continue
            print(f"  {n:>5} {s['n_evaluated']:>10} {s['eligible_fraction_of_corpus']*100:>6.1f}% "
                  f"{s['n_accepted']:>9} {s['acceptance_rate_pct']:>9.5f} "
                  f"{s['n_accepted_on_last_slot']:>7} "
                  f"{('--' if s['last_slot_share_of_accepted'] is None else f'{s['last_slot_share_of_accepted']:.2f}'):>7}")
        p = r["persistence"]
        print(f"  persistence: n_all_horizons={p['n_candidates_all_horizons']} "
              f"score>=1: {p['n_score_ge_1']}  score==7: {p['n_score_7']}"
              + (f"  (on {LAST_SLOT}: {p.get('n_score_ge_1_on_last_slot')})" if p.get("n_score_ge_1") else ""))
    print(f"\nwrote: {OUT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
