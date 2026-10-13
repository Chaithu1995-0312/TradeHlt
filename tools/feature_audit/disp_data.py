"""Displacement / retest group on XAUUSD H4 (UTC via declared clock): FM-020 disp_strength, FM-095 retest_depth,
FM-093 candles_since_sweep (e01 identities on the active config). Trunk + branches merged into divergence_h4.json."""
import sys, os, re, json, logging
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
assert CFG["sweep_semantics"] == "e01_lifecycle"
K = CFG["swing_window"]; LB = CFG["retest_lookback"]; BAND = CFG["retest_atr_band_mult"]
DLO, DHI = CFG["disp_strength_clip_low"], CFG["disp_strength_clip_high"]
RLO, RHI = CFG["retest_depth_clip_low"], CFG["retest_depth_clip_high"]
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
o, h, l, c = (raw[k].to_numpy(float) for k in ("open", "high", "low", "close")); n = len(c)
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
NE = len(enr); TSU = enr["timestamp"].astype(str).to_numpy()
OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
WIN = pd.Series(np.arange(NE), index=pd.to_datetime(enr["timestamp"])).reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

# ---- registered recompute ----
atr_abs = AP.sma(AP.true_range(h, l, c), CFG["atr_period"])
atr_rel32 = (atr_abs / c).astype(np.float32).astype(float)        # the pipeline stores atr as float32
denom = atr_rel32 * c
body = np.abs(c - o)
disp = np.clip(body / denom, DLO, DHI)
ema9 = AP.ema_first(c, CFG["ema_fast_span"])
sh, _ = AP.publish(AP.pivots(h, "high", K), h, K); sl, _ = AP.publish(AP.pivots(l, "low", K), l, K)
up, down, up_lv, dn_lv = AP.lifecycle(h, l, c, sh, sl, K)
event = (up | down).astype(int)
recent = AP.roll_any(event, LB)
dist_ema = np.abs(c - ema9) / denom
flag = (recent == 1) & (dist_ema <= BAND)
depth = np.where(flag, np.clip(dist_ema, RLO, RHI), 0.0)
since = np.zeros(n, int); last = None
for i in range(n):
    if event[i]: last = i
    since[i] = 0 if last is None else i - last

# ---- registry text + references ----
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
pct = lambda k: f"{k:,} of {NE:,} bars ({k / NE * 100:.0f}%)"

