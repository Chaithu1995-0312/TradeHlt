#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_h_g001_001_sweep_veto.py — Liquidity Sweep Veto on XAUUSD (H-G001-001 / 001b).

MEASURE-ONLY research. Does not edit production config, ontology, or FM math.

Baseline: ProductionSpineSource entries (CRT spine v2_multi_2026_04).
Treatment: same entries with liquidity_sweep≠0 bars vetoed (FM-058 presence veto).

H-G001-001  — default env BACKTEST_ENGINE_GATE (often fusion ON)
H-G001-001b — CRT-only lens: BACKTEST_ENGINE_GATE=0 (F-037 research spine)

Usage:
  python scripts/research/run_h_g001_001_sweep_veto.py
  python scripts/research/run_h_g001_001_sweep_veto.py --research-id H-G001-001b --engine-gate 0
  python scripts/research/run_h_g001_001_sweep_veto.py --permutations 200
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import research.controls  # noqa: F401,E402
import research.hypotheses  # noqa: F401,E402

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_STATUS,
    authority_status_note,
    guard_xauusd_csv_path,
)
from research.adapters.spine_signal_source import (  # noqa: E402
    ProductionSpineSource,
    SpineEntry,
)
from research.config import ResearchConfig  # noqa: E402
from research.costs import CostModel  # noqa: E402
from research.hypotheses.spine_hypothesis import SpineHypothesis  # noqa: E402
from research.measurement.metrics import EdgeAggregator  # noqa: E402
from research.provenance import provenance_block  # noqa: E402
from research.qualification import (  # noqa: E402
    BH_METHOD_VERSION,
    PERMUTATION_METHOD_VERSION,
    QUALIFICATION_VERSION,
    QualConfig,
    benjamini_hochberg,
    evaluate_pre_bh,
    finalize,
    _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY, register_hypothesis  # noqa: E402
from research.runner import HypothesisRunner  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402

INSTRUMENT = "XAUUSD"
SPINE_CONFIG = "configs/research/research_config_spine_xauusd.json"
PROD_VERSION = "v2_multi_2026_04"
# Defaults; overridden by CLI for H-G001-001b etc.
OUT_DIR = _ROOT / "research" / "H-G001-001"
RESEARCH_ID = "H-G001-001"


# ── sources ──────────────────────────────────────────────────────────────────

class FilteringSpineSource:
    """Spine entries filtered by a research-index predicate (treatment adapter)."""

    def __init__(
        self,
        base: ProductionSpineSource,
        keep_indices: set[int],
        *,
        label: str,
    ) -> None:
        self._base = base
        self._keep = keep_indices
        self.label = label
        self._cache: dict[str, dict[int, SpineEntry]] = {}

    def entries(self, instrument: str) -> dict[int, SpineEntry]:
        if instrument not in self._cache:
            raw = self._base.entries(instrument)
            self._cache[instrument] = {
                i: e for i, e in raw.items() if i in self._keep
            }
        return self._cache[instrument]


class _NamedSpineHypothesis:
    """Hypothesis protocol wrapper with injectable SpineHypothesis source."""

    family = "composite"

    def __init__(self, name: str, source, rationale: str):
        self.name = name
        self.economic_rationale = rationale
        self._inner = SpineHypothesis(source=source)

    def detect(self, window, features, ctx):
        return self._inner.detect(window, features, ctx)


def _load_ohlcv(csv_path: str):
    import pandas as pd

    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    # standard OHLCV names
    rename = {}
    for a, b in (
        ("time", "timestamp"),
        ("date", "timestamp"),
        ("datetime", "timestamp"),
    ):
        if a in df.columns and "timestamp" not in df.columns:
            rename[a] = "timestamp"
    df = df.rename(columns=rename)
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise KeyError(f"OHLCV missing {col} in {csv_path}")
    if "timestamp" not in df.columns:
        # synthetic index timestamps for alignment-only
        df["timestamp"] = pd.date_range("2000-01-01", periods=len(df), freq="15min")
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.reset_index(drop=True)


def _liquidity_sweep_series(csv_path: str) -> list[int]:
    """Row-preserving structure stage: length == candle stream length."""
    from features.feature_pipeline import FeaturePipeline

    df = _load_ohlcv(csv_path)
    fp = FeaturePipeline(df)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_structure_liquidity()
    return [int(v) for v in fp.df["liquidity_sweep"].tolist()]


def _corpus_span_months(csv_path: str) -> float:
    df = _load_ohlcv(csv_path)
    ts = df["timestamp"]
    if len(ts) < 2:
        return 1.0
    delta = ts.iloc[-1] - ts.iloc[0]
    days = max(delta.total_seconds() / 86400.0, 1.0)
    return max(days / 30.437, 1.0 / 30.437)


def _metrics_dict(report, months: float) -> dict[str, Any]:
    n = int(report.n)
    tpm = n / months if months > 0 else 0.0
    return {
        "n": n,
        "wins": int(report.wins),
        "losses": int(report.losses),
        "win_rate": float(report.win_rate),
        "profit_factor": (
            float(report.profit_factor)
            if report.profit_factor != float("inf")
            else None
        ),
        "profit_factor_raw": report.profit_factor,
        "expectancy_rr": float(report.expectancy_rr),
        "max_drawdown_rr": float(report.max_drawdown_rr),
        "trades_per_month": round(tpm, 4),
        "mfe_p50": float(report.mfe_p50),
        "mae_p50": float(report.mae_p50),
        "continuation_prob": float(report.continuation_prob),
    }


def _goal_metrics_for_validator(m: dict) -> dict:
    # GoalValidator expects max_drawdown_pct; we have max_drawdown_rr — SKIP if not comparable.
    return {
        "trades_per_month": m["trades_per_month"],
        "win_rate": m["win_rate"],
        "expectancy_r": m["expectancy_rr"],
        "avg_rr": m["expectancy_rr"],  # net mean R as proxy for avg_rr when available
        # max_drawdown_pct intentionally omitted → SKIP (units differ from R-drawdown)
    }


def _register(name: str, source, rationale: str):
    # Replace if re-running in same process
    HYPOTHESIS_REGISTRY.pop(name, None)
    h = _NamedSpineHypothesis(name, source, rationale)
    register_hypothesis(h)
    return h


def _qualify_one(
    runner: HypothesisRunner,
    hyp_name: str,
    csv_map: dict,
    qcfg: QualConfig,
    cost: CostModel,
    control_names: list[str],
) -> dict:
    agg = EdgeAggregator()
    candidates = [hyp_name]
    per_by_hyp = {
        name: runner.collect(name, csv_map) for name in candidates + control_names
    }
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        outs = per_by_hyp[name].get(INSTRUMENT, [])
        rrs = _net_rrs(outs, cost)
        rep = agg.aggregate(name, [INSTRUMENT], outs, cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0

    outs = per_by_hyp[hyp_name].get(INSTRUMENT, [])
    report = agg.aggregate(hyp_name, [INSTRUMENT], outs, cost_model=cost)
    st = evaluate_pre_bh(
        report, {INSTRUMENT: outs}, win_name, win_rrs, win_exp, qcfg, cost
    )
    bh_inputs = {hyp_name: st.p_value} if st.passed_1_to_6 else {}
    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)
    final = dataclasses.asdict(finalize(st, bh_survivors, qcfg))
    return {
        "edge_report": dataclasses.asdict(report),
        "qualification": final,
        "winning_control": win_name,
        "winning_control_exp": round(win_exp, 6),
        "n_outcomes": len(outs),
    }


def run(
    *,
    permutations: int | None = None,
    research_id: str = "H-G001-001",
    engine_gate: str | None = None,
    out_dir: Path | None = None,
) -> dict:
    global OUT_DIR, RESEARCH_ID
    RESEARCH_ID = research_id
    OUT_DIR = Path(out_dir) if out_dir is not None else (_ROOT / "research" / research_id)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG
    if engine_gate is not None:
        os.environ["BACKTEST_ENGINE_GATE"] = str(engine_gate)
        safe_print(f"[{RESEARCH_ID}] BACKTEST_ENGINE_GATE={engine_gate!r} (forced)")

    csv_path = guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)
    csv_map = {INSTRUMENT: csv_path}
    months = _corpus_span_months(csv_path)

    safe_print(f"[{RESEARCH_ID}] corpus={csv_path}")
    safe_print(f"[{RESEARCH_ID}] computing FM-058 liquidity_sweep series…")
    sweep = _liquidity_sweep_series(csv_path)
    n_bars = len(sweep)
    n_sweep_bars = sum(1 for v in sweep if v != 0)

    spine_out = (
        _ROOT
        / "results"
        / "research"
        / f"_spine_entries_{research_id.replace('-', '_').lower()}"
    )
    safe_print(f"[{RESEARCH_ID}] running production spine harvest (baseline)…")
    base_source = ProductionSpineSource(
        config_path=SPINE_CONFIG,
        out_root=str(spine_out),
    )
    base_entries = base_source.entries(INSTRUMENT)
    n_base = len(base_entries)

    # Veto: drop entries where entry bar has non-zero liquidity_sweep
    keep_indices: set[int] = set()
    vetoed: list[dict] = []
    for idx, ent in base_entries.items():
        if idx < 0 or idx >= n_bars:
            # index out of sweep series — keep (fail-open would bias; record)
            keep_indices.add(idx)
            continue
        if sweep[idx] != 0:
            vetoed.append(
                {
                    "entry_index": idx,
                    "liquidity_sweep": sweep[idx],
                    "timestamp": ent.timestamp,
                    "direction": ent.direction,
                }
            )
        else:
            keep_indices.add(idx)

    treat_source = FilteringSpineSource(
        base_source, keep_indices, label="liquidity_sweep_veto"
    )
    n_treat = len(treat_source.entries(INSTRUMENT))

    safe_print(
        f"[{RESEARCH_ID}] entries baseline={n_base} treatment={n_treat} "
        f"vetoed={len(vetoed)} sweep_bars={n_sweep_bars}/{n_bars}"
    )

    cfg = ResearchConfig.from_file(SPINE_CONFIG)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    qcfg = QualConfig.from_research_config(cfg)
    if permutations is not None:
        qcfg = dataclasses.replace(qcfg, n_permutations=permutations)

    control_names = sorted(
        n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control"
    )

    slug = research_id.lower().replace("-", "_")
    base_name = f"{slug}_baseline"
    treat_name = f"{slug}_treatment"
    _register(
        base_name,
        base_source,
        f"{research_id} baseline: production CRT spine unfiltered",
    )
    _register(
        treat_name,
        treat_source,
        f"{research_id} treatment: production CRT spine + liquidity_sweep veto",
    )

    safe_print(f"[{RESEARCH_ID}] M4 collect+qualify baseline (perms={qcfg.n_permutations})…")
    base_q = _qualify_one(runner, base_name, csv_map, qcfg, cost, control_names)
    safe_print(f"[{RESEARCH_ID}] M4 collect+qualify treatment…")
    treat_q = _qualify_one(runner, treat_name, csv_map, qcfg, cost, control_names)

    base_rep = base_q["edge_report"]
    treat_rep = treat_q["edge_report"]
    # rebuild EdgeReport-like metrics via aggregate fields already in dict
    base_m = {
        "n": base_rep["n"],
        "wins": base_rep["wins"],
        "losses": base_rep["losses"],
        "win_rate": base_rep["win_rate"],
        "profit_factor": base_rep["profit_factor"],
        "expectancy_rr": base_rep["expectancy_rr"],
        "max_drawdown_rr": base_rep["max_drawdown_rr"],
        "trades_per_month": round(base_rep["n"] / months, 4) if months else 0.0,
        "continuation_prob": base_rep["continuation_prob"],
    }
    treat_m = {
        "n": treat_rep["n"],
        "wins": treat_rep["wins"],
        "losses": treat_rep["losses"],
        "win_rate": treat_rep["win_rate"],
        "profit_factor": treat_rep["profit_factor"],
        "expectancy_rr": treat_rep["expectancy_rr"],
        "max_drawdown_rr": treat_rep["max_drawdown_rr"],
        "trades_per_month": round(treat_rep["n"] / months, 4) if months else 0.0,
        "continuation_prob": treat_rep["continuation_prob"],
    }

    delta = {
        "n": treat_m["n"] - base_m["n"],
        "win_rate": round(treat_m["win_rate"] - base_m["win_rate"], 6),
        "profit_factor": (
            None
            if base_m["profit_factor"] in (None, float("inf"))
            or treat_m["profit_factor"] in (None, float("inf"))
            else round(float(treat_m["profit_factor"]) - float(base_m["profit_factor"]), 6)
        ),
        "expectancy_rr": round(treat_m["expectancy_rr"] - base_m["expectancy_rr"], 6),
        "max_drawdown_rr": round(
            treat_m["max_drawdown_rr"] - base_m["max_drawdown_rr"], 6
        ),
        "trades_per_month": round(
            treat_m["trades_per_month"] - base_m["trades_per_month"], 6
        ),
    }

    # Goal reports
    from config_layer.goal_schema import load_goal_spec
    from config_layer.goal_validator import GoalValidator

    gspec = load_goal_spec()
    gv = GoalValidator()
    base_goal = gv.evaluate(_goal_metrics_for_validator(base_m), gspec).to_dict()
    treat_goal = gv.evaluate(_goal_metrics_for_validator(treat_m), gspec).to_dict()

    # Decision
    decision, reason = _decide(base_m, treat_m, delta, base_q, treat_q)

    gate = os.environ.get("BACKTEST_ENGINE_GATE")
    lens = (
        "crt_only_gate_off"
        if gate == "0"
        else "fusion_gate_on"
        if gate in ("1", "true", "True")
        else f"gate_{gate}"
    )

    common_meta = {
        "research_id": RESEARCH_ID,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument": INSTRUMENT,
        "prod_version": PROD_VERSION,
        "spine_config": SPINE_CONFIG,
        "corpus_path": str(csv_path).replace("\\", "/"),
        "corpus_status": PHASE1_STATUS,
        "authority_note": authority_status_note(),
        "validation_lens": lens,
        "backtest_engine_gate": gate,
        "corpus_span_months": round(months, 4),
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "n_permutations": qcfg.n_permutations,
        "exit_model": cfg.exit_model,
        "round_trip_bps": cfg.round_trip_bps,
        **provenance_block(cfg.exit_model, cfg.round_trip_bps),
        "non_promotable": True,
        "ontology_edits": False,
        "fm_math_edits": False,
    }

    baseline_doc = {
        **common_meta,
        "arm": "baseline",
        "description": "Production CRT spine entries unfiltered",
        "n_entries_harvested": n_base,
        "metrics": base_m,
        "qualification": base_q["qualification"],
        "winning_control": base_q["winning_control"],
        "goal_report": base_goal,
    }
    treatment_doc = {
        **common_meta,
        "arm": "treatment",
        "description": "Production CRT spine + liquidity_sweep veto (FM-058 != 0 discarded)",
        "n_entries_harvested": n_base,
        "n_entries_after_veto": n_treat,
        "n_vetoed": len(vetoed),
        "veto_rate": round(len(vetoed) / n_base, 6) if n_base else 0.0,
        "sweep_bars_in_corpus": n_sweep_bars,
        "metrics": treat_m,
        "qualification": treat_q["qualification"],
        "winning_control": treat_q["winning_control"],
        "goal_report": treat_goal,
        "vetoed_sample": vetoed[:20],
    }

    delta_doc = {
        **common_meta,
        "delta_treatment_minus_baseline": delta,
        "decision": decision,
        "decision_reason": reason,
    }

    # Write JSON
    (OUT_DIR / "baseline_results.json").write_text(
        json.dumps(baseline_doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "treatment_results.json").write_text(
        json.dumps(treatment_doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "delta_summary.json").write_text(
        json.dumps(delta_doc, indent=2, default=str) + "\n", encoding="utf-8"
    )

    _write_goal_report_md(OUT_DIR / "goal_report.md", baseline_doc, treatment_doc, delta)
    _write_promotion_decision(
        OUT_DIR / "promotion_decision.md",
        decision,
        reason,
        baseline_doc,
        treatment_doc,
        delta,
    )

    safe_print(f"[{RESEARCH_ID}] decision={decision}")
    safe_print(f"[{RESEARCH_ID}] wrote {OUT_DIR}")
    return delta_doc


def _decide(base_m, treat_m, delta, base_q, treat_q) -> tuple[str, str]:
    """Apply pre-registered decision rule (economic, not semantic)."""
    bq = base_q["qualification"].get("verdict", "")
    tq = treat_q["qualification"].get("verdict", "")
    de = delta["expectancy_rr"]
    dn = delta["n"]

    # Insufficient sample either arm
    if treat_m["n"] < 30 and base_m["n"] < 30:
        return (
            "REJECT_INSUFFICIENT",
            f"Both arms underpowered (baseline n={base_m['n']}, treatment n={treat_m['n']}; "
            f"min_samples=30). No ΔG001 claim.",
        )
    if treat_m["n"] < 30:
        return (
            "REJECT_INSUFFICIENT",
            f"Treatment n={treat_m['n']} < 30 after veto (baseline n={base_m['n']}). "
            f"Cannot claim positive ΔG001.",
        )

    # Strict: positive expectancy delta and non-negative PF direction
    if de is not None and de > 0:
        # still require treatment not clearly worse on PF if both finite
        pf_b, pf_t = base_m["profit_factor"], treat_m["profit_factor"]
        pf_ok = True
        if isinstance(pf_b, (int, float)) and isinstance(pf_t, (int, float)):
            if pf_b == pf_b and pf_t == pf_t:  # not NaN
                if pf_t < pf_b and pf_t < 1.0:
                    pf_ok = False
        if pf_ok and treat_m["expectancy_rr"] > 0:
            return (
                "QUALIFY_CANDIDATE",
                f"Treatment expectancy_rr={treat_m['expectancy_rr']:+.4f} "
                f"(Δ={de:+.4f} vs baseline {base_m['expectancy_rr']:+.4f}); "
                f"n={treat_m['n']} (Δn={dn}). M4 verdicts baseline={bq} treatment={tq}. "
                f"Remain in qualification only — corpus still non-promotable; "
                f"no production authority granted.",
            )
        return (
            "REJECT",
            f"Positive ΔE={de:+.4f} but treatment still non-useful "
            f"(E={treat_m['expectancy_rr']:+.4f}, PF={treat_m['profit_factor']}).",
        )

    if de is not None and de == 0 and dn == 0:
        return (
            "REJECT_NEUTRAL",
            "Veto removed zero entries or outcomes identical — no consumer effect measured.",
        )

    return (
        "REJECT",
        f"Δexpectancy_rr={de} (not > 0). Treatment E={treat_m['expectancy_rr']:+.4f}, "
        f"baseline E={base_m['expectancy_rr']:+.4f}, Δn={dn}. "
        f"Hypothesis rejected; consumer stays information-only.",
    )


def _write_goal_report_md(path: Path, base: dict, treat: dict, delta: dict) -> None:
    bm, tm = base["metrics"], treat["metrics"]
    research_id = base.get("research_id", RESEARCH_ID)
    lines = [
        f"# {research_id} Goal Report",
        "",
        f"Generated: `{base.get('generated_at_utc')}`",
        "",
        "## Corpus / standard",
        "",
        f"- Instrument: **{base['instrument']}** M15",
        f"- Corpus: `{base['corpus_path']}` ({base['corpus_status']})",
        f"- Span: **{base['corpus_span_months']}** months",
        f"- Exit: `{base.get('exit_model')}` · cost **{base.get('round_trip_bps')}** bps",
        f"- Lens: `{base.get('validation_lens')}` (BACKTEST_ENGINE_GATE={base.get('backtest_engine_gate')!r})",
        f"- Prod version: `{base['prod_version']}`",
        "",
        "## Metrics (net of costs)",
        "",
        "| Metric | Baseline | Treatment | Δ (T−B) |",
        "|---|---:|---:|---:|",
        f"| Trade count (n) | {bm['n']} | {tm['n']} | {delta['n']} |",
        f"| Trades / month | {bm['trades_per_month']} | {tm['trades_per_month']} | {delta['trades_per_month']} |",
        f"| Win rate | {bm['win_rate']} | {tm['win_rate']} | {delta['win_rate']} |",
        f"| Profit factor | {bm['profit_factor']} | {tm['profit_factor']} | {delta['profit_factor']} |",
        f"| Expectancy (R net) | {bm['expectancy_rr']} | {tm['expectancy_rr']} | {delta['expectancy_rr']} |",
        f"| Max DD (R) | {bm['max_drawdown_rr']} | {tm['max_drawdown_rr']} | {delta['max_drawdown_rr']} |",
        "",
        f"Veto removed **{treat.get('n_vetoed', 0)}** / {treat.get('n_entries_harvested', 0)} "
        f"entries (rate={treat.get('veto_rate')}).",
        "",
        "## G001 GoalValidator (measure-only)",
        "",
        f"### Baseline decision: **{base['goal_report'].get('decision')}** "
        f"(enabled={base['goal_report'].get('enabled')}, "
        f"enforced={base['goal_report'].get('enforced')})",
        "",
    ]
    for c in base["goal_report"].get("criteria") or []:
        lines.append(
            f"- `{c.get('name')}`: {c.get('status')} "
            f"(actual={c.get('actual')}, target={c.get('target')}, gap={c.get('gap')})"
        )
    lines += [
        "",
        f"### Treatment decision: **{treat['goal_report'].get('decision')}**",
        "",
    ]
    for c in treat["goal_report"].get("criteria") or []:
        lines.append(
            f"- `{c.get('name')}`: {c.get('status')} "
            f"(actual={c.get('actual')}, target={c.get('target')}, gap={c.get('gap')})"
        )
    lines += [
        "",
        "## M4 qualification verdicts",
        "",
        f"- Baseline: `{base['qualification'].get('verdict')}`",
        f"- Treatment: `{treat['qualification'].get('verdict')}`",
        "",
        "## Interpretation guard",
        "",
        "Semantic correctness of FM-058 is **not** re-tested here.",
        "This report answers economic usefulness vs G001 only.",
        "Corpus remains non-promotable for live authority.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_promotion_decision(
    path: Path, decision: str, reason: str, base: dict, treat: dict, delta: dict
) -> None:
    advance = decision == "QUALIFY_CANDIDATE"
    research_id = base.get("research_id", RESEARCH_ID)
    lines = [
        f"# {research_id} Promotion Decision",
        "",
        f"**Decision:** `{decision}`",
        "",
        f"**Authority ladder:** "
        + ("remain in qualification (still level 0 until revalidation + corpus authority)"
           if advance
           else "INFORMATION_ONLY (level 0) — no advancement"),
        "",
        "## Reason",
        "",
        reason,
        "",
        "## Pre-registered rule applied",
        "",
        "- Positive useful Δexpectancy and treatment E>0 → QUALIFY_CANDIDATE (research only)",
        "- Neutral / negative / underpowered → REJECT*",
        "- **Never** edit ontology, FM math, or promote production config from this run",
        "",
        "## Numbers (summary)",
        "",
        f"| | Baseline | Treatment |",
        f"|---|---:|---:|",
        f"| n | {base['metrics']['n']} | {treat['metrics']['n']} |",
        f"| E (R) | {base['metrics']['expectancy_rr']} | {treat['metrics']['expectancy_rr']} |",
        f"| PF | {base['metrics']['profit_factor']} | {treat['metrics']['profit_factor']} |",
        f"| WR | {base['metrics']['win_rate']} | {treat['metrics']['win_rate']} |",
        f"| ΔE | | {delta['expectancy_rr']} |",
        "",
        "## Production influence",
        "",
        "- **Liquidity sweep veto on CRT spine:** "
        + ("may remain a *research qualification candidate* only"
           if advance
           else "**not** authorized for production wiring"),
        "- **ACTIVE_VERSION / v2_multi_2026_04:** unchanged",
        "- **G001 consumer ledger:** update economic_status from this evidence; "
        "do not set ladder≥1 without MEASURED_POSITIVE package + human sign-off",
        "",
        f"Corpus note: {base.get('authority_note', '')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--permutations",
        type=int,
        default=None,
        help="override M4 permutation count (default: research_config_spine_xauusd)",
    )
    ap.add_argument(
        "--research-id",
        default="H-G001-001",
        help="research id / output folder under research/ (e.g. H-G001-001b)",
    )
    ap.add_argument(
        "--engine-gate",
        default=None,
        help="set BACKTEST_ENGINE_GATE for this run (0=CRT-only, 1=fusion). "
        "Omit to leave process env unchanged.",
    )
    ap.add_argument(
        "--out-dir",
        default=None,
        help="optional override output directory (default research/<research-id>)",
    )
    args = ap.parse_args()
    out = Path(args.out_dir) if args.out_dir else None
    run(
        permutations=args.permutations,
        research_id=args.research_id,
        engine_gate=args.engine_gate,
        out_dir=out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
