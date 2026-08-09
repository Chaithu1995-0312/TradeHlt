"""
production_bundle.py — the executable production state, as one immutable object.

WHY THIS EXISTS (Research Runtime Step 1b).
``resolve_model`` answers *which version would production load?* That is *Selected*.
It is NOT the same question as *which trained checkpoint actually reaches a decision?*
— that is *Enabled*. On the active patch the two genuinely diverge:

  * ``engine_runner.rr_fusion.enabled = false`` — a version resolves, but ``RRFusionLayer``
    is never constructed and base ``RREngine`` (a polarity formula, not the checkpoint)
    flows through instead (F-038).
  * TradeNet resolves a version but the fusion neural slot is unwired (F-005).
  * ``crt_engine.use_bitnet = false`` — the gate is inert on the active patch (F-004).

A benchmark that ranks alternatives against the *registry-selected* model would therefore
be comparing against something production does not execute. Research must compare against
the BUNDLE.

This is a READ-ONLY reconciliation of three existing authorities — it introduces none:

  * Registry ``__active__``            -> Selected   (operational authority: promote_*)
  * ``active_models.yaml`` identity    -> Enabled    (the v2.3 WHO mirror)
  * production config enable flags     -> Enabled    (effective, where a key governs)

Divergence between them is REPORTED (``divergences``), never raised and never silently
reconciled — CLAUDE.md §6.2 rule 3. ``execution_status`` reuses the v2.3 identity
vocabulary verbatim (absent | selected_not_enabled | selected_and_enabled |
enabled_without_checkpoint) rather than inventing a parallel one.

Grants no authority (§6.5): describing what executes is not permission to change it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from config_layer.model_resolver import (
    ModelResolveError,
    _declared_feature_dim,
    _load_identity_doc,
    list_model_families,
    resolve_model,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Resolver family -> active_models.yaml key (families may share one identity block:
# `rr` and `rr_fusion` both mirror `rr_model`).
_IDENTITY_KEY: dict[str, str] = {
    "zone_gate": "zone_gate",
    "rr": "rr_model",
    "rr_fusion": "rr_model",
    "gaussian": "gaussian",
    "bitnet": "bitnet",
    "tradenet": "tradenet",
}

# Production-config keys that GOVERN whether a family's checkpoint reaches decisions.
# Explicit and partial by design: a family absent here has no single governing switch,
# and we record None rather than inventing one (§6.5 — no silent defaults).
_CONFIG_ENABLE_KEY: dict[str, tuple[str, ...]] = {
    "rr_fusion": ("engine_runner", "rr_fusion", "enabled"),
    "bitnet": ("crt_engine", "use_bitnet"),
}

# v2.3 identity vocabulary — reused verbatim, not re-invented.
STATUS_ABSENT = "absent"
STATUS_SELECTED_NOT_ENABLED = "selected_not_enabled"
STATUS_SELECTED_AND_ENABLED = "selected_and_enabled"
STATUS_ENABLED_WITHOUT_CHECKPOINT = "enabled_without_checkpoint"


def derive_execution_status(*, selected: bool, enabled: bool) -> str:
    """Pure function of (Selected, Enabled) -> the v2.3 status token."""
    if selected and enabled:
        return STATUS_SELECTED_AND_ENABLED
    if selected and not enabled:
        return STATUS_SELECTED_NOT_ENABLED
    if not selected and enabled:
        return STATUS_ENABLED_WITHOUT_CHECKPOINT
    return STATUS_ABSENT


@dataclass(frozen=True)
class BundleMember:
    """One family's executable production state."""

    family: str
    selected_version: Optional[str]        # registry __active__ (WHAT would load)
    artifact_path: Optional[Path]
    artifact_exists: bool
    runtime_enabled: bool                  # declared: identity execution.runtime_enabled
    config_enabled: Optional[bool]         # effective: prod-config flag; None = no governing key
    config_enable_key: Optional[str]       # provenance for the above
    execution_status: str                  # v2.3 token, MECHANICALLY derived
    declared_identity_status: Optional[str]
    registry_feature_dim: Optional[int]    # the artifact's own declaration
    identity_feature_dim: Optional[int]    # active_models.yaml selection claim
    contested: bool = False                # derived status disagrees with declared
    divergences: tuple[str, ...] = ()

    @property
    def executes_checkpoint(self) -> bool:
        """True only when a selected checkpoint demonstrably reaches decisions.

        CONSERVATIVE ON CONFLICT: when the derived status disagrees with the declared
        identity status the answer is unknown, so this returns False rather than
        asserting execution we cannot confirm. Gaussian is the live example — the
        registry has a selected artifact that loads successfully, but none of its
        entries carry mu/sigma, so no learned parameter reaches the score (F-060).
        A registry+config derivation cannot observe that; identity encodes it. Per
        CLAUDE.md §6.2 rule 3 the conflict is surfaced, not silently resolved.
        """
        return self.execution_status == STATUS_SELECTED_AND_ENABLED and not self.contested


