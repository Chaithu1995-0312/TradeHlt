"""PNP incremental-information test (matched event/control, chronological discovery -> freeze -> holdout).

Research only.  Reuses the events of the existing bar-first census (results/pnp_bar_census_full/events.csv)
and the same FeaturePipeline.  Context covariates use only bars <= the observation bar.  Outcomes are read only
after matching.  Nothing under src/, configs/ or models/ is touched.

    python scripts/analysis/pnp_incremental_test.py --csv data/XAUUSD_M15.csv --stage discovery --out results/pnp_incremental_test
    python scripts/analysis/pnp_incremental_test.py --csv data/XAUUSD_M15.csv --stage holdout   --out results/pnp_incremental_test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

H = [1, 4, 8, 16]
SPEC = {
    "purpose": "Does a confirmed P->N->P (or N->P->N) transition add information about forward price movement beyond matched market context?",
    "events": "exact events from results/pnp_bar_census_full/events.csv (detector, thresholds, refractory and timestamps unchanged); trend_bias and ema_spread events are identical and are analysed once as family 'ema_spread'",
    "families": {"features": ["ema_spread", "macd_line", "momentum_score", "macd_hist", "trend_strength", "rsi_14"], "patterns": ["PNP", "NPN"],
                 "note": "PNP and NPN are distinct families; tests = 6 features x 2 patterns x 4 horizons = 48 per period"},
    "periods": {"discovery": ["2024-05-24", "2025-07-31"], "holdout": ["2025-08-01", "2026-05-21"],
                "freeze": "stage=discovery writes discovery_freeze.json (sha256 of discovery summary and spec); stage=holdout refuses to run without a matching freeze"},
    "observation_landmark": "bar close of the confirmation bar t; every covariate uses bars <= t",
    "context_covariates": {
        "exact": ["htf_state", "volatility_regime", "session", "hour_of_day", "feature_sign_at_t (control has the same current sign as the event's final phase)"],
        "nearest_neighbour_standardised": ["prior_ret_16 (1e4*ln(close[t]/close[t-16]))", "prior_ret_64", "volatility_ratio"],
        "htf_state": "sign(EMA20 - EMA50) of completed H4 closes (4h buckets starting 00,04,..; available when bucket end <= t close); ewm adjust=False; 0 before 50 buckets",
        "standardisation": "SD of each covariate over the eligible bars of the same period (context only; no outcomes)",
    },
    "control_pool": "eligible bars of the same period: finite features, 16-bar forward outcome available, not within +/-16 bars of any event of the same feature (either pattern), same exact strata",
    "matching": {"primary": "1:1 nearest neighbour, per-covariate caliper 0.5 SD, no replacement, greedy in event time order",
                 "sensitivity": {"caliper_025": "caliper 0.25 SD", "k3_replace": "up to 3 nearest controls with replacement (mean of controls)",
                                 "hour_relaxed": "session + 4-hour bucket instead of exact hour", "non_overlap": "primary pairs, events thinned to >= 16 bars apart"},
                 "unmatched": "events without a control in caliper are dropped and counted"},
    "outcome": {"formula": "10000 * ln(close[t+k] / close[t]) bps, k in {1,4,8,16}",
                "alignment": "multiplied by the event's final-phase sign (+1 PNP, -1 NPN); the matched control inherits the event's sign",
                "missing": "pair dropped for the horizon if timestamp[t+k]-timestamp[t] != 15min*k for event or control; events/controls need the 16-bar outcome so every horizon uses the same sample",
                "overlap": "forward windows of nearby events overlap; inference clusters by calendar day of the observation bar"},
    "hypotheses": {"H1": "context-only linear model of raw forward return (htf dummies, volatility regime dummies, hour dummies, prior_ret_16, prior_ret_64, volatility_ratio) fitted on discovery bars, out-of-sample R^2 on holdout bars",
                   "H2": "paired difference d = aligned(event) - aligned(control); day-cluster bootstrap (4000) CI and p; also pooled OLS of aligned return on context + event indicator with day-clustered SE (primary matching only)",
                   "H3": "same sign and holdout BH q < 0.05 in the chronological holdout after the discovery freeze"},
    "multiple_testing": "Benjamini-Hochberg across the 48 family x direction x horizon tests, separately in discovery and holdout",
    "promotion_rule": "NONE promotable from this experiment. Support requires discovery BH q<0.05 AND holdout same sign AND holdout BH q<0.05 AND holdout CI excluding 0 AND >=3 of 4 sensitivities same sign in both periods. Anything else = inconclusive/unsupported in scope. No production change either way.",
    "bootstrap_seed": 42,
}


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bh(p):
    p = np.asarray(p, float); q = np.full_like(p, np.nan); ok = ~np.isnan(p)
    if not ok.any():
        return q
    idx = np.argsort(p[ok]); pm = p[ok][idx]; m = len(pm)
    adj = np.minimum.accumulate((pm * m / (np.arange(m) + 1))[::-1])[::-1]
    o = np.empty(m); o[idx] = np.minimum(adj, 1); q[ok] = o
    return q


# ----------------------------------------------------------------------------- context
def build_context(df: pd.DataFrame) -> pd.DataFrame:
    """Causal context per M15 bar (uses only bars <= row)."""
    ts = df["timestamp"]
    close = df["close"].to_numpy(float)
    ctx = pd.DataFrame({"timestamp": ts})
    ctx["prior_ret_16"] = 1e4 * np.log(close / pd.Series(close).shift(16).to_numpy())
    ctx["prior_ret_64"] = 1e4 * np.log(close / pd.Series(close).shift(64).to_numpy())
    ctx["volatility_ratio"] = df["volatility_ratio"].to_numpy(float)
    ctx["volatility_regime"] = df["volatility_regime"].to_numpy(float)
    ctx["session"] = df["session"].to_numpy(float)
    ctx["hour"] = ts.dt.hour.to_numpy()
    # HTF (H4) state from completed buckets only
    b = pd.DataFrame({"ts": ts, "close": close}).set_index("ts")
    h4 = b["close"].resample("4h", closed="left", label="left").last().dropna()
    avail = h4.index + pd.Timedelta(hours=4)           # bucket usable once it has closed
    e20 = h4.ewm(span=20, adjust=False).mean(); e50 = h4.ewm(span=50, adjust=False).mean()
    st = np.sign(e20 - e50)
    st.iloc[:50] = 0
    h = pd.DataFrame({"avail": avail, "htf_state": st.to_numpy()}).sort_values("avail")
    # M15 bar at open time t closes at t+15min; usable buckets have avail <= t+15min
    left = pd.DataFrame({"close_ts": ts + pd.Timedelta(minutes=15)})
    m = pd.merge_asof(left, h, left_on="close_ts", right_on="avail", direction="backward")
    ctx["htf_state"] = m["htf_state"].fillna(0).to_numpy()
    return ctx


def forward(df: pd.DataFrame):
    ts = df["timestamp"]; close = df["close"].to_numpy(float); out = {}
    for k in H:
        r = np.full(len(df), np.nan)
        ok = (ts.shift(-k) - ts).dt.total_seconds().to_numpy()[:-k] == 15 * 60 * k
        r[:-k] = np.where(ok, 1e4 * np.log(close[k:] / close[:-k]), np.nan)
        out[k] = r
    return out


# ----------------------------------------------------------------------------- matching
def match_family(ev_idx, ev_sign, feat_sign, ctx, pool_ok, exclude, period_mask, cal=0.5, k=1, replace=False,
                 hour_relaxed=False, sd=None):
    """Return list of (event position, [control idx...]) and unmatched event positions. No outcome used."""
    cov = ctx[["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float)
    htf = ctx["htf_state"].to_numpy(); vr = ctx["volatility_regime"].to_numpy(); ses = ctx["session"].to_numpy(); hr = ctx["hour"].to_numpy()
    base = pool_ok & ~exclude & period_mask
    used = np.zeros(len(ctx), bool)
    pairs, unmatched = [], []
    for pos, (i, s) in enumerate(zip(ev_idx, ev_sign)):
        m = base & (htf == htf[i]) & (vr == vr[i]) & (ses == ses[i]) & (feat_sign == s)
        m &= ((hr // 4) == (hr[i] // 4)) if hour_relaxed else (hr == hr[i])
        if not replace:
            m &= ~used
        cand = np.where(m)[0]
        if len(cand):
            d = np.abs(cov[cand] - cov[i]) / sd
            keep = np.all(d <= cal, axis=1)
            cand, d = cand[keep], d[keep]
        if len(cand) == 0:
            unmatched.append(pos); continue
        order = np.argsort((d ** 2).sum(axis=1))[:k]
        chosen = cand[order]
        if not replace:
            used[chosen] = True
        pairs.append((pos, chosen.tolist()))
    return pairs, unmatched


def cluster_boot(d, days, rng, reps=4000):
    d = np.asarray(d, float)
    if len(d) < 3:
        return dict(mean=float(d.mean()) if len(d) else np.nan, lo=np.nan, hi=np.nan, p=np.nan, n_days=len(set(days)))
    u, inv = np.unique(days, return_inverse=True)
    S = np.bincount(inv, weights=d); N = np.bincount(inv).astype(float)
    idx = rng.integers(0, len(u), size=(reps, len(u)))
    bm = S[idx].sum(1) / N[idx].sum(1)
    mean = d.mean()
    p = float(((np.abs(bm - bm.mean()) >= abs(mean) - 1e-12).sum() + 1) / (reps + 1))
    return dict(mean=float(mean), lo=float(np.percentile(bm, 2.5)), hi=float(np.percentile(bm, 97.5)), p=p, n_days=len(u))


def cluster_ols(y, X, days):
    """OLS with day-clustered sandwich SE; returns coef, se for all columns."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    u, inv = np.unique(days, return_inverse=True)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in range(len(u)):
        xg = X[inv == g].T @ e[inv == g]
        meat += np.outer(xg, xg)
    V = XtX_inv @ meat @ XtX_inv
    return beta, np.sqrt(np.diag(V))


