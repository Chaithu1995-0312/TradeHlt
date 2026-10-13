"""Trunk checks + divergence branches for trend, volatility, momentum and volume features on XAUUSD H4.

Trunk  = pipeline value vs an independent recompute of the REGISTERED formula (plain loops), all bars.
Branch = a different definition (textbook / TradingView), a precision/implementation difference, or a
         data caveat. A branch is OPEN only if it changes something a decision reads (a zone, flag,
         regime, sign or threshold class) on at least one bar; otherwise it is CLOSED with its numbers.
"""
import sys, os, re, json, logging
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, _HERE)
logging.disable(logging.WARNING)
import numpy as np
import pandas as pd
import yaml
from features.feature_pipeline import FeaturePipeline

ACTIVE = open(os.path.join(ROOT, "configs", "production", "ACTIVE_VERSION"), encoding="utf-8").read().strip()   # §4.0
CFG = json.load(open(os.path.join(ROOT, "configs", "production", f"{ACTIVE}.json"), encoding="utf-8"))["feature_pipeline"]
from h4_loader import load_h4_utc
raw, CLOCK_ID = load_h4_utc()          # timestamps in UTC via the declared clock (mt5_icmarkets_xau)
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
o, h, l, c, v = (raw[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume")); n = len(c)
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
TS = enr["timestamp"].astype(str).to_numpy(); NE = len(enr)

# ---------------- primitives (plain loops; no pandas ewm/rolling, no repo feature code) ----------------
def ema(x, span, seed="first"):
    a = 2 / (span + 1); out = np.full(n, np.nan)
    idx = np.where(~np.isnan(x))[0]; s = idx[0]
    if seed == "first":
        out[s] = x[s]; start = s + 1
    else:                                        # SMA of the first `span` valid values (TradingView ta.ema)
        out[s + span - 1] = x[s:s + span].mean(); start = s + span
    for i in range(start, n): out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out
def sma(x, w):
    out = np.full(n, np.nan)
    for i in range(w - 1, n):
        seg = x[i - w + 1:i + 1]
        if not np.isnan(seg).any(): out[i] = seg.sum() / w
    return out
def rma(x, w):
    out = np.full(n, np.nan); idx = np.where(~np.isnan(x))[0]; s0 = idx[w - 1]; out[s0] = x[idx[:w]].mean()
    for i in range(s0 + 1, n): out[i] = (out[i - 1] * (w - 1) + x[i]) / w
    return out
def zroll(x, w):
    out = np.full(n, np.nan)
    for i in range(w - 1, n):
        seg = x[i - w + 1:i + 1]
        if np.isnan(seg).any(): continue
        m = seg.mean(); sd = np.sqrt(((seg - m) ** 2).sum() / (w - 1)); out[i] = (x[i] - m) / (sd + 1e-9)
    return out
def rank_regime(a, N, lo, hi):
    out = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(a[i]): continue
        seg = a[max(0, i - N + 1):i + 1]; seg = seg[~np.isnan(seg)]
        pct = ((seg < a[i]).sum() + ((seg == a[i]).sum() + 1) / 2) / len(seg)
        out[i] = 0 if pct < lo else (1 if pct < hi else 2)
    return out
def roll_quantile(x, w, minp, q):
    out = np.full(n, np.nan)
    for i in range(n):
        seg = x[max(0, i - w + 1):i + 1]; seg = seg[~np.isnan(seg)]
        if len(seg) >= minp:
            s = np.sort(seg); pos = q * (len(s) - 1); lo_ = int(np.floor(pos)); hi_ = int(np.ceil(pos))
            out[i] = s[lo_] + (s[hi_] - s[lo_]) * (pos - lo_)
    return out

# ---------------- registered (trunk) recompute ----------------
tr = np.empty(n); tr[0] = h[0] - l[0]
for i in range(1, n): tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
atr_abs = sma(tr, CFG["atr_period"]); atr_rel = atr_abs / c
atr_rel32 = atr_rel.astype(np.float32).astype(float)
dclose = np.full(n, np.nan); dclose[1:] = c[1:] - c[:-1]
gain = np.where(np.isnan(dclose), np.nan, np.maximum(dclose, 0)); loss = np.where(np.isnan(dclose), np.nan, np.maximum(-dclose, 0))
P = CFG["rsi_period"]
def rsi_from(g, lo_): return np.clip(100 - 100 / (1 + g / (lo_ + 1e-9)), 0, 100)
ef, es = ema(c, CFG["ema_fast_span"]), ema(c, CFG["ema_slow_span"])
ma20 = sma(c, CFG["ma_periods"][0]); slope = np.full(n, np.nan); slope[1:] = ma20[1:] - ma20[:-1]
vma = sma(v, CFG["volume_ma_window"]); vratio = np.where(vma > 0, v / vma, 1.0)
vthr = roll_quantile(vratio, CFG["volume_spike_adaptive_window"], CFG["volume_spike_min_samples"], CFG["volume_spike_percentile"] / 100)
vthr = np.where(np.isnan(vthr), CFG["volume_spike_fixed_fallback"], vthr)
mf, ms_, msig = CFG["macd_fast"], CFG["macd_slow"], CFG["macd_signal"]
macd = ema(c, mf) - ema(c, ms_); sig = ema(macd, msig); hist = macd - sig

TRUNK = {
    # group, FM, name, recompute, plain description
    "ema_fast":         ("trend", "FM-043", ef, "EMA of the close, span 9, seeded with the first close."),
    "ema_slow":         ("trend", "FM-044", es, "EMA of the close, span 21, seeded with the first close."),
    "ema_spread":       ("trend", "FM-030", (ef - es) / (atr_rel32 * c), "Fast minus slow EMA, in ATRs (price-unit ATR)."),
    "trend_bias":       ("trend", "FM-054", np.sign(ef - es), "+1 when the fast EMA is above the slow, −1 below, 0 equal."),
    "trend_strength_z": ("trend", "FM-064", zroll(sma(slope, CFG["trend_strength_window"]), CFG["zscore_window"]),
                         "Average 20-bar-MA slope over 10 bars, z-scored over 50 bars."),
    "atr":              ("volatility", "FM-041", atr_rel, "Simple average of true range over 14 bars, divided by the close."),
    "volatility_ratio": ("volatility", "FM-024", (h - l) / (atr_rel32 * c), "This bar's range in ATRs."),
    "volatility_regime":("volatility", "FM-050", rank_regime(atr_abs, CFG["volatility_percentile_window"], CFG["volatility_tercile_low"], CFG["volatility_tercile_high"]),
                         "Tercile of the price-unit ATR's rank within the last 200 bars: 0 low, 1 middle, 2 high."),
    "momentum_score":   ("momentum", "FM-031", dclose / (atr_rel32 * c), "One-bar close change in ATRs."),
    "rsi_14":           ("momentum", "FM-042", rsi_from(sma(gain, P), sma(loss, P)), "RSI with simple averages of gains and losses over 14 closes."),
    "macd_line":        ("momentum", "FM-047", macd, "EMA12 − EMA26 of the close."),
    "macd_signal":      ("momentum", "FM-048", sig, "EMA9 of the MACD line."),
    "macd_hist_raw":    ("momentum", "FM-049", hist, "MACD line − signal."),
    "macd_hist_z":      ("momentum", "FM-053", zroll(hist, CFG["zscore_window"]), "MACD histogram z-scored over 50 bars."),
    "volume_ratio":     ("volume", "FM-062", vratio, "Bar volume ÷ its 20-bar simple average."),
    "volume_spike":     ("volume", "FM-063", (vratio > vthr).astype(float),
                         "1 when the volume ratio is above its own 75th percentile over the last 50 bars (needs 20), else 1.5× fallback."),
}

def agrees(mine, pipe, discrete):
    return (mine == pipe) if discrete else (np.abs(mine - pipe) <= np.maximum(1e-6 * np.abs(pipe), 1e-6))
DISCRETE = {"trend_bias", "volatility_regime", "volume_spike"}

# Example bar + 60-bar window (same as the published H4 page)
EX = NE // 2; WIN = np.arange(EX - 59, EX + 1)

# Registered formulas by FM-id, and which source files reference each column name
onto = yaml.safe_load(open(os.path.join(ROOT, "configs", "formulas", "market_ontology.yaml"), encoding="utf-8"))
REG = {}
def walk(x, key=None):
    if isinstance(x, dict):
        if isinstance(x.get("id"), str) and x["id"].startswith("FM-"):
            REG.setdefault(x["id"], {"name": key, "formula": x.get("formula")})
        for k, vv in x.items(): walk(vv, k)
    elif isinstance(x, list):
        for vv in x: walk(vv, key)
walk(onto)
SRC = []
for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f)
            try: SRC.append((os.path.relpath(p, os.path.join(ROOT, "src")).replace("\\", "/"), open(p, encoding="utf-8", errors="ignore").read()))
            except OSError: pass
def refs(name):
    pat = re.compile(r"[\"']" + re.escape(name) + r"[\"']")
    return sorted(p for p, t in SRC if pat.search(t) and not p.startswith("features/feature_pipeline.py"))

out = {"window": {"ts": TS[WIN].tolist(), "o": enr["open"].iloc[WIN].astype(float).tolist(), "h": enr["high"].iloc[WIN].astype(float).tolist(),
                  "l": enr["low"].iloc[WIN].astype(float).tolist(), "c": enr["close"].iloc[WIN].astype(float).tolist()},
       "rows": int(NE), "example_ts": str(TS[EX]), "features": {}}

for col, (group, fm, mine_full, plain) in TRUNK.items():
    mine = mine_full[ROWS]; pipe = enr[col].to_numpy(float)
    both = ~np.isnan(mine) & ~np.isnan(pipe)
    ok = np.zeros(NE, bool); ok[both] = agrees(mine[both], pipe[both], col in DISCRETE)
    bad = np.where(~ok)[0]
    out["features"][col] = {
        "group": group, "fm": fm, "plain": plain, "registered": (REG.get(fm) or {}).get("formula"),
        "trunk": {"bars": int(NE), "mismatch_count": int(len(bad)),
                  "mismatch_first": [{"ts": TS[i], "mine": None if np.isnan(mine[i]) else float(mine[i]), "pipe": None if np.isnan(pipe[i]) else float(pipe[i])} for i in bad[:25]],
                  "max_abs_diff": float(np.nanmax(np.abs(mine[both] - pipe[both]))) if both.any() else None},
        "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
        "refs": refs(col), "branches": [],
    }

def add_branch(col, bid, kind, title, formula, stats, decision_label, decision_count, alt_full=None, alt_is_rows=False, note=None,
               mask=None, follows=None):
    """decision_count > 0 opens the branch. alt_full: branch series (raw-row indexed unless alt_is_rows).
    mask: per-emitted-row booleans marking bars where the decision-relevant reading changes (shaded on the chart).
    follows: id of the branch whose decision this one shares."""
    b = {"id": bid, "kind": kind, "title": title, "formula": formula, "stats": stats,
         "decision_label": decision_label, "decision_count": int(decision_count), "open": bool(decision_count > 0), "note": note,
         "follows": follows}
    if alt_full is not None:
        series = alt_full if alt_is_rows else alt_full[ROWS]
        b["window"] = [float(x) for x in series[WIN]]
    if mask is not None:
        b["window_mask"] = [bool(x) for x in np.asarray(mask)[WIN]]
    out["features"][col]["branches"].append(b)

pct = lambda k: f"{k:,} of {NE:,} bars ({k / NE * 100:.0f}%)"

# --- trend: EMA seed (definition) ---
for col, span in (("ema_fast", CFG["ema_fast_span"]), ("ema_slow", CFG["ema_slow_span"])):
    alt = ema(c, span, seed="sma")[ROWS]; d = np.abs(alt - enr[col].to_numpy(float))
    add_branch(col, f"{col}-sma-seed", "definition", "Seed with the SMA of the first bars (TradingView ta.ema)",
               f"first value = mean of the first {span} closes, then the same EMA",
               {"Largest difference after warm-up": f"${np.nanmax(d):.4f}"}, "trend_bias flips", 0, alt, True,
               "Differences fade within the 78-bar warm-up the pipeline already drops.")
bias_alt = np.sign(ema(c, CFG["ema_fast_span"], "sma") - ema(c, CFG["ema_slow_span"], "sma"))[ROWS]
flips = int((bias_alt != enr["trend_bias"].to_numpy(float)).sum())
add_branch("trend_bias", "trend_bias-sma-seed", "definition", "EMAs seeded with the SMA (TradingView)", "sign(ema_fast − ema_slow) with SMA-seeded EMAs",
           {"Bars where the flag differs": pct(flips)}, "flag flips", flips)

# --- trend: ema_spread precision (implementation) ---
sp64 = ((ef - es) / (atr_rel32 * c))[ROWS]; sp32 = enr["ema_spread"].to_numpy(float)
sign_flip = int((np.sign(sp64) != np.sign(sp32)).sum())
cls = lambda s, t: np.abs(s) > t
c15 = int((cls(sp64, 0.15) != cls(sp32, 0.15)).sum()); c30 = int((cls(sp64, 0.3) != cls(sp32, 0.3)).sum())
rel = np.abs(sp64 - sp32) / np.maximum(np.abs(sp64), 1e-12)
add_branch("ema_spread", "ema_spread-float64", "implementation", "Subtract the EMAs before rounding to float32",
           "(ema_fast − ema_slow) in float64, then ÷ (atr × close)",
           {"Largest difference": f"{np.nanmax(np.abs(sp64 - sp32)):.1e} ATR", "Largest relative difference": f"{np.nanmax(rel) * 100:.1f}% (near zero)",
            "Sign differs": pct(sign_flip), "|spread| > 0.15 class differs": pct(c15), "|spread| > 0.3 class differs": pct(c30)},
           "sign or 0.15/0.3 class changes", sign_flip + c15 + c30, sp64, True,
           "The pipeline stores ema_fast and ema_slow as float32 and then subtracts them, losing digits when they are close (known: F-053). 0.15 and 0.3 are the dual_engine regime cut-offs (F-061).")

# --- volatility: ATR Wilder (definition) ---
atr_w = rma(tr, CFG["atr_period"])
reg_w = rank_regime(atr_w, CFG["volatility_percentile_window"], CFG["volatility_tercile_low"], CFG["volatility_tercile_high"])[ROWS]
reg_s = enr["volatility_regime"].to_numpy(float)
k = CFG["candle_patterns"]["size_gate_atr_k"]; rng = (h - l)[ROWS]
gate_s = rng >= k * atr_abs[ROWS]; gate_w = rng >= k * atr_w[ROWS]
vr_s, vr_w = (rng / atr_abs[ROWS]), (rng / atr_w[ROWS])
d_atr = np.abs(atr_w - atr_abs)[ROWS] / atr_abs[ROWS]
reg_flip = int((reg_w != reg_s).sum()); gate_flip = int((gate_s != gate_w).sum()); vr_flip = int(((vr_s > 1) != (vr_w > 1)).sum())
add_branch("atr", "atr-wilder", "definition", "Wilder smoothing (TradingView ta.atr)", "ATR = (prev × 13 + true range) / 14, seeded with the first 14-bar SMA",
           {"Average difference": f"{np.nanmean(d_atr) * 100:.1f}%", "Largest difference": f"{np.nanmax(d_atr) * 100:.0f}%",
            "volatility_regime differs": pct(reg_flip), "Candle-pattern size gate (range ≥ 0.5 × ATR) differs": pct(gate_flip),
            "volatility_ratio above/below 1 differs": pct(vr_flip)},
           "regime, size-gate or ratio class changes", reg_flip + gate_flip + vr_flip, atr_w / c,
           mask=(reg_w != reg_s) | (gate_s != gate_w) | ((vr_s > 1) != (vr_w > 1)))
add_branch("volatility_regime", "volatility_regime-wilder", "definition", "Rank Wilder ATR instead (follows the ATR branch)",
           "same tercile rank, on Wilder ATR", {"Regime differs": pct(reg_flip)}, "regime changes", reg_flip, reg_w, True,
           "Decided together with the ATR branch.", mask=(reg_w != reg_s), follows="atr-wilder")
add_branch("volatility_ratio", "volatility_ratio-wilder", "definition", "Divide by Wilder ATR instead (follows the ATR branch)",
           "range / Wilder ATR", {"Above/below 1 differs": pct(vr_flip)}, "ratio class changes", vr_flip, vr_w, True,
           "Decided together with the ATR branch.", mask=((vr_s > 1) != (vr_w > 1)), follows="atr-wilder")
mom_w = (dclose[ROWS] / atr_w[ROWS]); mom_s = enr["momentum_score"].to_numpy(float)
m_sign = int((np.sign(mom_w) != np.sign(mom_s)).sum()); m1 = int(((np.abs(mom_w) > 1) != (np.abs(mom_s) > 1)).sum())
add_branch("momentum_score", "momentum_score-wilder", "definition", "Divide by Wilder ATR instead (follows the ATR branch)",
           "close change / Wilder ATR", {"Sign differs": pct(m_sign), "|score| > 1 class differs": pct(m1)},
           "|score| > 1 class changes", m1, mom_w, True, "The sign never changes; only the size does. Decided together with the ATR branch.",
           mask=((np.abs(mom_w) > 1) != (np.abs(mom_s) > 1)), follows="atr-wilder")

# --- momentum: RSI Wilder, MACD seed ---
rsi_w = rsi_from(rma(gain, P), rma(loss, P))[ROWS]; rsi_s = enr["rsi_14"].to_numpy(float)
zone = lambda r: np.where(r >= 70, 2, np.where(r <= 30, 0, 1))
zflip = int((zone(rsi_w) != zone(rsi_s)).sum())
add_branch("rsi_14", "rsi_14-wilder", "definition", "Wilder smoothing (TradingView ta.rsi)", "same RS ratio; gains and losses smoothed as (prev × 13 + x) / 14",
           {"30/70 zone differs": pct(zflip), "RSI ≥ 70": f"{int((rsi_s >= 70).sum()):,} → {int((rsi_w >= 70).sum()):,} bars",
            "RSI ≤ 30": f"{int((rsi_s <= 30).sum()):,} → {int((rsi_w <= 30).sum()):,} bars",
            "Average distance": f"{np.nanmean(np.abs(rsi_w - rsi_s)):.1f} points"}, "30/70 zone changes", zflip, rsi_w, True,
           mask=(zone(rsi_w) != zone(rsi_s)))
macd_a = ema(c, mf, "sma") - ema(c, ms_, "sma")
sig_a = np.full(n, np.nan); first = np.where(~np.isnan(macd_a))[0][0]
sig_tmp = ema(np.where(np.isnan(macd_a), np.nan, macd_a), msig, "sma"); sig_a = sig_tmp
hist_a = (macd_a - sig_a)[ROWS]
h_flip = int((np.sign(hist_a) != np.sign(enr["macd_hist_raw"].to_numpy(float))).sum())
add_branch("macd_hist_raw", "macd-sma-seed", "definition", "EMAs seeded with the SMA (TradingView ta.macd)", "same MACD, SMA-seeded EMAs",
           {"Histogram sign differs": pct(h_flip)}, "histogram sign flips", h_flip, hist_a, True)

# --- volume: spike definition + data caveat ---
spk = enr["volume_spike"].to_numpy(float); vr_p = enr["volume_ratio"].to_numpy(float)
for mult in (1.5, 2.0):
    alt = (vr_p > mult).astype(float); diff = int((alt != spk).sum())
    add_branch("volume_spike", f"volume_spike-fixed-{str(mult).replace('.', '_')}", "definition", f"Fixed {mult}× average volume",
               f"1 when volume_ratio > {mult}",
               {"Fires on (trunk)": f"{int(spk.sum()):,} bars ({spk.mean() * 100:.0f}%)", f"Fires on ({mult}×)": f"{int(alt.sum()):,} bars ({alt.mean() * 100:.0f}%)",
                "Flag differs": pct(diff)}, "flag changes", diff, alt, True,
               "The trunk flags the top quarter of recent ratios, so it fires on about 25% of bars by design.", mask=(alt != spk))
add_branch("volume_ratio", "volume-tick-data", "data", "Volume is MT5 tick volume, not traded volume",
           "count of price updates per bar (F-099: tick volume, ~0.6% from independently counted ticks)",
           {"Source": "data/mt5/XAUUSD_H4.csv volume column"}, "data caveat", 1, None, False,
           "A data branch: no formula change can fix it; it limits what volume features can mean.")

out["page_data_branch"] = {"id": "h4-clock", "kind": "data", "title": "H4 file clock (resolved: declared mt5_icmarkets_xau)",
                           "resolved": True,
                           "stats": {"Before": "timezone empty, not reviewed (detector: looks UTC, low confidence); the report read server time as UTC",
                                     "Evidence": "H4 OHLC equals 4-hour candles built from the reviewed M15 file on 2,561 of 2,561 complete bars with no time shift",
                                     "Fix (2026-10-14)": "declared on clock mt5_icmarkets_xau via scripts/governance/review_ohlcv_clocks.py; this report now converts the file's times to UTC through that clock",
                                     "Dataset registry": "still listed as a forensic path, not the canonical corpus"},
                           "options": "Every bar time on this page is now UTC. Price and indicator features did not change; session and hour did."}
out["clock_id"] = CLOCK_ID
out["doc_gaps"] = [{"where": "src/features/feature_pipeline.py:1259", "text": "comment says volume_spike has no FM id; it is FM-063"}]
out["active_version"] = ACTIVE
json.dump(out, open(os.path.join(ROOT, "results", "divergence_h4.json"), "w"), indent=1, default=float)
for col, f in out["features"].items():
    print(f"{f['fm']:7} {col:18} trunk mism={f['trunk']['mismatch_count']:4}  refs={len(f['refs']):2}  branches=" +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
