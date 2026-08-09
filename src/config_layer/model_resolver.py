"""
model_resolver.py — resolve family → registry active → artifact (+ WHO identity parity).

EngineRunner and loaders obtain ``ResolvedModel`` from here. They must not construct
``models/…`` strings themselves for resolution.

Authority:
  - Operational selection: models/*_registry.json (promote)
  - Layout: ModelPaths
  - WHO identity: active_models.yaml ``identity`` blocks (mirror — must agree)
  - HOW: optional how_path must match resolved artifact when require_how_match

Does NOT own thresholds, fusion weights, or enablement switches.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from config_layer.model_paths import ModelPaths

logger = logging.getLogger(__name__)

# Repo root: src/config_layer/model_resolver.py → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_MODELS_YAML = _REPO_ROOT / "active_models.yaml"

# Resolver family name → active_models.yaml top-level key
_IDENTITY_YAML_KEY: dict[str, str] = {
    "zone_gate": "zone_gate",
    "rr": "rr_model",
    "rr_fusion": "rr_model",
    "gaussian": "gaussian",
    "bitnet": "bitnet",
    "tradenet": "tradenet",
}

# Resolver family → version-registry path on ModelPaths
_REGISTRY_PATH: dict[str, Path] = {
    "zone_gate": ModelPaths.ZONE_GATE_VERSION_REGISTRY,
    "rr": ModelPaths.RR_REGISTRY,
    "rr_fusion": ModelPaths.RR_REGISTRY,
    "gaussian": ModelPaths.GAUSSIAN_REGISTRY,
    "bitnet": ModelPaths.BITNET_REGISTRY,
    "tradenet": ModelPaths.TRADENET_REGISTRY,
}


@dataclass(frozen=True)
class ResolvedModel:
    """Immutable resolution result for one model family."""

    family: str
    version: Optional[str]
    registry_path: Path
    artifact_path: Optional[Path]
    instrument: Optional[str] = None
    spine_wired: bool = False
    uses_trained_checkpoint: bool = False
    feature_schema_dim: Optional[int] = None
    identity_parity: bool = False
    how_path: Optional[Path] = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def require_artifact(self) -> Path:
        if self.artifact_path is None or not self.artifact_path.exists():
            raise RuntimeError(
                f"ResolvedModel[{self.family}]: artifact missing "
                f"version={self.version!r} path={self.artifact_path}"
            )
        return self.artifact_path


class ModelResolveError(RuntimeError):
    """Fail-closed resolution error (registry / identity / HOW mismatch)."""


def _norm(p: Path | str | None, *, repo_root: Path) -> Optional[Path]:
    if p is None:
        return None
    path = Path(str(p).replace("\\", "/"))
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    return path


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ModelResolveError(f"cannot read registry {path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _load_identity_doc(repo_root: Path) -> dict:
    path = repo_root / "active_models.yaml"
    if not path.exists():
        return {}
    try:
        import yaml  # local — tests already depend on PyYAML via active_models
    except ImportError as exc:
        raise ModelResolveError("PyYAML required to load active_models.yaml identity") from exc
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}


def _registry_active_version(
    reg: dict,
    *,
    instrument: Optional[str] = None,
    per_instrument: bool = False,
) -> Optional[str]:
    if per_instrument:
        amap = reg.get("__active__")
        if isinstance(amap, dict) and instrument and instrument in amap:
            return str(amap[instrument])
        if isinstance(amap, dict) and amap:
            # no instrument: first map value (deterministic sorted)
            return str(amap[sorted(amap.keys())[0]])
        # fall back to entry-level active + instrument
        matches = [
            str(e.get("version") or ver)
            for ver, e in reg.items()
            if not str(ver).startswith("__")
            and isinstance(e, dict)
            and e.get("active")
            and (instrument is None or e.get("instrument") == instrument)
        ]
        return matches[0] if matches else None

    for ver, e in reg.items():
        if str(ver).startswith("__") or not isinstance(e, dict):
            continue
        if e.get("active"):
            return str(e.get("version") or ver)
    return None


def _artifact_from_entry(reg: dict, version: str, *, repo_root: Path) -> Optional[Path]:
    entry = reg.get(version) or {}
    if not isinstance(entry, dict):
        return None
    mf = entry.get("model_file")
    if not mf:
        return None
    return _norm(str(mf), repo_root=repo_root)


def _identity_selection_block(ident: dict) -> Any:
    """v2.3 ``selection`` with v2.2 ``active`` fallback."""
    if "selection" in ident:
        return ident.get("selection")
    return ident.get("active")  # v2.2 legacy


def _identity_execution_block(ident: dict) -> dict:
    """v2.3 ``execution`` with v2.2 ``spine_binding`` fallback."""
    ex = ident.get("execution")
    if isinstance(ex, dict):
        return ex
    sb = ident.get("spine_binding")
    if isinstance(sb, dict):
        # map wired → runtime_enabled
        out = dict(sb)
        if "runtime_enabled" not in out and "wired" in out:
            out["runtime_enabled"] = bool(out["wired"])
        return out
    return {}


def _identity_selected_version(ident: dict, *, instrument: Optional[str]) -> Optional[str]:
    """
    Read selected version from identity (v2.3 selection / v2.2 active).

    Shapes:
      selection: {version: "x", ...}
      selection: {by_instrument: {ETHUSDT: {version: ...}}}
      selection: {version: null}  → None
      legacy active: same shapes or bare per-instrument map
    """
    sel = _identity_selection_block(ident)
    if sel is None:
        return None
    if isinstance(sel, str):
        return sel
    if not isinstance(sel, dict):
        return None
    # explicit null version
    if "version" in sel and sel["version"] is None and "by_instrument" not in sel:
        return None
    if "version" in sel and sel["version"] is not None:
        return str(sel["version"])
    by_inst = sel.get("by_instrument")
    if isinstance(by_inst, dict):
        if instrument and instrument in by_inst:
            entry = by_inst[instrument]
            if isinstance(entry, dict):
                v = entry.get("version")
                return str(v) if v is not None else None
            return str(entry) if entry is not None else None
        for _k, entry in sorted(by_inst.items()):
            if isinstance(entry, dict) and entry.get("version"):
                return str(entry["version"])
        return None
    # v2.2 bare per-instrument map under active (keys look like instruments)
    if "version" not in sel and all(isinstance(v, (dict, str)) for v in sel.values()):
        if instrument and instrument in sel:
            entry = sel[instrument]
            if isinstance(entry, dict):
                v = entry.get("version")
                return str(v) if v is not None else None
            return str(entry)
        for _k, entry in sorted(sel.items()):
            if isinstance(entry, dict) and entry.get("version"):
                return str(entry["version"])
    return None


def _identity_feature_schema_dim(ident: dict, *, instrument: Optional[str]) -> Optional[int]:
    sel = _identity_selection_block(ident)
    if not isinstance(sel, dict):
        return None
    if "feature_schema_dim" in sel and sel["feature_schema_dim"] is not None:
        return int(sel["feature_schema_dim"])
    by_inst = sel.get("by_instrument") if isinstance(sel.get("by_instrument"), dict) else None
    if by_inst is None and "version" not in sel:
        by_inst = sel  # v2.2 bare map
    if isinstance(by_inst, dict):
        key = instrument if instrument and instrument in by_inst else None
        if key is None and by_inst:
            key = sorted(by_inst.keys())[0]
        if key is not None:
            entry = by_inst[key]
            if isinstance(entry, dict) and entry.get("feature_schema_dim") is not None:
                return int(entry["feature_schema_dim"])
    return None


def resolve_model(
    family: str,
    *,
    instrument: Optional[str] = None,
    how_path: str | Path | None = None,
    require_artifact: bool = False,
    require_how_match: bool = False,
    require_identity_parity: bool = True,
    repo_root: Path | None = None,
) -> ResolvedModel:
    """
    Resolve a model family to its registry-active artifact.

    Parameters
    ----------
    family :
        One of zone_gate | rr | rr_fusion | gaussian | bitnet | tradenet.
    instrument :
        Optional instrument key (gaussian ``__active__`` map).
    how_path :
        Production config path claim; when ``require_how_match`` and set, must
        equal the resolved artifact path (normalized).
    require_artifact :
        If True, missing artifact raises ModelResolveError.
    require_how_match :
        If True and how_path set, HOW must equal artifact (ZoneGate spine path).
    require_identity_parity :
        If True and active_models.yaml has identity for this family, version
        must match registry active (WHO mirror).
    """
    root = (repo_root or _REPO_ROOT).resolve()
    fam = family.strip().lower()
    if fam not in _REGISTRY_PATH:
        raise ModelResolveError(
            f"unknown model family {family!r}; "
            f"expected one of {sorted(_REGISTRY_PATH)}"
        )

    reg_rel = _REGISTRY_PATH[fam]
    reg_path = _norm(reg_rel, repo_root=root)
    assert reg_path is not None
    reg = _load_json(reg_path)

    per_inst = fam == "gaussian"
    version = _registry_active_version(reg, instrument=instrument, per_instrument=per_inst)

    artifact: Optional[Path] = None
    if version:
        artifact = _artifact_from_entry(reg, version, repo_root=root)

    # Identity (WHO) — optional file, parity when present
    identity_parity = False
    spine_wired = False
    uses_ckpt = False
    schema_dim: Optional[int] = None
    yaml_key = _IDENTITY_YAML_KEY[fam]
    ident: dict = {}
    try:
        doc = _load_identity_doc(root)
        entry = doc.get(yaml_key) or {}
        if isinstance(entry, dict):
            ident = entry.get("identity") or {}
    except ModelResolveError:
        if require_identity_parity:
            raise
        ident = {}

    if ident:
        ex = _identity_execution_block(ident)
        spine_wired = bool(ex.get("runtime_enabled", ex.get("wired", False)))
        uses_ckpt = bool(ex.get("uses_trained_checkpoint", False))
        id_ver = _identity_selected_version(ident, instrument=instrument)
        if require_identity_parity and id_ver is not None and version is not None:
            if id_ver != version:
                raise ModelResolveError(
                    f"identity/registry version mismatch for {fam}: "
                    f"identity.selection={id_ver!r} registry={version!r}"
                )
            identity_parity = True
        elif require_identity_parity and id_ver is None and version is None:
            identity_parity = True  # bitnet empty both sides
        elif require_identity_parity and id_ver is None and version is not None:
            if fam != "bitnet":
                raise ModelResolveError(
                    f"identity.selection.version is null but registry has active "
                    f"{version!r} for {fam}"
                )
            identity_parity = True
        schema_dim = _identity_feature_schema_dim(ident, instrument=instrument)

    how_n = _norm(how_path, repo_root=root) if how_path is not None else None

    if require_how_match and how_n is not None and artifact is not None:
        if how_n != artifact:
            raise ModelResolveError(
                f"HOW path diverges from registry-active artifact for {fam}: "
                f"how={how_n} artifact={artifact}"
            )

    if require_artifact:
        if artifact is None or not artifact.exists():
            raise ModelResolveError(
                f"artifact required but missing for {fam} version={version!r} path={artifact}"
            )

    return ResolvedModel(
        family=fam,
        version=version,
        registry_path=reg_path,
        artifact_path=artifact,
        instrument=instrument,
        spine_wired=spine_wired,
        uses_trained_checkpoint=uses_ckpt,
        feature_schema_dim=schema_dim,
        identity_parity=identity_parity,
        how_path=how_n,
        meta={
            "registry_relative": str(reg_rel).replace("\\", "/"),
            "yaml_key": yaml_key,
            "identity_present": bool(ident),
        },
    )


def resolve_zone_gate_runtime(
    how_path: str | Path | None = None,
    *,
    repo_root: Path | None = None,
) -> ResolvedModel:
    """
    Spine helper: resolve ZoneGate with fail-closed artifact + HOW parity.

    When ``how_path`` is omitted, uses ModelPaths.ZONE_GATE_RUNTIME_ALIAS and still
    requires registry-active model_file to match that alias.
    """
    root = (repo_root or _REPO_ROOT).resolve()
    default = _norm(ModelPaths.ZONE_GATE_RUNTIME_ALIAS, repo_root=root)
    path = how_path if how_path is not None else default
    return resolve_model(
        "zone_gate",
        how_path=path,
        require_artifact=True,
        require_how_match=True,
        require_identity_parity=True,
        repo_root=root,
    )


# ─────────────────────────────────────────────────────────────────────────────
# READ-ONLY ENUMERATION (Research Runtime Step 1)
#
# `resolve_model` answers "which version does production run?" — exactly one per
# family. Research needs the complement: "which versions EXIST?" — so a benchmark can
# rank the selected model against its alternatives.
#
# Strictly read-only and non-authoritative:
#   * never writes a registry, never reaches promotion;
#   * `selected` is computed by the SAME `_registry_active_version` the trading path
#     uses, so the research label cannot drift from what production actually loads;
#   * a missing artifact is REPORTED (`artifact_exists=False`), never raised — an
#     unloadable checkpoint is an implementation-validation result, not a crash;
#   * identity parity is REPORTED, not enforced — a non-selected version by definition
#     does not match `active_models.yaml` identity, and that is not an error here.
#
# Enumerating a version grants no authority to run it in the spine: swapping a
# non-selected model into live fusion still requires the deferred resolution
# inversion (ModelSelectionPolicy -> EngineRunner). See CLAUDE.md §6.5.
# ─────────────────────────────────────────────────────────────────────────────

# Registry meta keys are shape-distinguished, not name-distinguished: a real entry is a
# dict carrying `model_file`. That excludes `__active__` (dict of instruments),
# `_schema_v4_note` and `canonical_schema_version_at_stamp` (strings) without hardcoding
# their names, so a new meta key cannot masquerade as a model version.
def _is_model_entry(key: str, entry: Any) -> bool:
    return (
        not str(key).startswith("__")
        and isinstance(entry, dict)
        and bool(entry.get("model_file"))
    )


def _declared_feature_dim(entry: Mapping[str, Any]) -> Optional[int]:
    """Feature width the artifact was TRAINED against, however the family declares it."""
    n = entry.get("n_features")
    if isinstance(n, int):
        return n
    for key in ("feature_order", "feature_schema"):
        seq = entry.get(key)
        if isinstance(seq, (list, tuple)):
            return len(seq)
    return None


@dataclass(frozen=True)
class RegistryEntry:
    """One version row in a model registry. Descriptive; carries no authority."""

    family: str
    version: str
    registry_path: Path
    artifact_path: Optional[Path]
    artifact_exists: bool
    selected: bool                       # == the version `resolve_model` would return
    lifecycle: str                       # production | unspecified (Step 3 populates the rest)
    instrument: Optional[str] = None
    declared_feature_dim: Optional[int] = None
    trained_at: Optional[str] = None
    meta: Mapping[str, Any] = field(default_factory=dict)


def list_model_families() -> list[str]:
    """Every resolvable family, deterministically ordered."""
    return sorted(_REGISTRY_PATH)


def enumerate_versions(
    family: str,
    *,
    instrument: Optional[str] = None,
    repo_root: Path | None = None,
) -> list[RegistryEntry]:
    """All versions in a family's registry, sorted by version (deterministic).

    `instrument` only affects which row is flagged `selected` for per-instrument
    families (gaussian); it never filters the enumeration.
    """
    root = (repo_root or _REPO_ROOT).resolve()
    fam = family.strip().lower()
    if fam not in _REGISTRY_PATH:
        raise ModelResolveError(
            f"unknown model family {family!r}; expected one of {sorted(_REGISTRY_PATH)}"
        )

    reg_path = _norm(_REGISTRY_PATH[fam], repo_root=root)
    assert reg_path is not None
    reg = _load_json(reg_path)
    active = _registry_active_version(
        reg, instrument=instrument, per_instrument=(fam == "gaussian")
    )

    rows: list[RegistryEntry] = []
    for key, entry in reg.items():
        if not _is_model_entry(key, entry):
            continue
        version = str(entry.get("version") or key)
        artifact = _artifact_from_entry(reg, key, repo_root=root)
        lifecycle = entry.get("lifecycle")
        rows.append(
            RegistryEntry(
                family=fam,
                version=version,
                registry_path=reg_path,
                artifact_path=artifact,
                artifact_exists=bool(artifact and artifact.exists()),
                selected=(active is not None and version == active),
                lifecycle=str(lifecycle) if lifecycle else (
                    "production" if version == active else "unspecified"
                ),
                instrument=entry.get("instrument"),
                declared_feature_dim=_declared_feature_dim(entry),
                trained_at=entry.get("trained_at"),
                meta={"registry_key": str(key)},
            )
        )
    return sorted(rows, key=lambda r: r.version)


def enumerate_all(
    *,
    repo_root: Path | None = None,
) -> dict[str, list[RegistryEntry]]:
    """Full discovery surface: every family -> every version. The research matrix axis."""
    return {fam: enumerate_versions(fam, repo_root=repo_root) for fam in list_model_families()}


def resolve_version(
    family: str,
    version: str,
    *,
    instrument: Optional[str] = None,
    repo_root: Path | None = None,
) -> ResolvedModel:
    """Resolve an EXPLICIT version — including non-selected ones — for standalone scoring.

    Unlike `resolve_model` this does not consult `active_models.yaml` to CHOOSE anything;
    identity parity is computed as an observation (`identity_parity` is True only when
    the requested version happens to be the identity-selected one).
    """
    root = (repo_root or _REPO_ROOT).resolve()
    fam = family.strip().lower()
    if fam not in _REGISTRY_PATH:
        raise ModelResolveError(
            f"unknown model family {family!r}; expected one of {sorted(_REGISTRY_PATH)}"
        )

    reg_path = _norm(_REGISTRY_PATH[fam], repo_root=root)
    assert reg_path is not None
    reg = _load_json(reg_path)

    reg_key = None
    for key, entry in reg.items():
        if _is_model_entry(key, entry) and str(entry.get("version") or key) == str(version):
            reg_key = key
            break
    if reg_key is None:
        raise ModelResolveError(
            f"version {version!r} not found in {fam} registry {reg_path}; "
            f"known: {[r.version for r in enumerate_versions(fam, repo_root=root)]}"
        )

    entry = reg[reg_key]
    artifact = _artifact_from_entry(reg, reg_key, repo_root=root)

    ident: dict = {}
    try:
        doc = _load_identity_doc(root)
        blk = doc.get(_IDENTITY_YAML_KEY[fam]) or {}
        if isinstance(blk, dict):
            ident = blk.get("identity") or {}
    except ModelResolveError:
        ident = {}   # identity is observational here — never fatal

    ex = _identity_execution_block(ident) if ident else {}
    id_ver = _identity_selected_version(ident, instrument=instrument) if ident else None

    return ResolvedModel(
        family=fam,
        version=str(version),
        registry_path=reg_path,
        artifact_path=artifact,
        instrument=instrument or entry.get("instrument"),
        spine_wired=bool(ex.get("runtime_enabled", ex.get("wired", False))),
        uses_trained_checkpoint=bool(ex.get("uses_trained_checkpoint", False)),
        feature_schema_dim=_declared_feature_dim(entry),
        identity_parity=(id_ver is not None and str(id_ver) == str(version)),
        how_path=None,
        meta={
            "registry_relative": str(_REGISTRY_PATH[fam]).replace("\\", "/"),
            "yaml_key": _IDENTITY_YAML_KEY[fam],
            "identity_present": bool(ident),
            "registry_key": str(reg_key),
            "explicit_version": True,
            "authority": "NONE",
        },
    )


__all__ = [
    "ResolvedModel",
    "ModelResolveError",
    "resolve_model",
    "resolve_zone_gate_runtime",
    # read-only enumeration (research)
    "RegistryEntry",
    "list_model_families",
    "enumerate_versions",
    "enumerate_all",
    "resolve_version",
]
