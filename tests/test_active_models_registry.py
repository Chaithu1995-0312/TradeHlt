"""active_models.yaml v2.1 reachability — citation-class reference-resolution floor.

Classification (conventions.md §9 Executable-Invariant Scope Policy): this is NOT a semantic
YAML↔code invariant (that scope stays test_crt_state_invariants.py only). It is the sibling of
tests/test_doc_citations.py / tests/test_framework_registry.py: every pointer the v2.1
`reachability` / `optimization` / `evidence.conflicts` / `evidence.hypotheses` blocks declare
must RESOLVE (paths exist, F-ids/H-ids/framework-ids are registered, event types are real).
Nothing volatile is pinned. Drift evidence for why pointer rot matters: F-041.

Plus the §6.5 negative guard: no promotion/threshold field can enter an `optimization` block —
the registry describes tunability, it never grants authority.

Also links the registry to the ACTIVE_VERSION config (§4.0 branch-scoped truth): binary runtime
FLAGS must match live config values (test_runtime_flags_match_active_config) and every CRT
config_key must resolve to a CRTConfig field / active section (test_yaml_config_keys_exist_in_schema).
This is a yaml↔config check, still NOT a yaml↔code invariant, and deliberately pins FLAGS + key
existence only — never threshold VALUES (yaml documents code defaults; config holds tuned overrides).
"""
from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from config_layer.state_identity import CRTConfig
from events.event_fabric import EventType
from governance.framework_registry import valid_finding_ids

_REPO = Path(__file__).resolve().parents[1]
_YAML = _REPO / "active_models.yaml"
_NON_MODEL_KEYS = {"meta", "philosophy", "feature_lineage"}

_HYP_SEED = _REPO / "scripts" / "governance" / "seed_hypothesis_registry.py"
_HYP_PATH = _REPO / "data" / "hypothesis_registry.jsonl"
_FRAME_SEED = _REPO / "scripts" / "governance" / "seed_framework_registry.py"
_FRAME_PATH = _REPO / "data" / "framework_registry.jsonl"

# §6.5 authority-creep regression: these key patterns may never appear inside `optimization`.
_AUTHORITY_CREEP_RE = re.compile(r"promotion_requirements|min_delta|threshold", re.IGNORECASE)


@pytest.fixture(scope="module", autouse=True)
def _ensure_registries_seeded() -> None:
    """data/ is gitignored — reseed both sibling registries deterministically if absent."""
    for path, seed in ((_HYP_PATH, _HYP_SEED), (_FRAME_PATH, _FRAME_SEED)):
        if not path.exists():
            subprocess.run([sys.executable, str(seed)], check=True, cwd=_REPO)
        assert path.exists(), f"seed failed to produce {path}"


