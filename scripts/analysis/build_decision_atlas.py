#!/usr/bin/env python
"""build_decision_atlas.py — transition-grained warehouse over the dual-construction streams.

READ-ONLY. DESCRIPTIVE ONLY. No p-values, no verdicts, no economic claim.

WHY THIS EXISTS
---------------
Every measurement in this chain pushed the unit of analysis down a level. "673 vs 75 EXPANSION
bars" looked like a state disagreement; episode decomposition showed it was 4 vs 1 ENTRY
DECISIONS with everything after them being dwell. P-001 then showed the pooled bar-level
statistic reverses sign between its own two largest episodes. So the bar is not the unit and
occupancy is not the unit -- the TRANSITION DECISION is. This builds that as four Parquet tables
a query engine can ask new questions of, instead of another bespoke script per question.

WHAT IT JOINS (no new emission required)
----------------------------------------
Two streams produced by the SAME run, joined on (run_id, bar_index):
  * `*_crt_construction.jsonl` (envelope v2.0.0) -- engine state, every transition on the bar,
    resolver state/site/L2 map, live_atr.
  * `*_bar_structure.jsonl` (122 fields) -- `crt_direction`, `parent_crt_state`, `parent_bias`,
    `objective_status`, `htf_state`, `htf_candle_id`, SMC context.
An earlier draft of this design claimed direction was unavailable and that an envelope schema
change was the prerequisite. That was wrong: it read only the first stream. `crt_direction` is
already emitted on the second, and resolves for exactly the 91 decisions that have a side
(SWEEP 72 / DISPLACEMENT 13 / EXPANSION 4 / RETEST 2); the other 108 are terminations into
RANGE, which is the NEUTRAL state and genuinely has no side.

THE GRAIN, AND THE ONE SUBTLETY
--------------------------------
`episode` = maximal contiguous occupancy run of one engine state. Nearly every transition opens
one -- but NOT the 38 `RANGE -> RANGE` self-transitions, which fire on an HTF window change and
do not break the occupancy run. So episodes = 161 state changes + 1 initial run = 162, not 199.
An atlas that assumed 1 episode per transition would double-count those 38.

WHAT THE DEFAULT RANKING MUST CARRY
------------------------------------
~99 of the 199 decisions are HTF-CLOCK resets, not market events (58 SWEEP->RANGE + 38 self +
3 DISPLACEMENT->RANGE, all `HTF changed`). Ranking all 199 would be half calendar bookkeeping,
so `decision_class` (MARKET / CLOCK / SESSION) and `is_self_transition` exist to make the
exclusion explicit rather than something a reader has to remember. Overlap and episode
concentration are columns for the same reason: decisions minutes apart share ~85% of an H20
window and are one observation counted twice.

SCOPE OF THIS BUILD: the 2,300-bar window already on disk (4 EXPANSION decisions). Nearly every
cell will read INSUFFICIENT and the ranking will be episode-concentrated. That is expected --
the machinery is the deliverable; `--stream/--bar-structure/--csv` re-point it at the full 47k
corpus without a rewrite.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Reuse P-001's verified loaders/guards rather than copying them -- the timestamp join and its
# float32-relative OHLC tolerance are the parts most likely to drift, and they are already
# proven on this exact pair of files.
_P001 = ROOT / "scripts" / "analysis" / "p001_excursion_probe.py"
_spec = importlib.util.spec_from_file_location("p001_excursion_probe", _P001)
p001 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p001)

HORIZONS = (20, 40, 80)

#: Reason-family taxonomy. `to_state` alone is NOT the decision type: 108 `-> RANGE` rows are at
#: least four semantically different terminations (HTF clock, fib extension, 50% retrace,
#: session close). Order matters -- first match wins.
_REASON_FAMILIES: tuple[tuple[str, str, str], ...] = (
    # Weekend/session gaps. These are the 4 transitions the pre-fix trace could not see at all
    # (`Session gap detected: 2955min > 120min` -- four Mondays). Calendar-driven, never market
    # decisions, so they must not reach a MARKET ranking.
    ("Session gap detected", "session_gap", "SESSION"),
    ("HTF changed", "htf_changed", "CLOCK"),
    ("off_session", "off_session", "SESSION"),
    ("extension hit", "extension_hit", "MARKET"),
    ("retrace hit", "retrace_hit", "MARKET"),
    ("Sweep @", "sweep_detected", "MARKET"),
    ("Displacement", "displacement_confirmed", "MARKET"),
    ("expansion", "expansion_confirmed", "MARKET"),
    ("Retest", "retest_confirmed", "MARKET"),
    ("Shadow", "shadow_resume", "MARKET"),
    ("age=", "age_expiry", "MARKET"),
    ("Soft confirmation", "soft_conf_timeout", "MARKET"),
    ("bias", "parent_bias_veto", "MARKET"),
    ("objective", "parent_objective_veto", "MARKET"),
)


def classify_reason(reason: str) -> tuple[str, str]:
    """(reason_family, decision_class) from the engine's free-text reason.

    The reason strings embed live prices and indices, so they are matched on stable SUBSTRINGS
    and never pinned as literals. An unmatched reason becomes `unclassified` rather than being
    forced into a family -- a silently mis-filed decision is worse than a visible unknown.
    """
    r = (reason or "").lower()
    for needle, family, klass in _REASON_FAMILIES:
        if needle.lower() in r:
            return family, klass
    # Fall back to UNKNOWN, never MARKET. An unrecognised reason defaulting to MARKET would
    # silently enter the default ranking as if it were a market decision -- which is exactly
    # what happened to the 4 session-gap rows before they were classified above.
    return "unclassified", "UNKNOWN"


def _runs_of(values: list[str]) -> list[tuple[int, int, str]]:
    """Maximal contiguous [start, end, value] runs. Self-transitions do not break a run."""
    out: list[tuple[int, int, str]] = []
    if not values:
        return out
    start, cur = 0, values[0]
    for i in range(1, len(values)):
        if values[i] != cur:
            out.append((start, i - 1, cur))
            start, cur = i, values[i]
    out.append((start, len(values) - 1, cur))
    return out


def load_bar_structure(path: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("phase") != "WARMUP":
                out[int(rec["bar_index"])] = rec
    return out


def cross_checks(live: list[dict], bstruct: dict[int, dict], joined: list[dict],
                 integrity: dict, eng_states: list[str]) -> dict:
    """Already-measured invariants. If the builder disagrees, the BUILDER is wrong -- abort.

    These are not tests of the market; they are tests that this script reproduces numbers three
    prior measurements already established by independent routes.
    """
    hops = [(i, t) for i, r in enumerate(live) for t in (r.get("engine.transitions") or [])]
    n_hops = len(hops)
    n_self = sum(1 for _, t in hops if t["from"] == t["to"])
    # NOT n_hops - n_self. That equated "count of non-self HOPS" with "count of bars whose
    # occupancy actually changed" -- true only when every bar carries at most one hop. On the
    # calibration window (multi_hop_bars=0) the two coincide; on the full corpus (67 multi-hop
    # bars, all exactly 2 hops) they diverge by exactly 22: 7 round-trip bars (e.g. a gap-reset
    # SWEEP->RANGE immediately followed by a fresh RANGE->SWEEP the same bar) each contribute 2
    # non-self hops but 0 occupancy change, and 60 net-change multi-hop bars (e.g. the
    # SHADOW_PENDING->SWEEP->EXPANSION shadow-resume path) each contribute 2 non-self hops for
    # 1 occupancy change. The correct comparison is per BAR (before != after), not per hop --
    # verified: engine_state_before(i) == engine_state_after(i-1) on all 47,196 bar boundaries
    # of the full corpus, so this is mathematically the same quantity the occupancy-run scan
    # computes, just derived from the emitted before/after fields instead of adjacent states.
    n_change = sum(1 for r in live if r.get("engine_state_before") != r.get("engine_state_after"))
    multi = sum(1 for r in live if len(r.get("engine.transitions") or []) > 1)
    changed_flag = sum(1 for b in bstruct.values() if b.get("crt_state_changed") is True)

    actions: dict[str, int] = {}
    for b in bstruct.values():
        a = str(b.get("crt_action"))
        actions[a] = actions.get(a, 0) + 1

    eng_exp_runs = [r for r in _runs_of(eng_states) if r[2] == "EXPANSION"]
    res_states = [str(r.get("ontology_state")) for r in live]
    res_exp_runs = [r for r in _runs_of(res_states) if r[2] == "EXPANSION"]
    eng_exp_idx = {i for a, b, _ in eng_exp_runs for i in range(a, b + 1)}
    res_exp_idx = {i for a, b, _ in res_exp_runs for i in range(a, b + 1)}

    # THE INVARIANT THAT CAUGHT THE CAPTURE BUG. Every change in engine-state occupancy must be
    # explained by a recorded non-self transition. It first read 162 vs 161: the G4 gap reset in
    # backtest_v2 calls reset_to_range BEFORE the trace marked the transition log, so weekend
    # gap resets were appended outside the capture window and vanished from engine.transitions.
    # Keep this pinned -- an atlas built on a stream that under-reports decisions is worse than
    # no atlas, and the shortfall is invisible in every other count.
    occ_changes = sum(1 for i in range(1, len(eng_states)) if eng_states[i] != eng_states[i - 1])

    # PIN VALUES CORRECTED after the gap-capture fix. The earlier pins (199 / 161 / 38) were
    # measured against a trace that marked the transition log AFTER backtest_v2's G4 gap reset
    # and therefore never saw gap-driven resets. Fixing the mark recovered 4 transitions:
    # 1 real state change (a weekend-gap SWEEP->RANGE) and 3 self-transitions (gap resets that
    # fired while already in RANGE). The counts below are the post-fix truth.
    # STRUCTURAL INVARIANTS -- must hold on ANY corpus, never skippable. These test the
    # BUILDER's own correctness (capture completeness, join fidelity, row-count parity), not a
    # fact about this particular window. `occupancy_changes_equal_transitions` is the one that
    # caught the gap-capture bug; disabling it on a new corpus would re-open exactly that class
    # of silent under-reporting.
    invariants = {
        "occupancy_changes_equal_transitions": (occ_changes, n_change),
        "join_unmatched": (integrity["unmatched"], 0),
        "join_ohlc_mismatches": (integrity["ohlc_mismatches"], 0),
        "envelope_rows_equal_bar_structure_rows": (len(live), len(bstruct)),
    }

    # WINDOW-CALIBRATION PINS -- true of the 2,300-bar XAUUSD window this builder was verified
    # against, and expected to legitimately differ on any other corpus (more bars -> more of
    # everything). Reported always; enforced only when `window_pins_expected` is True (the
    # caller's way of saying "this IS that calibration window"), so a genuine regression on the
    # SAME corpus still aborts, but pointing at a bigger corpus does not trip a false alarm.
    window_pins = {
        "transitions_total": (n_hops, 203),
        "multi_hop_bars": (multi, 0),
        "state_changes": (n_change, 162),
        "self_transitions": (n_self, 41),
        # NOT a target -- a pinned OBSERVATION about the sibling stream. bar_structure derives
        # `crt_state_changed` from crt_state_before/after, which are read after the same gap
        # reset, so it under-reports by the same 1 gap-driven change (161 vs 162 occupancy
        # changes). Pre-existing in that module; recorded here, deliberately not fixed.
        "crt_state_changed_flag_known_undercount": (changed_flag, 161),
        "action_sweep_detected": (actions.get("SWEEP_DETECTED", 0), 72),
        "action_displacement_confirmed": (actions.get("DISPLACEMENT_CONFIRMED", 0), 13),
        "action_expansion_confirmed": (actions.get("EXPANSION_CONFIRMED", 0), 4),
        "action_retest_confirmed": (actions.get("RETEST_CONFIRMED", 0), 2),
        "envelope_live_rows": (len(live), 2222),
        "bar_structure_rows": (len(bstruct), 2222),
        "engine_expansion_episodes": (len(eng_exp_runs), 4),
        "resolver_expansion_episodes": (len(res_exp_runs), 1),
    }
    checks = {**invariants, **window_pins}
    invariant_failures = {k: v for k, v in invariants.items() if v[0] != v[1]}
    window_pin_failures = {k: v for k, v in window_pins.items() if v[0] != v[1]}
    failures = {**invariant_failures, **window_pin_failures}
    return {
        "checks": {k: {"got": g, "want": w, "ok": g == w} for k, (g, w) in checks.items()},
        "resolver_expansion_subset_of_engine": res_exp_idx <= eng_exp_idx,
        "invariant_failures": invariant_failures,
        "window_pin_failures": window_pin_failures,
        "failures": failures,
    }


def build(live: list[dict], bstruct: dict[int, dict], joined: list[dict],
          corpus: list[dict]) -> dict[str, list[dict]]:
    eng_states = [str(r.get("engine.crt_state")) for r in live]
    runs = _runs_of(eng_states)

    # ── episodes: occupancy runs. Self-transitions do NOT open one. ──────────────────────
    pos_to_episode: dict[int, str] = {}
    episodes: list[dict] = []
    for k, (a, b, state) in enumerate(runs):
        eid = f"EP{k:04d}"
        for i in range(a, b + 1):
            pos_to_episode[i] = eid
        seg_bars = [joined[i]["bar"] for i in range(a, b + 1)]
        atr0 = (live[a].get("engine.live_context") or {}).get("live_atr")
        move = seg_bars[-1]["close"] - seg_bars[0]["open"]
        res_hits = [i for i in range(a, b + 1) if live[i].get("ontology_state") == state]
        episodes.append({
            "episode_id": eid,
            "state": state,
            "entry_pos": a,
            "entry_ts": live[a]["timestamp"],
            "exit_ts": live[b]["timestamp"],
            "bars": b - a + 1,
            "direction": (bstruct.get(live[a]["bar_index"]) or {}).get("crt_direction"),
            "net_move": round(move, 4),
            "net_atr": round(move / atr0, 4) if atr0 else None,
            "right_censored": b == len(live) - 1,
            "is_initial": a == 0,
            "resolver_agree_bars": len(res_hits),
            "resolver_first_agree_ts": live[min(res_hits)]["timestamp"] if res_hits else None,
            "resolver_lag_bars": (min(res_hits) - a) if res_hits else None,
        })

    # ── decisions ────────────────────────────────────────────────────────────────────────
    decisions: list[dict] = []
    prior_pos: Optional[int] = None
    for pos, r in enumerate(live):
        for ordinal, t in enumerate(r.get("engine.transitions") or []):
            b = bstruct.get(r["bar_index"]) or {}
            fam, klass = classify_reason(str(t.get("reason", "")))
            direction = b.get("crt_direction")
            if direction in ("NONE", "", None):
                direction = None
            decisions.append({
                "decision_id": f"{r['run_id']}:{r['bar_index']}:{ordinal}",
                "run_id": r["run_id"],
                "ts": r["timestamp"],
                "bar_index": int(r["bar_index"]),
                "pos": pos,
                "from_state": t["from"],
                "to_state": t["to"],
                "reason_raw": str(t.get("reason", "")),
                "reason_family": fam,
                "decision_class": klass,
                "is_self_transition": t["from"] == t["to"],
                "direction": direction,
                "direction_source": "bar_structure.crt_direction" if direction else "unavailable",
                "episode_id": pos_to_episode.get(pos),
                "opens_episode": pos_to_episode.get(pos) != pos_to_episode.get(pos - 1)
                                 if pos > 0 else False,
                "bars_to_prior_decision": (pos - prior_pos) if prior_pos is not None else None,
                # context, joined not recomputed
                "parent_crt_state": b.get("parent_crt_state"),
                "parent_bias": b.get("parent_bias"),
                "objective_status": b.get("objective_status"),
                "htf_state": b.get("htf_state"),
                "htf_candle_id": b.get("htf_candle_id"),
                "resolver_state": r.get("ontology_state"),
                "resolver_site": r.get("resolver.projected_site"),
                "agree": r.get("agree"),
            })
            prior_pos = pos

    # ── excursions: one row per decision per horizon ─────────────────────────────────────
    excursions: list[dict] = []
    for d in decisions:
        atr = (live[d["pos"]].get("engine.live_context") or {}).get("live_atr")
        ci = joined[d["pos"]]["bar"]["index"]
        for H in HORIZONS:
            ex = p001.excursion(corpus, ci, float(atr), H) if atr else None
            row = {
                "decision_id": d["decision_id"], "horizon": H,
                "truncated": ex is None,
                "up_exc": None, "down_exc": None, "reach": None, "spans_gap": None,
                "fav_exc": None, "adv_exc": None, "fav_minus_adv": None,
            }
            if ex:
                up, dn = ex["up"], ex["down"]
                row.update({
                    "up_exc": round(up, 4), "down_exc": round(dn, 4),
                    "reach": round(max(up, dn), 4), "spans_gap": ex["spans_gap"],
                })
                # NULL unless a side is declared. Never default to the up-side: for a
                # termination into RANGE there is nothing for "favourable" to mean.
                if d["direction"] in ("LONG", "SHORT"):
                    fav, adv = (up, dn) if d["direction"] == "LONG" else (dn, up)
                    row.update({"fav_exc": round(fav, 4), "adv_exc": round(adv, 4),
                                "fav_minus_adv": round(fav - adv, 4)})
            excursions.append(row)

    # ── envelope bars (the dwell grain) ──────────────────────────────────────────────────
    bars: list[dict] = []
    ep_entry = {e["episode_id"]: e["entry_pos"] for e in episodes}
    for pos, r in enumerate(live):
        b = bstruct.get(r["bar_index"]) or {}
        j = joined[pos]["bar"]
        eid = pos_to_episode.get(pos)
        bars.append({
            "run_id": r["run_id"], "ts": r["timestamp"], "bar_index": int(r["bar_index"]),
            "engine_state": r.get("engine.crt_state"),
            "resolver_state": r.get("ontology_state"),
            "agree": r.get("agree"),
            "projected_site": r.get("resolver.projected_site"),
            "live_atr": (r.get("engine.live_context") or {}).get("live_atr"),
            "open": j["open"], "high": j["high"], "low": j["low"], "close": j["close"],
            "episode_id": eid,
            "bars_since_entry": pos - ep_entry[eid],
            "crt_direction": b.get("crt_direction"),
            "parent_crt_state": b.get("parent_crt_state"),
            "parent_bias": b.get("parent_bias"),
            "objective_status": b.get("objective_status"),
            "htf_state": b.get("htf_state"),
            "htf_candle_id": b.get("htf_candle_id"),
        })

    for e in episodes:
        e.pop("entry_pos", None)
    for d in decisions:
        d.pop("pos", None)
    return {"transition_decision": decisions, "episode": episodes,
            "envelope_bar": bars, "excursion": excursions}


def write_parquet(tables: dict[str, list[dict]], out_dir: Path) -> dict[str, str]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, rows in tables.items():
        tbl = pa.Table.from_pylist(rows)
        path = out_dir / f"{name}.parquet"
        pq.write_table(tbl, path, compression="zstd")
        written[name] = str(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    d = "logs/dual_construction_v2_envelope_safe"
    ap.add_argument("--stream", default=f"{d}/XAUUSD_crt_construction.jsonl")
    ap.add_argument("--bar-structure", default=f"{d}/XAUUSD_bar_structure.jsonl")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv")
    ap.add_argument("--out", default="results/decision_atlas")
    ap.add_argument("--other-corpus", action="store_true",
                    help=("Pointed at a corpus OTHER than the 2,300-bar calibration window, so "
                          "the window-specific pins (transitions_total=203, etc.) are expected "
                          "to differ and are reported rather than enforced. STRUCTURAL "
                          "invariants (occupancy==transitions, join integrity, row-count "
                          "parity) are enforced regardless -- this flag can never waive them."))
    args = ap.parse_args()

    corpus = p001.load_corpus(ROOT / args.csv)
    live = p001.load_live_rows(ROOT / args.stream)
    bstruct = load_bar_structure(ROOT / args.bar_structure)
    joined, integrity = p001.join_and_verify(live, corpus)
    if integrity["ohlc_mismatches"] or integrity["unmatched"]:
        print(f"FATAL: join integrity failed: {integrity}")
        return 1

    eng_states = [str(r.get("engine.crt_state")) for r in live]
    cc = cross_checks(live, bstruct, joined, integrity, eng_states)
    label = ("window-calibration pins expected to differ (--other-corpus)" if args.other_corpus
             else "pinned against three prior independent measurements")
    print(f"=== cross-checks ({label}) ===")
    for k, v in cc["checks"].items():
        print(f"  {'OK ' if v['ok'] else 'FAIL'} {k:32s} got={v['got']:<6} want={v['want']}")
    print(f"  {'OK ' if cc['resolver_expansion_subset_of_engine'] else 'FAIL'} "
          f"{'resolver_exp_subset_of_engine':32s} {cc['resolver_expansion_subset_of_engine']}")
    if cc["invariant_failures"]:
        print(f"\nFATAL: {len(cc['invariant_failures'])} STRUCTURAL invariant(s) failed -> the "
              "builder is wrong, not the data. Never waivable by --other-corpus. Nothing written.")
        return 1
    if cc["window_pin_failures"] and not args.other_corpus:
        print(f"\nFATAL: {len(cc['window_pin_failures'])} window-calibration pin(s) failed on "
              "what should be the SAME 2,300-bar window -> a real regression, not an expected "
              "corpus difference. Pass --other-corpus only when deliberately pointing elsewhere. "
              "Nothing written.")
        return 1
    if cc["window_pin_failures"] and args.other_corpus:
        print(f"\n{len(cc['window_pin_failures'])} window-calibration pin(s) differ, as expected "
              "on a different corpus (reported above, not enforced). Proceeding.")

    tables = build(live, bstruct, joined, corpus)
    written = write_parquet(tables, ROOT / args.out)

    print("\n=== tables ===")
    for name, rows in tables.items():
        print(f"  {name:22s} {len(rows):6d} rows -> {written[name]}")

    dec = tables["transition_decision"]
    print("\n=== decision mix ===")
    by_class: dict[str, int] = {}
    for x in dec:
        by_class[x["decision_class"]] = by_class.get(x["decision_class"], 0) + 1
    print(f"  by class      : {by_class}")
    print(f"  self-transitions: {sum(1 for x in dec if x['is_self_transition'])}")
    print(f"  directional     : {sum(1 for x in dec if x['direction'])} "
          f"/ {len(dec)}  (the rest are terminations into the neutral RANGE state)")
    eps = tables["episode"]
    # NOT `sum(not is_self_transition)` -- that counts non-self HOPS (5269-1089=4180 on the
    # full corpus), which overcounts by exactly the multi-hop discrepancy fixed above (67
    # multi-hop bars contribute 2 hops each but only 0 or 1 occupancy change). Episodes are
    # bar-run boundaries, so report the per-BAR count that actually produced them.
    n_bar_changes = sum(1 for r in live if r.get("engine_state_before") != r.get("engine_state_after"))
    print(f"  episodes        : {len(eps)}  (= {n_bar_changes} bar-level state changes + 1 initial)")

    meta = {
        "generated_utc": datetime.now().astimezone().isoformat(),
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "window": args.csv,
        "streams": {"envelope": args.stream, "bar_structure": args.bar_structure},
        "cross_checks": cc["checks"],
        "row_counts": {k: len(v) for k, v in tables.items()},
        "note": (
            "Grain is the TRANSITION DECISION. Dwell bars are not observations: filter "
            "bars_since_entry=0 or group by episode_id. ~99 of 199 decisions are HTF-clock "
            "resets (decision_class=CLOCK) and 38 are self-transitions that do not open an "
            "episode. fav/adv are NULL wherever no side is declared."
        ),
    }
    (ROOT / args.out / "atlas_manifest.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")
    p001.assert_no_claim_keys(meta)
    print(f"\nmanifest: {ROOT / args.out / 'atlas_manifest.json'}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
