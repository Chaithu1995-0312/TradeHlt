#!/usr/bin/env python3
"""
implementation_model_validation_xauusd.py
=========================================
IMPLEMENTATION VALIDATION (not a backtest / not profitability).

Execute every trained model selected in active_models.yaml against the
Phase-1 frozen XAUUSD corpus and report load / feature-alignment /
runtime / consumer / wiring defects.

Never retrains. Never modifies checkpoints. Never optimises thresholds.

Outputs:
  results/implementation_validation/xauusd_model_validation_<ts>.json
  results/implementation_validation/xauusd_model_validation_LATEST.json
  docs/governance/implementation_model_validation-xauusd-2026-07-22.md
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import traceback
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Frozen corpus pin (Phase-1 candidate) ────────────────────────────────────
CORPUS_REL = "data/mt5/XAUUSD_M15.csv"
CORPUS_PIN = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
CORPUS_ROWS = 47275
INSTRUMENT = "XAUUSD"

OUT_DIR = ROOT / "results" / "implementation_validation"
REPORT_MD = ROOT / "docs" / "governance" / "implementation_model_validation-xauusd-2026-07-22.md"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stats(arr: np.ndarray) -> dict:
    a = np.asarray(arr, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {
            "n": 0, "mean": None, "std": None, "min": None, "max": None,
            "p01": None, "p50": None, "p99": None,
            "n_nan_or_inf": int(np.size(arr) - a.size) if hasattr(arr, "__len__") else 0,
            "n_unique": 0, "is_constant": True, "is_saturated_near_bound": False,
        }
    mn, mx = float(a.min()), float(a.max())
    # saturation near [0,1] bounds
    sat = False
    if mx <= 1.0 + 1e-9 and mn >= -1e-9:
        frac_hi = float((a >= 0.99).mean())
        frac_lo = float((a <= 0.01).mean())
        sat = frac_hi > 0.90 or frac_lo > 0.90
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "std": float(a.std()),
        "min": mn,
        "max": mx,
        "p01": float(np.percentile(a, 1)),
        "p50": float(np.percentile(a, 50)),
        "p99": float(np.percentile(a, 99)),
        "n_nan_or_inf": int(np.size(arr) - a.size) if np.size(arr) != a.size else 0,
        "n_unique": int(np.unique(np.round(a, 6)).size),
        "is_constant": bool(a.std() < 1e-12),
        "is_saturated_near_bound": sat,
        "frac_ge_0_99": float((a >= 0.99).mean()) if mx <= 1.0 + 1e-6 else None,
        "frac_le_0_01": float((a <= 0.01).mean()) if mn >= -1e-6 else None,
    }


def _safe(fn: Callable, *a, **kw) -> Tuple[Any, Optional[str]]:
    try:
        return fn(*a, **kw), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# Failure-mode taxonomy for implementation validation (not economic quality).
# PASS / FAIL_CLOSED / FAIL_OPEN / DEGRADED / DISABLED / ORPHAN / GOVERNANCE_INCOMPLETE
FAILURE_MODE_MEANING = {
    "PASS": "Executed correctly under a valid contract; outputs informative",
    "FAIL_CLOSED": "Correctly refused due to invalid schema/registry/contract",
    "FAIL_OPEN": "Executed under invalid assumptions (silent misalignment) — CRITICAL",
    "DEGRADED": "Executes but with reduced / near-null information",
    "DISABLED": "Configuration choice — intentionally not on the spine",
    "ORPHAN": "Produces (or could produce) outputs with no consumer",
    "GOVERNANCE_INCOMPLETE": "Runtime path works but selection/registry authority is missing",
    "NOT_RUN": "Validator did not reach this model",
}


def classify_failure_mode(r: "ModelReport") -> str:
    """Map raw harness status + bugs + wiring into the failure-mode taxonomy.

    Precedence (highest first):
      FAIL_OPEN > FAIL_CLOSED > GOVERNANCE_INCOMPLETE > ORPHAN > DEGRADED > DISABLED > PASS

    Post-P0 (2026-07-22): RR Fusion dim refuse and Gaussian name-anchored subset
    are FAIL_CLOSED / ORPHAN-contract-ok — not FAIL_OPEN.
    """
    codes = {b.get("code") for b in r.bugs}
    status = r.status or ""
    consumer = (r.consumer or "").upper()
    enabled = r.wiring.get("runtime_enabled")
    notes = " ".join(r.notes or [])

    # 1) FAIL_OPEN — only residual silent-mis-score paths (should be empty post-P0)
    if "RR_FUSION_INDEX_TRUNCATE_UNDER_V4" in codes:
        return "FAIL_OPEN"
    if (
        status == "EXECUTED_WITH_SCHEMA_DRIFT"
        and r.executed
        and not r.features_ok
        and "name_anchored" not in notes
        and "GAUSSIAN_NAME_ANCHORED_OK" not in codes
    ):
        return "FAIL_OPEN"

    # 2) FAIL_CLOSED — correctly refused invalid contract
    if any(
        c in codes
        for c in (
            "ZONEGATE_V4_FEATURE_ORDER_BLOCK",
            "GAUSSIAN_CKPT_LOAD_FAIL",
            "RR_FUSION_DIM_LOAD_REFUSED",
            "RR_FUSION_NOT_LOADED",
        )
    ):
        return "FAIL_CLOSED"
    if status in {"LOAD_FAIL_SCHEMA", "CANNOT_EXECUTE"}:
        return "FAIL_CLOSED"
    if status == "LOAD_FAIL":
        # Prefer FAIL_CLOSED for protective refuses (dim mismatch, etc.)
        return "FAIL_CLOSED"

    # 3) GOVERNANCE_INCOMPLETE — catalog/selection authority missing
    if "BITNET_REGISTRY_EMPTY" in codes or status == "NO_ACTIVE":
        return "GOVERNANCE_INCOMPLETE"

    # 4) ORPHAN — no consumer on the spine (includes contract-OK trained Gaussian ML)
    if status == "EXECUTED_ORPHAN" or "ORPHAN" in consumer:
        return "ORPHAN"

    # 5) DEGRADED — executes with reduced / near-null information
    if any(
        c in codes
        for c in (
            "GAUSSIAN_NEAR_CONSTANT",
            "GAUSSIAN_DEFAULT_MU_SIGMA",
            "GAUSSIAN_NO_XAUUSD_REGISTRY",
        )
    ):
        return "DEGRADED"
    if status in {"EXECUTED_DEGRADED", "DEGRADED"}:
        return "DEGRADED"

    # 6) DISABLED — config intentionally off, no contract hazard
    if enabled is False or status in {"EXECUTED_DISABLED_ON_SPINE", "DISABLED"}:
        return "DISABLED"

    # 7) PASS
    if status == "OK" and r.loaded and r.executed:
        return "PASS" if (r.features_ok and r.outputs_healthy) else "DEGRADED"

    return status or "NOT_RUN"


@dataclass
class ModelReport:
    model: str
    kind: str  # trained | rule_based | heuristic
    loaded: bool = False
    executed: bool = False
    features_ok: bool = False
    outputs_healthy: bool = False
    consumer: str = "unknown"
    status: str = "NOT_RUN"
    failure_mode: str = "NOT_RUN"  # PASS | FAIL_CLOSED | FAIL_OPEN | DEGRADED | DISABLED | ORPHAN | GOVERNANCE_INCOMPLETE
    load_detail: dict = field(default_factory=dict)
    feature_alignment: dict = field(default_factory=dict)
    runtime: dict = field(default_factory=dict)
    output_stats: dict = field(default_factory=dict)
    wiring: dict = field(default_factory=dict)
    bugs: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_bug(self, severity: str, code: str, msg: str, evidence: Any = None) -> None:
        self.bugs.append({
            "severity": severity,
            "code": code,
            "message": msg,
            "evidence": evidence,
        })

    def finalize_failure_mode(self) -> None:
        self.failure_mode = classify_failure_mode(self)


def load_corpus() -> Tuple[pd.DataFrame, dict]:
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path, PHASE1_STATUS

    path = guard_xauusd_csv_path(CORPUS_REL, INSTRUMENT)
    path = Path(path)
    digest = _sha256_file(path)
    meta = {
        "path": str(path).replace("\\", "/"),
        "sha256": digest,
        "pin_match": digest == CORPUS_PIN,
        "phase1_status": PHASE1_STATUS,
        "expected_rows": CORPUS_ROWS,
    }
    if digest != CORPUS_PIN:
        raise RuntimeError(
            f"Frozen corpus pin mismatch: got {digest}, expected {CORPUS_PIN}"
        )
    df = pd.read_csv(path)
    meta["rows"] = len(df)
    meta["cols"] = list(df.columns)
    meta["ts_start"] = str(df.iloc[0]["timestamp"]) if len(df) else None
    meta["ts_end"] = str(df.iloc[-1]["timestamp"]) if len(df) else None
    if len(df) != CORPUS_ROWS:
        meta["row_warning"] = f"expected {CORPUS_ROWS}, got {len(df)}"
    return df, meta


def build_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, dict]:
    from features.feature_pipeline import FeaturePipeline
    from features.feature_schema import (
        CANONICAL_FEATURES,
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_HASH,
        SCHEMA_V3_ALIASES,
        SCHEMA_V3_FEATURE_DIM,
    )

    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    info = {
        "schema_version_runtime": "v4.0",
        "canonical_feature_dim": CANONICAL_FEATURE_DIM,
        "canonical_feature_order": list(CANONICAL_FEATURE_ORDER),
        "feature_order_hash": FEATURE_ORDER_HASH,
        "schema_hash": SCHEMA_HASH,
        "schema_v3_aliases": dict(SCHEMA_V3_ALIASES),
        "schema_v3_feature_dim": SCHEMA_V3_FEATURE_DIM,
        "vector_shape": list(vectors.shape),
        "vector_dtype": str(vectors.dtype),
        "n_rows_after_finalize": len(enriched),
        "nan_counts": {
            k: int(enriched[k].isna().sum())
            for k in CANONICAL_FEATURE_ORDER
            if k in enriched.columns
        },
        "missing_canonical_cols": [
            k for k in CANONICAL_FEATURE_ORDER if k not in enriched.columns
        ],
        "extra_note": (
            "SCHEMA v4.0: macd_hist→(macd_hist_raw,macd_hist_z); "
            "wick_size→candle_range; session domain 0..4"
        ),
    }
    return enriched, vectors, info


def row_feature_dicts(enriched: pd.DataFrame) -> List[dict]:
    from features.feature_schema import CANONICAL_FEATURE_ORDER

    cols = [c for c in CANONICAL_FEATURE_ORDER if c in enriched.columns]
    # vectorized → list of dicts (memory heavy but OK at 47k×39)
    records = enriched[cols].to_dict(orient="records")
    return records


def align_report(
    expected: List[str],
    received: List[str],
    *,
    aliases: Optional[dict] = None,
) -> dict:
    exp, rec = list(expected), list(received)
    exp_set, rec_set = set(exp), set(rec)
    missing = [n for n in exp if n not in rec_set]
    extra = [n for n in rec if n not in exp_set]
    order_match = exp == rec
    # alias-aware remapped expected
    aliases = aliases or {}
    remapped = [aliases.get(n, n) for n in exp]
    remapped_missing = [n for n in remapped if n not in rec_set]
    return {
        "expected_dim": len(exp),
        "received_dim": len(rec),
        "expected": exp,
        "received": rec,
        "missing": missing,
        "extra": extra,
        "order_match_exact": order_match,
        "name_set_match": missing == [] and extra == [],
        "alias_remapped_expected": remapped,
        "alias_remapped_missing": remapped_missing,
        "alias_alignment_ok": remapped_missing == [] and len(remapped) == len(exp),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Model runners
# ═══════════════════════════════════════════════════════════════════════════

def validate_crt(enriched: pd.DataFrame, reports: List[ModelReport]) -> np.ndarray:
    """Rule-based CRT baseline. Returns numeric state-id series for correlation."""
    from config_layer.crt_engine_v2 import CRTEngine
    from config_layer.state_identity import CRTState
    from runtime.backtest_v2 import (
        BacktestConfig,
        CandleLoader,
        HTFBuilder,
        load_prod_config_from_registry,
    )
    from config_layer.production_config import PROD_VERSION
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    r = ModelReport(model="CRT", kind="rule_based")
    r.consumer = "spine_primary (deterministic state machine → TRADE_OPENED)"
    r.wiring = {
        "documented_intent": "rule-based market structure SM; NOT a trained model",
        "runtime_enabled": True,
        "active_models_status": "active",
        "file": "src/config_layer/crt_engine_v2.py",
    }
    r.feature_alignment = {
        "note": "CRT consumes OHLCV + ATR/EMA via internal SM; not the 39-dim vector",
        "features_ok": True,
    }
    r.features_ok = True

    # Align length to enriched feature rows (finalize may drop warmup edges)
    n_feat = len(enriched)
    state_ids = np.full(n_feat, -1, dtype=np.int16)
    scores = np.full(n_feat, np.nan, dtype=np.float64)
    exceptions = 0
    event_counts: Counter = Counter()
    trade_opened = 0
    state_name_counts: Counter = Counter()

    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
        bt_cfg = BacktestConfig.from_prod_config(instrument=INSTRUMENT, crt_config=crt_cfg)
        engine = CRTEngine(crt_cfg)
        r.loaded = True
        r.load_detail = {
            "engine": "CRTEngine",
            "config_version": PROD_VERSION,
            "instrument": INSTRUMENT,
            "n_states": len(CRTState),
            "warmup_candles": getattr(bt_cfg, "warmup_candles", None),
            "htf_candles_per_range": getattr(bt_cfg, "htf_candles_per_range", None),
        }

        csv_path = str(guard_xauusd_csv_path(CORPUS_REL, INSTRUMENT))
        loader = CandleLoader(csv_path, INSTRUMENT)
        htf = HTFBuilder(int(getattr(bt_cfg, "htf_candles_per_range", 16) or 16), INSTRUMENT)

        n_streamed = 0
        n_exec = 0
        warmup_done = False
        initialised = False
        warmup_n = int(getattr(bt_cfg, "warmup_candles", 64) or 64)

        for candle in loader.stream():
            n_streamed += 1
            htf.push(candle)

            if not warmup_done:
                if n_streamed < warmup_n:
                    continue
                warmup_done = True

            if not initialised:
                seeds = htf.seed_candles()
                if seeds:
                    try:
                        engine.initialise_range(seeds, htf.current_htf_id, "UNKNOWN")
                        initialised = True
                    except Exception as e:
                        r.notes.append(f"initialise_range: {type(e).__name__}: {e}")
                        # still try process_candle path
                        initialised = True
                else:
                    continue

            try:
                out = engine.process_candle(candle, htf.current_htf_id)
                n_exec += 1
                st = getattr(engine.state, "current_state", None)
                idx = min(n_exec - 1, n_feat - 1)
                if st is not None:
                    if hasattr(st, "value"):
                        state_ids[idx] = int(st.value)
                    state_name_counts[str(getattr(st, "name", st))] += 1
                if isinstance(out, dict):
                    event = (
                        out.get("event")
                        or out.get("event_type")
                        or out.get("status")
                        or out.get("action")
                    )
                    if event:
                        event_counts[str(event)] += 1
                    if "TRADE_OPENED" in str(event).upper() or out.get("trade_opened"):
                        trade_opened += 1
                    sc = out.get("score") or out.get("confidence") or out.get("final_score")
                    if sc is not None:
                        try:
                            scores[idx] = float(sc)
                        except (TypeError, ValueError):
                            pass
            except Exception:
                exceptions += 1
                if exceptions <= 5:
                    r.notes.append(f"crt_exception[{n_streamed}]: {traceback.format_exc(limit=2)}")

        r.executed = n_exec > 0
        r.runtime = {
            "n_candles_streamed": n_streamed,
            "n_processed": n_exec,
            "warmup_candles": warmup_n,
            "initialised": initialised,
            "exceptions": exceptions,
            "event_counts": dict(event_counts.most_common(40)),
            "state_name_counts": dict(state_name_counts.most_common(20)),
            "trade_opened_proxy_count": trade_opened,
            "final_state": str(getattr(getattr(engine, "state", None), "current_state", None)),
        }
        valid_states = state_ids[state_ids >= 0]
        r.output_stats = {
            "state_id": _stats(state_ids.astype(np.float64)),
            "state_distribution": dict(state_name_counts),
            "score_if_any": _stats(scores),
            "n_valid_state_samples": int(valid_states.size),
        }
        r.outputs_healthy = exceptions == 0 and n_exec > 0
        r.status = "OK" if r.outputs_healthy else "DEGRADED"
        if exceptions:
            r.add_bug("High", "CRT_EXCEPTIONS", f"{exceptions} process_candle exceptions", exceptions)
    except Exception as e:
        r.loaded = False
        r.status = "LOAD_FAIL"
        r.load_detail = {"error": f"{type(e).__name__}: {e}"}
        r.add_bug("Critical", "CRT_LOAD_FAIL", str(e), traceback.format_exc(limit=5))

    reports.append(r)
    return state_ids.astype(np.float64)


def validate_gaussian_heuristic(
    records: List[dict], reports: List[ModelReport]
) -> np.ndarray:
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine, GaussianRegistry
    from features.feature_schema import CANONICAL_FEATURE_ORDER

    r = ModelReport(model="Gaussian_heuristic_live", kind="heuristic")
    r.consumer = "fusion slot 'gaussian' (EngineRunner; gaussian_impl=heuristic)"
    r.wiring = {
        "documented_intent": "probability-of-success match via trained NB",
        "runtime_truth": "3-feature heuristic kernel; trained checkpoint NOT used (F-060)",
        "runtime_enabled": True,
        "active_models_status": "active / enabled_without_checkpoint",
        "config": "engine_runner.gaussian_impl=heuristic",
    }

    scores = np.full(len(records), np.nan)
    try:
        eng = HeuristicGaussianEngine({"instrument": INSTRUMENT}, instrument=INSTRUMENT, preload_registry=True)
        r.loaded = True
        reg_detail = {
            "registry_path": "models/gaussian_registry.json",
            "instrument": INSTRUMENT,
            "loaded_version": eng._loaded_version,
            "mu": eng.mu,
            "sigma": eng.sigma,
            "uses_trained_mu_sigma": False,
        }
        # XAUUSD has no active registry entry — expect defaults
        try:
            gr = GaussianRegistry(instrument=INSTRUMENT).load()
            reg_detail["registry_active_version"] = gr.active_version
            reg_detail["registry_mu"] = gr.mu
            reg_detail["registry_sigma"] = gr.sigma
            reg_detail["registry_feature_schema"] = getattr(gr, "feature_schema", None) or []
        except Exception as e:
            reg_detail["registry_load_error"] = f"{type(e).__name__}: {e}"
            r.add_bug(
                "High",
                "GAUSSIAN_NO_XAUUSD_REGISTRY",
                "No active Gaussian registry entry for XAUUSD; heuristic falls back to mu=0,sigma=1 defaults",
                str(e),
            )
        r.load_detail = reg_detail

        # Feature contract: only 3 features used; trained schema ignored
        used = ["ema_fast", "ema_slow", "momentum_score"]
        r.feature_alignment = align_report(used, list(CANONICAL_FEATURE_ORDER))
        r.feature_alignment["actual_consumed"] = used
        r.feature_alignment["trained_checkpoint_features_used"] = False
        r.features_ok = all(u in CANONICAL_FEATURE_ORDER for u in used)

        exceptions = 0
        reasons: Counter = Counter()
        for i, feat in enumerate(records):
            try:
                out = eng.compute(feat, candle_idx=i)
                scores[i] = float(out.get("score", float("nan")))
                reasons[str(out.get("reason", ""))] += 1
            except Exception as e:
                exceptions += 1
                if exceptions <= 3:
                    r.notes.append(f"gauss_h[{i}]: {type(e).__name__}: {e}")

        r.executed = True
        r.runtime = {
            "exceptions": exceptions,
            "reason_counts": dict(reasons.most_common(10)),
            "n": len(records),
        }
        r.output_stats = _stats(scores)
        const = r.output_stats.get("is_constant")
        sat = r.output_stats.get("is_saturated_near_bound")
        # F-060 class: near-constant ~0.88
        if const or (r.output_stats.get("std") is not None and r.output_stats["std"] < 0.02):
            r.add_bug(
                "High",
                "GAUSSIAN_NEAR_CONSTANT",
                "Heuristic gaussian outputs near-constant / low-variance (F-060 class)",
                r.output_stats,
            )
        if abs(eng.mu) < 1e-12 and abs(eng.sigma - 1.0) < 1e-12:
            r.add_bug(
                "Critical",
                "GAUSSIAN_DEFAULT_MU_SIGMA",
                "Live gaussian uses unparameterized defaults mu=0,sigma=1; trained checkpoint parameters never reach score",
                {"mu": eng.mu, "sigma": eng.sigma, "version": eng._loaded_version},
            )
        r.outputs_healthy = exceptions == 0 and not const
        r.status = "EXECUTED_DEGRADED" if (const or sat or exceptions) else "OK"
        if not r.features_ok:
            r.status = "FEATURE_MISALIGN"
    except Exception as e:
        r.status = "LOAD_FAIL"
        r.load_detail = {"error": f"{type(e).__name__}: {e}"}
        r.add_bug("Critical", "GAUSSIAN_H_LOAD_FAIL", str(e), traceback.format_exc(limit=4))

    reports.append(r)
    return scores


def validate_gaussian_trained(
    records: List[dict], reports: List[ModelReport]
) -> np.ndarray:
    """Force-load selected trained Gaussian NB checkpoints (not the live path)."""
    from pathlib import Path as P
    from training.trainer import load_gaussian_model
    from features.dataset_builder import extract_feature_vector
    from features.feature_schema import (
        CANONICAL_FEATURE_ORDER,
        FEATURE_ORDER_HASH,
        SCHEMA_V3_ALIASES,
    )

    scores = np.full(len(records), np.nan)
    r = ModelReport(model="Gaussian_trained_NB", kind="trained")
    r.consumer = "NOT on live spine when gaussian_impl=heuristic (orphan vs selection)"
    r.wiring = {
        "documented_intent": "trained GaussianNB on registry-selected version",
        "runtime_truth": "MLGaussianEngine only when gaussian_impl=ml|shadow_ml",
        "runtime_enabled": False,
        "selection": "active_models.yaml gaussian.identity.selection.by_instrument (BNB/ETH only)",
        "active_config_gaussian_impl": "heuristic",
    }

    # Prefer BNB 38-dim active entry; also try ETH 35-dim for schema contrast
    candidates = [
        ("p5_20260524T120449", "models/BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json", 38),
        ("v5_auto_2026_06_eth", "models/ETHUSDT/20260519_113806/gaussian_v5_auto_2026_06_eth.json", 35),
    ]

    loaded_any = False
    for version, path, expected_dim in candidates:
        p = P(path)
        entry = {
            "version": version,
            "path": path,
            "exists": p.exists(),
            "expected_dim": expected_dim,
        }
        if not p.exists():
            r.add_bug("High", "GAUSSIAN_CKPT_MISSING", f"checkpoint missing: {path}", entry)
            r.load_detail.setdefault("candidates", []).append(entry)
            continue
        entry["sha256"] = _sha256_file(p)
        try:
            # load_gaussian_model prepends models/ — strip if present
            mf = path
            if mf.replace("\\", "/").startswith("models/"):
                mf = mf.replace("\\", "/")[len("models/"):]
            model, scaler, meta = load_gaussian_model(mf)
            entry["loaded"] = True
            entry["model_n_features"] = getattr(model, "n_features", None)
            entry["meta_keys"] = list(meta.keys()) if isinstance(meta, dict) else type(meta).__name__
            entry["feature_order_hash_model"] = (meta or {}).get("feature_order_hash") if isinstance(meta, dict) else None
            entry["feature_schema"] = (meta or {}).get("feature_schema") if isinstance(meta, dict) else None
            entry["feature_schema_resolved"] = (meta or {}).get("feature_schema_resolved") if isinstance(meta, dict) else None
            entry["schema_alignment"] = (meta or {}).get("schema_alignment") if isinstance(meta, dict) else None
            entry["name_anchored"] = bool((meta or {}).get("name_anchored")) if isinstance(meta, dict) else False
            # schema may be on disk bundle
            bundle = json.loads(p.read_text(encoding="utf-8"))
            entry["bundle_feature_schema"] = bundle.get("feature_schema")
            entry["bundle_feature_order_hash"] = bundle.get("feature_order_hash")
            entry["runtime_feature_order_hash"] = FEATURE_ORDER_HASH
            entry["hash_match"] = (
                bundle.get("feature_order_hash") == FEATURE_ORDER_HASH
                if bundle.get("feature_order_hash") else False
            )
            r.load_detail.setdefault("candidates", []).append(entry)

            schema_saved = list(bundle.get("feature_schema") or [])
            schema_resolved = list(
                (meta or {}).get("feature_schema_resolved") or []
            )
            align = align_report(schema_saved, list(CANONICAL_FEATURE_ORDER), aliases=SCHEMA_V3_ALIASES)
            align["resolved_order"] = schema_resolved
            align["name_anchored"] = bool(schema_resolved)
            align["schema_alignment"] = (meta or {}).get("schema_alignment")
            r.feature_alignment[version] = align

            # Name-anchored contract (P0): raw name mismatch is expected for v3
            # checkpoints; resolved subset is the implementation truth.
            if schema_resolved and (meta or {}).get("name_anchored"):
                r.notes.append("name_anchored")
                r.add_bug(
                    "Low",
                    "GAUSSIAN_NAME_ANCHORED_OK",
                    f"Trained Gaussian {version} loads via name-anchored subset "
                    f"(alignment={(meta or {}).get('schema_alignment')}, "
                    f"n={len(schema_resolved)}); not ambient-vector truncate.",
                    {"resolved_dim": len(schema_resolved), "live_dim": len(CANONICAL_FEATURE_ORDER)},
                )
            elif not align["name_set_match"]:
                r.add_bug(
                    "Critical",
                    "GAUSSIAN_SCHEMA_DRIFT_V4",
                    f"Trained Gaussian {version} cannot name-align to live v4 schema",
                    {"missing": align["missing"], "extra": align["extra"], "dim_model": model.n_features},
                )

            # Execute primary (BNB 38) via name-anchored extract — never ambient slice
            if version.startswith("p5_") or not loaded_any:
                from features.gaussian_schema_contract import extract_model_feature_vector

                exceptions = 0
                fallback = 0
                confs = []
                order = schema_resolved or schema_saved
                for i, feat in enumerate(records):
                    try:
                        if order:
                            try:
                                vec = extract_model_feature_vector(feat, order)
                            except Exception:
                                # fallback: alias map saved names
                                vec_named = []
                                for name in order:
                                    if name in feat:
                                        vec_named.append(float(feat[name]))
                                    elif name in SCHEMA_V3_ALIASES and SCHEMA_V3_ALIASES[name] in feat:
                                        vec_named.append(float(feat[SCHEMA_V3_ALIASES[name]]))
                                    else:
                                        raise KeyError(name)
                                vec = vec_named
                        else:
                            fallback += 1
                            scores[i] = 0.5
                            continue
                        if len(vec) != model.n_features:
                            fallback += 1
                            scores[i] = 0.5
                            continue
                        scaled = scaler.transform_one(vec)
                        expected_rr, confidence, _probs = model.predict_expected_rr(scaled)
                        sc = 1.0 / (1.0 + math.exp(-float(expected_rr)))
                        scores[i] = max(0.0, min(1.0, sc))
                        confs.append(float(confidence))
                    except Exception as e:
                        exceptions += 1
                        scores[i] = float("nan")
                        if exceptions <= 3:
                            r.notes.append(f"gauss_ml[{i}]: {type(e).__name__}: {e}")
                r.executed = True
                loaded_any = True
                r.loaded = True
                r.runtime = {
                    "executed_version": version,
                    "exceptions": exceptions,
                    "fallback_dim_mismatch": fallback,
                    "n": len(records),
                    "path": "name_anchored_extract",
                    "confidence_stats": _stats(np.array(confs, dtype=float)) if confs else {},
                }
                r.output_stats = _stats(scores)
                # Contract-OK when name-anchored and scores produced without exception
                r.features_ok = bool(schema_resolved) and exceptions == 0 and fallback == 0
                r.outputs_healthy = exceptions == 0 and not r.output_stats.get("is_constant")
                # Not on live spine (gaussian_impl=heuristic) → ORPHAN even if contract-OK
                r.status = "EXECUTED_ORPHAN" if r.features_ok else (
                    "EXECUTED_WITH_SCHEMA_DRIFT" if not r.features_ok else "DEGRADED"
                )
                if r.features_ok and r.output_stats.get("is_saturated_near_bound"):
                    r.notes.append(
                        "scores saturated near 1.0 on XAUUSD — descriptive only; "
                        "no economic authority (research-only path)"
                    )
        except Exception as e:
            entry["loaded"] = False
            entry["error"] = f"{type(e).__name__}: {e}"
            r.load_detail.setdefault("candidates", []).append(entry)
            r.add_bug("Critical", "GAUSSIAN_CKPT_LOAD_FAIL", f"{version}: {e}", entry)

    if not r.loaded:
        r.status = "LOAD_FAIL"
    reports.append(r)
    return scores


def validate_zone_gate(records: List[dict], reports: List[ModelReport]) -> np.ndarray:
    """Validate the LIVE ZoneGate path (v4 remapped artifact), not the retired v3 file.

    Production truth (SCHEMA-V4-VECTOR-MIGRATION B6):
      engine_runner.zone_registry_path = models/zone_registry_v4_2026_07.json
      zone_gate_registry active = v4_gaussian_runtime_2026_07
      v3 models/zone_registry.json is retained and must still FAIL_CLOSED on load.
    """
    from engines.live_engine import get_zone_gate, ZoneFeatureOrderError, BitNetZoneGate
    from engines.zone_cluster_score import score_zone_cluster
    from features.feature_schema import CANONICAL_FEATURE_ORDER, SCHEMA_V3_ALIASES
    from config_layer.production_config import get_prod_section
    from config_layer.model_resolver import resolve_zone_gate_runtime
    from pathlib import Path as P

    r = ModelReport(model="ZoneGate", kind="trained")
    r.consumer = "fusion slot 'zone_gate' + hard gate (zone_mode=hard)"
    r.wiring = {
        "documented_intent": "feature-space neighbourhood historically good",
        "runtime_enabled": True,
        "active_models_status": "selected_and_enabled",
        "registry": "models/zone_gate_registry.json",
        "config_key": "engine_runner.zone_registry_path",
        "remap": "ALIGNMENT_REMAP v4 (macd_hist→macd_hist_z, wick_size→candle_range; session weight=0)",
    }

    scores = np.full(len(records), np.nan)
    reg_path = "models/zone_gate_registry.json"
    retired_v3 = "models/zone_registry.json"

    # Resolve production path (HOW + WHO parity)
    er = get_prod_section("engine_runner")
    how_path = str(er.get("zone_registry_path", ""))
    try:
        resolved = resolve_zone_gate_runtime(how_path=how_path)
        path = str(resolved.require_artifact()).replace("\\", "/")
        # prefer repo-relative if under cwd
        try:
            path = str(P(path).resolve().relative_to(ROOT)).replace("\\", "/")
        except Exception:
            pass
        r.load_detail["resolver"] = {
            "version": getattr(resolved, "version", None),
            "artifact_path": path,
            "identity_parity": getattr(resolved, "identity_parity", None),
            "how_path": how_path,
        }
    except Exception as e:
        path = how_path or "models/zone_registry_v4_2026_07.json"
        r.load_detail["resolver_error"] = f"{type(e).__name__}: {e}"
        r.add_bug("High", "ZONEGATE_RESOLVER_ERROR", str(e), how_path)

    r.wiring["artifact"] = path
    bundle = json.loads(P(path).read_text(encoding="utf-8")) if P(path).exists() else {}
    feature_order = list(bundle.get("feature_order") or [])
    r.load_detail.update({
        "artifact_path": path,
        "artifact_exists": P(path).exists(),
        "artifact_sha256": _sha256_file(P(path)) if P(path).exists() else None,
        "registry_path": reg_path,
        "registry_exists": P(reg_path).exists(),
        "n_zones": len(bundle.get("zones") or []),
        "schema_version": bundle.get("schema_version"),
        "feature_order_dim": len(feature_order),
        "feature_order": feature_order,
        "scored_dims_note": "38-name subset of 39-dim v4 (macd_hist_raw absent by design)",
    })

    if P(reg_path).exists():
        zreg = json.loads(P(reg_path).read_text(encoding="utf-8"))
        active = {k: v for k, v in zreg.items() if isinstance(v, dict) and v.get("active")}
        r.load_detail["registry_active"] = {
            k: {"model_file": v.get("model_file"), "version": v.get("version")}
            for k, v in active.items()
        }

    # Alignment: remapped names must be a subset of live schema (not necessarily equal)
    live = list(CANONICAL_FEATURE_ORDER)
    missing = [n for n in feature_order if n not in live]
    extra_live = [n for n in live if n not in set(feature_order)]
    r.feature_alignment = {
        "expected_trained_order": feature_order,
        "received_live_order": live,
        "trained_dim": len(feature_order),
        "live_dim": len(live),
        "missing_from_live": missing,
        "live_names_not_scored": extra_live,
        "renames_applied": dict(SCHEMA_V3_ALIASES),
        "name_set_subset_ok": missing == [],
        "has_macd_hist_z": "macd_hist_z" in feature_order,
        "has_candle_range": "candle_range" in feature_order,
        "no_v3_names": not ({"macd_hist", "wick_size"} & set(feature_order)),
    }
    r.features_ok = missing == [] and r.feature_alignment["no_v3_names"]

    # Retired v3 must still fail-closed (regression pin)
    try:
        BitNetZoneGate(zone_path=retired_v3)
        r.add_bug(
            "Critical",
            "ZONEGATE_V3_STILL_LOADS",
            "Retired v3 zone_registry.json loaded under v4 — safety net broken",
            retired_v3,
        )
        r.load_detail["v3_retired_load"] = "UNEXPECTED_OK"
    except ZoneFeatureOrderError as e:
        r.load_detail["v3_retired_load"] = f"FAIL_CLOSED_OK: {e}"
        r.notes.append("Retired v3 artifact correctly refuses load (fail-closed regression pin).")
    except Exception as e:
        r.load_detail["v3_retired_load"] = f"{type(e).__name__}: {e}"

    # Production v4 load
    try:
        zg = get_zone_gate(path)
        r.loaded = True
        r.load_detail["get_zone_gate"] = "OK"
        r.load_detail["gate_feature_order"] = getattr(zg, "feature_order", None)
        r.load_detail["n_zones_loaded"] = len(getattr(zg, "_zones", []) or [])
    except ZoneFeatureOrderError as e:
        r.loaded = False
        r.status = "LOAD_FAIL_SCHEMA"
        r.load_detail["get_zone_gate"] = f"ZoneFeatureOrderError: {e}"
        r.add_bug(
            "Critical",
            "ZONEGATE_V4_FEATURE_ORDER_BLOCK",
            f"Promoted v4 ZoneGate refused load: {e}",
            str(e),
        )
    except Exception as e:
        r.loaded = False
        r.status = "LOAD_FAIL"
        r.load_detail["get_zone_gate"] = f"{type(e).__name__}: {e}"
        r.add_bug("Critical", "ZONEGATE_LOAD_FAIL", str(e), traceback.format_exc(limit=4))

    # Execute production scoring path (score_zone_cluster — same as EngineRunner)
    if r.loaded and records:
        zcfg = er.get("zone_gate") or {}
        thr = float(er.get("zone_cluster_threshold", zcfg.get("threshold", 0.25)) or 0.25)
        # knobs from engine_runner
        try:
            thr = float(_cfg_thr) if (_cfg_thr := er.get("zone_cluster_threshold")) is not None else thr
        except Exception:
            pass
        cluster_min_n = int((zcfg.get("cluster_min_n") if isinstance(zcfg, dict) else None) or 2)
        cluster_spread_max = float((zcfg.get("cluster_spread_max") if isinstance(zcfg, dict) else None) or 0.15)
        # prefer strict keys if present under engine_runner
        for key, dest in (
            ("zone_cluster_threshold", "thr"),
        ):
            if key in er:
                try:
                    thr = float(er[key])
                except Exception:
                    pass

        exceptions = 0
        blocked = 0
        try:
            # Resolve knobs the way EngineRunner does when possible
            from config_layer.production_config import get_prod_section as _gps
            _er = _gps("engine_runner")
            _zg = _er.get("zone_gate") or {}
            top_k = int(_zg.get("top_k", 3))
            cluster_min_n = int(_zg.get("cluster_min_n", cluster_min_n))
            cluster_spread_max = float(_zg.get("cluster_spread_max", cluster_spread_max))
            # threshold: used by run_zone_gate_engine; hard mode historically 0.25-ish
            if "zone_min_samples" in _er:
                r.load_detail["zone_min_samples"] = _er["zone_min_samples"]
            r.load_detail["score_knobs"] = {
                "zone_cluster_threshold": thr,
                "cluster_min_n": cluster_min_n,
                "cluster_spread_max": cluster_spread_max,
                "top_k": top_k,
            }
        except Exception as e:
            r.notes.append(f"knob resolve soft: {e}")

        for i, feat in enumerate(records):
            try:
                out = score_zone_cluster(
                    feat,
                    zg,
                    zone_cluster_threshold=thr,
                    cluster_min_n=cluster_min_n,
                    cluster_spread_max=cluster_spread_max,
                )
                scores[i] = float(out.get("score", float("nan")))
                if not out.get("passed", False):
                    blocked += 1
            except Exception as e:
                exceptions += 1
                scores[i] = float("nan")
                if exceptions <= 3:
                    r.notes.append(f"zone[{i}]: {type(e).__name__}: {e}")

        r.executed = True
        r.runtime = {
            "mode": "production_score_zone_cluster",
            "production_path_executable": True,
            "exceptions": exceptions,
            "blocked": blocked,
            "block_rate": blocked / max(len(records), 1),
            "n": len(records),
            "artifact": path,
        }
        r.output_stats = _stats(scores)
        r.outputs_healthy = (
            exceptions == 0
            and not r.output_stats.get("is_constant")
            and r.features_ok
        )
        if r.features_ok and r.outputs_healthy:
            r.status = "OK"
        elif r.features_ok and exceptions == 0:
            # constant / saturated still DEGRADED not FAIL
            r.status = "EXECUTED_DEGRADED"
            if r.output_stats.get("is_constant"):
                r.add_bug(
                    "Medium",
                    "ZONEGATE_CONSTANT_OUTPUT",
                    "ZoneGate scores constant on this corpus (may be threshold/geometry inert — F-036 class)",
                    r.output_stats,
                )
        elif not r.features_ok:
            r.status = "FEATURE_MISALIGN"
        else:
            r.status = "DEGRADED"

    if r.status == "NOT_RUN":
        r.status = "LOAD_FAIL" if not r.loaded else "UNKNOWN"
    reports.append(r)
    return scores


def validate_rr_polarity(records: List[dict], reports: List[ModelReport]) -> np.ndarray:
    from engines.rr_engine import RREngine

    r = ModelReport(model="RR_polarity_engine", kind="rule_based")
    r.consumer = "fusion slot 'rr' ALWAYS (base RREngine); DecisionEngine low_rr gate (F-048)"
    r.wiring = {
        "documented_intent": "true reward-risk (historical name)",
        "runtime_truth": "Candle Polarity Index; NOT forward RR (semantic:candle_structure_quality)",
        "runtime_enabled": True,
        "rr_fusion_enabled": False,
        "file": "src/engines/rr_engine.py",
    }
    scores = np.full(len(records), np.nan)
    try:
        eng = RREngine({"min_rr": 1.5})
        r.loaded = True
        r.load_detail = {"engine": "RREngine", "checkpoint": None, "trained": False}
        needed = ["open", "high", "low", "close"]
        r.feature_alignment = align_report(needed, list(records[0].keys()) if records else needed)
        r.features_ok = True
        exceptions = 0
        reasons: Counter = Counter()
        for i, feat in enumerate(records):
            try:
                out = eng.compute(feat)
                scores[i] = float(out.get("score", float("nan")))
                reasons[str(out.get("reason", ""))[:40]] += 1
            except Exception as e:
                exceptions += 1
                if exceptions <= 3:
                    r.notes.append(str(e))
        r.executed = True
        r.runtime = {"exceptions": exceptions, "reason_sample": dict(reasons.most_common(5)), "n": len(records)}
        r.output_stats = _stats(scores)
        # polarity is in [0.5, 1.0] by design for non-doji
        r.outputs_healthy = exceptions == 0 and not r.output_stats.get("is_constant")
        r.status = "OK" if r.outputs_healthy else "DEGRADED"
        r.add_bug(
            "High",
            "RR_NAME_SEMANTIC_MISMATCH",
            "RREngine emits candle polarity ∈[0.5,1], not forward RR; DecisionEngine threshold 1.5 → structural low_rr (F-048)",
            {"score_range": [r.output_stats.get("min"), r.output_stats.get("max")], "decision_threshold": 1.5},
        )
    except Exception as e:
        r.status = "LOAD_FAIL"
        r.add_bug("Critical", "RR_POLARITY_FAIL", str(e), traceback.format_exc(limit=3))
    reports.append(r)
    return scores


def validate_rr_fusion(records: List[dict], reports: List[ModelReport]) -> np.ndarray:
    from config_layer.rr.rr_fusion import RRFusionLayer
    from config_layer.rr.rr_pattern_miner import NanoInferenceEngine
    from features.feature_schema import (
        CANONICAL_FEATURE_ORDER,
        SCHEMA_V3_ALIASES,
        FEATURE_ORDER_HASH,
    )
    from features.dataset_builder import extract_feature_vector
    from pathlib import Path as P

    r = ModelReport(model="RR_Fusion", kind="trained")
    r.consumer = "DISABLED on active config (engine_runner.rr_fusion.enabled=false); would mutate fusion rr slot when enabled"
    r.wiring = {
        "documented_intent": "trained NanoInference RR fusion over canonical features",
        "runtime_enabled": False,
        "active_models_status": "selected_not_enabled",
        "model_path": "models/rr_model.json",
        "registry": "models/rr_registry.json",
        "selection_version": "202605_bnb_v2_bnbusdt",
    }
    scores = np.full(len(records), np.nan)
    confidences = np.full(len(records), np.nan)
    statuses: Counter = Counter()

    path = "models/rr_model.json"
    p = P(path)
    r.load_detail = {
        "path": path,
        "exists": p.exists(),
        "sha256": _sha256_file(p) if p.exists() else None,
    }
    if p.exists():
        bundle = json.loads(p.read_text(encoding="utf-8"))
        r.load_detail.update({
            "n_features": bundle.get("n_features"),
            "feature_schema": bundle.get("feature_schema"),
            "n_train": bundle.get("n_train"),
            "zero_indices": bundle.get("zero_indices"),
            "ridge_alpha": bundle.get("ridge_alpha"),
            "has_conf_mu": "conf_mu" in bundle,
            "has_scale": "scale_mu" in bundle and "scale_sigma" in bundle,
        })

    # Registry selection vs file
    reg_path = P("models/rr_registry.json")
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        active = {k: v for k, v in reg.items() if isinstance(v, dict) and v.get("active")}
        r.load_detail["registry_active"] = {
            k: {"model_file": v.get("model_file"), "n_features": v.get("n_features")}
            for k, v in active.items()
        }
        # active points to rr_model_202605_bnb_v2.json but engine_runner uses models/rr_model.json
        for k, v in active.items():
            mf = str(v.get("model_file") or "").replace("\\", "/")
            if mf and mf != path and not path.endswith(Path(mf).name):
                r.add_bug(
                    "Medium",
                    "RR_REGISTRY_PATH_DRIFT",
                    f"Registry active '{k}' model_file={mf} but engine_runner.rr_fusion.model_path={path}",
                    {"registry_file": mf, "config_file": path},
                )

    # Feature alignment: model is 38-dim canonical_38 token, not name list
    expected_names_v3 = [
        # reconstruct v3 order from v4 + aliases inverse
    ]
    # Build synthetic v3 order from docs: v4 with macd_hist_raw+z collapsed to macd_hist, candle_range→wick_size
    v4 = list(CANONICAL_FEATURE_ORDER)
    # approximate reverse of v4 migration for alignment narrative
    v3_approx = []
    for n in v4:
        if n == "macd_hist_raw":
            continue  # drop raw; v3 had single hist
        if n == "macd_hist_z":
            v3_approx.append("macd_hist")
        elif n == "candle_range":
            v3_approx.append("wick_size")
        else:
            v3_approx.append(n)
    r.feature_alignment = {
        "model_declared_schema": r.load_detail.get("feature_schema"),
        "model_n_features": r.load_detail.get("n_features"),
        "runtime_dim": len(CANONICAL_FEATURE_ORDER),
        "runtime_feature_order_hash": FEATURE_ORDER_HASH,
        "v3_approx_order": v3_approx,
        "v3_approx_dim": len(v3_approx),
        "dim_match_v3": r.load_detail.get("n_features") == 38 and len(v3_approx) == 38,
        "note": (
            "P0 fail-closed: RRFusionLayer refuses load when model n_features != "
            "CANONICAL_FEATURE_DIM; NanoInferenceEngine.predict raises FeatureDimensionError "
            "on width mismatch (no silent truncate)."
        ),
    }
    r.features_ok = False  # cannot score ambient 39 against 38-dim checkpoint

    try:
        layer = RRFusionLayer(model_path=path, threshold=0.5, enabled=True)
        r.loaded = bool(layer.is_loaded)
        r.load_detail["rr_fusion_layer_loaded"] = layer.is_loaded
        r.load_detail["load_error"] = layer.load_error
        if not layer.is_loaded:
            err = layer.load_error or "not loaded"
            is_dim = "FeatureDimensionError" in err or "n_features" in err
            r.add_bug(
                "Critical" if is_dim else "High",
                "RR_FUSION_DIM_LOAD_REFUSED" if is_dim else "RR_FUSION_NOT_LOADED",
                err,
                {"fail_closed": True, "enabled_on_spine": False},
            )
            r.status = "LOAD_FAIL"
            r.notes.append("FAIL_CLOSED: load refused under schema v4 width mismatch (protective)")
            # Prove predict also refuses ambient 39 (no silent truncate)
            try:
                from config_layer.rr.rr_pattern_miner import (
                    NanoInferenceEngine,
                    FeatureDimensionError,
                )
                eng = NanoInferenceEngine.load(path)
                try:
                    eng.predict(
                        list(map(float, extract_feature_vector(records[0]))),
                        gaussian_score=0.5,
                        gaussian_p_win=0.5,
                    )
                    r.add_bug(
                        "Critical",
                        "RR_FUSION_INDEX_TRUNCATE_UNDER_V4",
                        "predict accepted overlong vector — FAIL_OPEN regression",
                        None,
                    )
                except FeatureDimensionError:
                    r.notes.append("predict correctly raises FeatureDimensionError on 39-dim input")
            except Exception as pe:
                r.notes.append(f"predict probe skipped: {pe}")
            reports.append(r)
            return scores

        engine = layer._engine  # NanoInferenceEngine
        exceptions = 0
        bypass = 0
        for i, feat in enumerate(records):
            try:
                vec = extract_feature_vector(feat)  # 39 floats in v4 order
                out = engine.predict(list(map(float, vec)), gaussian_score=0.5, gaussian_p_win=0.5)
                scores[i] = float(out.get("final_score", out.get("ml_score", float("nan"))))
                confidences[i] = float(out.get("confidence", float("nan")))
                st = str(out.get("status", ""))
                statuses[st] += 1
                if "bypass" in st.lower():
                    bypass += 1
            except Exception as e:
                exceptions += 1
                if exceptions <= 3:
                    r.notes.append(f"rrf[{i}]: {type(e).__name__}: {e}")
        r.executed = True
        r.runtime = {
            "exceptions": exceptions,
            "status_counts": dict(statuses),
            "n_bypass": bypass,
            "bypass_rate": bypass / max(len(records), 1),
            "n": len(records),
        }
        r.output_stats = {
            "final_score": _stats(scores),
            "confidence": _stats(confidences),
        }
        # F-044: confidence gate mis-scaled → near-100% bypass
        if bypass / max(len(records), 1) > 0.95:
            r.add_bug(
                "High",
                "RR_FUSION_CONFIDENCE_BYPASS_SATURATION",
                "≥95% predictions status=bypassed_low_confidence (F-044 dof mis-scale of exp(-0.5·d_sq))",
                r.runtime,
            )
        r.outputs_healthy = exceptions == 0 and bypass / max(len(records), 1) < 0.95
        r.status = "EXECUTED_DISABLED_ON_SPINE"
        r.notes.append("rr_fusion.enabled=false on active config — outputs not consumed by spine")
    except Exception as e:
        r.status = "LOAD_FAIL"
        r.add_bug("Critical", "RR_FUSION_FAIL", str(e), traceback.format_exc(limit=4))

    reports.append(r)
    return scores


def validate_tradenet(records: List[dict], reports: List[ModelReport]) -> np.ndarray:
    from pathlib import Path as P
    from features.feature_schema import CANONICAL_FEATURE_ORDER, SCHEMA_V3_ALIASES, FEATURE_ORDER_HASH
    from features.dataset_builder import extract_feature_vector

    r = ModelReport(model="TradeNet", kind="trained")
    r.consumer = "ORPHAN — fusion neural slot unwired (F-005); TradeNetMetaEngine not on live spine"
    r.wiring = {
        "documented_intent": "capital quality / p_win meta score",
        "runtime_enabled": False,
        "active_models_status": "selected_not_enabled / orphaned",
        "registry": "models/tradenet_registry.json",
        "selection_version": "v5_auto_2026_06_eth",
    }
    scores = np.full(len(records), np.nan)

    reg = json.loads(P("models/tradenet_registry.json").read_text(encoding="utf-8"))
    active = {k: v for k, v in reg.items() if isinstance(v, dict) and v.get("active")}
    r.load_detail = {"registry_active": active}

    # Prefer active ETH checkpoint
    target = None
    for k, v in active.items():
        target = (k, str(v.get("model_file", "")).replace("\\", "/"))
        break
    if target is None:
        r.status = "NO_ACTIVE"
        r.add_bug("High", "TRADENET_NO_ACTIVE", "No active TradeNet registry entry", None)
        reports.append(r)
        return scores

    version, mf = target
    p = P(mf)
    r.load_detail.update({
        "version": version,
        "model_file": mf,
        "exists": p.exists(),
        "sha256": _sha256_file(p) if p.exists() else None,
    })
    scaler_path = P(str(p).replace(".pth", "_scaler.json"))
    r.load_detail["scaler_path"] = str(scaler_path).replace("\\", "/")
    r.load_detail["scaler_exists"] = scaler_path.exists()

    # feature schema: ETH tradenet is 35-dim historically
    r.feature_alignment = {
        "selection_feature_schema_dim": 35,
        "runtime_dim": len(CANONICAL_FEATURE_ORDER),
        "runtime_hash": FEATURE_ORDER_HASH,
        "note": "TradeNetV2 slices/truncates by index; v4 39-dim → silent index misalignment risk",
    }
    r.features_ok = False
    r.add_bug(
        "High",
        "TRADENET_SCHEMA_DIM_MISMATCH",
        "Selected TradeNet trained at dim=35; runtime schema is v4 dim=39 with renames — index slice is unsafe",
        r.feature_alignment,
    )

    if not p.exists():
        r.status = "LOAD_FAIL"
        r.add_bug("Critical", "TRADENET_CKPT_MISSING", f"missing {mf}", None)
        reports.append(r)
        return scores

    try:
        # Try TradeNetV2 first, then trainer.load_model
        model = None
        n_features = None
        try:
            from training.trade_net_v2 import TradeNetV2
            tn = TradeNetV2(model_path=str(p))
            model = tn
            n_features = getattr(tn, "_v1_n_features", None) or 35
            r.load_detail["loader"] = "TradeNetV2"
            r.load_detail["n_features"] = n_features
            r.loaded = True
        except Exception as e1:
            r.load_detail["TradeNetV2_error"] = f"{type(e1).__name__}: {e1}"
            try:
                from training.trainer import load_model, load_tradenet_scaler
                # load_model expects name under models/
                name = mf
                if name.replace("\\", "/").startswith("models/"):
                    name = name.replace("\\", "/")[len("models/"):]
                # strip .pth
                if name.endswith(".pth"):
                    name = name[:-4]
                model = load_model(name)
                scaler = load_tradenet_scaler(name)
                r.load_detail["loader"] = "trainer.load_model"
                r.load_detail["scaler_loaded"] = scaler is not None
                r.loaded = model is not None
            except Exception as e2:
                r.load_detail["trainer_load_error"] = f"{type(e2).__name__}: {e2}"
                r.status = "LOAD_FAIL"
                r.add_bug("Critical", "TRADENET_LOAD_FAIL", f"{e1} | {e2}", None)
                reports.append(r)
                return scores

        exceptions = 0
        # Prefer TradeNetMetaEngine path for end-to-end
        try:
            from engines.tradenet_meta_engine import TradeNetMetaEngine
            meta_eng = TradeNetMetaEngine({}, preload=True)
            r.load_detail["meta_engine_loaded"] = not meta_eng._load_failed
            r.load_detail["meta_version"] = meta_eng._version
            r.load_detail["meta_n_features"] = meta_eng._n_features
            if meta_eng._load_failed:
                r.add_bug(
                    "High",
                    "TRADENET_META_LOAD_FAILED",
                    "TradeNetMetaEngine preload failed — compute will return neutral fallback",
                    r.load_detail,
                )
            for i, feat in enumerate(records):
                try:
                    out = meta_eng.compute(
                        feat,
                        gaussian_result={"score": 0.5},
                        rr_result={"score": 0.5},
                        zone_result={"score": 0.5},
                    )
                    scores[i] = float(out.get("capital_quality_score", out.get("score", float("nan"))))
                except Exception as e:
                    exceptions += 1
                    if exceptions <= 3:
                        r.notes.append(f"tn[{i}]: {type(e).__name__}: {e}")
            r.executed = True
            r.runtime = {
                "path": "TradeNetMetaEngine.compute",
                "exceptions": exceptions,
                "n": len(records),
                "load_failed_flag": meta_eng._load_failed,
            }
            r.output_stats = _stats(scores)
            # detect neutral fallback constant
            if r.output_stats.get("is_constant"):
                r.add_bug(
                    "High",
                    "TRADENET_CONSTANT_FALLBACK",
                    "TradeNet outputs constant — likely fallback path, not model inference",
                    r.output_stats,
                )
            r.outputs_healthy = exceptions == 0 and not r.output_stats.get("is_constant")
            r.status = "EXECUTED_ORPHAN"
        except Exception as e:
            # raw predict
            r.notes.append(f"meta path failed: {e}; trying raw")
            if hasattr(model, "predict"):
                for i, feat in enumerate(records):
                    try:
                        out = model.predict(feat)
                        if isinstance(out, dict):
                            scores[i] = float(out.get("p_win", out.get("score", float("nan"))))
                        elif out is not None:
                            scores[i] = float(out)
                    except Exception as e3:
                        exceptions += 1
                        if exceptions <= 3:
                            r.notes.append(str(e3))
                r.executed = True
                r.runtime = {"path": "raw_predict", "exceptions": exceptions, "n": len(records)}
                r.output_stats = _stats(scores)
                r.outputs_healthy = exceptions == 0 and not r.output_stats.get("is_constant")
                r.status = "EXECUTED_ORPHAN"
            else:
                r.status = "EXEC_FAIL"
                r.add_bug("Critical", "TRADENET_NO_PREDICT", str(e), None)
    except Exception as e:
        r.status = "LOAD_FAIL"
        r.add_bug("Critical", "TRADENET_FAIL", str(e), traceback.format_exc(limit=4))

    reports.append(r)
    return scores


def validate_bitnet(records: List[dict], reports: List[ModelReport]) -> np.ndarray:
    from pathlib import Path as P
    from features.feature_schema import CANONICAL_FEATURE_ORDER

    r = ModelReport(model="BitNet", kind="trained")
    r.consumer = "CRT hard-reject gate WHEN use_bitnet=true (score<0.55); INERT on active (use_bitnet=false, F-004)"
    r.wiring = {
        "documented_intent": "acceptability gate on market state",
        "runtime_enabled": False,
        "active_models_status": "catalogued_not_selected",
        "registry": "models/bitnet/bitnet_registry.json",
        "config_use_bitnet": False,
        "engine_runner.model_path": "results/model_export_format.json",
        "governance": "Exists≠Selected≠Enabled; require_selection_when_enabled",
    }
    scores = np.full(len(records), np.nan)

    reg_path = P("models/bitnet/bitnet_registry.json")
    reg_raw = reg_path.read_text(encoding="utf-8") if reg_path.exists() else ""
    reg = json.loads(reg_raw) if reg_raw.strip() else {}
    gov = reg.get("_governance") if isinstance(reg, dict) else {}
    entries = {
        k: v for k, v in (reg or {}).items()
        if isinstance(v, dict) and not str(k).startswith("_") and "model_file" in v
    }
    r.load_detail = {
        "registry_path": str(reg_path).replace("\\", "/"),
        "registry_exists": reg_path.exists(),
        "registry_empty": not entries,
        "registry_bytes": len(reg_raw),
        "catalog_versions": list(entries.keys()),
        "active_versions": [k for k, v in entries.items() if v.get("active")],
        "composition_default": (gov or {}).get("composition_default_version"),
        "model_json_exists": P("model.json").exists(),
        "export_exists": P("results/model_export_format.json").exists(),
    }
    if r.load_detail["registry_empty"]:
        r.add_bug(
            "Critical",
            "BITNET_REGISTRY_EMPTY",
            "models/bitnet/bitnet_registry.json has no catalog entries",
            r.load_detail,
        )
    else:
        r.notes.append(
            f"BitNet registry catalogued: {r.load_detail['catalog_versions']}; "
            f"selection={r.load_detail['active_versions'] or None}; "
            f"composition_default={r.load_detail['composition_default']}"
        )

    # Try bitnet_score composition path (production CRT path)
    try:
        from bitnet.bitnet_inference import bitnet_score, BitNetModel

        # Probe composition
        try:
            s0 = bitnet_score(records[0]) if records else None
            r.load_detail["bitnet_score_probe"] = s0
            r.loaded = True
            exceptions = 0
            for i, feat in enumerate(records):
                try:
                    scores[i] = float(bitnet_score(feat))
                except Exception as e:
                    exceptions += 1
                    scores[i] = float("nan")
                    if exceptions <= 3:
                        r.notes.append(f"bitnet_score[{i}]: {type(e).__name__}: {e}")
            r.executed = True
            r.runtime = {
                "path": "bitnet_score (composition)",
                "exceptions": exceptions,
                "n": len(records),
            }
            r.output_stats = _stats(scores)
            r.features_ok = exceptions == 0
            r.outputs_healthy = exceptions == 0 and not r.output_stats.get("is_constant")
            r.status = "EXECUTED_DISABLED_ON_SPINE"
            # feature contract for legacy 6-input
            r.feature_alignment = {
                "legacy_6_input": ["body_ratio", "retest_depth", "disp_strength", "atr", "candles_since_retest", "double_sweep"],
                "model_json_feature_order": json.loads(P("model.json").read_text(encoding="utf-8")).get("feature_order")
                if P("model.json").exists() else None,
                "export_input_dim": json.loads(P("results/model_export_format.json").read_text(encoding="utf-8")).get("input_dim")
                if P("results/model_export_format.json").exists() else None,
                "note": "CRT serve path uses 6-key legacy; export format is 35-dim — two incompatible schemas",
            }
            if P("model.json").exists() and P("results/model_export_format.json").exists():
                m6 = json.loads(P("model.json").read_text(encoding="utf-8")).get("feature_order")
                m35 = json.loads(P("results/model_export_format.json").read_text(encoding="utf-8")).get("feature_order")
                if m6 and m35 and m6 != m35:
                    r.add_bug(
                        "Low",
                        "BITNET_DUAL_SCHEMA",
                        "INTENTIONAL dual-schema fork: composition_default=legacy_6input; "
                        "HOW pin=export 35-dim. Documented in bitnet_registry governance — "
                        "not unified until a single serve contract is chosen.",
                        {"legacy_dim": len(m6), "export_dim": len(m35 or [])},
                    )
        except Exception as e:
            r.load_detail["bitnet_score_error"] = f"{type(e).__name__}: {e}"
            # Try raw BitNetModel on model.json
            try:
                bm = BitNetModel("model.json")
                r.loaded = True
                r.load_detail["BitNetModel_model_json"] = "OK"
                r.load_detail["input_dim"] = getattr(bm, "input_dim", None) or getattr(bm, "n_features", None)
                # legacy 6
                keys = ["body_ratio", "retest_depth", "disp_strength", "atr", "candles_since_retest", "double_sweep"]
                exceptions = 0
                for i, feat in enumerate(records):
                    try:
                        vec = np.array([float(feat.get(k, 0.0)) for k in keys], dtype=np.float32)
                        # may need different dim
                        scores[i] = float(bm.predict(vec))
                    except Exception as e2:
                        exceptions += 1
                        if exceptions <= 3:
                            r.notes.append(f"BitNetModel[{i}]: {type(e2).__name__}: {e2}")
                r.executed = exceptions < len(records)
                r.runtime = {"path": "BitNetModel(model.json)", "exceptions": exceptions, "n": len(records)}
                r.output_stats = _stats(scores)
                r.status = "EXECUTED_PARTIAL" if r.executed else "EXEC_FAIL"
                r.features_ok = False
            except Exception as e3:
                r.status = "CANNOT_EXECUTE"
                r.add_bug(
                    "Critical",
                    "BITNET_CANNOT_EXECUTE",
                    f"No executable BitNet path: registry empty; bitnet_score failed; BitNetModel failed: {e3}",
                    {"bitnet_score": str(e), "BitNetModel": str(e3)},
                )
    except Exception as e:
        r.status = "LOAD_FAIL"
        r.add_bug("Critical", "BITNET_IMPORT_FAIL", str(e), traceback.format_exc(limit=3))

    # Always record that spine does not enable it
    r.notes.append("crt_engine.use_bitnet=false on ACTIVE_VERSION v2_multi_2026_04 — dead path even if inference works")
    reports.append(r)
    return scores


def cross_model_comparison(series: Dict[str, np.ndarray]) -> dict:
    keys = [k for k, v in series.items() if v is not None and np.isfinite(v).sum() > 100]
    corr = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            x, y = series[a], series[b]
            mask = np.isfinite(x) & np.isfinite(y)
            if mask.sum() < 100:
                continue
            xa, yb = x[mask], y[mask]
            if xa.std() < 1e-12 or yb.std() < 1e-12:
                c = None
            else:
                c = float(np.corrcoef(xa, yb)[0, 1])
            corr[f"{a}__{b}"] = c
    # unique info: low max |corr| with others
    uniqueness = {}
    for a in keys:
        vals = []
        for k, c in corr.items():
            if c is None:
                continue
            if k.startswith(a + "__") or k.endswith("__" + a):
                vals.append(abs(c))
        uniqueness[a] = {
            "max_abs_corr_with_peer": max(vals) if vals else None,
            "mean_abs_corr_with_peer": float(np.mean(vals)) if vals else None,
        }
    return {"pearson": corr, "uniqueness": uniqueness, "models_compared": keys}


def classify_wiring(reports: List[ModelReport]) -> dict:
    return {
        "reachable": [r.model for r in reports if r.wiring.get("runtime_enabled")],
        "disabled": [r.model for r in reports if r.wiring.get("runtime_enabled") is False],
        "unused_or_orphaned": [
            r.model for r in reports
            if "ORPHAN" in (r.consumer or "").upper()
            or "orphan" in str(r.wiring.get("active_models_status", "")).lower()
            or r.status in {"EXECUTED_ORPHAN", "EXECUTED_DISABLED_ON_SPINE"}
        ],
        "dead_execution_paths": [
            r.model for r in reports
            if r.status in {"LOAD_FAIL", "LOAD_FAIL_SCHEMA", "CANNOT_EXECUTE", "NO_ACTIVE"}
            or any(b["severity"] == "Critical" for b in r.bugs)
        ],
        "rule_based_baseline": [r.model for r in reports if r.kind == "rule_based"],
    }


def build_execution_matrix(reports: List[ModelReport]) -> List[dict]:
    rows = []
    for r in reports:
        r.finalize_failure_mode()
        rows.append({
            "Model": r.model,
            "Loaded": r.loaded,
            "Executed": r.executed,
            "Features OK": r.features_ok,
            "Outputs Healthy": r.outputs_healthy,
            "Consumer": r.consumer,
            "Status": r.status,
            "Failure Mode": r.failure_mode,
            "Failure Mode Meaning": FAILURE_MODE_MEANING.get(r.failure_mode, ""),
        })
    return rows


def severity_rank(bugs: List[dict]) -> List[dict]:
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    return sorted(bugs, key=lambda b: (order.get(b.get("severity"), 9), b.get("code", "")))


def write_markdown(payload: dict) -> None:
    lines = []
    lines.append("# Implementation Model Validation — XAUUSD (Frozen Corpus)")
    lines.append("")
    lines.append(f"**Date:** {payload['meta']['timestamp']}")
    lines.append(f"**ACTIVE_VERSION:** `{payload['meta']['active_version']}`")
    lines.append(f"**Corpus:** `{payload['corpus']['path']}` sha256=`{payload['corpus']['sha256'][:16]}…` pin_match={payload['corpus']['pin_match']}")
    lines.append(f"**Rows scored:** {payload['features']['n_rows_after_finalize']} (schema **{payload['features']['schema_version_runtime']}** dim={payload['features']['canonical_feature_dim']})")
    lines.append("")
    lines.append("> Scope: implementation correctness only. No profitability, no threshold optimisation, no promotion.")
    lines.append("")
    lines.append("## 1. Execution Matrix")
    lines.append("")
    lines.append("### Failure-mode taxonomy")
    lines.append("")
    lines.append("| Status | Meaning | Action |")
    lines.append("|---|---|---|")
    lines.append("| PASS | Executed correctly | No action |")
    lines.append("| FAIL_CLOSED | Correctly refused invalid contract | Fix schema/registry |")
    lines.append("| FAIL_OPEN | Executed with invalid assumptions | **Critical** |")
    lines.append("| DEGRADED | Executes with reduced information | Investigate |")
    lines.append("| DISABLED | Configuration choice | None |")
    lines.append("| ORPHAN | Outputs with no consumer | Architecture review |")
    lines.append("| GOVERNANCE_INCOMPLETE | Runtime works; selection/registry incomplete | Complete registry |")
    lines.append("")
    lines.append("| Model | Loaded | Executed | Features OK | Outputs Healthy | Failure Mode | Consumer | Raw Status |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in payload["execution_matrix"]:
        fm = row.get("Failure Mode", row.get("Status", ""))
        lines.append(
            f"| {row['Model']} | {row['Loaded']} | {row['Executed']} | {row['Features OK']} | "
            f"{row['Outputs Healthy']} | **`{fm}`** | {str(row['Consumer'])[:50]} | `{row['Status']}` |"
        )
    lines.append("")
    # Highlight the sole FAIL_OPEN if present
    fail_open = [row for row in payload["execution_matrix"] if row.get("Failure Mode") == "FAIL_OPEN"]
    if fail_open:
        lines.append(
            f"> **Danger path:** {', '.join(r['Model'] for r in fail_open)} — "
            "FAIL_OPEN (executed under invalid contract assumptions)."
        )
        lines.append("")
    lines.append("## 2. Bug Report (severity-ranked)")
    lines.append("")
    for i, b in enumerate(payload["bug_report"], 1):
        lines.append(f"### {i}. [{b['severity']}] `{b['code']}` — {b.get('model', '?')}")
        lines.append("")
        lines.append(b["message"])
        lines.append("")
        if b.get("evidence") is not None:
            ev = b["evidence"]
            if isinstance(ev, (dict, list)):
                lines.append("```json")
                lines.append(json.dumps(ev, indent=2, default=str)[:2000])
                lines.append("```")
            else:
                lines.append(f"Evidence: `{ev}`")
            lines.append("")
    lines.append("## 3. Misalignment Report")
    lines.append("")
    for m in payload["misalignment_report"]:
        lines.append(f"### {m['model']}")
        lines.append("")
        lines.append(m["summary"])
        lines.append("")
        if m.get("detail"):
            lines.append("```json")
            lines.append(json.dumps(m["detail"], indent=2, default=str)[:2500])
            lines.append("```")
            lines.append("")
    lines.append("## 4. Architecture Observations")
    lines.append("")
    for obs in payload["architecture_observations"]:
        lines.append(f"- {obs}")
    lines.append("")
    lines.append("## 5. Wiring Classification")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(payload["wiring_classification"], indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 6. Cross-Model Comparison (Pearson on finite scores)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(payload["cross_model"], indent=2, default=str)[:4000])
    lines.append("```")
    lines.append("")
    lines.append("## 7. Per-Model Output Statistics")
    lines.append("")
    for r in payload["models"]:
        lines.append(f"### {r['model']} (`{r['status']}`)")
        lines.append("")
        lines.append(f"- kind: {r['kind']}")
        lines.append(f"- loaded/executed/features_ok/healthy: {r['loaded']}/{r['executed']}/{r['features_ok']}/{r['outputs_healthy']}")
        lines.append(f"- consumer: {r['consumer']}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(r.get("output_stats") or {}, indent=2, default=str)[:1500])
        lines.append("```")
        lines.append("")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_MD}")


def main() -> int:
    from config_layer.production_config import get_active_version

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"=== Implementation Model Validation XAUUSD @ {ts} ===")
    print(f"ACTIVE_VERSION={get_active_version()}")

    df, corpus_meta = load_corpus()
    print(f"Corpus OK: {corpus_meta['rows']} rows pin_match={corpus_meta['pin_match']}")

    enriched, vectors, feat_info = build_features(df)
    print(f"Features: shape={vectors.shape} schema={feat_info['schema_version_runtime']} dim={feat_info['canonical_feature_dim']}")
    records = row_feature_dicts(enriched)
    print(f"Feature dicts: {len(records)}")

    reports: List[ModelReport] = []
    series: Dict[str, np.ndarray] = {}

    print("--- CRT (rule-based baseline) ---")
    series["CRT_state"] = validate_crt(enriched, reports)

    print("--- Gaussian heuristic (live) ---")
    series["Gaussian_heuristic"] = validate_gaussian_heuristic(records, reports)

    print("--- Gaussian trained NB ---")
    series["Gaussian_trained"] = validate_gaussian_trained(records, reports)

    print("--- ZoneGate ---")
    series["ZoneGate"] = validate_zone_gate(records, reports)

    print("--- RR polarity ---")
    series["RR_polarity"] = validate_rr_polarity(records, reports)

    print("--- RR Fusion ---")
    series["RR_Fusion"] = validate_rr_fusion(records, reports)

    print("--- TradeNet ---")
    series["TradeNet"] = validate_tradenet(records, reports)

    print("--- BitNet ---")
    series["BitNet"] = validate_bitnet(records, reports)

    for r in reports:
        r.finalize_failure_mode()
    matrix = build_execution_matrix(reports)
    all_bugs = []
    for r in reports:
        for b in r.bugs:
            all_bugs.append({**b, "model": r.model})
    all_bugs = severity_rank(all_bugs)

    misalign = []
    for r in reports:
        if not r.features_ok or r.feature_alignment:
            misalign.append({
                "model": r.model,
                "summary": (
                    "Feature alignment FAILED" if not r.features_ok
                    else "Feature alignment noted (see detail)"
                ),
                "detail": r.feature_alignment,
            })

    arch = [
        "Runtime feature schema is v4.0 (39-dim): macd_hist split + wick_size→candle_range. "
        "All 38-dim trained artifacts (ZoneGate, RR fusion, Gaussian NB) predate this migration.",
        "Live Gaussian path is heuristic 3-feature kernel with mu/σ defaults — trained registry "
        "checkpoints are selected for BNB/ETH only and are not consumed when gaussian_impl=heuristic (F-060).",
        "ZoneGate is documented selected_and_enabled, but load-time ZoneFeatureOrderError now blocks "
        "EngineRunner construction under v4 — production hard-gate is currently unstartable without remap.",
        "RR fusion checkpoint loads and scores, but engine_runner.rr_fusion.enabled=false (F-038); "
        "confidence gate saturates bypass (F-044); index truncation under v4 is a new misalignment class.",
        "TradeNet is orphaned (F-005) — registry has an active ETH checkpoint but no spine consumer.",
        "BitNet registry is empty {}; use_bitnet=false — dual schema (legacy 6 vs export 35) remains.",
        "RREngine polarity vs DecisionEngine rr_threshold=1.5 is a structural consumer mismatch (F-048).",
        "CRT remains the only fully reachable, schema-independent decision generator on the spine.",
    ]

    payload = {
        "meta": {
            "timestamp": ts,
            "active_version": get_active_version(),
            "purpose": "implementation_validation",
            "not": ["profitability", "optimisation", "promotion", "retrain"],
        },
        "corpus": corpus_meta,
        "features": {**feat_info, "n_rows_after_finalize": len(enriched)},
        "failure_mode_taxonomy": FAILURE_MODE_MEANING,
        "execution_matrix": matrix,
        "bug_report": all_bugs,
        "misalignment_report": misalign,
        "architecture_observations": arch,
        "wiring_classification": classify_wiring(reports),
        "cross_model": cross_model_comparison(series),
        "models": [asdict(r) for r in reports],
        "failure_mode_summary": {
            r.model: r.failure_mode for r in reports
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_ts = OUT_DIR / f"xauusd_model_validation_{ts}.json"
    out_latest = OUT_DIR / "xauusd_model_validation_LATEST.json"
    text = json.dumps(payload, indent=2, default=str)
    out_ts.write_text(text, encoding="utf-8")
    out_latest.write_text(text, encoding="utf-8")
    print(f"Wrote {out_ts}")
    print(f"Wrote {out_latest}")

    write_markdown(payload)

    # Console matrix
    print("\n=== EXECUTION MATRIX ===")
    print(f"{'Model':28} {'Load':5} {'Exec':5} {'Feat':5} {'Hlth':5} {'FailureMode':22} {'RawStatus'}")
    for row in matrix:
        print(
            f"{row['Model']:28} {str(row['Loaded']):5} {str(row['Executed']):5} "
            f"{str(row['Features OK']):5} {str(row['Outputs Healthy']):5} "
            f"{str(row.get('Failure Mode','')):22} {row['Status']}"
        )
    print(f"\nBugs: {len(all_bugs)} "
          f"(Critical={sum(1 for b in all_bugs if b['severity']=='Critical')}, "
          f"High={sum(1 for b in all_bugs if b['severity']=='High')}, "
          f"Medium={sum(1 for b in all_bugs if b['severity']=='Medium')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
