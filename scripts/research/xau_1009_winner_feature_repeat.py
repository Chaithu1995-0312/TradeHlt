"""Do the feature values of winning trades repeat? (descriptive, 2026-10-09)

Takes the trades of the pre-registered H4 lower-wick 3R test (scripts/research/xau_1009_prereg_h4_lowerwick_3r.py,
run unchanged via runpy, so no trade logic is copied) and reads the 67 canonical features (all 79 minus 12
price-scale columns) at each trade's signal bar: the last M15 bar inside that H4 bar.

Two views per trade (CH-timeframe-ssot-v1): `m15_*` = the 67 M15 pipeline features at the LAST M15 bar of the signal
H4 bar (they describe that 15-minute candle, not the H4 candle); `h4_*` = candle-pattern flags computed on the H4
candles themselves via the frozen script's h4_patterns(). Questions, in-sample (2-year file, 83 trades) where there
are enough winners, run on each view:
1. Per feature: do winners and losers differ (AUC)? Compared with the largest AUC that 1,000 label shuffles
   produce, because 67 features will always show some difference by chance.
2. Do winners look like each other? For each winner, is its nearest other trade (standardized features) also a
   winner more often than the winner share would give by chance (1,000 shuffles)?
Out-of-sample (22 May - 6 Oct 2026, 14 trades, 2 winners): the two winners' feature values are listed beside the
losers, descriptive only. Selecting trades by outcome is hindsight by construction; nothing here is a rule.
Result: see the SESSION LOG entry of 2026-10-09 in assistant_project.md.
"""
import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research/xau_1009"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src"))
from data_ingestion.corpus_store import load as corpus_load  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features import feature_schema as FS  # noqa: E402

EXCLUDE = ["open", "high", "low", "close", "volume", "ema_fast", "ema_slow", "macd_line", "macd_signal",
           "macd_hist_raw", "body_size", "candle_range"]
FEATS = [f for f in FS.CANONICAL_FEATURES if f not in EXCLUDE]
SHOW = ["lower_wick_ratio", "body_ratio", "pin_lower", "hammer", "rsi_14", "trend_strength_z", "trend_bias",
        "volatility_ratio", "pdl_distance", "liquidity_distance", "break_of_structure", "hour_of_day"]

g = runpy.run_path(str(ROOT / "scripts/research/xau_1009_prereg_h4_lowerwick_3r.py"), run_name="__frozen__")
H4_FLAGS = ["pin_lower", "pin_upper", "hammer", "shooting_star", "doji_material", "dragonfly_doji", "gravestone_doji",
            "engulfing_bull", "engulfing_bear", "inside_bar", "morning_star", "upper_wick_ratio", "lower_wick_ratio"]
M15_COLS = ["m15_" + f for f in FEATS]
H4_COLS = ["h4_" + f for f in H4_FLAGS]


def features_at(trades, df_h4, csv):
    raw = corpus_load(csv, sequence_check=False).frame(parse_dates=["timestamp"])
    m15, _ = FeaturePipeline(raw.copy(), timeframe="M15").run()
    m15 = m15.set_index("timestamp").sort_index()
    pat, _atr = g["h4_patterns"](df_h4)                         # patterns on the H4 candles themselves
    rows = []
    for t in trades:
        start = pd.Timestamp(df_h4.t.iloc[t["i"]])
        win = m15.loc[start: start + pd.Timedelta(hours=3, minutes=45)]
        if len(win) == 0:
            continue
        r = {"m15_" + k: v for k, v in win.iloc[-1][FEATS].astype(float).to_dict().items()}
        r.update({"h4_" + k: float(pat[k][t["i"]]) for k in H4_FLAGS})
        r.update({"t": str(start), "win": int(t["exit"] == "target"), "exit": t["exit"], "R_net": t["R_net"]})
        rows.append(r)
    return pd.DataFrame(rows)


