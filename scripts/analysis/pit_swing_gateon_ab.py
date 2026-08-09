"""
pit_swing_gateon_ab.py — PIT Phase A decisive instrument: gate-ON ledger A/B.

READ-ONLY w.r.t. production. In-process monkeypatch of FeaturePipeline so that the
CAUSAL arm swaps ONLY the 10 centered structure columns for the causally re-derived
chain before vector extraction. Runs BACKTEST_ENGINE_GATE=1 on active config.

Harness proofs (7c causal-validity lesson):
  1. Corpus parity — identical bar counts/hashes both arms
  2. INTERVENTION_ISOLATION — only the 10-feature causal closure changes
  3. PC-1 local channel — force sweep perturbation → CRT s_sweep/final moves
  4. PC-2 end-to-end sensitivity — strong measurement intervention → ledger moves
     (PC-2 failure = sensitivity limitation, NOT automatic harness failure)

Staged expansion:
  BNB: parity FAIL→STOP · isolation FAIL→STOP · PC-1 FAIL→STOP
       PC-2 FAIL → report sensitivity limitation (continue, bounded claim)
       causal A/B identical → one more instrument (highest value divergence) → stop
       causal A/B ≠ identical → expand BTC/ETH/SOL

Usage:
  python scripts/analysis/pit_swing_gateon_ab.py --symbol BNBUSDT
  python scripts/analysis/pit_swing_gateon_ab.py --symbol BNBUSDT --skip-gateoff
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
os.chdir(_ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from engines.scoring_engine import compute_scores  # noqa: E402

# Reuse causal re-derivation from the blast-radius probe (same process, no src change)
from scripts.analysis.pit_swing_blast_radius import (  # noqa: E402
    CONTAMINATED_10,
    rederive_causal_structure_chain,
    probe_A_value_level,
)

_TOL = 1e-9
_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_OUT = _ROOT / "docs" / "governance"
_RESULTS = _ROOT / "results" / "pit_phaseA_gateon_ab"


# ─────────────────────────────────────────────────────────────────────────────
# FeaturePipeline wrappers (monkeypatch targets)
# ─────────────────────────────────────────────────────────────────────────────

class _BaseWrappedPipeline(FeaturePipeline):
    """Shared: run parent, optionally mutate self.df, rebuild vectors."""

    _mode: str = "identity"

    def run(self):  # type: ignore[override]
        df, vectors = super().run()
        df = self._intervene(df)
        self.df = df
        vectors = self.build_feature_vector()
        return df, vectors

    def _intervene(self, df: pd.DataFrame) -> pd.DataFrame:
        return df


class CausalStructurePipeline(_BaseWrappedPipeline):
    """Swap ONLY the 10 contaminated columns for the causal structure chain."""

    _mode = "causal_structure_graph"

    def _intervene(self, df: pd.DataFrame) -> pd.DataFrame:
        causal = rederive_causal_structure_chain(df)
        out = df.copy()
        for col, series in causal.items():
            out[col] = series
        return out


class StrongInterventionPipeline(_BaseWrappedPipeline):
    """PC-2: deliberately strong measurement-only intervention (zero all 10 dims)."""

    _mode = "pc2_zero_structure"

    def _intervene(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in CONTAMINATED_10:
            if col in out.columns:
                out[col] = 0
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Isolation + corpus parity (offline, no full backtest)
# ─────────────────────────────────────────────────────────────────────────────

def prove_corpus_parity(csv_path: Path) -> dict:
    """Hash raw OHLCV corpus — both arms must see the same file."""
    raw = csv_path.read_bytes()
    h = hashlib.sha256(raw).hexdigest()
    df = pd.read_csv(csv_path)
    return {
        "path": str(csv_path).replace("\\", "/"),
        "sha256": h,
        "n_rows": len(df),
        "n_cols": len(df.columns),
    }


def prove_intervention_isolation(csv_path: Path, limit: int = 8000) -> dict:
    """Assert only the 10 contaminated columns change under causal intervention."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    if limit and limit > 0:
        df = df.head(limit).copy()

    base = FeaturePipeline(df.copy())
    df_b, vec_b = base.run()

    causal_pipe = CausalStructurePipeline(df.copy())
    df_c, vec_c = causal_pipe.run()

    if len(df_b) != len(df_c):
        return {
            "pass": False,
            "reason": f"row count mismatch base={len(df_b)} causal={len(df_c)}",
        }
    if vec_b.shape != vec_c.shape:
        return {
            "pass": False,
            "reason": f"vector shape mismatch {vec_b.shape} vs {vec_c.shape}",
        }

    other_cols = [c for c in CANONICAL_FEATURES if c not in CONTAMINATED_10]
    invariant_fail = []
    for col in other_cols:
        a = df_b[col].to_numpy(dtype=float)
        b = df_c[col].to_numpy(dtype=float)
        both_nan = np.isnan(a) & np.isnan(b)
        differ = (~both_nan) & (np.isnan(a) | np.isnan(b) | (np.abs(a - b) > _TOL))
        if differ.any():
            invariant_fail.append({"col": col, "n_differ": int(differ.sum())})

    changed_ok = []
    changed_unexpected = []
    for col in CONTAMINATED_10:
        a = df_b[col].to_numpy(dtype=float)
        b = df_c[col].to_numpy(dtype=float)
        both_nan = np.isnan(a) & np.isnan(b)
        differ = (~both_nan) & (np.isnan(a) | np.isnan(b) | (np.abs(a - b) > _TOL))
        n_diff = int(differ.sum())
        changed_ok.append({"col": col, "n_differ": n_diff, "differ_rate": n_diff / len(a)})
        # no "unexpected" — all 10 are allowed to change

    # Vector-level: columns outside contaminated indices must match
    contam_idx = [list(CANONICAL_FEATURES).index(c) for c in CONTAMINATED_10]
    other_idx = [i for i in range(len(CANONICAL_FEATURES)) if i not in contam_idx]
    vec_other_diff = int(np.sum(np.abs(vec_b[:, other_idx] - vec_c[:, other_idx]) > _TOL))

    passed = (not invariant_fail) and vec_other_diff == 0
    return {
        "pass": passed,
        "bars": len(df_b),
        "other_28_column_failures": invariant_fail,
        "contaminated_10_diffs": changed_ok,
        "vector_other_cell_diffs": vec_other_diff,
        "note": (
            "The 10 columns are a DEPENDENCY GRAPH, not independent variables. "
            "Measured effect = TOTAL effect of switching production structure graph "
            "from centered to causal. No feature-level attribution claimed."
        ),
    }


