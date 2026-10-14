"""Candle Images workflow: the study cards' pattern rules (docs/reference/candle_theory) as a parallel
branch beside the registered candle patterns (FM-107..114, FM-120), on the last month of XAUUSD H4.

Trunk: independent recompute of the registered rule vs the pipeline column.
Branch: the card's rule. Cards give no numbers, so a card rule reuses the registered thresholds and
changes only what the card itself changes (stated per pattern). Writes D["candle_images"].
"""
import sys, os, json, logging
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
P = CFG["candle_patterns"]; L = int(P["swing_lookback"])
raw, CLOCK_ID = load_h4_utc()
enr, _ = FeaturePipeline(raw.copy(), timeframe="H4").run(); enr = enr.reset_index(drop=True)
ts = pd.to_datetime(enr["timestamp"])
o, h, l, c = (enr[k].to_numpy(float) for k in ("open", "high", "low", "close")); n = len(c)

# ---- independent primitives (plain numpy, not features.candle_patterns) ----
rng = h - l; body = np.abs(c - o); up = h - np.maximum(o, c); lo = np.minimum(o, c) - l
pos = rng > 0
B = np.where(pos, body / np.where(pos, rng, 1), 0.0); U = np.where(pos, up / np.where(pos, rng, 1), 0.0); Dn = np.where(pos, lo / np.where(pos, rng, 1), 0.0)
atr = AP.sma(AP.true_range(h, l, c), CFG["atr_period"])
gate = pos & ~np.isnan(atr) & (rng >= P["size_gate_atr_k"] * np.nan_to_num(atr, nan=np.inf))
contig = np.zeros(n, bool); contig[1:] = np.diff(ts.to_numpy().astype("datetime64[ns]").astype(np.int64)) == np.int64(4 * 3600 * 10**9)
prev = lambda x, k=1: np.concatenate([np.full(k, np.nan), x[:-k]])
prior_low = pd.Series(l).shift(1).rolling(L).min().to_numpy(); prior_high = pd.Series(h).shift(1).rolling(L).max().to_numpy()
down_before = prev(c, 1) < prev(c, L + 1)      # card "after a downtrend": the previous close is below the close L bars before it
up_before = prev(c, 1) > prev(c, L + 1)
bull, bear = c > o, c < o
o1, h1, l1, c1 = prev(o), prev(h), prev(l), prev(c); body1 = np.abs(c1 - o1)
c2_contig = contig & np.concatenate([[False], contig[:-1]])
B1, B2 = prev(B, 1), prev(B, 2); o2, c2 = prev(o, 2), prev(c, 2)

probe_lo = (lo >= P["probe_wick_body_multiple"] * body) & (U <= P["probe_opposite_wick_max"])
probe_hi = (up >= P["probe_wick_body_multiple"] * body) & (Dn <= P["probe_opposite_wick_max"])
eng_body_bull = contig & (c1 < o1) & bull & (o <= c1) & (c >= o1) & (body > body1)
eng_body_bear = contig & (c1 > o1) & bear & (o >= c1) & (c <= o1) & (body > body1)
ms_repo = c2_contig & (c2 < o2) & (B2 >= P["morning_star_body_min"]) & (B1 <= P["morning_star_mid_max"]) & bull & (B >= P["morning_star_body_min"])

PATTERNS = [
    # (column, card, title, repo rule array, card rule array, card rule text, what the card changes)
    ("hammer", "03, 07", "Hammer",
     probe_lo & (l <= prior_low) & gate,
     probe_lo & down_before,
     "lower wick ≥ 2 × body, upper wick ≤ 10% of range, and the previous close is below the close 5 bars earlier (a downtrend)",
     "Card: 'appears after a downtrend'. Drops the fresh-5-bar-low test and the 0.5 × ATR size floor; the card has neither."),
    ("shooting_star", "04, 07", "Shooting star",
     probe_hi & (h >= prior_high) & gate,
     probe_hi & up_before,
     "upper wick ≥ 2 × body, lower wick ≤ 10% of range, and the previous close is above the close 5 bars earlier (an uptrend)",
     "Card: 'after uptrend'. Drops the fresh-5-bar-high test and the ATR floor."),
    ("doji_material", "05, 06", "Doji",
     (B <= P["doji_body_max"]) & (np.abs(U - Dn) <= P["doji_wick_asymmetry_max"]) & gate,
     pos & (B <= P["doji_body_max"]) & (up > 0) & (lo > 0),
     "body ≤ 10% of range with a wick on both sides",
     "Card: 'open and close nearly equal, price moved up and down'. No size floor and no rule that the wicks be equal."),
    ("engulfing_bull", "06, 07", "Bullish engulfing",
     eng_body_bull,
     eng_body_bull & (h >= h1) & (l <= l1),
     "registered body test, and the new candle's high and low also cover the previous candle's high and low",
     "Card draws the green candle covering the whole red one, wicks included; the registered rule covers bodies only."),
    ("engulfing_bear", "06, 07", "Bearish engulfing",
     eng_body_bear,
     eng_body_bear & (h >= h1) & (l <= l1),
     "registered body test plus full high/low coverage",
     "Mirror of bullish engulfing."),
    ("morning_star", "06", "Morning star",
     ms_repo,
     ms_repo & (prev(c, 3) < prev(c, L + 3)),
     "registered 3-candle rule, and the close before candle 1 is below the close 5 bars earlier (a downtrend)",
     "Card draws it at the bottom of a decline ('bullish reversal'); FM-120 deliberately has no trend argument."),
    ("inside_bar", "12", "Inside bar",
     contig & (h <= h1) & (l >= l1),
     contig & (h <= h1) & (l >= l1),
     "small candle inside the previous larger candle's high and low",
     "Same as the registered rule."),
]

