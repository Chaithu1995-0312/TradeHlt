"""Session/time group (FM-051 hour_of_day, FM-052 session) on XAUUSD H4, after the clock fix.

Trunk = pipeline on UTC timestamps (the file's times converted through its declared clock).
The pre-fix behaviour (server time read as UTC) stays visible as a RESOLVED data branch.
"""
import sys, os, re, json, logging
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, _HERE)
logging.disable(logging.WARNING)
import numpy as np
import pandas as pd
from features.feature_pipeline import FeaturePipeline
from h4_loader import load_h4_utc, load_h4_file_time

ACTIVE = open(os.path.join(ROOT, "configs", "production", "ACTIVE_VERSION"), encoding="utf-8").read().strip()   # §4.0
CFG = json.load(open(os.path.join(ROOT, "configs", "production", f"{ACTIVE}.json"), encoding="utf-8"))["feature_pipeline"]
WINS = {k: tuple(v) for k, v in CFG["session_windows_utc"].items()}
raw_utc, CLOCK_ID = load_h4_utc(); raw_file = load_h4_file_time()
assert len(raw_utc) == len(raw_file)
enr, _ = FeaturePipeline(raw_utc.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
ts_utc = pd.to_datetime(enr["timestamp"]); NE = len(enr)
row = pd.Series(np.arange(len(raw_utc)), index=raw_utc["timestamp"]).reindex(ts_utc).to_numpy().astype(int)
ts_file = raw_file["timestamp"].iloc[row].reset_index(drop=True)

OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
pos = pd.Series(np.arange(NE), index=ts_utc)
WIN = pos.reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

ASIA, LONDON, NEWYORK, OVERLAP, CLOSED = 0, 1, 2, 3, 4
NAMES = {0: "ASIA", 1: "LONDON", 2: "NEWYORK", 3: "OVERLAP", 4: "CLOSED"}
def inw(hh, w): return w[0] <= hh < w[1]
def classify(hh):
    lo, ny, asia = inw(hh, WINS["LONDON"]), inw(hh, WINS["NEWYORK"]), inw(hh, WINS["ASIA"])
    if lo and ny: return OVERLAP
    if ny: return NEWYORK
    if lo: return LONDON
    if asia: return ASIA
    return CLOSED

hour_u = ts_utc.dt.hour.to_numpy(); sess_u = np.array([classify(x) for x in hour_u])
hour_f = ts_file.dt.hour.to_numpy(); sess_f = np.array([classify(x) for x in hour_f])
pipe_h = enr["hour_of_day"].to_numpy(float); pipe_s = enr["session"].to_numpy(float)
dist = lambda a: {NAMES[k]: int((a == k).sum()) for k in range(5)}
pct = lambda k: f"{k:,} of {NE:,} bars ({k / NE * 100:.0f}%)"
h_diff = int((hour_f != hour_u).sum()); s_diff = int((sess_f != sess_u).sum())

def classify_dst(t):
    tz = pd.Timestamp(t).tz_localize("UTC")
    lon = tz.tz_convert("Europe/London").hour; nyc = tz.tz_convert("America/New_York").hour
    lo, nyy, asia = 8 <= lon < 17, 8 <= nyc < 17, inw(tz.hour, WINS["ASIA"])
    if lo and nyy: return OVERLAP
    if nyy: return NEWYORK
    if lo: return LONDON
    if asia: return ASIA
    return CLOSED
sess_dst = np.array([classify_dst(t) for t in ts_utc]); dst_diff = int((sess_dst != sess_u).sum())
def majority(hh):
    labs = [classify((hh + k) % 24) for k in range(4)]
    vals, cnt = np.unique(labs, return_counts=True); best = vals[cnt == cnt.max()]
    return classify(hh) if classify(hh) in best else int(best[0])
sess_maj = np.array([majority(x) for x in hour_u]); maj_diff = int((sess_maj != sess_u).sum())

SRC = []
for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f)
            SRC.append((os.path.relpath(p, os.path.join(ROOT, "src")).replace("\\", "/"), open(p, encoding="utf-8", errors="ignore").read()))
def refs(name):
    pat = re.compile(r"[\"']" + re.escape(name) + r"[\"']")
    return sorted(p for p, t in SRC if pat.search(t) and not p.startswith("features/feature_pipeline.py"))