def design(ctxrows, event_flag=None):
    cols = [ctxrows["prior_ret_16"], ctxrows["prior_ret_64"], ctxrows["volatility_ratio"],
            (ctxrows["htf_state"] > 0).astype(float), (ctxrows["htf_state"] < 0).astype(float),
            (ctxrows["volatility_regime"] == 1).astype(float), (ctxrows["volatility_regime"] == 2).astype(float)]
    X = np.column_stack([np.ones(len(ctxrows))] + [np.asarray(c, float) for c in cols])
    if event_flag is not None:
        X = np.column_stack([X, event_flag])
    return X


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--stage", choices=["discovery", "holdout"], required=True)
    ap.add_argument("--events", default=str(ROOT / "results/pnp_bar_census_full/events.csv"))
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    spec_txt = json.dumps(SPEC, indent=2, sort_keys=True)
    spec_path = out / "spec.json"
    if a.stage == "discovery":
        spec_path.write_text(spec_txt)
    else:
        assert spec_path.read_text() == spec_txt, "spec changed since discovery"
        fz = json.loads((out / "discovery_freeze.json").read_text())
        assert fz["discovery_summary_sha256"] == sha_file(out / "summary_discovery.csv"), "discovery results changed after freeze"
        assert fz["spec_sha256"] == hashlib.sha256(spec_txt.encode()).hexdigest()

    from features import feature_schema as fs
    from features.feature_pipeline import FeaturePipeline
    census = json.loads((ROOT / "results/pnp_bar_census_full/manifest.json").read_text())
    assert sha_file(ROOT / "src/features/feature_pipeline.py") == census["pipeline_sha256"], "feature pipeline changed since the census"
    assert sha_file(a.csv) == census["ohlcv_sha256"], "corpus changed since the census"
    raw = pd.read_csv(a.csv); raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    df, _ = FeaturePipeline(raw.copy()).run(); df = df.reset_index(drop=True); df["timestamp"] = pd.to_datetime(df["timestamp"])
    ts = df["timestamp"]
    ctx = build_context(df)
    fwd = forward(df)
    EV = pd.read_csv(a.events)
    EV = EV[EV.feature != "trend_bias"].copy()                   # identical to ema_spread
    feats = SPEC["families"]["features"]
    allf = np.all(np.isfinite(df[feats].to_numpy(float)), axis=1) & np.isfinite(ctx[["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float)).all(axis=1)
    out_ok = np.all([np.isfinite(fwd[k]) for k in H], axis=0)
    pool_ok = allf & out_ok
    d0, d1 = pd.Timestamp(SPEC["periods"]["discovery"][0]), pd.Timestamp(SPEC["periods"]["discovery"][1]) + pd.Timedelta(days=1)
    disc = ((ts >= d0) & (ts < d1)).to_numpy()
    hold = (ts >= d1).to_numpy()
    periods = {"discovery": disc} if a.stage == "discovery" else {"holdout": hold}
    rng = np.random.default_rng(SPEC["bootstrap_seed"])
    day = ts.dt.date.astype(str).to_numpy()

    rows, ev_out, ct_out, bal = [], [], [], []
    for per, pmask in periods.items():
        sd = np.nanstd(ctx.loc[pool_ok & pmask, ["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float), axis=0)
        for f in feats:
            v = df[f].to_numpy(float) - (50.0 if f == "rsi_14" else 0.0)
            fsign = np.sign(v).astype(int)
            fe = EV[EV.feature == f]
            excl = np.zeros(len(df), bool)
            for i in fe.confirm_idx.to_numpy():
                excl[max(0, i - 16):i + 17] = True
            for pat in SPEC["families"]["patterns"]:
                e = fe[(fe.pattern == pat) & pmask[fe.confirm_idx.clip(upper=len(df) - 1).to_numpy()]]
                e_ok = e[pool_ok[e.confirm_idx.to_numpy()]]
                ev_idx = e_ok.confirm_idx.to_numpy(); ev_sign = e_ok["sign"].to_numpy()
                n_events, n_outcome_missing = len(e), len(e) - len(e_ok)
                variants = {
                    "primary": dict(cal=0.5, k=1, replace=False, hour_relaxed=False),
                    "caliper_025": dict(cal=0.25, k=1, replace=False, hour_relaxed=False),
                    "k3_replace": dict(cal=0.5, k=3, replace=True, hour_relaxed=False),
                    "hour_relaxed": dict(cal=0.5, k=1, replace=False, hour_relaxed=True),
                    "non_overlap": dict(cal=0.5, k=1, replace=False, hour_relaxed=False),
                }
                for vname, kw in variants.items():
                    ei, es = ev_idx, ev_sign
                    if vname == "non_overlap":
                        keep, last = [], -10**9
                        for j, i in enumerate(ei):
                            if i - last >= 16:
                                keep.append(j); last = i
                        ei, es = ei[keep], es[keep]
                    pairs, unm = match_family(ei, es, fsign, ctx, pool_ok, excl, pmask, sd=sd, **kw)
                    for k in H:
                        d, dd, ev_r, ct_r = [], [], [], []
                        for pos, ch in pairs:
                            i, s = ei[pos], es[pos]
                            er = s * fwd[k][i]; cr = np.mean([s * fwd[k][c] for c in ch])
                            d.append(er - cr); dd.append(day[i]); ev_r.append(er); ct_r.append(cr)
                        res = cluster_boot(d, dd, rng) if d else dict(mean=np.nan, lo=np.nan, hi=np.nan, p=np.nan, n_days=0)
                        oc = ose = np.nan
                        if vname == "primary" and len(pairs) >= 8:
                            eidx = [ei[p_] for p_, _ in pairs]; cidx = [ch[0] for _, ch in pairs]; sg = np.array([es[p_] for p_, _ in pairs], float)
                            y = np.concatenate([sg * fwd[k][eidx], sg * fwd[k][cidx]])
                            X = design(ctx.loc[eidx + cidx], np.r_[np.ones(len(eidx)), np.zeros(len(cidx))])
                            bt, se_ = cluster_ols(y, X, np.r_[day[eidx], day[cidx]])
                            oc, ose = float(bt[-1]), float(se_[-1])
                        dz = (np.mean(d) / np.std(d, ddof=1)) if len(d) > 2 and np.std(d, ddof=1) > 0 else np.nan
                        rows.append(dict(period=per, variant=vname, feature=f, pattern=pat, horizon=k, events=n_events,
                                         events_outcome_missing=n_outcome_missing, events_considered=len(ei), pairs=len(pairs),
                                         unmatched=len(unm), match_rate=(len(pairs) / len(ei)) if len(ei) else np.nan,
                                         event_mean_bps=float(np.mean(ev_r)) if ev_r else np.nan, control_mean_bps=float(np.mean(ct_r)) if ct_r else np.nan,
                                         diff_mean_bps=res["mean"], ci_lo=res["lo"], ci_hi=res["hi"], boot_p=res["p"], n_days=res["n_days"], d_z=dz, ols_event_coef=oc, ols_event_se=ose))
                    if vname == "primary":
                        # record matched pairs and balance (no outcomes used to choose)
                        for pos, ch in pairs:
                            i, s = ei[pos], es[pos]
                            ev_out.append(dict(period=per, feature=f, pattern=pat, event_idx=int(i), confirm_ts=str(ts.iloc[i]), sign=int(s), day=day[i],
                                               controls=";".join(str(c) for c in ch),
                                               **{f"ret_{k}": float(fwd[k][i]) for k in H}))
                            for c in ch:
                                ct_out.append(dict(period=per, feature=f, pattern=pat, event_idx=int(i), control_idx=int(c), control_ts=str(ts.iloc[c]),
                                                   sign=int(s), **{f"ret_{k}": float(fwd[k][c]) for k in H}))
                        if pairs:
                            cols = ["prior_ret_16", "prior_ret_64", "volatility_ratio"]
                            E_ = ctx.loc[[ei[p_] for p_, _ in pairs], cols].to_numpy(); C_ = ctx.loc[[c[0] for _, c in pairs], cols].to_numpy()
                            U_ = ctx.loc[pool_ok & pmask & ~excl & (fsign == fsign[ei[pairs[0][0]]]), cols].to_numpy()
                            for j, cname in enumerate(cols):
                                pooled_sd = np.sqrt((E_[:, j].var(ddof=1) + C_[:, j].var(ddof=1)) / 2) if len(E_) > 2 else np.nan
                                bal.append(dict(period=per, feature=f, pattern=pat, covariate=cname, pairs=len(pairs),
                                                smd_matched=float((E_[:, j].mean() - C_[:, j].mean()) / pooled_sd) if pooled_sd else np.nan,
                                                smd_unmatched_pool=float((E_[:, j].mean() - U_[:, j].mean()) / np.sqrt((E_[:, j].var(ddof=1) + U_[:, j].var(ddof=1)) / 2)) if len(E_) > 2 and len(U_) > 2 else np.nan))
    R = pd.DataFrame(rows)
    # BH on primary
    prim = R.variant == "primary"
    R.loc[prim, "bh_q"] = bh(R.loc[prim, "boot_p"].to_numpy())
    # sensitivity agreement
    def sens_agree(g):
        base = g[g.variant == "primary"]
        if base.empty or np.isnan(base.diff_mean_bps.iloc[0]):
            return np.nan
        s0 = np.sign(base.diff_mean_bps.iloc[0]); o = g[(g.variant != "primary")]
        return int((np.sign(o.diff_mean_bps) == s0).sum())
    agl = []
    for key, g in R.groupby(["period", "feature", "pattern", "horizon"]):
        agl.append(dict(zip(["period", "feature", "pattern", "horizon"], key), sensitivities_same_sign_of_4=sens_agree(g)))
    R = R.merge(pd.DataFrame(agl), on=["period", "feature", "pattern", "horizon"], how="left")
    pd.DataFrame(bal).to_csv(out / f"balance_{a.stage}.csv", index=False)
    pd.DataFrame(ev_out).to_csv(out / f"matched_events_{a.stage}.csv", index=False)
    pd.DataFrame(ct_out).to_csv(out / f"matched_controls_{a.stage}.csv", index=False)
    R.to_csv(out / f"summary_{a.stage}.csv", index=False)

    # ---- H1: context baseline (discovery bars -> holdout bars), run at the holdout stage with the frozen discovery fit
    h1 = None
    if a.stage == "holdout":
        tr = pool_ok & disc; te = pool_ok & hold
        hrs = ctx["hour"].to_numpy()
        def X_of(mask):
            X = design(ctx.loc[mask])
            H24 = np.column_stack([(hrs[mask] == h).astype(float) for h in range(1, 24)])
            return np.column_stack([X, H24])
        Xtr, Xte = X_of(tr), X_of(te)
        h1 = {}
        for k in H:
            ytr, yte = fwd[k][tr], fwd[k][te]
            beta = np.linalg.pinv(Xtr.T @ Xtr + 1e-6 * np.eye(Xtr.shape[1])) @ Xtr.T @ ytr
            pred = Xte @ beta
            r2 = 1 - ((yte - pred) ** 2).sum() / ((yte - ytr.mean()) ** 2).sum()
            h1[str(k)] = dict(oos_r2=float(r2), train_n=int(tr.sum()), test_n=int(te.sum()), corr=float(np.corrcoef(pred, yte)[0, 1]))
        (out / "h1_context_baseline.json").write_text(json.dumps(h1, indent=2))

    if a.stage == "discovery":
        (out / "discovery_freeze.json").write_text(json.dumps({
            "discovery_summary_sha256": sha_file(out / "summary_discovery.csv"),
            "spec_sha256": hashlib.sha256(spec_txt.encode()).hexdigest(),
            "frozen_before_holdout": True,
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()}, indent=2))
    P = R[prim]
    print(a.stage, "rows", len(R), "primary tests", len(P), "min boot_p", P.boot_p.min(), "min q", P.bh_q.min(),
          "pairs total", int(P.groupby(['feature', 'pattern']).pairs.first().sum()), "mean match rate", round(P.match_rate.mean(), 3))
    pd.set_option("display.width", 200)
    print(P[P.horizon == 8][["feature", "pattern", "events", "pairs", "unmatched", "event_mean_bps", "control_mean_bps", "diff_mean_bps", "ci_lo", "ci_hi", "boot_p", "bh_q"]].round(2).to_string())
    if h1:
        print("H1", {k: round(v["oos_r2"], 5) for k, v in h1.items()})


if __name__ == "__main__":
    main()
