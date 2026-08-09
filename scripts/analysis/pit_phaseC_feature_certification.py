"""
pit_phaseC_feature_certification.py — PIT Phase C: empirical certification of ALL 38
canonical features (READ-ONLY).

PIT Phases A/B fixed the two known-leaking families (FC1-A centered swings → causal
delayed publication; FC1-D volatility_regime → rolling causal). The surface-closure audit
is a STATIC synthesis; this probe supplies the missing EMPIRICAL half over the whole
vector, per the review sequence ("audit remaining configured canonical features for
prefix invariance, future dependence, global-fit dependence, warmup, missing-value
behavior"):

  1. PREFIX INVARIANCE (the decisive property): run FeaturePipeline on the full corpus
     and on strict prefixes; on shared timestamps every production column must be
     IDENTICAL — post-FC1-A/FC1-D, bar t may use only information ≤ t, so the prefix run
     possesses everything needed. NO tail exclusion is granted to production columns.
  2. WARMUP / MISSING-VALUE census: first-valid index and NaN policy per feature
     (pre-finalize), plus what finalize() drops.
  3. GLOBAL-FIT dependence: AST scan of feature_pipeline.py for full-frame ops
     (rank(pct=True) without rolling/expanding, whole-frame quantile/mean) feeding
     columns; empirical prefix harness is the ground truth, the scan localizes.

Census/lint-clean by construction: the probe computes NO feature math — it only runs the
real pipeline twice and compares columns.

Verdicts per feature: PREFIX_INVARIANT · VARIANT (any shared-timestamp mismatch — STOP
condition per the Phase-C plan: report, do not remediate).

Usage: python scripts/analysis/pit_phaseC_feature_certification.py [--symbol BNBUSDT]
       [--limit 30000] [--cuts 0.5,0.75]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

_GOV = _ROOT / "docs" / "governance"
_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── corpus ───────────────────────────────────────────────────────────────────

def _load_corpus(symbol: str, limit: int) -> pd.DataFrame:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    df.columns = [c.strip().lower() for c in df.columns]
    if limit:
        df = df.head(limit).copy()
    return df


def _synthetic(n: int = 1200, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def _run_pipeline(raw: pd.DataFrame) -> pd.DataFrame:
    feat_df, _vectors = FeaturePipeline(raw.copy()).run()
    ts_col = "timestamp" if "timestamp" in feat_df.columns else None
    if ts_col is None:
        raise RuntimeError("finalized frame lacks timestamp column")
    return feat_df.set_index(ts_col)


# ── 1. prefix invariance ─────────────────────────────────────────────────────

def prefix_invariance(raw: pd.DataFrame, cuts: list[float], corpus_label: str) -> dict:
    full = _run_pipeline(raw)
    per_feature: dict[str, dict] = {
        n: {"verdict": "PREFIX_INVARIANT", "mismatch_bars": 0, "cuts_checked": 0,
            "worst_example": None}
        for n in CANONICAL_FEATURES
    }
    cut_rows = []
    for frac in cuts:
        n_cut = int(len(raw) * frac)
        pref = _run_pipeline(raw.head(n_cut))
        shared = pref.index.intersection(full.index)
        cut_rows.append({"cut_fraction": frac, "cut_bars": n_cut, "shared_rows": len(shared)})
        for name in CANONICAL_FEATURES:
            a = pref.loc[shared, name].to_numpy()
            b = full.loc[shared, name].to_numpy()
            # exact equality with NaN==NaN (production columns are typed/deterministic)
            eq = (a == b) | (pd.isna(a) & pd.isna(b))
            n_bad = int((~eq).sum())
            rec = per_feature[name]
            rec["cuts_checked"] += 1
            if n_bad:
                rec["verdict"] = "VARIANT"
                rec["mismatch_bars"] += n_bad
                if rec["worst_example"] is None:
                    i = int(np.argmax(~eq))
                    rec["worst_example"] = {
                        "cut_fraction": frac,
                        "timestamp": str(shared[i]),
                        "prefix_value": None if pd.isna(a[i]) else float(a[i]),
                        "full_value": None if pd.isna(b[i]) else float(b[i]),
                    }
    variant = sorted(n for n, r in per_feature.items() if r["verdict"] == "VARIANT")
    return {"corpus": corpus_label, "bars": len(raw), "cuts": cut_rows,
            "per_feature": per_feature, "variant_features": variant,
            "all_prefix_invariant": not variant}


# ── 2. warmup / missing-value census ────────────────────────────────────────

def warmup_census(raw: pd.DataFrame) -> dict:
    p = FeaturePipeline(raw.copy())
    feat_df, _ = p.run()
    pre = p.df  # pre-finalize frame retained by the pipeline instance
    out: dict[str, dict] = {}
    for name in CANONICAL_FEATURES:
        col = pre[name] if name in pre.columns else None
        if col is None:
            out[name] = {"present_pre_finalize": False}
            continue
        valid = col.notna()
        first_valid = int(valid.idxmax()) if valid.any() else None
        out[name] = {
            "present_pre_finalize": True,
            "first_valid_row": first_valid,
            "nan_rows_pre_finalize": int((~valid).sum()),
            "dtype": str(col.dtype),
        }
    return {
        "rows_pre_finalize": len(pre),
        "rows_post_finalize": len(feat_df),
        "rows_dropped_by_finalize": len(pre) - len(feat_df),
        "per_feature": out,
        "note": "finalize() dropna(subset=CANONICAL_FEATURES) removes warmup rows; a NaN "
                "policy is therefore a ROW-DROP policy for the production vector",
    }


# ── 3. global-fit dependence (AST localization; empirical truth is section 1) ─

def global_fit_scan() -> dict:
    src = (_ROOT / "src" / "features" / "feature_pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        leaf = node.func.attr
        if leaf not in ("rank", "quantile"):
            continue
        # walk the attribute/call chain looking for a windowing stage
        chain: list[str] = []
        cur = node.func.value
        while True:
            if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Attribute):
                chain.append(cur.func.attr)
                cur = cur.func.value
            elif isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            else:
                break
        windowed = any(c in ("rolling", "expanding", "groupby") for c in chain)
        hits.append({"line": node.lineno, "op": leaf,
                     "windowed": windowed, "chain": list(reversed(chain))})
    unwindowed = [h for h in hits if not h["windowed"]]
    return {
        "rank_quantile_sites": hits,
        "unwindowed_sites": unwindowed,
        "note": "unwindowed rank/quantile = full-frame fit. Post-FC1-D the only such site "
                "must feed research-only columns (volatility_regime_global_batch), never a "
                "production canonical column — section 1 is the empirical proof.",
    }


# ── report ───────────────────────────────────────────────────────────────────

def _to_md(rep: dict) -> str:
    lines = [
        "# PIT Phase C — Empirical 38-Feature Certification",
        "",
        f"_Generated {rep['generated_at']} · ACTIVE_VERSION={rep['active_version']} · read-only._",
        "",
        "## Verdict",
        "",
    ]
    ok = all(arm["all_prefix_invariant"] for arm in rep["prefix_invariance"])
    if ok:
        lines += [
            "**ALL 38 production canonical columns are PREFIX-INVARIANT** on every tested cut "
            "(real corpus + synthetic), with **zero tail exclusion** — bar *t* uses only "
            "information ≤ *t* across the entire production vector. Combined with the "
            "batch↔online structure parity tests (FC1-A) and the rolling-causal volregime "
            "bind (FC1-D), the canonical FeaturePipeline is certified **PIT-clean at the "
            "prefix-invariance level**.",
            "",
            "> SCOPE: this certifies temporal correctness (no future dependence, no global-fit "
            "> leakage into production columns). It is NOT an economic claim, does NOT "
            "> un-taint PIT_UNCLEAN artifacts (rr/zone), and grants no authority (§6.5).",
        ]
    else:
        bad = sorted({f for arm in rep["prefix_invariance"] for f in arm["variant_features"]})
        lines += [
            f"**STOP — {len(bad)} production column(s) are prefix-VARIANT: {bad}.** "
            "Per the Phase-C plan this is a stop condition: report, adjudicate, no auto-remediation.",
        ]
    for arm in rep["prefix_invariance"]:
        lines += [
            "",
            f"## Prefix invariance — {arm['corpus']} ({arm['bars']} bars)",
            "",
            f"- cuts: {[c['cut_fraction'] for c in arm['cuts']]} · shared rows/cut: "
            f"{[c['shared_rows'] for c in arm['cuts']]}",
            f"- variant features: **{arm['variant_features'] or 'none'}**",
        ]
    wc = rep["warmup_census"]
    lines += [
        "",
        "## Warmup / missing-value census",
        "",
        f"- pre-finalize rows: {wc['rows_pre_finalize']} · post: {wc['rows_post_finalize']} · "
        f"dropped: {wc['rows_dropped_by_finalize']}",
        f"- {wc['note']}",
        "",
        "## Global-fit scan (feature_pipeline.py)",
        "",
    ]
    gf = rep["global_fit_scan"]
    for h in gf["rank_quantile_sites"]:
        lines.append(f"- line {h['line']}: `.{h['op']}` chain={h['chain']} windowed={h['windowed']}")
    lines += ["", f"> {gf['note']}"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="PIT Phase C empirical feature certification (read-only).")
    ap.add_argument("--symbol", default="BNBUSDT")
    ap.add_argument("--limit", type=int, default=30000)
    ap.add_argument("--cuts", default="0.5,0.75")
    args = ap.parse_args()
    cuts = [float(x) for x in args.cuts.split(",")]

    active = (_ROOT / "configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip()

    real = _load_corpus(args.symbol, args.limit)
    synth = _synthetic()

    rep = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_version": active,
        "probe": "pit_phaseC_feature_certification",
        "behavior_changed": False,
        "prefix_invariance": [
            prefix_invariance(real, cuts, f"{args.symbol}_M15"),
            prefix_invariance(synth, [0.6], "synthetic_1200"),
        ],
        "warmup_census": warmup_census(real),
        "global_fit_scan": global_fit_scan(),
        "permanent_floor": "tests/test_pit_prefix_invariance.py",
    }

    stem = f"pit_phaseC_feature_certification-{_STAMP}"
    (_GOV / f"{stem}.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (_GOV / f"{stem}.md").write_text(_to_md(rep), encoding="utf-8")

    ok = all(arm["all_prefix_invariant"] for arm in rep["prefix_invariance"])
    print(f"probe → docs/governance/{stem}.{{json,md}}")
    for arm in rep["prefix_invariance"]:
        print(f"  {arm['corpus']}: all_prefix_invariant={arm['all_prefix_invariant']} "
              f"variant={arm['variant_features'] or '[]'}")
    print(f"  unwindowed rank/quantile sites: {len(rep['global_fit_scan']['unwindowed_sites'])}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
