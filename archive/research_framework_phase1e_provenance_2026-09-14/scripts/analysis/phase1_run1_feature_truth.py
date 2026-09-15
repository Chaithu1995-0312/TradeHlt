#!/usr/bin/env python3
"""Phase 1 RUN 1 — Legacy baseline verification (1A) + feature universe census (1B).

Read-only w.r.t. production feature formulas / model enablement / artifacts.
Preserves prior FC-* evidence; writes append-only phase1_run1_* artifacts.

  python scripts/analysis/phase1_run1_feature_truth.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DATE = "2026-07-10"
GOV = ROOT / "docs" / "governance"

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_PHYSICAL_PATH,
    PHASE1_ROWS,
    PHASE1_SHA256,
    PHASE1_STATUS,
    require_phase1_frozen_candidate,
)
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW  # noqa: E402
from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
)

LEGACY_SEM = GOV / "legacy_feature_semantics_v1-2026-07-10.json"
LEGACY_FP = GOV / "legacy_feature_output_fingerprint_xauusd-2026-07-10.json"

IMPL_PATHS = [
    "src/features/feature_pipeline.py",
    "src/features/candle_math.py",
    "src/features/derived_math.py",
    "src/features/feature_schema.py",
    "src/features/crt_feature_builder.py",
    "src/features/dataset_builder.py",
    "src/features/formula_registry.py",
    "configs/formulas/market_ontology.yaml",
]

# High-signal names that indicate feature mathematics (not all hits are quantities).
FEATUREISH_NAMES = {
    "open", "high", "low", "close", "volume", "volume_ratio", "volume_spike",
    "double_sweep", "ema_fast", "ema_slow", "ema_spread", "trend_bias",
    "trend_strength", "momentum_score", "atr", "atr_14", "volatility_ratio",
    "rsi_14", "macd_line", "macd_signal", "macd_hist", "sweep_detected",
    "liquidity_sweep", "break_of_structure", "swing_high", "swing_low",
    "higher_high", "lower_low", "body_size", "wick_size", "body_ratio",
    "volatility_regime", "session", "hour_of_day", "disp_strength",
    "retest_depth", "candles_since_retest", "liquidity_distance",
    "liquidity_pressure_score", "displacement_retrace", "displacement_atr_ratio",
    "volume_range_proxy", "last_swing_high", "last_swing_low",
    "last_swing_high_price", "last_swing_low_price", "retest_flag",
    "true_range", "body", "upper_wick", "lower_wick", "candle_range",
    "disp_str", "displacement", "time_decay_feature", "gaussian_score",
    "zone_score", "rr_ratio", "confidence",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _git() -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=ROOT
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, cwd=ROOT
            ).strip()
        )
        return commit, dirty
    except Exception:
        return "UNKNOWN", True


# ── 1A Legacy baseline ──────────────────────────────────────────────────────


def verify_legacy_baseline() -> dict[str, Any]:
    require_phase1_frozen_candidate(repo_root=ROOT)
    for k in ("TRUST_SWING_CAUSAL", "TRUST_VOLREGIME_CAUSAL"):
        os.environ.pop(k, None)

    commit, dirty = _git()
    leg = json.loads(LEGACY_SEM.read_text(encoding="utf-8"))
    stored_fp = json.loads(LEGACY_FP.read_text(encoding="utf-8"))

    impl_now = {}
    impl_match = {}
    for p in IMPL_PATHS:
        path = ROOT / p
        if not path.is_file():
            impl_now[p] = None
            impl_match[p] = False
            continue
        rec = {"sha256": _sha(path), "size_bytes": path.stat().st_size}
        impl_now[p] = rec
        frozen = (leg.get("implementation_hashes") or {}).get(p) or (
            stored_fp.get("implementation_hashes") or {}
        ).get(p)
        impl_match[p] = bool(frozen and frozen.get("sha256") == rec["sha256"])

    # Live fingerprint
    path = ROOT / PHASE1_PHYSICAL_PATH
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    pipe = FeaturePipeline(df)
    enriched, vectors = pipe.run()
    mat = enriched[list(CANONICAL_FEATURES)].astype(np.float32).to_numpy()
    joint = hashlib.sha256(mat.tobytes(order="C")).hexdigest()
    col_hashes = {
        name: hashlib.sha256(mat[:, i].tobytes(order="C")).hexdigest()
        for i, name in enumerate(CANONICAL_FEATURES)
    }
    ts = pd.to_datetime(enriched["timestamp"])
    live_fp = {
        "rows_after_finalize": int(len(enriched)),
        "vector_rows": int(len(vectors)),
        "first_timestamp": str(ts.iloc[0]),
        "last_timestamp": str(ts.iloc[-1]),
        "feature_order": list(CANONICAL_FEATURES),
        "n_features": len(CANONICAL_FEATURES),
        "joint_float32_sha256": joint,
        "per_column_float32_sha256": col_hashes,
        "dtype": "float32",
    }

    stored_out = stored_fp["output"]
    output_match = {
        "joint_float32_sha256": joint == stored_out["joint_float32_sha256"],
        "rows_after_finalize": live_fp["rows_after_finalize"]
        == stored_out["rows_after_finalize"],
        "feature_order": list(CANONICAL_FEATURES) == list(stored_out["feature_order"]),
        "per_column_float32_sha256": col_hashes
        == stored_out["per_column_float32_sha256"],
        "n_features": len(CANONICAL_FEATURES) == stored_out["n_features"],
    }
    fingerprint_reproducible = all(output_match.values())

    divergences = []
    if not fingerprint_reproducible:
        for k, ok in output_match.items():
            if not ok:
                divergences.append(
                    {
                        "kind": "OUTPUT_FINGERPRINT_MISMATCH",
                        "field": k,
                        "stored": stored_out.get(k)
                        if k != "per_column_float32_sha256"
                        else "see stored file",
                        "live": live_fp.get(k)
                        if k != "per_column_float32_sha256"
                        else "see live recomputation",
                    }
                )
    for p, ok in impl_match.items():
        if not ok and p in (leg.get("implementation_hashes") or {}):
            divergences.append(
                {
                    "kind": "IMPLEMENTATION_HASH_DRIFT",
                    "path": p,
                    "frozen_sha256": leg["implementation_hashes"][p]["sha256"],
                    "current_sha256": (impl_now.get(p) or {}).get("sha256"),
                    "note": "code hash drifted; output may still match if change is non-semantic",
                }
            )
        elif not ok and p not in (leg.get("implementation_hashes") or {}):
            divergences.append(
                {
                    "kind": "IMPLEMENTATION_HASH_NOT_IN_LEGACY_FREEZE",
                    "path": p,
                    "current_sha256": (impl_now.get(p) or {}).get("sha256"),
                }
            )

    # Known defects from prior evidence (descriptive — not automatic closure)
    known_defects = {
        "PIT": [
            "centered swing center=True publishes at t with future k (PASS-A / FC-0.5)",
            "12-feature transitive LEAKING swing closure (FC-0.5 graph; re-verify in 1C)",
        ],
        "formula_collisions": [
            "volume vs T-003 high-low proxy same column",
            "disp_strength FM-020 vs displacement_atr_ratio FM-028",
            "retest_depth FM-021 vs displacement_retrace FM-027",
        ],
        "semantic_substitutions": [
            "T-003 may rewrite volume under same name",
            "BitNet alias map CRT FM into pipeline names when use_bitnet",
        ],
        "batch_runtime": [
            "volatility_regime global full-batch rank (GLOBAL_FIT)",
            "live_engine_hook batch/live parity BLOCKED_PENDING_EVIDENCE (FC-0.5)",
        ],
        "config_dependent": [
            "TRUST_SWING_CAUSAL env",
            "TRUST_VOLREGIME_CAUSAL env (expanding|rolling)",
        ],
    }

    if fingerprint_reproducible:
        status = "VERIFIED_REPRODUCIBLE"
        # Note implementation drift separately — does not demote output reproducibility
        if any(d["kind"] == "IMPLEMENTATION_HASH_DRIFT" for d in divergences):
            status = "VERIFIED_REPRODUCIBLE"
            note = (
                "Output fingerprint byte-identical to freeze despite implementation "
                "hash drift on tracked paths — treat drift as evidence for RUN 2, "
                "not automatic invalidation of LEGACY freeze reproducibility."
            )
        else:
            note = "Output fingerprint and core freeze hashes align."
    else:
        status = "BLOCKED:OUTPUT_FINGERPRINT_NOT_REPRODUCIBLE"
        note = "Live FeaturePipeline output diverges from frozen fingerprint."

    return {
        "_doc": "Phase 1A legacy baseline verification. Not VALIDATED/APPROVED/AUTHORITATIVE.",
        "generated_at_utc": _now(),
        "LEGACY_BASELINE_STATUS": status,
        "note": note,
        "repository_commit": commit,
        "worktree_dirty": dirty,
        "legacy_freeze_ref": str(LEGACY_SEM.relative_to(ROOT)).replace("\\", "/"),
        "legacy_fingerprint_ref": str(LEGACY_FP.relative_to(ROOT)).replace("\\", "/"),
        "legacy_freeze_commit": leg.get("repository_commit"),
        "corpus_binding": {
            "path": PHASE1_PHYSICAL_PATH.as_posix(),
            "sha256": PHASE1_SHA256,
            "rows": PHASE1_ROWS,
            "status": PHASE1_STATUS,
            "require_phase1_frozen_candidate": "PASS",
        },
        "active_semantic_flags_at_run": {
            "TRUST_SWING_CAUSAL": "",
            "TRUST_VOLREGIME_CAUSAL": "",
        },
        "schema_hash_md5": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "swing_window": SWING_WINDOW,
        "implementation_hashes_current": impl_now,
        "implementation_hash_match_to_legacy_freeze": impl_match,
        "live_output_fingerprint": live_fp,
        "stored_joint_float32_sha256": stored_out["joint_float32_sha256"],
        "output_match": output_match,
        "fingerprint_reproducible": fingerprint_reproducible,
        "divergences": divergences,
        "known_defects_from_prior_evidence": known_defects,
        "warmup_behavior": "ATR-gated features NaN during 14-bar warmup; finalize drops NaN rows",
        "missing_value_behavior": "finalize NaN drop; retest_depth 0.0 if no retest",
        "fallback_behavior": "implementation-defined per column; T-003 volume rewrite",
        "dtype": "float32 vector",
        "row_population": {
            "input_rows": PHASE1_ROWS,
            "output_rows": live_fp["rows_after_finalize"],
            "dropped": PHASE1_ROWS - live_fp["rows_after_finalize"],
        },
        "prior_fc_artifacts_preserved": True,
        "production_feature_code_modified_by_this_script": False,
    }


# ── 1B Universe discovery ───────────────────────────────────────────────────


def _ast_assign_targets(node: ast.AST) -> list[str]:
    names: list[str] = []
    if isinstance(node, ast.Name):
        names.append(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            names.extend(_ast_assign_targets(e))
    elif isinstance(node, ast.Attribute):
        names.append(node.attr)
    return names


def _df_column_writes(tree: ast.AST) -> list[dict]:
    """Detect df['col'] = ... and self.df['col'] = ... patterns."""
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if isinstance(t, ast.Subscript):
                # value['key']
                sl = t.slice
                key = None
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    key = sl.value
                if key:
                    hits.append({"column": key, "lineno": n.lineno})
    return hits


def _function_defs(tree: ast.AST, rel: str) -> list[dict]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(
                {
                    "file": rel,
                    "function": n.name,
                    "lineno": n.lineno,
                    "is_private": n.name.startswith("_"),
                }
            )
    return out


def scan_python_file(rel: str) -> dict:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return {"file": rel, "error": str(e), "columns": [], "functions": [], "featureish": []}
    cols = _df_column_writes(tree)
    funcs = _function_defs(tree, rel)
    # featureish string literals and names
    featureish = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if n.value in FEATUREISH_NAMES or n.value in CANONICAL_FEATURES:
                featureish.append({"kind": "str", "name": n.value, "lineno": getattr(n, "lineno", None)})
        if isinstance(n, ast.Name) and n.id in FEATUREISH_NAMES:
            featureish.append({"kind": "name", "name": n.id, "lineno": getattr(n, "lineno", None)})
    return {
        "file": rel,
        "columns": cols,
        "functions": [f for f in funcs if not f["is_private"] or f["function"] in FEATUREISH_NAMES],
        "n_functions_all": len(funcs),
        "featureish_hits": featureish[:200],
        "n_featureish": len(featureish),
    }


def collect_search_roots() -> dict[str, list[Path]]:
    roots = {
        "src/features": list((ROOT / "src" / "features").rglob("*.py")),
        "src/engines": list((ROOT / "src" / "engines").rglob("*.py"))
        if (ROOT / "src" / "engines").exists()
        else [],
        "src/config_layer": list((ROOT / "src" / "config_layer").rglob("*.py")),
        "src/core": list((ROOT / "src" / "core").rglob("*.py")),
        "src/runtime": list((ROOT / "src" / "runtime").rglob("*.py")),
        "src/research": list((ROOT / "src" / "research").rglob("*.py"))
        if (ROOT / "src" / "research").exists()
        else [],
        "src/interpreters": list((ROOT / "src" / "interpreters").rglob("*.py"))
        if (ROOT / "src" / "interpreters").exists()
        else [],
        "scripts/research": list((ROOT / "scripts" / "research").rglob("*.py"))
        if (ROOT / "scripts" / "research").exists()
        else [],
        "scripts/analysis": list((ROOT / "scripts" / "analysis").rglob("*.py")),
        "tests": list((ROOT / "tests").rglob("*.py")),
    }
    # filter pycache
    for k in roots:
        roots[k] = [p for p in roots[k] if "__pycache__" not in p.parts and p.is_file()]
    return roots


def build_quantities_from_authorities() -> list[dict]:
    """Hand-curated + code-backed quantity records (semantic, not text-hit)."""
    qs: list[dict] = []

    def add(**kw):
        qs.append(kw)

    # OHLCV raw
    for name in ("open", "high", "low", "close"):
        add(
            id=f"Q-RAW-{name.upper()}",
            names=[name],
            source_fields=[name],
            formula=f"passthrough {name}",
            parameters={},
            temporal="t",
            normalization=None,
            fallback=None,
            units="price",
            impl=["FeaturePipeline"],
            class_="UNIQUE_CANONICAL_CANDIDATE",
            evidence=["feature_pipeline.py", "feature_schema CANONICAL"],
        )
    add(
        id="Q-VOL-TICK",
        names=["volume"],
        source_fields=["volume"],
        formula="source tick_volume passthrough when non-all-zero",
        parameters={},
        temporal="t",
        normalization=None,
        fallback=None,
        units="tick_count",
        impl=["FeaturePipeline.compute_volume_features", "mt5"],
        class_="UNIQUE_CANONICAL_CANDIDATE",
        evidence=["feature_pipeline T-003 gate"],
    )
    add(
        id="Q-VOL-PROXY-T003",
        names=["volume"],
        source_fields=["high", "low"],
        formula="high-low when volume all-zero (T-003)",
        parameters={},
        temporal="t",
        normalization=None,
        fallback="same column name volume",
        units="price_range_proxy",
        impl=["FeaturePipeline.compute_volume_features"],
        class_="FORMULA_COLLISION",
        evidence=["PASS-A", "feature_pipeline"],
    )
    add(
        id="Q-VOL-RANGE-PROXY-SEPARATE",
        names=["volume_range_proxy"],
        source_fields=["high", "low"],
        formula="high-low explicit proxy identity (contract FEAT-VOLUME_RANGE_PROXY)",
        parameters={},
        temporal="t",
        normalization=None,
        fallback=None,
        units="price",
        impl=["FeatureContract v1 separation intent"],
        class_="UNIQUE_CANONICAL_CANDIDATE",
        evidence=["feature_contract_v1", "FC-0 SEP-B"],
    )
    # Indicators
    add(id="Q-EMA-FAST", names=["ema_fast"], source_fields=["close"], formula="EWM span=9", parameters={"span": 9}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["feature_pipeline"])
    add(id="Q-EMA-SLOW", names=["ema_slow"], source_fields=["close"], formula="EWM span=21", parameters={"span": 21}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["feature_pipeline"])
    add(id="Q-ATR", names=["atr", "atr_14"], source_fields=["high", "low", "close"], formula="rolling mean TR 14", parameters={"period": 14}, temporal="t", normalization=None, fallback="NaN warmup", units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["feature_pipeline"])
    add(id="Q-VOL-RATIO", names=["volume_ratio"], source_fields=["volume"], formula="volume / rolling_mean(volume,20)", parameters={"window": 20}, temporal="t", normalization=None, fallback=None, units="ratio", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["inherits volume semantic risk"])
    add(id="Q-VOL-SPIKE", names=["volume_spike"], source_fields=["volume_ratio"], formula="volume_ratio > threshold binary", parameters={}, temporal="t", normalization=None, fallback=None, units="binary", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-EMA-SPREAD", names=["ema_spread"], source_fields=["close"], formula="(ema_fast-ema_slow)/(atr*close)", parameters={}, temporal="t", normalization=None, fallback="NaN atr warmup", units="ratio", impl=["FeaturePipeline", "derived_math"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["FM registry"])
    add(id="Q-MOMENTUM", names=["momentum_score"], source_fields=["close"], formula="(close-close.shift(14))/(atr*close)", parameters={"lookback": 14}, temporal="t", normalization=None, fallback="NaN", units="ratio", impl=["FeaturePipeline", "derived_math"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-RSI", names=["rsi_14"], source_fields=["close"], formula="RSI 14", parameters={"period": 14}, temporal="t", normalization=None, fallback=None, units="index", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-MACD-L", names=["macd_line"], source_fields=["close"], formula="EMA12-EMA26", parameters={}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-MACD-S", names=["macd_signal"], source_fields=["close"], formula="EMA9 of macd_line", parameters={}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-MACD-H", names=["macd_hist"], source_fields=["close"], formula="macd_line-macd_signal", parameters={}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-TREND-BIAS", names=["trend_bias"], source_fields=["close"], formula="sign(ema_fast-ema_slow)", parameters={}, temporal="t", normalization=None, fallback=None, units="sign", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-TREND-STR", names=["trend_strength"], source_fields=["close"], formula="ma slope / atr style", parameters={"ma": 20}, temporal="t", normalization=None, fallback=None, units="ratio", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-VOLATILITY-RATIO", names=["volatility_ratio"], source_fields=["high", "low", "close"], formula="atr / close or related", parameters={}, temporal="t", normalization=None, fallback=None, units="ratio", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])

    # Swings temporal family
    add(
        id="Q-SWING-CENTER",
        names=["swing_high", "swing_low"],
        source_fields=["high", "low"],
        formula=f"rolling(center=True,k={SWING_WINDOW}) extremum equality",
        parameters={"SWING_WINDOW": SWING_WINDOW},
        temporal="t with future k (legacy publish)",
        normalization=None,
        fallback="0",
        units="binary",
        impl=["FeaturePipeline.compute_structure_liquidity"],
        class_="TEMPORAL_SEMANTIC_COLLISION",
        evidence=["center=True", "PASS-A"],
    )
    add(
        id="Q-SWING-CAUSAL-ENV",
        names=["swing_high", "swing_low"],
        source_fields=["high", "low"],
        formula="center + shift(k) when TRUST_SWING_CAUSAL=1",
        parameters={"env": "TRUST_SWING_CAUSAL"},
        temporal="delayed causal",
        normalization=None,
        fallback="0",
        units="binary",
        impl=["FeaturePipeline env branch"],
        class_="CONFIG_DEPENDENT_IDENTITY",
        evidence=["feature_pipeline"],
    )
    for n in (
        "higher_high", "lower_low", "break_of_structure", "liquidity_sweep",
        "sweep_detected", "double_sweep", "liquidity_distance",
        "liquidity_pressure_score", "candles_since_retest",
    ):
        add(
            id=f"Q-STRUCT-{n.upper()}",
            names=[n],
            source_fields=["high", "low", "close"],
            formula=f"structure derived; inherits swing temporal semantic ({n})",
            parameters={"SWING_WINDOW": SWING_WINDOW},
            temporal="inherits swing",
            normalization=None,
            fallback="0",
            units="mixed",
            impl=["FeaturePipeline.compute_structure_liquidity / retest"],
            class_="TEMPORAL_SEMANTIC_COLLISION",
            evidence=["FC-0.5 dependency graph"],
        )
    add(
        id="Q-INTER-LAST-SWING-H",
        names=["last_swing_high_price", "last_swing_high"],
        source_fields=["high"],
        formula="ffill high where swing_high",
        parameters={},
        temporal="inherits swing",
        normalization=None,
        fallback=None,
        units="price",
        impl=["FeaturePipeline intermediate"],
        class_="TEMPORAL_SEMANTIC_COLLISION",
        evidence=["not in CANONICAL_FEATURES vector"],
    )
    add(
        id="Q-INTER-LAST-SWING-L",
        names=["last_swing_low_price", "last_swing_low"],
        source_fields=["low"],
        formula="ffill low where swing_low",
        parameters={},
        temporal="inherits swing",
        normalization=None,
        fallback=None,
        units="price",
        impl=["FeaturePipeline intermediate"],
        class_="TEMPORAL_SEMANTIC_COLLISION",
        evidence=[],
    )
    add(
        id="Q-INTER-RETEST-FLAG",
        names=["retest_flag"],
        source_fields=["close"],
        formula="retest condition after sweep",
        parameters={},
        temporal="inherits swing",
        normalization=None,
        fallback=None,
        units="binary",
        impl=["FeaturePipeline"],
        class_="TEMPORAL_SEMANTIC_COLLISION",
        evidence=[],
    )

    # Body geometry
    add(id="Q-BODY-SIZE", names=["body_size"], source_fields=["open", "close"], formula="abs(close-open)", parameters={}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline", "candle_math"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-WICK-SIZE", names=["wick_size"], source_fields=["high", "low"], formula="range or wick component (verify)", parameters={}, temporal="t", normalization=None, fallback=None, units="price", impl=["FeaturePipeline", "candle_math"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["F-046 body_ratio canonical body/range"])
    add(id="Q-BODY-RATIO", names=["body_ratio"], source_fields=["open", "high", "low", "close"], formula="body/range [0,1]", parameters={}, temporal="t", normalization=None, fallback="0", units="ratio", impl=["candle_math", "FeaturePipeline", "CRT"], class_="INTENTIONAL_ALIAS", evidence=["F-046 unified candle_math"])
    add(id="Q-BODY-RATIO-NONCANON-LIVE", names=["body_ratio"], source_fields=["open", "high", "low", "close"], formula="body/total_wick (GD-001 live_engine_hook path)", parameters={}, temporal="t", normalization=None, fallback=None, units="ratio", impl=["live_engine_hook non-canonical"], class_="LIVE_LOCAL_DUPLICATE", evidence=["F-047 GD-001", "live_engine_hook"])

    # FM-020 / 028
    add(id="Q-FM020", names=["disp_strength"], source_fields=["open", "close"], formula="body/(atr*close) clip 0..3", parameters={"clip": [0, 3]}, temporal="t", normalization=None, fallback="NaN atr", units="ratio", impl=["FeaturePipeline", "derived_math.disp_strength"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["FM-020"])
    add(id="Q-FM028", names=["displacement_atr_ratio", "disp_strength", "disp_str"], source_fields=["high", "low"], formula="candle_range/atr", parameters={}, temporal="CRT retest", normalization=None, fallback="0", units="ratio", impl=["derived_math.displacement_atr_ratio", "crt_engine_v2"], class_="FORMULA_COLLISION", evidence=["FM-028", "CH-002"])
    add(id="Q-FM021", names=["retest_depth"], source_fields=["close"], formula="|close-ema|/(atr*close) if retest else 0", parameters={}, temporal="t inherits swing via retest_flag", normalization=None, fallback="0", units="ratio", impl=["FeaturePipeline", "derived_math.retest_depth"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=["FM-021", "LEAKING transitive"])
    add(id="Q-FM027", names=["displacement_retrace", "retest_depth"], source_fields=["open", "close"], formula="cross-candle retrace to disp open", parameters={}, temporal="CRT retest", normalization=None, fallback="0", units="ratio", impl=["derived_math.displacement_retrace", "crt_engine_v2"], class_="FORMULA_COLLISION", evidence=["FM-027", "CH-002"])

    # Vol regime family
    add(id="Q-VR-GLOBAL", names=["volatility_regime"], source_fields=["atr"], formula="global atr rank tercile", parameters={}, temporal="full batch", normalization=None, fallback=None, units="class_0_2", impl=["FeaturePipeline default"], class_="TEMPORAL_SEMANTIC_COLLISION", evidence=["GLOBAL_FIT", "PASS-A"])
    add(id="Q-VR-EXPAND", names=["volatility_regime"], source_fields=["atr"], formula="expanding atr rank", parameters={"env": "expanding"}, temporal="causal expanding", normalization=None, fallback=None, units="class_0_2", impl=["FeaturePipeline TRUST_VOLREGIME_CAUSAL"], class_="CONFIG_DEPENDENT_IDENTITY", evidence=[])
    add(id="Q-VR-ROLL", names=["volatility_regime"], source_fields=["atr"], formula="rolling(N) atr rank", parameters={"env": "rolling", "N": 200}, temporal="causal rolling", normalization=None, fallback=None, units="class_0_2", impl=["FeaturePipeline TRUST_VOLREGIME_CAUSAL"], class_="CONFIG_DEPENDENT_IDENTITY", evidence=["FC-0.5 provisional N=200 not frozen canonical"])

    # Context
    add(id="Q-SESSION", names=["session"], source_fields=["timestamp"], formula="Asia/London/NY hour buckets", parameters={}, temporal="calendar t", normalization=None, fallback=None, units="enum", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])
    add(id="Q-HOUR", names=["hour_of_day"], source_fields=["timestamp"], formula="hour", parameters={}, temporal="calendar t", normalization=None, fallback=None, units="hour", impl=["FeaturePipeline"], class_="UNIQUE_CANONICAL_CANDIDATE", evidence=[])

    # Model-local
    add(id="Q-GAUSS-3", names=["ema_fast", "ema_slow", "momentum_score"], source_fields=["close"], formula="live heuristic 3-feature vote", parameters={}, temporal="t", normalization=None, fallback=None, units="score", impl=["heuristic_gaussian_engine"], class_="MODEL_LOCAL_DUPLICATE", evidence=["active_models gaussian live"])
    add(id="Q-GAUSS-38", names=["CANONICAL_FEATURES"], source_fields=["pipeline vector"], formula="38-dim NB experimental", parameters={}, temporal="unknown train", normalization="artifact scaler", fallback=None, units="vector", impl=["gaussian registry"], class_="UNKNOWN", evidence=["train lineage not recovered in RUN1"])
    add(id="Q-BITNET-6", names=["body_ratio", "retest_depth", "disp_strength", "atr", "candles_since_retest", "double_sweep"], source_fields=["mixed"], formula="BitNet hard-reject inputs; CRT may alias FM-027/028 into names", parameters={}, temporal="CRT", normalization=None, fallback=None, units="mixed", impl=["BitNetZoneGate", "crt bitnet map"], class_="UNINTENTIONAL_ALIAS", evidence=["use_bitnet false", "FC-0.5"])
    add(id="Q-RR-POLARITY", names=["rr_ratio"], source_fields=["OHLC"], formula="candle polarity index misnamed RR", parameters={}, temporal="t", normalization=None, fallback=None, units="index_0_1", impl=["rr_engine"], class_="MODEL_LOCAL_DUPLICATE", evidence=["F-048"])
    add(id="Q-RR-FUSION-38", names=["CANONICAL_FEATURES"], source_fields=["pipeline"], formula="Mahalanobis 38-dim path historical", parameters={}, temporal="unknown train", normalization="model mean/cov", fallback="gaussian bypass F-044", units="vector", impl=["rr_fusion"], class_="UNKNOWN", evidence=["enabled:false", "F-044/045"])
    add(id="Q-TRADENET", names=["CANONICAL_FEATURES"], source_fields=["pipeline intended"], formula="TradeNet fusion slot", parameters={}, temporal="unknown train", normalization=None, fallback=None, units="vector", impl=["tradenet"], class_="UNKNOWN", evidence=["F-005 unwired"])
    add(id="Q-ZONE-MEMBER", names=["zone membership"], source_fields=["price geometry"], formula="zone_registry hard membership", parameters={}, temporal="t", normalization=None, fallback=None, units="score", impl=["zone_gate_engine"], class_="MODEL_LOCAL_DUPLICATE", evidence=["F-041"])
    add(id="Q-SCORING-DISP", names=["disp_strength"], source_fields=["move", "atr"], formula="move/atr local in scoring paths", parameters={}, temporal="unknown", normalization=None, fallback=None, units="ratio", impl=["scoring_engine residual"], class_="UNKNOWN", evidence=["FC-0.5 residual UNKNOWN"])
    add(id="Q-CRT-FEATURE-BUILDER", names=["body_ratio", "features"], source_fields=["OHLC"], formula="crt_feature_builder may recompute", parameters={}, temporal="unknown", normalization=None, fallback=None, units="mixed", impl=["crt_feature_builder.py"], class_="UNKNOWN", evidence=["git shows modified; call-site audit RUN1 partial"])
    add(id="Q-DATASET-BUILDER", names=["CANONICAL_FEATURES"], source_fields=["trade_data"], formula="dataset_builder.build_feature_vector", parameters={"lambda_decay": 0.05}, temporal="trade-event", normalization=None, fallback=None, units="vector", impl=["dataset_builder", "LiveEngine.process"], class_="TRAINING_LOCAL_DUPLICATE", evidence=["live_engine uses dataset_builder"])
    add(id="Q-RESEARCH-INDICATORS", names=["various"], source_fields=["OHLCV"], formula="src/research/indicators and hypotheses recompute", parameters={}, temporal="varies", normalization=None, fallback=None, units="mixed", impl=["src/research/*"], class_="RESEARCH_LOCAL_DUPLICATE", evidence=["research package independent of FeaturePipeline for many paths"])
    add(id="Q-SECONDLOW", names=["secondlow detector geometry"], source_fields=["OHLCV"], formula="secondlow_v1 detector raw OHLCV", parameters={}, temporal="detector-defined", normalization=None, fallback=None, units="geometry", impl=["src/research/secondlow_v1"], class_="RESEARCH_LOCAL_DUPLICATE", evidence=["FC-0.5 NOT_APPLICABLE FeaturePipeline"])
    add(id="Q-REGIME-LABELER", names=["RegimeLabeler S_t"], source_fields=["ATR/vol"], formula="macro vol tercile labeling for research", parameters={"tercile_window": 2000}, temporal="research batch", normalization=None, fallback=None, units="class", impl=["interpreters/regime", "regime_conditioning"], class_="RESEARCH_LOCAL_DUPLICATE", evidence=["F-030/F-043 separate from volatility_regime feature"])
    add(id="Q-MARKOV-FORECAST", names=["MarkovRegimeForecaster"], source_fields=["S_t"], formula="trailing transition matrix P^H", parameters={"w_markov": 480, "h": 8}, temporal="research", normalization=None, fallback=None, units="prob", impl=["regime_observer"], class_="RESEARCH_LOCAL_DUPLICATE", evidence=["F-043"])

    # Normalize class key
    for q in qs:
        if "class_" in q:
            q["class"] = q.pop("class_")
    return qs


def discover_producers_consumers(scan_results: list[dict]) -> dict:
    producers = []
    consumers = []

    known_producers = [
        {"path": "src/features/feature_pipeline.py", "role": "PRIMARY_BATCH_PRODUCER", "status": "REACHABLE"},
        {"path": "src/features/candle_math.py", "role": "PRIMITIVE_MATH", "status": "REACHABLE"},
        {"path": "src/features/derived_math.py", "role": "DERIVED_MATH", "status": "REACHABLE"},
        {"path": "src/features/dataset_builder.py", "role": "TRADE_EVENT_VECTOR", "status": "REACHABLE"},
        {"path": "src/features/crt_feature_builder.py", "role": "CRT_FEATURE_BUILDER", "status": "PARTIAL_UNKNOWN_CALLSITES"},
        {"path": "src/config_layer/crt_engine_v2.py", "role": "CRT_STATE_CACHED_FEATURES", "status": "REACHABLE"},
        {"path": "src/engines/heuristic_gaussian_engine.py", "role": "GAUSSIAN_LIVE_3", "status": "REACHABLE"},
        {"path": "src/engines/zone_gate_engine.py", "role": "ZONE_SCORE", "status": "REACHABLE"},
        {"path": "src/engines/rr_engine.py", "role": "RR_POLARITY", "status": "REACHABLE"},
        {"path": "src/runtime/backtest_v2.py", "role": "BACKTEST_PIPELINE_CONSUMER_PRODUCER", "status": "REACHABLE"},
        {"path": "src/runtime/live_engine_hook.py", "role": "LIVE_HOOK", "status": "REACHABLE_PARITY_UNKNOWN"},
        {"path": "src/engines/live_engine.py", "role": "LIVE_ENGINE", "status": "REACHABLE"},
        {"path": "src/research/indicators.py", "role": "RESEARCH_INDICATORS", "status": "RESEARCH"},
        {"path": "src/research/secondlow_v1", "role": "SECONDLOW", "status": "RESEARCH"},
        {"path": "src/interpreters", "role": "REGIME_INTERPRETERS", "status": "RESEARCH"},
    ]
    known_consumers = [
        {"path": "src/core/engine_runner.py", "role": "FUSION_ORCHESTRATOR", "status": "REACHABLE"},
        {"path": "src/runtime/backtest_v2.py", "role": "BACKTEST", "status": "REACHABLE"},
        {"path": "src/engines/crt_engine.py", "role": "CRT_SCORE_WRAPPER", "status": "REACHABLE"},
        {"path": "src/engines/live_engine.py", "role": "BITNET_GATE_CONSUMER", "status": "REACHABLE_INACTIVE_BITNET"},
        {"path": "src/features/feature_monitor.py", "role": "DRIFT_MONITOR", "status": "REACHABLE"},
        {"path": "scripts/research/*", "role": "RESEARCH_SCRIPTS", "status": "MANY_PATHS"},
        {"path": "models/*", "role": "TRAINED_ARTIFACTS", "status": "ARTIFACT_BINDING_UNKNOWN_RUN1"},
    ]

    # Column write map from scans of high-value files
    col_map = defaultdict(list)
    for s in scan_results:
        for c in s.get("columns") or []:
            col_map[c["column"]].append({"file": s["file"], "lineno": c["lineno"]})

    return {
        "known_producers": known_producers,
        "known_consumers": known_consumers,
        "column_write_sites": {k: v for k, v in sorted(col_map.items()) if k in FEATUREISH_NAMES or k in CANONICAL_FEATURES or k.startswith("last_swing") or k.startswith("disp") or k.startswith("retest") or k.startswith("volume") or k.startswith("swing") or k.startswith("liquidity") or k.startswith("macd") or k.startswith("ema") or k.startswith("atr") or k in ("body_ratio", "body_size", "wick_size", "volatility_regime", "session", "hour_of_day", "true_range")},
        "n_featureish_column_keys": len(col_map),
    }


def run_1b() -> tuple[dict, dict, dict, dict, dict]:
    roots = collect_search_roots()
    coverage = {
        "_doc": "Phase 1B search coverage. Numerators/denominators explicit. Shallow hits ≠ semantic coverage.",
        "generated_at_utc": _now(),
        "directories": {},
        "methods": [
            "AST FunctionDef + df['col'] assignment scan",
            "hand-curated semantic quantity table from executable authorities",
            "prior FC-0/FC-0.5 evidence cross-walk",
            "import/path inventory of producers/consumers",
            "FEATUREISH name set intersection",
        ],
        "excluded": [
            {"path": "venv/", "reason": "third-party"},
            {"path": "data/", "reason": "corpus only via phase1 bind"},
            {"path": "**/__pycache__/**", "reason": "bytecode"},
        ],
        "limitations": [
            "Not every scripts/research file executed at runtime",
            "Dynamic getattr/config-selected paths may be undercounted",
            "Historical git revisions of training code not fully recovered (deferred to RUN 6 for models)",
            "Text featureish hits are discovery signals, not semantic proof",
        ],
    }
    scan_results = []
    total_py = 0
    scanned_py = 0
    for root_name, files in roots.items():
        total_py += len(files)
        # Cap deep trees for determinism/time: always fully scan features/engines/config_layer/core/runtime
        full = root_name in (
            "src/features",
            "src/engines",
            "src/config_layer",
            "src/core",
            "src/runtime",
        )
        sample = files if full else files[:80]
        coverage["directories"][root_name] = {
            "py_files_found": len(files),
            "py_files_ast_scanned": len(sample),
            "scan_mode": "full" if full else "capped_80",
            "numerator_scanned": len(sample),
            "denominator_found": len(files),
        }
        for p in sample:
            rel = p.relative_to(ROOT).as_posix()
            scan_results.append(scan_python_file(rel))
            scanned_py += 1

    coverage["totals"] = {
        "py_files_found_sum": total_py,
        "py_files_ast_scanned_sum": scanned_py,
        "definition": "found = rglob *.py under listed roots excluding __pycache__; scanned = AST-parsed subset",
    }

    quantities = build_quantities_from_authorities()
    by_class = defaultdict(int)
    for q in quantities:
        by_class[q["class"]] += 1

    # Extra columns discovered via AST not in curated list
    known_names = set()
    for q in quantities:
        known_names.update(q.get("names") or [])
    discovered_cols = set()
    for s in scan_results:
        for c in s.get("columns") or []:
            discovered_cols.add(c["column"])
    extra_cols = sorted(
        c
        for c in discovered_cols
        if c not in known_names
        and not c.startswith("_")
        and len(c) < 40
    )

    # Mark extras as UNKNOWN pending adjudication (honest — not silent drop)
    extra_records = []
    for col in extra_cols[:80]:
        # skip pure OHLCV intermediates already known
        extra_records.append(
            {
                "id": f"Q-AST-COL-{col}",
                "names": [col],
                "source_fields": ["UNKNOWN"],
                "formula": "UNKNOWN — column assignment discovered via AST; not yet formula-bound",
                "parameters": {},
                "temporal": "UNKNOWN",
                "normalization": None,
                "fallback": None,
                "units": "UNKNOWN",
                "impl": [
                    f"{s['file']}:{h['lineno']}"
                    for s in scan_results
                    for h in (s.get("columns") or [])
                    if h.get("column") == col
                ][:5],
                "class": "UNKNOWN",
                "evidence": ["AST df column write"],
            }
        )
        by_class["UNKNOWN"] += 1

    all_q = quantities + extra_records

    universe = {
        "_doc": "Phase 1B feature universe census. COMPLETE search package ≠ closed universe.",
        "generated_at_utc": _now(),
        "n_quantities": len(all_q),
        "n_curated_semantic": len(quantities),
        "n_ast_extra_columns": len(extra_records),
        "counts_by_class": dict(by_class),
        "quantities": all_q,
        "canonical_vector_names": list(CANONICAL_FEATURES),
        "canonical_vector_dim": len(CANONICAL_FEATURES),
        "feature_contract_v1_entries": 41,  # prior FC-0; not assumed complete
        "assumption_rejected": [
            "38 features is complete universe",
            "41 FeatureContract entries is complete universe",
            "FC-0.5 collision exhaustiveness",
        ],
        "FORMULA_COLLISION_EXHAUSTIVENESS_STATUS": "UNPROVEN",
        "unknowns_explicit": [
            q["id"] for q in all_q if q["class"] == "UNKNOWN"
        ],
        "prior_evidence_refs": [
            "docs/governance/legacy_feature_semantics_v1-2026-07-10.json",
            "docs/governance/feature_contract_v1-2026-07-10.json",
            "docs/governance/feature_formula_identity_census_fc05-2026-07-10.json",
            "docs/governance/feature_dependency_graph_fc05-2026-07-10.json",
            "docs/governance/feature_semantic_adjudication_pass_a-2026-07-10.json",
        ],
    }

    collision_report = {
        "_doc": "Phase 1B formula collision report (discovery, not closure).",
        "generated_at_utc": _now(),
        "KNOWN_FAMILIES": [
            "volume tick vs T-003 proxy same name",
            "FM-020 vs FM-028 name collision",
            "FM-021 vs FM-027 name collision",
            "swing center vs causal-env",
            "volatility_regime global vs expanding vs rolling",
            "body_ratio canonical vs live non-canonical",
        ],
        "FORMULA_COLLISION_EXHAUSTIVENESS_STATUS": "UNPROVEN",
        "counts": dict(by_class),
        "collision_class_ids": [
            q["id"] for q in all_q if q["class"] == "FORMULA_COLLISION"
        ],
        "temporal_collision_ids": [
            q["id"] for q in all_q if q["class"] == "TEMPORAL_SEMANTIC_COLLISION"
        ],
        "unknown_ids": [q["id"] for q in all_q if q["class"] == "UNKNOWN"],
        "note": "UNKNOWNs are explicit, not silent. RUN 1 does not force resolve to canonical.",
    }

    pc_graph = discover_producers_consumers(scan_results)
    pc_graph["_doc"] = "Phase 1B producer/consumer graph (discovery)."
    pc_graph["generated_at_utc"] = _now()
    pc_graph["unresolved_dynamic_paths"] = [
        "optional imports in live_engine_hook",
        "config-driven strategy modules",
        "getattr/feature dict consumers without schema verify",
        "historical training scripts not bit-identical to HEAD",
        "BitNet feature map only if use_bitnet true",
    ]
    pc_graph["counts"] = {
        "FEATURE_PRODUCING_PATHS_DISCOVERED": len(pc_graph["known_producers"]),
        "FEATURE_CONSUMING_PATHS_DISCOVERED": len(pc_graph["known_consumers"]),
        "UNRESOLVED_DYNAMIC_PATHS": len(pc_graph["unresolved_dynamic_paths"]),
        "column_keys_tracked": len(pc_graph["column_write_sites"]),
    }

    identity_census = {
        "_doc": "Phase 1B formula identity census (extends FC-0.5; does not claim exhaustiveness).",
        "generated_at_utc": _now(),
        "quantities": all_q,
        "counts": dict(by_class),
        "n_quantities": len(all_q),
        "KNOWN_COLLISIONS_IDENTIFIED": True,
        "ALL_COLLISIONS_EXHAUSTED": "unproven",
        "FORMULA_COLLISION_EXHAUSTIVENESS_STATUS": "UNPROVEN",
    }

    return universe, identity_census, collision_report, pc_graph, coverage


def main() -> int:
    print("Phase 1A legacy baseline...")
    baseline = verify_legacy_baseline()
    (GOV / f"phase1_run1_legacy_baseline_verification-{DATE}.json").write_text(
        json.dumps(baseline, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (GOV / f"phase1_run1_legacy_baseline_verification-{DATE}.md").write_text(
        f"# Phase 1A — Legacy Baseline Verification\n\n"
        f"**LEGACY_BASELINE_STATUS** = `{baseline['LEGACY_BASELINE_STATUS']}`\n\n"
        f"{baseline['note']}\n\n"
        f"- commit: `{baseline['repository_commit']}`\n"
        f"- worktree_dirty: {baseline['worktree_dirty']}\n"
        f"- joint live: `{baseline['live_output_fingerprint']['joint_float32_sha256']}`\n"
        f"- joint stored: `{baseline['stored_joint_float32_sha256']}`\n"
        f"- fingerprint_reproducible: {baseline['fingerprint_reproducible']}\n"
        f"- output_match: {json.dumps(baseline['output_match'], indent=2)}\n"
        f"- divergences: {len(baseline['divergences'])}\n"
        f"- prior FC artifacts preserved: true\n"
        f"- production code modified by this run: false\n",
        encoding="utf-8",
    )
    print("LEGACY_BASELINE_STATUS", baseline["LEGACY_BASELINE_STATUS"])

    print("Phase 1B universe discovery...")
    universe, identity, collision, pc, coverage = run_1b()

    (GOV / f"phase1_run1_feature_universe_census-{DATE}.json").write_text(
        json.dumps(universe, indent=2) + "\n", encoding="utf-8"
    )
    counts = universe["counts_by_class"]
    (GOV / f"phase1_run1_feature_universe_census-{DATE}.md").write_text(
        f"# Phase 1B — Feature Universe Census\n\n"
        f"n_quantities = {universe['n_quantities']} "
        f"(curated {universe['n_curated_semantic']} + AST extras {universe['n_ast_extra_columns']})\n\n"
        f"## Counts by class\n\n```\n{json.dumps(counts, indent=2)}\n```\n\n"
        f"FORMULA_COLLISION_EXHAUSTIVENESS_STATUS = "
        f"{universe['FORMULA_COLLISION_EXHAUSTIVENESS_STATUS']}\n\n"
        f"UNKNOWN ids: {len(universe['unknowns_explicit'])}\n\n"
        f"Assumptions rejected: {universe['assumption_rejected']}\n",
        encoding="utf-8",
    )
    (GOV / f"phase1_run1_formula_identity_census-{DATE}.json").write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8"
    )
    (GOV / f"phase1_run1_formula_collision_report-{DATE}.json").write_text(
        json.dumps(collision, indent=2) + "\n", encoding="utf-8"
    )
    (GOV / f"phase1_run1_feature_producer_consumer_graph-{DATE}.json").write_text(
        json.dumps(pc, indent=2) + "\n", encoding="utf-8"
    )
    (GOV / f"phase1_run1_search_coverage-{DATE}.json").write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
    )

    # RUN1 status
    if baseline["LEGACY_BASELINE_STATUS"].startswith("BLOCKED"):
        run_status = f"BLOCKED:{baseline['LEGACY_BASELINE_STATUS']}"
    else:
        run_status = "COMPLETE"

    manifest = {
        "program": "PHASE1_CANONICAL_FEATURE_TRUTH_AND_MODEL_LINEAGE",
        "run": 1,
        "phases": ["1A", "1B"],
        "PHASE1_RUN1_STATUS": run_status,
        "generated_at_utc": _now(),
        "repository_commit": baseline["repository_commit"],
        "worktree_dirty": baseline["worktree_dirty"],
        "LEGACY_BASELINE_STATUS": baseline["LEGACY_BASELINE_STATUS"],
        "DISCOVERED_MATHEMATICAL_QUANTITIES": universe["n_quantities"],
        "CANONICAL_CANDIDATES": counts.get("UNIQUE_CANONICAL_CANDIDATE", 0),
        "INTENTIONAL_ALIASES": counts.get("INTENTIONAL_ALIAS", 0),
        "UNINTENTIONAL_ALIASES": counts.get("UNINTENTIONAL_ALIAS", 0),
        "FORMULA_COLLISIONS": counts.get("FORMULA_COLLISION", 0),
        "TEMPORAL_SEMANTIC_COLLISIONS": counts.get("TEMPORAL_SEMANTIC_COLLISION", 0),
        "NORMALIZATION_COLLISIONS": counts.get("NORMALIZATION_COLLISION", 0),
        "FALLBACK_COLLISIONS": counts.get("FALLBACK_COLLISION", 0),
        "CONFIG_DEPENDENT_IDENTITIES": counts.get("CONFIG_DEPENDENT_IDENTITY", 0),
        "MODEL_LOCAL_DUPLICATES": counts.get("MODEL_LOCAL_DUPLICATE", 0),
        "RESEARCH_LOCAL_DUPLICATES": counts.get("RESEARCH_LOCAL_DUPLICATE", 0),
        "TRAINING_LOCAL_DUPLICATES": counts.get("TRAINING_LOCAL_DUPLICATE", 0),
        "LIVE_LOCAL_DUPLICATES": counts.get("LIVE_LOCAL_DUPLICATE", 0),
        "UNKNOWN_IDENTITIES": counts.get("UNKNOWN", 0),
        "FEATURE_PRODUCING_PATHS_DISCOVERED": pc["counts"][
            "FEATURE_PRODUCING_PATHS_DISCOVERED"
        ],
        "FEATURE_CONSUMING_PATHS_DISCOVERED": pc["counts"][
            "FEATURE_CONSUMING_PATHS_DISCOVERED"
        ],
        "UNRESOLVED_DYNAMIC_PATHS": pc["counts"]["UNRESOLVED_DYNAMIC_PATHS"],
        "FORMULA_COLLISION_EXHAUSTIVENESS_STATUS": "UNPROVEN",
        "production_feature_code_changed": False,
        "model_enablement_changed": False,
        "model_artifacts_changed": False,
        "model_training_lineage_started": False,
        "run2_authorized": False,
        "prior_fc_artifacts_preserved": True,
        "artifacts": [
            f"docs/governance/phase1_run1_legacy_baseline_verification-{DATE}.json",
            f"docs/governance/phase1_run1_legacy_baseline_verification-{DATE}.md",
            f"docs/governance/phase1_run1_feature_universe_census-{DATE}.json",
            f"docs/governance/phase1_run1_feature_universe_census-{DATE}.md",
            f"docs/governance/phase1_run1_formula_identity_census-{DATE}.json",
            f"docs/governance/phase1_run1_formula_collision_report-{DATE}.json",
            f"docs/governance/phase1_run1_feature_producer_consumer_graph-{DATE}.json",
            f"docs/governance/phase1_run1_search_coverage-{DATE}.json",
            f"docs/governance/phase1_run1_manifest-{DATE}.json",
            "scripts/analysis/phase1_run1_feature_truth.py",
            "tests/test_phase1_run1_legacy_baseline.py",
        ],
        "evidence_inputs_not_authority": [
            "FC-0 / FC-0.5 artifacts",
            "historical F-xxx",
            "FeatureContract v1 statuses",
        ],
        "ECONOMIC_CLAIMS_ALLOWED": False,
    }
    (GOV / f"phase1_run1_manifest-{DATE}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps({k: manifest[k] for k in (
        "PHASE1_RUN1_STATUS",
        "LEGACY_BASELINE_STATUS",
        "DISCOVERED_MATHEMATICAL_QUANTITIES",
        "UNKNOWN_IDENTITIES",
        "FORMULA_COLLISION_EXHAUSTIVENESS_STATUS",
    )}, indent=2))
    return 0 if run_status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
