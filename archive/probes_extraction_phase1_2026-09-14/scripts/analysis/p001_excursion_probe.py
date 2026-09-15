#!/usr/bin/env python
"""p001_excursion_probe.py — uncapped forward excursion on the CRT envelope populations.

PROBE P-001. READ-ONLY. DESCRIPTIVE ONLY. Grants no authority (CLAUDE.md 6.5).

WHY THIS EXISTS
---------------
The prior symmetric 1R:1R first-touch probe returned MFE ~= |MAE| ~= 0.97R in EVERY population
(agree / disagree / F-069 core). That is the instrument, not the market: a 1R barrier pins both
excursions at ~1R by construction, so an expansion that travels 8 ATR and a range that wiggles
1 ATR score identically. P-001 removes the cap and measures how far price actually reaches.

THE OBJECT
----------
Per LIVE envelope bar i that has a next bar, for each horizon H:

    entry    = open[i+1]                       (next-bar open; matches the 1R probe's convention)
    atr_i    = engine.live_context.live_atr    (PRICE UNITS)
    up_exc   = (max(high[i+1 .. i+H]) - entry) / atr_i
    down_exc = (entry - min(low[i+1 .. i+H])) / atr_i

ATR DISCIPLINE (the F-072 trap). Two different ATRs ride on every envelope row: the canonical
`atr` in resolver.feature_vector is CLOSE-RELATIVE (FM-041, ~0.0018) and `live_atr` in
engine.live_context is PRICE UNITS (~9.07); their ratio is the close. Excursions are price
units, so this probe uses `live_atr` and never the canonical one. Mixing them silently rescales
every number by ~5,000x.

ONE ROW PER BAR, NOT TWO. The brief inherited "both directions" from the 1R probe. For uncapped
excursion that is wrong: first-touch is path-dependent so long/short are genuinely different
trades, but excursion is not -- long-MFE == up_exc == short-MAE, and long-MAE == down_exc ==
short-MFE. Emitting both directions would duplicate every bar as perfectly anti-correlated rows
and double the apparent n while adding zero information. So: one row per bar, n = bars.

REUSE, NOT REIMPLEMENTATION. Excursion comes from the governed `research.measurement.forward_walk`
kernel driven with UNREACHABLE SL/TP multiples, so the walk never exits and its `mfe`/`mae` are
the full-horizon excursions -- inheriting the same bar-iteration semantics every other measured
result in this repo uses. That reuse is certified against an independent naive max/min twin
(the same twin-certification `multi_tp_walk` got under F-088); a mismatch is fatal, not a warning.

WHAT THIS CANNOT SAY
--------------------
Nothing about significance, and nothing economic. Forward windows on adjacent bars overlap almost
completely (at H=80 neighbours share 79/80 of the window), so independent blocks ~= bars/H: on
this 2,222-bar window that is ~111 / ~55 / ~28 for the whole sample, and population C (27% of
bars) gets roughly 30 / 15 / 7. A naive n=598 at H=80 is about SEVEN independent observations.
Every cell therefore ships `n_independent_blocks` and a power label, and the artifact carries no
p-value, no CI and no verdict key -- a number that does not exist cannot be quoted later.

Tail statistics (p90/p95 of total reach) are where an EXPANSION effect would actually live, since
a population can hold its median while its upper decile runs away. They are also the LEAST stable
statistic under overlap: at ~7 blocks a p95 can be one expansion episode wearing a percentile's
clothing. So every tail cell ships `n_distinct_runs_in_top_decile` and
`top_decile_share_from_largest_run`, and the artifact asserts a tail number is never emitted
without them.

SELECTION (stated here, not only in the log). Population C is selected BECAUSE the engine already
took an ATR-extension into EXPANSION. Any forward asymmetry is therefore partly mechanical
continuation of a move already underway -- the F-030/F-043 REGIME_REDUNDANT shape: real, and fully
explicable by something that is not skill.

USAGE
    venv/Scripts/python.exe scripts/analysis/p001_excursion_probe.py \
        --stream logs/dual_construction_v2_envelope_safe/XAUUSD_crt_construction.jsonl \
        --csv data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import forward_walk  # noqa: E402

HORIZONS = (20, 40, 80)
#: SL/TP multiples large enough that the walk can never exit, turning forward_walk into a pure
#: excursion tracker over the full horizon. Certified against the naive twin.
UNREACHABLE_ATR_MULT = 1e9
#: A forward window whose bar spacing exceeds this is spanning a session/weekend gap.
GAP_THRESHOLD = timedelta(minutes=30)
BAR_SPACING = timedelta(minutes=15)


class _Bar:
    """Minimal bar for forward_walk (reads .high/.low/.close/.index only)."""

    __slots__ = ("high", "low", "close", "index")

    def __init__(self, high: float, low: float, close: float, index: int) -> None:
        self.high, self.low, self.close, self.index = high, low, close, index


# ── io ────────────────────────────────────────────────────────────────────────────────────
def load_corpus(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            rows.append({
                "index": i,
                "ts": datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
            })
    return rows


def load_live_rows(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("phase") == "LIVE":
                out.append(rec)
    return out


# ── join + integrity ──────────────────────────────────────────────────────────────────────
def join_and_verify(live: list[dict], corpus: list[dict]) -> tuple[list[dict], dict]:
    """Join envelope rows to corpus bars BY TIMESTAMP and verify the OHLC agrees.

    The feature pipeline drops warmup bars and resets its index, so a POSITIONAL join is exactly
    the alignment bug that has bitten this corpus before. Timestamp is the key; the OHLC compare
    is the guard that proves the key was right.
    """
    by_ts = {c["ts"]: c for c in corpus}
    joined, mismatches, unmatched = [], 0, 0
    for rec in live:
        ts = datetime.fromisoformat(rec["timestamp"])
        bar = by_ts.get(ts)
        if bar is None:
            unmatched += 1
            continue
        fv = rec.get("resolver.feature_vector") or {}
        for field in ("open", "high", "low", "close"):
            if field not in fv:
                continue
            # RELATIVE tolerance: the canonical vector stores prices as float32, so at XAUUSD's
            # ~4,000 level it round-trips as 4155.47021484375 vs the CSV's 4155.47 -- ~2e-4 of
            # representation noise. 1e-6 relative (~0.004 here) sits ~20x above that noise and
            # orders of magnitude below any real misalignment, which would differ by whole
            # dollars. An ABSOLUTE 1e-6 flagged all 2,222 rows and was a bug in this guard.
            if abs(float(fv[field]) - bar[field]) > 1e-6 * max(1.0, abs(bar[field])):
                mismatches += 1
                break
        joined.append({"rec": rec, "bar": bar})
    return joined, {"unmatched": unmatched, "ohlc_mismatches": mismatches}


# ── excursion ─────────────────────────────────────────────────────────────────────────────
def excursion(corpus: list[dict], i: int, atr: float, horizon: int) -> Optional[dict]:
    """Uncapped (up, down) excursion in ATR units over bars i+1 .. i+horizon.

    Returns None when the window is truncated by corpus end (reported, never silently short).
    """
    future = corpus[i + 1: i + 1 + horizon]
    if len(future) < horizon:
        return None
    entry = corpus[i + 1]["open"]

    sig = Signal(
        instrument="XAUUSD", timestamp=corpus[i]["ts"], entry_index=i, direction="long",
        entry=entry, sl_atr_mult=UNREACHABLE_ATR_MULT, tp_atr_mult=UNREACHABLE_ATR_MULT, atr=atr,
    )
    bars = [_Bar(b["high"], b["low"], b["close"], b["index"]) for b in future]
    oc = forward_walk(sig, bars, max_forward=horizon, exit_model="intrabar_fixed")
    if oc.outcome != "TIMEOUT":
        raise AssertionError(
            f"forward_walk exited ({oc.outcome}) despite unreachable barriers at bar {i} -- the "
            "excursion object is not what this probe declares. Refusing to report."
        )

    # Independent naive twin (F-088 certification pattern): a private max/min, computed without
    # the kernel, must agree to 1e-10 or the reuse is not the object it claims to be.
    twin_up = max(b["high"] for b in future) - entry
    twin_down = entry - min(b["low"] for b in future)
    if abs(oc.mfe - twin_up) > 1e-10 or abs(-oc.mae - twin_down) > 1e-10:
        raise AssertionError(
            f"twin certification FAILED at bar {i}: kernel up={oc.mfe} down={-oc.mae} vs "
            f"naive up={twin_up} down={twin_down}"
        )

    spans_gap = any(
        future[k + 1]["ts"] - future[k]["ts"] > GAP_THRESHOLD for k in range(len(future) - 1)
    ) or (future[0]["ts"] - corpus[i]["ts"] > GAP_THRESHOLD)

    return {
        "up": oc.mfe / atr,
        "down": twin_down / atr,
        "spans_gap": spans_gap,
    }


# ── populations ───────────────────────────────────────────────────────────────────────────
def classify(rec: dict) -> dict[str, bool]:
    eng = rec.get("engine.crt_state")
    onto = rec.get("ontology_state")
    agree = rec.get("agree")
    eng_exp = eng == "EXPANSION"
    return {
        "A_agree": agree is True,
        "B_disagree": agree is False,
        "C_engEXP_resNotEXP": eng_exp and onto != "EXPANSION",
        "D_engEXP_resEXP": eng_exp and onto == "EXPANSION",
        "E_engEXP_all": eng_exp,
        "F_engNotEXP": not eng_exp,
    }


# ── statistics (descriptive only — no p-values, no CI, no verdict) ────────────────────────
def _pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _tail_concentration(reach: list[float], bar_idx: list[int]) -> dict:
    """How many DISTINCT contiguous bar-runs supply the top decile.

    A p95 over 598 overlapping bars can be a single expansion episode. This is the number that
    says so. Adjacent bars (index diff <= 1) collapse into one run.
    """
    if not reach:
        return {"n_distinct_runs_in_top_decile": 0, "top_decile_share_from_largest_run": None}
    k = max(1, len(reach) // 10)
    top = sorted(zip(reach, bar_idx), key=lambda t: -t[0])[:k]
    idxs = sorted(i for _, i in top)
    runs, cur = [], [idxs[0]]
    for a, b in zip(idxs, idxs[1:]):
        if b - a <= 1:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    return {
        "n_distinct_runs_in_top_decile": len(runs),
        "top_decile_share_from_largest_run": round(max(len(r) for r in runs) / len(idxs), 4),
    }


def summarize(rows: list[dict], horizon: int, total_bars: int) -> dict:
    up = [r["up"] for r in rows]
    down = [r["down"] for r in rows]
    reach = [max(r["up"], r["down"]) for r in rows]
    asym = [abs(r["up"] - r["down"]) for r in rows]
    bar_idx = [r["bar_index"] for r in rows]
    n = len(rows)
    blocks = n // horizon  # windows only stop overlapping once they are `horizon` bars apart
    # How many distinct MARKET EPISODES the population is, not how many bars. A population of
    # 598 bars that is 4 contiguous runs is 4 events observed 598 times, and this is a harder
    # ceiling than the block arithmetic: blocks assume the bars are spread out, runs measure
    # whether they actually are.
    runs = 1 if n else 0
    for a, b in zip(bar_idx, bar_idx[1:]):
        if b - a > 1:
            runs += 1
    cell = {
        "n_bars": n,
        "n_contiguous_runs": runs,
        "n_independent_blocks": blocks,
        "power": "INSUFFICIENT" if min(blocks, runs) < 30 else "WEAK",
        "windows_spanning_gap": sum(1 for r in rows if r["spans_gap"]),
        "up_mean": round(st.mean(up), 4) if up else None,
        "up_median": round(st.median(up), 4) if up else None,
        "up_p75": round(_pct(up, 75), 4) if up else None,
        "down_mean": round(st.mean(down), 4) if down else None,
        "down_median": round(st.median(down), 4) if down else None,
        "down_p75": round(_pct(down, 75), 4) if down else None,
        "reach_mean": round(st.mean(reach), 4) if reach else None,
        "reach_median": round(st.median(reach), 4) if reach else None,
        "asymmetry_mean": round(st.mean(asym), 4) if asym else None,
        "reach_p90": round(_pct(reach, 90), 4) if reach else None,
        "reach_p95": round(_pct(reach, 95), 4) if reach else None,
        "reach_max": round(max(reach), 4) if reach else None,
    }
    cell.update(_tail_concentration(reach, bar_idx))
    return cell


# ── episode inventory ─────────────────────────────────────────────────────────────────────
def _runs(idxs: list[int]) -> list[tuple[int, int]]:
    """Maximal contiguous [start, end] runs over sorted positions."""
    if not idxs:
        return []
    out, start, prev = [], idxs[0], idxs[0]
    for i in idxs[1:]:
        if i == prev + 1:
            prev = i
            continue
        out.append((start, prev))
        start = prev = i
    out.append((start, prev))
    return out


def episode_inventory(joined: list[dict], corpus: list[dict] | None = None,
                      horizon: int = 20) -> dict:
    """Segment the window into engine-EXPANSION EPISODES and describe each one.

    P-001's excursion cells found the binding limit is not horizon or barrier choice but
    EPISODE COUNT: 598 C-bars collapse to a handful of engine-expansion events, so the bar is
    the wrong unit of analysis for F-069 and the episode is the right one. This inventory is a
    LISTING, not a statistic -- with this few episodes any cross-episode average would be a
    number about four things.

    Note the segmentation is on ENGINE state only. The resolver's own EXPANSION occupancy is
    reported as an overlay on those episodes, because on this window it is a strict subset.
    """
    recs = [j["rec"] for j in joined]
    bars = [j["bar"] for j in joined]
    n = len(recs)

    eng_idx = [i for i, r in enumerate(recs) if r.get("engine.crt_state") == "EXPANSION"]
    res_idx = [i for i, r in enumerate(recs) if r.get("ontology_state") == "EXPANSION"]
    eng_eps, res_eps = _runs(eng_idx), _runs(res_idx)

    episodes = []
    for k, (a, b) in enumerate(eng_eps, start=1):
        seg = recs[a: b + 1]
        segbars = bars[a: b + 1]
        labels: dict[str, int] = {}
        sites: dict[str, int] = {}
        for r in seg:
            labels[str(r.get("ontology_state"))] = labels.get(str(r.get("ontology_state")), 0) + 1
            s = str(r.get("resolver.projected_site"))
            sites[s] = sites.get(s, 0) + 1
        overlap = [i for i in res_idx if a <= i <= b]
        atr0 = (recs[a].get("engine.live_context") or {}).get("live_atr")

        # The DECLARED SIDE of this expansion, established two independent ways so the
        # direction-normalized numbers below do not rest on parsing English. (1) the engine's
        # transition reason text, which is free-form and could drift; (2) the sign of the entry
        # candle, which is structural -- try_displacement_to_expansion REQUIRES close>open for
        # LONG and close<open for SHORT, so the candle sign IS the gate's own condition. They
        # are cross-checked; a disagreement voids the side rather than silently picking one.
        side_txt = side_num = None
        for t in (recs[a].get("engine.transitions") or []):
            if t.get("to") == "EXPANSION":
                rs = str(t.get("reason", ""))
                side_txt = "bullish" if "Bullish" in rs else ("bearish" if "Bearish" in rs else None)
        fv0 = recs[a].get("resolver.feature_vector") or {}
        if "open" in fv0 and "close" in fv0:
            side_num = "bullish" if fv0["close"] > fv0["open"] else "bearish"
        side = side_num if (side_txt is None or side_txt == side_num) else None

        # Per-episode excursion. This is the number that shows WHY the episode is the unit:
        # pooling the engine-EXPANSION bars gives one sign, and the two substantial episodes
        # disagree on it. An aggregate that reverses between its own two largest constituents
        # is not describing a property of EXPANSION.
        ep_up, ep_dn = [], []
        if corpus is not None:
            for j in joined[a: b + 1]:
                atr = (j["rec"].get("engine.live_context") or {}).get("live_atr")
                if not atr:
                    continue
                ex = excursion(corpus, j["bar"]["index"], float(atr), horizon)
                if ex:
                    ep_up.append(ex["up"])
                    ep_dn.append(ex["down"])
        hi = max(x["high"] for x in segbars)
        lo = min(x["low"] for x in segbars)
        move = segbars[-1]["close"] - segbars[0]["open"]
        episodes.append({
            "episode": f"E{k}",
            "start_pos": a, "end_pos": b, "duration_bars": b - a + 1,
            "duration_hours": round((b - a + 1) * 0.25, 2),
            "start_ts": recs[a]["timestamp"], "end_ts": recs[b]["timestamp"],
            "right_censored": b == n - 1,
            "price_open": round(segbars[0]["open"], 2),
            "price_close": round(segbars[-1]["close"], 2),
            "price_move": round(move, 2),
            "move_in_atr_at_start": round(move / atr0, 2) if atr0 else None,
            "range_high": round(hi, 2), "range_low": round(lo, 2),
            "resolver_labels": dict(sorted(labels.items(), key=lambda t: -t[1])),
            "resolver_sites": dict(sorted(sites.items(), key=lambda t: -t[1])),
            "resolver_agreed_expansion_bars": len(overlap),
            "resolver_agreement_lag_bars": (min(overlap) - a) if overlap else None,
            f"excursion_H{horizon}_n": len(ep_up),
            f"excursion_H{horizon}_up_median": round(st.median(ep_up), 3) if ep_up else None,
            f"excursion_H{horizon}_down_median": round(st.median(ep_dn), 3) if ep_dn else None,
            f"excursion_H{horizon}_up_minus_down": (
                round(st.median(ep_up) - st.median(ep_dn), 3) if ep_up else None
            ),
            # DIRECTION-NORMALIZED: favourable = travel in the expansion's OWN declared side.
            # This is the number that can actually be read as "did the continuation continue";
            # the raw up/down above cannot, because a bearish expansion travelling correctly
            # produces a large DOWN excursion.
            "declared_side": side,
            "side_agreement_text_vs_candle_sign": (
                None if side_txt is None else side_txt == side_num
            ),
            f"excursion_H{horizon}_favourable_median": (
                round(st.median(ep_up if side == "bullish" else ep_dn), 3)
                if (ep_up and side) else None
            ),
            f"excursion_H{horizon}_adverse_median": (
                round(st.median(ep_dn if side == "bullish" else ep_up), 3)
                if (ep_up and side) else None
            ),
            f"excursion_H{horizon}_favourable_minus_adverse": (
                round(st.median(ep_up if side == "bullish" else ep_dn)
                      - st.median(ep_dn if side == "bullish" else ep_up), 3)
                if (ep_up and side) else None
            ),
        })

    # How the resolver actually REACHED expansion, per bar. Distinguishes "granted the label
    # reluctantly on strong evidence" from "took a rare structural branch once and then dwelled".
    onset = min(res_idx) if res_idx else None
    route_sites: dict[str, int] = {}
    for i in res_idx:
        s = str(recs[i].get("resolver.projected_site"))
        route_sites[s] = route_sites.get(s, 0) + 1

    return {
        "unit_note": (
            "The EPISODE is the unit, not the bar. Engine-EXPANSION bars on this window "
            "collapse into a small number of events; per-bar n is those events resampled."
        ),
        "resolver_expansion_mechanism": {
            "sites_on_resolver_expansion_bars": dict(sorted(route_sites.items(), key=lambda t: -t[1])),
            "site_at_bar_before_onset": (
                str(recs[onset - 1].get("resolver.projected_site")) if onset else None
            ),
            "state_at_bar_before_onset": (
                str(recs[onset - 1].get("ontology_state")) if onset else None
            ),
            "note": (
                "Read this before concluding the resolver 'requires stronger evidence'. On this "
                "config the resolver has exactly ONE reachable route into EXPANSION: "
                "shadow_collapse_expansion. The continuous DISPLACEMENT->EXPANSION funnel is "
                "config-disabled (thresholds.continuous_disp_to_expansion=false) and the "
                "declarative when-block is skipped on entry by the htf_range guard "
                "(crt_state_resolver._resolve_from_features: EXPANSION is skipped unless the "
                "resolver is ALREADY in EXPANSION). So resolver-EXPANSION occupancy is one "
                "entry decision plus unconditional dwell (expansion_dwell_hold), not N "
                "independent grants of the label."
            ),
        },
        "n_engine_expansion_episodes": len(eng_eps),
        "n_resolver_expansion_episodes": len(res_eps),
        "resolver_expansion_is_subset_of_engine": set(res_idx) <= set(eng_idx),
        "engine_expansion_bars": len(eng_idx),
        "resolver_expansion_bars": len(res_idx),
        "episodes": episodes,
    }


FORBIDDEN_KEYS = ("p_value", "pvalue", "ci", "conf_int", "verdict", "significant", "decision")


def assert_no_claim_keys(obj: Any, path: str = "") -> None:
    """A number that does not exist cannot be quoted. Enforce that mechanically."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_KEYS:
                raise AssertionError(f"forbidden claim key '{k}' at {path}")
            assert_no_claim_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for j, v in enumerate(obj):
            assert_no_claim_keys(v, f"{path}[{j}]")


