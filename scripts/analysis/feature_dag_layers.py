"""
feature_dag_layers.py — the authoritative topological feature-DAG + semantic layer
assignment (READ-ONLY). The missing spine for bottom-up certification.

The repo has two partial edge sources: the ontology `depends_on` (registry-authoritative
for the ~19 registered math features) and the fuller 38-node `DEPS` map in
scripts/analysis/feature_pipeline_fc05_closure.py (code-authority for structural/rolling
features the ontology treats as leaves). Neither computes a topological order or a
layer assignment. This module merges them into ONE authoritative edge set, fixes the two
known data bugs, runs a Kahn topological sort, and assigns each node a semantic layer
L0..L6 (the bottom-up certification order):

  RAW_INPUT (-1)  open/high/low/close/volume/timestamp
  L0 candle primitives   body/range/wicks/true_range
  L1 rolling indicators  atr/rsi/ema/macd + causal swing publication
  L2 direct derived      body_ratio/volatility_ratio/disp_strength/ema_spread/momentum/...
  L3 structural / event  HH/LL/BOS/sweep/retest/liquidity_distance
  L4 composite / context trend_strength/volatility_regime/liquidity_pressure/session
  L5 temporal market-reality  (compression/expansion/... — none in the current canonical vector)
  L6 models / thresholds / decisions  (not features)

Emits an immutable dated artifact + LATEST pointer (feature_38_lineage_census convention).
Computes NO feature math — pure graph structure. Grants no authority (§6.5).

Usage: python scripts/analysis/feature_dag_layers.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM  # noqa: E402
from features.formula_registry import build_lineage_graph  # noqa: E402

_GOV = _ROOT / "docs" / "governance"
_STAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d")

RAW = "RAW_INPUT"
LAYER_NAMES = {
    -1: RAW,
    0: "L0_candle_primitive",
    1: "L1_rolling_indicator",
    2: "L2_direct_derived",
    3: "L3_structural_event",
    4: "L4_composite_context",
    5: "L5_temporal_market_reality",
    6: "L6_model_threshold_decision",
}

_RAW_INPUTS = ("open", "high", "low", "close", "volume", "timestamp")

# ── The authoritative merged edge set ────────────────────────────────────────────
# Transcribed from feature_pipeline.py (code authority) + market_ontology.yaml
# (`depends_on`, registry-authoritative), reconciled. TWO BUG-FIXES vs the fc05 DEPS map:
#   (1) disp_strength gains its `body_size` + `close` edges (ontology FM-020 = body/(atr*close);
#       fc05 DEPS wrongly listed only [atr]).
#   (2) double_sweep appears exactly once here (fc05 had a duplicate dict key).
# `atr` is edged to `true_range` (not a bare leaf) — the true computational dependency.
# Each node: (deps, semantic_layer, formula_id_or_None).
#
# v4.0 RE-SYNC (Semantic Layer Certification Audit, Tier 1 item 1): this map was written
# against schema v3.0 (38-dim) and silently drifted out of sync when schema v4.0 (39-dim,
# 2026-07-22) renamed `wick_size` -> `candle_range` (feature_schema.py:89) and split the single
# `macd_hist` column into `macd_hist_raw` (FM-049, index 18) + `macd_hist_z` (FM-053, index 19)
# (feature_schema.py:82-84). The stale names left `candle_range`/`macd_hist_raw`/`macd_hist_z`
# with no DAG node -> no certification-ledger row -> feature_surface_query reported
# `closure: {CLOSED: 36, None: 3}` while still printing `surface_status: CLOSED`. Renamed/split
# below; math and edges are unchanged, this is a node-identity fix only.
_NODES: dict[str, tuple[list[str], int, str | None]] = {
    # RAW inputs
    "open":      ([], -1, None),
    "high":      ([], -1, None),
    "low":       ([], -1, None),
    "close":     ([], -1, None),
    "volume":    ([], -1, None),
    "timestamp": ([], -1, None),
    # L0 candle primitives
    "body_size":    (["open", "close"], 0, "FM-001"),
    "candle_range": (["high", "low"], 0, "FM-002"),        # v4.0 name; was `wick_size` (v3.0 misnomer)
    "upper_wick": (["open", "high", "close"], 0, "FM-003"),
    "lower_wick": (["open", "low", "close"], 0, "FM-004"),
    "total_wick": (["upper_wick", "lower_wick"], 0, "FM-005"),
    "true_range": (["high", "low", "close"], 0, "FM-040"),
    # L1 rolling indicators + causal swing publication (first-class registered, rolling_indicators)
    "atr":         (["true_range"], 1, "FM-041"),
    "rsi_14":      (["close"], 1, "FM-042"),
    "ema_fast":    (["close"], 1, "FM-043"),
    "ema_slow":    (["close"], 1, "FM-044"),
    "macd_line":   (["close"], 1, None),          # not registered (no L2 consumer certifies against it)
    "macd_signal": (["macd_line"], 1, None),
    "swing_high":  (["high"], 1, "FM-045"),
    "swing_low":   (["low"], 1, "FM-046"),
    # L2 direct derived
    "body_ratio":       (["body_size", "candle_range"], 2, "FM-010"),
    "volatility_ratio": (["candle_range", "atr", "close"], 2, "FM-024"),
    "disp_strength":    (["body_size", "atr", "close"], 2, "FM-020"),   # BUG-FIX: +body_size,+close
    "ema_spread":       (["ema_fast", "ema_slow", "atr"], 2, "FM-022"),
    "momentum_score":   (["close", "atr"], 2, "FM-023"),
    "volume_ratio":     (["volume"], 2, "FM-VOLR"),
    "volume_spike":     (["volume_ratio"], 2, "FM-VOLS"),
    "trend_bias":       (["ema_fast", "ema_slow"], 2, "FM-TRB"),
    # v4.0 MACD split (feature_schema.py:82-84): `macd_hist` (single v3.0 column) is now two
    # canonical slots. macd_hist_raw = macd_line - macd_signal (FM-049, index 18, unchanged math);
    # macd_hist_z = rolling z-score of macd_hist_raw (FM-053, index 19 -- what v3.0's single
    # `macd_hist` column actually emitted, per compute_normalization's NORMALIZE_TO_NEW_COL).
    "macd_hist_raw":    (["macd_line", "macd_signal"], 2, "FM-049"),
    "macd_hist_z":      (["macd_hist_raw"], 2, "FM-053"),
    # L2 candidate / CRT-emitted derived identities (not in the 39-vector)
    "ema_spread_atr":          (["ema_fast", "ema_slow", "atr", "close"], 2, "FM-030"),
    "momentum_score_atr":      (["close", "atr"], 2, "FM-031"),
    "disp_strength_atr_rescale": (["disp_strength", "atr"], 2, "FM-029"),
    # FM-028 dep corrected 2026-07-31 (Semantic Layer Certification Audit, Tier 1 item 5): both
    # real callers (crt_engine_v2.py:1548, crt_gaussian_scorer.py:208-211) pass state.atr_abs
    # (ABSOLUTE ATR, an SMA of true_range) as the `atr` arg, not the close-relative FM-041 `atr`.
    # Mirrors the FM-050 fix (2026-07-19) for the same declaration-drift class.
    "displacement_atr_ratio":  (["candle_range", "true_range"], 2, "FM-028"),
    # L3 structural / event
    "higher_high":        (["swing_high"], 3, None),
    "lower_low":          (["swing_low"], 3, None),
    "break_of_structure": (["swing_high", "swing_low"], 3, None),
    "liquidity_sweep":    (["swing_high", "swing_low"], 3, None),
    "sweep_detected":     (["liquidity_sweep"], 3, None),
    "double_sweep":       (["liquidity_sweep"], 3, None),                # BUG-FIX: single entry
    # M10 / F-054-RD: gated production composition — close is a direct executable dep
    # (near_fast_ema + FM-021 kernel); retest_flag is intermediate, NOT a DAG node.
    "retest_depth":       (["liquidity_sweep", "ema_fast", "atr", "close"], 3, "FM-021"),
    "candles_since_retest": (["liquidity_sweep"], 3, "FM-065"),
    "liquidity_distance": (["close", "atr", "swing_high", "swing_low", "break_of_structure"], 3, "FM-025"),
    "displacement_retrace": (["close", "open"], 3, "FM-027"),
    # L4 composite / context
    "liquidity_pressure_score": (["liquidity_distance"], 4, "FM-026"),
    # M14B: production ranks absolute atr_14 = SMA14(TR(high,low,close));
    # NOT published relative atr (FM-041 = atr_14_raw/close, a DIFFERENT quantity).
    # 2026-07-19: edge tightened from the structural roots [close, high, low] to the direct
    # registered producer `true_range` (FM-040), so this matches ontology FM-050 exactly and the
    # ontology<->DAG crosscheck stays divergence-free (alarm armed rather than whitelisted).
    # M14B's conclusion is UNCHANGED -- true_range IS the absolute chain; only the granularity
    # of the recorded edge changed. atr_14 = SMA(14) of true_range.
    "volatility_regime":        (["true_range"], 4, "FM-050"),
    "trend_strength":           (["close"], 4, "FM-064"),
    # Item-2 (2026-07-19): registered as temporal_context FM-052/FM-051. `session` derives from
    # hour_of_day (not timestamp directly) — matches feature_pipeline.compute_context and keeps the
    # ontology<->DAG crosscheck divergence-free.
    "session":                  (["hour_of_day"], 4, "FM-052"),
    "hour_of_day":              (["timestamp"], 4, "FM-051"),
}


# ── graph algorithms ──────────────────────────────────────────────────────────────

def _kahn_toposort(edges: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Return (topological_order, cycle_nodes). cycle_nodes non-empty ⇒ not a DAG."""
    indeg = {n: 0 for n in edges}
    for n, deps in edges.items():
        for _ in deps:
            indeg[n] += 1
    # deterministic: process ready nodes in sorted order
    ready = sorted(n for n, d in indeg.items() if d == 0)
    order: list[str] = []
    users: dict[str, list[str]] = {n: [] for n in edges}
    for n, deps in edges.items():
        for d in deps:
            users[d].append(n)
    while ready:
        n = ready.pop(0)
        order.append(n)
        for u in sorted(users[n]):
            indeg[u] -= 1
            if indeg[u] == 0:
                ready.append(u)
        ready.sort()
    cycle = sorted(n for n, d in indeg.items() if d > 0)
    return order, cycle


