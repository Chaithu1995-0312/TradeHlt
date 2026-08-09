#!/usr/bin/env python3
"""
feature_surface_query.py — LLM-facing read-only query API over the feature surface.

Joins EXISTING governance artifacts (no new census). One command/API surface for:

  FEATURE_ID ↔ FORMULA ↔ OHLCV INPUTS ↔ ALIASES ↔ PRODUCERS ↔ CONSUMERS
  ↔ CONFIG KEYS ↔ ACTIVE VALUES ↔ OVERRIDE PATHS ↔ PIT STATUS
  ↔ REACHABILITY ↔ TEST_REFERENCE_HITS ↔ CLOSURE STATUS

Evidence discipline (2026-07-11 hardening): every joined element carries an
evidence_class ∈ {PROVEN, HEURISTIC, TEXT_REFERENCE}; name-based config joins are
HEURISTIC, test scans are TEXT_REFERENCE (textual hits, NOT behavioral coverage);
ambiguous aliases FAIL CLOSED (AmbiguousAliasError); artifact freshness comes from
embedded generated_at + schema validation, never the filename.

Examples:
  python scripts/governance/feature_surface_query.py --summary
  python scripts/governance/feature_surface_query.py --feature swing_high
  python scripts/governance/feature_surface_query.py --feature FEAT-SWING_HIGH_CAUSAL_CONFIRMED
  python scripts/governance/feature_surface_query.py --pit CAUSAL_DELAYED_PUBLICATION
  python scripts/governance/feature_surface_query.py --closure CLOSED
  python scripts/governance/feature_surface_query.py --list --json
  python scripts/governance/feature_surface_query.py --search sweep
  python scripts/governance/feature_surface_query.py --field consumers --feature body_ratio

Importable:
  from scripts.governance.feature_surface_query import FeatureSurfaceIndex
  idx = FeatureSurfaceIndex.load()
  row = idx.get(\"swing_high\")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console guard

_ROOT = Path(__file__).resolve().parents[2]
_GOV = _ROOT / "docs" / "governance"
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── artifact paths (existing only) ───────────────────────────────────────────
#
# Freshness authority = the artifact's EMBEDDED generated_at timestamp, never the
# filename (a copied old artifact with a newer filename must not win — governance
# rule: stale census artifacts must not silently become authority). A stable
# LATEST pointer (written by the census script) wins when present and verifiable.


class AmbiguousAliasError(KeyError):
    """An alias maps to more than one feature — the query fails closed."""

    def __init__(self, alias: str, candidates: list[str]):
        super().__init__(alias)
        self.alias = alias
        self.candidates = sorted(candidates)

    def __str__(self) -> str:  # noqa: D105
        return f"alias {self.alias!r} is AMBIGUOUS — candidates: {self.candidates}"


def _artifact_generated_at(p: Path) -> str:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("generated_at") or data.get("generated_at_utc") or "")


def _latest_by_generated_at(gov: Path, pattern: str, what: str) -> tuple[Path, list[str]]:
    """Freshest readable artifact by embedded generated_at. Empty → FileNotFoundError."""
    warnings: list[str] = []
    best: Path | None = None
    best_ts = ""
    for p in gov.glob(pattern):
        ts = _artifact_generated_at(p)
        if not ts:
            warnings.append(f"no_generated_at_or_unreadable:{p.name}")
            continue
        if ts > best_ts:
            best, best_ts = p, ts
    if best is None:
        raise FileNotFoundError(f"no readable {pattern} with generated_at under {gov} ({what})")
    return best, warnings


def _latest_lineage(gov: Path) -> tuple[Path, list[str]]:
    # Stable pointer written by scripts/analysis/feature_38_lineage_census.py wins
    # when present and its target verifies (path exists + sha256 matches).
    warnings: list[str] = []
    ptr = gov / "feature_38_lineage_census.LATEST.json"
    if ptr.is_file():
        try:
            meta = json.loads(ptr.read_text(encoding="utf-8"))
            target = gov.parent.parent / str(meta.get("path", ""))
            if target.is_file():
                import hashlib
                sha = hashlib.sha256(target.read_bytes()).hexdigest()
                if sha == meta.get("sha256"):
                    return target, warnings
                warnings.append("latest_pointer_sha_mismatch — falling back to generated_at scan")
            else:
                warnings.append("latest_pointer_target_missing — falling back to generated_at scan")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"latest_pointer_unreadable({exc}) — falling back to generated_at scan")
    best, w = _latest_by_generated_at(gov, "feature_38_lineage_census-*.json", "lineage census")
    return best, warnings + w


def _latest_closure(gov: Path) -> tuple[Path, list[str]]:
    return _latest_by_generated_at(gov, "feature_surface_closure_audit-*.json", "closure audit")


ARTIFACTS = {
    "lineage": None,  # filled at load
    "closure": None,
    "identity": _GOV / "phase1_feature_identity_registry-2026-07-10.json",
    "producer_consumer": _GOV / "phase1_run1_feature_producer_consumer_graph-2026-07-10.json",
    "consumer_binding": _GOV / "feature_consumer_binding_manifest_fc05-2026-07-10.json",
    "dependency": _GOV / "feature_dependency_graph_fc05-2026-07-10.json",
    "contract_v1": _GOV / "feature_contract_v1-2026-07-10.json",
    "ontology": _ROOT / "configs" / "formulas" / "market_ontology.yaml",
    "crt_reachability": _GOV / "crt_config_reachability.json",
    "config_reachability": _ROOT / "docs" / "research-readiness" / "config-reachability-report.json",
    "rr_provenance": _ROOT / "models" / "rr_model.provenance.json",
    "zone_provenance": _ROOT / "models" / "zone_registry.provenance.json",
    "rr_model": _ROOT / "models" / "rr_model.json",
    "zone_registry": _ROOT / "models" / "zone_registry.json",
    "surface_gate": _GOV / "canonical_feature_code_surface_closure-2026-07-11.md",
}


def _jload(p: Path) -> Any:
    if not p or not Path(p).is_file():
        return None
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _yload(p: Path) -> Any:
    if not p or not Path(p).is_file():
        return None
    import yaml
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


# ── index ────────────────────────────────────────────────────────────────────

@dataclass
class FeatureSurfaceIndex:
    """In-memory join of feature-surface artifacts."""

    rows: dict[str, dict] = field(default_factory=dict)  # keyed by canonical vector name
    by_feature_id: dict[str, str] = field(default_factory=dict)  # FEATURE_ID → name
    by_alias: dict[str, str] = field(default_factory=dict)  # UNAMBIGUOUS alias → name
    by_alias_ambiguous: dict[str, list[str]] = field(default_factory=dict)  # alias → candidates (fail closed)
    meta: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | None = None) -> "FeatureSurfaceIndex":
        root = root or _ROOT
        gov = root / "docs" / "governance"

        # root is honored consistently; empty candidate sets raise FileNotFoundError
        # (never IndexError), and freshness comes from embedded generated_at.
        lineage_path, lineage_warnings = _latest_lineage(gov)
        closure_path, closure_warnings = _latest_closure(gov)

        lineage = _jload(lineage_path) or {}
        closure = _jload(closure_path) or {}
        identity = _jload(gov / "phase1_feature_identity_registry-2026-07-10.json") or {}
        graph = _jload(gov / "phase1_run1_feature_producer_consumer_graph-2026-07-10.json") or {}
        consumers = _jload(gov / "feature_consumer_binding_manifest_fc05-2026-07-10.json") or {}
        dep = _jload(gov / "feature_dependency_graph_fc05-2026-07-10.json") or {}
        contract = _jload(gov / "feature_contract_v1-2026-07-10.json") or {}
        ont = _yload(root / "configs" / "formulas" / "market_ontology.yaml") or {}
        crt_reach = _jload(gov / "crt_config_reachability.json") or {}
        cfg_reach = _jload(root / "docs" / "research-readiness" / "config-reachability-report.json") or {}
        rr_model = _jload(root / "models" / "rr_model.json") or {}
        rr_prov = _jload(root / "models" / "rr_model.provenance.json") or {}
        zone = _jload(root / "models" / "zone_registry.json") or {}
        zone_prov = _jload(root / "models" / "zone_registry.provenance.json") or {}

        # schema
        sys.path.insert(0, str(root / "src"))
        from features.feature_schema import (  # noqa: PLC0415
            CANONICAL_FEATURES,
            CANONICAL_FEATURE_DIM,
            FEATURE_INDEX_MAP,
            SCHEMA_HASH,
            FEATURE_ORDER_HASH,
        )

        lineage_by = {f["name"]: f for f in (lineage.get("features") or []) if "name" in f}
        closure_by = {f["name"]: f for f in (closure.get("features") or []) if "name" in f}
        write_sites = graph.get("column_write_sites") or {}

        # consumers from binding manifest
        cons_by: dict[str, list[dict]] = {n: [] for n in CANONICAL_FEATURES}
        for c in consumers.get("consumers") or []:
            cname = c.get("consumer") or "?"
            active = c.get("active", True)
            entry = {
                "consumer": cname,
                "active": active,
                "type": c.get("type"),
                "entrypoint": c.get("entrypoint"),
            }
            for fname in c.get("features") or []:
                if fname in cons_by:
                    cons_by[fname].append(entry)

        # identity registry: map names/aliases → identities.
        # Alias targets are COLLECTED (never last-write-wins) and materialized at the
        # end of load(): 1 target → by_alias, >1 → by_alias_ambiguous (fail closed).
        alias_targets: dict[str, set[str]] = {}

        def _collect_alias(alias, target) -> None:
            if not alias or not target or str(alias) == str(target):
                return
            alias_targets.setdefault(str(alias), set()).add(str(target))

        id_by_name: dict[str, list[dict]] = {n: [] for n in CANONICAL_FEATURES}
        for ident in identity.get("identities") or []:
            names = [ident.get("canonical_name")] + list(ident.get("legacy_names") or [])
            for n in names:
                if not n:
                    continue
                if n in id_by_name:
                    id_by_name[n].append(ident)
                if n in CANONICAL_FEATURES:
                    for a in ident.get("legacy_names") or []:
                        _collect_alias(a, n)
                    _collect_alias(ident.get("canonical_name"), n)

        # ontology aliases + formulas — collisions collected, never silently overwritten
        ont_by: dict[str, dict] = {}
        ontology_alias_collisions: dict[str, list[str]] = {}

        def _ont_register(k: str, rec: dict) -> None:
            prev = ont_by.get(k)
            if prev is not None and prev.get("ontology_key") != rec.get("ontology_key"):
                ontology_alias_collisions.setdefault(k, [prev.get("ontology_key")]).append(
                    rec.get("ontology_key")
                )
                return  # first registration wins; collision is EXPOSED, not resolved
            ont_by[k] = rec

        for section in ("primitives", "feature_compositions", "derived_metrics"):
            block = ont.get(section) or {}
            if not isinstance(block, dict):
                continue
            for key, item in block.items():
                if not isinstance(item, dict):
                    continue
                rec = {**item, "ontology_key": key, "ontology_section": section}
                _ont_register(key, rec)
                # the vector name an ontology entry binds to, if any
                vector_name = None
                if item.get("vector_key") and str(item["vector_key"]) in CANONICAL_FEATURES:
                    vector_name = str(item["vector_key"])
                for a in item.get("aliases") or []:
                    _ont_register(str(a), rec)
                    if str(a) in CANONICAL_FEATURES:
                        vector_name = vector_name or str(a)
                if item.get("vector_key"):
                    _ont_register(str(item["vector_key"]), rec)
                if vector_name:
                    _collect_alias(key, vector_name)
                    for a in item.get("aliases") or []:
                        _collect_alias(a, vector_name)

        # config reachability → feature name. NAME-BASED join = HEURISTIC evidence by
        # definition (a config key mentioning a feature name is not a proven semantic
        # dependency). Matching is token-segment based: the feature's full underscore-
        # segment sequence must appear as a contiguous run of the key's segments — no
        # substring traps ('low' in 'allowed_sessions', 'atr' in 'exponatrial', ...).
        cfg_by: dict[str, list[dict]] = {n: [] for n in CANONICAL_FEATURES}
        for row in cfg_reach.get("keys") or []:
            section = row.get("section")
            key = row.get("key")
            verdict = row.get("verdict")
            for n in CANONICAL_FEATURES:
                if _cfg_key_matches(n, key):
                    cfg_by[n].append({
                        "section": section,
                        "key": key,
                        "verdict": verdict,
                        "evidence": row.get("evidence"),
                        "source": "config-reachability-report",
                        "evidence_class": "HEURISTIC",
                        "match_rule": "token_segment_run",
                    })

        # CRT matrix (params that use feature-like names) — same rule, same class
        crt_by: dict[str, list[dict]] = {n: [] for n in CANONICAL_FEATURES}
        for row in crt_reach.get("matrix") or []:
            k = str(row.get("key") or "")
            for n in CANONICAL_FEATURES:
                if _cfg_key_matches(n, k):
                    crt_by[n].append({
                        "key": k,
                        "runtime_value": row.get("runtime_value_bnbusdt"),
                        "load_authority": row.get("load_authority"),
                        "in_production_json": row.get("in_production_json"),
                        "status": row.get("status") or row.get("reachability_status"),
                        "source": "crt_config_reachability",
                        "evidence_class": "HEURISTIC",
                        "match_rule": "token_segment_run",
                    })

        # env / override paths
        overrides_global = list(crt_reach.get("environment_overrides") or [])
        # known feature-surface env overrides (from pipeline)
        feature_env = [
            {
                "name": "TRUST_SWING_CAUSAL",
                "effect": "dual-emit research_view only; must not mutate production (FC1-A)",
                "features": ["swing_high", "swing_low"],
                "source": "feature_pipeline.compute_structure_liquidity",
            },
            {
                "name": "TRUST_VOLREGIME_CAUSAL",
                "effect": "dual-emit research_view; production is rolling causal (FC1-D)",
                "features": ["volatility_regime"],
                "source": "feature_pipeline.compute_volatility_regime",
            },
        ]

        # RR / zone exposure
        zero_idx = set(rr_model.get("zero_indices") or [])
        zone_mass = [0.0] * CANONICAL_FEATURE_DIM
        for z in zone.get("zones") or []:
            for i, w in enumerate(z.get("weights") or []):
                if i < len(zone_mass):
                    zone_mass[i] += abs(float(w))

        # tests: static scan (cached)
        tests_by = _scan_tests(root, CANONICAL_FEATURES)

        # active production values for matched config keys
        active_cfg = _load_active_config_values(root)

        idx = cls()
        idx.sources = {
            "lineage": str(lineage_path.relative_to(root)).replace("\\", "/"),
            "closure": str(closure_path.relative_to(root)).replace("\\", "/"),
            "identity": "docs/governance/phase1_feature_identity_registry-2026-07-10.json",
            "producer_consumer": "docs/governance/phase1_run1_feature_producer_consumer_graph-2026-07-10.json",
            "consumer_binding": "docs/governance/feature_consumer_binding_manifest_fc05-2026-07-10.json",
            "dependency": "docs/governance/feature_dependency_graph_fc05-2026-07-10.json",
            "ontology": "configs/formulas/market_ontology.yaml",
            "crt_reachability": "docs/governance/crt_config_reachability.json",
            "config_reachability": "docs/research-readiness/config-reachability-report.json",
        }
        # ── artifact freshness / schema validation (loud, never silent) ──
        stale_artifacts: list[dict] = []
        for label, art, path in (("lineage", lineage, lineage_path), ("closure", closure, closure_path)):
            a_hash = art.get("schema_hash") or (art.get("schema") or {}).get("schema_hash")
            a_dim = art.get("dim") or (art.get("schema") or {}).get("dim") or art.get("canonical_feature_dim")
            problems = []
            if a_hash and a_hash != SCHEMA_HASH and a_hash != FEATURE_ORDER_HASH:
                problems.append(f"schema_hash {a_hash} != live {SCHEMA_HASH}")
            if a_dim and int(a_dim) != CANONICAL_FEATURE_DIM:
                problems.append(f"dim {a_dim} != live {CANONICAL_FEATURE_DIM}")
            if not (art.get("generated_at") or art.get("generated_at_utc")):
                problems.append("missing generated_at")
            if problems:
                stale_artifacts.append({"artifact": label, "path": str(path), "problems": problems})

        idx.meta = {
            "canonical_feature_dim": CANONICAL_FEATURE_DIM,
            "schema_hash": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH,
            "artifact_warnings": lineage_warnings + closure_warnings,
            "stale_artifacts": stale_artifacts,  # non-empty ⇒ STALE_ARTIFACT: do not treat rows as authority
            "closure_verdict": (closure.get("closure_verdict") or {}),
            "surface_status": (closure.get("closure_verdict") or {}).get(
                "CANONICAL_FEATURE_CODE_SURFACE_STATUS"
            ),
            "active_version": (closure.get("active_version")
                               or open(root / "configs/production/ACTIVE_VERSION", encoding="utf-8").read().strip()),
            "rr_pit_status": rr_prov.get("pit_status"),
            "zone_pit_status": zone_prov.get("pit_status"),
            "generated_from": "existing artifacts only — no new census",
        }

        for name in CANONICAL_FEATURES:
            i = FEATURE_INDEX_MAP[name]
            lin = lineage_by.get(name) or {}
            clo = closure_by.get(name) or {}
            identities = id_by_name.get(name) or []

            # primary FEATURE_ID + THE identity all formula metadata must come from
            # (never identities[0] — order-dependent metadata can contradict the id).
            feature_ids = [x.get("feature_id") for x in identities if x.get("feature_id")]
            primary_ident: dict | None = None
            identity_metadata_source = "none"
            canonical_idents = [
                x for x in identities if x.get("status") == "CANONICAL_IMPLEMENTATION_SELECTED"
            ]
            if len(canonical_idents) == 1:
                primary_ident = canonical_idents[0]
                identity_metadata_source = "canonical_implementation_selected"
            elif len(canonical_idents) > 1:
                identity_metadata_source = "ambiguous_multiple_canonical"
            elif len(identities) == 1:
                primary_ident = identities[0]
                identity_metadata_source = "sole_identity"
            elif len(identities) > 1:
                identity_metadata_source = "ambiguous_multiple_non_canonical"
            primary_id = (primary_ident or {}).get("feature_id")
            if not primary_id and feature_ids:
                # id shown but metadata stays None — labeled, never mixed across identities
                primary_id = feature_ids[0]
            if not primary_id:
                # synthetic stable id for unregistered vector members
                primary_id = f"VEC-{name.upper()}"

            # aliases
            aliases = set()
            for x in identities:
                aliases.add(x.get("canonical_name"))
                aliases.update(x.get("legacy_names") or [])
            if name in ont_by:
                o = ont_by[name]
                aliases.add(o.get("ontology_key"))
                aliases.update(o.get("aliases") or [])
                if o.get("vector_key"):
                    aliases.add(o["vector_key"])
            # reverse: ontology keys that alias TO this vector name
            for k, rec in ont_by.items():
                if rec.get("vector_key") == name or name in (rec.get("aliases") or []):
                    aliases.add(k)
                    aliases.update(rec.get("aliases") or [])
            aliases.discard(None)
            aliases.discard(name)

            # formula — identity-sourced fields come ONLY from primary_ident (same
            # identity as the displayed FEATURE_ID); lineage-sourced fields labeled.
            _pi = primary_ident or {}
            formula = {
                "formula_id": lin.get("formula_id") or _pi.get("formula_id"),
                "formula": lin.get("formula") or _pi.get("formula_definition"),
                "formula_version": _pi.get("formula_version"),
                "ontology_id": (ont_by.get(name) or {}).get("id"),
                "ontology_section": (ont_by.get(name) or {}).get("ontology_section"),
                "impl": lin.get("impl"),
                "impl_refs": lin.get("impl_refs") or [],
                "implementation_authority": _pi.get("implementation_authority"),
                "identity_metadata_source": identity_metadata_source,
                "evidence_class": "PROVEN" if (primary_ident or lin) else "HEURISTIC",
            }

            # producers
            producers = {
                "write_sites": write_sites.get(name) or [],
                "impl_refs": lin.get("impl_refs") or [],
                "impl": lin.get("impl"),
            }

            # consumers — ONE key domain (consumer name) for both sources, so a
            # binding-manifest consumer is never duplicated by its lineage twin.
            consumer_list = []
            seen: set[str] = set()
            for entry in cons_by.get(name) or []:
                cname = str(entry["consumer"])
                if cname not in seen:
                    seen.add(cname)
                    consumer_list.append({**entry, "evidence_class": "PROVEN"})
            for c in lin.get("consumers") or []:
                cname = str(c)
                if cname not in seen:
                    seen.add(cname)
                    consumer_list.append({
                        "consumer": cname, "active": None, "type": "lineage_curated",
                        # lineage consumers come from hand-curation + textual grep
                        "evidence_class": "TEXT_REFERENCE",
                    })

            # config keys + active values
            config_keys = list(cfg_by.get(name) or []) + list(crt_by.get(name) or [])
            active_values = []
            for ck in config_keys:
                sec = ck.get("section")
                key = ck.get("key")
                if sec and key and key != "<section>":
                    path = f"{sec}.{key}" if sec else key
                    val = _dig(active_cfg, sec, key)
                    active_values.append({
                        "path": path,
                        "value": val,
                        "verdict": ck.get("verdict") or ck.get("status"),
                        "runtime_value_probe": ck.get("runtime_value"),
                    })
                elif ck.get("key") and "runtime_value" in ck:
                    active_values.append({
                        "path": f"params/crt≈{ck['key']}",
                        "value": ck.get("runtime_value"),
                        "verdict": ck.get("load_authority"),
                    })

            # overrides relevant to this feature
            overrides = [e for e in feature_env if name in e.get("features", [])]
            for eo in overrides_global:
                blob = json.dumps(eo).lower()
                if name in blob:
                    overrides.append({**eo, "source": "crt_config_reachability.environment_overrides"})

            # reachability summary
            reach = {
                "in_canonical_vector": True,
                "index": i,
                "has_producer": bool(producers["write_sites"] or producers["impl_refs"]),
                "n_consumers": len(consumer_list),
                "n_config_keys": len(config_keys),
                "rr_model_dim_active": i not in zero_idx if rr_model else None,
                "zone_weight_mass": zone_mass[i] if i < len(zone_mass) else None,
                "dependency_node": _dep_has(dep, name),
                "contract_v1_member": name in (contract.get("vector_members") or [])
                or name in (contract.get("features") or {}),
            }

            # PIT
            pit = {
                "pit_class": lin.get("pit_class") or clo.get("pit_class_effective"),
                "pit_class_census": clo.get("pit_class_census") or lin.get("pit_class"),
                "pit_class_effective": clo.get("pit_class_effective") or lin.get("pit_class"),
                "pit_note": lin.get("pit"),
                "pit_caveat": lin.get("pit_caveat"),
                "fc1a": clo.get("fc1a_overlay") or {},
            }

            # closure
            closure_status = {
                "code_status": clo.get("closure_status") or (clo.get("closure") or {}).get("code_status"),
                "doc_alignment": (clo.get("closure") or {}).get("doc_alignment"),
                "ontology": (clo.get("closure") or {}).get("ontology"),
                "artifact_flags": (clo.get("closure") or {}).get("artifact_flags") or [],
                "issues": (clo.get("closure") or {}).get("issues") or [],
            }

            # test REFERENCES — textual \b-name\b hits in tests/, NOT behavioral coverage
            test_hits = tests_by.get(name) or []

            row = {
                "FEATURE_ID": primary_id,
                "FEATURE_IDS_ALL": feature_ids or [primary_id],
                "NAME": name,
                "INDEX": i,
                "FORMULA": formula,
                "OHLCV_INPUTS": lin.get("source_ohlcv") or [],
                "ALIASES": sorted(a for a in aliases if a),
                "PRODUCERS": producers,
                "CONSUMERS": consumer_list,
                "CONFIG_KEYS": config_keys,
                "ACTIVE_VALUES": active_values,
                "OVERRIDE_PATHS": overrides,
                "PIT_STATUS": pit,
                "REACHABILITY": reach,
                # textual occurrences of the name in tests/ — evidence_class TEXT_REFERENCE;
                # a hit does NOT mean the feature's behavior is tested.
                "TEST_REFERENCE_HITS": test_hits,
                "CLOSURE_STATUS": closure_status,
                "IDENTITIES": [
                    {
                        "feature_id": x.get("feature_id"),
                        "canonical_name": x.get("canonical_name"),
                        "status": x.get("status"),
                        "temporal_semantics": x.get("temporal_semantics"),
                        "legacy_names": x.get("legacy_names"),
                    }
                    for x in identities
                ],
                "MODEL_EXPOSURE": {
                    "rr_dim_active": i not in zero_idx if rr_model else None,
                    "rr_pit_status": rr_prov.get("pit_status"),
                    "zone_weight_mass": zone_mass[i] if i < len(zone_mass) else None,
                    "zone_pit_status": zone_prov.get("pit_status"),
                },
            }
            idx.rows[name] = row
            idx.by_feature_id[primary_id] = name
            for fid in feature_ids:
                idx.by_feature_id[fid] = name
            for a in aliases:
                _collect_alias(a, name)
            _collect_alias(primary_id, name)

        # identity-only names that aren't vector members (e.g. swing_high_centered_batch).
        # An identity whose feature_id is ALREADY bound to a vector member does NOT get a
        # shadow row (that would duplicate the same identity under two names) — its
        # canonical_name becomes an alias to the vector row instead.
        for ident in identity.get("identities") or []:
            cn = ident.get("canonical_name")
            fid = ident.get("feature_id")
            if not cn or cn in idx.rows:
                continue
            if fid and fid in idx.by_feature_id:
                _collect_alias(cn, idx.by_feature_id[fid])
                continue
            if fid:
                idx.by_feature_id[fid] = cn
            # lightweight shadow row (first-class resolvable; not a vector member)
            if cn not in idx.rows:
                    idx.rows[cn] = {
                        "FEATURE_ID": ident["feature_id"],
                        "FEATURE_IDS_ALL": [ident["feature_id"]],
                        "NAME": cn,
                        "INDEX": None,
                        "FORMULA": {
                            "formula_id": ident.get("formula_id"),
                            "formula": ident.get("formula_definition"),
                            "formula_version": ident.get("formula_version"),
                            "implementation_authority": ident.get("implementation_authority"),
                        },
                        "OHLCV_INPUTS": [],
                        "ALIASES": list(ident.get("legacy_names") or []),
                        "PRODUCERS": {"impl_refs": [ident.get("implementation_authority")], "write_sites": []},
                        "CONSUMERS": [{"consumer": c, "active": None} for c in (ident.get("consumer_bindings") or [])],
                        "CONFIG_KEYS": [],
                        "ACTIVE_VALUES": [],
                        "OVERRIDE_PATHS": [],
                        "PIT_STATUS": {"pit_class": ident.get("temporal_semantics"), "note": "identity-registry only (not vector member)"},
                        "REACHABILITY": {"in_canonical_vector": False},
                        "TEST_REFERENCE_HITS": _scan_tests(root, [cn]).get(cn) or [],
                        "CLOSURE_STATUS": {"code_status": "IDENTITY_ONLY_NOT_VECTOR"},
                        "IDENTITIES": [ident],
                        "MODEL_EXPOSURE": {},
                        "_vector_member": False,
                    }

        for n in CANONICAL_FEATURES:
            idx.rows[n]["_vector_member"] = True

        # ── materialize aliases: 1 target → by_alias · >1 → AMBIGUOUS (fail closed) ──
        # Row names are the primary key domain and always resolve to themselves; an
        # alias that equals a row name but points elsewhere is EXPOSED as shadowing.
        alias_name_shadowing: dict[str, list[str]] = {}
        for a, targets in alias_targets.items():
            t = sorted(x for x in targets if x and x in idx.rows)
            if not t:
                continue
            if a in idx.rows:
                others = [x for x in t if x != a]
                if others:
                    alias_name_shadowing[a] = others
                continue  # name precedence: never override a row key
            if len(t) == 1:
                idx.by_alias[a] = t[0]
            else:
                idx.by_alias_ambiguous[a] = t
        idx.meta["ontology_alias_collisions"] = ontology_alias_collisions
        idx.meta["alias_name_shadowing"] = alias_name_shadowing
        idx.meta["ambiguous_aliases"] = dict(idx.by_alias_ambiguous)

        return idx

    def resolve_name(self, q: str) -> Optional[str]:
        """Resolve a name/FEATURE_ID/alias to a row key.

        Row names (vector members AND identity-only shadow rows) resolve to
        themselves. Ambiguous aliases raise AmbiguousAliasError (fail closed).
        """
        if q in self.rows:
            return q
        if q in self.by_feature_id:
            return self.by_feature_id[q]
        if q in self.by_alias_ambiguous:
            raise AmbiguousAliasError(q, self.by_alias_ambiguous[q])
        if q in self.by_alias:
            return self.by_alias[q]
        # case-insensitive
        ql = q.lower()
        for k in self.rows:
            if k.lower() == ql:
                return k
        for k, v in self.by_feature_id.items():
            if k.lower() == ql:
                return v
        return None

    def get(self, q: str) -> Optional[dict]:
        name = self.resolve_name(q)  # may raise AmbiguousAliasError (fail closed)
        if name is None:
            return None
        return self.rows.get(name)

    def list_vector(self) -> list[dict]:
        return [r for r in self.rows.values() if r.get("_vector_member", True) and r.get("INDEX") is not None]

    def filter(
        self,
        *,
        pit: str | None = None,
        closure: str | None = None,
        search: str | None = None,
        vector_only: bool = True,
    ) -> list[dict]:
        rows = self.list_vector() if vector_only else list(self.rows.values())
        out = []
        for r in rows:
            if pit and (r.get("PIT_STATUS") or {}).get("pit_class_effective") != pit and (r.get("PIT_STATUS") or {}).get("pit_class") != pit:
                continue
            if closure and (r.get("CLOSURE_STATUS") or {}).get("code_status") != closure:
                continue
            if search:
                blob = json.dumps(r, default=str).lower()
                if search.lower() not in blob:
                    continue
            out.append(r)
        return sorted(out, key=lambda x: (x.get("INDEX") is None, x.get("INDEX") or 999, x.get("NAME") or ""))

    def summary(self) -> dict:
        vec = self.list_vector()
        from collections import Counter
        return {
            "meta": self.meta,
            "n_vector": len(vec),
            "n_rows_total": len(self.rows),
            "pit_histogram": dict(Counter((r.get("PIT_STATUS") or {}).get("pit_class_effective") for r in vec)),
            "closure_histogram": dict(Counter((r.get("CLOSURE_STATUS") or {}).get("code_status") for r in vec)),
            "n_with_config_keys": sum(1 for r in vec if r.get("CONFIG_KEYS")),
            "n_with_test_references": sum(1 for r in vec if r.get("TEST_REFERENCE_HITS")),
            "sources": self.sources,
        }


def _cfg_key_matches(feature: str, key: str | None) -> bool:
    """Token-segment match: the feature's full segment sequence must appear as a
    contiguous run of the key's underscore segments. Purely name-based ⇒ callers
    must tag results HEURISTIC."""
    if not key:
        return False
    segs = str(key).lower().split("_")
    f_segs = feature.lower().split("_")
    if len(f_segs) > len(segs):
        return False
    return any(segs[i : i + len(f_segs)] == f_segs for i in range(len(segs) - len(f_segs) + 1))


def _dep_has(dep: dict, name: str) -> bool:
    nodes = dep.get("nodes")
    if isinstance(nodes, dict):
        return name in nodes
    if isinstance(nodes, list):
        return any((n.get("name") or n.get("feature")) == name for n in nodes if isinstance(n, dict))
    return False


def _dig(cfg: dict, section: str, key: str) -> Any:
    if not cfg:
        return None
    sec = cfg.get(section)
    if isinstance(sec, dict) and key in sec:
        return sec[key]
    # params nested
    params = cfg.get("params") or {}
    if section == "params" and key in params:
        return params[key]
    if key in params:
        return params[key]
    return None


def _load_active_config_values(root: Path) -> dict:
    try:
        sys.path.insert(0, str(root / "src"))
        from config_layer.production_config import get_full_config_dict  # type: ignore
        return get_full_config_dict() or {}
    except Exception:
        # fallback: raw active json
        try:
            ver = (root / "configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip()
            p = root / "configs" / "production" / f"{ver}.json"
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}


@lru_cache(maxsize=1)
def _scan_tests_cached(root_s: str, names_t: tuple[str, ...]) -> dict:
    root = Path(root_s)
    names = list(names_t)
    out: dict[str, list[str]] = {n: [] for n in names}
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return out
    # precompile
    pats = {n: re.compile(rf"\b{re.escape(n)}\b") for n in names}
    for p in tests_root.rglob("test_*.py"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        for n, pat in pats.items():
            if pat.search(text):
                out[n].append(rel)
    # cap
    for n in out:
        out[n] = sorted(set(out[n]))[:25]
    return out


def _scan_tests(root: Path, names: Iterable[str]) -> dict:
    return _scan_tests_cached(str(root), tuple(names))


# ── presentation ─────────────────────────────────────────────────────────────

def _print_feature(row: dict, *, fields: list[str] | None = None) -> None:
    if fields:
        slim = {k: row.get(k) for k in fields if k in row}
        print(json.dumps(slim, indent=2, default=str))
        return
    # human-readable card
    print(f"══ {row.get('NAME')}  [{row.get('FEATURE_ID')}]  index={row.get('INDEX')}")
    f = row.get("FORMULA") or {}
    print(f"  FORMULA:     {f.get('formula_id')} — {f.get('formula')}")
    if f.get("ontology_id"):
        print(f"               ontology {f.get('ontology_id')} ({f.get('ontology_section')})")
    print(f"  OHLCV:       {row.get('OHLCV_INPUTS')}")
    print(f"  ALIASES:     {row.get('ALIASES')}")
    prod = row.get("PRODUCERS") or {}
    print(f"  PRODUCERS:   {prod.get('impl') or prod.get('impl_refs')}")
    if prod.get("write_sites"):
        print(f"               write_sites={prod['write_sites'][:3]}")
    cons = row.get("CONSUMERS") or []
    print(f"  CONSUMERS:   {len(cons)} → " + ", ".join(
        f"{c.get('consumer')}{'*' if c.get('active') else ''}" for c in cons[:8]
    ))
    ck = row.get("CONFIG_KEYS") or []
    print(f"  CONFIG KEYS: {len(ck)}")
    for c in ck[:6]:
        print(f"               {c.get('section') or ''}.{c.get('key')} [{c.get('verdict') or c.get('status')}]")
    av = row.get("ACTIVE_VALUES") or []
    if av:
        print(f"  ACTIVE VALS: " + "; ".join(f"{a.get('path')}={a.get('value')}" for a in av[:6]))
    ov = row.get("OVERRIDE_PATHS") or []
    if ov:
        print(f"  OVERRIDES:   " + ", ".join(o.get("name", str(o)) for o in ov[:6]))
    pit = row.get("PIT_STATUS") or {}
    print(f"  PIT:         {pit.get('pit_class_effective') or pit.get('pit_class')} — {pit.get('pit_note') or ''}")
    rch = row.get("REACHABILITY") or {}
    print(f"  REACH:       producer={rch.get('has_producer')} consumers={rch.get('n_consumers')} "
          f"cfg={rch.get('n_config_keys')} rr_active={rch.get('rr_model_dim_active')} "
          f"zone_mass={rch.get('zone_weight_mass')}")
    cl = row.get("CLOSURE_STATUS") or {}
    print(f"  CLOSURE:     {cl.get('code_status')}  doc={cl.get('doc_alignment')}")
    tests = row.get("TEST_REFERENCE_HITS") or []
    print(f"  TEST REFS:   {len(tests)} (textual, not behavioral coverage) → {', '.join(tests[:5])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Query the feature surface (read-only join of existing governance artifacts)."
    )
    ap.add_argument("--summary", action="store_true", help="index summary + surface gate status")
    ap.add_argument("--feature", "-f", metavar="NAME|FEATURE_ID", help="full card for one feature")
    ap.add_argument("--list", action="store_true", help="list vector features (compact)")
    ap.add_argument("--search", metavar="TEXT", help="substring search across joined rows")
    ap.add_argument("--pit", metavar="PIT_CLASS", help="filter by effective PIT class")
    ap.add_argument("--closure", metavar="STATUS", help="filter by code closure status")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON output")
    ap.add_argument(
        "--field",
        action="append",
        dest="fields",
        metavar="FIELD",
        help="with --feature: only these top-level fields (repeatable)",
    )
    ap.add_argument("--sources", action="store_true", help="print artifact source paths")
    args = ap.parse_args(argv)

    try:
        idx = FeatureSurfaceIndex.load()
    except Exception as e:
        print(f"ERROR loading feature surface index: {e}", file=sys.stderr)
        return 2

    if args.sources:
        print(json.dumps(idx.sources, indent=2))
        if not any([args.summary, args.feature, args.list, args.search, args.pit, args.closure]):
            return 0

    if args.summary or not any([args.feature, args.list, args.search, args.pit, args.closure, args.sources]):
        s = idx.summary()
        if args.json:
            print(json.dumps(s, indent=2, default=str))
        else:
            print("Feature Surface Index (read-only join)")
            print(f"  surface_status: {s['meta'].get('surface_status')}")
            print(f"  active_version: {s['meta'].get('active_version')}")
            print(f"  vector: {s['n_vector']}  rows_total: {s['n_rows_total']}")
            print(f"  pit: {s['pit_histogram']}")
            print(f"  closure: {s['closure_histogram']}")
            print(f"  rr_pit: {s['meta'].get('rr_pit_status')}  zone_pit: {s['meta'].get('zone_pit_status')}")
            print(f"  sources: {len(s['sources'])} artifacts")
        if not any([args.feature, args.list, args.search, args.pit, args.closure]):
            return 0

    if args.feature:
        try:
            row = idx.get(args.feature)
        except AmbiguousAliasError as e:
            print(f"AMBIGUOUS alias {e.alias!r} — candidates: {', '.join(e.candidates)}", file=sys.stderr)
            print("Query one of the candidates explicitly.", file=sys.stderr)
            return 1
        if not row:
            print(f"UNKNOWN feature: {args.feature}", file=sys.stderr)
            print("Hint: try --list or --search", file=sys.stderr)
            return 1
        if args.json or args.fields:
            if args.fields:
                print(json.dumps({k: row.get(k) for k in args.fields}, indent=2, default=str))
            else:
                print(json.dumps(row, indent=2, default=str))
        else:
            _print_feature(row, fields=args.fields)
        return 0

    # list / filter
    rows = idx.filter(pit=args.pit, closure=args.closure, search=args.search, vector_only=True)
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        print(f"{'idx':>3}  {'name':<28} {'FEATURE_ID':<40} {'PIT':<28} {'CLOSURE'}")
        for r in rows:
            print(
                f"{str(r.get('INDEX')):>3}  {r.get('NAME') or '':<28} "
                f"{(r.get('FEATURE_ID') or ''):<40} "
                f"{((r.get('PIT_STATUS') or {}).get('pit_class_effective') or ''):<28} "
                f"{(r.get('CLOSURE_STATUS') or {}).get('code_status')}"
            )
        print(f"({len(rows)} features)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
