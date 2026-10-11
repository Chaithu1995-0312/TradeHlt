"""Bar-first P->N->P (and mirror N->P->N) census on the canonical M15 feature series.

Unit of analysis: every eligible M15 bar (no trades required).  The detector is a causal
streaming state machine, frozen in SPEC and written to spec.json before any outcome is computed.
Detection never reads forward prices; forward returns are attached afterwards.

    python scripts/analysis/pnp_bar_census.py --csv data/XAUUSD_M15.csv --scope month --month 2025-07 \
        --out results/pnp_bar_census_2025_07
    python scripts/analysis/pnp_bar_census.py ... --scope full --month 2025-07 --out results/pnp_bar_census_full
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

SPEC = {
    "features": ["trend_bias", "ema_spread", "macd_line", "momentum_score", "macd_hist", "trend_strength", "rsi_14"],
    "feature_sign": "sign(x); rsi_14 uses sign(rsi_14 - 50); zero values are skipped (state unchanged)",
    "name_mapping": "macd_hist_z, trend_strength_z, fvg_distance are not canonical features; macd_hist, trend_strength used",
    "patterns": {"PNP": "confirmed + run (>=2 bars), then - run (2..10 bars), then + run; event on the bar the final + run reaches 2 bars",
                 "NPN": "mirror: - run, + run, - run (the short-aligned counterpart)"},
    "phase_limits": {"min_run": 2, "max_middle_run": 10, "max_confirm_span_bars_from_middle_start": 12},
    "refractory_bars": 8,
    "refractory_note": "events of the same feature/pattern within 8 bars of the previous event are one episode and are not counted again",
    "gap_rule": "detector state resets on any gap > 15 minutes between consecutive bars (weekend, daily break, data holes)",
    "eligible_bar": "bar inside the scope whose 7 feature values are finite (pipeline warm-up already removed)",
    "horizons_bars": [1, 4, 8, 16],
    "forward_return": "10000 * ln(close[t+k] / close[t]) in bps, dropped if timestamp[t+k]-timestamp[t] != 15min*k; aligned = sign_of_final_phase * return",
    "episode_groups": "events from any features within +/-4 bars are grouped into one cross-feature episode group",
    "null": "random-timing null: 5000 draws of the same number of eligible bars with the observed final-phase signs shuffled; two-sided p of mean aligned return",
    "time_structure": "calendar day, hour of day, minute of hour, M15 bar position (0..95); chi-square vs exposure (eligible bars share), Monte-Carlo p (5000)",
    "multiple_testing": "Benjamini-Hochberg over feature x pattern x horizon",
    "discovery_month_default": "2025-07 (chosen in advance by availability of data/XAUUSD_M15_2025-07.csv; the month was used in earlier unrelated trace work, disclosed)",
    "scopes": "month = discovery only; full = discovery month, pre-discovery months and chronological holdout (bars after the discovery month)",
    "seed": 42,
}
H = SPEC["horizons_bars"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def detect(sign: np.ndarray, gap_break: np.ndarray, a: int, min_run=2, max_mid=10, max_span=12, refractory=8):
    """Streaming detector for pattern a,-a,a (a=+1 PNP, a=-1 NPN).  Returns list of dicts.

    gap_break[i] True means a gap precedes bar i (state reset).  Uses only bars <= i at step i.
    """
    ev = []
    runs: list[list[int]] = []  # completed runs [sign, start, length]
    cur_s, cur_start, cur_len = 0, 0, 0
    last_ev = -10**9
    for i in range(len(sign)):
        if gap_break[i]:
            runs, cur_s, cur_start, cur_len = [], 0, i, 0
        s = int(sign[i])
        if s == 0:
            continue
        if s == cur_s:
            cur_len += 1
        else:
            if cur_s != 0:
                runs.append([cur_s, cur_start, cur_len])
                runs = runs[-3:]
            cur_s, cur_start, cur_len = s, i, 1
        if cur_s == a and cur_len == min_run and len(runs) >= 2:
            mid, first = runs[-1], runs[-2]
            if (mid[0] == -a and first[0] == a and first[2] >= min_run and min_run <= mid[2] <= max_mid
                    and (i - mid[1]) <= max_span and i - last_ev >= refractory):
                ev.append(dict(confirm_idx=i, p1_len=first[2], n_len=mid[2], n_start=mid[1], p2_start=cur_start,
                               span_from_mid=i - mid[1], sign=a))
                last_ev = i
    return ev


def bh(p):
    p = np.asarray(p, float); q = np.full_like(p, np.nan); ok = ~np.isnan(p)
    if not ok.any():
        return q
    idx = np.argsort(p[ok]); pm = p[ok][idx]; m = len(pm)
    adj = np.minimum.accumulate((pm * m / (np.arange(m) + 1))[::-1])[::-1]
    o = np.empty(m); o[idx] = np.minimum(adj, 1); q[ok] = o
    return q


def chi_mc(counts, exposure, rng, n=5000):
    counts = np.asarray(counts, float); exposure = np.asarray(exposure, float)
    tot = int(counts.sum())
    if tot == 0 or exposure.sum() == 0:
        return float("nan"), float("nan")
    pr = exposure / exposure.sum(); exp = pr * tot
    m = exp > 0
    stat = float((((counts - exp) ** 2)[m] / exp[m]).sum())
    sims = rng.multinomial(tot, pr, size=n)
    s = (((sims - exp) ** 2)[:, m] / exp[m]).sum(axis=1)
    return stat, float(((s >= stat - 1e-12).sum() + 1) / (n + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--month", default="2025-07"); ap.add_argument("--scope", choices=["month", "full"], default="month")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    spec_txt = json.dumps(SPEC, indent=2, sort_keys=True); (out / "spec.json").write_text(spec_txt)
    rng = np.random.default_rng(SPEC["seed"])

    from features import feature_schema as fs
    from features.feature_pipeline import FeaturePipeline
    raw = pd.read_csv(a.csv); raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    df, _ = FeaturePipeline(raw.copy()).run(); df = df.reset_index(drop=True); df["timestamp"] = pd.to_datetime(df["timestamp"])
    for f in SPEC["features"]:
        assert f in fs.CANONICAL_FEATURES, f
    ts = df["timestamp"]; close = df["close"].to_numpy(float)
    gap = np.zeros(len(df), bool); gap[1:] = (ts.diff().dt.total_seconds().to_numpy()[1:] > 15 * 60 + 1e-9)
    finite = np.all(np.isfinite(df[SPEC["features"]].to_numpy(float)), axis=1)
    month_start = pd.Timestamp(a.month + "-01"); month_end = month_start + pd.offsets.MonthBegin(1)
    in_month = ((ts >= month_start) & (ts < month_end)).to_numpy()
    scope_mask = in_month if a.scope == "month" else np.ones(len(df), bool)
    eligible = finite & scope_mask
    period = np.where(ts < month_start, "pre_discovery", np.where(ts >= month_end, "holdout_after", "discovery")).astype(object)

    # forward returns (attached after detection)
    fwd = {}
    for k in H:
        r = np.full(len(df), np.nan)
        ok = np.zeros(len(df), bool)
        ok[:-k] = (ts.shift(-k) - ts).dt.total_seconds().to_numpy()[:-k] == 15 * 60 * k
        r[:-k] = np.where(ok[:-k], 1e4 * np.log(close[k:] / close[:-k]), np.nan)
        fwd[k] = r

    events = []
    for f in SPEC["features"]:
        v = df[f].to_numpy(float) - (50.0 if f == "rsi_14" else 0.0)
        s = np.sign(v).astype(int)
        for a_, name in ((1, "PNP"), (-1, "NPN")):
            for e in detect(s, gap, a_, **{"min_run": 2, "max_mid": 10, "max_span": 12, "refractory": 8}):
                i = e["confirm_idx"]
                if not eligible[i]:
                    continue
                row = dict(feature=f, pattern=name, confirm_ts=str(ts.iloc[i]), confirm_idx=i, period=period[i],
                           day=str(ts.iloc[i].date()), hour=int(ts.iloc[i].hour), minute=int(ts.iloc[i].minute),
                           bar_pos=int(ts.iloc[i].hour * 4 + ts.iloc[i].minute // 15), dow=int(ts.iloc[i].dayofweek),
                           month=str(ts.iloc[i])[:7], p1_len=e["p1_len"], n_len=e["n_len"],
                           p2_to_confirm=e["span_from_mid"] - e["n_len"] + 1, span_from_mid=e["span_from_mid"], sign=a_)
                for k in H:
                    r = fwd[k][i]
                    row[f"ret_{k}"] = None if np.isnan(r) else float(r)
                    row[f"aligned_{k}"] = None if np.isnan(r) else float(a_ * r)
                events.append(row)
    E = pd.DataFrame(events)
    E.to_csv(out / "events.csv", index=False)

    # episode groups across features (+/-4 bars)
    if len(E):
        idx = np.sort(E.confirm_idx.unique()); grp = 0; gid = {}
        prev = -10**9
        for j in idx:
            grp += (j - prev > 4); gid[j] = grp; prev = j
        E["group"] = E.confirm_idx.map(gid)
    n_elig = int(eligible.sum())

    # ---- summaries --------------------------------------------------------
    elig_ts = ts[eligible]
    summ = []
    base = {k: float(np.nanmean(fwd[k][eligible])) for k in H}
    for (f, p), g in E.groupby(["feature", "pattern"]) if len(E) else []:
        row = dict(feature=f, pattern=p, events=len(g), per_1000_bars=1000 * len(g) / max(n_elig, 1),
                   days_with_event=int(g.day.nunique()), median_p1=float(g.p1_len.median()), median_n=float(g.n_len.median()),
                   median_span=float(g.span_from_mid.median()))
        signs = g["sign"].to_numpy()
        for k in H:
            x = g[f"aligned_{k}"].dropna().to_numpy(float)
            row[f"n_{k}"] = len(x)
            row[f"mean_aligned_{k}"] = float(x.mean()) if len(x) else float("nan")
            row[f"median_aligned_{k}"] = float(np.median(x)) if len(x) else float("nan")
            row[f"hit_{k}"] = float((x > 0).mean()) if len(x) else float("nan")
            pool = np.where(eligible & ~np.isnan(fwd[k]))[0]
            if len(x) >= 3 and len(pool):
                sg = np.array(signs[:len(x)])
                nulls = np.empty(5000)
                for t in range(5000):
                    pick = rng.choice(pool, len(x)); nulls[t] = (rng.permutation(sg) * fwd[k][pick]).mean()
                row[f"null_p_{k}"] = float(((np.abs(nulls) >= abs(x.mean()) - 1e-12).sum() + 1) / 5001)
            else:
                row[f"null_p_{k}"] = float("nan")
        summ.append(row)
    S = pd.DataFrame(summ)
    if len(S):
        for k in H:
            S[f"null_q_bh_{k}"] = bh(S[f"null_p_{k}"].to_numpy())
        qcols = [f"null_p_{k}" for k in H]
        allp = S[qcols].to_numpy().ravel(); allq = bh(allp)
        S["min_null_p"] = S[qcols].min(axis=1)
        S.attrs["global_q_min"] = float(np.nanmin(allq)) if np.isfinite(allq).any() else float("nan")
    S.to_csv(out / "summary.csv", index=False)

    # ---- time structure (discovery scope events only for month scope; whole scope for full) -------
    ts_struct = []
    el = pd.DataFrame({"ts": elig_ts}); el["day"] = el.ts.dt.date.astype(str); el["hour"] = el.ts.dt.hour
    el["minute"] = el.ts.dt.minute; el["bar_pos"] = el.ts.dt.hour * 4 + el.ts.dt.minute // 15
    for key, bins in (("hour", range(24)), ("minute", (0, 15, 30, 45)), ("bar_pos", range(96)), ("day", None)):
        for (f, p), g in (E.groupby(["feature", "pattern"]) if len(E) else []):
            bl = sorted(el[key].unique()) if bins is None else list(bins)
            cnt = [int((g[key] == b).sum()) for b in bl]; ex = [int((el[key] == b).sum()) for b in bl]
            chi, pv = chi_mc(cnt, ex, rng, 3000)
            ts_struct.append(dict(feature=f, pattern=p, dimension=key, bins=len(bl), events=int(sum(cnt)), chi2=chi, mc_p=pv,
                                  max_bin_share=float(max(cnt) / max(sum(cnt), 1))))
    TS = pd.DataFrame(ts_struct); TS.to_csv(out / "time_structure.csv", index=False)
    if len(E):
        E.groupby(["month", "feature", "pattern"]).size().rename("events").reset_index().to_csv(out / "events_by_month.csv", index=False)
        bars_m = pd.Series(ts[eligible].astype(str).str[:7]).value_counts().rename("eligible_bars")
        bars_m.to_csv(out / "eligible_bars_by_month.csv")
        by_period = []
        for (f, p, per), g in E.groupby(["feature", "pattern", "period"]):
            row = dict(feature=f, pattern=p, period=per, events=len(g), eligible_bars=int((period[eligible] == per).sum()))
            for k in H:
                x = g[f"aligned_{k}"].dropna(); row[f"mean_aligned_{k}"] = float(x.mean()) if len(x) else float("nan"); row[f"n_{k}"] = len(x)
            by_period.append(row)
        pd.DataFrame(by_period).to_csv(out / "by_period.csv", index=False)
        # per-month aligned mean at 8 bars for stability
        mm = E.dropna(subset=["aligned_8"]).groupby(["feature", "pattern", "month"]).aligned_8.agg(["count", "mean"]).reset_index()
        mm.to_csv(out / "monthly_aligned_8.csv", index=False)

    manifest = {
        "command": f"python scripts/analysis/pnp_bar_census.py --csv {a.csv} --scope {a.scope} --month {a.month} --out {a.out}",
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "ohlcv_sha256": sha(a.csv), "spec_sha256": hashlib.sha256(spec_txt.encode()).hexdigest(),
        "pipeline_sha256": sha(ROOT / "src/features/feature_pipeline.py"),
        "schema": {"count": len(fs.CANONICAL_FEATURES), "checksum": fs.GAUSSIAN_SCHEMA.checksum, "version": fs.GAUSSIAN_SCHEMA.version},
        "scope": a.scope, "month": a.month, "eligible_bars": n_elig, "events_total": int(len(E)),
        "episode_groups": int(E.group.nunique()) if len(E) else 0, "gap_resets": int(gap[scope_mask].sum()),
        "unconditional_mean_return_bps": base,
        "global_min_bh_q": S.attrs.get("global_q_min") if len(S) else None,
        "range": [str(ts[eligible].min()), str(ts[eligible].max())],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    pd.set_option("display.width", 220)
    print(json.dumps({k: manifest[k] for k in ("scope", "eligible_bars", "events_total", "episode_groups", "gap_resets", "global_min_bh_q")}, default=str))
    if len(S):
        print(S[["feature", "pattern", "events", "per_1000_bars", "days_with_event", "median_n", "median_span", "mean_aligned_8", "null_p_8"]].round(3).to_string())


if __name__ == "__main__":
    main()
