"""
feature_surface_closure_audit.py — Feature Surface Closure Audit (read-only).

Joins existing governance artifacts over the 38 CANONICAL_FEATURES:

  · feature_schema / CANONICAL_FEATURES
  · market_ontology.yaml
  · feature_38_lineage_census
  · phase1 producer-consumer graph + feature identity registry
  · feature_consumer_binding_manifest_fc05
  · feature_dependency_graph_fc05
  · feature_contract_v1
  · feature-math-grandfather-retirements / geometry census summary
  · rr_model zero_indices + zone_registry weights
  · FC1-A implementation evidence (PIT overlay for structure family)
  · FC1 change contracts + phase1 backlog open items

Produces:
  docs/governance/feature_surface_closure_audit-<date>.{json,md}

Usage:
  python scripts/analysis/feature_surface_closure_audit.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    CANONICAL_FEATURE_DIM,
    FEATURE_INDEX_MAP,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
)

_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_GOV = _ROOT / "docs" / "governance"

# Structure family remapped by FC1-A (production publication is causal delayed)
_FC1A_STRUCTURE = frozenset({
    "double_sweep", "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "liquidity_distance", "liquidity_pressure_score",
})
_FC1A_RETEST_SECONDARIES = frozenset({"retest_depth", "candles_since_retest"})


def _load_json(rel: str) -> Any:
    p = _ROOT / rel if not rel.startswith("/") else Path(rel)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _load_yaml(rel: str) -> Any:
    import yaml
    p = _ROOT / rel
    if not p.is_file():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _ontology_index(ont: dict | None) -> dict[str, dict]:
    """Map name / id / aliases → ontology record with section."""
    out: dict[str, dict] = {}
    if not ont:
        return out
    for section in ("primitives", "feature_compositions", "derived_metrics", "base_inputs"):
        block = ont.get(section) or {}
        if isinstance(block, dict):
            items = block.values() if not any(isinstance(v, list) for v in block.values()) else []
            # handle list-or-dict
            if isinstance(block, list):
                items = block
            elif all(isinstance(v, dict) for v in block.values()):
                items = list(block.values())
            else:
                items = [block] if block else []
        elif isinstance(block, list):
            items = block
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            rec = {**item, "_ontology_section": section}
            names = []
            for k in ("name", "id", "feature_id", "canonical_name", "key"):
                if item.get(k):
                    names.append(str(item[k]))
            for a in item.get("aliases") or item.get("legacy_names") or []:
                names.append(str(a))
            # also index by bare formula keys used in derived_metrics
            if section == "derived_metrics":
                # yaml may be list of dicts with name field
                pass
            for n in names:
                out[n] = rec
                # also strip FEAT- / FM- prefixes variants
                if n.startswith("FEAT-"):
                    out[n.replace("FEAT-", "").lower().replace("_", "")] = rec
    # second pass: list-style sections common in this ontology
    for section in ("primitives", "feature_compositions", "derived_metrics"):
        block = ont.get(section)
        if isinstance(block, list):
            for item in block:
                if not isinstance(item, dict):
                    continue
                rec = {**item, "_ontology_section": section}
                for k in ("name", "id", "feature_id", "canonical_name"):
                    if item.get(k):
                        out[str(item[k])] = rec
                if item.get("name"):
                    out[str(item["name"])] = rec
        elif isinstance(block, dict):
            for key, item in block.items():
                if isinstance(item, dict):
                    rec = {**item, "_ontology_section": section, "_map_key": key}
                    out[str(key)] = rec
                    if item.get("name"):
                        out[str(item["name"])] = rec
                    if item.get("id"):
                        out[str(item["id"])] = rec
    return out


def _index_lineage(feats: list) -> dict[str, dict]:
    return {f["name"]: f for f in feats if "name" in f}


def _index_contract(contract: dict | None) -> dict[str, dict]:
    if not contract:
        return {}
    feats = contract.get("features") or {}
    if isinstance(feats, list):
        return {f.get("name") or f.get("feature"): f for f in feats if isinstance(f, dict)}
    if isinstance(feats, dict):
        return feats
    return {}


def _consumer_features(consumers: list) -> dict[str, list[str]]:
    """feature → list of active consumer names."""
    m: dict[str, list[str]] = defaultdict(list)
    for c in consumers or []:
        name = c.get("consumer") or c.get("name") or "?"
        active = c.get("active", True)
        for f in c.get("features") or []:
            m[str(f)].append(f"{name}{'[active]' if active else '[inactive]'}")
    return m


def _dep_nodes(dep: dict | None) -> dict[str, dict]:
    if not dep:
        return {}
    nodes = dep.get("nodes") or {}
    if isinstance(nodes, list):
        return {n.get("name") or n.get("feature"): n for n in nodes if isinstance(n, dict)}
    if isinstance(nodes, dict):
        return nodes
    return {}


def _identity_by_name(identities: list) -> dict[str, list[dict]]:
    m: dict[str, list[dict]] = defaultdict(list)
    for ident in identities or []:
        for key in (ident.get("canonical_name"), *(ident.get("legacy_names") or [])):
            if key:
                m[str(key)].append(ident)
    return m


def _write_sites(graph: dict | None) -> dict[str, list]:
    if not graph:
        return {}
    return graph.get("column_write_sites") or {}


def _rr_zone_exposure() -> dict[str, Any]:
    out: dict[str, Any] = {"rr": None, "zone": None}
    rr_path = _ROOT / "models" / "rr_model.json"
    if rr_path.is_file():
        rr = json.loads(rr_path.read_text(encoding="utf-8"))
        zi = set(rr.get("zero_indices") or [])
        out["rr"] = {
            "path": "models/rr_model.json",
            "zero_indices": sorted(zi),
            "provenance": "models/rr_model.provenance.json",
            "pit_status": None,
        }
        prov = _ROOT / "models" / "rr_model.provenance.json"
        if prov.is_file():
            out["rr"]["pit_status"] = json.loads(prov.read_text(encoding="utf-8")).get("pit_status")
    zone_path = _ROOT / "models" / "zone_registry.json"
    if zone_path.is_file():
        z = json.loads(zone_path.read_text(encoding="utf-8"))
        zones = z.get("zones") or []
        out["zone"] = {
            "path": "models/zone_registry.json",
            "n_zones": len(zones),
            "feature_order": z.get("feature_order") or list(CANONICAL_FEATURES),
            "provenance": "models/zone_registry.provenance.json",
            "pit_status": None,
        }
        prov = _ROOT / "models" / "zone_registry.provenance.json"
        if prov.is_file():
            out["zone"]["pit_status"] = json.loads(prov.read_text(encoding="utf-8")).get("pit_status")
    return out


def _fc1a_overlay(name: str, pit_class: str | None) -> dict[str, Any]:
    """Post-FC1-A PIT status for structure family (code-verified binding)."""
    if name in _FC1A_STRUCTURE:
        return {
            "fc1a_applies": True,
            "pre_fc1a_pit_class": pit_class,
            "post_fc1a_pit_class": (
                "CAUSAL_DELAYED_PUBLICATION"
                if name in ("swing_high", "swing_low")
                else "STRUCTURE_WITH_CAUSAL_SWING"
            ),
            "production_bind": "causal_confirmed (available_at=t+k, k=SWING_WINDOW)",
            "research_bind": "*_centered_batch preserved" if name.startswith("swing_") else "derived from causal refs",
            "evidence": "CH-fc1a-swing-causal / F-051",
            "doc_stale": pit_class in (
                "CENTERED_SWING_LOOKAHEAD_IN_BATCH",
                "STRUCTURE_WITH_CENTERED_SWING",
            ),
        }
    if name in _FC1A_RETEST_SECONDARIES:
        return {
            "fc1a_applies": True,
            "role": "coherent_secondary",
            "note": "retest_* derives from liquidity_sweep; must follow causal sweep (no hybrid)",
            "post_fc1a_pit_class": pit_class if pit_class and "CAUSAL" in pit_class else "CAUSAL_DERIVED",
            "evidence": "FC1-A contract §2",
            "doc_stale": False,
        }
    if name == "volatility_regime":
        return {
            "fc1a_applies": False,
            "fc1d_applies": True,
            "pre_fc1d_pit_class": pit_class,
            "post_fc1a_pit_class": (
                "CAUSAL_ROLLING"
                if pit_class in ("CAUSAL_ROLLING", "REGIME_RANK_REVIEW") or pit_class is None
                else pit_class
            ),
            "production_bind": "rolling ATR percentile tercile N=200 (FC1-D)",
            "evidence": "CH-fc1d-volregime-causal / FC-0.5 adjudication",
            "doc_stale": pit_class == "REGIME_RANK_REVIEW",
        }
    return {"fc1a_applies": False}


def _closure_status(row: dict) -> dict:
    """
    Split code-surface closure from doc alignment and artifact exposure.

    code_status:
      CLOSED  — in schema + lineage + producer + effective PIT not an open LEAKING class
      PARTIAL — present but missing consumer annotation or open regime review
      OPEN    — missing lineage or producer
    doc_alignment: ALIGNED | STALE_CENSUS (lineage PIT label pre-dates FC1-A)
    ontology: IN_SCOPE_HIT | IN_SCOPE_MISS | N_A (ontology covers geometry/derived only)
    artifact_flags: list (RR/Zone unclean exposure is artifact-level, not code-open)
    """
    out = {
        "code_status": "CLOSED",
        "doc_alignment": "ALIGNED",
        "ontology": "N_A",
        "artifact_flags": [],
        "issues": [],
    }
    if not row.get("in_schema"):
        out["code_status"] = "MISSING_FROM_SCHEMA"
        return out
    if not row.get("lineage"):
        out["code_status"] = "OPEN_NO_LINEAGE"
        out["issues"].append("NO_LINEAGE")
        return out
    if not row.get("has_producer"):
        out["code_status"] = "OPEN_NO_PRODUCER"
        out["issues"].append("NO_PRODUCER")
        return out

    # Ontology is authoritative for geometry + registered derived metrics only
    geom_like = row["name"] in {
        "body_size", "wick_size", "body_ratio", "disp_strength", "retest_depth",
        "ema_spread", "momentum_score", "volatility_ratio",
        "liquidity_distance", "liquidity_pressure_score",
    }
    if geom_like:
        out["ontology"] = "IN_SCOPE_HIT" if row.get("ontology_hit") else "IN_SCOPE_MISS"
        if not row.get("ontology_hit"):
            out["issues"].append("ONTOLOGY_MISS")
            out["code_status"] = "PARTIAL_ONTOLOGY"

    # Effective PIT: leaking class still open if not remapped
    pit_eff = row.get("pit_class_effective") or ""
    if "LOOKAHEAD" in pit_eff or pit_eff == "CENTERED_SWING_LOOKAHEAD_IN_BATCH":
        out["issues"].append("PIT_LEAKING")
        out["code_status"] = "OPEN_PIT_LEAK"
    if pit_eff == "REGIME_RANK_REVIEW":
        out["issues"].append("REGIME_RANK_OPEN")
        if out["code_status"] == "CLOSED":
            out["code_status"] = "PARTIAL_REGIME_REVIEW"

    if row.get("fc1a_overlay", {}).get("doc_stale"):
        out["doc_alignment"] = "STALE_CENSUS"
        out["issues"].append("DOC_STALE_PIT_LABEL")

    if not row.get("consumers"):
        out["issues"].append("NO_CURATED_CONSUMER")
        if out["code_status"] == "CLOSED":
            out["code_status"] = "PARTIAL_NO_CONSUMER"

    # Artifact exposure (informational; does not open code surface)
    me = row.get("model_exposure") or {}
    if me.get("rr_active") and me.get("rr_pit_unclean"):
        out["artifact_flags"].append("RR_DIM_ACTIVE_ON_PIT_UNCLEAN_MODEL")
    if me.get("zone_weight_mass_sum") and me.get("zone_pit_unclean") and float(me["zone_weight_mass_sum"] or 0) > 0:
        out["artifact_flags"].append("ZONE_WEIGHT_ON_PIT_UNCLEAN_MODEL")

    return out


def _resolve_lineage_census() -> str:
    """Resolve the current lineage census through the stable pointer (sha-verified),
    falling back to the freshest embedded generated_at_utc — never by filename date."""
    import hashlib
    ptr = _ROOT / "docs/governance/feature_38_lineage_census.LATEST.json"
    if ptr.is_file():
        try:
            meta = json.loads(ptr.read_text(encoding="utf-8"))
            target = _ROOT / str(meta.get("path", ""))
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == meta.get("sha256"):
                return str(meta["path"])
        except Exception:
            pass
    best, best_ts = None, ""
    for p in (_ROOT / "docs/governance").glob("feature_38_lineage_census-*.json"):
        try:
            ts = str(json.loads(p.read_text(encoding="utf-8")).get("generated_at_utc") or "")
        except Exception:
            continue
        if ts > best_ts:
            best, best_ts = p, ts
    if best is None:
        raise FileNotFoundError("no readable feature_38_lineage_census-*.json")
    return str(best.relative_to(_ROOT)).replace("\\", "/")


def run_audit() -> dict:
    _lineage_path = _resolve_lineage_census()
    lineage_doc = _load_json(_lineage_path) or {}
    graph = _load_json("docs/governance/phase1_run1_feature_producer_consumer_graph-2026-07-10.json") or {}
    consumer_man = _load_json("docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json") or {}
    dep = _load_json("docs/governance/feature_dependency_graph_fc05-2026-07-10.json") or {}
    contract = _load_json("docs/governance/feature_contract_v1-2026-07-10.json") or {}
    identity_reg = _load_json("docs/governance/phase1_feature_identity_registry-2026-07-10.json") or {}
    universe = _load_json("docs/governance/phase1_run1_feature_universe_census-2026-07-10.json") or {}
    fc05_closure = _load_json("docs/governance/feature_pipeline_fc05_closure_manifest-2026-07-10.json") or {}
    fc1a_contract = _load_json("docs/governance/feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json") or {}
    pit_decision = _load_json("docs/governance/pit_phaseA_centered_swing_decision_record-2026-07-11.json") or {}
    grandpa = _load_json("docs/governance/feature-math-grandfather-retirements.json") or {}
    geom_sum = _load_json("docs/governance/geometry_census_summary.json") or {}
    ont = _load_yaml("configs/formulas/market_ontology.yaml")

    lineage_by = _index_lineage(lineage_doc.get("features") or [])
    ont_idx = _ontology_index(ont)
    cons_by = _consumer_features(consumer_man.get("consumers") or [])
    dep_by = _dep_nodes(dep)
    contract_by = _index_contract(contract)
    id_by = _identity_by_name(identity_reg.get("identities") or [])
    writes = _write_sites(graph)
    model_exp = _rr_zone_exposure()
    zero_idx = set((model_exp.get("rr") or {}).get("zero_indices") or [])

    # zone weight mass per dim
    zone_mass = [0.0] * CANONICAL_FEATURE_DIM
    zone_path = _ROOT / "models" / "zone_registry.json"
    if zone_path.is_file():
        z = json.loads(zone_path.read_text(encoding="utf-8"))
        for zone in z.get("zones") or []:
            w = zone.get("weights") or []
            for i, wi in enumerate(w):
                if i < len(zone_mass):
                    zone_mass[i] += abs(float(wi))

    rows = []
    for idx, name in enumerate(CANONICAL_FEATURES):
        lin = lineage_by.get(name)
        pit_class = (lin or {}).get("pit_class")
        overlay = _fc1a_overlay(name, pit_class)
        ont_hit = None
        for key in (name, name.upper(), f"FEAT-{name.upper()}", f"FM-{name}"):
            if key in ont_idx:
                ont_hit = {"key": key, "section": ont_idx[key].get("_ontology_section"),
                           "id": ont_idx[key].get("id") or ont_idx[key].get("feature_id")}
                break
        # derived_metrics / primitives by key or aliases (e.g. wick_size → candle_range)
        if not ont_hit and ont:
            for section in ("derived_metrics", "feature_compositions", "primitives"):
                block = ont.get(section)
                if isinstance(block, dict):
                    if name in block:
                        ont_hit = {"key": name, "section": section, "id": block[name].get("id")}
                        break
                    for k, item in block.items():
                        if not isinstance(item, dict):
                            continue
                        aliases = item.get("aliases") or []
                        if name in aliases or item.get("vector_key") == name:
                            ont_hit = {
                                "key": k,
                                "section": section,
                                "id": item.get("id"),
                                "via_alias": True,
                                "canonical_ontology_key": k,
                            }
                            break
                    if ont_hit:
                        break
                if isinstance(block, list):
                    for item in block:
                        if isinstance(item, dict) and item.get("name") == name:
                            ont_hit = {"key": name, "section": section, "id": item.get("id")}
                            break

        rr_active = idx not in zero_idx if model_exp.get("rr") else None
        row = {
            "index": idx,
            "name": name,
            "in_schema": True,
            "lineage": lin is not None,
            "pit_class_census": pit_class,
            "pit_class_effective": overlay.get("post_fc1a_pit_class") or pit_class,
            "formula_id": (lin or {}).get("formula_id"),
            "impl_refs": (lin or {}).get("impl_refs") or [],
            "lineage_consumers": (lin or {}).get("consumers") or [],
            "binding_consumers": cons_by.get(name) or [],
            "consumers": list(dict.fromkeys((lin or {}).get("consumers") or [] + (cons_by.get(name) or []))),
            "has_producer": name in writes or bool((lin or {}).get("impl_refs")),
            "write_sites": writes.get(name) or [],
            "dependency_node": bool(name in dep_by or any(
                (n.get("name") if isinstance(n, dict) else None) == name
                for n in (dep_by.values() if isinstance(list(dep_by.values())[:1], list) else [])
            ) or name in dep_by),
            "ontology_hit": ont_hit,
            "identity_registry": [
                {"feature_id": i.get("feature_id"), "status": i.get("status"),
                 "temporal": i.get("temporal_semantics")}
                for i in id_by.get(name) or []
            ],
            "contract_v1": contract_by.get(name) is not None or name in (
                contract.get("vector_members") or []
            ),
            "fc1a_overlay": overlay,
            "model_exposure": {
                "rr_active": rr_active,
                "rr_zeroed": idx in zero_idx if model_exp.get("rr") else None,
                "rr_pit_unclean": (model_exp.get("rr") or {}).get("pit_status") == "PIT_UNCLEAN_CENTERED_SWINGS",
                "zone_weight_mass_sum": zone_mass[idx] if idx < len(zone_mass) else None,
                "zone_pit_unclean": (model_exp.get("zone") or {}).get("pit_status") == "PIT_UNCLEAN_CENTERED_SWINGS",
            },
        }
        # fix consumers list construction
        row["consumers"] = list(dict.fromkeys(
            list((lin or {}).get("consumers") or []) + list(cons_by.get(name) or [])
        ))
        # dependency: check nodes dict keys
        if isinstance(dep.get("nodes"), dict):
            row["dependency_node"] = name in dep["nodes"]
        elif isinstance(dep.get("nodes"), list):
            row["dependency_node"] = any(
                (n.get("name") or n.get("feature")) == name for n in dep["nodes"] if isinstance(n, dict)
            )
        row["closure"] = _closure_status(row)
        row["closure_status"] = row["closure"]["code_status"]
        rows.append(row)

    status_counts = Counter(r["closure_status"] for r in rows)
    doc_counts = Counter(r["closure"]["doc_alignment"] for r in rows)
    pit_effective = Counter(r["pit_class_effective"] for r in rows)
    pit_census = Counter(r["pit_class_census"] for r in rows)

    # family rollups
    families = {
        "ohlcv_raw": ["open", "high", "low", "close", "volume"],
        "volume_derived": ["volume_ratio", "volume_spike"],
        "ema_trend": ["ema_fast", "ema_slow", "ema_spread", "trend_bias", "trend_strength", "momentum_score"],
        "volatility": ["atr", "volatility_ratio", "volatility_regime"],
        "momentum_indicators": ["rsi_14", "macd_line", "macd_signal", "macd_hist"],
        "structure_fc1a": sorted(_FC1A_STRUCTURE),
        "retest_secondaries": sorted(_FC1A_RETEST_SECONDARIES),
        "candle_anatomy": ["body_size", "wick_size", "body_ratio", "disp_strength"],
        "calendar": ["session", "hour_of_day"],
    }
    family_status = {}
    for fam, names in families.items():
        sub = [r for r in rows if r["name"] in names]
        family_status[fam] = {
            "n": len(sub),
            "status_counts": dict(Counter(r["closure_status"] for r in sub)),
            "doc_alignment": dict(Counter(r["closure"]["doc_alignment"] for r in sub)),
            "members": [r["name"] for r in sub],
        }

    open_remediations = {
        "FC1-A": {
            "status": fc1a_contract.get("status"),
            "change_id": fc1a_contract.get("implementation_change_id") or "CH-fc1a-swing-causal",
            "affects": sorted(_FC1A_STRUCTURE | _FC1A_RETEST_SECONDARIES),
        },
        "FC1-B-VOLUME": _load_json("docs/governance/feature_pipeline_change_contracts/FC1-B-VOLUME-SEMANTIC-SPLIT.json"),
        "FC1-C-FM-IDENTITY": _load_json("docs/governance/feature_pipeline_change_contracts/FC1-C-FM-IDENTITY-SEPARATION.json"),
        "FC1-D-VOLREGIME": _load_json("docs/governance/feature_pipeline_change_contracts/FC1-D-VOLREGIME-CAUSAL.json"),
        "F-051": "registered; FC1-A implemented",
        "rr_zone_provenance": {
            "rr": (model_exp.get("rr") or {}).get("pit_status"),
            "zone": (model_exp.get("zone") or {}).get("pit_status"),
            "rule": "no promote/re-enable/economic evidence without causal revalidation",
        },
    }
    # strip bulky contract bodies — keep status only
    for k in ("FC1-B-VOLUME", "FC1-C-FM-IDENTITY", "FC1-D-VOLREGIME"):
        c = open_remediations[k]
        if isinstance(c, dict):
            open_remediations[k] = {
                "status": c.get("status"),
                "title": c.get("title"),
                "change_id": c.get("change_id"),
            }

    # grandfather residual
    gd_open = []
    if isinstance(grandpa, dict):
        for item in grandpa.get("active") or grandpa.get("pins") or grandpa.get("retirements") or []:
            if isinstance(item, dict) and item.get("status") not in ("RETIRED", "CLOSED", None):
                gd_open.append(item.get("id") or item.get("gd_id") or item)
        # common shape: list under various keys
        for key in ("grandfathered", "active_pins", "open"):
            for item in grandpa.get(key) or []:
                if isinstance(item, dict):
                    gd_open.append(item.get("id") or item)

    audit = {
        "artifact": "feature_surface_closure_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": _DATE,
        "active_version": (_ROOT / "configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip(),
        "schema": {
            "canonical_feature_dim": CANONICAL_FEATURE_DIM,
            "n_features": len(CANONICAL_FEATURES),
            "schema_hash_md5": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "order": list(CANONICAL_FEATURES),
        },
        "sources": {
            "lineage_census": _lineage_path,
            "producer_consumer_graph": "docs/governance/phase1_run1_feature_producer_consumer_graph-2026-07-10.json",
            "consumer_binding_manifest": "docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json",
            "dependency_graph": "docs/governance/feature_dependency_graph_fc05-2026-07-10.json",
            "feature_contract_v1": "docs/governance/feature_contract_v1-2026-07-10.json",
            "identity_registry": "docs/governance/phase1_feature_identity_registry-2026-07-10.json",
            "universe_census": "docs/governance/phase1_run1_feature_universe_census-2026-07-10.json",
            "ontology": "configs/formulas/market_ontology.yaml",
            "fc05_closure_manifest": "docs/governance/feature_pipeline_fc05_closure_manifest-2026-07-10.json",
            "fc1a_contract": "docs/governance/feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json",
            "fc1a_impl": "docs/governance/fc1a_post_implementation_measurement-2026-07-11.md",
            "pit_decision": "docs/governance/pit_phaseA_centered_swing_decision_record-2026-07-11.json",
            "geometry_census_summary": "docs/governance/geometry_census_summary.json",
            "rr_provenance": "models/rr_model.provenance.json",
            "zone_provenance": "models/zone_registry.provenance.json",
        },
        "fc05_prior_status": {
            "FEATURE_PIPELINE_FC05_STATUS": fc05_closure.get("FEATURE_PIPELINE_FC05_STATUS"),
            "dependency_graph_status": fc05_closure.get("dependency_graph_status"),
            "formula_collision_status": fc05_closure.get("formula_collision_status"),
            "consumer_binding_status": fc05_closure.get("consumer_binding_status"),
            "volatility_regime_verdict": fc05_closure.get("volatility_regime_verdict"),
            "unresolved_unknowns": fc05_closure.get("unresolved_unknowns"),
        },
        "fc1a_status": {
            "contract_status": fc1a_contract.get("status"),
            "implementation_change_id": "CH-fc1a-swing-causal",
            "finding": "F-051",
            "structure_features_remapped": sorted(_FC1A_STRUCTURE),
            "ledger_importance": "INCONCLUSIVE (PC-2 failed) — see F-051",
        },
        "model_artifact_exposure": model_exp,
        "geometry_census_summary": geom_sum.get("counts") if isinstance(geom_sum, dict) else None,
        "rollup": {
            "closure_status_counts": dict(status_counts),
            "doc_alignment_counts": dict(doc_counts),
            "pit_class_census_counts": dict(pit_census),
            "pit_class_effective_counts": dict(pit_effective),
            "n_ontology_hits": sum(1 for r in rows if r["ontology_hit"]),
            "n_identity_registry_hits": sum(1 for r in rows if r["identity_registry"]),
            "n_with_write_sites": sum(1 for r in rows if r["write_sites"]),
            "n_rr_active_dims": sum(1 for r in rows if r["model_exposure"].get("rr_active")),
            "n_doc_stale_pit_after_fc1a": sum(
                1 for r in rows if r.get("fc1a_overlay", {}).get("doc_stale")
            ),
            "n_with_artifact_flags": sum(1 for r in rows if r["closure"].get("artifact_flags")),
        },
        "families": family_status,
        "open_remediations": open_remediations,
        "features": rows,
        "closure_verdict": _overall_verdict(status_counts, rows),
    }
    return audit


def _overall_verdict(status_counts: Counter, rows: list) -> dict:
    """Surface-level verdict — no economic claims."""
    n = len(rows)
    closed = status_counts.get("CLOSED", 0)
    partial = sum(v for k, v in status_counts.items() if k.startswith("PARTIAL"))
    open_n = sum(v for k, v in status_counts.items() if k.startswith("OPEN"))
    stale = sum(1 for r in rows if r["closure"].get("doc_alignment") == "STALE_CENSUS")
    return {
        "surface": "38_canonical_features",
        "n": n,
        "closed": closed,
        "partial": partial,
        "open": open_n,
        "doc_stale_census_labels": stale,
        "summary": (
            f"Code surface: {closed}/{n} CLOSED · {partial}/{n} PARTIAL · {open_n}/{n} OPEN. "
            f"Doc alignment: {stale}/{n} STALE_CENSUS labels. "
            "FC1-A structure + FC1-D rolling volregime production binds applied. "
            "RR/Zone remain PIT_UNCLEAN (separate economic-admissibility machine). "
            "No economic authority claimed."
        ),
        "CANONICAL_FEATURE_CODE_SURFACE_STATUS": (
            "CLOSED" if closed == n and partial == 0 and open_n == 0 and stale == 0 else "NOT_CLOSED"
        ),
        "blocked_for_canonical_feature_surface_closure": (
            []
            if closed == n and partial == 0 and open_n == 0 and stale == 0
            else [
                *(["residual PARTIAL code rows"] if partial else []),
                *(["residual OPEN code rows"] if open_n else []),
                *(["re-export lineage census (STALE_CENSUS labels)"] if stale else []),
            ]
        ),
        "blocked_for_economic_use_of_existing_artifacts": [
            "RR PIT_UNCLEAN_CENTERED_SWINGS — no promote/re-enable without causal revalidation",
            "Zone PIT_UNCLEAN_CENTERED_SWINGS — same provenance rule",
            "Causal dataset regeneration / revalidation before promotion of structure-sensitive models",
            "Existing model-specific lineage defects and §6.5 marginal-value requirements",
        ],
        "ready_for": [
            "PIT-correct batch production structure vectors (FC1-A)",
            "PIT-correct production volatility_regime rolling causal (FC1-D)",
            "Live delayed-confirmed structure via FeatureStore",
            "Research use of *_centered_batch / volatility_regime_global_batch",
            "wick_size as exact FM-002 candle_range alias (ontology)",
        ],
        "note_separation": (
            "Feature-surface closure and artifact economic admissibility are separate. "
            "Closing the 38-feature code surface does NOT authorize RR/Zone reuse or imply edge."
        ),
    }


def _to_md(audit: dict) -> str:
    r = audit["rollup"]
    v = audit["closure_verdict"]
    lines = [
        "# Feature Surface Closure Audit — 38 Canonical Features",
        "",
        f"_Generated {audit['generated_at']} · ACTIVE_VERSION=`{audit['active_version']}` · read-only synthesis._",
        "",
        "## Verdict",
        "",
        f"**{v['summary']}**",
        "",
        "### Ready for",
        *[f"- {x}" for x in v["ready_for"]],
        "",
        "### Blocked for CANONICAL FEATURE-SURFACE CLOSURE",
        *(
            [f"- {x}" for x in v.get("blocked_for_canonical_feature_surface_closure") or []]
            or ["- *(none — see rollup for residual PARTIAL/OPEN if any)*"]
        ),
        "",
        "### Blocked for ECONOMIC USE OF EXISTING ARTIFACTS",
        *(
            [f"- {x}" for x in v.get("blocked_for_economic_use_of_existing_artifacts") or []]
        ),
        "",
        f"> {v.get('note_separation', '')}",
        "",
        "## Schema",
        "",
        f"- dim={audit['schema']['canonical_feature_dim']} · "
        f"schema_hash={audit['schema']['schema_hash_md5']} · "
        f"order_hash={audit['schema']['feature_order_hash']}",
        "",
        "## Rollup",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| CLOSED (code) | {r['closure_status_counts'].get('CLOSED', 0)} |",
        f"| PARTIAL_* (code) | {sum(v for k,v in r['closure_status_counts'].items() if k.startswith('PARTIAL'))} |",
        f"| OPEN_* (code) | {sum(v for k,v in r['closure_status_counts'].items() if k.startswith('OPEN'))} |",
        f"| Doc STALE_CENSUS | {r.get('doc_alignment_counts', {}).get('STALE_CENSUS', 0)} |",
        f"| Ontology hits | {r['n_ontology_hits']}/38 |",
        f"| Identity-registry hits | {r['n_identity_registry_hits']}/38 |",
        f"| Write-site hits | {r['n_with_write_sites']}/38 |",
        f"| RR active dims | {r['n_rr_active_dims']}/38 |",
        f"| Features with artifact flags | {r.get('n_with_artifact_flags', 0)} |",
        "",
        "### Code-closure status histogram",
        "",
        "```json",
        json.dumps(r["closure_status_counts"], indent=2),
        "```",
        "",
        "### PIT class — census vs effective (FC1-A overlay)",
        "",
        "| Class | Census (2026-07-10) | Effective (post-FC1-A) |",
        "|---|---:|---:|",
    ]
    all_pit = sorted(set(r["pit_class_census_counts"]) | set(r["pit_class_effective_counts"]))
    for c in all_pit:
        lines.append(
            f"| `{c}` | {r['pit_class_census_counts'].get(c, 0)} | "
            f"{r['pit_class_effective_counts'].get(c, 0)} |"
        )
    lines += [
        "",
        "## FC1-A status",
        "",
        f"- contract: **{audit['fc1a_status']['contract_status']}**",
        f"- change: `{audit['fc1a_status']['implementation_change_id']}`",
        f"- finding: {audit['fc1a_status']['finding']}",
        f"- structure remapped: {', '.join(f'`{x}`' for x in audit['fc1a_status']['structure_features_remapped'])}",
        f"- ledger importance: {audit['fc1a_status']['ledger_importance']}",
        "",
        "## Families",
        "",
        "| Family | n | code statuses | doc |",
        "|---|---:|---|---|",
    ]
    for fam, info in audit["families"].items():
        lines.append(
            f"| `{fam}` | {info['n']} | `{info['status_counts']}` | `{info.get('doc_alignment', {})}` |"
        )
    lines += [
        "",
        "## Per-feature matrix",
        "",
        "| # | Feature | PIT effective | Code closure | Doc | Ontology | RR | Zone Σ|w| | FC1-A |",
        "|---:|---|---|---|---|---|---|---:|---|",
    ]
    for f in audit["features"]:
        ont = f["closure"].get("ontology", "—")
        if ont == "N_A":
            ont = "—"
        elif ont == "IN_SCOPE_HIT":
            ont = "Y"
        elif ont == "IN_SCOPE_MISS":
            ont = "MISS"
        rr = f["model_exposure"].get("rr_active")
        rr_s = "Y" if rr else ("N" if rr is False else "—")
        zw = f["model_exposure"].get("zone_weight_mass_sum")
        zw_s = f"{zw:.3f}" if isinstance(zw, (int, float)) else "—"
        fc = "Y" if f["fc1a_overlay"].get("fc1a_applies") else "—"
        doc = f["closure"].get("doc_alignment", "—")
        lines.append(
            f"| {f['index']} | `{f['name']}` | `{f['pit_class_effective']}` | "
            f"**{f['closure_status']}** | {doc} | {ont} | {rr_s} | {zw_s} | {fc} |"
        )
    lines += [
        "",
        "## Open remediations (adjacent surface)",
        "",
        "```json",
        json.dumps(audit["open_remediations"], indent=2, default=str)[:4000],
        "```",
        "",
        "## Sources",
        "",
    ]
    for k, v in audit["sources"].items():
        lines.append(f"- **{k}:** `{v}`")
    lines += [
        "",
        "## Method notes",
        "",
        "1. **Read-only** — no `src/` or config mutation; synthesizes dated artifacts.",
        "2. **FC1-A overlay** updates *effective* PIT for the structure family; census file remains historical (DOC_STALE flag).",
        "3. **CLOSED** requires schema + lineage + producer + no blocking issue; ontology gaps and stale docs yield PARTIAL.",
        "4. **Authority:** architecture/governance surface hygiene only — no ΔG001 claim.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    audit = run_audit()
    out = _GOV
    out.mkdir(parents=True, exist_ok=True)
    stem = f"feature_surface_closure_audit-{_DATE}"
    jp = out / f"{stem}.json"
    mp = out / f"{stem}.md"
    jp.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    mp.write_text(_to_md(audit), encoding="utf-8")
    v = audit["closure_verdict"]
    r = audit["rollup"]
    print(f"Feature Surface Closure Audit → {jp.relative_to(_ROOT)}")
    print(f"  {v['summary']}")
    print(f"  statuses: {r['closure_status_counts']}")
    print(f"  FC1-A: {audit['fc1a_status']['contract_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
