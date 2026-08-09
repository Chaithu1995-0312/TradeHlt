"""Validator for docs/governance/layer-audit-manifest.json (Phase 1, PASS A).

Guards the layer-by-layer audit program's stable discovery manifest:

  1. schema shape — required fields present per layer;
  2. every listed active artifact EXISTS and its recorded SHA-256 matches the
     on-disk bytes (a stale manifest is FC-OHLCV-23 / F-041A-class drift);
  3. closure guard — a layer may carry closure_verdict == "CLOSED" ONLY if its
     closure_report path exists and contains the literal verdict token
     `<LAYER_ID>_CLOSURE_STATUS = CLOSED` (PASS-B contract; PASS A must leave
     the verdict null).

Read-only; no fixtures, no data dependencies beyond the repo docs tree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "governance" / "layer-audit-manifest.json"

REQUIRED_LAYER_FIELDS = {
    "layer_id", "layer_name", "phase", "phase_status", "audit_started_utc",
    "repository_commit", "branch", "closure_verdict", "closure_report",
    "closure_timestamp_utc", "output_contract", "active_artifacts",
    "unresolved_blocker_candidates",
}

ALLOWED_VERDICTS = {None, "CLOSED"}  # BLOCKED is encoded as "BLOCKED:<reason>"


def _load() -> dict:
    assert MANIFEST.is_file(), f"missing manifest: {MANIFEST}"
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_manifest_schema_shape():
    m = _load()
    assert m.get("schema_version") == "1.0.0"
    layers = m.get("layers")
    assert isinstance(layers, list) and layers, "manifest must declare layers"
    for layer in layers:
        missing = REQUIRED_LAYER_FIELDS - set(layer)
        assert not missing, f"layer {layer.get('layer_id')} missing {sorted(missing)}"
        assert layer["active_artifacts"], "a frozen layer must list artifacts"


def test_active_artifacts_exist_and_hashes_match():
    m = _load()
    for layer in m["layers"]:
        for art in layer["active_artifacts"]:
            p = ROOT / art["path"]
            assert p.is_file(), f"manifest artifact missing on disk: {art['path']}"
            actual = _sha256(p)
            assert actual == art["sha256"], (
                f"stale manifest hash for {art['path']}: recorded "
                f"{art['sha256'][:12]}.., on-disk {actual[:12]}.. "
                "(regenerate the manifest or investigate the silent edit)"
            )


def test_closure_verdict_guard():
    m = _load()
    for layer in m["layers"]:
        verdict = layer["closure_verdict"]
        if verdict is None or (isinstance(verdict, str) and verdict.startswith("BLOCKED:")):
            continue  # PASS-A frozen or explicitly blocked — both legal
        assert verdict == "CLOSED", (
            f"illegal closure_verdict {verdict!r} for layer {layer['layer_id']} "
            "(only null, 'CLOSED', or 'BLOCKED:<reason>' are legal — C1 grammar)"
        )
        report_rel = layer["closure_report"]
        assert report_rel, "CLOSED requires a closure_report path"
        report = ROOT / report_rel
        assert report.is_file(), f"CLOSED but closure report missing: {report_rel}"
        token = f"{layer['layer_id']}_CLOSURE_STATUS = CLOSED"
        assert token in report.read_text(encoding="utf-8"), (
            f"CLOSED but the closure report lacks the literal token {token!r}"
        )


def test_pass_a_leaves_ohlcv_unclosed():
    """Point-in-time PASS-A invariant: the OHLCV layer is frozen, not closed."""
    m = _load()
    ohlcv = next(l for l in m["layers"] if l["layer_id"] == "OHLCV")
    if ohlcv["phase_status"] == "PASS_A_EVIDENCE_FROZEN":
        assert ohlcv["closure_verdict"] is None
        assert ohlcv["output_contract"] is None