def _grounds_in_raw(node: str, edges: dict[str, list[str]], memo: dict[str, bool]) -> bool:
    if node in memo:
        return memo[node]
    if node in _RAW_INPUTS:
        memo[node] = True
        return True
    deps = edges.get(node, [])
    memo[node] = bool(deps) and all(_grounds_in_raw(d, edges, memo) for d in deps)
    return memo[node]


# ── build ─────────────────────────────────────────────────────────────────────────

def build_dag() -> dict:
    edges = {n: list(v[0]) for n, v in _NODES.items()}
    layer = {n: v[1] for n, v in _NODES.items()}
    formula_id = {n: v[2] for n, v in _NODES.items()}

    # every referenced dependency must be a known node
    missing = sorted({d for deps in edges.values() for d in deps if d not in edges})
    order, cycle = _kahn_toposort(edges)
    topo_index = {n: i for i, n in enumerate(order)}

    # groundedness
    memo: dict[str, bool] = {}
    ungrounded = sorted(n for n in edges if not _grounds_in_raw(n, edges, memo))

    # layer monotonicity: every edge dep→node must have layer(dep) <= layer(node)
    violations = []
    for n, deps in edges.items():
        for d in deps:
            if layer.get(d, 99) > layer[n]:
                violations.append({"edge": f"{d}->{n}", "dep_layer": layer.get(d), "node_layer": layer[n]})

    # cross-check the registered-feature edges against the ontology depends_on
    lin = build_lineage_graph()
    ont_dep = lin["depends_on"]
    # v4.0 re-sync: ontology and DAG both use `candle_range` now, so no alias is needed for that
    # pair. Kept as an empty, documented seam in case a future ontology rename needs one again.
    _ALIAS: dict[str, str] = {}  # ontology name -> our vector name
    xcheck = []
    for name, ont_deps in ont_dep.items():
        our = name if name in edges else _ALIAS.get(name)
        if our is None or our not in edges:
            continue
        norm_ont = sorted(_ALIAS.get(d, d) for d in ont_deps)
        norm_our = sorted(edges[our])
        # ontology may carry finer structural leaves (ref_high/ref_low/bos_level/close_delta/
        # disp_open/...) that we roll up to their producing node; record, don't fail.
        extra_ont = sorted(set(norm_ont) - set(norm_our))
        extra_our = sorted(set(norm_our) - set(norm_ont))
        if extra_ont or extra_our:
            xcheck.append({"feature": name, "ontology_only": extra_ont, "dag_only": extra_our})

    canon_idx = {f: i for i, f in enumerate(CANONICAL_FEATURES)}
    nodes_out = []
    for n in sorted(edges):
        nodes_out.append({
            "name": n,
            "layer": layer[n],
            "layer_name": LAYER_NAMES[layer[n]],
            "topo_index": topo_index.get(n),
            "deps": sorted(edges[n]),
            "formula_id": formula_id[n],
            "in_canonical_vector": n in canon_idx,
            "canonical_index": canon_idx.get(n),
        })

    layer_hist: dict[str, int] = {}
    for n in edges:
        layer_hist[LAYER_NAMES[layer[n]]] = layer_hist.get(LAYER_NAMES[layer[n]], 0) + 1

    covered = {n for n in edges if n in canon_idx}
    missing_canonical = sorted(set(CANONICAL_FEATURES) - covered)

    return {
        "probe": "feature_dag_layers",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": ("research/governance only — structural DAG + semantic layering for bottom-up "
                      "certification order. No feature math. Grants no authority (§6.5)."),
        "layer_names": LAYER_NAMES,
        "n_nodes": len(edges),
        "n_canonical_covered": len(covered),
        "missing_canonical": missing_canonical,
        "undefined_dependency_nodes": missing,
        "is_dag": not cycle,
        "cycle_nodes": cycle,
        "ungrounded_nodes": ungrounded,
        "layer_monotonicity_violations": violations,
        "layer_histogram": layer_hist,
        "topological_order": order,
        "ontology_crosscheck": xcheck,
        "bugfixes_applied": {
            "disp_strength_body_size_close_edge": sorted(edges["disp_strength"]) == ["atr", "body_size", "close"],
            "double_sweep_single_entry": edges["double_sweep"] == ["liquidity_sweep"],
        },
        "nodes": nodes_out,
        "permanent_floor": "tests/test_feature_dag_layers.py",
    }


