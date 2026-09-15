#!/usr/bin/env python3
"""Discriminator analysis on the four live engines (OBSERVATION_ONLY).

Uses the rr-slot A/B aligned dataset (results/research/ab_rr_slot_aligned_*.jsonl)
plus forward-return labels to answer: what actually drives the 0.6466 fused mean,
and does any engine (or fusion) discriminate next-bar direction?

Reports, per horizon H in {1,4}:
  * per-engine AUROC vs direction label + Spearman vs forward return
  * Pearson correlation matrix across the five inputs (incl. rr_trained reference)
  * Gaussian flatness (mean/std, corr w/ fused + label)
  * weight-sensitivity: fused distribution + AUROC under base / no-Gaussian
    (renormalized) / uniform / CRT-only weightings

No train. No promote. Research authority only.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]

COMPONENTS = ["crt", "gaussian", "zone_gate", "rr_live_polarity", "rr_trained"]
HORIZONS = (1, 4)


def _auroc(score: np.ndarray, y: np.ndarray) -> float | None:
    mask = y != 0
    s, t = score[mask], (y[mask] > 0).astype(int)
    if len(np.unique(t)) < 2:
        return None
    return float(roc_auc_score(t, s))


def _moments(x: np.ndarray) -> dict:
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "p50": float(np.median(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(spearmanr(a, b).statistic)


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(pearsonr(a, b)[0])


def _latest_aligned(dir_: Path) -> Path:
    cands = sorted(glob.glob(str(dir_ / "ab_rr_slot_aligned_XAUUSD_*.jsonl")))
    if not cands:
        raise FileNotFoundError(f"no ab_rr_slot_aligned_*.jsonl under {dir_}")
    return Path(cands[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "results" / "research"))
    ap.add_argument("--aligned", default=None, help="explicit aligned jsonl path")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    aligned = Path(args.aligned) if args.aligned else _latest_aligned(out_dir)

    rows = []
    with aligned.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    print(f"aligned source: {aligned.name}")
    print(f"rows: {len(df)}")

    # ── per-engine discrimination + Gaussian flatness ───────────────────────
    per_engine, gaussian = {}, {}
    for h in HORIZONS:
        col = f"fwd_ret_h{h}"
        sub = df.dropna(subset=[col])
        y = sub[col].to_numpy()
        per_engine[f"h{h}"] = {}
        for c in COMPONENTS:
            s = sub[c].to_numpy()
            per_engine[f"h{h}"][c] = {
                "auroc": _auroc(s, y),
                "spearman": _spearman(s, y),
            }

    g = df["gaussian"].to_numpy()
    gaussian["moments"] = _moments(g)
    gaussian["corr_vs_fused"] = _pearson(g, df["fused_base_live_rr"].to_numpy())
    gaussian["corr_vs_zone"] = _pearson(g, df["zone_gate"].to_numpy())
    gaussian["discrimination"] = {}
    for h in HORIZONS:
        col = f"fwd_ret_h{h}"
        m = df[col].notna().to_numpy()
        gv = g[m]
        yv = df[col].to_numpy()[m]
        gaussian["discrimination"][f"h{h}"] = {
            "auroc": _auroc(gv, yv),
            "spearman": _spearman(gv, yv),
        }

    # ── component correlation matrix (Pearson) ─────────────────────────────
    corr = {}
    for a in COMPONENTS:
        corr[a] = {}
        for b in COMPONENTS:
            corr[a][b] = _pearson(df[a].to_numpy(), df[b].to_numpy())

    result = {
        "aligned_source": aligned.name,
        "components": COMPONENTS,
        "per_engine": per_engine,
        "gaussian": gaussian,
        "correlation_matrix": corr,
    }

    # ── weight-sensitivity on the fused score (live rr slot) ───────────────
    crt = df["crt"].to_numpy()
    g = df["gaussian"].to_numpy()
    zone = df["zone_gate"].to_numpy()
    rr = df["rr_live_polarity"].to_numpy()
    base = df["fused_base_live_rr"].to_numpy()

    no_gauss = (0.4 * crt + 0.2 * zone + 0.2 * rr) / 0.8
    uniform = 0.25 * (crt + g + zone + rr)
    crt_only = crt
    variants = {
        "base_live_rr": base,
        "no_gaussian_renorm": no_gauss,
        "uniform_025": uniform,
        "crt_only": crt_only,
    }
    ws = {}
    for name, s in variants.items():
        entry = {"moments": _moments(s)}
        entry["discrimination"] = {}
        for h in HORIZONS:
            col = f"fwd_ret_h{h}"
            m = df[col].notna().to_numpy()
            sv = s[m]
            yv = df[col].to_numpy()[m]
            entry["discrimination"][f"h{h}"] = {
                "auroc": _auroc(sv, yv),
                "spearman": _spearman(sv, yv),
            }
        ws[name] = entry
    result["weight_sensitivity"] = ws

    ts_s = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_out = out_dir / f"discriminator_XAUUSD_{ts_s}.json"
    json_out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    # ── console summary ────────────────────────────────────────────────────
    print("\n== per-engine discrimination (AUROC / Spearman) ==")
    for h in HORIZONS:
        print(f"  h{h}:")
        for c in COMPONENTS:
            e = per_engine[f"h{h}"][c]
            a = e["auroc"]
            sp = e["spearman"]
            print(f"    {c:16s} auroc={a if a is None else round(a,4)} "
                  f"spearman={sp if sp is None else round(sp,4)}")
    print(f"\ngaussian: {json.dumps(gaussian['moments'])}")
    print(f"  corr gaussian->fused={gaussian['corr_vs_fused']:.4f}")
    print("\n== correlation matrix ==")
    for a in COMPONENTS:
        row = "  ".join(
            f"{b[0]}{corr[a][b]:.2f}" if corr[a][b] is not None else f"{b[0]} ."
            for b in COMPONENTS
        )
        print(f"  {a:16s} {row}")
    print("\n== weight sensitivity ==")
    for name, e in ws.items():
        m = e["moments"]
        h1 = e["discrimination"]["h1"]["auroc"]
        h4 = e["discrimination"]["h4"]["auroc"]
        print(f"  {name:18s} mean={m['mean']:.4f} std={m['std']:.4f} "
              f"auroc_h1={h1 if h1 is None else round(h1,4)} "
              f"auroc_h4={h4 if h4 is None else round(h4,4)}")

    print(f"\nwrote {json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