onto = yaml.safe_load(open(os.path.join(ROOT, "configs", "formulas", "market_ontology.yaml"), encoding="utf-8"))
FM = {}
def walk(x, key=None):
    if isinstance(x, dict):
        if isinstance(x.get("id"), str) and x["id"].startswith("FM-") and key: FM.setdefault(key, (x["id"], x.get("formula")))
        for k, v in x.items(): walk(v, k)
    elif isinstance(x, list):
        for v in x: walk(v)
walk(onto)

end = ts.max(); start = end - pd.Timedelta(days=30)
M = (ts > start).to_numpy(); idx = np.where(M)[0]
out = {"window": {"ts": ts[M].dt.strftime("%Y-%m-%d %H:%M").tolist(), "o": o[M].tolist(), "h": h[M].tolist(), "l": l[M].tolist(), "c": c[M].tolist()},
       "bars": int(M.sum()), "from": str(ts[M].min())[:16], "to": str(end)[:16], "lookback": L, "patterns": []}
for col, card, title, repo, cardr, ctext, cchange in PATTERNS:
    pipe = enr[col].to_numpy(float) == 1.0
    repo = np.nan_to_num(repo.astype(float), nan=0.0) == 1.0; cardr = np.nan_to_num(cardr.astype(float), nan=0.0) == 1.0
    trunk_bad_all = int((repo != pipe).sum()); trunk_bad_m = int((repo[M] != pipe[M]).sum())
    diff = M & (pipe != cardr)
    fm, formula = FM.get(col, ("?", None))
    out["patterns"].append({
        "col": col, "fm": fm, "card": card, "title": title, "registered": formula, "card_rule": ctext, "card_change": cchange,
        "trunk_month_mismatch": trunk_bad_m, "trunk_all_mismatch": trunk_bad_all, "trunk_all_bars": n,
        "repo_hits": int(pipe[M].sum()), "card_hits": int(cardr[M].sum()), "both": int((pipe & cardr)[M].sum()),
        "repo_only": int((pipe & ~cardr)[M].sum()), "card_only": int((cardr & ~pipe)[M].sum()),
        "repo_mask": pipe[M].tolist(), "card_mask": cardr[M].tolist(),
        "diff_bars": [{"ts": str(ts[i])[:16], "repo": int(pipe[i]), "card": int(cardr[i])} for i in np.where(diff)[0]],
        "all_repo_hits": int(pipe.sum()), "all_card_hits": int(cardr.sum()), "all_diff": int((pipe != cardr).sum()),
        "open": bool(diff.sum() > 0)})

OUTP = os.path.join(ROOT, "results", "divergence_h4.json")
D = json.load(open(OUTP, encoding="utf-8")); D["candle_images"] = out
json.dump(D, open(OUTP, "w"), indent=1, default=float)
print(f"window {out['from']} -> {out['to']} UTC, {out['bars']} bars; clock {CLOCK_ID}")
for p in out["patterns"]:
    print(f"{p['fm']:7} {p['col']:15} trunk(month/all)={p['trunk_month_mismatch']}/{p['trunk_all_mismatch']}  repo={p['repo_hits']:3} card={p['card_hits']:3} both={p['both']:3} "
          f"repo_only={p['repo_only']:3} card_only={p['card_only']:3}  | full file repo={p['all_repo_hits']} card={p['all_card_hits']} diff={p['all_diff']}")
