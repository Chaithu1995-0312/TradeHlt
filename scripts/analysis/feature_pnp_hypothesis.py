"""Phase-anchored P->N->P hypothesis on the canonical schema (descriptive; read-only, writes under --out).

Pre-registered in SPEC before measuring.  Reuses run-cleaning from feature_transition_research.
"""
import argparse, csv, json, sys, hashlib
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
from feature_transition_research import clean_runs  # noqa: E402

SPEC = {
    "features": {"primary": ["trend_bias", "ema_spread", "macd_line", "momentum_score", "macd_hist", "trend_strength"],
                 "secondary": ["rsi_14"],
                 "name_mapping": "macd_hist_z, trend_strength_z and fvg_distance are not in CANONICAL_FEATURES; macd_hist and trend_strength are used; fvg_distance is not tested",
                 "rsi_14_sign": "sign(rsi_14 - 50)"},
    "representations": ["raw", "direction_aligned (value x +1 LONG, x -1 SHORT)"],
    "sequence": {"span": "bars [entry-11 .. exit]", "min_run_len": 2,
                 "P1": "cleaned run (+) whose start <= entry bar and sign at entry bar and bar before are +",
                 "N": "next cleaned run (-) starting after the entry bar (adverse phase)",
                 "P2": "next cleaned run (+) starting at or before the exit bar (recovery)",
                 "causality": "P1 is entry-time; N and P2 use bars after entry, so the full sequence is descriptive/exit research, never an entry rule"},
    "split_by_direction": True,
    "groups": "profitable = pnl_rr_net > 0; losing otherwise",
    "adverse_bar": "bar of maximum adverse excursion in entry+1..exit (exit bar for STOPPED)",
}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", required=True); ap.add_argument("--trades", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from features.feature_pipeline import FeaturePipeline
    raw = pd.read_csv(a.csv); raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    df, _ = FeaturePipeline(raw.copy()).run(); df = df.reset_index(drop=True); df["timestamp"] = pd.to_datetime(df["timestamp"])
    ix = {t: i for i, t in enumerate(df.timestamp)}
    trades = sorted(csv.DictReader(open(a.trades, encoding="utf-8-sig")), key=lambda r: r["opened_at"])
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    (out / "spec.json").write_text(json.dumps(SPEC, indent=2))
    feats = SPEC["features"]["primary"] + SPEC["features"]["secondary"]
    rows = []; seqs = {}
    for r in trades:
        i, e = ix[pd.Timestamp(r["opened_at"])], ix[pd.Timestamp(r["closed_at"])]
        d = 1 if r["direction"] == "LONG" else -1
        ef, sl = float(r["entry_fill"]), float(r["sl"]); R = abs(ef - sl)
        adv = (ef - lo[i + 1:e + 1]) / R if d == 1 else (hi[i + 1:e + 1] - ef) / R
        mae_bar = int(np.argmax(adv)) + 1 if len(adv) else 0
        net = float(r["pnl_rr_net"])
        for f in feats:
            v = df[f].to_numpy(float)[i - 11:e + 1]
            v = v - 50 if f == "rsi_14" else v
            for rep in ("raw", "aligned"):
                s = np.sign(v * (d if rep == "aligned" else 1)).astype(int)
                rs = clean_runs(s, 2); ent = 11
                p1 = next((k for k, x in enumerate(rs) if x[0] == 1 and x[1] <= ent and s[ent] == 1 and s[ent - 1] == 1), None)
                seq = False; n_start = p2_start = None
                if p1 is not None:
                    for k in range(p1 + 1, len(rs) - 1):
                        if rs[k][0] == -1 and rs[k][1] > ent and rs[k + 1][0] == 1 and rs[k + 1][1] <= e - i + ent:
                            seq, n_start, p2_start = True, rs[k][1] - ent, rs[k + 1][1] - ent; break
                rows.append(dict(trade_id=r["trade_id"], direction=r["direction"], net_R=net, profitable=net > 0, duration=e - i,
                                 mae_bar=mae_bar, feature=f, rep=rep, positive_at_entry=bool(s[ent] > 0),
                                 p1_established=p1 is not None, pnp_observed=seq, n_start_rel_entry=n_start, p2_start_rel_entry=p2_start,
                                 sign_string="".join("+" if x > 0 else "-" if x < 0 else "0" for x in s)))
    R_ = pd.DataFrame(rows); R_.to_csv(out / "per_trade_feature.csv", index=False)
    summ = []
    for (f, rep, dr), g in R_.groupby(["feature", "rep", "direction"]):
        summ.append(dict(feature=f, rep=rep, direction=dr, n_trades=len(g), pos_at_entry=int(g.positive_at_entry.sum()),
                         pnp_n=int(g.pnp_observed.sum()), pnp_profitable=int((g.pnp_observed & g.profitable).sum()),
                         pnp_losing=int((g.pnp_observed & ~g.profitable).sum()),
                         trades_with_duration_ge_4=int((g.duration >= 4).sum())))
    S = pd.DataFrame(summ); S.to_csv(out / "summary.csv", index=False)
    # candidate redundancy over the corpus (sign agreement / correlation), for the 'adds information' question
    X = df[SPEC["features"]["primary"]].replace([np.inf, -np.inf], np.nan).dropna()
    corr = X.corr(method="spearman").round(3); corr.to_csv(out / "corpus_spearman.csv")
    sg = {a_: {b_: round(float((np.sign(X[a_]) == np.sign(X[b_])).mean()), 3) for b_ in X.columns} for a_ in X.columns}
    (out / "corpus_sign_agreement.json").write_text(json.dumps(sg, indent=1))
    dur = pd.read_csv(Path(a.trades)).set_index("trade_id")["duration_candles"].to_dict()
    meta = {"trades_sha256": hashlib.sha256(Path(a.trades).read_bytes()).hexdigest(), "ohlcv_sha256": hashlib.sha256(Path(a.csv).read_bytes()).hexdigest(),
            "spec_sha256": hashlib.sha256((out / "spec.json").read_bytes()).hexdigest(), "durations": dur,
            "profitable_ids": sorted(set(R_[R_.profitable].trade_id)), "losing_ids": sorted(set(R_[~R_.profitable].trade_id))}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(S.groupby(["rep"]).agg(pnp=("pnp_n", "sum"), prof=("pnp_profitable", "sum"), los=("pnp_losing", "sum")))
    print(S[S.pnp_n > 0].to_string())
    print(R_[R_.pnp_observed].trade_id.value_counts().to_dict()); print(dur)
    print(corr.to_string())


main()