def assert_tail_has_concentration(obj: dict) -> None:
    """No p90/p95 may ship without its concentration companion."""
    for pop, horizons in obj.items():
        for h, cell in horizons.items():
            if cell.get("reach_p90") is not None or cell.get("reach_p95") is not None:
                if "n_distinct_runs_in_top_decile" not in cell:
                    raise AssertionError(f"{pop}/{h}: tail emitted without concentration guard")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stream", default="logs/dual_construction_v2_envelope_safe/XAUUSD_crt_construction.jsonl")
    ap.add_argument("--csv", default="data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv")
    ap.add_argument("--out", default="results/p001_excursion/p001_excursion_probe.json")
    args = ap.parse_args()

    corpus = load_corpus(ROOT / args.csv)
    live = load_live_rows(ROOT / args.stream)
    joined, integrity = join_and_verify(live, corpus)

    print(f"corpus bars      : {len(corpus):,}")
    print(f"envelope LIVE    : {len(live):,}")
    print(f"joined           : {len(joined):,}  unmatched={integrity['unmatched']} "
          f"ohlc_mismatches={integrity['ohlc_mismatches']}")
    if integrity["ohlc_mismatches"]:
        print("FATAL: stream OHLC disagrees with the corpus -- the join is wrong.")
        return 1

    # Population counts BEFORE any excursion is computed (verification gate 3).
    pops = ["A_agree", "B_disagree", "C_engEXP_resNotEXP", "D_engEXP_resEXP",
            "E_engEXP_all", "F_engNotEXP"]
    counts = {p: 0 for p in pops}
    for j in joined:
        for p, hit in classify(j["rec"]).items():
            counts[p] += int(hit)
    print("\npopulations (pre-excursion):")
    for p in pops:
        print(f"  {p:22s} {counts[p]:5d}")

    # Secondary cuts
    resolver_cut, site_cut = {}, {}

    results: dict[str, dict] = {p: {} for p in pops}
    for H in HORIZONS:
        buckets: dict[str, list] = {p: [] for p in pops}
        rc: dict[str, list] = {}
        sc: dict[str, list] = {}
        dropped = 0
        for j in joined:
            rec, bar = j["rec"], j["bar"]
            atr = (rec.get("engine.live_context") or {}).get("live_atr")
            if not atr:
                continue
            e = excursion(corpus, bar["index"], float(atr), H)
            if e is None:
                dropped += 1
                continue
            e["bar_index"] = bar["index"]
            flags = classify(rec)
            for p, hit in flags.items():
                if hit:
                    buckets[p].append(e)
            if flags["C_engEXP_resNotEXP"]:
                rc.setdefault(str(rec.get("ontology_state")), []).append(e)
                sc.setdefault(str(rec.get("resolver.projected_site")), []).append(e)
        for p in pops:
            results[p][f"H{H}"] = summarize(buckets[p], H, len(joined))
            results[p][f"H{H}"]["dropped_truncated"] = dropped
        resolver_cut[f"H{H}"] = {k: summarize(v, H, len(joined)) for k, v in sorted(rc.items())}
        site_cut[f"H{H}"] = {k: summarize(v, H, len(joined)) for k, v in sorted(sc.items())}

    artifact = {
        "probe_id": "P-001",
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "window": args.csv,
        "stream": args.stream,
        "window_note": (
            "Single ~1-month XAUUSD M15 window (2,300 bars). Independent blocks ~= bars/H, so "
            "H40 and H80 are structurally underpowered here; every cell carries its own count."
        ),
        "selection_note": (
            "Population C is selected BECAUSE the engine already took an ATR-extension into "
            "EXPANSION. Forward asymmetry is therefore partly mechanical continuation of a move "
            "already underway (F-030/F-043 REGIME_REDUNDANT shape): real, and fully explicable "
            "by something that is not skill."
        ),
        "direction_limitation": (
            "SCOPE-CORRECTED. In the POOLED populations below (A/B/C/D/E/F) up_exc/down_exc "
            "remain absolute -- above/below entry, not normalized to any expansion's own side "
            "-- so no pooled up>down reading may be called 'the expansion continued'. This "
            "window drifts +3.8% (4181->4341), which loads the same axis. "
            "RESOLVED AT EPISODE LEVEL: the v2.0.0 envelope's engine.transitions field carries "
            "the entry transition, whose reason declares the side, and the entry candle's sign "
            "is the gate's own structural condition (try_displacement_to_expansion requires "
            "close>open for LONG, close<open for SHORT). The two agree 4/4 here, so the "
            "per-episode favourable/adverse figures ARE direction-normalized and may be read as "
            "'did the declared continuation continue'."
        ),
        "episode_limitation": (
            "Population C is 4 contiguous runs and population D is a SINGLE run (the last 75 "
            "bars of the window), so these are 4 and 1 market episodes observed many times, not "
            "598 and 75 independent bars. D was designed as the confound control separating "
            "'engine is expanding' from 'the two disagree'; on this window it does not have the "
            "sample to do that job, and at H=80 it is empty (truncated by corpus end)."
        ),
        "atr_basis": "engine.live_context.live_atr (PRICE UNITS) -- never the canonical close-relative atr (FM-041)",
        "unit_note": "one row per BAR; up/down excursion fully describe it (no long/short duplication)",
        "kernel": "research.measurement.forward_walk with unreachable SL/TP, twin-certified to 1e-10",
        "integrity": integrity,
        "population_counts": counts,
        "episode_inventory": episode_inventory(joined, corpus, horizon=20),
        "populations": results,
        "C_by_resolver_label": resolver_cut,
        "C_by_projected_site": site_cut,
    }
    assert_no_claim_keys(artifact)
    assert_tail_has_concentration(results)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    for H in HORIZONS:
        print(f"\n=== H={H} bars ===")
        print(f"{'population':24s} {'n':>5s} {'eps':>4s} {'blk':>4s} {'pow':>12s} "
              f"{'up_med':>7s} {'dn_med':>7s} {'reach_med':>9s} {'p90':>7s} {'p95':>7s} "
              f"{'gap%':>5s}")
        for p in pops:
            c = results[p][f"H{H}"]
            gp = 100.0 * c["windows_spanning_gap"] / c["n_bars"] if c["n_bars"] else 0.0
            print(f"{p:24s} {c['n_bars']:5d} {c['n_contiguous_runs']:4d} "
                  f"{c['n_independent_blocks']:4d} {c['power']:>12s} "
                  f"{c['up_median'] or 0:7.3f} {c['down_median'] or 0:7.3f} "
                  f"{c['reach_median'] or 0:9.3f} {c['reach_p90'] or 0:7.3f} "
                  f"{c['reach_p95'] or 0:7.3f} {gp:5.0f}")

    inv = artifact["episode_inventory"]
    print(f"\n=== EPISODE INVENTORY (the unit is the episode, not the bar) ===")
    print(f"engine EXPANSION: {inv['engine_expansion_bars']} bars in "
          f"{inv['n_engine_expansion_episodes']} episodes | "
          f"resolver EXPANSION: {inv['resolver_expansion_bars']} bars in "
          f"{inv['n_resolver_expansion_episodes']} | "
          f"resolver subset of engine: {inv['resolver_expansion_is_subset_of_engine']}")
    for e in inv["episodes"]:
        cens = " [RIGHT-CENSORED]" if e["right_censored"] else ""
        lag = e["resolver_agreement_lag_bars"]
        lag_s = f"{lag} bars ({lag * 0.25:.1f}h)" if lag is not None else "never agreed"
        print(f"\n  {e['episode']}  {e['start_ts']} -> {e['end_ts']}{cens}")
        print(f"     duration : {e['duration_bars']} bars ({e['duration_hours']}h)")
        print(f"     price    : {e['price_open']} -> {e['price_close']} "
              f"({e['price_move']:+.2f}, {e['move_in_atr_at_start']:+.2f} ATR)")
        print(f"     resolver : {e['resolver_labels']}")
        print(f"     agreed   : {e['resolver_agreed_expansion_bars']} bars, lag {lag_s}")
        d = e.get("excursion_H20_up_minus_down")
        if d is not None:
            print(f"     exc H20  : up {e['excursion_H20_up_median']:.3f} / "
                  f"dn {e['excursion_H20_down_median']:.3f}  ->  up-dn {d:+.3f}")
        fa = e.get("excursion_H20_favourable_minus_adverse")
        if fa is not None:
            print(f"     side     : {e['declared_side'].upper()} (text==sign: "
                  f"{e['side_agreement_text_vs_candle_sign']})  ->  "
                  f"fav {e['excursion_H20_favourable_median']:.3f} / "
                  f"adv {e['excursion_H20_adverse_median']:.3f}  ->  fav-adv {fa:+.3f}")

    print(f"\nartifact: {out}")
    print("DESCRIPTIVE ONLY -- no significance, no economic claim, no finding id.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
