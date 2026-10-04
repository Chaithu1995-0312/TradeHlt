"""
reachability_validation_report.py
=================================
L2 GENERATED EVIDENCE artifact — a consolidated, regenerable snapshot of the reachability
validation state at reports/reachability_validation.{json,md}.

Authority = OBSERVATIONAL (docs/research-readiness/README.md Test-Authority Ladder). It records
what IS (verdict counts, resolved runtime flags, which guards certify this state) — NOT assertions
about external processes. There is deliberately NO `guards_passed` field: a stored `true` goes stale
the moment the artifact is regenerated without running the tests. Pass/fail is determined by actually
running `guard_suite` in CI / the verification pipeline, never read from this file.

Stable filename (the timestamp lives INSIDE the json), so `git diff reports/` is meaningful — mirrors
reports/framework_registry_report.md. Regenerate:
    python scripts/analysis/reachability_validation_report.py
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "reports"

# The behavioral guards that CERTIFY this reachability state (an observation — a list of files,
# not a claim they were run here). CI / the verification pipeline runs them for actual pass/fail.
_GUARD_SUITE = [
    "tests/test_config_reachability.py",       # L1: no DEAD keys (CAN FAIL BUILDS)
    "tests/test_reachability_golden.py",        # L3: config + registry drift alarms
    "tests/test_active_models_registry.py",     # citation-resolution floor + runtime-flag drift
    "tests/test_crt_state_invariants.py",       # CRT yaml<->code semantic invariant
]


def _load(mod_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _active_config() -> dict:
    version = (_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    return json.loads((_ROOT / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))


def build_evidence() -> dict:
    cr = _load(Path(__file__).with_name("config_reachability.py"), "config_reachability")
    report = cr.build_report()
    summary = cr.build_summary(report)
    cfg = _active_config()
    er = cfg["engine_runner"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_version": report["active_version"],
        "verdict_counts": summary["verdict_counts"],
        "dead_count": len(summary["dead_keys"]),
        "tooling_only_keys": summary["tooling_only_keys"],
        "runtime_flags_verified": {
            "bitnet_enabled": cfg["crt_engine"]["use_bitnet"],
            "zone_mode": er["zone_mode"],
            "registry_file": er["zone_registry_path"],
            "gaussian_impl": er["gaussian_impl"],
            "rr_fusion_active": er["rr_fusion"]["enabled"],
        },
        "guard_suite": _GUARD_SUITE,   # observation: the guards that certify this state
    }


def _render_md(ev: dict) -> str:
    flags = "".join(f"| `{k}` | `{v}` |\n" for k, v in ev["runtime_flags_verified"].items())
    counts = "".join(f"| {k} | {v} |\n" for k, v in ev["verdict_counts"].items())
    guards = "".join(f"- `{g}`\n" for g in ev["guard_suite"])
    return (
        f"# Reachability Validation — Evidence (L2, observational)\n\n"
        f"> Generated `{ev['generated_at']}` · ACTIVE_VERSION = `{ev['active_version']}` · "
        f"branch-scoped (§4.0). Regenerate: `python scripts/analysis/reachability_validation_report.py`.\n"
        f"> **Authority: OBSERVATIONAL.** Pass/fail is NOT stored here — run `guard_suite` in CI.\n\n"
        f"## Verdict counts\n\n| Verdict | Count |\n|---|---|\n{counts}\n"
        f"**DEAD count:** {ev['dead_count']} (must be 0 — gated by `tests/test_config_reachability.py`).\n\n"
        f"## Runtime flags verified (vs ACTIVE_VERSION config)\n\n| Flag | Value |\n|---|---|\n{flags}\n"
        f"## Certifying guard suite (observation)\n\n{guards}"
    )


def main() -> int:
    ev = build_evidence()
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "reachability_validation.json").write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    (_OUT / "reachability_validation.md").write_text(_render_md(ev), encoding="utf-8")
    print(f"L2 evidence → reports/reachability_validation.{{json,md}}")
    print(f"  active_version={ev['active_version']} dead={ev['dead_count']} "
          f"verdicts={ev['verdict_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
