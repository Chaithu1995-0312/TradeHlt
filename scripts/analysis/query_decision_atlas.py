#!/usr/bin/env python
"""query_decision_atlas.py — DuckDB query surface over the decision atlas.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

Reads the four Parquet tables written by `build_decision_atlas.py` directly via
`read_parquet` -- no .db file, no persistent state, nothing to keep in sync.

THE THREE CONTROLS EVERY RANKING CARRIES
-----------------------------------------
A raw "top N by fav_minus_adv" over this atlas would be misleading three ways at once, so the
default ranking reports its own limits alongside its rows:

1. EPISODE CONCENTRATION. One episode (E4) contains a +58 ATR move. Decisions inside it occupy
   the top of any excursion ranking regardless of their state. Every ranking prints how many
   DISTINCT episodes the top N came from; if that is 2, the ranking is a fact about 2 events.
2. OVERLAP. Decisions minutes apart share ~85% of an H20 forward window and are one observation
   counted twice. `bars_to_prior_decision` is printed per row.
3. BASE RATE. RANGE fires 108 times and EXPANSION 4, so a "state distribution of winners" is
   mostly a distribution of how often each state fires. Per-state summaries print n and a power
   label; n < 30 is INSUFFICIENT.

The default ranking also excludes, explicitly rather than by convention:
  * `decision_class = CLOCK` -- ~99 of 199 decisions are HTF-clock resets, not market events;
  * `is_self_transition` -- 38 RANGE->RANGE rows where the state does not change at all;
  * rows with no declared direction -- terminations into RANGE, the neutral state, where
    "favourable" has no referent.

USAGE
    venv/Scripts/python.exe scripts/analysis/query_decision_atlas.py            # all sections
    venv/Scripts/python.exe scripts/analysis/query_decision_atlas.py --sql "select ..."
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _rel(d: Path, name: str) -> str:
    return f"read_parquet('{(d / f'{name}.parquet').as_posix()}')"


def main() -> int:
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default="results/decision_atlas")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--sql", help="Run one ad-hoc query against the atlas views and exit.")
    args = ap.parse_args()

    d = ROOT / args.atlas
    if not (d / "transition_decision.parquet").exists():
        print(f"no atlas at {d} -- run build_decision_atlas.py first")
        return 1

    con = duckdb.connect()
    for t in ("transition_decision", "episode", "envelope_bar", "excursion"):
        con.execute(f"create view {t} as select * from {_rel(d, t)}")

    if args.sql:
        con.execute(args.sql).df().to_string(sys.stdout)
        print()
        return 0

    H, N = args.horizon, args.top

    print("=== decision mix (what the decision rows actually are) ===")
    print(con.execute("""
        select decision_class, is_self_transition,
               count(*) as n,
               count(direction) as with_direction
        from transition_decision
        group by 1,2 order by n desc
    """).df().to_string(index=False))

    print("\n=== by decision type (from -> to, reason_family) ===")
    print(con.execute("""
        select from_state, to_state, reason_family, decision_class, count(*) as n,
               count(direction) as directional
        from transition_decision group by 1,2,3,4 order by n desc
    """).df().to_string(index=False))

    print(f"\n=== TOP {N} MARKET decisions by fav_minus_adv @H{H} ===")
    print("(CLOCK resets, self-transitions and direction-less terminations excluded)")
    top = con.execute(f"""
        select d.decision_id, d.ts, d.from_state || '->' || d.to_state as decision,
               d.direction, d.episode_id, d.bars_to_prior_decision as gap_bars,
               e.fav_minus_adv, e.fav_exc, e.adv_exc, e.spans_gap,
               d.parent_crt_state, d.htf_state
        from transition_decision d join excursion e using (decision_id)
        where e.horizon = {H} and d.decision_class = 'MARKET'
          and not d.is_self_transition and d.direction is not null
          and e.fav_minus_adv is not null
        order by e.fav_minus_adv desc limit {N}
    """).df()
    print(top.to_string(index=False))

    conc = con.execute(f"""
        with t as (
          select d.episode_id, e.fav_minus_adv
          from transition_decision d join excursion e using (decision_id)
          where e.horizon = {H} and d.decision_class = 'MARKET'
            and not d.is_self_transition and d.direction is not null
            and e.fav_minus_adv is not null
          order by e.fav_minus_adv desc limit {N}
        )
        select count(*) as rows, count(distinct episode_id) as distinct_episodes
        from t
    """).df()
    r, ep = int(conc.iloc[0]["rows"]), int(conc.iloc[0]["distinct_episodes"])
    print(f"\n  CONCENTRATION: the top {r} rows come from {ep} distinct episode(s).")
    if ep <= 3:
        print(f"  -> This ranking is a fact about {ep} event(s), not a population.")

    print(f"\n=== per-state summary @H{H} (entry decisions only, with power) ===")
    print(con.execute(f"""
        select d.to_state as entered,
               count(*) as n,
               count(distinct d.episode_id) as episodes,
               round(median(e.fav_minus_adv), 3) as fav_minus_adv_median,
               round(median(e.fav_exc), 3) as fav_median,
               round(median(e.adv_exc), 3) as adv_median,
               case when count(*) < 30 then 'INSUFFICIENT' else 'WEAK' end as power
        from transition_decision d join excursion e using (decision_id)
        where e.horizon = {H} and d.decision_class = 'MARKET'
          and not d.is_self_transition and d.direction is not null
        group by 1 order by n desc
    """).df().to_string(index=False))

    print("\n=== engine EXPANSION episodes (the E1..E4 objects) ===")
    print(con.execute("""
        select episode_id, entry_ts, bars, direction, net_atr, right_censored,
               resolver_agree_bars, resolver_lag_bars
        from episode where state = 'EXPANSION' order by entry_ts
    """).df().to_string(index=False))

    print("\n=== resolver lag: where the two constructions agree on a state ===")
    print(con.execute("""
        select state, count(*) as episodes,
               sum(case when resolver_agree_bars > 0 then 1 else 0 end) as episodes_with_agreement,
               min(resolver_lag_bars) as min_lag, max(resolver_lag_bars) as max_lag
        from episode group by 1 order by episodes desc
    """).df().to_string(index=False))

    print("\n=== top disagreement episodes (bars where engine != resolver) ===")
    print(con.execute("""
        select b.episode_id, any_value(b.engine_state) as engine_state,
               count(*) as bars,
               sum(case when b.agree = false then 1 else 0 end) as disagree_bars,
               round(100.0 * sum(case when b.agree = false then 1 else 0 end) / count(*), 1) as pct
        from envelope_bar b group by 1
        having disagree_bars > 0 order by disagree_bars desc limit 10
    """).df().to_string(index=False))

    print("\n=== dwell check: decisions are entry bars, not occupancy ===")
    print(con.execute("""
        select engine_state,
               count(*) as occupancy_bars,
               sum(case when bars_since_entry = 0 then 1 else 0 end) as entry_bars
        from envelope_bar group by 1 order by occupancy_bars desc
    """).df().to_string(index=False))

    print("\nDESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
