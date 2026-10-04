# -*- coding: utf-8 -*-
"""analyze_trace_corpus.py — DESCRIPTIVE distributions over the Mathematical Trace Corpus (ERP).

Reads results/research/trace_corpus/xauusd/trace_corpus.jsonl and describes the 38-feature distributions
overall and segmented by outcome / timing / MFE, plus a family comparison. This asks "what mathematical
structures repeatedly FAIL?" — it is DESCRIPTIVE measurement: information, NOT authority (§6.5). It makes
NO edge/profit claim and emits no promote/verdict field. NaN-drop per feature (no imputation);
`n_valid` reported per cell.

Usage:
  python scripts/research/analyze_trace_corpus.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402
from utils.run_manifest import build_manifest, write_run  # noqa: E402

CORPUS_DIR = _ROOT / "results" / "research" / "trace_corpus" / "xauusd"
CORPUS = CORPUS_DIR / "trace_corpus.jsonl"
RUNS_DIR = _ROOT / "results" / "test_runs"
_FEAT_COLS = [f"feature_{n}" for n in CANONICAL_FEATURES]
_BANNER = "DESCRIPTIVE — information not authority (§6.5); no edge/profit claim; failure structure only."


def _stats(s: pd.Series) -> dict:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {"n_valid": 0}
    return {
        "n_valid": int(s.size), "mean": round(float(s.mean()), 6), "std": round(float(s.std()), 6),
        "p10": round(float(s.quantile(0.10)), 6), "p25": round(float(s.quantile(0.25)), 6),
        "p50": round(float(s.quantile(0.50)), 6), "p75": round(float(s.quantile(0.75)), 6),
        "p90": round(float(s.quantile(0.90)), 6),
    }


def _feature_stats(df: pd.DataFrame) -> dict:
    return {n: _stats(df[f"feature_{n}"]) for n in CANONICAL_FEATURES}


def analyze(df: pd.DataFrame) -> dict:
    out: dict = {"banner": _BANNER, "n_traces": int(len(df)),
                 "families": sorted(df["family"].unique().tolist()),
                 "outcome_counts": {k: int(v) for k, v in df["outcome"].value_counts().items()}}

    # per-feature distributions: overall + by outcome
    out["overall"] = _feature_stats(df)
    out["by_outcome"] = {oc: _feature_stats(g) for oc, g in df.groupby("outcome")}

    # loser timing terciles (among SL_HIT, by survival duration)
    losers = df[df["outcome"] == "SL_HIT"].copy()
    out["loser_timing"] = {}
    if len(losers) >= 6:
        losers["_dur_bucket"] = pd.qcut(losers["duration_candles"].rank(method="first"),
                                        3, labels=["fast", "mid", "slow"])
        out["loser_timing"] = {str(b): _feature_stats(g) for b, g in losers.groupby("_dur_bucket")}
        # near-miss: SL_HIT whose MFE reached the top quartile of loser MFE
        thr = float(losers["mfe"].quantile(0.75))
        near = losers[losers["mfe"] >= thr]
        out["near_miss_sl"] = {"mfe_p75_threshold": round(thr, 6), "n": int(len(near)),
                               "features": _feature_stats(near)}

    # MFE terciles (all trades)
    d = df.copy()
    out["mfe_segments"] = {}
    if len(d) >= 6:
        d["_mfe_bucket"] = pd.qcut(d["mfe"].rank(method="first"), 3, labels=["low", "mid", "high"])
        out["mfe_segments"] = {str(b): _feature_stats(g) for b, g in d.groupby("_mfe_bucket")}

    # family comparison — per-feature mean per family (spine n=1 flagged non-comparable)
    fam_means: dict = {}
    for fam, g in df.groupby("family"):
        fam_means[fam] = {"n": int(len(g)),
                          "comparable": bool(len(g) >= 30),
                          "feature_mean": {n: _stats(g[f"feature_{n}"]).get("mean") for n in CANONICAL_FEATURES}}
    out["family_comparison"] = fam_means
    return out


def _markdown(rep: dict) -> str:
    L = ["# XAUUSD Mathematical Trace Corpus — Descriptive Distributions", "",
         f"> {rep['banner']}", "",
         f"Traces: **{rep['n_traces']}** · families: {rep['families']} · outcomes: {rep['outcome_counts']}",
         "", "## Per-feature mean by outcome (SL_HIT vs TP_HIT vs TIMEOUT)", "",
         "| Feature | SL_HIT | TP_HIT | TIMEOUT | overall |", "|---|--:|--:|--:|--:|"]

    def _m(block, feat):
        v = block.get(feat, {}).get("mean")
        return "—" if v is None else f"{v:.4f}"

    for n in CANONICAL_FEATURES:
        L.append(f"| {n} | {_m(rep['by_outcome'].get('SL_HIT', {}), n)} "
                 f"| {_m(rep['by_outcome'].get('TP_HIT', {}), n)} "
                 f"| {_m(rep['by_outcome'].get('TIMEOUT', {}), n)} "
                 f"| {_m(rep['overall'], n)} |")

    L += ["", "## Family comparison (per-feature mean; spine n=1 non-comparable)", "",
          "| Feature | " + " | ".join(f"{f} (n={d['n']})" for f, d in rep["family_comparison"].items()) + " |",
          "|---|" + "|".join(["--:"] * len(rep["family_comparison"])) + "|"]
    for n in CANONICAL_FEATURES:
        cells = []
        for _f, d in rep["family_comparison"].items():
            v = d["feature_mean"].get(n)
            cells.append("—" if v is None else f"{v:.4f}")
        L.append(f"| {n} | " + " | ".join(cells) + " |")

    if rep.get("near_miss_sl"):
        nm = rep["near_miss_sl"]
        L += ["", f"## Near-miss losers (SL_HIT, MFE ≥ p75={nm['mfe_p75_threshold']:.4f}; n={nm['n']})",
              "", "Structures that ran favorably before stopping out — descriptive only.", ""]
    L += ["", f"> {rep['banner']}", ""]
    return "\n".join(L)


def main() -> int:
    if not CORPUS.exists():
        safe_print(f"No corpus at {CORPUS} — run build_trace_corpus.py first.")
        return 1
    df = pd.read_json(CORPUS, lines=True)
    rep = analyze(df)

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    (CORPUS_DIR / "distributions.json").write_text(json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")
    (CORPUS_DIR / "DISTRIBUTIONS.md").write_text(_markdown(rep), encoding="utf-8")

    manifest = build_manifest(
        command="python scripts/research/analyze_trace_corpus.py",
        argv=sys.argv,
        validation_lens="trace_corpus_descriptive",
        exit_model="intrabar_fixed", cost_model_bps=0,
        label_source="forward_walk_intrabar_fixed",
        instruments=["XAUUSD"], timeframe="M15",
        data_source="local_csv_mt5", network="none", dry_run=True,
        intended_work_item_id="WI-005",
    )
    write_run(RUNS_DIR / manifest["run_id"], manifest,
              {"descriptive_only": True, "non_promotable": True, "n_traces": rep["n_traces"],
               "outcome_counts": rep["outcome_counts"], "note": _BANNER})

    safe_print(f"Analyzed {rep['n_traces']} traces -> {CORPUS_DIR / 'DISTRIBUTIONS.md'}")
    safe_print(_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