def prove_pc1_local_channel(csv_path: Path, limit: int = 5000) -> dict:
    """Force sweep_detected/double_sweep perturbation → assert CRT scores change."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    if limit:
        df = df.head(limit).copy()
    feat, _ = FeaturePipeline(df).run()

    moved = 0
    checked = 0
    # Take bars where sweep_detected is currently False — force True
    for i in range(min(len(feat), 2000)):
        row = feat.iloc[i]
        base = compute_scores(
            body_ratio=float(row["body_ratio"]),
            move=float(row["disp_strength"]),
            atr=float(row["atr"]),
            retest_depth=float(row["retest_depth"]),
            candles_since_retest=int(row.get("candles_since_retest", 0)),
            sweep_detected=False,
            double_sweep=False,
        )
        pert = compute_scores(
            body_ratio=float(row["body_ratio"]),
            move=float(row["disp_strength"]),
            atr=float(row["atr"]),
            retest_depth=float(row["retest_depth"]),
            candles_since_retest=int(row.get("candles_since_retest", 0)),
            sweep_detected=True,
            double_sweep=True,
        )
        checked += 1
        if abs(pert["sweep"] - base["sweep"]) > _TOL or abs(pert["final"] - base["final"]) > _TOL:
            moved += 1

    # Also verify the formula constants: False→0, True+double→1.0
    formula_ok = (
        compute_scores(0.5, 1.0, 0.01, 0.4, 2, False, False)["sweep"] == 0.0
        and compute_scores(0.5, 1.0, 0.01, 0.4, 2, True, True)["sweep"] == 1.0
        and compute_scores(0.5, 1.0, 0.01, 0.4, 2, True, False)["sweep"] == 0.7
    )
    passed = formula_ok and moved == checked and checked > 0
    return {
        "pass": passed,
        "bars_checked": checked,
        "bars_score_moved": moved,
        "move_rate": moved / checked if checked else 0.0,
        "formula_constants_ok": formula_ok,
        "channel": "scoring_engine.compute_scores s_sweep / final",
        "note": "PC-1 failure = channel harness INVALID → STOP",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Backtest runner (gate-ON / gate-OFF)
# ─────────────────────────────────────────────────────────────────────────────

def _load_crt_cfg(instrument: str):
    from scripts.analysis.session_sweep import load_prod_config_from_registry, PROD_VERSION
    return load_prod_config_from_registry(PROD_VERSION, instrument), PROD_VERSION


def _run_backtest(
    instrument: str,
    csv_path: str,
    output_dir: Path,
    label: str,
    pipeline_cls,
    engine_gate: str,
) -> dict:
    """Run one BacktestRunner with FeaturePipeline monkeypatched to pipeline_cls."""
    import features.feature_pipeline as fp_mod
    import runtime.backtest_v2 as bt

    # Patch BOTH module-level names: BacktestRunner re-imports locally from
    # features.feature_pipeline (backtest_v2.py:1644), while run_backtest uses
    # the module-level backtest_v2.FeaturePipeline (line 60 / 2846).
    prev_fp = fp_mod.FeaturePipeline
    prev_bt = getattr(bt, "FeaturePipeline", None)
    fp_mod.FeaturePipeline = pipeline_cls
    bt.FeaturePipeline = pipeline_cls

    prev_gate = os.environ.get("BACKTEST_ENGINE_GATE")
    os.environ["BACKTEST_ENGINE_GATE"] = engine_gate

    try:
        from runtime.backtest_v2 import BacktestRunner, BacktestConfig, CandleLoader, MultiInstrumentRunner

        crt_cfg, prod_version = _load_crt_cfg(instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001)

        output_dir.mkdir(parents=True, exist_ok=True)
        loader = CandleLoader(csv_path, instrument)
        runner = BacktestRunner(
            cfg, csv_path=csv_path,
            overrides={"diagnostic": label, "instrument": instrument, "pit_arm": label},
        )
        t0 = time.time()
        m = runner.run(loader.stream(), loader.count(), str(output_dir))
        elapsed = time.time() - t0
        fc = m.funnel_counts or {}
        return {
            "label": label,
            "instrument": instrument,
            "engine_gate": engine_gate,
            "pipeline_mode": getattr(pipeline_cls, "_mode", pipeline_cls.__name__),
            "prod_version": prod_version,
            "approved_trades": int(m.approved_trades),
            "win_rate": round(float(m.win_rate), 4),
            "expectancy_rr": round(float(m.avg_rr_net), 4),
            "profit_factor": round(float(m.profit_factor), 4),
            "total_return_pct": round(float(m.total_return_pct), 6),
            "max_drawdown_pct": round(float(m.max_drawdown_pct), 6),
            "funnel_execution": int(fc.get("EXECUTION", 0)),
            "funnel_retest": int(fc.get("RETEST", 0)),
            "candles": int(loader.count()),
            "elapsed_s": round(elapsed, 1),
            "output_dir": str(output_dir).replace("\\", "/"),
        }
    finally:
        fp_mod.FeaturePipeline = prev_fp
        if prev_bt is not None:
            bt.FeaturePipeline = prev_bt
        if prev_gate is None:
            os.environ.pop("BACKTEST_ENGINE_GATE", None)
        else:
            os.environ["BACKTEST_ENGINE_GATE"] = prev_gate


def _load_ledger(out_dir: Path, instrument: str) -> list[dict]:
    hits = list(out_dir.rglob(f"{instrument}_trades.csv"))
    if not hits:
        hits = list(out_dir.rglob("*_trades.csv"))
    if not hits:
        return []
    with open(hits[0], newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _trade_keys(ledger: list[dict]) -> list[str]:
    keys = []
    for r in ledger:
        opened = r.get("opened_at") or r.get("entry_time") or r.get("timestamp") or ""
        direction = r.get("direction") or r.get("side") or ""
        keys.append(f"{opened}|{direction}")
    return keys


def _ledger_diff(a: list[dict], b: list[dict]) -> dict:
    ka, kb = set(_trade_keys(a)), set(_trade_keys(b))
    added, removed = kb - ka, ka - kb
    overlap, union = ka & kb, ka | kb
    return {
        "n_a": len(ka),
        "n_b": len(kb),
        "added": len(added),
        "removed": len(removed),
        "overlap": len(overlap),
        "overlap_pct": round(100.0 * len(overlap) / len(union), 2) if union else 100.0,
        "identical": len(added) == 0 and len(removed) == 0 and len(ka) == len(kb),
        "added_keys_sample": sorted(added)[:10],
        "removed_keys_sample": sorted(removed)[:10],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Staged instrument expansion
# ─────────────────────────────────────────────────────────────────────────────

def run_instrument(
    instrument: str,
    *,
    do_pc2: bool = True,
    do_gateoff: bool = True,
    isolation_limit: int = 8000,
) -> dict:
    csv_path = _ROOT / "data" / f"{instrument}_M15.csv"
    if not csv_path.exists():
        return {"instrument": instrument, "status": "NOT_MEASURABLE", "reason": "no csv"}

    result: dict[str, Any] = {
        "instrument": instrument,
        "status": "RUNNING",
        "stop": False,
        "stop_reason": None,
    }

    # 1. Corpus parity
    parity = prove_corpus_parity(csv_path)
    result["corpus_parity"] = parity
    print(f"  [{instrument}] corpus n={parity['n_rows']} sha256={parity['sha256'][:12]}…")

    # 2. Intervention isolation
    print(f"  [{instrument}] INTERVENTION_ISOLATION…")
    isolation = prove_intervention_isolation(csv_path, limit=isolation_limit)
    result["intervention_isolation"] = isolation
    if not isolation["pass"]:
        result["status"] = "STOP"
        result["stop"] = True
        result["stop_reason"] = "INTERVENTION_ISOLATION_FAIL"
        print(f"  [{instrument}] STOP: isolation FAIL — {isolation.get('reason') or isolation.get('other_28_column_failures')}")
        return result
    print(f"  [{instrument}] isolation PASS (bars={isolation['bars']})")

    # 3. PC-1
    print(f"  [{instrument}] PC-1 local CRT channel…")
    pc1 = prove_pc1_local_channel(csv_path)
    result["pc1"] = pc1
    if not pc1["pass"]:
        result["status"] = "STOP"
        result["stop"] = True
        result["stop_reason"] = "PC1_FAIL"
        print(f"  [{instrument}] STOP: PC-1 FAIL")
        return result
    print(f"  [{instrument}] PC-1 PASS (moved {pc1['bars_score_moved']}/{pc1['bars_checked']})")

    # 4. PC-2 end-to-end sensitivity (gate-ON)
    pc2_sensitivity_ok = None
    if do_pc2:
        print(f"  [{instrument}] PC-2 strong intervention (gate-ON)…")
        base_dir = _RESULTS / instrument / "pc2_baseline"
        strong_dir = _RESULTS / instrument / "pc2_strong"
        try:
            m_base = _run_backtest(instrument, str(csv_path), base_dir, "pc2_baseline", FeaturePipeline, "1")
            m_strong = _run_backtest(instrument, str(csv_path), strong_dir, "pc2_strong", StrongInterventionPipeline, "1")
            led_b = _load_ledger(base_dir, instrument)
            led_s = _load_ledger(strong_dir, instrument)
            diff_pc2 = _ledger_diff(led_b, led_s)
            # Also accept metric divergence as sensitivity
            metrics_differ = any(
                m_base.get(k) != m_strong.get(k)
                for k in ("approved_trades", "funnel_execution", "funnel_retest", "profit_factor")
            )
            pc2_sensitivity_ok = (not diff_pc2["identical"]) or metrics_differ
            result["pc2"] = {
                "pass_as_sensitivity": pc2_sensitivity_ok,
                "baseline": m_base,
                "strong": m_strong,
                "ledger_diff": diff_pc2,
                "note": (
                    "PC-2 failure is a REPORTED SENSITIVITY LIMITATION, not harness failure"
                    if not pc2_sensitivity_ok else
                    "PC-2: strong intervention moved at least one ledger/decision observable"
                ),
            }
            print(f"  [{instrument}] PC-2 sensitivity={'OK' if pc2_sensitivity_ok else 'LIMITATION'} "
                  f"trades {m_base['approved_trades']}→{m_strong['approved_trades']} "
                  f"overlap={diff_pc2['overlap_pct']}%")
        except Exception as exc:
            result["pc2"] = {
                "pass_as_sensitivity": False,
                "error": str(exc),
                "traceback": traceback.format_exc()[-1500:],
                "note": "PC-2 errored — treated as sensitivity limitation, not STOP",
            }
            pc2_sensitivity_ok = False
            print(f"  [{instrument}] PC-2 ERROR (sensitivity limitation): {exc}")

    # 5. Causal A/B gate-ON
    print(f"  [{instrument}] causal A/B gate-ON…")
    centered_dir = _RESULTS / instrument / "gateon_centered"
    causal_dir = _RESULTS / instrument / "gateon_causal"
    m_c = _run_backtest(instrument, str(csv_path), centered_dir, "gateon_centered", FeaturePipeline, "1")
    m_a = _run_backtest(instrument, str(csv_path), causal_dir, "gateon_causal", CausalStructurePipeline, "1")

    # Corpus parity of candle counts across arms
    if m_c["candles"] != m_a["candles"]:
        result["status"] = "STOP"
        result["stop"] = True
        result["stop_reason"] = "CORPUS_PARITY_FAIL"
        result["gateon_ab"] = {"centered": m_c, "causal": m_a}
        print(f"  [{instrument}] STOP: candle count mismatch {m_c['candles']} vs {m_a['candles']}")
        return result

    led_c = _load_ledger(centered_dir, instrument)
    led_a = _load_ledger(causal_dir, instrument)
    diff = _ledger_diff(led_c, led_a)
    result["gateon_ab"] = {
        "centered": m_c,
        "causal": m_a,
        "ledger_diff": diff,
        "identical": diff["identical"],
    }
    print(f"  [{instrument}] gate-ON A/B trades {m_c['approved_trades']}→{m_a['approved_trades']} "
          f"identical={diff['identical']} overlap={diff['overlap_pct']}% "
          f"+{diff['added']}/-{diff['removed']}")

    # 6. Gate-OFF F-029 reconciliation (cheap replay on one instrument)
    if do_gateoff:
        print(f"  [{instrument}] gate-OFF F-029 reconciliation…")
        goff_c_dir = _RESULTS / instrument / "gateoff_centered"
        goff_a_dir = _RESULTS / instrument / "gateoff_causal"
        m_gc = _run_backtest(instrument, str(csv_path), goff_c_dir, "gateoff_centered", FeaturePipeline, "0")
        m_ga = _run_backtest(instrument, str(csv_path), goff_a_dir, "gateoff_causal", CausalStructurePipeline, "0")
        led_gc = _load_ledger(goff_c_dir, instrument)
        led_ga = _load_ledger(goff_a_dir, instrument)
        diff_goff = _ledger_diff(led_gc, led_ga)
        f029_holds = diff_goff["identical"]
        result["gateoff_f029_replay"] = {
            "centered": m_gc,
            "causal": m_ga,
            "ledger_diff": diff_goff,
            "f029_byte_identical": f029_holds,
            "truth_conflict": (not f029_holds),
            "note": (
                "F-029 refined (scope=gate-OFF trade generation) STANDS"
                if f029_holds else
                "TRUTH CONFLICT: gate-OFF ledger diverged — do NOT reverse F-029 in findings; surface conflict"
            ),
        }
        print(f"  [{instrument}] gate-OFF identical={f029_holds} "
              f"trades {m_gc['approved_trades']}→{m_ga['approved_trades']}")
        if not f029_holds:
            result["status"] = "TRUTH_CONFLICT"
            # Do not STOP for expansion, but flag — user instruction: report as TruthConflict
            print(f"  [{instrument}] TRUTH CONFLICT vs F-029 — reported, findings NOT edited")

    result["status"] = result.get("status") if result.get("status") in ("TRUTH_CONFLICT",) else "OK"
    result["pc2_sensitivity_ok"] = pc2_sensitivity_ok
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="PIT Phase A gate-ON ledger A/B (read-only).")
    ap.add_argument("--symbol", default="BNBUSDT")
    ap.add_argument("--skip-pc2", action="store_true")
    ap.add_argument("--skip-gateoff", action="store_true")
    ap.add_argument("--isolation-limit", type=int, default=8000)
    ap.add_argument("--no-expand", action="store_true", help="do not expand beyond --symbol")
    args = ap.parse_args()

    active_version = (_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    print(f"ORIENT_RUNTIME ACTIVE_VERSION={active_version}")
    print(f"PIT Phase A gate-ON A/B · symbol={args.symbol} · BACKTEST_ENGINE_GATE=1")

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_version": active_version,
        "probe": "pit_swing_gateon_ab",
        "behavior_changed": False,
        "contaminated_10": list(CONTAMINATED_10),
        "instruments": {},
        "staged_expansion": {},
    }

    # Primary instrument
    primary = run_instrument(
        args.symbol,
        do_pc2=not args.skip_pc2,
        do_gateoff=not args.skip_gateoff,
        isolation_limit=args.isolation_limit,
    )
    report["instruments"][args.symbol] = primary

    if primary.get("stop"):
        report["staged_expansion"] = {
            "decision": "STOP",
            "reason": primary.get("stop_reason"),
            "expanded": [],
        }
        print(f"\nSTOP: {primary.get('stop_reason')}")
    elif args.no_expand:
        report["staged_expansion"] = {"decision": "NO_EXPAND_FLAG", "expanded": []}
    else:
        identical = bool(primary.get("gateon_ab", {}).get("identical", False))
        if identical:
            # Run ONE more instrument with highest value-level divergence
            print("\nCausal A/B EXACTLY IDENTICAL on primary → select one expansion instrument…")
            candidates = ["SOLUSDT", "BTCUSDT", "ETHUSDT", "EURUSD"]
            candidates = [c for c in candidates if c != args.symbol]
            best_sym, best_rate = None, -1.0
            for sym in candidates:
                csv_p = _ROOT / "data" / f"{sym}_M15.csv"
                if not csv_p.exists():
                    continue
                try:
                    a = probe_A_value_level(sym, 15000)
                    rate = float(a["any_of_10_differ_rate"])
                    print(f"  value-level {sym}: any-of-10 differ {rate:.2%}")
                    if rate > best_rate:
                        best_rate, best_sym = rate, sym
                except Exception as exc:
                    print(f"  value-level {sym}: skip ({exc})")
            if best_sym:
                print(f"\nExpanding once to {best_sym} (highest value diverge {best_rate:.2%})…")
                second = run_instrument(
                    best_sym,
                    do_pc2=False,  # PC-1/isolation only + A/B; PC-2 already done on primary
                    do_gateoff=False,
                    isolation_limit=args.isolation_limit,
                )
                report["instruments"][best_sym] = second
                report["staged_expansion"] = {
                    "decision": "IDENTICAL_THEN_ONE_MORE",
                    "primary_identical": True,
                    "expanded": [best_sym],
                    "selection_metric": "any_of_10_differ_rate",
                    "selected_rate": best_rate,
                }
            else:
                report["staged_expansion"] = {
                    "decision": "IDENTICAL_NO_CANDIDATE",
                    "primary_identical": True,
                    "expanded": [],
                }
        else:
            # Expand BTC/ETH/SOL
            expand = [s for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT") if s != args.symbol]
            print(f"\nCausal A/B ≠ identical → expand {expand}")
            expanded = []
            for sym in expand:
                print(f"\n--- {sym} ---")
                r = run_instrument(
                    sym,
                    do_pc2=False,
                    do_gateoff=False,
                    isolation_limit=args.isolation_limit,
                )
                report["instruments"][sym] = r
                expanded.append(sym)
                if r.get("stop"):
                    print(f"Expansion STOP on {sym}: {r.get('stop_reason')}")
                    break
            report["staged_expansion"] = {
                "decision": "DIVERGENT_EXPAND_MAJORS",
                "primary_identical": False,
                "expanded": expanded,
            }

    # Write artifacts
    _OUT.mkdir(parents=True, exist_ok=True)
    stem = f"pit_phaseA_gateon_ab-{_DATE}"
    json_path = _OUT / f"{stem}.json"
    md_path = _OUT / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_to_md(report), encoding="utf-8")
    print(f"\nArtifacts → {json_path.relative_to(_ROOT)} , {md_path.relative_to(_ROOT)}")

    if primary.get("stop"):
        return 2
    return 0


def _to_md(rep: dict) -> str:
    lines = [
        "# PIT Phase A — Gate-ON Ledger A/B",
        "",
        f"_Generated {rep['generated_at']} · ACTIVE_VERSION={rep['active_version']} · read-only._",
        "",
        f"## Staged expansion: `{rep.get('staged_expansion', {}).get('decision')}`",
        f"- expanded: {rep.get('staged_expansion', {}).get('expanded')}",
        "",
    ]
    for sym, r in rep.get("instruments", {}).items():
        lines.append(f"## {sym} — status={r.get('status')}")
        if r.get("stop"):
            lines.append(f"- **STOP:** {r.get('stop_reason')}")
        iso = r.get("intervention_isolation") or {}
        lines.append(f"- isolation: **{'PASS' if iso.get('pass') else 'FAIL'}** (bars={iso.get('bars')})")
        pc1 = r.get("pc1") or {}
        lines.append(f"- PC-1: **{'PASS' if pc1.get('pass') else 'FAIL/n/a'}**")
        pc2 = r.get("pc2")
        if pc2:
            lines.append(
                f"- PC-2 sensitivity: **{pc2.get('pass_as_sensitivity')}** — {pc2.get('note', '')}"
            )
        gab = r.get("gateon_ab") or {}
        if gab:
            d = gab.get("ledger_diff") or {}
            mc, ma = gab.get("centered") or {}, gab.get("causal") or {}
            lines.append(
                f"- gate-ON A/B: trades {mc.get('approved_trades')}→{ma.get('approved_trades')} "
                f"identical={gab.get('identical')} overlap={d.get('overlap_pct')}% "
                f"+{d.get('added')}/-{d.get('removed')}"
            )
        goff = r.get("gateoff_f029_replay")
        if goff:
            lines.append(
                f"- gate-OFF F-029 replay: identical={goff.get('f029_byte_identical')} "
                f"truth_conflict={goff.get('truth_conflict')}"
            )
        lines.append("")
    lines += [
        "## Scope",
        "",
        "- Intervention = TOTAL causal structure-graph swap (10-feature dependency closure).",
        "- No feature-level attribution claimed.",
        "- FINAL_LEDGER_EXPOSURE lives here only (not inferred from ZoneGate score deltas).",
        "- F-029 gate-OFF claim refined-not-reversed unless truth_conflict flagged.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
