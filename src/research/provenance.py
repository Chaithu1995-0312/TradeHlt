"""provenance.py — versioned realism/method stamps for research artifacts.

Every `edge_report.json` carries these so a stored verdict is permanently interpretable:
the assumed execution reality, the cost model, and (at M4) the qualification method. The
research↔spine realism difference is therefore self-documenting and greppable — it can
never drift unnoticed. Bump a version whenever the thing it names changes.

target-strategy-architecture.md §14.D also asks for "config hash, feature schema hash" on
every experiment record — `production_config_block()` below closes that: it stamps which
PRODUCTION config (ACTIVE_VERSION + its hash) and which canonical feature schema were live
when the research ran, so a finding can be tied back to the spine truth it was measured
against. This is DISTINCT from `cfg.sha256()` (the research config's own hash, stamped
separately at each call site) — one says "which research recipe", this says "which spine
truth". `strategy_id` is deliberately NOT stamped here: no research config currently
declares one (`ResearchConfig` has no such field) — adding it is a real feature addition,
out of scope for this provenance stamp. Fail-open: if the production registry can't be
read (e.g. in an isolated test), the block degrades to `None` fields rather than raising —
provenance is best-effort and must never block a research run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path

from governance.measurement_basis import canonicalise

# Execution-reality standard shared with the live spine's governed exit model.
# Bump when exit geometry / slippage model / tie-break changes.
TRUTH_STANDARD_VERSION = "2.0"

# Research uses a deterministic flat round-trip cost (preserves byte-identical
# determinism); the spine uses seeded-random ATR-fraction slippage + spread. The two
# are intentionally different — versioned so the divergence stays explicit.
RESEARCH_COST_MODEL_VERSION = "1.0"
SPINE_COST_MODEL_VERSION = "1.0"


def truth_standard_block(
    exit_model: str,
    round_trip_bps: float,
    *,
    tie_break: str,
    cost_model: dict | None = None,
    fill_model: dict | None = None,
) -> dict:
    """The execution-reality stamp for a research artifact.

    `cost_model` / `fill_model` are optional and ADDITIVE: when both are omitted the
    returned dict is byte-identical to the pre-2026-08-19 shape (except for `tie_break`
    — see below), so every existing artifact keeps its provenance unchanged.

    Supply them when a run uses the SEM-015 component cost model or the SEM-016
    adverse-fill model, so a result carries the ruler that produced it. A result whose
    measurement basis cannot be recovered from its own artifact is precisely the gap
    MEASUREMENT_CONTRACT.md was written about.

    `tie_break` is REQUIRED, no default (CH-measurement-basis-declaration). Before this
    change the field was hardcoded `"SL_before_TP"` with no parameter at all — happened
    to be accurate for every current caller (all measure via `forward_walk`, which
    hardcodes the SL-first convention in both exit models), but was a structurally
    unguarded declaration: it could not have tracked a caller using the `optimistic`
    arm, which exists and is reachable (`multi_tp_walk`/`reference_walker`). Pass the
    governance.measurement_basis constant your caller actually measured under; a caller
    that genuinely cannot name its own basis passes `UNSTAMPED` explicitly — never a
    plausible-looking guess. Canonicalised through the same alias table `can_compare`
    uses, so `"SL_before_TP"` (the historical literal) still resolves to `"production"`.

    Args:
        cost_model: e.g. `ComponentCostModel.provenance()` — model id, instrument,
            source manifest sha256, per-component values, entry-slippage basis.
        fill_model: how a triggered stop filled, e.g.
            `{"model": "adverse_fill", "ontology_id": "SEM-016",
              "stop_slippage": 0.09, "model_gaps": True}`.
    """
    _tie_break = canonicalise("tie_break", tie_break)
    if _tie_break is None:
        raise ValueError(
            f"truth_standard_block: tie_break={tie_break!r} is not a recognised "
            "measurement_basis.TIE_BREAKS member or alias — pass UNSTAMPED explicitly "
            "if the caller genuinely cannot name its basis, never a guess."
        )
    block = {
        "version": TRUTH_STANDARD_VERSION,
        "exit_geometry": exit_model,
        "slippage_model": f"flat_{round_trip_bps:g}bps",
        "tie_break": _tie_break,
    }
    if cost_model is not None:
        # The flat bps figure is retained above as provenance of what WOULD have been
        # charged, so a reader can see both rulers side by side rather than only the
        # one that won.
        block["slippage_model"] = cost_model.get("cost_model_id", "component_measured")
        block["flat_bps_superseded"] = f"flat_{round_trip_bps:g}bps"
        block["cost_model"] = cost_model
    block["fill_model"] = fill_model if fill_model is not None else "perfect_stop_fill"
    return block


def production_config_block() -> dict:
    """Which PRODUCTION config + canonical feature schema were live for this research run.

    Fail-open by design (see module docstring) — never raises.
    """
    config_version = None
    config_hash = None
    try:
        from config_layer.production_config import get_prod_metadata
        meta = get_prod_metadata()
        config_version = meta.get("version")
        config_hash = meta.get("config_hash")
    except Exception:
        pass

    feature_schema_hash = None
    try:
        from features.feature_schema import FEATURE_ORDER_HASH
        feature_schema_hash = FEATURE_ORDER_HASH
    except Exception:
        pass

    return {
        "config_version": config_version,
        "config_hash": config_hash,
        "feature_schema_hash": feature_schema_hash,
    }


# ── run-manifest primitives ───────────────────────────────────────────────────────────────────
# Research-framework consolidation Phase 1 (2026-09-14): these replace byte-for-byte copies that
# lived as private helpers in scripts/analysis + scripts/research (`_git_commit` ×18,
# `_sha256`/`_sha256_file`/`_sha` ×33, `_utc` ×4, `_utc_now` ×4). Each keeps the EXACT behavior of
# the copies it replaces — pinned by tests/research/test_provenance_helpers.py against those
# originals — so a script importing it under its old private name is behavior-identical.
#
# Phase 4 (2026-09-17): migrated the 3 remaining genuine `sha256_file` stragglers found by a fresh
# sweep (`build_bar_matrix.py`, `xauusd_mt5_cost_calibration.py`, `zone_x_o4_gap_study.py`) and
# added `write_report()` below, centralizing the report.json + `{stem}_manifest.json` split
# several scripts had independently hand-written identically. Deliberately did NOT build a generic
# `ScriptRunner`/base-class framework across all ~163 `scripts/research/*.py` files, or migrate
# every script to `write_report()` — reading `research.mc_kit`'s own "SCOPE HONESTY" lesson (Phase
# 3, same date) first: many scripts differ by design (different output shapes, some write
# Markdown/HTML alongside JSON, not a manifest), and forcing them into one template would either
# silently drop a real distinction or need a risky one-size-fits-all DSL. Two candidates found in
# the same sweep were deliberately NOT migrated for the identical reason: `path_ambiguity_census.py`
# `_git_commit` pins `cwd=_ROOT` (a real behavioral difference from `git_commit()` below, not a
# duplicate); `run_h_msip_002.py`'s `_git_meta`/`_sha256_bytes` are genuinely distinct helpers (a
# dirty-tree-flag dict; hashing in-memory bytes rather than a file path). Migrating the remaining
# non-piloted scripts onto `write_report()` is left as future, optional, one-script-at-a-time,
# parity-proven cleanup — not committed work.
# Originals: archive/research_framework_phase1*_2026-09-14/. Variants that differed (e.g. a
# `_git_commit` with `cwd=_ROOT` + timeout) were deliberately NOT folded in.


def git_commit() -> str:
    """HEAD commit of the git repo containing the process cwd, or ``"unknown"`` on any failure."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def sha256_file(path: str | PathLike) -> str:
    """Streaming SHA-256 hex digest of a file (1 MiB chunks; corpora are large)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_stamp_compact() -> str:
    """UTC wall clock as ``YYYYMMDDTHHMMSSZ`` (run-directory / run-id stamp)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    """UTC wall clock as ``YYYY-MM-DDTHH:MM:SSZ`` (manifest ``generated_at`` stamp)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_report(
    out_dir: Path,
    stem: str,
    body: dict,
    *,
    extra_manifest: dict | None = None,
    include_body_sha256: bool = True,
) -> "tuple[Path, Path]":
    """Write `body` -> `{stem}.json` (deterministic, sort_keys, indent=2 — no wall-clock, safe
    to byte-compare across runs) plus a sibling `{stem}_manifest.json` carrying `generated_at`
    (`datetime.now(timezone.utc).isoformat()`) + `git_commit()` + (by default) the report's own
    `body_sha256`, merged with any caller-supplied `extra_manifest` fields.

    Research-framework consolidation Phase 4 (2026-09-17): centralizes a report+manifest split
    already hand-written IDENTICALLY in `ablate_zone_thr_xauusd_fusion.py`,
    `diagnose_gaussian_pivotality.py`, and (minus `body_sha256`, hence the opt-out flag)
    `transition_information.py`. `generated_at` deliberately uses the same raw
    `datetime.now(timezone.utc).isoformat()` those scripts (and `research.cli.cmd_run`) already
    use — NOT `utc_now_iso()` above, which is a different, more compact format used elsewhere —
    so migrating a script onto this function does not change its manifest's timestamp shape.

    Returns `(report_path, manifest_path)`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    body_json = json.dumps(body, sort_keys=True, indent=2)
    report_path = out_dir / f"{stem}.json"
    report_path.write_text(body_json, encoding="utf-8")

    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
    }
    if include_body_sha256:
        manifest["body_sha256"] = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    if extra_manifest:
        manifest.update(extra_manifest)

    manifest_path = out_dir / f"{stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    return report_path, manifest_path


def provenance_block(
    exit_model: str,
    round_trip_bps: float,
    *,
    tie_break: str,
    cost_model: dict | None = None,
    fill_model: dict | None = None,
) -> dict:
    """Realism + cost-model + production-truth provenance (M4 adds qual/method versions).

    `tie_break` is REQUIRED (CH-measurement-basis-declaration) — see
    `truth_standard_block`'s docstring for the rationale and the `UNSTAMPED` escape
    hatch. `cost_model` / `fill_model` pass through to `truth_standard_block`; omitting
    both reproduces the historical block exactly (aside from the now-required tie_break).
    """
    return {
        "truth_standard": truth_standard_block(
            exit_model, round_trip_bps, tie_break=tie_break,
            cost_model=cost_model, fill_model=fill_model,
        ),
        "research_cost_model_version": RESEARCH_COST_MODEL_VERSION,
        "spine_cost_model_version": SPINE_COST_MODEL_VERSION,
        **production_config_block(),
    }
