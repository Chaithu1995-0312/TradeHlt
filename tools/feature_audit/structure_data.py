"""Sweeps / structure group on XAUUSD H4 (UTC via declared clock): trunk + branches, merged into divergence_h4.json.

Independent recompute: plain loops for pivots, causal publication, pierce events, BOS, the MKT-E01 level
lifecycle (own level book, not features.level_lifecycle) and the swing-sequence states.
"""
import sys, os, re, json, logging
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, _HERE)
logging.disable(logging.WARNING)
import numpy as np
import pandas as pd
from features.feature_pipeline import FeaturePipeline
from h4_loader import load_h4_utc

ACTIVE = open(os.path.join(ROOT, "configs", "production", "ACTIVE_VERSION"), encoding="utf-8").read().strip()   # §4.0
CFG = json.load(open(os.path.join(ROOT, "configs", "production", f"{ACTIVE}.json"), encoding="utf-8"))["feature_pipeline"]
K = CFG["swing_window"]; DSW = CFG["double_sweep_window"]
assert CFG["sweep_semantics"] == "e01_lifecycle"
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
h, l, c = (raw[k].to_numpy(float) for k in ("high", "low", "close")); n = len(c)
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
NE = len(enr)
OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
WIN = pd.Series(np.arange(NE), index=pd.to_datetime(enr["timestamp"])).reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

import audit_primitives as AP
def pivots(x, kind, strict=False): return AP.pivots(x, kind, K, strict)
def publish(piv, x): return AP.publish(piv, x, K)
def lifecycle(sh, sl): return AP.lifecycle(h, l, c, sh, sl, K)[:2]

def sequence_states(sh, sl, last_h, last_l):
    """Registered FM-121..123 text: on a confirmation bar compare the new last-swing price with the
    same series one bar earlier (strict); state persists; 0 until two swings of that side."""
    hl = np.zeros(n, int); lh = np.zeros(n, int); sw = np.zeros(n, int)
    s_hh = s_hl = s_lh = s_ll = False; hk = lk = False
    for i in range(1, n):
        if sl[i] == 1 and np.isfinite(last_l[i]) and np.isfinite(last_l[i - 1]):
            s_hl, s_ll, lk = last_l[i] > last_l[i - 1], last_l[i] < last_l[i - 1], True
        if sh[i] == 1 and np.isfinite(last_h[i]) and np.isfinite(last_h[i - 1]):
            s_hh, s_lh, hk = last_h[i] > last_h[i - 1], last_h[i] < last_h[i - 1], True
        hl[i] = int(lk and s_hl); lh[i] = int(hk and s_lh)
        if hk and lk and not (s_hh and hl[i]) and not (lh[i] and s_ll): sw[i] = 1
    return hl, lh, sw, (lambda: None)

roll_any = AP.roll_any

# ---- trunk (registered) ----
ph, pl = pivots(h, "high"), pivots(l, "low")
sh, last_h = publish(ph, h); sl, last_l = publish(pl, l)
ref_h = np.r_[np.nan, last_h[:-1]]; ref_l = np.r_[np.nan, last_l[:-1]]
with np.errstate(invalid="ignore"):
    hh = (h > ref_h).astype(int); ll = (l < ref_l).astype(int)
    bos = np.where(c > ref_h, 1, np.where(c < ref_l, -1, 0))
up, down = lifecycle(sh, sl)
lsweep = np.where(up == 1, 1, np.where(down == 1, -1, 0))
dsweep = (roll_any(up, DSW) & roll_any(down, DSW)).astype(int)
hl, lh, sw, _ = sequence_states(sh, sl, last_h, last_l)

