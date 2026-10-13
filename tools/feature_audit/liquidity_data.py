"""Liquidity group on XAUUSD H4 (UTC via declared clock): FM-025 liquidity_distance, FM-026 liquidity_pressure_score.
Trunk + branches merged into divergence_h4.json."""
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
K = CFG["swing_window"]; DECAY = CFG["liquidity_decay_coeff"]; SENT = CFG["liquidity_nan_sentinel"]
COMPRESSED = 0.7      # market_state_cluster_engine.py:224 — liquidity_pressure > 0.7 -> "compressed"
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
atr_px = (atr_abs / c).astype(np.float32).astype(float) * c          # pipeline: atr (float32) * close
sh, last_h = AP.publish(AP.pivots(h, "high", K), h, K); sl, last_l = AP.publish(AP.pivots(l, "low", K), l, K)
ref_h = np.r_[np.nan, last_h[:-1]]; ref_l = np.r_[np.nan, last_l[:-1]]
bos_lv = np.full(n, np.nan); cur = np.nan
for i in range(n):
    if np.isfinite(ref_h[i]) and c[i] > ref_h[i]: cur = ref_h[i]
    elif np.isfinite(ref_l[i]) and c[i] < ref_l[i]: cur = ref_l[i]
    bos_lv[i] = cur
def nearest(cands, i):
    vals = [abs(c[i] - x) for x in cands if np.isfinite(x)]
    return min(vals) if vals else np.nan
dist = np.array([nearest((ref_h[i], ref_l[i], bos_lv[i]), i) / atr_px[i] if atr_px[i] > 0 else np.nan for i in range(n)])
dist = np.where(np.isnan(dist), np.nan, np.maximum(dist, 0.0))
press = np.clip(np.exp(DECAY * np.where(np.isnan(dist), SENT, dist)), 0.0, 1.0)

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
    "liquidity_distance": ("FM-025", dist, "Distance from the close to the nearest of: the last swing high, the last swing low, and the level of the last break of structure, in ATRs."),
    "liquidity_pressure_score": ("FM-026", press, f"exp({DECAY:g} × liquidity_distance), clipped to [0, 1]; a missing distance counts as {SENT:g}. Closer to a level = nearer 1."),
}
for col, (fm, mine_full, plain) in TRUNK.items():
    mine = mine_full[ROWS].astype(float); pipe = enr[col].to_numpy(float)
    both = ~np.isnan(mine) & ~np.isnan(pipe)
    ok = np.zeros(NE, bool); ok[both] = np.abs(mine[both] - pipe[both]) <= np.maximum(1e-6 * np.abs(pipe[both]), 1e-6)
    ok |= np.isnan(mine) & np.isnan(pipe)
    bad = np.where(~ok)[0]
    D["features"][col] = {"group": "liquidity", "fm": fm, "plain": plain, "registered": REG.get(fm),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(np.nanmax(np.abs(mine - pipe))),
                                    "mismatch_first": [{"ts": TSU[i], "mine": None if np.isnan(mine[i]) else float(mine[i]), "pipe": None if np.isnan(pipe[i]) else float(pipe[i])} for i in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": []}

def add(col, b, alt_rows=None, mask_rows=None):
    b.setdefault("follows", None); b.setdefault("note", None)
    if alt_rows is not None: b["window"] = [float(x) for x in alt_rows[WIN]]
    if mask_rows is not None: b["window_mask"] = [bool(x) for x in mask_rows[WIN]]
    D["features"][col]["branches"].append(b)

# Branch: liquidity = levels still ACTIVE (not yet swept or closed through), the same book the sweep features use
snap = AP.active_levels_before_bar(h, l, c, sh, sl, K)
dist_a = np.array([nearest(snap[i], i) / atr_px[i] if (atr_px[i] > 0 and snap[i]) else np.nan for i in range(n)])
press_a = np.clip(np.exp(DECAY * np.where(np.isnan(dist_a), SENT, dist_a)), 0.0, 1.0)
p_trunk = enr["liquidity_pressure_score"].to_numpy(float); p_br = press_a[ROWS]
d_cls = (p_br > COMPRESSED) != (p_trunk > COMPRESSED)
n_levels = np.array([len(snap[i]) for i in range(n)])[ROWS]
# How often the trunk's nearest level is one that is no longer active (already swept or closed through)
stale = 0
for r, i in enumerate(ROWS):
    cands = [x for x in (ref_h[i], ref_l[i], bos_lv[i]) if np.isfinite(x)]
    if not cands or not (atr_px[i] > 0): continue
    best = min(cands, key=lambda x: abs(c[i] - x))
    if not any(abs(best - a) < 1e-9 for a in snap[i]): stale += 1
add("liquidity_pressure_score", {"id": "liquidity-active-levels", "kind": "definition",
    "title": "Measure to levels still untaken (active swing levels, as the sweep features use)",
    "formula": "nearest of all swing levels not yet swept or closed through, known before the bar opens; same exp decay",
    "stats": {"'Compressed' (pressure > 0.7) differs": pct(int(d_cls.sum())),
              "Trunk's nearest level is already swept or broken": pct(stale),
              "Bars with no active level (distance missing)": pct(int(np.isnan(dist_a[ROWS]).sum())),
              "Active levels per bar (median)": f"{int(np.median(n_levels))}"},
    "decision_label": "'compressed' class changes", "decision_count": int(d_cls.sum()), "open": bool(d_cls.sum() > 0),
    "note": "The registered distance uses the last swing high, the last swing low (even after they were swept) and the last break-of-structure level, which price has by definition closed through. The sweep features (FM-090) already track which levels are still untaken. The 0.7 cut-off is read by market_state_cluster_engine.py:224 (a sidecar, F-012)."},
    p_br, d_cls)
add("liquidity_distance", {"id": "liquidity_distance-active", "kind": "definition", "title": "Distance to untaken levels (follows the pressure decision)",
    "formula": "nearest active swing level ÷ ATR", "stats": {"Distance below 0.71 ATR differs": pct(int(d_cls.sum()))},
    "decision_label": "class changes", "decision_count": int(d_cls.sum()), "open": bool(d_cls.sum() > 0), "follows": "liquidity-active-levels"},
    dist_a[ROWS], d_cls)

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in TRUNK:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:25} trunk mism={f['trunk']['mismatch_count']:4} maxdiff={f['trunk']['max_abs_diff']:.2e} refs={len(f['refs']):2} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
print("stale nearest", stale, "| compressed trunk", int((p_trunk > COMPRESSED).sum()), "branch", int((p_br > COMPRESSED).sum()))