@pytest.fixture(scope="module")
def doc() -> dict:
    return yaml.safe_load(_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def models(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in _NON_MODEL_KEYS}


def _jsonl_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as fh:
        return {json.loads(line)["id"] for line in fh if line.strip()}


def _active_config() -> dict:
    """The config named by configs/production/ACTIVE_VERSION (branch-scoped truth, §4.0)."""
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    return json.loads((_REPO / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))


def test_schema_version_and_layers(doc: dict) -> None:
    assert doc["meta"]["schema_version"] == 2.3
    assert doc["meta"]["truth_schema"]["canonical_layers"] == ["intent", "runtime", "evidence", "status"]
    assert doc["meta"]["truth_schema"]["version"] == 2.0, (
        "the truth-LAYER schema stays 2.0 — v2.1/v2.2/v2.3 are file-format bumps only (conventions.md §9)"
    )
    # identity is a sub-block, not a new truth layer
    assert "identity" not in doc["meta"]["truth_schema"]["canonical_layers"]


def test_finding_ids_resolve(doc: dict, models: dict) -> None:
    """Every F-id in evidence.findings / evidence.conflicts / philosophy.authority.findings exists."""
    known = valid_finding_ids(_REPO / "docs" / "current-findings.md")
    assert known, "no F-NNN ids parsed from docs/current-findings.md"
    problems: list[str] = []
    cited: list[tuple[str, list]] = [
        (name, (entry.get("evidence") or {}).get(key) or [])
        for name, entry in models.items()
        for key in ("findings", "conflicts")
    ]
    cited.append(("philosophy", doc["philosophy"]["authority"].get("findings") or []))
    for name, fids in cited:
        problems.extend(f"{name}: unknown finding {fid}" for fid in fids if fid not in known)
    assert not problems, "\n".join(problems)


def test_hypothesis_ids_resolve(models: dict) -> None:
    """Every H-id in evidence.hypotheses exists in data/hypothesis_registry.jsonl (reseeded)."""
    known = _jsonl_ids(_HYP_PATH)
    problems = [
        f"{name}: unknown hypothesis {hid}"
        for name, entry in models.items()
        for hid in (entry.get("evidence") or {}).get("hypotheses") or []
        if hid not in known
    ]
    assert not problems, "\n".join(problems)


def test_machine_readable_sources_resolve(doc: dict) -> None:
    """meta.machine_readable_sources: generator + guard exist; path exists (post-reseed for data/)."""
    sources = doc["meta"]["machine_readable_sources"]
    assert sources, "meta.machine_readable_sources is empty"
    problems: list[str] = []
    for name, src in sources.items():
        for key in ("generator", "guard"):
            if not (_REPO / src[key]).exists():
                problems.append(f"{name}.{key}: missing {src[key]}")
        artifact = _REPO / src["path"]
        if not artifact.exists() and name != "findings_export":
            problems.append(f"{name}.path: missing {src['path']} (reseed fixture should have made it)")
        if name == "findings_export" and not artifact.exists():
            subprocess.run([sys.executable, str(_REPO / src["generator"])], check=True, cwd=_REPO)
            if not artifact.exists():
                problems.append(f"{name}.path: generator did not produce {src['path']}")
    assert not problems, "\n".join(problems)


def test_reachability_paths_resolve(models: dict) -> None:
    """Every reachability tests/topics path and telemetry emitter exists from repo root."""
    problems: list[str] = []
    for name, entry in models.items():
        reach = entry.get("reachability")
        if reach is None:
            problems.append(f"{name}: missing v2.1 reachability block")
            continue
        for key in ("tests", "topics"):
            for p in reach.get(key) or []:
                if not (_REPO / p).exists():
                    problems.append(f"{name}.reachability.{key}: missing {p}")
        for t in reach.get("telemetry") or []:
            if not (_REPO / t["emitter"]).exists():
                problems.append(f"{name}: telemetry emitter missing {t['emitter']}")
    assert not problems, "\n".join(problems)


def test_telemetry_semantic_contract(models: dict) -> None:
    """event_type is a real EventType; stream basename appears in the emitter source; the schema
    anchor's doc exists and carries the referenced §9 heading; purpose is non-empty.
    (Citation-class only — llm_questions content is deliberately NOT pinned.)"""
    valid_types = {e.value for e in EventType}
    problems: list[str] = []
    for name, entry in models.items():
        for t in (entry.get("reachability") or {}).get("telemetry") or []:
            if t["event_type"] not in valid_types:
                problems.append(f"{name}: {t['event_type']} not an EventType member")
            emitter = _REPO / t["emitter"]
            if emitter.exists():
                basename = Path(t["stream"]).name
                if basename not in emitter.read_text(encoding="utf-8"):
                    problems.append(f"{name}: stream {basename} not referenced in {t['emitter']}")
            doc_path, _, anchor = t["schema"].partition("#")
            schema_doc = _REPO / doc_path
            if not schema_doc.exists():
                problems.append(f"{name}: schema doc missing {doc_path}")
            elif anchor.startswith("94") and "### 9.4" not in schema_doc.read_text(encoding="utf-8"):
                problems.append(f"{name}: schema anchor §9.4 heading absent from {doc_path}")
            if not (t.get("purpose") or "").strip():
                problems.append(f"{name}: telemetry {t['event_type']} has empty purpose")
    assert not problems, "\n".join(problems)


def test_config_sections_are_active_config_keys(models: dict) -> None:
    """Every reachability/optimization config_sections entry is a top-level key of the config
    named by configs/production/ACTIVE_VERSION (branch-scoped truth, CLAUDE.md §4.0)."""
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = json.loads((_REPO / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, entry in models.items():
        for block in ("reachability", "optimization"):
            for section in (entry.get(block) or {}).get("config_sections") or []:
                if section not in cfg:
                    problems.append(f"{name}.{block}: {section!r} not a top-level key of {version}.json")
    assert not problems, "\n".join(problems)


def test_optimization_is_descriptive_only(models: dict) -> None:
    """§6.5 floor: authority disclaims, cites §6.5, and NO promotion/threshold key exists in the
    block (authority-creep regression); promotion_standard points at the M4 gate + PromotionManager."""
    problems: list[str] = []
    for name, entry in models.items():
        opt = entry.get("optimization")
        if opt is None:
            problems.append(f"{name}: missing v2.1 optimization block")
            continue
        authority = opt.get("authority", "")
        if not authority.startswith("none") or "§6.5" not in authority:
            problems.append(f"{name}: optimization.authority must start 'none' and cite §6.5")
        creep = [k for k in opt if _AUTHORITY_CREEP_RE.search(k)]
        if creep:
            problems.append(f"{name}: authority-creep keys in optimization: {creep}")
        std = opt.get("promotion_standard") or {}
        for role, expected in (("research", "src/research/qualification.py"),
                               ("production", "src/governance/promotion_manager.py")):
            if std.get(role) != expected:
                problems.append(f"{name}: promotion_standard.{role} must be {expected}")
            elif not (_REPO / expected).exists():
                problems.append(f"{name}: promotion_standard.{role} path missing: {expected}")
    assert not problems, "\n".join(problems)


def test_framework_ids_resolve(models: dict) -> None:
    """Every reachability.framework_ids entry exists in data/framework_registry.jsonl (reseeded)."""
    known = _jsonl_ids(_FRAME_PATH)
    problems = [
        f"{name}: unknown framework id {fid}"
        for name, entry in models.items()
        for fid in (entry.get("reachability") or {}).get("framework_ids") or []
        if fid not in known
    ]
    assert not problems, "\n".join(problems)


# The heuristic Gaussian runtime class ↔ its config `gaussian_impl` selector string.
_GAUSSIAN_ENGINE_IMPL = {"HeuristicGaussianEngine": "heuristic"}


def test_runtime_flags_match_active_config(doc: dict) -> None:
    """Binary runtime CLAIMS in the registry match the ACTIVE_VERSION config's live values.

    FLAGS ONLY — never numeric thresholds. The yaml documents CODE defaults while the config holds
    tuned overrides (e.g. retest_depth_max 0.25 vs 0.15), so value-equality on thresholds would be a
    false alarm; only these on/off + selector claims are genuine drift when they disagree. Sibling of
    test_config_sections_are_active_config_keys (which checks SECTION presence, not these flags)."""
    cfg = _active_config()
    er = cfg["engine_runner"]
    gaussian_engine = doc["gaussian"]["runtime"]["engine"]
    checks = [
        ("bitnet.enabled", doc["bitnet"]["runtime"]["enabled"], cfg["crt_engine"]["use_bitnet"]),
        ("zone_gate.zone_mode", doc["zone_gate"]["runtime"]["zone_mode"], er["zone_mode"]),
        ("zone_gate.registry_file", doc["zone_gate"]["runtime"]["registry_file"], er["zone_registry_path"]),
        ("gaussian.engine→impl", _GAUSSIAN_ENGINE_IMPL.get(gaussian_engine, gaussian_engine), er["gaussian_impl"]),
        ("rr_model.rr_fusion_active", doc["rr_model"]["runtime"]["rr_fusion_active"], er["rr_fusion"]["enabled"]),
    ]
    problems = [f"{label}: registry={yaml_v!r} != config={cfg_v!r}"
                for label, yaml_v, cfg_v in checks if yaml_v != cfg_v]
    assert not problems, "\n".join(problems)


def test_yaml_config_keys_exist_in_schema(doc: dict) -> None:
    """Every CRT detection.config_keys / thresholds key resolves to a CRTConfig field or an active
    config section key — catches a renamed/removed knob without pinning VALUES (§6.5 tunability)."""
    crt = doc["crt"]["runtime"]
    cfg = _active_config()
    resolvable = (
        {f.name for f in dataclasses.fields(CRTConfig)}
        | set(cfg.get("params") or {})
        | set(cfg.get("crt_engine") or {})
    )
    declared: set[str] = set((crt.get("thresholds") or {}).keys())
    for blk in (crt.get("detection") or {}).values():
        declared |= set(blk.get("config_keys") or [])
    missing = sorted(declared - resolvable)
    assert not missing, f"CRT registry config keys not in CRTConfig/params/crt_engine: {missing}"


# ─── feature_lineage block (OHLCV → formula → state → consumer → fusion weight) ───────────
_LINEAGE_ROLES = {"structural", "advisory", "unused"}
_LINEAGE_FUSION_WEIGHTS = {"crt:0.4", "gaussian:0.2", "zone:0.2_nonpivotal", "regime_routing", "inert:0"}


def test_feature_lineage_covers_all_canonical_features_in_order(doc: dict) -> None:
    """The lineage lists every CANONICAL_FEATURE exactly once, in schema order, indices 0..N-1."""
    from features.feature_schema import CANONICAL_FEATURES
    feats = doc["feature_lineage"]["features"]
    assert [f["index"] for f in feats] == list(range(len(CANONICAL_FEATURES))), "indices must be 0..37"
    assert tuple(f["name"] for f in feats) == tuple(CANONICAL_FEATURES), (
        "feature_lineage names must match CANONICAL_FEATURES order exactly (canonical spine)"
    )


def test_feature_lineage_fields_and_provenance_resolve(doc: dict) -> None:
    """Each row: role ∈ enum, fusion_weight ∈ enum, provenance.file exists; authority disclaimed."""
    fl = doc["feature_lineage"]
    assert fl["authority"] == "none", "feature_lineage is descriptive; authority must be none (§6.5)"
    assert (_REPO / fl["human_source"]).exists()
    assert (_REPO / fl["candle_geometry_primitive"]).exists()
    problems: list[str] = []
    for f in fl["features"]:
        if f["role"] not in _LINEAGE_ROLES:
            problems.append(f"{f['name']}: bad role {f['role']!r}")
        if f["fusion_weight"] not in _LINEAGE_FUSION_WEIGHTS:
            problems.append(f"{f['name']}: bad fusion_weight {f['fusion_weight']!r}")
        prov = (f.get("provenance") or {}).get("file")
        if not prov or not (_REPO / prov).exists():
            problems.append(f"{f['name']}: provenance file missing {prov!r}")
    assert not problems, "\n".join(problems)


def test_feature_lineage_role_counts_match(doc: dict) -> None:
    """The declared role_counts equal the actual per-row roll-up (no silent drift)."""
    fl = doc["feature_lineage"]
    from collections import Counter
    actual = Counter(f["role"] for f in fl["features"])
    assert dict(actual) == dict(fl["role_counts"]), f"role_counts {fl['role_counts']} != actual {dict(actual)}"


def test_feature_lineage_is_branch_scoped_to_active_config(doc: dict) -> None:
    """config: must name the active production version (branch-scoped truth, §4.0)."""
    version = (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    assert doc["feature_lineage"]["config"] == version


# ─── v2.3 identity (Exists ≠ Selected ≠ Enabled; mirror of registries; not loaders) ───────────
_IDENTITY_FAMILIES = ("gaussian", "zone_gate", "rr_model", "bitnet", "tradenet")
_IDENTITY_STATUS_ENUM = frozenset(
    {
        "absent",
        "selected_not_enabled",
        "selected_and_enabled",
        "enabled_without_checkpoint",
    }
)


def _active_version_file() -> str:
    return (_REPO / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()


def _load_json(rel: str) -> dict:
    path = _REPO / rel
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _cfg_lookup(cfg: dict, section: str, key: str):
    """Resolve dotted key under a top-level config section (e.g. rr_fusion.model_path)."""
    node = cfg.get(section)
    if node is None:
        return None
    parts = key.split(".")
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


def _registry_active_versions(reg: dict, *, per_instrument: bool = False) -> set[str] | dict[str, str]:
    """Extract active version id(s) from a model registry JSON object."""
    if per_instrument:
        amap = reg.get("__active__")
        if isinstance(amap, dict) and amap:
            return {str(k): str(v) for k, v in amap.items()}
        out: dict[str, str] = {}
        for ver, entry in reg.items():
            if ver.startswith("__") or not isinstance(entry, dict):
                continue
            if entry.get("active") and entry.get("instrument"):
                out[str(entry["instrument"])] = str(entry.get("version") or ver)
        return out
    actives = [
        str(entry.get("version") or ver)
        for ver, entry in reg.items()
        if not str(ver).startswith("__") and isinstance(entry, dict) and entry.get("active")
    ]
    return set(actives)


def _artifact_path_from_registry(reg: dict, version: str) -> Path | None:
    entry = reg.get(version) or {}
    mf = entry.get("model_file")
    if not mf:
        return None
    p = Path(str(mf).replace("\\", "/"))
    if not p.is_absolute():
        p = _REPO / p
    return p


def _selection_version(ident: dict) -> str | None:
    sel = ident.get("selection") or {}
    if not isinstance(sel, dict):
        return None
    if "version" in sel:
        v = sel["version"]
        return None if v is None else str(v)
    return None


def _selection_by_instrument(ident: dict) -> dict:
    sel = ident.get("selection") or {}
    if not isinstance(sel, dict):
        return {}
    bi = sel.get("by_instrument")
    return bi if isinstance(bi, dict) else {}


def _execution(ident: dict) -> dict:
    ex = ident.get("execution")
    return ex if isinstance(ex, dict) else {}


def _derive_identity_status(ident: dict) -> str:
    """Mechanical rollup: Exists/Selected/Enabled (not free prose)."""
    ex = _execution(ident)
    enabled = bool(ex.get("runtime_enabled"))
    uses_ckpt = bool(ex.get("uses_trained_checkpoint"))
    sel = ident.get("selection") or {}
    has_version = False
    if isinstance(sel, dict):
        if sel.get("version") is not None:
            has_version = True
        bi = sel.get("by_instrument")
        if isinstance(bi, dict) and any(
            isinstance(e, dict) and e.get("version") for e in bi.values()
        ):
            has_version = True
    if not has_version and not enabled:
        return "absent"
    if has_version and not enabled:
        return "selected_not_enabled"
    if enabled and not uses_ckpt:
        return "enabled_without_checkpoint"
    if has_version and enabled and uses_ckpt:
        return "selected_and_enabled"
    return "selected_and_enabled" if enabled else "selected_not_enabled"


def test_identity_required_families_present(models: dict) -> None:
    """v2.3: identity has selection + execution.runtime_enabled + identity_status."""
    problems: list[str] = []
    for name in _IDENTITY_FAMILIES:
        if name not in models:
            problems.append(f"missing top-level family {name!r}")
            continue
        ident = models[name].get("identity")
        if not isinstance(ident, dict):
            problems.append(f"{name}: missing identity block")
            continue
        if ident.get("authority") != "mirror_of_registry":
            problems.append(f"{name}: identity.authority must be 'mirror_of_registry' (not promote)")
        if not ident.get("registry"):
            problems.append(f"{name}: identity.registry path required")
        elif not (_REPO / ident["registry"]).exists():
            problems.append(f"{name}: identity.registry missing on disk: {ident['registry']}")
        if "selection" not in ident:
            problems.append(f"{name}: identity.selection required (v2.3; was active)")
        if "spine_binding" in ident:
            problems.append(f"{name}: spine_binding is retired — use execution")
        if "active" in ident and "selection" not in ident:
            problems.append(f"{name}: active is retired — use selection")
        ex = _execution(ident)
        if "runtime_enabled" not in ex:
            problems.append(f"{name}: execution.runtime_enabled required")
        st = ident.get("identity_status")
        if st not in _IDENTITY_STATUS_ENUM:
            problems.append(f"{name}: identity_status must be one of {_IDENTITY_STATUS_ENUM}, got {st!r}")
        else:
            derived = _derive_identity_status(ident)
            if st != derived:
                problems.append(
                    f"{name}: identity_status={st!r} != derived={derived!r} "
                    f"(selection/execution inconsistent)"
                )
        rb = ident.get("runtime_binding") or {}
        if not rb.get("config_version"):
            problems.append(f"{name}: runtime_binding.config_version required")
    assert not problems, "\n".join(problems)


def test_identity_r1_registry_selection_mirror(models: dict) -> None:
    """R1: identity.selection.version matches registry active (or by_instrument map)."""
    problems: list[str] = []

    zg_id = models["zone_gate"]["identity"]
    zg_reg = _load_json(zg_id["registry"])
    zg_actives = _registry_active_versions(zg_reg)
    zg_ver = _selection_version(zg_id)
    if zg_ver not in zg_actives:
        problems.append(
            f"zone_gate: selection.version={zg_ver!r} not in registry actives {zg_actives}"
        )

    rr_id = models["rr_model"]["identity"]
    rr_reg = _load_json(rr_id["registry"])
    rr_actives = _registry_active_versions(rr_reg)
    rr_ver = _selection_version(rr_id)
    if rr_ver not in rr_actives:
        problems.append(
            f"rr_model: selection.version={rr_ver!r} not in registry actives {rr_actives}"
        )

    tn_id = models["tradenet"]["identity"]
    tn_reg = _load_json(tn_id["registry"])
    tn_actives = _registry_active_versions(tn_reg)
    tn_ver = _selection_version(tn_id)
    if tn_ver not in tn_actives:
        problems.append(
            f"tradenet: selection.version={tn_ver!r} not in registry actives {tn_actives}"
        )

    g_id = models["gaussian"]["identity"]
    g_reg = _load_json(g_id["registry"])
    g_map = _registry_active_versions(g_reg, per_instrument=True)
    assert isinstance(g_map, dict)
    g_by = _selection_by_instrument(g_id)
    if not g_by:
        problems.append("gaussian: selection.by_instrument required")
    else:
        for inst, entry in g_by.items():
            ver = entry.get("version") if isinstance(entry, dict) else entry
            if g_map.get(inst) != ver:
                problems.append(
                    f"gaussian[{inst}]: selection version={ver!r} != registry __active__ "
                    f"{g_map.get(inst)!r}"
                )

    bn_id = models["bitnet"]["identity"]
    bn_reg = _load_json(bn_id["registry"])
    bn_actives = _registry_active_versions(bn_reg)
    bn_ver = _selection_version(bn_id)
    if bn_ver is None:
        if bn_actives:
            problems.append(
                f"bitnet: selection.version is null but registry has active {bn_actives!r}"
            )
        # Catalog may list entries with active:false — that is Exists without Selected.
    else:
        if bn_ver not in bn_actives:
            problems.append(
                f"bitnet: selection.version={bn_ver!r} not in registry actives {bn_actives}"
            )

    assert not problems, "\n".join(problems)


def test_identity_r2_how_path_ref_parity(models: dict) -> None:
    """R2: when execution.runtime_enabled and how_path_ref set, expected_value == production path."""
    cfg = _active_config()
    problems: list[str] = []
    for name in _IDENTITY_FAMILIES:
        ident = models[name]["identity"]
        enabled = bool(_execution(ident).get("runtime_enabled"))
        href = ident.get("how_path_ref")
        if not enabled:
            continue
        if not href:
            if name == "gaussian":
                continue
            problems.append(f"{name}: runtime_enabled but how_path_ref missing")
            continue
        section = href["config_section"]
        key = href["config_key"]
        expected = href["expected_value"]
        actual = _cfg_lookup(cfg, section, key)
        if actual != expected:
            problems.append(
                f"{name}: how_path_ref expected {expected!r} != config {section}.{key}={actual!r}"
            )
    rr_href = models["rr_model"]["identity"].get("how_path_ref") or {}
    if rr_href:
        actual = _cfg_lookup(cfg, rr_href["config_section"], rr_href["config_key"])
        if actual is not None and actual != rr_href["expected_value"]:
            problems.append(
                f"rr_model: how_path_ref {rr_href['expected_value']!r} != config {actual!r} "
                f"(even when runtime_enabled=false the documented path must match HOW)"
            )
    assert not problems, "\n".join(problems)


def test_identity_r3_runtime_binding_config_version(models: dict) -> None:
    """R3: identity.runtime_binding.config_version == configs/production/ACTIVE_VERSION."""
    active = _active_version_file()
    problems = [
        f"{name}: runtime_binding.config_version="
        f"{(models[name]['identity'].get('runtime_binding') or {}).get('config_version')!r} "
        f"!= ACTIVE_VERSION {active!r}"
        for name in _IDENTITY_FAMILIES
        if (models[name]["identity"].get("runtime_binding") or {}).get("config_version") != active
    ]
    assert not problems, "\n".join(problems)


def test_identity_r4_artifact_when_uses_trained_checkpoint(models: dict) -> None:
    """R4: if uses_trained_checkpoint, selected registry model_file must exist on disk."""
    problems: list[str] = []
    for name in _IDENTITY_FAMILIES:
        ident = models[name]["identity"]
        ex = _execution(ident)
        if not ex.get("uses_trained_checkpoint"):
            continue
        reg = _load_json(ident["registry"])
        versions: list[str] = []
        v = _selection_version(ident)
        if v:
            versions = [v]
        for entry in _selection_by_instrument(ident).values():
            if isinstance(entry, dict) and entry.get("version"):
                versions.append(str(entry["version"]))
        if not versions:
            problems.append(f"{name}: uses_trained_checkpoint but no selection.version")
            continue
        for ver in versions:
            art = _artifact_path_from_registry(reg, ver)
            if art is None:
                href = ident.get("how_path_ref") or {}
                if href.get("expected_value"):
                    art = _REPO / href["expected_value"]
            if art is None or not art.exists():
                problems.append(f"{name}: artifact missing for version {ver!r} path={art}")
    assert not problems, "\n".join(problems)


def test_identity_no_threshold_authority_creep(models: dict) -> None:
    """identity must not carry threshold/weight/promote keys (HOW/CODE own those)."""
    banned = re.compile(
        r"threshold|weight_|promote|min_delta|top_k|cluster_min|model_path(?!_ref)",
        re.IGNORECASE,
    )
    problems: list[str] = []
    for name in _IDENTITY_FAMILIES:
        ident = dict(models[name]["identity"] or {})
        ident.pop("how_path_ref", None)
        for k in ident.keys():
            if banned.search(k) and k not in ("authority",):
                if any(x in k.lower() for x in ("threshold", "weight_", "promote", "min_delta", "top_k")):
                    problems.append(f"{name}: banned identity key {k!r}")
    assert not problems, "\n".join(problems)


def test_identity_runtime_enabled_matches_how_flags(models: dict, doc: dict) -> None:
    """execution.runtime_enabled agrees with HOW flags (Exists≠Selected≠Enabled)."""
    cfg = _active_config()
    er = cfg["engine_runner"]
    checks = [
        ("bitnet", _execution(models["bitnet"]["identity"]).get("runtime_enabled"), cfg["crt_engine"]["use_bitnet"]),
        ("rr_model", _execution(models["rr_model"]["identity"]).get("runtime_enabled"), er["rr_fusion"]["enabled"]),
        ("zone_gate", _execution(models["zone_gate"]["identity"]).get("runtime_enabled"), True),
        ("tradenet", _execution(models["tradenet"]["identity"]).get("runtime_enabled"), False),
        (
            "gaussian.live_impl",
            _execution(models["gaussian"]["identity"]).get("live_impl"),
            er["gaussian_impl"],
        ),
    ]
    problems = [
        f"{label}: identity={iv!r} != expected={ev!r}" for label, iv, ev in checks if iv != ev
    ]
    if er["gaussian_impl"] == "heuristic":
        if _execution(models["gaussian"]["identity"]).get("uses_trained_checkpoint"):
            problems.append("gaussian: heuristic impl requires uses_trained_checkpoint=false")
    # selected_not_enabled examples must not auto-enable
    if _execution(models["rr_model"]["identity"]).get("runtime_enabled"):
        problems.append("rr_model must remain runtime_enabled=false (selected ≠ enabled)")
    assert not problems, "\n".join(problems)
