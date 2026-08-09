"""
update_reachability_golden.py
=============================
ACCEPT-CHANGES script for the reachability L3 goldens (mirror of scripts/update_config_hash.py:
regenerate the committed truth so a drift is an EXPLICIT accepted change, never silent).

Two goldens are refreshed:
  1. Config golden  — the committed docs/research-readiness/config-reachability-report.{json,md}
                      (the report IS the golden; tests/test_reachability_golden.py diffs its
                      semantic subset). Reuses config_reachability.build_report/render_md.
  2. Registry golden — tests/golden/registry_summary.json, derived here by build_registry_summary()
                      (the SINGLE source of the registry summary; the golden test imports this same
                      function, so there is exactly one derivation, no duplication/drift).

Run after an INTENTIONAL change (new config knob, model added, flag flipped):
    python scripts/analysis/update_reachability_golden.py
then commit the regenerated artifacts. Authority: this only ACCEPTS truth changes; it never
DEFINES truth (see docs/research-readiness/README.md Test-Authority Ladder).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN = _ROOT / "tests" / "golden" / "registry_summary.json"
_REPORT_DIR = _ROOT / "docs" / "research-readiness"
_NON_MODEL_KEYS = {"meta", "philosophy"}


def _load_config_reachability():
    """Import the sibling analyzer by path (same importlib idiom as test_config_reachability.py)."""
    tool = Path(__file__).with_name("config_reachability.py")
    spec = importlib.util.spec_from_file_location("config_reachability", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _active_config() -> dict:
    version = (_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    return json.loads((_ROOT / "configs" / "production" / f"{version}.json").read_text(encoding="utf-8"))


def build_registry_summary() -> dict:
    """The STABLE semantic subset of active_models.yaml + ACTIVE_VERSION config — the registry
    L3 golden surface. Pins model coverage + the load-bearing runtime FLAGS (resolved from the
    active config, the §4.0 authority), never volatile prose. Drift here = a model added/removed
    or a runtime flag flipped. Single source of the derivation (imported by the golden test).
    """
    doc = yaml.safe_load((_ROOT / "active_models.yaml").read_text(encoding="utf-8"))
    models = {k: v for k, v in doc.items() if k not in _NON_MODEL_KEYS}
    cfg = _active_config()
    er = cfg["engine_runner"]
    return {
        "active_version": (_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip(),
        "model_count": len(models),
        "model_names": sorted(models),
        "runtime_flags": {
            "bitnet_enabled": cfg["crt_engine"]["use_bitnet"],
            "zone_mode": er["zone_mode"],
            "registry_file": er["zone_registry_path"],
            "gaussian_impl": er["gaussian_impl"],
            "rr_fusion_active": er["rr_fusion"]["enabled"],
        },
    }


def main() -> int:
    # 1. config golden = regenerate the committed report (reuses the analyzer's own writers)
    cr = _load_config_reachability()
    report = cr.build_report()
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (_REPORT_DIR / "config-reachability-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    (_REPORT_DIR / "config-reachability-report.md").write_text(
        cr.render_md(report), encoding="utf-8")

    # 2. registry golden fixture
    _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    summary = build_registry_summary()
    _GOLDEN.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"config golden  → {_REPORT_DIR.relative_to(_ROOT)}/config-reachability-report.{{json,md}}")
    print(f"registry golden → {_GOLDEN.relative_to(_ROOT)}")
    print(f"  active_version={summary['active_version']} models={summary['model_count']} "
          f"flags={summary['runtime_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
