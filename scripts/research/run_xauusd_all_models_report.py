#!/usr/bin/env python3
"""Run every catalogued model on data/mt5/XAUUSD_M15.csv and write a report.

OBSERVATION_ONLY — research authority. No promote. No config mutation.

Captures:
  - per-model scores.jsonl + manifest under results/model_runners/
  - feature-flow report: docs/analysis/xauusd-model-layer-run-report-YYYY-MM-DD.md
  - machine summary: results/model_runners/XAUUSD/ALL_MODELS_SUMMARY.json
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
INSTRUMENT = "XAUUSD"
OUT_DIR = ROOT / "results" / "model_runners"
CONFIG = ROOT / "configs" / "production" / "v2_multi_2026_04.json"
LIMIT = 200  # post-warmup bars; full FeaturePipeline still runs on entire CSV
# Preferred 39-dim shadow envelope (post-retrain 2026-07-28); not production-active.
TRADENET_ARTIFACT = (
    ROOT
    / "models"
    / "XAUUSD"
    / "20260728T060800"
    / "tradenet_v2_XAUUSD_20260728T060800.json"
)
RR_TRAINED_ARTIFACT = ROOT / "models" / "rr_model.json"
GAUSSIAN_ML_ARTIFACT = (
    ROOT
    / "models"
    / "XAUUSD"
    / "20260722T194904Z"
    / "gaussian_xauusd_nb_20260722T194904Z.json"
)


def _resolve_envelope_artifact() -> Path | None:
    """Prefer LATEST pointer under results/envelope_offline/XAUUSD."""
    pointer = ROOT / "results" / "envelope_offline" / INSTRUMENT / "LATEST" / "pointer.json"
    if pointer.is_file():
        data = json.loads(pointer.read_text(encoding="utf-8"))
        # bundle field or out_dir
        if "bundle" in data:
            p = Path(data["bundle"])
            if p.is_file():
                return p.parent
            if not p.is_absolute():
                p2 = ROOT / p
                if p2.is_file():
                    return p2.parent
        if "out_dir" in data:
            d = Path(data["out_dir"])
            if not d.is_absolute():
                d = ROOT / d
            if (d / "envelope_bundle.json").is_file():
                return d
    # fallthrough: newest run dir with bundle
    root = ROOT / "results" / "envelope_offline" / INSTRUMENT
    if root.is_dir():
        candidates = sorted(
            [p for p in root.iterdir() if p.is_dir() and p.name != "LATEST"],
            reverse=True,
        )
        for d in candidates:
            if (d / "envelope_bundle.json").is_file():
                return d
    return None

# Feature-flow truth (source-verified) — single report authority for flow diagrams.
FEATURE_FLOWS: dict[str, dict] = {
    "rr": {
        "inputs": ["high", "low", "close"],
        "derived": [
            "candle_range = high - low",
            "upper_body = (high - close) / range",
            "lower_body = (close - low) / range",
            "polarity = max(upper_body, lower_body)",
        ],
        "outputs": ["score", "candle_polarity", "rr_ratio", "semantic=candle_structure_quality"],
        "unused_from_pipeline": "all other 36 canonical features ignored",
    },
    "gaussian": {
        "inputs": ["ema_fast", "ema_slow", "momentum_score"],
        "derived": [
            "ema_diff = (ema_fast - ema_slow) / ema_slow",
            "momentum_norm = tanh(momentum_score)",
            "x = (ema_diff + momentum_norm) / 2",
            "score = exp(-((x - mu)^2) / (2*sigma^2))  # mu/sigma from registry or engine defaults",
        ],
        "outputs": ["score", "reason", "meta{mu,sigma,x}"],
        "unused_from_pipeline": "direction ignored; full dict required by assert only",
    },
    "zone_gate": {
        "inputs": "full CANONICAL_FEATURES (39) name-anchored vector",
        "derived": [
            "BitNetZoneGate.check(vector) → top_scores",
            "cluster_score if len(top_scores) >= cluster_min_n else best",
            "passed = score >= zone_cluster_threshold",
        ],
        "outputs": ["score", "passed", "best_zone_id", "top_scores", "cluster_score"],
        "config_keys": [
            "engine_runner.zone_registry_path",
            "engine_runner.zone_cluster_threshold",
            "engine_runner.zone_gate.{top_k,cluster_min_n,cluster_spread_max}",
        ],
    },
    "crt_score": {
        "inputs": [
            "body_ratio",
            "disp_strength (as move)",
            "atr",
            "retest_depth",
            "double_sweep",
            "candles_since_retest",
            "sweep_detected",
        ],
        "derived": [
            "FM-029 disp_strength_atr_rescale(move, atr)",
            "s_sweep from sweep_detected/double_sweep",
            "s_breakout = 0.5*body + 0.5*min(disp_rescale/2,1)",
            "s_retest = exp(-((depth-0.5)^2)/0.04)",
            "s_time = exp(-lambda * candles_since_retest)",
            "final = weighted sum via crt_engine.score_component_weights",
        ],
        "outputs": ["score"],
        "note": "NOT UltronRiskEngine linear retest (audit MD-1 dual path)",
    },
    "fusion_compute": {
        "inputs": "union of crt_score + gaussian + zone_gate + rr inputs",
        "derived": [
            "run four engines independently",
            "FusionEngine.compute weighted average with fusion_engine.weight_*",
            "optional ScoreNormalizer rolling min-max",
        ],
        "outputs": ["final_score", "scores{}", "component_native", "weights_used"],
        "not_included": ["DecisionEngine", "ExecutionPlanner", "UltronRiskGate", "neural_fn", "llm_fn"],
    },
    "bitnet": {
        "inputs": [
            "body_ratio",
            "retest_depth",
            "disp_strength",
            "atr",
            "candles_since_retest",
            "double_sweep",
        ],
        "derived": [
            "legacy6 encoder → MLP backbone → confidence sigmoid",
            "optional FM-027/028 → retest_depth/disp_strength aliases",
            "would_reject = confidence < bitnet_main_threshold",
        ],
        "outputs": ["confidence", "score", "would_reject", "threshold"],
        "note": "prod use_bitnet remains false; observe only",
    },
    "tradenet": {
        "inputs": "full canonical feature dict → 39-vector (name-anchored)",
        "derived": [
            "optional scaler",
            "MLP trunk 39→32→16",
            "3 sigmoid heads: p_tp1, p_tp2, p_survives_be",
            "composite = 0.4*p_tp1 + 0.4*p_tp2 + 0.2*p_survives_be",
        ],
        "outputs": ["tradenet_score", "p_tp1", "p_tp2", "p_survives_be"],
        "note": "UNWIRED F-005; XAUUSD v2 envelope degenerate metrics",
    },
    "rr_trained": {
        "inputs": "39-dim v4 features → explicit v3 38-name map",
        "map": "macd_hist_z→macd_hist; candle_range→wick_size; drop macd_hist_raw",
        "derived": [
            "scale (mu/sigma)",
            "ridge expected_rr + GNB p_win + Mahalanobis confidence",
            "raw path (no F-044 gate bypass theatre)",
        ],
        "outputs": ["expected_rr_raw", "p_win_raw", "ml_score_raw", "confidence_raw", "d_sq"],
        "note": "OFF-spine; rr_fusion.enabled=false",
    },
    "crt_state_machine": {
        "inputs": "raw OHLCV Candle stream (not 39-dim scorer)",
        "derived": [
            "RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION",
            "internal cached_features at RETEST (body_ratio, displacement_*, …)",
            "BitNet only if use_bitnet (false on active)",
        ],
        "outputs": ["state", "action", "trade fields on TRADE_OPENED"],
        "note": "distinct from crt_score fusion path",
    },
    "envelope": {
        "inputs": "38-dim LEGACY_FEATURE_NAMES from live feature dict (drop macd_hist_raw)",
        "derived": [
            "load envelope_bundle.json + 4 HistGradientBoosting heads",
            "predict_heads → mfe_r, mae_r_heat, holding_bars, time_to_mfe",
        ],
        "outputs": ["mfe_r", "mae_r_heat", "holding_bars", "time_to_mfe"],
        "note": "requires --artifact bundle; XAUUSD train 20260728T062350Z SIGNAL_RETAINED",
    },
    "gaussian_ml": {
        "inputs": "name-anchored feature_schema_resolved from artifact (typically 39)",
        "derived": [
            "load_gaussian_model(artifact) — NOT engine_runner.gaussian_impl",
            "scale + predict_expected_rr → logistic score",
        ],
        "outputs": ["score", "expected_rr", "confidence"],
        "note": "offline model_id independent of prod gaussian_impl=heuristic",
    },
    "llm_gate": {
        "inputs": "gaussian/neural scores on evaluate() path",
        "outputs": ["llm blend when score in band"],
        "block_reason": "EngineRunner never injects llm_fn; fusion_use_evaluate=false",
    },
    "strategies": {
        "inputs": "strategy-specific",
        "outputs": ["consensus score"],
        "block_reason": "Sidecar S1-S10; participates_in_live_spine=false",
    },
    "engine_runner": {
        "inputs": "full feature dict + context",
        "outputs": ["fusion + decision package"],
        "block_reason": "Orchestrator — not a single model; use backtest_v2",
    },
}


def _run_one(model_id: str, **kwargs):
    from research.model_runners.runner import RunRequest, run_model

    req = RunRequest(
        model_id=model_id,
        csv_path=CSV,
        instrument=INSTRUMENT,
        out_dir=OUT_DIR,
        repo_root=ROOT,
        config_path=CONFIG,
        start=None,
        end=None,
        limit=LIMIT,
        formats="jsonl,manifest,summary,csv",
        artifact=kwargs.get("artifact"),
        emit=kwargs.get("emit"),
    )
    return run_model(req)


def main() -> int:
    from research.model_runners.contracts import list_models
    from research.model_runners.require_config import sha256_file

    if not CSV.is_file():
        print(f"ERROR: missing {CSV}", file=sys.stderr)
        return 2
    if not CONFIG.is_file():
        print(f"ERROR: missing {CONFIG}", file=sys.stderr)
        return 2

    csv_sha = sha256_file(CSV)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results: list[dict] = []

    for m in list_models():
        entry: dict = {
            "model_id": m.model_id,
            "runnable": m.runnable,
            "spine_active": m.spine_active,
            "audit_status": m.audit_status,
            "entry_point": m.entry_point,
            "description": m.description,
            "feature_flow": FEATURE_FLOWS.get(m.model_id, {}),
        }
        if not m.runnable:
            entry["status"] = "BLOCKED"
            entry["block_reason"] = FEATURE_FLOWS.get(m.model_id, {}).get(
                "block_reason", m.description
            )
            print(f"[BLOCK] {m.model_id}: {entry['block_reason']}")
            results.append(entry)
            continue

        kwargs: dict = {}
        if m.model_id == "tradenet":
            if not TRADENET_ARTIFACT.is_file():
                entry["status"] = "BLOCKED"
                entry["block_reason"] = f"artifact missing: {TRADENET_ARTIFACT}"
                print(f"[BLOCK] tradenet: {entry['block_reason']}")
                results.append(entry)
                continue
            kwargs["artifact"] = TRADENET_ARTIFACT
        if m.model_id == "rr_trained":
            if not RR_TRAINED_ARTIFACT.is_file():
                entry["status"] = "BLOCKED"
                entry["block_reason"] = f"artifact missing: {RR_TRAINED_ARTIFACT}"
                print(f"[BLOCK] rr_trained: {entry['block_reason']}")
                results.append(entry)
                continue
            kwargs["artifact"] = RR_TRAINED_ARTIFACT
        if m.model_id == "gaussian_ml":
            if not GAUSSIAN_ML_ARTIFACT.is_file():
                entry["status"] = "BLOCKED"
                entry["block_reason"] = f"artifact missing: {GAUSSIAN_ML_ARTIFACT}"
                print(f"[BLOCK] gaussian_ml: {entry['block_reason']}")
                results.append(entry)
                continue
            kwargs["artifact"] = GAUSSIAN_ML_ARTIFACT
        if m.model_id == "envelope":
            env_art = _resolve_envelope_artifact()
            if env_art is None:
                entry["status"] = "BLOCKED"
                entry["block_reason"] = (
                    "no XAUUSD envelope bundle "
                    "(train: scripts/research/train_envelope_offline.py --instrument XAUUSD)"
                )
                print(f"[BLOCK] envelope: {entry['block_reason']}")
                results.append(entry)
                continue
            kwargs["artifact"] = env_art
        if m.model_id == "crt_state_machine":
            kwargs["emit"] = "all"

        print(f"[RUN ] {m.model_id} ...")
        try:
            res = _run_one(m.model_id, **kwargs)
            man_path = res.manifest_path
            man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
            summary_path = res.run_dir / "summary.json"
            summary = (
                json.loads(summary_path.read_text(encoding="utf-8"))
                if summary_path.is_file()
                else {}
            )
            # sample first ok native
            sample = None
            jsonl = res.run_dir / "scores.jsonl"
            if jsonl.is_file():
                for line in jsonl.read_text(encoding="utf-8").splitlines():
                    rec = json.loads(line)
                    if rec.get("status") == "ok":
                        sample = rec.get("native")
                        break
            entry.update(
                {
                    "status": "OK" if res.n_error == 0 else "PARTIAL",
                    "run_id": res.run_id,
                    "run_dir": str(res.run_dir),
                    "n_ok": res.n_ok,
                    "n_error": res.n_error,
                    "summary": summary,
                    "config_keys_read": man.get("config_keys_read"),
                    "artifact": man.get("artifact"),
                    "sample_native": sample,
                }
            )
            print(
                f"       n_ok={res.n_ok} n_error={res.n_error} dir={res.run_dir}"
            )
        except Exception as exc:
            entry["status"] = "ERROR"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["traceback"] = traceback.format_exc()
            print(f"       ERROR: {entry['error']}")
        results.append(entry)

    # write summary JSON
    summary_root = OUT_DIR / INSTRUMENT
    summary_root.mkdir(parents=True, exist_ok=True)
    all_path = summary_root / "ALL_MODELS_SUMMARY.json"
    payload = {
        "schema": "xauusd_all_models_summary_v1",
        "authority": "research_only",
        "PRODUCTION_BEHAVIOR_CHANGED": False,
        "created_at": created,
        "instrument": INSTRUMENT,
        "csv": str(CSV),
        "csv_sha256": csv_sha,
        "config": str(CONFIG),
        "limit": LIMIT,
        "models": results,
    }
    all_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

    # markdown report
    report_path = (
        ROOT / "docs" / "analysis" / f"xauusd-model-layer-run-report-{day}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# XAUUSD Model Layer Run Report — {day}")
    lines.append("")
    lines.append("**Authority:** research_only · OBSERVATION_ONLY · no promote")
    lines.append(f"**Corpus:** `{CSV.as_posix()}` sha256=`{csv_sha[:16]}…`")
    lines.append(f"**Config:** `{CONFIG.name}`")
    lines.append(f"**Bars scored:** post-warmup `--limit {LIMIT}` (full CSV used for FeaturePipeline warmup)")
    lines.append(f"**Created:** {created}")
    lines.append("")
    lines.append("**Refresh note:** includes post-unblock `envelope` (XAU train) and "
                 "`gaussian_ml` (artifact offline, not gated by `gaussian_impl`); "
                 "TradeNet 39-dim shadow envelope.")
    lines.append("")
    lines.append("## Executive scoreboard")
    lines.append("")
    lines.append("| Model | Status | Spine | Audit | n_ok | n_err | Notes |")
    lines.append("|---|---|---|---|---:|---:|---|")
    for r in results:
        note = r.get("block_reason") or r.get("error") or r.get("run_id") or ""
        if isinstance(note, str) and len(note) > 60:
            note = note[:57] + "..."
        lines.append(
            f"| `{r['model_id']}` | **{r['status']}** | {r['spine_active']} | "
            f"{r['audit_status']} | {r.get('n_ok', '—')} | {r.get('n_error', '—')} | {note} |"
        )
    lines.append("")
    lines.append("## Shared substrate (all feature-path models)")
    lines.append("")
    lines.append("```text")
    lines.append("data/mt5/XAUUSD_M15.csv")
    lines.append("  → normalize OHLCV columns")
    lines.append("  → FeaturePipeline.run()  # full corpus warmup")
    lines.append("  → build_features(row) → 39-key CANONICAL_FEATURES dict")
    lines.append("  → model adapter.score_bar(BarContext)")
    lines.append("  → scores.jsonl + manifest.json")
    lines.append("```")
    lines.append("")
    lines.append("**Canonical dim:** 39 (schema v4.0).")
    lines.append("")

    for r in results:
        mid = r["model_id"]
        lines.append(f"## Model: `{mid}`")
        lines.append("")
        lines.append(f"- **Status:** {r['status']}")
        lines.append(f"- **Entry:** `{r['entry_point']}`")
        lines.append(f"- **Spine active:** {r['spine_active']}")
        lines.append(f"- **Audit tag:** {r['audit_status']}")
        lines.append(f"- **Description:** {r['description']}")
        flow = r.get("feature_flow") or {}
        lines.append("")
        lines.append("### Feature flow")
        lines.append("")
        if flow:
            for k, v in flow.items():
                if k == "block_reason":
                    continue
                lines.append(f"- **{k}:** `{v}`" if not isinstance(v, list) else f"- **{k}:**")
                if isinstance(v, list):
                    for item in v:
                        lines.append(f"  - `{item}`")
        else:
            lines.append("_No flow metadata._")
        lines.append("")
        if r["status"] in ("OK", "PARTIAL"):
            lines.append("### Run capture")
            lines.append("")
            lines.append(f"- **run_dir:** `{r.get('run_dir')}`")
            lines.append(f"- **n_ok / n_error:** {r.get('n_ok')} / {r.get('n_error')}")
            if r.get("summary"):
                lines.append(f"- **summary:** `{json.dumps(r['summary'], default=str)[:500]}`")
            if r.get("sample_native"):
                lines.append("- **sample native (first ok bar):**")
                lines.append("```json")
                lines.append(json.dumps(r["sample_native"], indent=2, default=str)[:2000])
                lines.append("```")
            if r.get("config_keys_read"):
                lines.append(f"- **config keys read:** {r['config_keys_read']}")
        elif r["status"] == "BLOCKED":
            lines.append(f"**Blocked:** {r.get('block_reason')}")
        elif r["status"] == "ERROR":
            lines.append(f"**Error:** {r.get('error')}")
            if r.get("traceback"):
                lines.append("```")
                lines.append(r["traceback"][:3000])
                lines.append("```")
        lines.append("")

    lines.append("## Authority & non-claims")
    lines.append("")
    lines.append("- No economic edge claim from these scores.")
    lines.append("- No production config or model registry mutation.")
    lines.append("- Fusion compose ≠ full EngineRunner decision path.")
    lines.append("- BitNet/TradeNet/rr_trained runs do **not** enable those systems in production.")
    lines.append("")
    lines.append(f"Machine summary: `{all_path.as_posix()}`")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSUMMARY → {all_path}")
    print(f"REPORT  → {report_path}")
    n_ok = sum(1 for r in results if r["status"] in ("OK", "PARTIAL"))
    n_block = sum(1 for r in results if r["status"] == "BLOCKED")
    n_err = sum(1 for r in results if r["status"] == "ERROR")
    print(f"done: ok/partial={n_ok} blocked={n_block} error={n_err}")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