TRUNK = {
    "disp_strength": ("FM-020", disp, False, f"This bar's body in ATRs: |close − open| ÷ ATR, clipped to [{DLO:g}, {DHI:g}]."),
    "retest_depth": ("FM-095", depth, False, f"On a retest bar, how far the close is from the {CFG['ema_fast_span']}-bar EMA, in ATRs (0 otherwise). A retest bar = a sweep in the last {LB} bars and the close within {BAND:g} ATR of that EMA."),
    "candles_since_sweep": ("FM-093", since.astype(float), True, "Bars since the last sweep event (0 on the sweep bar and before the first one)."),
}
for col, (fm, mine_full, discrete, plain) in TRUNK.items():
    mine = mine_full[ROWS].astype(float); pipe = enr[col].to_numpy(float)
    ok = (mine == pipe) if discrete else (np.abs(mine - pipe) <= np.maximum(1e-6 * np.abs(pipe), 1e-6))
    bad = np.where(~ok)[0]
    D["features"][col] = {"group": "displacement", "fm": fm, "plain": plain, "registered": REG.get(fm),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(np.nanmax(np.abs(mine - pipe))),
                                    "mismatch_first": [{"ts": TSU[i], "mine": float(mine[i]), "pipe": float(pipe[i])} for i in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": []}

def add(col, b, alt_rows=None, mask_rows=None):
    b.setdefault("follows", None); b.setdefault("note", None)
    if alt_rows is not None: b["window"] = [float(x) for x in alt_rows[WIN]]
    if mask_rows is not None: b["window_mask"] = [bool(x) for x in mask_rows[WIN]]
    D["features"][col]["branches"].append(b)

# Branch (implementation): the pipeline stores ema_fast as float32 before measuring the distance
ema32 = ema9.astype(np.float32).astype(float)
dist32 = np.abs(c - ema32) / denom
flag32 = (recent == 1) & (dist32 <= BAND)
depth32 = np.where(flag32, np.clip(dist32, RLO, RHI), 0.0)[ROWS]
pipe_rd = enr["retest_depth"].to_numpy(float)
m32 = int((np.abs(depth32 - pipe_rd) > np.maximum(1e-6 * np.abs(pipe_rd), 1e-6)).sum())
flag_flip = int((flag32 != flag)[ROWS].sum())
add("retest_depth", {"id": "retest_depth-float64", "kind": "implementation", "title": "Measure from the EMA before rounding it to float32", "open": flag_flip > 0,
                     "formula": "same formula with ema_fast kept in float64",
                     "stats": {"Pipeline vs float32-EMA recompute": f"{m32:,} of {NE:,} bars differ (explains the trunk differences)",
                               "Largest difference from float64": f"{np.nanmax(np.abs(depth[ROWS] - pipe_rd)):.1e} ATR",
                               "Retest flag changes": pct(flag_flip)},
                     "decision_label": "retest flag changes", "decision_count": flag_flip,
                     "note": "The pipeline casts ema_fast to float32 (feature_pipeline.compute_canonical_ema_features) and then measures |close − ema_fast|. Same cause as the ema_spread precision branch."})

# Branch: disp_strength clip at 3 ATR (information note)
clipped = int((enr["disp_strength"].to_numpy(float) >= DHI).sum())
add("disp_strength", {"id": "disp-clip", "kind": "definition", "title": f"No upper clip at {DHI:g} ATR", "open": False,
                      "formula": "|close − open| ÷ ATR, unclipped", "stats": {f"Bars at the {DHI:g} clip": pct(clipped),
                      "Largest unclipped value": f"{np.nanmax((body / denom)[ROWS]):.2f} ATR"},
                      "decision_label": "no decision reading uses values above the clip", "decision_count": 0,
                      "note": "The clip is part of the registered formula. It only flattens the few largest bodies, so no known decision reading changes."})

# Branch: textbook retest = price returns to the SWEPT LEVEL (not to the 9-bar EMA)
lvl = np.full(n, np.nan); last_lv = np.nan; last_ev = -10**9
for i in range(n):
    if event[i]:
        cands = up_lv[i] + dn_lv[i]
        last_lv = cands[0]; last_ev = i                 # first swept level on the event bar
    if i - last_ev < LB: lvl[i] = last_lv
dist_lvl = np.abs(c - lvl) / denom
flag_lvl = (recent == 1) & (dist_lvl <= BAND)
depth_lvl = np.where(flag_lvl, np.clip(dist_lvl, RLO, RHI), 0.0)
d_flag = (flag_lvl != flag)[ROWS]
add("retest_depth", {"id": "retest-to-swept-level", "kind": "definition", "title": "Retest = price comes back to the swept level (textbook)",
                     "formula": f"retest bar = a sweep in the last {LB} bars and the close within {BAND:g} ATR of the level that was swept; depth = |close − level| ÷ ATR",
                     "stats": {"Retest flag differs": pct(int(d_flag.sum())),
                               "Retest bars (trunk → branch)": f"{int(flag[ROWS].sum()):,} → {int(flag_lvl[ROWS].sum()):,}",
                               "Both call it a retest": f"{int((flag & flag_lvl)[ROWS].sum()):,} bars"},
                     "decision_label": "retest flag changes", "decision_count": int(d_flag.sum()), "open": bool(d_flag.sum() > 0),
                     "note": "The registered retest_depth measures distance from the 9-bar EMA, so 'depth' is really 'how far from the EMA after a recent sweep'. In SMC/CRT usage a retest is a return to the level that was swept or broken."},
    depth_lvl[ROWS], d_flag)

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in TRUNK:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:20} trunk mism={f['trunk']['mismatch_count']:4} maxdiff={f['trunk']['max_abs_diff']:.2e} refs={len(f['refs']):2} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
print("clipped", clipped, "| retest bars trunk", int(flag[ROWS].sum()), "branch", int(flag_lvl[ROWS].sum()))
