#!/usr/bin/env python
"""phase1_resolver_replay_sample_acquisition.py — Phase-1 sample acquisition (same object).

STANDING CONTRACT (unchanged — do not widen the unit)
------------------------------------------------------
Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · Cost=SEM-015 TIMEOUT
Control=Always-Long (stride H20) · Engine=EXP entry + atlas direction
Resolver-Memory   = SHADOW→EXP + pending_displacement_dir (strict_memory)
Resolver-TrendBias = SHADOW→EXP + trend_bias sign
Outputs ONLY: n, coverage %, expectancy, PF, win rate
Interpret Cases A–D only. economic_claims_allowed=false by default.

PURPOSE
-------
Increase *n* for the SAME measurement object by pooling SHADOW→EXP collapses
across Phase-1-admitted instruments only. Does not invent corpora, does not
promote unbound sibling CSVs into Phase-1, does not widen to all EXPANSION.

PHASE-1 ELIGIBILITY (honest gate)
---------------------------------
An instrument is Phase-1-runnable for this object only if ALL hold:
  1. Bound Dataset Identity with dataset_id matching *_PHASE1_* in
     docs/governance/dataset_identity_registry.json
  2. Canonical admitted M15 CSV present at the bound path
  3. bar_matrix.parquet present (trend_bias + ATR for TrendBias / Always-Long)
  4. SEM-015 ComponentCostModel measurable for that instrument (manifest)

Sibling M15 CSVs under data/mt5/ that lack (1)–(4) are inventoried as
PRESENT_UNBOUND and are NOT scored as Phase-1.

USAGE
-----
  $env:PYTHONPATH='D:\\Tradelatest'
  .\\.venv\\Scripts\\python.exe scripts\\analysis\\phase1_resolver_replay_sample_acquisition.py
  # optional: reuse prior XAUUSD collapses without re-running BT
  .\\.venv\\Scripts\\python.exe scripts\\analysis\\phase1_resolver_replay_sample_acquisition.py --skip-replay

FORBIDDEN (this script does none)
---------------------------------
Flip continuous_disp_to_expansion · wire CHoCH · reopen occupancy · optimize parity ·
reclassify April rejects · TV forensic as occupancy adjudicator · promote economic
findings · redefine object to harvest the 148 EXPANSION entries.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.costs import ComponentCostModel, UnmeasuredCostError  # noqa: E402

_EV = _ROOT / "scripts" / "analysis" / "phase1_resolver_replay_evidence.py"
_spec = importlib.util.spec_from_file_location("phase1_resolver_replay_evidence", _EV)
ev = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ev)

from research.probes.corpus import load_corpus  # noqa: E402
from research.probes.governance import assert_no_claim_keys  # noqa: E402

_REGISTRY = _ROOT / "docs" / "governance" / "dataset_identity_registry.json"
_DATASETS_DIR = _ROOT / "docs" / "governance" / "datasets"
_MT5_DIR = _ROOT / "data" / "mt5"
_BAR_MATRIX_ROOT = _ROOT / "results" / "research" / "bar_matrix"
_COST_MANIFEST = (
    _ROOT
    / "results"
    / "research"
    / "xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)
_PRIOR_COLLAPSES = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "collapses.json"
_OUT_DIR = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "sample_acquisition"
_NOTE_PATH = _ROOT / "docs" / "research" / "phase1_resolver_replay_sample_acquisition_note.md"

# Sibling instruments commonly co-located with Phase-1 M15 CSVs (inventory only).
_SIBLING_PROBE = ("XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "EURCAD")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_provenance() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        sha = None
    try:
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=str(_ROOT), text=True
            ).strip()
        )
    except Exception:
        dirty = None
    return {"git_sha": sha, "tree_dirty": dirty}


def _load_phase1_bound_instruments() -> list[dict]:
    """Return Phase-1 bound dataset records from the identity registry."""
    reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    out: list[dict] = []
    for row in reg.get("datasets", []):
        did = str(row.get("dataset_id", ""))
        if "PHASE1" not in did.upper():
            continue
        record_rel = row.get("record")
        record_path = _ROOT / record_rel if record_rel else _DATASETS_DIR / f"{did}.json"
        rec = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
        canon = rec.get("canonical_artifact") or {}
        csv_rel = canon.get("path") or f"data/mt5/{row.get('symbol')}_M15.csv"
        out.append(
            {
                "dataset_id": did,
                "symbol": row.get("symbol") or rec.get("symbol"),
                "record": str(record_path),
                "csv_path": str(_ROOT / csv_rel),
                "csv_sha256_bound": canon.get("sha256"),
                "decision_status": rec.get("decision_status"),
                "rows_bound": canon.get("rows"),
                "start": canon.get("start"),
                "end": canon.get("end"),
            }
        )
    return out


def _inventory() -> dict:
    """Full inventory: Phase-1 bound vs sibling unbound CSVs + readiness gates."""
    phase1 = _load_phase1_bound_instruments()
    phase1_syms = {p["symbol"] for p in phase1}

    siblings: list[dict] = []
    for sym in _SIBLING_PROBE:
        csv_path = _MT5_DIR / f"{sym}_M15.csv"
        bm_path = _BAR_MATRIX_ROOT / f"{sym}_M15" / "bar_matrix.parquet"
        cost_ok = sym == "XAUUSD" and _COST_MANIFEST.is_file()
        # Only XAUUSD has a measured SEM-015 manifest in-repo today.
        entry = {
            "instrument": sym,
            "csv_present": csv_path.is_file(),
            "csv_path": str(csv_path) if csv_path.is_file() else None,
            "csv_sha256": _sha256_file(csv_path) if csv_path.is_file() else None,
            "bar_matrix_present": bm_path.is_file(),
            "bar_matrix_path": str(bm_path) if bm_path.is_file() else None,
            "sem015_cost_manifest_present": cost_ok,
            "phase1_bound": sym in phase1_syms,
            "phase1_dataset_id": next(
                (p["dataset_id"] for p in phase1 if p["symbol"] == sym), None
            ),
        }
        if entry["csv_present"]:
            # date span (first/last data line) — descriptive inventory only
            try:
                lines = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) >= 2:
                    entry["csv_rows"] = len(lines) - 1
                    entry["csv_start"] = lines[1].split(",")[0]
                    entry["csv_end"] = lines[-1].split(",")[0]
            except Exception as exc:
                entry["csv_span_error"] = str(exc)

        runnable = (
            entry["phase1_bound"]
            and entry["csv_present"]
            and entry["bar_matrix_present"]
            and entry["sem015_cost_manifest_present"]
        )
        entry["phase1_runnable_for_resolver_object"] = runnable
        if not runnable:
            blockers = []
            if not entry["phase1_bound"]:
                blockers.append("not_in_phase1_dataset_identity_registry")
            if not entry["csv_present"]:
                blockers.append("missing_m15_csv")
            if not entry["bar_matrix_present"]:
                blockers.append("missing_bar_matrix_parquet_trend_bias")
            if not entry["sem015_cost_manifest_present"]:
                blockers.append("missing_sem015_cost_manifest_for_instrument")
            entry["blockers"] = blockers
            entry["status"] = (
                "PHASE1_RUNNABLE"
                if runnable
                else ("PHASE1_BOUND_BUT_INCOMPLETE" if entry["phase1_bound"] else "PRESENT_UNBOUND")
            )
        else:
            entry["blockers"] = []
            entry["status"] = "PHASE1_RUNNABLE"
        siblings.append(entry)

    how_xau = (
        "XAUUSD was chosen because it is the sole Phase-1 bound Dataset Identity "
        "(dataset_id=XAUUSD_MT5_PHASE1_20260521) in docs/governance/dataset_identity_registry.json; "
        "the existing replay defaults (_DEFAULT_CSV / bar_matrix / SEM-015 XAUUSD cost manifest) "
        "all pin that same admitted artifact (sha256 4d73f5ce…). "
        "Sibling MT5 M15 CSVs share a similar calendar window but are unbound "
        "(path_passthrough only) and lack Phase-1 dataset records, bar_matrix, and SEM-015 costs."
    )

    return {
        "how_xauusd_was_chosen": how_xau,
        "phase1_bound_datasets": phase1,
        "instruments": siblings,
        "phase1_runnable": [s["instrument"] for s in siblings if s["phase1_runnable_for_resolver_object"]],
        "present_unbound_siblings": [
            s["instrument"] for s in siblings if s["status"] == "PRESENT_UNBOUND"
        ],
        "acquisition_required_to_extend_n": [
            "Admit a new Dataset Identity record under docs/governance/datasets/ "
            "with dataset_id matching *_PHASE1_* and register it in dataset_identity_registry.json "
            "(do not silently treat unbound CSVs as Phase-1).",
            "Canonical admitted M15 CSV at the bound path (native_fetch; hash-bound).",
            "Build results/research/bar_matrix/<SYM>_M15/bar_matrix.parquet for trend_bias + atr_abs "
            "(same SEM-018 surface used by Resolver-TrendBias / Always-Long).",
            "Measure SEM-015 ComponentCostModel for that instrument (do not reuse XAUUSD oz costs on FX).",
            "Re-run this sample_acquisition wrapper to pool SHADOW→EXP collapses with instrument tags.",
            "Object definition stays SHADOW→EXP + pending_displacement_dir / trend_bias sign — "
            "do not harvest the 148 EXPANSION entries.",
        ],
    }


def _score_instrument(
    *,
    instrument: str,
    csv_path: Path,
    bar_matrix: Path,
    out_dir: Path,
    cost_model: ComponentCostModel,
    skip_replay: bool,
    prior_collapses_path: Optional[Path],
) -> dict:
    """Run (or reuse) SHADOW→EXP capture and score Memory / TrendBias / Always-Long."""
    collapses_path = out_dir / f"collapses_{instrument}.json"
    if skip_replay and prior_collapses_path and prior_collapses_path.is_file() and instrument == "XAUUSD":
        collapses = json.loads(prior_collapses_path.read_text(encoding="utf-8"))
        print(f"[{instrument}] reused prior collapses: n={len(collapses)} from {prior_collapses_path}")
    elif skip_replay and collapses_path.is_file():
        collapses = json.loads(collapses_path.read_text(encoding="utf-8"))
        print(f"[{instrument}] reused collapses: n={len(collapses)} from {collapses_path}")
    else:
        print(f"[{instrument}] running SHADOW→EXP collapse replay...")
        collapses = ev.run_shadow_collapse_replay(csv_path, instrument, out_dir)
        print(f"[{instrument}] captured collapses: n={len(collapses)}")

    for ep in collapses:
        ep["instrument"] = instrument

    collapses_path.write_text(json.dumps(collapses, indent=2), encoding="utf-8")

    trend_by_ts, atr_by_ts = ev._load_trend_bias_by_ts(bar_matrix)
    corpus = load_corpus(csv_path)

    for ep in collapses:
        key = ev._normalize_ts(ep["timestamp"])
        ep["trend_bias"] = trend_by_ts.get(key)
        ep["trend_bias_ts_key"] = key
        if ep.get("atr_abs") is None:
            ep["atr_abs"] = atr_by_ts.get(key)
        ep["memory_direction"] = ev._dir_to_long_short(ep.get("pending_displacement_dir"))
        ep["trendbias_direction"] = ev._tb_to_long_short(ep.get("trend_bias"))

    n_universe = len(collapses)

    mem_nets: list[float] = []
    mem_eligible = 0
    for ep in collapses:
        d = ep["memory_direction"]
        if d is None:
            ep["memory_skip"] = "no_pending_displacement_dir"
            continue
        mem_eligible += 1
        atr = ep.get("atr_abs")
        if not atr or atr <= 0:
            ep["memory_skip"] = "no_atr"
            continue
        net = ev._net_r(corpus, ep["candle_index"], d, float(atr), cost_model)
        if net is None:
            ep["memory_skip"] = "horizon_truncated"
            continue
        ep["memory_net_R"] = net
        ep["memory_skip"] = None
        mem_nets.append(net)

    tb_nets: list[float] = []
    tb_eligible = 0
    for ep in collapses:
        d = ep["trendbias_direction"]
        if d is None:
            ep["trendbias_skip"] = "trend_bias_zero_or_missing"
            continue
        tb_eligible += 1
        atr = ep.get("atr_abs")
        if not atr or atr <= 0:
            ep["trendbias_skip"] = "no_atr"
            continue
        net = ev._net_r(corpus, ep["candle_index"], d, float(atr), cost_model)
        if net is None:
            ep["trendbias_skip"] = "horizon_truncated"
            continue
        ep["trendbias_net_R"] = net
        ep["trendbias_skip"] = None
        tb_nets.append(net)

    atr_by_index: dict[int, float] = {}
    for i, row in enumerate(corpus):
        key = row["ts"].strftime("%Y-%m-%d %H:%M:%S")
        if key in atr_by_ts:
            atr_by_index[i] = atr_by_ts[key]

    al_nets: list[float] = []
    al_universe = 0
    for i in range(len(corpus)):
        if (i % ev.STRIDE) != 0:
            continue
        al_universe += 1
        atr = atr_by_index.get(i)
        if not atr or atr <= 0:
            continue
        net = ev._net_r(corpus, i, "LONG", float(atr), cost_model)
        if net is None:
            continue
        al_nets.append(net)

    mem_row = ev._scoreboard_row(
        "Resolver-Memory", mem_nets, n_universe=n_universe, n_eligible=mem_eligible
    )
    tb_row = ev._scoreboard_row(
        "Resolver-TrendBias", tb_nets, n_universe=n_universe, n_eligible=tb_eligible
    )
    al_row = ev._scoreboard_row(
        "Always-Long", al_nets, n_universe=al_universe, n_eligible=al_universe
    )
    # Per-instrument case vs its own Always-Long (label clearly; pooled case separate).
    case_call = ev._call_case(mem_row, tb_row, al_row)

    return {
        "instrument": instrument,
        "csv_path": str(csv_path),
        "csv_sha256": _sha256_file(csv_path),
        "bar_matrix": str(bar_matrix),
        "n_shadow_exp_collapses": n_universe,
        "collapses": collapses,
        "scoreboard": {
            "Resolver-Memory": mem_row,
            "Resolver-TrendBias": tb_row,
            "Always-Long": al_row,
        },
        "case_call_vs_own_always_long": case_call,
        "memory_nets": mem_nets,
        "trendbias_nets": tb_nets,
        "always_long": al_row,
    }


def _pool_and_score(per_inst: list[dict], always_long_by_inst: dict) -> dict:
    """Pool Memory/TrendBias collapses; keep Always-Long per-instrument."""
    pooled_collapses: list[dict] = []
    mem_nets: list[float] = []
    tb_nets: list[float] = []
    for inst in per_inst:
        for ep in inst["collapses"]:
            pooled_collapses.append(ep)
            if ep.get("memory_net_R") is not None and ep.get("memory_skip") is None:
                mem_nets.append(float(ep["memory_net_R"]))
            if ep.get("trendbias_net_R") is not None and ep.get("trendbias_skip") is None:
                tb_nets.append(float(ep["trendbias_net_R"]))

    n_universe = len(pooled_collapses)
    mem_eligible = sum(
        1 for ep in pooled_collapses if ep.get("memory_direction") is not None
    )
    tb_eligible = sum(
        1 for ep in pooled_collapses if ep.get("trendbias_direction") is not None
    )

    mem_row = ev._scoreboard_row(
        "Resolver-Memory", mem_nets, n_universe=n_universe, n_eligible=mem_eligible
    )
    tb_row = ev._scoreboard_row(
        "Resolver-TrendBias", tb_nets, n_universe=n_universe, n_eligible=tb_eligible
    )

    # Prefer per-instrument Always-Long; report pooled resolver n vs each control.
    # For case call when only one instrument: use that instrument's Always-Long.
    # When multiple: case call vs each control is reported; primary case uses
    # equal-weight mean of per-instrument Always-Long expectancies as a
    # DESCRIPTIVE label only (not a promotion gate).
    al_rows = always_long_by_inst
    if len(al_rows) == 1:
        al_primary_key = next(iter(al_rows))
        al_primary = al_rows[al_primary_key]
        case_call = ev._call_case(mem_row, tb_row, al_primary)
        case_call["always_long_reference"] = al_primary_key
    else:
        expectancies = [
            r["expectancy"] for r in al_rows.values() if r.get("expectancy") is not None
        ]
        if expectancies:
            synthetic = {
                "arm": "Always-Long-equal-weight-mean-of-per-instrument",
                "n": None,
                "expectancy": round(st.mean(expectancies), 6),
                "PF": None,
                "win_rate": None,
                "power": "SYNTHETIC_LABEL_ONLY",
            }
            case_call = ev._call_case(mem_row, tb_row, synthetic)
            case_call["always_long_reference"] = "equal_weight_mean_of_per_instrument"
            case_call["per_instrument_case_vs_own_control"] = {
                k: ev._call_case(mem_row, tb_row, v)["case"] for k, v in al_rows.items()
            }
        else:
            case_call = ev._call_case(mem_row, tb_row, {"expectancy": None})
            case_call["always_long_reference"] = "unavailable"

    return {
        "n_shadow_exp_collapses_pooled": n_universe,
        "n_ge_30": n_universe >= 30,
        "collapses_pooled": pooled_collapses,
        "scoreboard_pooled": {
            "Resolver-Memory": mem_row,
            "Resolver-TrendBias": tb_row,
        },
        "always_long_per_instrument": al_rows,
        "case_call": case_call,
    }


def _render_note(artifact: dict) -> str:
    inv = artifact["inventory"]
    pooled = artifact["pooled"]
    lines = [
        "# Phase-1 resolver replay — sample acquisition note",
        "",
        "**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none",
        "",
        "**Object definition unchanged:** Unit=ENTRY · Corpus=Phase-1 · Horizon=H20 · "
        "Cost=SEM-015 TIMEOUT · Control=Always-Long stride H20 · "
        "Resolver-Memory = SHADOW→EXP + `pending_displacement_dir` (strict_memory) · "
        "Resolver-TrendBias = SHADOW→EXP + `trend_bias` sign. "
        "No widening to the 148 EXPANSION entries; no forbidden work.",
        "",
        "## How XAUUSD was chosen",
        "",
        inv["how_xauusd_was_chosen"],
        "",
        "## Inventory (Phase-1 vs siblings)",
        "",
        "| Instrument | Phase-1 bound | CSV | bar_matrix | SEM-015 cost | Status | Blockers |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in inv["instruments"]:
        lines.append(
            f"| {s['instrument']} | {s['phase1_bound']} | {s['csv_present']} | "
            f"{s['bar_matrix_present']} | {s['sem015_cost_manifest_present']} | "
            f"{s['status']} | {', '.join(s.get('blockers') or []) or '—'} |"
        )
    lines += [
        "",
        f"**Phase-1 runnable for this object:** {inv['phase1_runnable'] or '(none)'}",
        f"**Present unbound siblings (NOT scored as Phase-1):** {inv['present_unbound_siblings']}",
        "",
        "## Per-instrument SHADOW→EXP n",
        "",
        "| Instrument | n_collapses | Memory n | TrendBias n | Always-Long n | Always-Long E | Case vs own AL | power (Memory) |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for inst in artifact["per_instrument"]:
        sb = inst["scoreboard"]
        cc = inst["case_call_vs_own_always_long"]
        al = sb["Always-Long"]
        e = f"{al['expectancy']:+.6f}" if al["expectancy"] is not None else "n/a"
        lines.append(
            f"| {inst['instrument']} | {inst['n_shadow_exp_collapses']} | "
            f"{sb['Resolver-Memory']['n']} | {sb['Resolver-TrendBias']['n']} | "
            f"{al['n']} | {e} | {cc['case']} | {sb['Resolver-Memory']['power']} |"
        )

    mem = pooled["scoreboard_pooled"]["Resolver-Memory"]
    tb = pooled["scoreboard_pooled"]["Resolver-TrendBias"]
    cc = pooled["case_call"]
    lines += [
        "",
        "## Pooled resolver scoreboard (Memory / TrendBias)",
        "",
        f"**Pooled n (SHADOW→EXP collapses):** {pooled['n_shadow_exp_collapses_pooled']}",
        f"**n ≥ 30 reached:** {pooled['n_ge_30']}",
        "",
        "| Arm | n | coverage % | expectancy | PF | win rate | power |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for key, r in (
        ("Resolver-Memory", mem),
        ("Resolver-TrendBias", tb),
    ):
        e = f"{r['expectancy']:+.6f}" if r["expectancy"] is not None else "n/a"
        pf = f"{r['PF']:.4f}" if r["PF"] is not None else "n/a"
        wr = f"{r['win_rate']:.4f}" if r["win_rate"] is not None else "n/a"
        lines.append(
            f"| {key} | {r['n']} | {r['coverage_pct']:.2f} | {e} | {pf} | {wr} | {r['power']} |"
        )

    lines += [
        "",
        "### Always-Long controls (per-instrument; not pooled into resolver n)",
        "",
        "| Instrument | n | coverage % | expectancy | PF | win rate | power |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for sym, r in pooled["always_long_per_instrument"].items():
        e = f"{r['expectancy']:+.6f}" if r["expectancy"] is not None else "n/a"
        pf = f"{r['PF']:.4f}" if r["PF"] is not None else "n/a"
        wr = f"{r['win_rate']:.4f}" if r["win_rate"] is not None else "n/a"
        lines.append(
            f"| Always-Long ({sym}) | {r['n']} | {r['coverage_pct']:.2f} | {e} | {pf} | {wr} | {r['power']} |"
        )

    lines += [
        "",
        "## Cases A–D (interpretive only)",
        "",
        f"**Case call (pooled resolver vs Always-Long reference `{cc.get('always_long_reference')}`): {cc['case']}**",
        "",
        f"- Memory expectancy: `{cc.get('memory_expectancy')}`",
        f"- TrendBias expectancy: `{cc.get('trendbias_expectancy')}`",
        f"- Always-Long expectancy (reference): `{cc.get('always_long_expectancy')}`",
        f"- Memory beats control: `{cc.get('memory_beats_control')}`",
        f"- TrendBias beats control: `{cc.get('trendbias_beats_control')}`",
        "",
        cc.get("rubric", ""),
        "",
        cc.get("note", ""),
        "",
        f"**Power labels:** Memory=`{mem['power']}`, TrendBias=`{tb['power']}` "
        f"(MIN_N_LABEL={ev.MIN_N_LABEL}). economic_claims_allowed=false.",
        "",
        "## Blocker (if n < 30)",
        "",
    ]
    if not pooled["n_ge_30"]:
        lines += [
            f"Only Phase-1-runnable instrument(s): **{inv['phase1_runnable']}**. "
            f"Pooled SHADOW→EXP n={pooled['n_shadow_exp_collapses_pooled']} < 30.",
            "",
            "Sibling M15 CSVs exist on disk (EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD) with a "
            "similar 2024-05→2026-05 window, but they are **not** Phase-1 Dataset Identities. "
            "Treating them as Phase-1 would invent corpora. Missing for each unbound sibling: "
            "dataset identity admission, bar_matrix (trend_bias), and instrument-specific SEM-015 cost.",
            "",
            "### What acquisition would require (new data / admission — not invented here)",
            "",
        ]
        for item in inv["acquisition_required_to_extend_n"]:
            lines.append(f"- {item}")
    else:
        lines.append("n ≥ 30 reached under the same object; still DESCRIPTIVE_ONLY unless gates explicitly allow.")

    lines += [
        "",
        "## Forbidden-work confirmation",
        "",
        "All forbidden flags in the JSON artifact are `false`.",
        "",
        "## Artifacts",
        "",
        f"- Inventory + scoreboard JSON: `{artifact['paths']['scoreboard']}`",
        f"- Pooled collapses: `{artifact['paths']['collapses_pooled']}`",
        f"- This note: `{_NOTE_PATH}`",
        "",
        f"generated_at (UTC): `{artifact['generated_at']}`",
        "",
        "---",
        "No economic promotion. Object unchanged. Measure-before-promote. Cases A–D only.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", default=str(_OUT_DIR))
    ap.add_argument(
        "--skip-replay",
        action="store_true",
        help="Reuse prior Phase-1 collapses.json for XAUUSD when present (inventory still live).",
    )
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = _inventory()
    inv_path = out_dir / "inventory.json"
    inv_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print("=== INVENTORY ===")
    print(f"Phase-1 runnable: {inventory['phase1_runnable']}")
    print(f"Present unbound:  {inventory['present_unbound_siblings']}")
    print(f"Wrote {inv_path}")

    if not _COST_MANIFEST.is_file():
        print(f"BLOCKER: SEM-015 cost manifest missing at {_COST_MANIFEST}")
        return 2

    try:
        cost_model = ComponentCostModel.from_manifest(
            json.loads(_COST_MANIFEST.read_text(encoding="utf-8")),
            instrument="XAUUSD",
            source=_COST_MANIFEST.name,
        )
    except UnmeasuredCostError as exc:
        print(f"BLOCKER: SEM-015 cost model unusable — {exc}")
        return 2

    runnable = [
        s for s in inventory["instruments"] if s["phase1_runnable_for_resolver_object"]
    ]
    if not runnable:
        print("BLOCKER: no Phase-1-runnable instruments for this resolver object.")
        # Still write a blocker artifact + note.
        artifact = {
            "artifact": "phase1_resolver_replay_sample_acquisition",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "claim_class": "DESCRIPTIVE_ONLY",
            "economic_claims_allowed": False,
            "object_definition_unchanged": True,
            "inventory": inventory,
            "per_instrument": [],
            "pooled": {
                "n_shadow_exp_collapses_pooled": 0,
                "n_ge_30": False,
                "collapses_pooled": [],
                "scoreboard_pooled": {},
                "always_long_per_instrument": {},
                "case_call": {"case": "D", "reason": "no runnable Phase-1 instruments"},
            },
            "blocker": "only_xauusd_phase1_but_incomplete_or_none_runnable",
            "paths": {"scoreboard": str(out_dir / "scoreboard.json"), "collapses_pooled": str(out_dir / "collapses_pooled.json")},
            "forbidden_work_confirmation": {
                "continuous_disp_to_expansion_flipped": False,
                "choch_wired": False,
                "occupancy_reopened": False,
                "parity_optimized": False,
                "april_offsession_reclassified": False,
                "tv_forensic_as_occupancy_adjudicator": False,
                "economic_promotion": False,
                "expanded_to_148_expansion_entries": False,
                "unbound_csvs_treated_as_phase1": False,
            },
            "provenance": {**_git_provenance()},
        }
        (out_dir / "scoreboard.json").write_text(
            json.dumps(artifact, indent=2, default=str), encoding="utf-8"
        )
        (out_dir / "collapses_pooled.json").write_text("[]", encoding="utf-8")
        _NOTE_PATH.write_text(_render_note(artifact), encoding="utf-8")
        return 2

    per_instrument: list[dict] = []
    always_long_by_inst: dict = {}
    for s in runnable:
        sym = s["instrument"]
        # Cost model is XAUUSD-only today; runnable gate already requires SEM-015 for sym.
        if sym != "XAUUSD":
            print(
                f"BLOCKER: {sym} marked runnable but no instrument-specific SEM-015 "
                "loader wired — refusing to apply XAUUSD costs to non-XAU."
            )
            continue
        result = _score_instrument(
            instrument=sym,
            csv_path=Path(s["csv_path"]),
            bar_matrix=Path(s["bar_matrix_path"]),
            out_dir=out_dir,
            cost_model=cost_model,
            skip_replay=args.skip_replay,
            prior_collapses_path=_PRIOR_COLLAPSES,
        )
        always_long_by_inst[sym] = result["scoreboard"]["Always-Long"]
        # Drop bulky nets from persisted per-instrument view (nets remain on collapses).
        slim = {k: v for k, v in result.items() if k not in ("memory_nets", "trendbias_nets")}
        per_instrument.append(slim)

    pooled = _pool_and_score(per_instrument, always_long_by_inst)
    collapses_pooled_path = out_dir / "collapses_pooled.json"
    collapses_pooled_path.write_text(
        json.dumps(pooled["collapses_pooled"], indent=2, default=str), encoding="utf-8"
    )

    artifact = {
        "artifact": "phase1_resolver_replay_sample_acquisition",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "object_definition_unchanged": True,
        "standing_contract": {
            "unit": "ENTRY",
            "corpus": "Phase-1",
            "horizon": "H20",
            "cost": "SEM-015 TIMEOUT",
            "control": "Always-Long stride H20 (per-instrument)",
            "resolver_memory": "SHADOW→EXP + pending_displacement_dir (strict_memory)",
            "resolver_trendbias": "SHADOW→EXP + trend_bias sign",
            "outputs": ["n", "coverage_pct", "expectancy", "PF", "win_rate"],
        },
        "forbidden_work_confirmation": {
            "continuous_disp_to_expansion_flipped": False,
            "choch_wired": False,
            "occupancy_reopened": False,
            "parity_optimized": False,
            "april_offsession_reclassified": False,
            "tv_forensic_as_occupancy_adjudicator": False,
            "economic_promotion": False,
            "expanded_to_148_expansion_entries": False,
            "unbound_csvs_treated_as_phase1": False,
        },
        "provenance": {
            **_git_provenance(),
            "cost_model_provenance": cost_model.provenance(),
            "config_version": ev.PROD_VERSION,
            "horizon": ev.HORIZON,
            "always_long_stride": ev.STRIDE,
            "prior_collapses_reused": bool(args.skip_replay),
        },
        "inventory": inventory,
        "per_instrument": [
            {
                **{k: v for k, v in inst.items() if k != "collapses"},
                "n_shadow_exp_collapses": inst["n_shadow_exp_collapses"],
            }
            for inst in per_instrument
        ],
        "pooled": {
            **{k: v for k, v in pooled.items() if k != "collapses_pooled"},
            "collapses_pooled_path": str(collapses_pooled_path),
        },
        "paths": {
            "scoreboard": str(out_dir / "scoreboard.json"),
            "scoreboard_md": str(out_dir / "scoreboard.md"),
            "collapses_pooled": str(collapses_pooled_path),
            "inventory": str(inv_path),
            "note": str(_NOTE_PATH),
        },
        "cases_rubric": ev.CASES_RUBRIC,
    }
    # Attach collapses into per_instrument persistence separately already via collapses_*.json
    assert_no_claim_keys(artifact)

    scoreboard_path = out_dir / "scoreboard.json"
    scoreboard_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

    note = _render_note(
        {
            **artifact,
            "per_instrument": per_instrument,
            "pooled": pooled,
        }
    )
    md_path = out_dir / "scoreboard.md"
    md_path.write_text(note, encoding="utf-8")
    _NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NOTE_PATH.write_text(note, encoding="utf-8")

    print("\n=== SAMPLE ACQUISITION SCOREBOARD ===")
    print(f"Pooled SHADOW→EXP n: {pooled['n_shadow_exp_collapses_pooled']}  n>=30={pooled['n_ge_30']}")
    mem = pooled["scoreboard_pooled"]["Resolver-Memory"]
    tb = pooled["scoreboard_pooled"]["Resolver-TrendBias"]
    print(
        f"Memory    n={mem['n']} E={mem['expectancy']} PF={mem['PF']} WR={mem['win_rate']} power={mem['power']}"
    )
    print(
        f"TrendBias n={tb['n']} E={tb['expectancy']} PF={tb['PF']} WR={tb['win_rate']} power={tb['power']}"
    )
    for sym, al in pooled["always_long_per_instrument"].items():
        print(
            f"Always-Long[{sym}] n={al['n']} E={al['expectancy']} PF={al['PF']} WR={al['win_rate']} power={al['power']}"
        )
    print(f"Case call: {pooled['case_call']['case']}")
    print(f"JSON: {scoreboard_path}")
    print(f"MD:   {md_path}")
    print(f"NOTE: {_NOTE_PATH}")
    print("DESCRIPTIVE ONLY — economic_claims_allowed=false — object unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