ins = features_at(g["i_one"], g["ins_df"], ROOT / "data/mt5/XAUUSD_M15.csv")
oos = features_at(g["o_one"], g["oos_df"], ROOT / "data/mt5/XAUUSD_M15_2026-04-20_to_2026-10-06.csv")
print("in-sample trades with features", len(ins), "winners", int(ins.win.sum()),
      "| out-of-sample", len(oos), "winners", int(oos.win.sum()), flush=True)
y = ins.win.to_numpy()
results = {}


def analyse(view, cols):
    X = ins[cols].to_numpy(float)
    usable = [j for j in range(len(cols)) if np.nanstd(X[:, j]) > 0]
    rng = np.random.default_rng(7)

    def aucs(labels):
        return np.array([roc_auc_score(labels, X[:, j]) for j in usable])

    obs = aucs(y); dev = np.abs(obs - 0.5)
    null_max = np.array([np.max(np.abs(aucs(rng.permutation(y)) - 0.5)) for _ in range(1000)])
    order = np.argsort(-dev)
    top = [(cols[usable[k]], float(obs[k])) for k in order[:10]]
    p_max = float((np.sum(null_max >= dev.max()) + 1) / 1001)
    print(f"[{view}] {len(usable)} usable columns; top by |AUC-0.5|:", [(f, round(a, 3)) for f, a in top])
    print(f"[{view}] largest |AUC-0.5| = {dev.max():.3f}; shuffle 95th percentile of the largest = {np.percentile(null_max, 95):.3f}; p = {p_max:.3f}")
    mu, sd = np.nanmean(X[:, usable], axis=0), np.nanstd(X[:, usable], axis=0)
    Z = np.nan_to_num((X[:, usable] - mu) / sd)
    D = np.sqrt(((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1)); np.fill_diagonal(D, np.inf)
    nn = D.argmin(axis=1)

    def nn_share(labels):
        w = np.where(labels == 1)[0]
        return float(labels[nn[w]].mean())

    share = nn_share(y); null_nn = np.array([nn_share(rng.permutation(y)) for _ in range(1000)])
    p_nn = float((np.sum(null_nn >= share) + 1) / 1001)
    expect = (y.sum() - 1) / (len(y) - 1)
    print(f"[{view}] winners whose nearest other trade is also a winner: {share:.3f} (chance {expect:.3f}, shuffle mean {null_nn.mean():.3f}), p = {p_nn:.3f}")
    results[view] = {"top_auc": top, "max_dev": float(dev.max()), "null95_max_dev": float(np.percentile(null_max, 95)),
                     "p_max": p_max, "nn_share": share, "nn_expect": float(expect), "p_nn": p_nn}


analyse("m15 features at the last M15 bar", M15_COLS)
analyse("h4 candle patterns", H4_COLS)

# how the H4 pattern flags look on the trades (the rule's own trigger: pin_lower or hammer on the H4 bar)
pd.set_option("display.width", 250)
print("H4-candle flags on in-sample trades (share of trades with the flag set):")
print(ins.groupby("win")[["h4_pin_lower", "h4_hammer", "h4_doji_material", "h4_engulfing_bull", "h4_inside_bar"]].mean().round(3).to_string())
cols = ["t", "exit", "R_net", "h4_pin_lower", "h4_hammer", "h4_lower_wick_ratio"] + ["m15_" + s for s in SHOW]
print(oos[cols].round(3).to_string(index=False))
med = ins.groupby("win")[["m15_" + s for s in SHOW]].median().T.rename(columns={0: "in-sample losers median", 1: "in-sample winners median"})
print(med.round(3).to_string())
(OUT / "winner_feature_repeat.json").write_text(json.dumps({
    "n_ins": len(ins), "win_ins": int(ins.win.sum()), "n_oos": len(oos), "win_oos": int(oos.win.sum()),
    "views": results, "oos_rows": oos[cols].to_dict("records"), "medians": med.to_dict()}, default=str), encoding="utf-8")
