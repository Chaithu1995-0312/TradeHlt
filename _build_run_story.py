#!/usr/bin/env python
"""Build the run_20260909_202201 story: enrich the frozen 69-create census with
timestamp-joined OHLC + per-create compact story strings, and emit the run story.

Read-only join of frozen artifacts (census.json) + corpus CSV. DESCRIPTIVE_ONLY,
economic_claims_allowed=false. No promotion, no code/config/finding change.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"D:/Tradelatest")
CENSUS = ROOT / "results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/census.json"
CSV = ROOT / "data/mt5/XAUUSD_M15.csv"
OUT_JSON = ROOT / "results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/story_rows.json"

# --- load census ---
census = json.load(open(CENSUS, encoding="utf-8"))
rows = census["rows"]


def fmt_ts(ts: str) -> str:
    return ts.replace("T", " ")


# --- load corpus OHLC by timestamp ---
by_ts = {}
with open(CSV, encoding="utf-8", errors="replace") as f:
    rdr = csv.reader(f)
    header = next(rdr)
    for r in rdr:
        by_ts[r[0]] = r  # [ts, open, high, low, close, volume]

# --- enrich ---
story_rows = []
miss = 0
for r in sorted(rows, key=lambda x: x["timestamp"]):
    ts = fmt_ts(r["timestamp"])
    ohlc = by_ts.get(ts)
    rec = dict(r)
    if ohlc is None:
        miss += 1
        rec["open"] = rec["high"] = rec["low"] = rec["close"] = rec["volume"] = None
    else:
        rec["open"] = float(ohlc[1])
        rec["high"] = float(ohlc[2])
        rec["low"] = float(ohlc[3])
        rec["close"] = float(ohlc[4])
        rec["volume"] = float(ohlc[5])

    dir_mem = rec.get("pending_dir", "NA")
    dir_tb = rec.get("trendbias_dir", "NA")
    tt = rec.get("t1_t3", "NA")
    sess = rec.get("session_bucket", "NA")
    crt = rec.get("parent_crt", "NA")
    atr = rec.get("live_atr")
    atr_s = f"{atr:.1f}" if isinstance(atr, (int, float)) else "NA"
    fate = rec.get("outcome", "NA")
    closed = rec.get("closed_idx")
    age = rec.get("age_at_reset")
    h20 = rec.get("memory_dir_H20")
    h100 = rec.get("memory_dir_H100")
    h20s = f"{h20:+.2f}" if isinstance(h20, (int, float)) else "NA"
    h100s = f"{h100:+.2f}" if isinstance(h100, (int, float)) else "NA"

    o = rec.get("open"); h = rec.get("high"); l = rec.get("low"); cl = rec.get("close")
    oh = f"{o:.1f}" if o is not None else "NA"
    hh = f"{h:.1f}" if h is not None else "NA"
    ll = f"{l:.1f}" if l is not None else "NA"
    cc = f"{cl:.1f}" if cl is not None else "NA"

    rec["story"] = (
        f"{ts} c={rec['created_idx']} OHLC={oh}/{hh}/{ll}/{cc} sess={sess} "
        f"CRT={crt} T1/T3={tt} mem={dir_mem}/tb={dir_tb} ATR={atr_s} "
        f"fate={fate}@{closed}(age={age}) H20={h20s} H100={h100s}"
    )
    story_rows.append(rec)

# --- summary ---
from collections import Counter
outcome = Counter(r.get("outcome") for r in story_rows)
parent = Counter(r.get("parent_crt") for r in story_rows)
session = Counter(r.get("session_bucket") for r in story_rows)
tt = Counter(r.get("t1_t3") for r in story_rows)

arc = {
    "total": len(story_rows),
    "ohlc_join_hits": len(story_rows) - miss,
    "ohlc_join_miss": miss,
    "timespan": [story_rows[0]["timestamp"], story_rows[-1]["timestamp"]],
    "outcome_counts": dict(outcome),
    "parent_crt_counts": dict(parent),
    "session_counts": dict(session),
    "t1_t3_counts": dict(tt),
    "funnel": {
        "CREATE": 69,
        "EXPIRE_TTL": 45,
        "CLEAR_NON_HTF": 17,
        "RESTORE": 6,
        "OVERWRITE": 1,
    },
    "signal_bundle": {
        "candidate": "t1_t3=DISAGREE reinforced by session=LONDON_NY_OVERLAP_13_17",
        "note": "economic_claims_allowed=false; no promotion; every positive-lift cell n<30 INSUFFICIENT",
    },
}

artifact = {
    "artifact": "phase1_run_story_run_20260909_202201",
    "parent_run_id": "run_20260909_202201",
    "source_run_id": "run_20260906_013609",
    "claim_class": "DESCRIPTIVE_ONLY",
    "economic_claims_allowed": False,
    "authority": "none",
    "object": "69-create HTF-displacement pending-memory run story (OHLC + state + fate + H20-H100)",
    "summary": arc,
    "rows": story_rows,
}

OUT_JSON.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
print(f"WROTE {OUT_JSON}")
print(f"rows={len(story_rows)} ohlc_join_miss={miss}")
print("outcome", dict(outcome))
print("timespan", story_rows[0]["timestamp"], "->", story_rows[-1]["timestamp"])