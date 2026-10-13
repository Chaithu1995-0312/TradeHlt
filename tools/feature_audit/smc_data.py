"""SMC zones group on XAUUSD H4 (UTC via declared clock): FM-075..083 and FM-097..102.

Independent re-derivation of the registered features.smc rules (does not import features.smc):
order block, FVG, breaker, mitigation block, PDH/PDL, EQH/EQL, change of character. Same per-bar
trailing window (feature_pipeline.smc_max_window) as the pipeline. Trunk + branches -> divergence_h4.json.
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
EQ_TOL, EQ_MAX = 0.1, 8          # features/smc/levels.py defaults (code literals, not config)
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
o, h, l, c = (raw[k].to_numpy(float) for k in ("open", "high", "low", "close")); n = len(c)
ts = pd.to_datetime(raw["timestamp"])
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
NE = len(enr); TSU = enr["timestamp"].astype(str).to_numpy()
OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
WIN = pd.Series(np.arange(NE), index=pd.to_datetime(enr["timestamp"])).reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

atr_abs = AP.sma(AP.true_range(h, l, c), CFG["atr_period"])
atr_i = (atr_abs / c).astype(np.float32).astype(float) * c          # pipeline: atr (float32) * close
atr_i = np.where(np.isnan(atr_i), 0.0, atr_i)

# Global pivots (centered over [j-k, j+k], ties count) and "latest pivot at or before x"
ph = AP.pivots(h, "high", K); pl = AP.pivots(l, "low", K)
def last_idx(piv):
    out = np.full(n, -1); cur = -1
    for x in range(n):
        if piv[x]: cur = x
        out[x] = cur
    return out
LPH, LPL = last_idx(ph), last_idx(pl)

def tanh_dist(close, edge, atr, sign):
    return 0.0 if atr <= 0 else math.tanh(sign * (close - edge) / atr)

def overlaps(lo_z, hi_z, a, b):
    """Any bar in [a, b] (inclusive) trading into [lo_z, hi_z]."""
    if a > b: return False
    return bool(np.any((l[a:b + 1] <= hi_z) & (h[a:b + 1] >= lo_z)))

def break_events(s, i, first_only=False):
    ev = []
    for p in range(s + 2 * K + 1, i + 1):
        x = p - 1 - K
        hp, lp = LPH[x], LPL[x]
        if hp >= s + K and c[p] > h[hp]: ev.append((p, True))
        elif lp >= s + K and c[p] < l[lp]: ev.append((p, False))
    if first_only:                      # keep only the first bar of each run of same-direction breaks
        keep, prev = [], None
        for p, b in ev:
            if not (prev and prev[0] == p - 1 and prev[1] == b): keep.append((p, b))
            prev = (p, b)
        ev = keep
    return ev

def origin(s, p, bullish):
    for j in range(p - 1, s - 1, -1):
        if bullish and c[j] < o[j]: return j
        if (not bullish) and c[j] > o[j]: return j
    return None

def order_block(s, i, ev):
    for p, bull in reversed(ev):
        j = origin(s, p, bull)
        if j is None: continue
        if not overlaps(l[j], h[j], p + 1, i): return (l[j], h[j], bull)
    return None

def breaker(s, i, ev):
    for p, bull in reversed(ev):
        j = origin(s, p, bull)
        if j is None: continue
        q = None
        for t in range(j + 1, i + 1):
            if bull and c[t] < l[j]: q = t; break
            if (not bull) and c[t] > h[j]: q = t; break
        if q is None: continue
        if not overlaps(l[j], h[j], q + 1, i): return (l[j], h[j], not bull)
    return None

def mitigation(s, i, ev):
    for p, bull in reversed(ev):
        j = origin(s, p, bull)
        if j is None: continue
        if not overlaps(l[j], h[j], p + 1, i): continue
        bh, bl = max(o[j], c[j]), min(o[j], c[j])
        if bh <= bl: continue
        if not overlaps(bl, bh, p + 1, i): return (bl, bh, bull)
    return None

def fvg(s, i, full_fill=False):
    for m in range(i - 1, s, -1):                    # most recent middle candle first
        if h[m - 1] < l[m + 1]: lo_z, hi_z, bull = h[m - 1], l[m + 1], True
        elif l[m - 1] > h[m + 1]: lo_z, hi_z, bull = h[m + 1], l[m - 1], False
        else: continue
        a, b = m + 2, i
        if full_fill:
            filled = a <= b and (np.any(l[a:b + 1] <= lo_z) if bull else np.any(h[a:b + 1] >= hi_z))
        else:
            filled = overlaps(lo_z, hi_z, a, b)
        if not filled: return (lo_z, hi_z, bull)
    return None

def eq_cluster(s, i, kind):
    piv, x = (ph, h) if kind == "high" else (pl, l)
    sw = []
    for j in range(i - K, s + K - 1, -1):
        if piv[j]: sw.append(x[j])
        if len(sw) >= EQ_MAX: break
    a = atr_i[i]
    if a <= 0 or len(sw) < 2: return None
    band = EQ_TOL * a
    for u, pu in enumerate(sw):
        if any(abs(pu - q) <= band for q in sw[u + 1:]): return pu
    return None

def zone_dist(z, i):
    if z is None: return 0.0
    lo_z, hi_z, bull = z
    return tanh_dist(c[i], hi_z, atr_i[i], 1) if bull else tanh_dist(c[i], lo_z, atr_i[i], -1)

# Previous closed D1 (market day = 17:00 New York, fx_metals calendar)
ny = ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
# Wall-clock arithmetic: drop the zone before subtracting, so a DST switch cannot move the boundary
# (subtracting 17 elapsed hours from an aware time crosses the 02:00 change and lands a day early).
day = (ny.dt.tz_localize(None) - pd.Timedelta(hours=17)).dt.date.to_numpy()
pdh = np.full(n, np.nan); pdl = np.full(n, np.nan); cur_day = None; d_hi = d_lo = None; prev = (np.nan, np.nan)
for i in range(n):
    if day[i] != cur_day:
        if cur_day is not None: prev = (d_hi, d_lo)
        cur_day, d_hi, d_lo = day[i], h[i], l[i]
    else:
        d_hi, d_lo = max(d_hi, h[i]), min(d_lo, l[i])
    pdh[i], pdl[i] = prev

def run_all(window, first_only=False, full_fill=False, only=None):
    out = {k_: np.zeros(n) for k_ in ("ob_d", "ob_p", "fvg_d", "fvg_p", "brk_d", "brk_p", "mit_d", "mit_p", "eqh_d", "eqh_p", "eql_d", "eql_p")}
    for i in range(n):
        s = max(0, i - window + 1)
        if only is None or "ob" in only or "brk" in only or "mit" in only:
            ev = break_events(s, i, first_only)
        if only is None or "ob" in only:
            z = order_block(s, i, ev); out["ob_p"][i] = z is not None; out["ob_d"][i] = zone_dist(z, i)
        if only is None or "fvg" in only:
            z = fvg(s, i, full_fill); out["fvg_p"][i] = z is not None; out["fvg_d"][i] = zone_dist(z, i)
        if only is None or "brk" in only:
            z = breaker(s, i, ev); out["brk_p"][i] = z is not None; out["brk_d"][i] = zone_dist(z, i)
        if only is None or "mit" in only:
            z = mitigation(s, i, ev); out["mit_p"][i] = z is not None; out["mit_d"][i] = zone_dist(z, i)
        if only is None or "eq" in only:
            eh, el = eq_cluster(s, i, "high"), eq_cluster(s, i, "low")
            out["eqh_p"][i] = eh is not None; out["eql_p"][i] = el is not None
            out["eqh_d"][i] = 0.0 if eh is None else tanh_dist(c[i], eh, atr_i[i], -1)
            out["eql_d"][i] = 0.0 if el is None else tanh_dist(c[i], el, atr_i[i], 1)
    return out

T = run_all(W)
pdh_d = np.array([0.0 if np.isnan(pdh[i]) else tanh_dist(c[i], pdh[i], atr_i[i], -1) for i in range(n)])
pdl_d = np.array([0.0 if np.isnan(pdl[i]) else tanh_dist(c[i], pdl[i], atr_i[i], 1) for i in range(n)])
# CHoCH from independently recomputed BOS and trend_bias
sh, last_h = AP.publish(ph, h, K); sl, last_l = AP.publish(pl, l, K)
ref_h = np.r_[np.nan, last_h[:-1]]; ref_l = np.r_[np.nan, last_l[:-1]]
with np.errstate(invalid="ignore"):
    bos = np.where(c > ref_h, 1, np.where(c < ref_l, -1, 0))
tb = np.sign(AP.ema_first(c, CFG["ema_fast_span"]) - AP.ema_first(c, CFG["ema_slow_span"]))
choch = np.where((bos != 0) & (tb != 0) & (np.sign(bos) != tb), bos, 0)

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
WIN_TXT = f"the last {W} bars"
TRUNK = {
    "order_block_distance": ("FM-075", T["ob_d"], False, f"Signed distance (tanh of ATRs) from the close to the latest unmitigated order block's near edge, within {WIN_TXT}. 0 if none."),
    "fvg_distance": ("FM-076", T["fvg_d"], False, f"Signed distance to the latest unfilled fair value gap's near edge, within {WIN_TXT}. 0 if none."),
    "breaker_distance": ("FM-077", T["brk_d"], False, "Signed distance to the latest un-retested breaker (an order block closed through, polarity flipped). 0 if none."),
    "mitigation_block_distance": ("FM-078", T["mit_d"], False, "Signed distance to the body of the latest order block whose outer range was touched but whose body was not. 0 if none."),
    "pdh_distance": ("FM-079", pdh_d, False, "Signed distance to the previous trading day's high (day starts 17:00 New York). Positive = below it."),
    "pdl_distance": ("FM-080", pdl_d, False, "Signed distance to the previous trading day's low. Positive = above it."),
    "eqh_distance": ("FM-081", T["eqh_d"], False, f"Signed distance to the latest equal-highs cluster (2+ of the last {EQ_MAX} swing highs within {EQ_TOL:g} ATR). Positive = below it."),
    "eql_distance": ("FM-082", T["eql_d"], False, "Signed distance to the latest equal-lows cluster. Positive = above it."),
    "change_of_character": ("FM-083", choch.astype(float), True, "A break of structure against the EMA trend (trend_bias): +1 / −1 in the break's direction, else 0."),
    "order_block_present": ("FM-097", T["ob_p"], True, "1 when an unmitigated order block exists."),
    "fvg_present": ("FM-098", T["fvg_p"], True, "1 when an unfilled fair value gap exists."),
    "breaker_present": ("FM-099", T["brk_p"], True, "1 when an un-retested breaker exists."),
    "mitigation_block_present": ("FM-100", T["mit_p"], True, "1 when a live mitigation block exists."),
    "eqh_present": ("FM-101", T["eqh_p"], True, "1 when an equal-highs cluster exists."),
    "eql_present": ("FM-102", T["eql_p"], True, "1 when an equal-lows cluster exists."),
}
for col, (fm, mine_full, discrete, plain) in TRUNK.items():
    mine = mine_full[ROWS].astype(float); pipe = enr[col].to_numpy(float)
    ok = (mine == pipe) if discrete else (np.abs(mine - pipe) <= np.maximum(1e-6 * np.abs(pipe), 1e-6))
    bad = np.where(~ok)[0]
    D["features"][col] = {"group": "smc", "fm": fm, "plain": plain, "registered": REG.get(fm),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(np.nanmax(np.abs(mine - pipe))),
                                    "mismatch_first": [{"ts": TSU[r], "mine": float(mine[r]), "pipe": float(pipe[r])} for r in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": []}

def add(col, b, alt_rows=None, mask_rows=None):
    b.setdefault("follows", None); b.setdefault("note", None)
    if alt_rows is not None: b["window"] = [float(x) for x in alt_rows[WIN]]
    if mask_rows is not None: b["window_mask"] = [bool(x) for x in mask_rows[WIN]]
    D["features"][col]["branches"].append(b)

# B1: CHoCH against swing structure instead of the EMA trend
hl, lh, _sw = [np.zeros(n, int) for _ in range(3)]
s_hh = s_hl = s_lh = s_ll = False; hk = lk = False
trend_struct = np.zeros(n, int)
for i in range(1, n):
    if sl[i] == 1 and np.isfinite(last_l[i]) and np.isfinite(last_l[i - 1]): s_hl, s_ll, lk = last_l[i] > last_l[i - 1], last_l[i] < last_l[i - 1], True
    if sh[i] == 1 and np.isfinite(last_h[i]) and np.isfinite(last_h[i - 1]): s_hh, s_lh, hk = last_h[i] > last_h[i - 1], last_h[i] < last_h[i - 1], True
    if hk and lk:
        trend_struct[i] = 1 if (s_hh and s_hl) else (-1 if (s_lh and s_ll) else 0)
choch_s = np.where((bos != 0) & (trend_struct != 0) & (np.sign(bos) != trend_struct), bos, 0)
d_ch = (choch_s != choch)[ROWS]
add("change_of_character", {"id": "choch-swing-structure", "kind": "definition", "title": "Change of character against swing structure (textbook)",
    "formula": "break of structure against the swing trend: bullish = higher high + higher low, bearish = lower high + lower low; neither = no trend",
    "stats": {"CHoCH differs": pct(int(d_ch.sum())), "CHoCH bars (trunk → branch)": f"{int((choch[ROWS] != 0).sum()):,} → {int((choch_s[ROWS] != 0).sum()):,}"},
    "decision_label": "CHoCH changes", "decision_count": int(d_ch.sum()), "open": bool(d_ch.sum() > 0),
    "note": "The registered CHoCH uses trend_bias, which is the 9/21 EMA cross. In SMC/ICT usage the trend that a change of character breaks is the swing structure."},
    choch_s[ROWS].astype(float), d_ch)

# B2: order block from the FIRST break bar of each run only
F = run_all(W, first_only=True, only={"ob"})
d_ob = (F["ob_p"] != T["ob_p"])[ROWS] | (np.sign(F["ob_d"]) != np.sign(T["ob_d"]))[ROWS]
add("order_block_distance", {"id": "ob-first-break", "kind": "definition", "title": "Order block = last opposite candle before the FIRST break (not every later close beyond the swing)",
    "formula": "only the first bar of each run of same-direction breaks creates an order block",
    "stats": {"Presence or side (sign) differs": pct(int(d_ob.sum())),
              "Break bars counted (trunk, whole series)": f"{sum(len(break_events(0, n - 1)) for _ in [0]):,}",
              "First-break bars (branch, whole series)": f"{len(break_events(0, n - 1, True)):,}"},
    "decision_label": "order block presence or side changes", "decision_count": int(d_ob.sum()), "open": bool(d_ob.sum() > 0),
    "note": "Every bar that closes beyond the last swing counts as a break in the registered code, so the latest order block is often a small pullback candle inside an ongoing move rather than the candle before the move began."},
    F["ob_d"][ROWS], d_ob)
add("order_block_present", {"id": "ob_present-first-break", "kind": "definition", "title": "First-break order blocks (follows the order-block decision)",
    "formula": "same as the distance branch", "stats": {"Presence differs": pct(int((F["ob_p"] != T["ob_p"])[ROWS].sum()))},
    "decision_label": "presence changes", "decision_count": int((F["ob_p"] != T["ob_p"])[ROWS].sum()),
    "open": bool((F["ob_p"] != T["ob_p"])[ROWS].sum() > 0), "follows": "ob-first-break"},
    F["ob_p"][ROWS], (F["ob_p"] != T["ob_p"])[ROWS])

# B3: FVG filled only when price trades through the whole gap
G = run_all(W, full_fill=True, only={"fvg"})
d_fvg = (G["fvg_p"] != T["fvg_p"])[ROWS] | (np.sign(G["fvg_d"]) != np.sign(T["fvg_d"]))[ROWS]
add("fvg_distance", {"id": "fvg-full-fill", "kind": "definition", "title": "A gap counts as filled only when price trades through all of it",
    "formula": "bullish gap filled when a later low reaches the gap's bottom; bearish when a later high reaches its top",
    "stats": {"Presence or side differs": pct(int(d_fvg.sum())),
              "FVG present (trunk → branch)": f"{int(T['fvg_p'][ROWS].sum()):,} → {int(G['fvg_p'][ROWS].sum()):,} bars"},
    "decision_label": "FVG presence or side changes", "decision_count": int(d_fvg.sum()), "open": bool(d_fvg.sum() > 0),
    "note": "The registered rule ends a gap on the first touch (the same overlap test used for order-block mitigation). Many traders call a touch 'mitigated' and only a full trade-through 'filled'."},
    G["fvg_d"][ROWS], d_fvg)
add("fvg_present", {"id": "fvg_present-full-fill", "kind": "definition", "title": "Full-fill gaps (follows the FVG decision)", "formula": "same as the distance branch",
    "stats": {"Presence differs": pct(int((G["fvg_p"] != T["fvg_p"])[ROWS].sum()))}, "decision_label": "presence changes",
    "decision_count": int((G["fvg_p"] != T["fvg_p"])[ROWS].sum()), "open": bool((G["fvg_p"] != T["fvg_p"])[ROWS].sum() > 0), "follows": "fvg-full-fill"},
    G["fvg_p"][ROWS], (G["fvg_p"] != T["fvg_p"])[ROWS])

# B4: the trailing window (smc_max_window) changes which zones exist
W2 = 300
L2 = run_all(W2)
parts = {"order block": ("ob_p",), "FVG": ("fvg_p",), "breaker": ("brk_p",), "mitigation block": ("mit_p",), "equal highs/lows": ("eqh_p", "eql_p")}
stats = {}
any_diff = np.zeros(NE, bool)
for name, keys in parts.items():
    dd = np.zeros(NE, bool)
    for k_ in keys: dd |= (L2[k_] != T[k_])[ROWS]
    any_diff |= dd; stats[f"{name} presence differs"] = pct(int(dd.sum()))
add("order_block_present", {"id": "smc-window-300", "kind": "implementation", "title": f"Look back {W2} bars instead of {W} (smc_max_window)",
    "formula": f"same finders over the last {W2} bars", "stats": stats,
    "decision_label": "zone presence changes", "decision_count": int(any_diff.sum()), "open": bool(any_diff.sum() > 0),
    "note": f"The pipeline config describes smc_max_window as a performance bound (\"smaller values simply forget older, likely-stale zones sooner\"), but it decides which zones exist. On H4, {W} bars is about 17 trading days."},
    L2["ob_p"][ROWS], any_diff)

# B5 (implementation): a frame without an instrument tag silently gets the UTC calendar
untagged = raw.copy(); untagged.attrs = {}
enr_u, _ = FeaturePipeline(untagged, timeframe="H4").run(); enr_u = enr_u.reset_index(drop=True)
pdh_u, pdl_u = enr_u["pdh_distance"].to_numpy(float), enr_u["pdl_distance"].to_numpy(float)
pdh_t, pdl_t = enr["pdh_distance"].to_numpy(float), enr["pdl_distance"].to_numpy(float)
d_pdh = np.abs(pdh_u - pdh_t) > 1e-6; d_pdl = np.abs(pdl_u - pdl_t) > 1e-6
s_pdh = np.sign(pdh_u) != np.sign(pdh_t); s_pdl = np.sign(pdl_u) != np.sign(pdl_t)
add("pdh_distance", {"id": "calendar-untagged-utc", "kind": "implementation", "title": "Frames without an instrument tag silently use the UTC day",
    "formula": "FeaturePipeline(df) with no df.attrs['instrument'] -> UTC calendar (day starts 00:00 UTC) instead of fx_metals (17:00 New York)",
    "stats": {"pdh_distance differs": pct(int(d_pdh.sum())), "pdl_distance differs": pct(int(d_pdl.sum())),
              "Side of PDH/PDL (sign) flips": pct(int((s_pdh | s_pdl).sum())),
              "Who is affected": "any caller that builds the frame itself (pd.read_csv); corpus_store.frame() sets the tag"},
    "decision_label": "PDH/PDL side changes", "decision_count": int((s_pdh | s_pdl).sum()), "open": bool((s_pdh | s_pdl).sum() > 0),
    "note": "Found while auditing: this report's own loader read the CSV directly and got UTC days until the tag was added. feature_pipeline.py:475-478 falls back without a warning, the same silent-default class as F-018/F-058."},
    pdh_u, (s_pdh | s_pdl))

out_gaps = D.setdefault("doc_gaps", [])
for g in [{"where": "src/features/smc/_geometry.py:50", "text": "docstring says a swing is a 'strict local extreme'; the code at :70 uses equality, so tied highs/lows both count"},
          {"where": "src/features/smc/order_block.py:105 (and fvg/breaker/mitigation distance docstrings)", "text": "docstrings say distance to the 'nearest' active zone; the finders return the most recent one"},
          {"where": "src/features/smc/levels.py:56", "text": "equal-highs/lows tolerance 0.1 ATR and max 8 swings are code literals, not config (CLAUDE.md §6.5)"}]:
    if g not in out_gaps: out_gaps.append(g)

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in TRUNK:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:26} trunk mism={f['trunk']['mismatch_count']:4} maxdiff={f['trunk']['max_abs_diff']:.2e} refs={len(f['refs']):2} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
