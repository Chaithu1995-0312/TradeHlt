"""Profitable-zone feature-transition research (read-only; writes only under --out).

Pre-registered rules live in SPEC below and are written to spec.json (with its hash)
BEFORE any outcome-conditioned statistic is computed.  Nothing in src/, configs/ or
models/ is touched.

    python scripts/analysis/feature_transition_research.py \
        --csv data/XAUUSD_M15.csv --trades <run>/XAUUSD_trades.csv \
        --out results/feature_transition_research
"""
from __future__ import annotations

import argparse
import csv
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

# ----------------------------------------------------------------------------
# Pre-registered specification (fixed before measuring)
# ----------------------------------------------------------------------------
SPEC = {
    "windows": [8, 12, 16, 20],
    "phases": {
        "before": "bars [entry-W+1 .. entry] (entry bar close is when the entry is decided; causal)",
        "during": "bars [entry+1 .. entry+W], only if the trade is still open through entry+W (descriptive only)",
        "after": "bars [exit+1 .. exit+W] (descriptive / exit research only)",
    },
    "sign_rule": {
        "signed_feature": "min<0<max over the post-warm-up corpus (property of the feature, not of outcomes) -> sign(x_t)",
        "non_signed_feature": "sign(x_t - trailing median of previous 96 bars, current excluded); equal -> 0",
        "zeros_dropped": True,
        "min_run_len": 2,
        "run_cleanup": "consecutive equal signs form a run; runs shorter than min_run_len are removed; adjacent equal runs merged",
    },
    "patterns": {
        "NPN": "three consecutive runs (-,+,-) anywhere in the window; transition bar = start of 3rd run",
        "PNP": "three consecutive runs (+,-,+) anywhere in the window; transition bar = start of 3rd run",
        "NP": "window's last two runs are (-,+) ('other': single upward crossing); transition bar = start of last run",
        "PN": "window's last two runs are (+,-) ('other': single downward crossing); transition bar = start of last run",
    },
    "groups": {
        "profitable": "pnl_rr_net > 0",
        "losing": "pnl_rr_net <= 0",
        "mfe_1r": "MFE >= 1.0R (R = |entry_fill - sl|; MFE/MAE from highs/lows of bars entry+1..exit-1, plus the exit bar in full for non-stop/non-TP exits, or only the realised exit excursion for STOPPED/TP exits)",
        "no_mfe_1r": "MFE < 1.0R",
        "gaveback": "MFE >= 1.0R and (MFE - exit_favorable_R) >= 0.5R",
        "held": "MFE >= 1.0R and (MFE - exit_favorable_R) < 0.5R",
    },
    "comparisons": {
        "win_vs_loss": ["profitable", "losing"],
        "mfe1r_vs_not": ["mfe_1r", "no_mfe_1r"],
        "gaveback_vs_held": ["gaveback", "held"],
    },
    "features_used": "all names in CANONICAL_FEATURES, raw values (not direction-adjusted), exact order",
    "direction_note": "features are NOT sign-flipped for SHORT trades (semantics preserved)",
    "oos": "chronological split of trades by entry time: first 70% (floor) = train, rest = test; candidates selected on train only: n_with>=2, n_without>=2 and |dNetR|>=0.10",
    "tests": {
        "prevalence": "Fisher exact (group A vs B), risk difference",
        "outcome_effect": "mean net R with vs without pattern; Hedges g; bootstrap 95% CI (2000); permutation p (5000, seed 42)",
        "multiple_testing": "Benjamini-Hochberg q over every row with n_with>=2 and n_without>=2; Bonferroni threshold reported",
        "baseline": "pattern base rate over corpus windows (stride 4); exact binomial test of trade-window frequency against it",
        "null": "label permutation (above)",
        "min_n": 2,
    },
    "seed": 42,
}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ----------------------------------------------------------------------------
# Transition detection
# ----------------------------------------------------------------------------
def clean_runs(signs, min_len: int = 2):
    """signs: iterable of -1/0/1 -> list of (sign, start_offset) after dropping 0s,
    removing runs shorter than min_len and merging adjacent equal runs."""
    runs: list[list[int]] = []  # [sign, start, length]
    for off, s in enumerate(signs):
        if s == 0:
            continue
        if runs and runs[-1][0] == s and runs[-1][1] + runs[-1][2] == off:
            runs[-1][2] += 1
        elif runs and runs[-1][0] == s:
            # same sign separated only by dropped zeros -> same run
            runs[-1][2] += (off - (runs[-1][1] + runs[-1][2])) + 1
        else:
            runs.append([s, off, 1])
    kept = [r for r in runs if r[2] >= min_len]
    merged: list[list[int]] = []
    for r in kept:
        if merged and merged[-1][0] == r[0]:
            merged[-1][2] = r[1] + r[2] - merged[-1][1]
        else:
            merged.append(list(r))
    return [(r[0], r[1]) for r in merged]