@dataclass(frozen=True)
class ProductionBundle:
    """Immutable snapshot of what production actually executes.

    This is the object research benchmarks AGAINST — not the registry.
    """

    active_version: str
    members: Mapping[str, BundleMember] = field(default_factory=dict)
    divergences: tuple[str, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

    def executing_families(self) -> tuple[str, ...]:
        return tuple(sorted(f for f, m in self.members.items() if m.executes_checkpoint))

    def selected_version(self, family: str) -> Optional[str]:
        m = self.members.get(family)
        return m.selected_version if m else None

    def executes(self, family: str) -> bool:
        m = self.members.get(family)
        return bool(m and m.executes_checkpoint)


def _config_enable_flag(cfg: Mapping[str, Any], path: tuple[str, ...]) -> Optional[bool]:
    node: Any = cfg
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    return bool(node) if isinstance(node, bool) else None


def load_production_bundle(
    *,
    repo_root: Path | None = None,
    active_version: str | None = None,
) -> ProductionBundle:
    """Read-only: reconcile registry + identity + production config into one snapshot.

    Never writes, never promotes, never raises on divergence.
    """
    root = (repo_root or _REPO_ROOT).resolve()

    # Tier-0 runtime truth (CLAUDE.md §4.0) — the config the bundle describes.
    from config_layer.production_config import get_active_version, get_full_config_dict

    version = active_version or get_active_version()
    try:
        cfg = get_full_config_dict(version) or {}
    except Exception as exc:                       # config unreadable -> recorded, not fatal
        logger.warning("production_bundle: cannot read config %s: %s", version, exc)
        cfg = {}

    identity_doc = {}
    try:
        identity_doc = _load_identity_doc(root)
    except ModelResolveError as exc:
        logger.warning("production_bundle: identity unavailable: %s", exc)

    members: dict[str, BundleMember] = {}
    bundle_divergences: list[str] = []

    for family in list_model_families():
        divergences: list[str] = []

        # ── Selected (registry) ────────────────────────────────────────────
        try:
            resolved = resolve_model(family, require_identity_parity=False, repo_root=root)
            selected_version = resolved.version
            artifact = resolved.artifact_path
            runtime_enabled = bool(resolved.spine_wired)
        except ModelResolveError as exc:
            divergences.append(f"registry resolution failed: {exc}")
            selected_version, artifact, runtime_enabled = None, None, False

        # ── Enabled (identity, declared) ───────────────────────────────────
        ident = {}
        blk = identity_doc.get(_IDENTITY_KEY[family]) or {}
        if isinstance(blk, dict):
            ident = blk.get("identity") or {}
        declared_status = ident.get("identity_status") if isinstance(ident, dict) else None

        # ── Enabled (config, effective) ────────────────────────────────────
        key_path = _CONFIG_ENABLE_KEY.get(family)
        config_enabled = _config_enable_flag(cfg, key_path) if key_path else None
        config_key = ".".join(key_path) if key_path else None

        # A governing config flag is the EFFECTIVE truth; identity is the declared mirror.
        effective_enabled = runtime_enabled if config_enabled is None else config_enabled
        if config_enabled is not None and config_enabled != runtime_enabled:
            divergences.append(
                f"config {config_key}={config_enabled} != identity runtime_enabled={runtime_enabled}"
            )

        status = derive_execution_status(
            selected=selected_version is not None, enabled=effective_enabled
        )
        contested = bool(declared_status and declared_status != status)
        if contested:
            divergences.append(
                f"identity_status declared={declared_status!r} but derived={status!r} "
                "(CONTESTED - executes_checkpoint withheld)"
            )

        # Feature width, from BOTH authorities. They can disagree: on the active patch
        # zone_gate identity claims 39 while the v4 artifact's own feature_order lists 38
        # (missing macd_hist_raw). Report both; never pick a winner here.
        identity_dim = resolved.feature_schema_dim if selected_version else None
        registry_dim = None
        if selected_version:
            try:
                from config_layer.model_resolver import enumerate_versions

                for row in enumerate_versions(family, repo_root=root):
                    if row.version == selected_version:
                        registry_dim = row.declared_feature_dim
                        break
            except ModelResolveError:
                registry_dim = None
        if (
            identity_dim is not None
            and registry_dim is not None
            and identity_dim != registry_dim
        ):
            divergences.append(
                f"feature dim: identity={identity_dim} != registry artifact={registry_dim}"
            )

        members[family] = BundleMember(
            family=family,
            selected_version=selected_version,
            artifact_path=artifact,
            artifact_exists=bool(artifact and artifact.exists()),
            runtime_enabled=runtime_enabled,
            config_enabled=config_enabled,
            config_enable_key=config_key,
            execution_status=status,
            declared_identity_status=declared_status,
            registry_feature_dim=registry_dim,
            identity_feature_dim=identity_dim,
            contested=contested,
            divergences=tuple(divergences),
        )
        bundle_divergences.extend(f"{family}: {d}" for d in divergences)

    return ProductionBundle(
        active_version=version,
        members=members,
        divergences=tuple(bundle_divergences),
        meta={"repo_root": str(root), "authority": "NONE"},
    )


__all__ = [
    "BundleMember",
    "ProductionBundle",
    "load_production_bundle",
    "derive_execution_status",
    "STATUS_ABSENT",
    "STATUS_SELECTED_NOT_ENABLED",
    "STATUS_SELECTED_AND_ENABLED",
    "STATUS_ENABLED_WITHOUT_CHECKPOINT",
]
