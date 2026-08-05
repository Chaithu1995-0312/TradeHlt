"""
CRT Semantic Parity — Sweep Driver (F-069 program)
=====================================================
Research-only. Determines whether CRTStateResolver can reproduce
BacktestRunner's semantic CRT-state decisions through configuration tuning
alone (Stage A: resolver-only) and, as a separately-labeled one-way
diagnostic, how sensitive the residual is to engine-side thresholds
(Stage B). NEVER writes to a tracked config path — every candidate config is
materialized under a content-addressed scratch tree and path-confinement is
asserted before every write.

Pre-registration (predictions frozen BEFORE this driver's first run):
    docs/research/preregistration-crt-semantic-parity.md

DEFECT UNDER MEASUREMENT
-------------------------
Baseline (config-only, injection=none, engine_mode=exit, XAUUSD M15,
47,197 aligned bars): 88.16% agreement (41,607/47,197). RANGE/SWEEP/
DISPLACEMENT already >=96% recall; EXPANSION recall is 10.77% (498/4,625)
despite a *reachable* feature vector (state_to-only oracle diagnostic
recovers EXPANSION to ~99% recall) — the defect is entry/exit TIMING, not a
missing signal. See the pre-registration doc for the frozen per-state table.

PREDICTION (frozen; already partially tested during driver development)
-------------------------------------------------------------------------
`thresholds.continuous_disp_to_expansion=True` (A1) was hypothesized to
recover EXPANSION recall. Directly measured before this driver existed: it
does NOT — it exactly reproduces the pre-B1h over-firing state (78.03%
agreement, EXPANSION res_n=10,600 vs engine 4,625). That specific
sub-hypothesis is REFUTED; A1 is still evaluated first (as A1a, so the
result lands in the ledger rather than being silently assumed), but the
search's real weight is on A2 (funnel timing) and A3 (TTL).

NON-TRANSITIVE CLOSURE
------------------------
A PROMOTE-eligible candidate here grants NO authority to write
`configs/formulas/market_crt_states.yaml` — that requires the separate,
explicitly-confirmed --promote path (Step 11 of the F-069 implementation
plan), which is not part of this script. Stage B grants NO authority to
modify CRTConfig/production config; it is a one-way sensitivity diagnostic.

USAGE
-----
    python scripts/research/crt_parity_sweep.py --stage A --max-candidates 5
    python scripts/research/crt_parity_sweep.py --stage A
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "research"))

import crt_state_confusion_matrix as cm  # noqa: E402
import crt_parity_classifier as cpc  # noqa: E402

CERT_VERSION = "1.0.0"

DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
DEFAULT_EVENTS = _ROOT / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_events.jsonl"
DEFAULT_BASE_CONFIG = _ROOT / "configs" / "formulas" / "market_crt_states.yaml"
SWEEP_ROOT = _ROOT / "results" / "analysis" / "crt_parity_sweep"

POWERED_STATES = ("RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION")  # engine_n >= MIN_CELL_N always
ANTI_SIMPSON_TOLERANCE_PP = 5.0
CONVERGENCE_MIN_GAIN_PP = 0.10
S2_MAX_CANDIDATES_STAGE_A = 250
S2_MAX_CANDIDATES_STAGE_B = 24

# ── Stage-A parameter groups (pre-registration doc, in priority order) ─────

A1_PARAMS: dict[str, list[Any]] = {
    "thresholds.continuous_disp_to_expansion": [True],  # baseline (False) always tried as cand 0
}
A2_PARAMS: dict[str, list[Any]] = {
    "thresholds.expansion_atr_min_distance": [0.15, 0.20, 0.45],
    "thresholds.max_sweep_age_candles": [10, 30],
    "thresholds.max_displacement_age_candles": [2, 5, 8],
    "thresholds.atr_min_displacement": [0.9, 1.5],
    "thresholds.body_ratio_min": [0.55, 0.70],
    "thresholds.atr_multiplier_min": [0.8, 1.5],
}
A3_PARAMS: dict[str, list[Any]] = {
    "thresholds.max_expansion_age_candles": [120, 250, 900],
    "thresholds.max_expansion_age_hours": [24, 999],
}
A4_PARAMS: dict[str, list[Any]] = {
    "thresholds.lifecycle.htf_protect_states": [
        ["EXPANSION", "RETEST", "DISPLACEMENT"], ["EXPANSION"],
    ],
    "thresholds.lifecycle.htf_protect_execution": [False],
    "thresholds.lifecycle.shadow_on_htf_displacement_reset": [False],
    "thresholds.range_atr_period": [4, 20],
}
A5_PARAMS: dict[str, list[Any]] = {
    "thresholds.retest_depth_max": [0.02, 0.04, 0.25],
    "thresholds.retest_atr_depth_fraction": [0.25],
}
A6_PARAMS: dict[str, list[Any]] = {
    "thresholds.lifecycle.pending_displacement_ttl_candles": [2, 8],
}
STAGE_A_GROUPS: list[tuple[str, dict[str, list[Any]]]] = [
    ("A1", A1_PARAMS), ("A2", A2_PARAMS), ("A3", A3_PARAMS),
    ("A4", A4_PARAMS), ("A5", A5_PARAMS), ("A6", A6_PARAMS),
]


# ── YAML delta application (never touches the tracked file) ────────────────

def _get_nested(d: dict, dotted: str) -> Any:
    node = d
    for key in dotted.split("."):
        node = node[key]
    return node


def _set_nested(d: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    node = d
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value


def apply_delta(base_cfg: dict, delta: dict[str, Any]) -> dict:
    cand = copy.deepcopy(base_cfg)
    for dotted, value in delta.items():
        _set_nested(cand, dotted, value)
    return cand


def delta_sha12(delta: dict[str, Any]) -> str:
    canonical = json.dumps(delta, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def materialize_candidate(base_cfg: dict, delta: dict[str, Any], sweep_root: Path) -> Path:
    """Write a candidate YAML under sweep_root/candidates/. Content-addressed
    on the delta; never touches any tracked path. Hard path-confinement
    guard — the only thing standing between a driver bug and clobbering the
    live resolver config.
    """
    import yaml

    cand_cfg = apply_delta(base_cfg, delta)
    sha = delta_sha12(delta)
    out_dir = (sweep_root / "candidates").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cand_path = (out_dir / f"cand_{sha}.yaml").resolve()
    assert cand_path.is_relative_to(sweep_root.resolve()), (
        f"REFUSING write outside sweep root: {cand_path}"
    )
    if not cand_path.exists():
        cand_path.write_text(yaml.safe_dump(cand_cfg, sort_keys=False), encoding="utf-8")
    return cand_path


# ── Per-candidate evaluation ────────────────────────────────────────────────

def per_state_summary(report: "cm.ConfusionReport") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in cm.ALL_STATES:
        eng_n = report.engine_counts.get(s, 0)
        res_n = report.resolver_counts.get(s, 0)
        tp = report.matrix.get((s, s), 0)
        if not eng_n and not res_n:
            continue
        out[s] = {
            "engine_n": eng_n, "resolver_n": res_n, "tp": tp,
            "recall": (tp / eng_n) if eng_n else None,
            "precision": (tp / res_n) if res_n else None,
            "powered": eng_n >= cpc.MIN_CELL_N,
        }
    return out


def anti_simpson_ok(
    baseline_per_state: dict[str, dict[str, Any]],
    candidate_per_state: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    """S3: reject a candidate that raises overall agreement while dropping
    any POWERED per-state recall by more than ANTI_SIMPSON_TOLERANCE_PP.
    """
    violations = []
    for s, base in baseline_per_state.items():
        if not base.get("powered") or base.get("recall") is None:
            continue
        cand = candidate_per_state.get(s)
        cand_recall = cand.get("recall") if cand else 0.0
        if cand_recall is None:
            cand_recall = 0.0
        drop_pp = (base["recall"] - cand_recall) * 100.0
        if drop_pp > ANTI_SIMPSON_TOLERANCE_PP:
            violations.append(f"{s}: recall {base['recall']:.2%} -> {cand_recall:.2%} "
                               f"(-{drop_pp:.1f}pp)")
    return (len(violations) == 0), violations


def evaluate_candidate(
    engine_ctx: "cm.PreparedEngineContext",
    *,
    iter_num: int,
    stage: str,
    delta: dict[str, Any],
    cand_path: Optional[Path],
    engine_overrides: Optional[dict[str, Any]] = None,
    enriched: Optional[Any] = None,
    baseline_agreement: int,
    baseline_total: int,
    best_agreement: int,
) -> dict[str, Any]:
    t0 = time.time()
    report, res_meta = cm.run_once(
        engine_ctx, config_path=cand_path, engine_mode="exit", injection="none",
        enriched=enriched, max_episodes=100_000,  # effectively uncapped -> true episode_n
    )
    elapsed = time.time() - t0

    per_state = per_state_summary(report)
    eng_aligned_len = report.total
    n_mismatch_episodes = len(report.divergence_episodes)  # true total (uncapped above)
    mismatches = list(report.divergence_episodes[:500])

    return {
        "cert_version": CERT_VERSION,
        "iter": iter_num,
        "stage": stage,
        "cand_sha": cand_path.stem if cand_path else "baseline",
        "candidate_path": str(cand_path.relative_to(_ROOT)) if cand_path else None,
        "config_delta": delta,
        "engine_overrides": engine_overrides or {},
        "engine_mode": "exit",
        "injection": "none",
        "agreement": report.agreement,
        "total": report.total,
        "agreement_rate": report.agreement / report.total if report.total else 0.0,
        "delta_vs_baseline_pp": (
            (report.agreement / report.total) - (baseline_agreement / baseline_total)
        ) * 100.0 if report.total and baseline_total else 0.0,
        "delta_vs_best_pp": (
            (report.agreement / eng_aligned_len) - (best_agreement / eng_aligned_len)
        ) * 100.0 if eng_aligned_len else 0.0,
        "per_state": per_state,
        "matrix": {f"{e}|{r}": n for (e, r), n in report.matrix.items()},
        "mismatch_n": report.total - report.agreement,
        "episode_n": n_mismatch_episodes,
        "mismatches": mismatches,
        "mismatches_truncated_at": 500,
        "elapsed_s": round(elapsed, 2),
        "states_sha256": hashlib.sha256(
            json.dumps(res_meta.get("resolver_counts", {}), sort_keys=True).encode()
        ).hexdigest()[:16],
    }


def write_iteration(sweep_root: Path, record: dict[str, Any]) -> Path:
    iters_dir = (sweep_root / "iters").resolve()
    iters_dir.mkdir(parents=True, exist_ok=True)
    path = (iters_dir / f"iter_{record['iter']:04d}.json").resolve()
    assert path.is_relative_to(sweep_root.resolve())
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    ledger_path = (sweep_root / "ledger.jsonl").resolve()
    assert ledger_path.is_relative_to(sweep_root.resolve())
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "iter": record["iter"], "stage": record["stage"], "cand_sha": record["cand_sha"],
            "config_delta": record["config_delta"], "engine_overrides": record["engine_overrides"],
            "agreement_rate": record["agreement_rate"],
            "delta_vs_baseline_pp": record["delta_vs_baseline_pp"],
            "mismatch_n": record["mismatch_n"], "elapsed_s": record["elapsed_s"],
            "anti_simpson_ok": record.get("anti_simpson_ok"),
        }, default=str) + "\n")
    return path


def write_iteration_b(sweep_root: Path, record: dict[str, Any]) -> Path:
    """Stage B's own namespace (iters_b/ + ledger_b.jsonl) — DELIBERATELY
    separate from write_iteration()'s iters/ + ledger.jsonl. Stage A and
    Stage B each restart their own iter counter at 1; sharing a namespace
    would let Stage B silently overwrite Stage A's canonical artifacts
    (iter_0001.json in particular is Stage A's baseline, cited directly in
    F-069 and CLAUDE.md — this collision was caught and fixed during the
    F-069 program itself after Stage B's first run clobbered it).
    """
    iters_dir = (sweep_root / "iters_b").resolve()
    iters_dir.mkdir(parents=True, exist_ok=True)
    path = (iters_dir / f"iter_{record['iter']:04d}.json").resolve()
    assert path.is_relative_to(sweep_root.resolve())
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    ledger_path = (sweep_root / "ledger_b.jsonl").resolve()
    assert ledger_path.is_relative_to(sweep_root.resolve())
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "iter": record["iter"], "stage": record["stage"], "label": record["label"],
            "engine_overrides": record["engine_overrides"],
            "resolver_config": record["resolver_config"],
            "agreement_rate": record["agreement_rate"],
            "delta_vs_baseline_pp": record["delta_vs_baseline_pp"],
            "mismatch_n": record["mismatch_n"], "elapsed_s": record["elapsed_s"],
            "anti_simpson_ok": record.get("anti_simpson_ok"),
            "authority": record["authority"],
        }, default=str) + "\n")
    return path


def write_latest(sweep_root: Path, best_record: dict[str, Any], all_deltas_so_far: dict) -> None:
    out = {
        "_doc": "Best-so-far CRT Semantic Parity Stage-A candidate. Research only (F-069).",
        "cert_version": CERT_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "best_iter": best_record["iter"],
        "best_cand_sha": best_record["cand_sha"],
        "config_delta": best_record["config_delta"],
        "agreement_rate": best_record["agreement_rate"],
        "delta_vs_baseline_pp": best_record["delta_vs_baseline_pp"],
        "per_state": best_record["per_state"],
    }
    path = (sweep_root / "crt_semantic_parity.LATEST.json").resolve()
    assert path.is_relative_to(sweep_root.resolve())
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


# ── Stage A orchestration ───────────────────────────────────────────────────

def run_stage_a(
    engine_ctx: "cm.PreparedEngineContext",
    *,
    sweep_root: Path,
    base_config_path: Path,
    max_candidates: int,
) -> dict[str, Any]:
    import yaml

    base_cfg = yaml.safe_load(base_config_path.read_text(encoding="utf-8"))
    enriched = cm.compute_enriched_frame(engine_ctx.ohlcv_path)

    iter_num = 0
    n_candidates = 0
    # Placeholder until the first _eval() call (the baseline itself) fills it in.
    baseline: dict[str, Any] = {"agreement": 0, "total": 0, "per_state": {}}

    def _eval(delta: dict[str, Any], best_agreement: int) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal iter_num, n_candidates
        cand_path = materialize_candidate(base_cfg, delta, sweep_root) if delta else None
        iter_num += 1
        n_candidates += 1
        record = evaluate_candidate(
            engine_ctx, iter_num=iter_num, stage="A", delta=delta, cand_path=cand_path,
            enriched=enriched,
            baseline_agreement=baseline["agreement"], baseline_total=baseline["total"],
            best_agreement=best_agreement,
        )
        cpc_per_state = {
            s: (d["engine_n"], d["resolver_n"], d["tp"]) for s, d in record["per_state"].items()
        }
        ok, violations = anti_simpson_ok(baseline["per_state"], record["per_state"])
        record["anti_simpson_ok"] = ok
        record["anti_simpson_violations"] = violations
        write_iteration(sweep_root, record)  # written AFTER anti_simpson fields are set
        print(
            f"  iter={iter_num:04d} stage=A delta={delta or '(baseline)'} "
            f"agreement={record['agreement_rate']:.4%} "
            f"({record['delta_vs_baseline_pp']:+.2f}pp) "
            f"anti_simpson={'OK' if ok else 'VIOLATED:' + '; '.join(violations)} "
            f"elapsed={record['elapsed_s']}s"
        )
        return record, cpc_per_state

    print("Baseline (empty delta)...")
    baseline_record, _ = _eval({}, best_agreement=0)
    baseline = {
        "agreement": baseline_record["agreement"], "total": baseline_record["total"],
        "per_state": baseline_record["per_state"],
    }
    best_record = baseline_record
    current_best_delta: dict[str, Any] = {}

    for group_name, params in STAGE_A_GROUPS:
        if n_candidates >= max_candidates:
            print(f"S2 budget reached ({max_candidates}); stopping before {group_name}.")
            break
        print(f"--- {group_name} ---")
        pass_start_rate = best_record["agreement_rate"]
        for param_name, values in params.items():
            best_for_param = current_best_delta.get(param_name, None)
            best_rate_for_param = best_record["agreement_rate"]
            for value in values:
                if n_candidates >= max_candidates:
                    break
                trial_delta = dict(current_best_delta)
                trial_delta[param_name] = value
                record, _ = _eval(trial_delta, best_agreement=best_record["agreement"])
                accept = record["anti_simpson_ok"] and record["agreement_rate"] > best_rate_for_param
                if accept:
                    best_rate_for_param = record["agreement_rate"]
                    best_for_param = value
                    if record["agreement_rate"] > best_record["agreement_rate"]:
                        best_record = record
            if best_for_param is not None:
                current_best_delta[param_name] = best_for_param
        pass_gain_pp = (best_record["agreement_rate"] - pass_start_rate) * 100.0
        print(f"  {group_name} pass gain: {pass_gain_pp:+.2f}pp "
              f"(best so far: {best_record['agreement_rate']:.4%})")
        write_latest(sweep_root, best_record, current_best_delta)
        if pass_gain_pp < CONVERGENCE_MIN_GAIN_PP and group_name != "A1":
            print(f"S1 convergence ({pass_gain_pp:.3f}pp < {CONVERGENCE_MIN_GAIN_PP}pp) "
                  f"after {group_name} — continuing to next group anyway "
                  f"(S1 stops a GROUP's internal passes, not the whole sweep; "
                  f"each group is tried once per this budget).")

    write_latest(sweep_root, best_record, current_best_delta)
    return {
        "baseline": baseline_record,
        "best": best_record,
        "best_delta": current_best_delta,
        "n_candidates": n_candidates,
    }


# ── Stage B — engine sensitivity diagnostic (one-way, promotion FORBIDDEN) ─
#
# Params chosen because each has NO resolver-side counterpart (grep-confirmed
# absent from configs/formulas/market_crt_states.yaml `thresholds:`) — each is
# therefore a candidate explanation for any gap that survives Stage A.
# This does NOT test "config-only reproducibility": moving the reference
# engine to raise agreement would manufacture parity, not test it. Results
# are reported separately from the Stage-A parity number and grant no
# authority to modify CRTConfig / production config (§6.5).

STAGE_B_PARAMS: dict[str, list[Any]] = {
    "retest_min_depth_atr_fraction": [0.05, 0.20],
    "max_displacement_strength": [1.5, 3.0],
    "atr_buffer_multiplier": [2, 4],
    "score_decay_lambda": [0.02, 0.10],
}
S2_MAX_CANDIDATES_STAGE_B_DEFAULT = S2_MAX_CANDIDATES_STAGE_B


def run_engine_candidate(
    base_crt_cfg: Any,
    overrides: dict[str, Any],
    *,
    instrument: str,
    csv_path: Path,
    engine_runs_dir: Path,
    label: str,
) -> Path:
    """Run one BacktestRunner candidate; return its events.jsonl path.

    ``engine_runs_dir / label`` is a unique parent per candidate so the
    auto-timestamped ``run_<ts>_{instrument}`` subdirectory ReportWriter
    creates can be found unambiguously via glob, with no risk of colliding
    with another candidate's output.
    """
    import dataclasses

    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    crt_cfg = dataclasses.replace(base_crt_cfg, **overrides)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    loader = CandleLoader(str(csv_path), instrument)
    runner = BacktestRunner(
        cfg, csv_path=str(csv_path), overrides={"diagnostic": label, "instrument": instrument}
    )
    cand_output_dir = (engine_runs_dir / label).resolve()
    assert cand_output_dir.is_relative_to(engine_runs_dir.resolve())
    cand_output_dir.mkdir(parents=True, exist_ok=True)
    runner.run(loader.stream(), loader.count(), str(cand_output_dir))
    matches = list(cand_output_dir.glob(f"run_*_{instrument}/{instrument}_events.jsonl"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly 1 events.jsonl under {cand_output_dir}, found {len(matches)}: "
            f"{matches}"
        )
    return matches[0]


def run_stage_b(
    *,
    sweep_root: Path,
    ohlcv_path: Path,
    resolver_config_path: Optional[Path],
    instrument: str,
    max_candidates: int,
) -> dict[str, Any]:
    from config_layer.config_builder import ConfigBuilder

    engine_runs_dir = (sweep_root / "engine_runs").resolve()
    engine_runs_dir.mkdir(parents=True, exist_ok=True)
    base_crt_cfg = ConfigBuilder.build(instrument)

    iter_num = 0
    n_candidates = 0
    baseline: dict[str, Any] = {"agreement": 0, "total": 0, "per_state": {}}

    def _eval_b(overrides: dict[str, Any], label: str) -> dict[str, Any]:
        nonlocal iter_num, n_candidates
        t0 = time.time()
        events_path = run_engine_candidate(
            base_crt_cfg, overrides, instrument=instrument, csv_path=ohlcv_path,
            engine_runs_dir=engine_runs_dir, label=label,
        )
        engine_ctx_b = cm.prepare_engine_context(ohlcv_path, events_path)
        report, res_meta = cm.run_once(
            engine_ctx_b, config_path=resolver_config_path, engine_mode="exit",
            injection="none", max_episodes=100_000,
        )
        elapsed = time.time() - t0
        iter_num += 1
        n_candidates += 1
        per_state = per_state_summary(report)
        ok, violations = anti_simpson_ok(baseline["per_state"], per_state) if baseline["total"] else (True, [])
        record = {
            "cert_version": CERT_VERSION,
            "iter": iter_num,
            "stage": "B",
            "label": label,
            "engine_overrides": overrides,
            "config_delta": {},
            "resolver_config": str(resolver_config_path) if resolver_config_path else "(default)",
            "agreement": report.agreement,
            "total": report.total,
            "agreement_rate": report.agreement / report.total if report.total else 0.0,
            "delta_vs_baseline_pp": (
                (report.agreement / report.total - baseline["agreement"] / baseline["total"]) * 100.0
                if report.total and baseline["total"] else 0.0
            ),
            "per_state": per_state,
            "mismatch_n": report.total - report.agreement,
            "episode_n": len(report.divergence_episodes),
            "elapsed_s": round(elapsed, 2),
            "anti_simpson_ok": ok,
            "anti_simpson_violations": violations,
            "authority": "one_way_sensitivity_diagnostic_ONLY_no_promotion",
        }
        write_iteration_b(sweep_root, record)
        print(
            f"  iter={iter_num:04d} stage=B label={label} "
            f"agreement={record['agreement_rate']:.4%} "
            f"({record['delta_vs_baseline_pp']:+.2f}pp) elapsed={record['elapsed_s']}s"
        )
        return record

    print("Stage B baseline (unmodified CRTConfig)...")
    baseline_record = _eval_b({}, "B_baseline")
    baseline = {
        "agreement": baseline_record["agreement"], "total": baseline_record["total"],
        "per_state": baseline_record["per_state"],
    }
    records = [baseline_record]

    for param_name, values in STAGE_B_PARAMS.items():
        if n_candidates >= max_candidates:
            print(f"S2 budget reached ({max_candidates}); stopping Stage B sweep.")
            break
        for value in values:
            if n_candidates >= max_candidates:
                break
            label = f"B_{param_name}_{value}".replace(".", "p")
            records.append(_eval_b({param_name: value}, label))

    best = max(records, key=lambda r: r["agreement_rate"])
    return {"baseline": baseline_record, "records": records, "best": best,
            "n_candidates": n_candidates}


def main() -> int:
    parser = argparse.ArgumentParser(description="CRT Semantic Parity sweep driver (F-069)")
    parser.add_argument("--stage", choices=("A", "B"), default="A")
    parser.add_argument("--ohlcv", default=str(DEFAULT_OHLCV))
    parser.add_argument("--events", default=str(DEFAULT_EVENTS))
    parser.add_argument("--base-config", default=str(DEFAULT_BASE_CONFIG))
    parser.add_argument("--resolver-config", default=None,
                         help="Stage B only: resolver config held fixed while engine varies "
                              "(default: the base/live market_crt_states.yaml).")
    parser.add_argument("--instrument", default="XAUUSD")
    parser.add_argument("--max-candidates", type=int, default=S2_MAX_CANDIDATES_STAGE_A)
    parser.add_argument("--out", default=str(SWEEP_ROOT))
    args = parser.parse_args()

    sweep_root = Path(args.out).resolve()
    sweep_root.mkdir(parents=True, exist_ok=True)

    ohlcv_path = Path(args.ohlcv)
    events_path = Path(args.events)
    base_config_path = Path(args.base_config)

    if args.stage == "A":
        print(f"Preparing engine context ({ohlcv_path}, {events_path})...")
        engine_ctx = cm.prepare_engine_context(ohlcv_path, events_path)
        print(f"  n_bars={engine_ctx.n_bars} transitions={engine_ctx.timeline.n_transitions}")
        max_candidates = min(args.max_candidates, S2_MAX_CANDIDATES_STAGE_A)
        result = run_stage_a(
            engine_ctx, sweep_root=sweep_root, base_config_path=base_config_path,
            max_candidates=max_candidates,
        )
        print(f"\nStage A done: {result['n_candidates']} candidates.")
        print(f"  baseline: {result['baseline']['agreement_rate']:.4%}")
        print(f"  best:     {result['best']['agreement_rate']:.4%} "
              f"({result['best']['delta_vs_baseline_pp']:+.2f}pp)")
        print(f"  best_delta: {result['best_delta']}")
    else:
        resolver_cfg = Path(args.resolver_config) if args.resolver_config else None
        max_candidates = min(args.max_candidates, S2_MAX_CANDIDATES_STAGE_B)
        result = run_stage_b(
            sweep_root=sweep_root, ohlcv_path=ohlcv_path, resolver_config_path=resolver_cfg,
            instrument=args.instrument, max_candidates=max_candidates,
        )
        print(f"\nStage B done: {result['n_candidates']} candidates "
              "(ONE-WAY DIAGNOSTIC — no promotion authority).")
        print(f"  baseline: {result['baseline']['agreement_rate']:.4%}")
        print(f"  best:     {result['best']['agreement_rate']:.4%} (label={result['best']['label']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
