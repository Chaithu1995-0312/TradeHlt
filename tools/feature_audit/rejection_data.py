"""Rejection-block group on XAUUSD H4 (UTC via declared clock): FM-124..127.

Independent re-derivation of the registered rule (does not import features.smc.rejection), same
per-bar trailing window (feature_pipeline.smc_max_window). Trunk + branches -> divergence_h4.json.
"""
import sys, os, re, json, logging, math
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, _HERE)
logging.disable(logging.WARNING)
import numpy as np
import pandas as pd
import yaml
from features.feature_pipeline import FeaturePipeline
from h4_loader import load_h4_utc
import audit_primitives as AP

ACTIVE = open(os.path.join(ROOT, "configs", "production", "ACTIVE_VERSION"), encoding="utf-8").read().strip()   # §4.0
CFG = json.load(open(os.path.join(ROOT, "configs", "production", f"{ACTIVE}.json"), encoding="utf-8"))["feature_pipeline"]
K = CFG["swing_window"]; W = int(CFG["smc_max_window"])
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
o, h, l, c = (raw[k].to_numpy(float) for k in ("open", "high", "low", "close")); n = len(c)
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
NE = len(enr); TSU = enr["timestamp"].astype(str).to_numpy()
OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
WIN = pd.Series(np.arange(NE), index=pd.to_datetime(enr["timestamp"])).reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

atr_abs = AP.sma(AP.true_range(h, l, c), CFG["atr_period"])
atr_i = np.where(np.isnan(atr_abs), 0.0, (atr_abs / c).astype(np.float32).astype(float) * c)
ph = AP.pivots(h, "high", K); pl = AP.pivots(l, "low", K)
upper = h - np.maximum(o, c); lower = np.minimum(o, c) - l

def tanh_dist(close, edge, atr, sign):
    return 0.0 if atr <= 0 else math.tanh(sign * (close - edge) / atr)

def blocks(window, textbook=False):
    """Per bar: latest live (bull_lo, bull_hi) and (bear_lo, bear_hi), or None.
    Registered kill: bear dies on a later close > high OR a later high >= body top (any trade into the wick);
    bull mirrored. textbook=True: dies only on a close beyond the wick extreme."""
    bull_z = [None] * n; bear_z = [None] * n
    for i in range(n):
        s = max(0, i - window + 1)
        bull = bear = None
        for j in range(i - K, s + K - 1, -1):
            a, b = j + K + 1, i                       # bars after the confirming window
            if bear is None and ph[j] and upper[j] > 0:
                top = h[j] - upper[j]
                if textbook:
                    dead = a <= b and np.any(c[a:b + 1] > h[j])
                else:
                    dead = a <= b and (np.any(c[a:b + 1] > h[j]) or np.any(h[a:b + 1] >= top))
                if not dead: bear = (top, h[j])
            if bull is None and pl[j] and lower[j] > 0:
                bot = l[j] + lower[j]
                if textbook:
                    dead = a <= b and np.any(c[a:b + 1] < l[j])
                else:
                    dead = a <= b and (np.any(c[a:b + 1] < l[j]) or np.any(l[a:b + 1] <= bot))
                if not dead: bull = (l[j], bot)
            if bull is not None and bear is not None: break
        bull_z[i], bear_z[i] = bull, bear
    return bull_z, bear_z

def features(bull_z, bear_z):
    bp = np.array([z is not None for z in bull_z], float); rp = np.array([z is not None for z in bear_z], float)
    bd = np.array([0.0 if z is None else tanh_dist(c[i], z[1], atr_i[i], 1) for i, z in enumerate(bull_z)])
    rd = np.array([0.0 if z is None else tanh_dist(c[i], z[0], atr_i[i], -1) for i, z in enumerate(bear_z)])
    inside_bull = np.array([z is not None and z[0] <= c[i] <= z[1] for i, z in enumerate(bull_z)])
    inside_bear = np.array([z is not None and z[0] <= c[i] <= z[1] for i, z in enumerate(bear_z)])
    return bp, rp, bd, rd, inside_bull, inside_bear

bull_t, bear_t = blocks(W)
bp, rp, bd, rd, in_bu, in_be = features(bull_t, bear_t)

onto = yaml.safe_load(open(os.path.join(ROOT, "configs", "formulas", "market_ontology.yaml"), encoding="utf-8"))
REG = {}
def walk(x):
    if isinstance(x, dict):
        if isinstance(x.get("id"), str) and x["id"].startswith("FM-"): REG.setdefault(x["id"], x.get("formula"))
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
walk(onto)
SRC = []
for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f); SRC.append((os.path.relpath(p, os.path.join(ROOT, "src")).replace("\\", "/"), open(p, encoding="utf-8", errors="ignore").read()))
def refs(name):
    pat = re.compile(r"[\"']" + re.escape(name) + r"[\"']")
    return sorted(p for p, t in SRC if pat.search(t) and not p.startswith("features/feature_pipeline.py"))
pct = lambda k_: f"{k_:,} of {NE:,} bars ({k_ / NE * 100:.0f}%)"