TRUNK = {
    "swing_high": ("FM-045", sh, "1 on the bar a swing high is confirmed: a high equal to the highest of the 5 bars around it, published 2 bars later."),
    "swing_low": ("FM-046", sl, "1 on the bar a swing low is confirmed (mirror of swing_high)."),
    "higher_high": ("FM-055", hh, "1 when this bar's high goes above the last confirmed swing high (a one-bar pierce)."),
    "lower_low": ("FM-056", ll, "1 when this bar's low goes below the last confirmed swing low (a one-bar pierce)."),
    "higher_low": ("FM-121", hl, "1 while the latest confirmed swing low is higher than the one before it."),
    "lower_high": ("FM-122", lh, "1 while the latest confirmed swing high is lower than the one before it."),
    "sideways": ("FM-123", sw, "1 when both swing pairs are known and they are neither higher-high + higher-low nor lower-high + lower-low."),
    "break_of_structure": ("FM-057", bos, "+1 when the close is above the last swing high, −1 below the last swing low, else 0."),
    "liquidity_sweep": ("FM-090", lsweep, "+1 when any active swing-high level is swept (high above, close back below); else −1 for a swing-low level. A level ends once swept or closed through."),
    "sweep_detected": ("FM-091", (lsweep != 0).astype(int), "1 on any sweep event (FM-090 not 0)."),
    "double_sweep": ("FM-092", dsweep, f"1 when at least one upper and one lower sweep event happened in the last {DSW} bars."),
}

onto = __import__("yaml").safe_load(open(os.path.join(ROOT, "configs", "formulas", "market_ontology.yaml"), encoding="utf-8"))
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
TSU = enr["timestamp"].astype(str).to_numpy()