def detect_patterns(signs, min_len: int = 2) -> dict:
    """-> {pattern: transition_offset or None} for NPN, PNP, NP, PN."""
    rs = clean_runs(signs, min_len)
    out = {"NPN": None, "PNP": None, "NP": None, "PN": None}
    for i in range(len(rs) - 2):
        a, b, c = rs[i][0], rs[i + 1][0], rs[i + 2][0]
        if (a, b, c) == (-1, 1, -1) and out["NPN"] is None:
            out["NPN"] = rs[i + 2][1]
        if (a, b, c) == (1, -1, 1) and out["PNP"] is None:
            out["PNP"] = rs[i + 2][1]
    if len(rs) >= 2:
        if (rs[-2][0], rs[-1][0]) == (-1, 1):
            out["NP"] = rs[-1][1]
        if (rs[-2][0], rs[-1][0]) == (1, -1):
            out["PN"] = rs[-1][1]
    return out


# ----------------------------------------------------------------------------
# Statistics helpers
# ----------------------------------------------------------------------------
def fisher_exact_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact for [[a,b],[c,d]] (sum of tables with prob <= observed)."""
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def pr(x):
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)

    lo, hi = max(0, c1 - r2), min(r1, c1)
    obs = pr(a)
    return float(min(1.0, sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= obs * (1 + 1e-9))))


def binom_two_sided(k: int, n: int, p: float) -> float:
    """Exact two-sided binomial test (sum of outcomes with prob <= observed)."""
    if n == 0:
        return float("nan")
    p = min(max(p, 1e-12), 1 - 1e-12)

    def pm(x):
        return math.comb(n, x) * p ** x * (1 - p) ** (n - x)

    obs = pm(k)
    return float(min(1.0, sum(pm(x) for x in range(n + 1) if pm(x) <= obs * (1 + 1e-9))))


def hedges_g(x, y) -> float:
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return float("nan")
    sp = math.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    if sp == 0:
        return float("nan")
    j = 1 - 3 / (4 * (nx + ny) - 9)
    return float(j * (np.mean(x) - np.mean(y)) / sp)


def boot_ci(x, y, rng, n=2000):
    if len(x) < 2 or len(y) < 2:
        return (float("nan"), float("nan"))
    d = [rng.choice(x, len(x)).mean() - rng.choice(y, len(y)).mean() for _ in range(n)]
    return (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)))


def perm_p(x, y, rng, n=5000) -> float:
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    pooled = np.concatenate([x, y])
    obs = abs(np.mean(x) - np.mean(y))
    cnt = 0
    for _ in range(n):
        rng.shuffle(pooled)
        if abs(pooled[: len(x)].mean() - pooled[len(x):].mean()) >= obs - 1e-12:
            cnt += 1
    return (cnt + 1) / (n + 1)


def bh_q(pvals):
    p = np.array(pvals, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    if ok.sum() == 0:
        return q
    idx = np.argsort(p[ok])
    pm = p[ok][idx]
    m = len(pm)
    adj = np.minimum.accumulate((pm * m / (np.arange(m) + 1))[::-1])[::-1]
    out = np.empty(m)
    out[idx] = np.minimum(adj, 1.0)
    q[ok] = out
    return q


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--trades", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # ---- schema authority ---------------------------------------------------
    from features import feature_schema as fs
    from features.dataset_builder import CANONICAL_FEATURE_ORDER
    from features.feature_pipeline import FeaturePipeline
    feats = list(fs.CANONICAL_FEATURES)
    schema = {
        "source_file": "src/features/feature_schema.py",
        "authoritative": "CANONICAL_FEATURES (35, ordered); GAUSSIAN_SCHEMA/TRADENET_SCHEMA are built from it",
        "feature_count": len(feats),
        "ordered_features": feats,
        "schema_object_version": fs.GAUSSIAN_SCHEMA.version,
        "schema_object_checksum": fs.GAUSSIAN_SCHEMA.checksum,
        "names_only_SCHEMA_HASH": fs.SCHEMA_HASH,
        "module_SCHEMA_VERSION": str(fs.SCHEMA_VERSION),
        "dataset_builder_order_equal": feats == list(CANONICAL_FEATURE_ORDER),
        "model_export_format.json": None,
        "discrepancies": [],
    }
    mx = json.loads((ROOT / "model_export_format.json").read_text())
    schema["model_export_format.json"] = {
        "schema_version": mx.get("schema_version"), "input_dim": mx.get("input_dim"),
        "feature_order_equal": mx.get("feature_order") == feats,
    }
    schema["discrepancies"] = [
        f"version labels disagree: module SCHEMA_VERSION={fs.SCHEMA_VERSION}, SchemaObject.version={fs.GAUSSIAN_SCHEMA.version}, model_export_format schema_version={mx.get('schema_version')}",
        "two incompatible hashes: names-only SCHEMA_HASH vs SchemaObject.checksum (md5 of json.dumps(feature_schema))",
        "feature_schema.FEATURE_SCHEMA (legacy 24-key BitNet input dict) is a different structure from CANONICAL_FEATURES",
        "SESSION_MAP in feature_schema disagrees with pipeline session encoding (hour<8->0, <16->1, else 2); pipeline values are used here",
    ]
    cfgp = ROOT / "configs/production/v1_multi_2026_03.json"
    manifest = {
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
        "command": f"python scripts/analysis/feature_transition_research.py --csv {a.csv} --trades {a.trades} --out {a.out}",
        "ohlcv_csv": a.csv, "ohlcv_sha256": sha256_file(Path(a.csv)),
        "trades_csv": a.trades, "trades_sha256": sha256_file(Path(a.trades)),
        "production_config": str(cfgp.relative_to(ROOT)), "production_config_sha256": sha256_file(cfgp),
        "feature_pipeline_sha256": sha256_file(ROOT / "src/features/feature_pipeline.py"),
        "structure_mode": "causal_v2", "schema": schema,
    }
    spec_txt = json.dumps(SPEC, indent=2, sort_keys=True)
    (out / "spec.json").write_text(spec_txt)
    manifest["spec_sha256"] = hashlib.sha256(spec_txt.encode()).hexdigest()

    # ---- data ---------------------------------------------------------------
    raw = pd.read_csv(a.csv)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    df, _ = FeaturePipeline(raw.copy()).run()
    df = df.reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    assert list(feats) == [c for c in feats if c in df.columns], "pipeline missing canonical columns"
    ts_idx = {t: i for i, t in enumerate(df["timestamp"])}
    manifest["corpus"] = {"raw_bars": len(raw), "feature_rows": len(df),
                          "range": [str(raw.timestamp.iloc[0]), str(raw.timestamp.iloc[-1])]}

    trades = sorted(csv.DictReader(open(a.trades, encoding="utf-8-sig")), key=lambda r: r["opened_at"])
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    rows_t = []
    for r in trades:
        i = ts_idx[pd.Timestamp(r["opened_at"])]
        e = ts_idx[pd.Timestamp(r["closed_at"])]
        d = 1 if r["direction"] == "LONG" else -1
        ef, slp, xf = float(r["entry_fill"]), float(r["sl"]), float(r["exit_fill"])
        Rd = abs(ef - slp)
        exit_fav = d * (xf - ef) / Rd
        # exit bar: for STOPPED/TP exits the bar's range after the fill is unknowable (trade closed), so the exit bar
        # contributes only the realised exit excursion; other exits use the full bar.
        full_exit_bar = not (r["exit_reason"] == "STOPPED" or r["exit_reason"].startswith("TP"))
        end = e + 1 if full_exit_bar else e
        seg_h, seg_l = hi[i + 1:end], lo[i + 1:end]
        if len(seg_h) == 0:
            fav = np.array([0.0]); adv = np.array([0.0])
        elif d == 1:
            fav, adv = (seg_h - ef) / Rd, (ef - seg_l) / Rd
        else:
            fav, adv = (ef - seg_l) / Rd, (seg_h - ef) / Rd
        mfe, mae = float(max(fav.max(), 0)), float(max(adv.max(), 0))
        if not full_exit_bar:
            mfe, mae = max(mfe, exit_fav), max(mae, -exit_fav)
        mfe_bar = int(np.argmax(fav)) + 1 if len(seg_h) else 0
        net = float(r["pnl_rr_net"])
        rows_t.append(dict(
            trade_id=r["trade_id"], direction=r["direction"], opened_at=r["opened_at"], closed_at=r["closed_at"],
            entry_idx=i, exit_idx=e, duration=e - i, exit_reason=r["exit_reason"], net_R=net, mfe_R=mfe, mae_R=mae,
            mfe_bar_rel_entry=mfe_bar, exit_fav_R=float(exit_fav),
            profitable=net > 0, mfe_1r=mfe >= 1.0,
            gaveback=(mfe >= 1.0 and (mfe - exit_fav) >= 0.5), held=(mfe >= 1.0 and (mfe - exit_fav) < 0.5),
            entry_close_matches_entry_raw=bool(abs(float(df["close"].iloc[i]) - float(r["entry_raw"])) < 1e-6),
        ))
    T = pd.DataFrame(rows_t)
    n_tr = len(T)
    n_train = int(n_tr * 0.7)
    T["split"] = ["train"] * n_train + ["test"] * (n_tr - n_train)
    # overlapping episodes
    ep = [(r.entry_idx - 20, r.exit_idx + 20) for r in T.itertuples()]
    manifest["overlapping_episode_pairs"] = sum(1 for x in range(n_tr) for y in range(x + 1, n_tr)
                                                if ep[x][0] <= ep[y][1] and ep[y][0] <= ep[x][1])
    # integrity: batch snapshot equals trades.csv snapshot
    chk = []
    for r, tr in zip(T.itertuples(), trades):
        for f in ("rsi_14", "atr", "volatility_regime", "macd_hist"):
            chk.append(abs(float(df[f].iloc[r.entry_idx]) - float(tr[f])) <= 1e-4 * max(1.0, abs(float(tr[f]))))  # trades.csv holds float32-rounded values
    manifest["snapshot_integrity_all_equal"] = bool(all(chk))
    T.to_csv(out / "trades.csv", index=False)

    # ---- signs --------------------------------------------------------------
    signed = {}
    sign_arr = {}
    for f in feats:
        v = df[f].to_numpy(float)
        signed[f] = bool(np.nanmin(v) < 0 < np.nanmax(v))
        if signed[f]:
            s = np.sign(np.nan_to_num(v, nan=0.0))
        else:
            med = pd.Series(v).rolling(96, min_periods=96).median().shift(1).to_numpy()
            s = np.sign(np.nan_to_num(v - med, nan=0.0))
        sign_arr[f] = s.astype(int)
    manifest["signed_features"] = [f for f in feats if signed[f]]
    manifest["non_signed_features"] = [f for f in feats if not signed[f]]

    # ---- corpus base rates (stride 4) ---------------------------------------
    W_list = SPEC["windows"]
    start = 96 + max(W_list)
    base = {}
    pats = list(SPEC["patterns"])
    for f in feats:
        s = sign_arr[f]
        for W in W_list:
            cnt = {p: 0 for p in pats}; n = 0
            for i in range(start, len(df), 4):
                r = detect_patterns(s[i - W + 1:i + 1])
                n += 1
                for p in pats:
                    cnt[p] += r[p] is not None
            for p in pats:
                base[(f, p, W)] = (cnt[p] / n, n)

    # ---- per-trade windows and traces ---------------------------------------
    hits = {}  # (f,p,phase,W) -> list of dict per trade (or None when incomplete)
    for f in feats:
        s = sign_arr[f]
        for W in W_list:
            for ph in ("before", "during", "after"):
                for tr in T.itertuples():
                    if ph == "before":
                        lo_i, hi_i = tr.entry_idx - W + 1, tr.entry_idx
                    elif ph == "during":
                        lo_i, hi_i = tr.entry_idx + 1, tr.entry_idx + W
                        if hi_i > tr.exit_idx:
                            hits[(f, ph, W, tr.trade_id)] = None
                            continue
                    else:
                        lo_i, hi_i = tr.exit_idx + 1, tr.exit_idx + W
                    if lo_i < 0 or hi_i >= len(df):
                        hits[(f, ph, W, tr.trade_id)] = None
                        continue
                    hits[(f, ph, W, tr.trade_id)] = (lo_i, detect_patterns(s[lo_i:hi_i + 1]))

    rng = np.random.default_rng(SPEC["seed"])
    rows = []
    group_masks = {
        "profitable": T.profitable.to_numpy(), "losing": ~T.profitable.to_numpy(),
        "mfe_1r": T.mfe_1r.to_numpy(), "no_mfe_1r": ~T.mfe_1r.to_numpy(),
        "gaveback": T.gaveback.to_numpy(), "held": T.held.to_numpy(),
    }
    net = T.net_R.to_numpy(float); mfe_a = T.mfe_R.to_numpy(float); mae_a = T.mae_R.to_numpy(float)
    dur = T.duration.to_numpy(float)
    train_mask = (T.split == "train").to_numpy()
    for f in feats:
        for p in pats:
            for ph in ("before", "during", "after"):
                for W in W_list:
                    elig = np.zeros(n_tr, bool); present = np.zeros(n_tr, bool)
                    trans_rel_entry = []; trans_rel_exit = []; trans_rel_mfe = []
                    for k, tr in enumerate(T.itertuples()):
                        h = hits[(f, ph, W, tr.trade_id)]
                        if h is None:
                            continue
                        elig[k] = True
                        lo_i, res = h
                        if res[p] is not None:
                            present[k] = True
                            bar = lo_i + res[p]
                            trans_rel_entry.append(bar - tr.entry_idx)
                            trans_rel_exit.append(bar - tr.exit_idx)
                            trans_rel_mfe.append(bar - (tr.entry_idx + tr.mfe_bar_rel_entry))
                    w_, wo_ = present & elig, (~present) & elig
                    nw, nwo = int(w_.sum()), int(wo_.sum())
                    def m(a_, mk):
                        return float(a_[mk].mean()) if mk.sum() else float("nan")
                    d_net = m(net, w_) - m(net, wo_) if nw and nwo else float("nan")
                    # train/test effect
                    def eff(mask_split):
                        a1, b1 = w_ & mask_split, wo_ & mask_split
                        return (m(net, a1) - m(net, b1)) if a1.sum() and b1.sum() else float("nan"), int(a1.sum()), int(b1.sum())
                    tr_eff, trw, trwo = eff(train_mask)
                    te_eff, tew, tewo = eff(~train_mask)
                    selected = bool(trw >= 2 and trwo >= 2 and abs(tr_eff) >= 0.10)
                    if not selected:
                        oos = "not_selected_on_train"
                    elif tew < 1 or tewo < 1 or math.isnan(te_eff):
                        oos = "test_not_evaluable"
                    else:
                        oos = "same_sign" if np.sign(te_eff) == np.sign(tr_eff) else "sign_flip"
                    bs, bn = base[(f, p, W)]
                    row = dict(
                        feature=f, signed=signed[f], family="zero_cross" if signed[f] else "median_relative",
                        pattern=p, phase=ph, window=W, causal_entry_time=(ph == "before"),
                        n_eval=int(elig.sum()), n_with=nw, n_without=nwo,
                        freq_with=(nw / int(elig.sum())) if elig.sum() else float("nan"),
                        corpus_base_rate=bs, corpus_windows=bn,
                        freq_vs_base_p=binom_two_sided(nw, int(elig.sum()), bs) if elig.sum() else float("nan"),
                        net_R_with=m(net, w_), net_R_without=m(net, wo_), d_net_R=d_net,
                        win_rate_with=m(T.profitable.to_numpy(float), w_), win_rate_without=m(T.profitable.to_numpy(float), wo_),
                        mfe_with=m(mfe_a, w_), mfe_without=m(mfe_a, wo_),
                        mae_with=m(mae_a, w_), mae_without=m(mae_a, wo_),
                        duration_with=m(dur, w_), duration_without=m(dur, wo_),
                        hedges_g=hedges_g(net[w_], net[wo_]) if nw >= 2 and nwo >= 2 else float("nan"),
                        trans_rel_entry_median=float(np.median(trans_rel_entry)) if trans_rel_entry else float("nan"),
                        trans_rel_exit_median=float(np.median(trans_rel_exit)) if trans_rel_exit else float("nan"),
                        trans_rel_mfe_median=float(np.median(trans_rel_mfe)) if trans_rel_mfe else float("nan"),
                        train_d_net_R=tr_eff, train_n_with=trw, train_n_without=trwo,
                        test_d_net_R=te_eff, test_n_with=tew, test_n_without=tewo,
                        selected_on_train=selected, oos_status=oos,
                    )
                    if nw >= 2 and nwo >= 2:
                        lo_c, hi_c = boot_ci(net[w_], net[wo_], rng)
                        row.update(d_net_R_ci_lo=lo_c, d_net_R_ci_hi=hi_c, perm_p=perm_p(net[w_], net[wo_], rng))
                    else:
                        row.update(d_net_R_ci_lo=float("nan"), d_net_R_ci_hi=float("nan"), perm_p=float("nan"))
                    for cname, (ga, gb) in SPEC["comparisons"].items():
                        A, B = group_masks[ga] & elig, group_masks[gb] & elig
                        kA, kB = int((A & present).sum()), int((B & present).sum())
                        nA, nB = int(A.sum()), int(B.sum())
                        row[f"{cname}_nA"], row[f"{cname}_nB"] = nA, nB
                        row[f"{cname}_kA"], row[f"{cname}_kB"] = kA, kB
                        row[f"{cname}_rateA"] = kA / nA if nA else float("nan")
                        row[f"{cname}_rateB"] = kB / nB if nB else float("nan")
                        row[f"{cname}_risk_diff"] = (kA / nA - kB / nB) if nA and nB else float("nan")
                        row[f"{cname}_fisher_p"] = fisher_exact_p(kA, nA - kA, kB, nB - kB) if nA and nB else float("nan")
                    row["testable"] = bool(nw >= 2 and nwo >= 2)
                    rows.append(row)
    R = pd.DataFrame(rows)
    R["perm_q_bh"] = bh_q(R["perm_p"].to_numpy())
    for c in SPEC["comparisons"]:
        R[f"{c}_fisher_q_bh"] = bh_q(R[f"{c}_fisher_p"].to_numpy())
    n_testable = int(R.perm_p.notna().sum())
    manifest["tests"] = {"rows_total": len(R), "rows_testable": n_testable,
                         "bonferroni_alpha_0.05": (0.05 / n_testable) if n_testable else None,
                         "min_perm_p_possible": 1 / 5001,
                         "rows_perm_q_lt_0.10": int((R.perm_q_bh < 0.10).sum()),
                         "rows_selected_on_train": int(R.selected_on_train.sum()),
                         "selected_oos_same_sign": int((R.oos_status == "same_sign").sum()),
                         "selected_oos_sign_flip": int((R.oos_status == "sign_flip").sum()),
                         "selected_test_not_evaluable": int((R.oos_status == "test_not_evaluable").sum())}
    # ---- traces -------------------------------------------------------------
    traces = {}
    for tr in T.itertuples():
        a0, b0 = max(0, tr.entry_idx - 20), min(len(df) - 1, tr.exit_idx + 20)
        traces[tr.trade_id] = {
            "trade": {k: (v.item() if hasattr(v, "item") else v) for k, v in T[T.trade_id == tr.trade_id].iloc[0].to_dict().items()},
            "bar_offsets_rel_entry": list(range(a0 - tr.entry_idx, b0 - tr.entry_idx + 1)),
            "timestamps": [str(t) for t in df["timestamp"].iloc[a0:b0 + 1]],
            "features": {f: [None if not np.isfinite(x) else round(float(x), 8) for x in df[f].iloc[a0:b0 + 1]] for f in feats},
        }
    R.to_csv(out / "transitions.csv", index=False)
    R.replace({np.nan: None}).to_json(out / "transitions.json", orient="records")
    (out / "traces.json").write_text(json.dumps(traces))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps({"manifest": manifest["tests"], "trades": n_tr, "snapshot_ok": manifest["snapshot_integrity_all_equal"],
                      "overlaps": manifest["overlapping_episode_pairs"]}, indent=2))


if __name__ == "__main__":
    main()
