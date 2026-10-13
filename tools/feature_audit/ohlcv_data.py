"""Raw OHLCV group on XAUUSD H4 (UTC via declared clock): FM-085..089.

Trunk: the pipeline's open/high/low/close/volume against the file's own values (registered formula =
identity). Data checks: candle consistency, timestamps, H4 vs 4h buckets of the M15 file (same
server clock, read-only), and the short daily-open bar. Merges into results/divergence_h4.json.
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
from h4_loader import load_h4_utc

ACTIVE = open(os.path.join(ROOT, "configs", "production", "ACTIVE_VERSION"), encoding="utf-8").read().strip()   # §4.0
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
n = len(raw); NE = len(enr); TSU = enr["timestamp"].astype(str).to_numpy()
ROWS = pd.Series(np.arange(n), index=raw["timestamp"]).reindex(pd.to_datetime(enr["timestamp"])).to_numpy().astype(int)
OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8"))
WIN = pd.Series(np.arange(NE), index=pd.to_datetime(enr["timestamp"])).reindex(pd.to_datetime(pd.Series(D["window"]["ts"]))).to_numpy().astype(int)

onto = yaml.safe_load(open(os.path.join(ROOT, "configs", "formulas", "market_ontology.yaml"), encoding="utf-8"))
REG = {k: v.get("formula") for k, v in onto["source_inputs"].items()}
SRC = []
for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f); SRC.append((os.path.relpath(p, os.path.join(ROOT, "src")).replace("\\", "/"), open(p, encoding="utf-8", errors="ignore").read()))
def refs(name):
    pat = re.compile(r"[\"']" + re.escape(name) + r"[\"']")
    return sorted(p for p, t in SRC if pat.search(t) and not p.startswith("features/feature_pipeline.py"))
pct = lambda k_, d=NE: f"{k_:,} of {d:,} bars ({k_ / d * 100:.1f}%)"

# ---- trunk: identity ----
COLS = {"open": ("FM-085", "The bar's first traded price, as delivered by MT5."),
        "high": ("FM-086", "The bar's highest price."),
        "low": ("FM-087", "The bar's lowest price."),
        "close": ("FM-088", "The bar's last price. Almost every other feature is anchored to it."),
        "volume": ("FM-089", "MT5 tick volume: the number of price updates in the bar, not ounces or lots traded.")}
for col, (fm, plain) in COLS.items():
    mine = raw[col].to_numpy(float)[ROWS]; pipe = enr[col].to_numpy(float)
    diff = np.abs(mine - pipe); bad = np.where(diff > 0)[0]
    D["features"][col] = {"group": "ohlcv", "fm": fm, "plain": plain, "registered": REG.get(col),
                          "trunk": {"bars": NE, "mismatch_count": int(len(bad)), "max_abs_diff": float(diff.max()),
                                    "mismatch_first": [{"ts": TSU[r], "mine": float(mine[r]), "pipe": float(pipe[r])} for r in bad[:25]]},
                          "window_pipe": [float(x) for x in pipe[WIN]], "window_mine": [float(x) for x in mine[WIN]],
                          "refs": refs(col), "branches": [], "dtype": str(enr[col].dtype)}

def add(col, b):
    b.setdefault("follows", None); b.setdefault("note", None); D["features"][col]["branches"].append(b)

o, h, l, c, v = (raw[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
# ---- data check 1: candle consistency + timestamps (whole file, before warmup drop) ----
bad_hi = int((h < np.maximum(o, c)).sum()); bad_lo = int((l > np.minimum(o, c)).sum())
flat = int((h == l).sum()); zero_v = int((v <= 0).sum())
ts_srv = pd.to_datetime(pd.read_csv(os.path.join(ROOT, "data", "mt5", "XAUUSD_H4.csv"), usecols=["timestamp"])["timestamp"])
dup = int(ts_srv.duplicated().sum()); nonmono = int((ts_srv.diff().dt.total_seconds() <= 0).sum())
step_h = ts_srv.diff().dt.total_seconds().div(3600)
gaps = step_h[(step_h > 4)]
weekend = int(((ts_srv.dt.dayofweek[gaps.index] == 0) & (gaps > 40)).sum())   # Fri close -> Mon open
add("high", {"id": "ohlcv-candle-consistency", "kind": "data", "title": "Every bar is a valid candle (high on top, low at the bottom)",
    "formula": "high >= max(open, close), low <= min(open, close), increasing unique timestamps",
    "stats": {"high below the body": pct(bad_hi, n), "low above the body": pct(bad_lo, n), "zero-range bars": pct(flat, n),
              "zero-volume bars": pct(zero_v, n), "duplicate timestamps": f"{dup}", "out-of-order timestamps": f"{nonmono}",
              "gaps longer than 4h": f"{len(gaps):,} ({weekend:,} are weekend Friday→Monday; the rest are daily breaks and holidays)",
              "rows in file → rows the pipeline emits": f"{n:,} → {NE:,} (the first {n - NE} are indicator warm-up)"},
    "decision_label": "bars where a feature would read an impossible candle", "decision_count": bad_hi + bad_lo + dup + nonmono,
    "open": bool(bad_hi + bad_lo + dup + nonmono > 0)})

# ---- data check 2: H4 == 4h buckets of the M15 file (both are server time on the same clock) ----
m = pd.read_csv(os.path.join(ROOT, "data", "mt5", "XAUUSD_M15.csv"))
m["timestamp"] = pd.to_datetime(m["timestamp"]); m["b"] = m["timestamp"].dt.floor("4h")
agg = m.groupby("b").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                         volume=("volume", "sum"), slots=("open", "size"), first=("timestamp", "min"))
h4s = pd.read_csv(os.path.join(ROOT, "data", "mt5", "XAUUSD_H4.csv")); h4s["timestamp"] = pd.to_datetime(h4s["timestamp"])
h4s = h4s.set_index("timestamp")
ov = h4s.index.intersection(agg.index)
eq = {k: int((np.abs(h4s.loc[ov, k].to_numpy(float) - agg.loc[ov, k].to_numpy(float)) < 1e-9).sum()) for k in ("open", "high", "low", "close", "volume")}
all_ok = int(np.all([np.abs(h4s.loc[ov, k].to_numpy(float) - agg.loc[ov, k].to_numpy(float)) < 1e-9 for k in ("open", "high", "low", "close", "volume")], axis=0).sum())
vol_bad = len(ov) - eq["volume"]
vd = (h4s.loc[ov, "volume"] - agg.loc[ov, "volume"]); vd = vd[vd != 0]
add("close", {"id": "ohlcv-h4-vs-m15", "kind": "data", "title": "The H4 file equals 4-hour buckets of the M15 file",
    "formula": "bucket M15 bars by floor(server time, 4h): first open, max high, min low, last close, summed volume",
    "stats": {"overlap": f"{len(ov):,} H4 bars ({ov.min():%Y-%m-%d} to {ov.max():%Y-%m-%d}, server time)",
              "open / high / low / close equal": f"{eq['open']:,} / {eq['high']:,} / {eq['low']:,} / {eq['close']:,}",
              "volume equal": f"{eq['volume']:,}" + ("" if not vol_bad else f" ({vol_bad:,} differ, median {vd.median():+.0f} ticks)"),
              "all five equal": pct(all_ok, len(ov))},
    "decision_label": "H4 bars that disagree with their M15 bucket", "decision_count": len(ov) - all_ok, "open": bool(len(ov) - all_ok > 0)})

# ---- data check 3: the server-midnight bar holds fewer M15 slots (the M15 day opens at 01:00 server, F-080) ----
mid = agg.loc[ov][agg.loc[ov].index.hour == 0]; rest = agg.loc[ov][agg.loc[ov].index.hour != 0]
rng = (h4s["high"] - h4s["low"])
r_mid = float(rng.loc[mid.index].median()); r_rest = float(rng.loc[rest.index].median())
add("high", {"id": "ohlcv-short-midnight-bar", "kind": "data", "title": "The 00:00 server bar is shorter than the others",
    "formula": "count M15 slots inside each H4 bar; compare the 00:00 bar's range with the rest",
    "stats": {"M15 slots in the 00:00 bar (median)": f"{int(mid['slots'].median())} of 16 (first print {mid['first'].dt.strftime('%H:%M').mode().iloc[0]} server)",
              "M15 slots in other bars (median)": f"{int(rest['slots'].median())} of 16",
              "median range, 00:00 bar vs others": f"${r_mid:.2f} vs ${r_rest:.2f}",
              "00:00 bars in the file": f"{int((ts_srv.dt.hour == 0).sum()):,}"},
    "decision_label": "no alternative value to compare (a property of the feed)", "decision_count": 0, "open": False,
    "note": "The bar is a true 4-hour bucket but the market only trades about 3 of those hours, so its range (and the true range ATR reads) is smaller. Rolling windows count it as a full bar."})

# ---- volume caveat follows the existing volume branch ----
add("volume", {"id": "volume-raw-tick-data", "kind": "data", "title": "Tick volume, not traded volume (follows the volume decision)",
    "formula": "MT5 tick_volume; real_volume is 0 for this symbol (F-099)", "stats": {"bars": f"{NE:,}"},
    "decision_label": "follows volume-tick-data", "decision_count": 0, "open": False, "follows": "volume-tick-data"})

json.dump(D, open(OUTP, "w"), indent=1, default=float)
for col in COLS:
    f = D["features"][col]
    print(f"{f['fm']:7} {col:7} {f['dtype']:8} trunk mism={f['trunk']['mismatch_count']:4} maxdiff={f['trunk']['max_abs_diff']:.2e} refs={len(f['refs']):3} " +
          ", ".join(f"{b['id']}({'OPEN' if b['open'] else 'closed'}:{b['decision_count']})" for b in f["branches"]))
    for b in f["branches"]:
        for k_, v_ in b["stats"].items(): print("     ", k_, "=", v_)