for col, (fm, mine_full, plain) in TRUNK.items():
    mine = mine_full[ROWS].astype(float); pipe = enr[col].to_numpy(float)
    bad = np.where(mine != pipe)[0]
    D["features"][col] = {"group": "structure", "fm": fm, "plain": plain, "registered": REG.get(fm),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(np.abs(mine - pipe).max()),
                                    "mismatch_first": [{"ts": TSU[i], "mine": float(mine[i]), "pipe": float(pipe[i])} for i in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": []}

def add(col, b, alt_rows=None, mask_rows=None):
    if alt_rows is not None: b["window"] = [float(x) for x in alt_rows[WIN]]
    if mask_rows is not None: b["window_mask"] = [bool(x) for x in mask_rows[WIN]]
    b.setdefault("follows", None); b.setdefault("note", None)
    D["features"][col]["branches"].append(b)

# Branch 1: strict (textbook fractal) pivots, and what they change downstream
ph_s, pl_s = pivots(h, "high", True), pivots(l, "low", True)
sh_s, last_h_s = publish(ph_s, h); sl_s, last_l_s = publish(pl_s, l)
up_s, down_s = lifecycle(sh_s, sl_s); ls_s = np.where(up_s == 1, 1, np.where(down_s == 1, -1, 0))
d_sh = (sh_s != sh)[ROWS]; d_sl = (sl_s != sl)[ROWS]; d_ls = (ls_s != lsweep)[ROWS]
add("swing_high", {"id": "swing-strict-fractal", "kind": "definition", "title": "Strict pivots (textbook fractal: higher than all 4 neighbours)",
                   "formula": "high[t] > every other high in t−2…t+2 (ties do not count); same 2-bar publication delay",
                   "stats": {"swing_high flag differs": pct(int(d_sh.sum())), "swing_low flag differs": pct(int(d_sl.sum())),
                             "liquidity_sweep (FM-090) differs": pct(int(d_ls.sum())),
                             "Swing highs (trunk → branch)": f"{int(sh[ROWS].sum()):,} → {int(sh_s[ROWS].sum()):,}",
                             "Swing lows (trunk → branch)": f"{int(sl[ROWS].sum()):,} → {int(sl_s[ROWS].sum()):,}"},
                   "decision_label": "swing flags or sweep events change", "decision_count": int(d_sh.sum() + d_sl.sum() + d_ls.sum()),
                   "open": bool(d_sh.sum() + d_sl.sum() + d_ls.sum() > 0),
                   "note": "Equal highs (a double top inside the 5-bar window) count as two pivots in the registered rule and as none in the strict one. Swings feed every structure and sweep feature."},
    sh_s[ROWS].astype(float), d_sh)
add("swing_low", {"id": "swing_low-strict", "kind": "definition", "title": "Strict pivots (follows the swing_high decision)",
                  "formula": "low[t] < every other low in t−2…t+2", "stats": {"Flag differs": pct(int(d_sl.sum()))},
                  "decision_label": "flag changes", "decision_count": int(d_sl.sum()), "open": bool(d_sl.sum() > 0), "follows": "swing-strict-fractal"},
    sl_s[ROWS].astype(float), d_sl)
add("liquidity_sweep", {"id": "sweep-on-strict-pivots", "kind": "definition", "title": "Sweeps on strict pivots (follows the swing decision)",
                        "formula": "same MKT-E01 lifecycle, levels from strict pivots", "stats": {"Sweep event differs": pct(int(d_ls.sum()))},
                        "decision_label": "sweep event changes", "decision_count": int(d_ls.sum()), "open": bool(d_ls.sum() > 0), "follows": "swing-strict-fractal"},
    ls_s[ROWS].astype(float), d_ls)

# Branch 2: HH/LL as swing-sequence states (textbook HH/LL), like FM-121/122
hh_seq = np.zeros(n, int); ll_seq = np.zeros(n, int); s_hh = s_ll = False; hk = lk = False
for i in range(1, n):
    if sh[i] == 1 and np.isfinite(last_h[i]) and np.isfinite(last_h[i - 1]): s_hh, hk = last_h[i] > last_h[i - 1], True
    if sl[i] == 1 and np.isfinite(last_l[i]) and np.isfinite(last_l[i - 1]): s_ll, lk = last_l[i] < last_l[i - 1], True
    hh_seq[i] = int(hk and s_hh); ll_seq[i] = int(lk and s_ll)
d_hh = (hh_seq != hh)[ROWS]; d_ll = (ll_seq != ll)[ROWS]
add("higher_high", {"id": "hh-ll-swing-sequence", "kind": "definition", "title": "Higher high / lower low as swing-to-swing states (textbook)",
                    "formula": "1 while the latest confirmed swing high is higher than the previous one (mirror for lower low); same rule as FM-121/122",
                    "stats": {"higher_high differs": pct(int(d_hh.sum())), "lower_low differs": pct(int(d_ll.sum())),
                              "higher_high = 1 (trunk → branch)": f"{int(hh[ROWS].sum()):,} → {int(hh_seq[ROWS].sum()):,} bars",
                              "lower_low = 1 (trunk → branch)": f"{int(ll[ROWS].sum()):,} → {int(ll_seq[ROWS].sum()):,} bars"},
                    "decision_label": "flag changes", "decision_count": int(d_hh.sum() + d_ll.sum()), "open": bool(d_hh.sum() + d_ll.sum() > 0),
                    "note": "The registered higher_high / lower_low are one-bar pierce events, while higher_low / lower_high (FM-121/122) are swing-to-swing states. Same naming family, two meanings. The repo's structure_sequence.py says so explicitly; this branch asks whether the names should match their textbook sense."},
    hh_seq[ROWS].astype(float), d_hh)
add("lower_low", {"id": "ll-swing-sequence", "kind": "definition", "title": "Lower low as a swing-to-swing state (follows the higher_high decision)",
                  "formula": "1 while the latest confirmed swing low is lower than the previous one", "stats": {"Flag differs": pct(int(d_ll.sum()))},
                  "decision_label": "flag changes", "decision_count": int(d_ll.sum()), "open": bool(d_ll.sum() > 0), "follows": "hh-ll-swing-sequence"},
    ll_seq[ROWS].astype(float), d_ll)

# Branch 3 (already decided): the legacy FM-058 sweep definition
leg = np.where((h > ref_h) & (c <= ref_h), 1, np.where((l < ref_l) & (c >= ref_l), -1, 0))
d_leg = (leg != lsweep)[ROWS]
add("liquidity_sweep", {"id": "sweep-legacy-fm058", "kind": "definition", "title": "Earlier definition FM-058 (latest swing only, never consumed, close ≤ level)",
                        "formula": "+1 if high > last swing high and close ≤ it; −1 mirrored", "open": False, "resolved": True,
                        "stats": {"Sweep event differs from the active FM-090": pct(int(d_leg.sum())),
                                  "Events (FM-058 → FM-090)": f"{int((leg[ROWS] != 0).sum()):,} → {int((lsweep[ROWS] != 0).sum()):,} bars"},
                        "decision_label": "decided earlier", "decision_count": int(d_leg.sum()),
                        "note": "Already decided: the e01 lifecycle definition was activated by user decision (F-112, F-117). Shown for audit only."},
    leg[ROWS].astype(float), d_leg)

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in TRUNK:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:19} trunk mism={f['trunk']['mismatch_count']:4} refs={len(f['refs']):2} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
