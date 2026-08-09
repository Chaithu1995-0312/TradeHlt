"""validation_contract.py — H1/H2/H3 guards over run manifests (ERP testing-plan §5/§6).

Reusable by producers and tests. These are the mechanical anti-hallucination checks:
  H1 (invented result)  -> require_manifest: an economic claim without a manifest raises.
  H2 (misread result)   -> assert_summary_matches_manifest / summary_from_assertions: a prose-facing
                           summary cannot silently disagree with the manifest / assertions.
  H3 (wrong path)        -> validate_manifest_against_intent: lens/label/cost/instrument/network/broker
                           must match the work-item intent contract, else violations are returned.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Summary keys that MUST equal the manifest (the H2 surface: what a human/LLM reads).
_SUMMARY_MANIFEST_KEYS: tuple[str, ...] = (
    "instruments", "validation_lens", "cost_model_bps", "label_source", "exit_model",
)


class SummaryManifestMismatch(AssertionError):
    """A prose-facing summary disagrees with the run manifest (H2)."""


class MissingManifestError(RuntimeError):
    """An economic/market claim was attempted without a run manifest (H1)."""


def require_manifest(run_dir: Path | str) -> dict[str, Any]:
    """Return the manifest for run_dir, or raise MissingManifestError. Anti-H1 gate for any code
    path that is about to emit an economic/market claim."""
    p = Path(run_dir) / "run_manifest.json"
    if not p.exists():
        raise MissingManifestError(
            f"economic/market claim refused: no run_manifest.json in {run_dir} (anti-H1)")
    return json.loads(p.read_text(encoding="utf-8"))


def assert_summary_matches_manifest(summary: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Raise SummaryManifestMismatch if any load-bearing summary field ≠ manifest (anti-H2)."""
    diffs = []
    for k in _SUMMARY_MANIFEST_KEYS:
        if k not in summary:
            continue
        if summary[k] != manifest.get(k):
            diffs.append(f"{k}: summary={summary[k]!r} != manifest={manifest.get(k)!r}")
    if diffs:
        raise SummaryManifestMismatch("summary disagrees with manifest (H2): " + "; ".join(diffs))


def classify_run_status(stdout: str, returncode: int, timed_out: bool = False) -> str:
    """'OK' only on a non-empty stdout AND returncode 0 AND not timed out; else 'ERROR'.

    A timeout / empty stdout / non-zero exit NEVER defaults to success (anti-H3/AH-03)."""
    if timed_out or returncode != 0 or not (stdout or "").strip():
        return "ERROR"
    return "OK"


def load_intent_contract(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest_against_intent(manifest: dict[str, Any],
                                     intent: dict[str, Any]) -> list[str]:
    """Return a list of violations where the manifest's actual path ≠ the intent contract (H3).

    Empty list == FLOW matches intent (necessary, not sufficient — human still reviews)."""
    violations: list[str] = []

    def _cmp(field: str, intent_key: str | None = None) -> None:
        ik = intent_key or field
        if ik in intent and manifest.get(field) != intent[ik]:
            violations.append(f"{field}: manifest={manifest.get(field)!r} != intent={intent[ik]!r}")

    _cmp("validation_lens")
    _cmp("exit_model")
    _cmp("cost_model_bps")
    _cmp("label_source")
    _cmp("instruments")

    # network / broker gating: intent says whether they are allowed.
    if intent.get("allow_network") is False and manifest.get("network", "none") != "none":
        violations.append(f"network={manifest.get('network')!r} but intent allow_network=false")
    if intent.get("allow_broker") is False and manifest.get("dry_run") is not True:
        violations.append("dry_run is not True but intent allow_broker=false")
    return violations


def summary_from_assertions(assertions: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Generate the canonical prose-facing summary FROM assertions + manifest (anti-H2/VP-05).

    Producers/agents should render summaries via this, never free-hand — so a summary structurally
    cannot drift from what ran."""
    return {
        "run_id": manifest.get("run_id"),
        "instruments": manifest.get("instruments"),
        "validation_lens": manifest.get("validation_lens"),
        "cost_model_bps": manifest.get("cost_model_bps"),
        "label_source": manifest.get("label_source"),
        "exit_model": manifest.get("exit_model"),
        "validation_flow_review": manifest.get("validation_flow_review"),
        "result": assertions,
    }