TRUNK = {
    "rejection_bull_present": ("FM-124", bp, True, "1 when a live bullish rejection block exists: the lower wick of a confirmed swing low that no later bar has traded into or closed below."),
    "rejection_bear_present": ("FM-125", rp, True, "1 when a live bearish rejection block exists: the upper wick of a confirmed swing high that no later bar has traded into or closed above."),
    "rejection_bull_distance": ("FM-126", bd, False, "Signed distance (tanh of ATRs) from the close to the bullish block's body bottom. Positive = above it. 0 if none."),
    "rejection_bear_distance": ("FM-127", rd, False, "Signed distance to the bearish block's body top. Positive = below it. 0 if none."),
}
for col, (fm, mine_full, discrete, plain) in TRUNK.items():
    mine = mine_full[ROWS].astype(float); pipe = enr[col].to_numpy(float)
    ok = (mine == pipe) if discrete else (np.abs(mine - pipe) <= np.maximum(1e-6 * np.abs(pipe), 1e-6))
    bad = np.where(~ok)[0]
    D["features"][col] = {"group": "rejection", "fm": fm, "plain": plain, "registered": REG.get(fm),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(np.nanmax(np.abs(mine - pipe))),
                                    "mismatch_first": [{"ts": TSU[r], "mine": float(mine[r]), "pipe": float(pipe[r])} for r in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": []}

def add(col, b, alt_rows=None, mask_rows=None):
    b.setdefault("follows", None); b.setdefault("note", None)
    if alt_rows is not None: b["window"] = [float(x) for x in alt_rows[WIN]]
    if mask_rows is not None: b["window_mask"] = [bool(x) for x in mask_rows[WIN]]
    D["features"][col]["branches"].append(b)

# B1: textbook invalidation (close beyond the wick extreme only); a retest into the wick keeps the block
bull_x, bear_x = blocks(W, textbook=True)
bp2, rp2, bd2, rd2, in_bu2, in_be2 = features(bull_x, bear_x)
d_bull = (bp2 != bp)[ROWS] | (np.sign(bd2) != np.sign(bd))[ROWS]
d_bear = (rp2 != rp)[ROWS] | (np.sign(rd2) != np.sign(rd))[ROWS]
add("rejection_bear_present", {"id": "rejection-textbook-invalidation", "kind": "definition",
    "title": "Keep the block while price retests the wick; end it only on a close beyond the wick's extreme (textbook)",
    "formula": "bearish block dies on a later close above its high (bullish: close below its low); trading into the wick no longer kills it",
    "stats": {"Bearish block presence or side differs": pct(int(d_bear.sum())), "Bullish block presence or side differs": pct(int(d_bull.sum())),
              "Close inside a live bearish block (trunk → branch)": f"{int(in_be[ROWS].sum()):,} → {int(in_be2[ROWS].sum()):,} bars",
              "Close inside a live bullish block (trunk → branch)": f"{int(in_bu[ROWS].sum()):,} → {int(in_bu2[ROWS].sum()):,} bars",
              "Bearish block live (trunk → branch)": f"{int(rp[ROWS].sum()):,} → {int(rp2[ROWS].sum()):,} bars",
              "Bullish block live (trunk → branch)": f"{int(bp[ROWS].sum()):,} → {int(bp2[ROWS].sum()):,} bars"},
    "decision_label": "block presence or side changes", "decision_count": int((d_bear | d_bull).sum()), "open": bool((d_bear | d_bull).sum() > 0),
    "note": "Under the registered rule the first bar that trades into the wick ends the block, so the feature can never say 'price is inside a rejection block now', which is the moment the textbook setup is about. features/smc/rejection.py:46 and :53."},
    rp2[ROWS], d_bear)
for col, ser, mask in (("rejection_bull_present", bp2, d_bull), ("rejection_bull_distance", bd2, d_bull), ("rejection_bear_distance", rd2, d_bear)):
    add(col, {"id": f"{col}-textbook", "kind": "definition", "title": "Textbook invalidation (follows the rejection-block decision)",
              "formula": "same rule as the bearish-presence branch", "stats": {"Presence or side differs": pct(int(mask.sum()))},
              "decision_label": "presence or side changes", "decision_count": int(mask.sum()), "open": bool(mask.sum() > 0),
              "follows": "rejection-textbook-invalidation"}, ser[ROWS], mask)

# B2: the trailing window also decides which blocks exist (follows the SMC window decision)
bull_w, bear_w = blocks(300)
bpw, rpw, *_ = features(bull_w, bear_w)
d_w = (bpw != bp)[ROWS] | (rpw != rp)[ROWS]
add("rejection_bull_present", {"id": "rejection-window-300", "kind": "implementation", "title": f"Look back 300 bars instead of {W} (follows the SMC window decision)",
    "formula": "same rule over the last 300 bars", "stats": {"Bull or bear presence differs": pct(int(d_w.sum()))},
    "decision_label": "presence changes", "decision_count": int(d_w.sum()), "open": bool(d_w.sum() > 0), "follows": "smc-window-300"},
    bpw[ROWS], d_w)

# Duplicate implementation in the chart tool: confirm it gives the same blocks (tools/xau_chart/smc_zone_prices.py)
dup_note = {"where": "tools/xau_chart/smc_zone_prices.py:32 and tools/xau_chart/README.md",
            "text": "the chart tool keeps its own copy of the rejection-block rule and its README says the rule is 'not in the repo'; FM-124..127 (features/smc/rejection.py) now are. Same rule today, but two copies can drift."}
gaps = D.setdefault("doc_gaps", [])
if dup_note not in gaps: gaps.append(dup_note)

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in TRUNK:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:25} trunk mism={f['trunk']['mismatch_count']:4} maxdiff={f['trunk']['max_abs_diff']:.2e} refs={len(f['refs']):2} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
print("inside bear", int(in_be[ROWS].sum()), "->", int(in_be2[ROWS].sum()), "| inside bull", int(in_bu[ROWS].sum()), "->", int(in_bu2[ROWS].sum()))