def _to_md(rep: dict) -> str:
    lines = [
        "# Feature DAG — Topological Layer Spine (bottom-up certification order)",
        "",
        f"_Generated {rep['generated_at']} · READ-ONLY · {rep['n_nodes']} nodes, "
        f"{rep['n_canonical_covered']}/{CANONICAL_FEATURE_DIM} canonical covered._",
        "",
        f"- is_dag: **{rep['is_dag']}** · cycles: {rep['cycle_nodes'] or 'none'}",
        f"- ungrounded: {rep['ungrounded_nodes'] or 'none'} · layer-monotonicity violations: "
        f"{len(rep['layer_monotonicity_violations'])}",
        f"- missing canonical: {rep['missing_canonical'] or 'none'}",
        f"- bug-fixes applied: {rep['bugfixes_applied']}",
        "",
        "## Layer histogram",
        "",
    ]
    for lname in LAYER_NAMES.values():
        if lname in rep["layer_histogram"]:
            lines.append(f"- {lname}: {rep['layer_histogram'][lname]}")
    lines += ["", "## Nodes by layer then topo index", ""]
    for lvl in sorted(LAYER_NAMES):
        names = [n for n in rep["nodes"] if n["layer"] == lvl]
        if not names:
            continue
        lines.append(f"### {LAYER_NAMES[lvl]}")
        for nd in sorted(names, key=lambda x: x["topo_index"]):
            idx = f" (vec idx {nd['canonical_index']})" if nd["in_canonical_vector"] else ""
            fid = f" [{nd['formula_id']}]" if nd["formula_id"] else ""
            lines.append(f"- `{nd['name']}`{fid}{idx} ← {nd['deps'] or 'raw'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _write(rep: dict) -> tuple[Path, str]:
    stem = f"feature_dag_layers-{_STAMP}"
    out_json = _GOV / f"{stem}.json"
    out_md = _GOV / f"{stem}.md"
    out_ptr = _GOV / "feature_dag_layers.LATEST.json"
    payload = json.dumps(rep, indent=2) + "\n"
    out_json.write_text(payload, encoding="utf-8")
    out_md.write_text(_to_md(rep), encoding="utf-8")
    sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    out_ptr.write_text(json.dumps({
        "_doc": "Stable pointer to the freshest feature-DAG layer spine. Dated artifacts are "
                "immutable; resolve via this pointer (verify sha256) — never by filename date.",
        "path": str(out_json.relative_to(_ROOT)).replace("\\", "/"),
        "generated_at": rep["generated_at"],
        "sha256": sha,
        "is_dag": rep["is_dag"],
        "n_nodes": rep["n_nodes"],
    }, indent=2) + "\n", encoding="utf-8")
    return out_json, sha


def main() -> int:
    rep = build_dag()
    out_json, sha = _write(rep)
    print(f"probe → {out_json.relative_to(_ROOT)}  (sha256 {sha[:12]}…)")
    print(f"  is_dag={rep['is_dag']} nodes={rep['n_nodes']} "
          f"canonical={rep['n_canonical_covered']}/{CANONICAL_FEATURE_DIM}")
    print(f"  missing_canonical={rep['missing_canonical'] or '[]'}  undefined_deps={rep['undefined_dependency_nodes'] or '[]'}")
    print(f"  monotonicity_violations={len(rep['layer_monotonicity_violations'])}  ungrounded={rep['ungrounded_nodes'] or '[]'}")
    print(f"  bugfixes={rep['bugfixes_applied']}")
    ok = (rep["is_dag"] and not rep["missing_canonical"] and not rep["undefined_dependency_nodes"]
          and not rep["layer_monotonicity_violations"] and not rep["ungrounded_nodes"]
          and all(rep["bugfixes_applied"].values()))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