def feat(col, fm, plain, registered, mine_full, pipe_full, branches):
    bad = np.where(mine_full != pipe_full)[0]
    return {"group": "session", "fm": fm, "plain": plain, "registered": registered,
            "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "mismatch_first": [{"ts": str(ts_utc.iloc[i]), "mine": float(mine_full[i]), "pipe": float(pipe_full[i])} for i in bad[:25]],
                      "max_abs_diff": float(np.abs(mine_full - pipe_full).max())},
            "window_pipe": [float(x) for x in pipe_full[WIN]], "window_mine": [float(x) for x in mine_full[WIN]],
            "refs": refs(col), "branches": branches}

RESOLVED = "Resolved 2026-10-14: the H4 file's clock was declared (mt5_icmarkets_xau) and this report now converts its times to UTC. Numbers below are what was wrong before the fix."
b_hour = {"id": "hour-utc", "kind": "data", "title": "Before the fix: server time read as UTC", "open": False, "resolved": True,
          "formula": "hour of the file's server time (UTC+2 winter / UTC+3 summer)",
          "stats": {"Hour was wrong on": pct(h_diff)}, "decision_label": "resolved by the clock decision", "decision_count": h_diff,
          "note": RESOLVED, "follows": "h4-clock"}
b_sess = {"id": "session-utc", "kind": "data", "title": "Before the fix: sessions labelled on server time", "open": False, "resolved": True,
          "formula": "same windows applied to the server-time hour",
          "stats": {"Session was wrong on": pct(s_diff), "Labels before (server time)": ", ".join(f"{k} {v:,}" for k, v in dist(sess_f).items()),
                    "Labels now (UTC)": ", ".join(f"{k} {v:,}" for k, v in dist(sess_u).items())},
          "decision_label": "resolved by the clock decision", "decision_count": s_diff, "note": RESOLVED, "follows": "h4-clock"}
b_dst = {"id": "session-dst-local", "kind": "definition", "title": "Session windows follow daylight saving", "open": dst_diff > 0,
         "formula": "London and New York sessions = 08:00–17:00 local time all year; Asia unchanged",
         "stats": {"Session differs from fixed UTC windows": pct(dst_diff)}, "decision_label": "session label changes", "decision_count": dst_diff,
         "note": "On H4 open hours the fixed UTC windows and the daylight-saving windows give the same label.", "follows": None,
         "window": [float(x) for x in sess_dst[WIN]], "window_mask": [bool(x) for x in (sess_dst != sess_u)[WIN]]}
b_maj = {"id": "session-bar-majority", "kind": "definition", "title": "Label a 4-hour bar by the session of most of its hours", "open": maj_diff > 0,
         "formula": "session of hours h, h+1, h+2, h+3; the most common one (ties keep the open hour's session)",
         "stats": {"Session differs from open-hour label": pct(maj_diff), "Majority labels": ", ".join(f"{k} {v:,}" for k, v in dist(sess_maj).items()),
                   "Open-hour labels (trunk)": ", ".join(f"{k} {v:,}" for k, v in dist(sess_u).items())},
         "decision_label": "session label changes", "decision_count": maj_diff,
         "note": "The registered rule labels a bar by its open hour. On M15 that is nearly the same thing; an H4 bar spans four hours and can cross a session boundary.",
         "follows": None, "window": [float(x) for x in sess_maj[WIN]], "window_mask": [bool(x) for x in (sess_maj != sess_u)[WIN]]}

D["features"]["hour_of_day"] = feat("hour_of_day", "FM-051", "The UTC hour of the bar's open.", "timestamp.dt.hour -> int8",
                                    hour_u.astype(float), pipe_h, [b_hour])
D["features"]["session"] = feat("session", "FM-052", "Trading session of the bar's open hour, from fixed UTC windows: ASIA [0,9), LONDON [7,16), NEWYORK [12,21). Both London and New York = OVERLAP; none = CLOSED.",
                                "window model over session_windows_utc, half-open [start, end): OVERLAP if in LONDON and NEWYORK; else NEWYORK; else LONDON; else ASIA; else CLOSED",
                                sess_u.astype(float), pipe_s, [b_dst, b_maj, b_sess])
json.dump(D, open(OUTP, "w"), indent=1, default=float)
print("clock", CLOCK_ID, "| trunk hour mism", D["features"]["hour_of_day"]["trunk"]["mismatch_count"], "session mism", D["features"]["session"]["trunk"]["mismatch_count"])
print("before-fix hour wrong", h_diff, "session wrong", s_diff, "| dst", dst_diff, "| majority", maj_diff)
print("UTC labels", dist(sess_u))
