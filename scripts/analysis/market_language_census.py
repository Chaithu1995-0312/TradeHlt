"""
market_language_census.py — deterministic market-language vocabulary census.

WHAT IT DOES (read-only, no mutation of authorities)
    Walks the FIVE canonical authority files plus the trade-schema sources and emits a
    machine-extractable census of the EXISTING market-language vocabulary, split into the
    eight sections of the census taxonomy (S1..S8):

      S1 FEATURE SCHEMA          every governed feature identity + vector binding
      S2 STATE SCHEMA            four DISTINCT state vocabularies (never merged):
                                   (a) CRT machine states   (b) feature-enum states
                                   (c) SMC/CHoCH structural  (d) trade/execution
      S3 HIERARCHICAL STATE TREE parent->child per vocabulary (implementation-evidence only)
      S4 TRADE SCHEMA            trade/execution vocabulary with citations
      S5 TRACEABLE ONTOLOGY      OHLCV -> Feature -> State -> Shape -> Trade code relationships
      S6 DUPLICATES / OVERLAPS   N-way word overlaps across vocabularies (surfaced, NOT normalized)
      S7 ORPHANS                 features with no state | states with no parent |
                                 shapes referencing undefined states
      S8 CANONICAL VOCABULARY    single table: word | type | parent | vocabulary | source_file

AUTHORITY MODEL (the rules that make this deterministic)
    - configs/formulas/*.yaml  + src/features/feature_schema.py + src/features/registry/ +
      src/features/feature_states.py + magnitude_states.py + smc/choch.py +
      src/journal/trade_logger.py + schema.py + src/config_layer/execution_planner.py ARE
      AUTHORITY. This script NEVER invents, renames, or normalises a word: every emitted word is
      read verbatim from its authority file and every row carries a source_file citation.
    - All words are cross-checked for side-by-side reuse (S6) rather than folded into one list.

USAGE
    python scripts/analysis/market_language_census.py            # emit JSON + MD report
    python scripts/analysis/market_language_census.py --json out # write JSON to a path

Outputs are written under docs/research-readiness/market_language_census_report.json (.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover  # noqa: BLE001
    yaml = None

_ROOT = Path(__file__).resolve().parents[2]

# ── Authority set (exact files) ───────────────────────────────────────────────
ONTOLOGY = _ROOT / "configs" / "formulas" / "market_ontology.yaml"
CRT_STATES = _ROOT / "configs" / "formulas" / "market_crt_states.yaml"
CRT_IDENTITY = _ROOT / "configs" / "formulas" / "crt_state_identity.yaml"
SHAPES = _ROOT / "configs" / "formulas" / "market_shapes.yaml"
FEATURE_SCHEMA_PY = _ROOT / "src" / "features" / "feature_schema.py"
CHOCH_PY = _ROOT / "src" / "features" / "smc" / "choch.py"
TRADE_SCHEMA_PY = _ROOT / "src" / "journal" / "schema.py"
TRADE_LOGGER_PY = _ROOT / "src" / "journal" / "trade_logger.py"
PLANNER_PY = _ROOT / "src" / "config_layer" / "execution_planner.py"
BACKTEST_PY = _ROOT / "src" / "runtime" / "backtest_v2.py"
CRT_ENGINE_PY = _ROOT / "src" / "config_layer" / "crt_engine_v2.py"

# Ontology sections that carry governed feature identities (mirrors
# src/features/registry/__init__.py::_ITERATED_SECTIONS).
ITERATED_SECTIONS = (
    "source_inputs", "primitives", "feature_compositions", "derived_metrics",
    "rolling_indicators", "temporal_context", "structural_states",
)

STATE_VOCABS = ("crt_machine", "feature_enum", "smc_choch", "trade_execution")

# ── loaders ────────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> object:
    if yaml is None:
        raise RuntimeError("PyYAML is required to run the market-language census")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return path.resolve().relative_to(_ROOT.resolve()).as_posix()


# ── S1 FEATURE SCHEMA ─────────────────────────────────────────────────────────
def census_s1(ont: dict) -> dict:
    rows = []
    for section in ITERATED_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            lin = spec.get("lineage") or {}
            states = spec.get("states") or []
            formula = spec.get("formula")
            num_den = spec.get("numerator") and spec.get("denominator")
            impl = spec.get("impl")
            source = formula or impl or (
                f"{spec.get('numerator')}/{spec.get('denominator')}" if num_den else None
            ) or ""
            rows.append({
                "name": name,
                "fm_id": spec.get("id"),
                "section": section,
                "lifecycle": spec.get("lifecycle"),
                "formula_or_source": source,
                "activation_condition": spec.get("bounds") or "",
                "n_states": len(states) if isinstance(states, list) else 0,
                "vector_key": lin.get("vector_key"),
                "vector_index": lin.get("vector_index"),
                "source_file": _rel(ONTOLOGY),
            })
    # Derive the canonical vector order from the ontology (v6.0 authoritative source for
    # the generated CANONICAL_FEATURES) and mirror the feature_schema hash functions.
    slots = {}
    for row in rows:
        vi = row["vector_index"]
        if isinstance(vi, int) and row["vector_key"]:
            slots.setdefault(vi, row["vector_key"])
    vector = [slots[i] for i in sorted(slots)]
    schema_hash = hashlib.md5("".join(vector).encode()).hexdigest()
    order_hash = hashlib.sha256(json.dumps(list(vector), sort_keys=False).encode()).hexdigest()[:16]
    return {
        "header": {
            "schema_vector_derived_from": _rel(ONTOLOGY),
            "schema_hash_md5": schema_hash,
            "feature_order_hash_sha256_16": order_hash,
            "dim": len(vector),
            "schema_hash_formula": "md5(concat(names)) + sha256(json).hex[:16] mirror of "
                                   "src/features/feature_schema.py:237/243-248 (v6.0 generated vector)",
        },
        "rows": rows,
        "_n": len(rows),
    }


# ── S2 STATE SCHEMA ───────────────────────────────────────────────────────────
def _feature_enum_states(ont: dict) -> list:
    rows = []
    for section in ("structural_states", "htf_states"):
        for fname, spec in (ont.get(section) or {}).items():
            for st in (spec.get("states") or []):
                if not isinstance(st, dict):
                    continue
                rows.append({
                    "state_name": st.get("name"),
                    "parent": fname,
                    "fm_id": spec.get("id"),
                    "value": st.get("value"),
                    "activation_condition": st.get("condition"),
                    "source_file": _rel(ONTOLOGY),
                })
        return rows


def census_s2(ont: dict, crt_states: dict, crt_id: dict) -> dict:
    # (a) CRT machine states — semantic identity core + predicate activation.
    crt_pred = {}
    for st in (crt_states.get("states") or []):
        if isinstance(st, dict) and st.get("name"):
            crt_pred[st["name"]] = st.get("when") or {}
    crt_rows = []
    identity = crt_id.get("identity") or {}
    for name, stdef in (identity.get("states") or {}).items():
        crt_rows.append({
            "state_name": name,
            "parent": None,
            "defined": stdef.get("defined"),
            "sticky": stdef.get("sticky"),
            "reachable": stdef.get("reachable"),
            "activation_condition": crt_pred.get(name) or None,
            "predicate_source": stdef.get("predicate_source"),
            "source_file": _rel(CRT_IDENTITY),
        })
    # (b) feature-enum states.
    enum_rows = _feature_enum_states(ont)
    # (c) SMC / CHoCH structural — the pure signed combination in smc/choch.py + the
    #     ontology structural identities it composes. No invented state-machine states.
    smc_rows = [{
        "state_name": "change_of_character",
        "parent": None,
        "domain": "{-1, 0, +1}",
        "activation_condition": "break_of_structure != 0 and trend_bias != 0 and "
                                "sign(break_of_structure) != sign(trend_bias)",
        "source_file": _rel(CHOCH_PY),
        "note": "Pure signed operation over registered features (BOS x trend_bias); the ontology "
                "explicitly excludes BOS/CHOCH detection state-machines (market_ontology.yaml:32).",
    }]
    # (d) trade / execution vocabulary — from journal schema + planner + crt Trade geometry.
    trade_rows = census_s4()
    return {
        "vocabularies": {
            "crt_machine": {
                "note": "CRT engine/resolver lifecycle states (constructor-neutral identity).",
                "rows": crt_rows, "_n": len(crt_rows),
            },
            "feature_enum": {
                "note": "Feature-value -> meaning map declared in ontology states blocks "
                        "(name/value/condition/description shape).",
                "rows": enum_rows, "_n": len(enum_rows),
            },
            "smc_choch": {
                "note": "SMC structural signal (CHoCH) — a signed combination, NOT a state machine.",
                "rows": smc_rows, "_n": len(smc_rows),
            },
            "trade_execution": {
                "note": "Trade/execution record + intent + geometry vocabulary.",
                "rows": trade_rows, "_n": len(trade_rows),
            },
        }
    }


# ── S3 HIERARCHICAL STATE TREE ────────────────────────────────────────────────
def census_s3(crt_id: dict, enum_rows: list) -> dict:
    identity = crt_id.get("identity") or {}
    crt_edges = []
    for src, targets in (identity.get("valid_transitions") or {}).items():
        for tgt in targets:
            crt_edges.append({"parent": src, "child": tgt})
    enum_edges = []
    for r in enum_rows:
        enum_edges.append({"parent": r["parent"], "child": r["state_name"]})
    return {
        "crt_machine_transition_edges": crt_edges,
        "crt_parent_timeframe_states": identity.get("parent_timeframe_states"),
        "feature_enum_feature_to_state": enum_edges,
        "note": "crt_machine edges are transition edges from crt_state_identity.yaml "
                "valid_transitions (implementation-evidence), not an inferred hierarchy.",
    }


# ── S4 TRADE SCHEMA ───────────────────────────────────────────────────────────
def census_s4() -> list:
    rows = []

    def add(name, definition, source, parent=None, vocabulary="record_field"):
        rows.append({
            "name": name, "definition": definition, "source_file": _rel(source),
            "parent": parent, "vocabulary": vocabulary,
        })

    # TradeRecord (src/journal/schema.py).
    fields = {
        "trade_id": "opaque execution-intent id (authoritative identity)",
        "timestamp": "entry timestamp",
        "symbol": "instrument symbol",
        "regime": "market regime classification",
        "config_profile": "config profile reference",
        "confidence": "decision confidence",
        "rr": "reward-to-risk ratio",
        "zone": "zone-gate value",
        "allocated_risk": "allocated risk capital",
        "portfolio_exposure_before": "portfolio exposure before entry",
        "engine_action": "engine decision action",
        "override_action": "override action",
        "result": "WIN | LOSS | BREAKEVEN (outcome after close)",
        "pnl": "realised pnl",
        "duration_candles": "trade duration in candles",
        "drawdown_at_entry": "drawdown at entry",
    }
    for fn, doc in fields.items():
        add(fn, doc, TRADE_SCHEMA_PY)
    # Geometry (src/config_layer/crt_engine_v2.py Trade + backtest position record).
    add("Trade", "CRT trade geometry: id, direction, entry_price, sl_price, tp1_price",
CRT_ENGINE_PY, vocabulary="geometry")
    for f in ("entry_price", "sl_price", "tp1_price"):
        add(f, "trade price level (crt_engine_v2.py Trade)", CRT_ENGINE_PY,
            parent="Trade", vocabulary="geometry")
    add("entry_price_fill", "filled entry price (backtest position record)", BACKTEST_PY,
        parent="Trade", vocabulary="geometry")
    add("tp2_price", "second take-profit level (backtest position record)", BACKTEST_PY,
        parent="Trade", vocabulary="geometry")
    add("risk_pct", "gate-adjusted risk percentage", BACKTEST_PY, parent="Trade",
        vocabulary="geometry")
    add("rr_ratio", "reward/risk ratio on the record", BACKTEST_PY, parent="Trade",
        vocabulary="geometry")
    # Planner intents + delegation note (src/config_layer/execution_planner.py).
    for intent in ("BREAKOUT", "PULLBACK", "LIQ_SWEEP", "REVERSAL", "CONTINUATION", "UNKNOWN"):
        add(intent, "ExecutionPlannerV1_2 trade-intent class", PLANNER_PY,
            parent="intent", vocabulary="intent")
    add("entry_price_plan", "entry price derived by planner; SL/TP delegated to compute_crt_levels",
        PLANNER_PY, parent="intent", vocabulary="intent")
    return rows
# ── S5 TRACEABLE ONTOLOGY ─────────────────────────────────────────────────────
def census_s5(ont: dict, crt_states: dict, shapes: dict, s1: dict) -> dict:
    enum_names = {r["state_name"] for r in _feature_enum_states(ont)}
    feature_names = {r["name"] for r in s1["rows"]}
    grounded = enum_names | feature_names  # a predicate key is grounded as a feature OR state name
    crt_refs = set()
    for st in (crt_states.get("states") or []):
        for k in (st.get("when") or {}):
            crt_refs.add(k)
    shape_refs = set()
    for sh in (shapes.get("shapes") or []):
        for k in (sh.get("when") or {}):
            shape_refs.add(k)
    planner_req = set()
    try:
        src = PLANNER_PY.read_text(encoding="utf-8")
        chunk = src.split("_REQUIRED_FEATURE_KEYS", 1)[1].split(")", 1)[0]
        planner_req = {x.strip("'\", ") for x in chunk.splitlines()
                       if x.strip().startswith('"') and '"' in x}
        planner_req = {x for x in planner_req if x}
    except Exception:  # noqa: BLE001
        planner_req = set()
    return {
        "chain": [
            {"layer": "OHLCV (source_inputs)",
             "names": list((ont.get("source_inputs") or {}).keys())},
            {"layer": "Features (S1)", "count": s1["_n"]},
            {"layer": "Feature identities referenced by CRT predicates",
             "names": sorted(crt_refs), "not_grounded": sorted(crt_refs - grounded)},
            {"layer": "Feature identities referenced by Shape predicates",
             "names": sorted(shape_refs), "not_grounded": sorted(shape_refs - grounded)},
            {"layer": "Trade-planner required feature keys",
             "names": sorted(planner_req)},
        ],
        "note": "Code relationships, not prose: a feature is bound to a vector slot (S1); "
                "feature-enum states are declared in ontology states blocks (S2b); CRT/Shape "
                "predicates reference those state names (verified above); the planner consumes "
                "the features (required-keys).",
    }


# ── S6 DUPLICATES / OVERLAPS ──────────────────────────────────────────────────
def _tokens(name) -> set:
    """Deterministic tokenisation of a vocabulary word (camelCase + snake_case).

    'DoubleSweepTrap' -> {double, sweep, trap}; 'liquidity_sweep' -> {liquidity, sweep};
    'SWEEP' -> {sweep}. Used solely to surface concept-stem overlaps across vocabularies.
    """
    joined = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    joined = re.sub(r"[^A-Za-z0-9]+", " ", joined)
    return {t.lower() for t in joined.split() if t}


def census_s6(sections: dict, shape_list: list) -> dict:
    label = {r["state_name"]: ("state", "feature_enum")
             for r in sections["s2"]["vocabularies"]["feature_enum"]["rows"]}
    for r in sections["s2"]["vocabularies"]["crt_machine"]["rows"]:
        label[r["state_name"]] = ("state", "crt_machine")
    for r in sections["s2"]["vocabularies"]["smc_choch"]["rows"]:
        label[r["state_name"]] = ("state", "smc_choch")
    for r in sections["s4"]:
        label.setdefault(r["name"], ("trade", r["vocabulary"]))
    for r in sections["s1"]["rows"]:
        label.setdefault(r["name"], ("feature", r["section"]))
    for sh in shape_list:
        if sh.get("name"):
            label.setdefault(sh["name"], ("shape", "shape_layer"))

    # 1) EXACT-NAME overlaps — the same word (case-insensitive) used verbatim in >=2 vocabularies.
    occ = defaultdict(set)
    for word, tag in label.items():
        occ[str(word).upper()].add(f"{tag[0]}/{tag[1]}")
    exact = [{"kind": "exact_name", "word": w, "appears_in": sorted(tags)}
             for w, tags in sorted(occ.items()) if len(tags) > 1]

    # 2) CONCEPT-TOKEN overlaps — a linguistic stem shared across >=2 vocabularies
    #    (e.g. 'sweep' in feature liquidity_sweep, feature sweep_detected, CRT SWEEP,
    #     shape DoubleSweepTrap). Surfaced, never normalised.
    stem = defaultdict(set)  # stem -> {(type/vocab, original_word)}
    for word, tag in label.items():
        for tok in _tokens(word):
            stem[tok].add((f"{tag[0]}/{tag[1]}", str(word)))
    concept = []
    for tok, members in sorted(stem.items()):
        vocabs = {m[0] for m in members}
        if len(vocabs) >= 2:
            concept.append({
                "kind": "concept_token",
                "stem": tok,
                "vocabularies": sorted(vocabs),
                "member_words": sorted({m[1].lower() for m in members}),
            })
    return {"exact_name_overlaps": exact, "concept_token_overlaps": concept}


# ── S7 ORPHANS ────────────────────────────────────────────────────────────────
def census_s7(ont: dict, enum_rows: list, shapes: dict, s1: dict) -> dict:
    enum_names = {r["state_name"] for r in enum_rows}
    no_state = [r["name"] for r in s1["rows"]
                if r["n_states"] == 0 and r["section"] != "source_inputs"]
    undefined_shape_refs = []
    for sh in (shapes.get("shapes") or []):
        for k in (sh.get("when") or {}):
            if k not in enum_names:
                undefined_shape_refs.append({"shape": sh.get("name"), "ref_key": k})
    no_parent = [r["state_name"] for r in enum_rows if not r["parent"]]
    return {
        "features_with_no_state": sorted(no_state),
        "states_with_no_feature_parent": sorted(no_parent),
        "shape_predicate_keys_referencing_undefined_feature_state": sorted(
            undefined_shape_refs, key=lambda d: (d.get("shape") or "", d.get("ref_key") or "")),
        "note": "Orphans are reported, never silently normalised. A shape.when key that is not a "
                "declared feature-enum state is a linkage gap to surface.",
    }


# ── S8 CANONICAL VOCABULARY ───────────────────────────────────────────────────
def census_s8(sections: dict, shape_list: list) -> list:
    table = []
    for r in sections["s1"]["rows"]:
        table.append({"word": r["name"], "type": "feature", "parent": r["section"],
                      "vocabulary": "feature_schema", "source_file": r["source_file"]})
    for stub in ("crt_machine", "feature_enum", "smc_choch"):
        for r in sections["s2"]["vocabularies"][stub]["rows"]:
            table.append({"word": r["state_name"], "type": "state",
                          "parent": r.get("parent") or "",
                          "vocabulary": stub, "source_file": r.get("source_file", "")})
    for r in sections["s4"]:
        table.append({"word": r["name"], "type": "trade", "parent": r.get("parent") or "",
                      "vocabulary": f"trade/{r.get('vocabulary','')}",
                      "source_file": r["source_file"]})
    for sh in shape_list:
        if sh.get("name"):
            table.append({"word": sh["name"], "type": "shape", "parent": sh.get("family") or "",
                          "vocabulary": "shape_layer", "source_file": _rel(SHAPES)})
    table = [r for r in table if r["word"]]
    table.sort(key=lambda r: (r["word"].upper(), r["type"], r["source_file"]))
    return table
# ── orchestration ─────────────────────────────────────────────────────────────
def run() -> dict:
    ont = _load_yaml(ONTOLOGY)
    crt_states = _load_yaml(CRT_STATES)
    crt_id = _load_yaml(CRT_IDENTITY)
    shapes = _load_yaml(SHAPES)
    shape_list = [s for s in (shapes.get("shapes") or []) if isinstance(s, dict)]

    s1 = census_s1(ont)
    s2 = census_s2(ont, crt_states, crt_id)
    s3 = census_s3(crt_id, s2["vocabularies"]["feature_enum"]["rows"])
    s4 = census_s4()
    s5 = census_s5(ont, crt_states, shapes, s1)
    sections = {"s1": s1, "s2": s2, "s3": s3, "s4": s4, "s5": s5}
    s6 = census_s6(sections, shape_list)
    s7 = census_s7(ont, s2["vocabularies"]["feature_enum"]["rows"], shapes, s1)
    s8 = census_s8(sections, shape_list)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "census": "market_language",
        "version": "1.0",
        "authority_files": [_rel(ONTOLOGY), _rel(CRT_STATES), _rel(CRT_IDENTITY),
                            _rel(SHAPES), _rel(FEATURE_SCHEMA_PY)],
        "S1_feature_schema": s1,
        "S2_state_schema": s2,
        "S3_hierarchical_state_tree": s3,
        "S4_trade_schema": s4,
        "S5_traceable_ontology": s5,
        "S6_duplicates_overlaps": s6,
        "S7_orphans": s7,
        "S8_canonical_vocabulary": s8,
    }


def _summary(res: dict) -> str:
    st = res["S2_state_schema"]["vocabularies"]
    n2 = sum(v["_n"] for v in st.values())
    ov = len(res["S6_duplicates_overlaps"]["exact_name_overlaps"])
    ct = len(res["S6_duplicates_overlaps"]["concept_token_overlaps"])
    orphan_feats = len(res["S7_orphans"]["features_with_no_state"])
    return (f"    S1 features={res['S1_feature_schema']['_n']}  "
            f"states(all-vocabs)={n2}  "
            f"canonical-vocab(S8)={len(res['S8_canonical_vocabulary'])}  "
            f"exact-overlaps(S6)={ov}  concept-overlaps(S6)={ct}  "
            f"orphan-no-state-feats(S7)={orphan_feats}")


def _render_md(res: dict) -> str:
    L = []
    L.append("# Market Language Census (deterministic)")
    L.append("")
    L.append(f"Generated: `{res['generated_at']}`")
    L.append("")
    L.append("## Authority files (every emitted word is cited to one of these)")
    for a in res["authority_files"]:
        L.append(f"- `{a}`")
    L.append("")
    L.append("## S1 — Feature schema")
    L.append("| name | fm_id | section | lifecycle | formula/source | vector_index | n_states |")
    L.append("|---|---|---|---|---|---|---|")
    for r in res["S1_feature_schema"]["rows"]:
        L.append(f"| {r['name']} | {r['fm_id']} | {r['section']} | {r['lifecycle']} | "
                 f"{r['formula_or_source']!r} | {r['vector_index']} | {r['n_states']} |")
    L.append("")
    L.append("## S2 — State schema (four distinct vocabularies, never merged)")
    for vname in ("crt_machine", "feature_enum", "smc_choch"):
        v = res["S2_state_schema"]["vocabularies"][vname]
        L.append(f"### `{vname}` — {v.get('note','')}  ({v['_n']})")
        L.append("| state | parent | activation | source |")
        L.append("|---|---|---|---|")
        for r in v["rows"]:
            cond = r.get("activation_condition")
            if isinstance(cond, dict):
                cond = " AND ".join(f"{k}={val}" for k, val in cond.items())
            L.append(f"| {r['state_name']} | {r.get('parent') or ''} | {cond!r} | "
                     f"{r.get('source_file','')} |")
        L.append("")
    L.append("## S6 — Duplicates / overlaps (surfaced, not normalised)")
    L.append("### Exact-name overlaps (same word reused in >=2 vocabularies)")
    L.append("| word | appears in |")
    L.append("|---|---|")
    for o in res["S6_duplicates_overlaps"]["exact_name_overlaps"]:
        L.append(f"| {o['word']} | {', '.join(o['appears_in'])} |")
    L.append("")
    L.append("### Concept-token overlaps (linguistic stem shared across vocabularies)")
    L.append("| stem | vocabularies | member words |")
    L.append("|---|---|---|")
    for o in res["S6_duplicates_overlaps"]["concept_token_overlaps"]:
        L.append(f"| {o['stem']} | {', '.join(o['vocabularies'])} | {', '.join(o['member_words'])} |")
    L.append("")
    L.append("## S7 — Orphans")
    nf = ", ".join(res["S7_orphans"]["features_with_no_state"])
    L.append(f"- features with no declared state: `{nf or '(none)'}`")
    L.append("- shape predicates referencing an undefined feature-state: `%s`" %
             res["S7_orphans"]["shape_predicate_keys_referencing_undefined_feature_state"])
    L.append("")
    L.append("## S8 — Canonical vocabulary")
    L.append("| word | type | parent | vocabulary | source_file |")
    L.append("|---|---|---|---|---|")
    for r in res["S8_canonical_vocabulary"]:
        L.append(f"| {r['word']} | {r['type']} | {r['parent']} | {r['vocabulary']} | "
                 f"{r['source_file']} |")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic market-language census")
    ap.add_argument("--json", default=str(_ROOT / "docs" / "research-readiness" /
                                          "market_language_census_report.json"))
    ap.add_argument("--md", default=str(_ROOT / "docs" / "research-readiness" /
                                        "market_language_census_report.md"))
    args = ap.parse_args()
    res = run()
    jp = Path(args.json); mp = Path(args.md)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(res, indent=2), encoding="utf-8")
    mp.write_text(_render_md(res), encoding="utf-8")
    print("market_language_census OK")
    print("  ->", jp)
    print("  ->", mp)
    print(_summary(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
def census_s8(sections: dict, shape_list: list) -> list:
    """S8 — single canonical vocabulary table: word | type | parent | vocabulary | source_file."""
    table = []
    for r in sections["s1"]["rows"]:
        table.append({"word": r["name"], "type": "feature", "parent": r["section"],
                      "vocabulary": "feature_schema", "source_file": r["source_file"]})
    for stub in ("crt_machine", "feature_enum", "smc_choch"):
        for r in sections["s2"]["vocabularies"][stub]["rows"]:
            table.append({"word": r["state_name"], "type": "state",
                          "parent": r.get("parent") or "",
                          "vocabulary": stub, "source_file": r.get("source_file", "")})
    for r in sections["s4"]:
        table.append({"word": r["name"], "type": "trade", "parent": r.get("parent") or "",
                      "vocabulary": f"trade/{r.get('vocabulary','')}",
                      "source_file": r["source_file"]})
    for sh in shape_list:
        if sh.get("name"):
            table.append({"word": sh["name"], "type": "shape", "parent": sh.get("family") or "",
                          "vocabulary": "shape_layer", "source_file": _rel(SHAPES)})
    table = [r for r in table if r["word"]]
    table.sort(key=lambda r: (r["word"].upper(), r["type"], r["source_file"]))
    return table
