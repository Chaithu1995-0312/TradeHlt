"""Generate `.grok/infra_file_citations.md` for sidecar / measurement / tests / lab.

Existence inventory only. Does not claim behavior or G001.
Reads disk declared trees minus paths already cited in How-index / INFRA /
topics / architecture (not this file — avoid a circular empty remainder).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".grok" / "infra_file_citations.md"
MARKER = "Remainder inventory (2026-09-04 citation pass, GCMC v3 denominator close 2026-09-04)"

# More-specific prefixes first. Topic name or INFRA.
_OWNERS: list[tuple[str, str]] = [
    # v3 — non-declared trees closed 2026-09-04 (GCMC v3 denominator fix).
    # Distinct labels on the non-live buckets: cited != running system.
    ("archive/", "INFRA.md (archived — not live)"),
    ("msip_1_verification_package/", "INFRA.md (frozen verification copy)"),
    ("H-SECONDLOW-002_Complete_Package/", "INFRA.md (frozen research package)"),
    ("docs/reference/example-service.py", "INFRA.md (reference template)"),
    (".grok/", "INFRA.md (self-tooling)"),
    ("grok/", "INFRA.md (self-tooling)"),
    ("results/", "INFRA.md (untracked scratch)"),
    ("copiedSrcFiles/", "INFRA.md (untracked scratch)"),
    ("terminals/", "INFRA.md (untracked scratch)"),
    ("exec_telemetry/", "live-execution.md"),
    ("manual_tools/", "research-measurement-contract.md"),
    ("reports/", "research-measurement-contract.md"),
    ("src/research/", "research-measurement-contract.md"),
    ("scripts/research/", "research-measurement-contract.md"),
    ("scripts/analysis/", "research-measurement-contract.md"),
    ("tests/research/", "research-measurement-contract.md"),
    ("src/governance/", "promotion-governance.md"),
    ("scripts/governance/", "promotion-governance.md"),
    ("tests/governance/", "promotion-governance.md"),
    ("src/bitnet/", "bitnet-gate.md"),
    ("src/agent/", "ai-automation-agent.md"),
    ("src/multi_llm/", "ai-automation-agent.md"),
    ("src/llm_research/", "ai-automation-agent.md"),
    ("scripts/context/", "ai-automation-agent.md"),
    ("src/control_plane/", "context-report.md"),
    ("src/charts/", "crt-spine.md"),
    ("src/cognitive/", "replay-memory.md"),
    ("src/replay/", "replay-memory.md"),
    ("src/retrieval/", "replay-memory.md"),
    ("src/scanner/", "execution-loop.md"),
    ("src/msip/", "execution-loop.md"),
    ("src/strategies/", "execution-loop.md"),
    ("src/expansion/", "expansion-engine.md"),
    ("src/search/", "weight-search.md"),
    ("src/interpreters/", "interpreter-contract.md"),
    ("scripts/training/", "training-calibration.md"),
    ("tests/training/", "training-calibration.md"),
    ("src/analytics/", "analytics-sltp.md"),
    ("tests/analytics/", "analytics-sltp.md"),
    ("src/events/", "event-fabric.md"),
    ("tests/events/", "event-fabric.md"),
    ("src/portfolio/", "portfolio-allocation.md"),
    ("tests/portfolio/", "portfolio-allocation.md"),
    ("src/regime/", "regime-classifier.md"),
    ("tests/regime/", "regime-classifier.md"),
    ("src/execution/", "execution-loop.md"),
    ("tests/execution/", "execution-loop.md"),
    ("src/live/", "live-execution.md"),
    ("src/inout/", "live-execution.md"),
    ("mt5_analytics/", "live-execution.md"),
    ("tests/mt5_analytics/", "live-execution.md"),
    ("oss_lab/", "INFRA.md (lab)"),
    ("tools/", "INFRA.md (lab)"),
    ("tests/Grok/", "crt-spine.md"),
    ("tests/Claude/", "crt-spine.md"),
    ("src/config_layer/", "config-validation.md"),
    ("src/core/", "fusion-decision.md"),
    ("src/engines/", "scoring-engines.md"),
    ("src/features/", "feature-schema.md"),
    ("src/runtime/", "crt-spine.md"),
    ("src/identity/", "research-measurement-contract.md"),
    ("src/data_ingestion/", "feature-schema.md"),
    ("src/journal/", "metrics-layer.md"),
    ("src/training/", "training-calibration.md"),
    ("src/validation_access/", "promotion-governance.md"),
    ("scripts/data/", "feature-schema.md"),
    ("scripts/maintenance/", "promotion-governance.md"),
    ("scripts/live/", "live-execution.md"),
    ("scripts/backtest/", "crt-spine.md"),
    ("scripts/evaluation/", "research-measurement-contract.md"),
    ("scripts/export/", "promotion-governance.md"),
    ("scripts/misc/", "INFRA.md (tooling)"),
    ("tests/data_ingestion/", "feature-schema.md"),
    ("tests/journal/", "metrics-layer.md"),
    ("tests/features/", "feature-schema.md"),
    ("tests/engines/", "scoring-engines.md"),
    ("tests/runtime/", "live-execution.md"),
    ("tests/harness/", "crt-spine.md"),
    ("tests/helpers/", "crt-spine.md"),
    ("tests/interpreters/", "interpreter-contract.md"),
    ("tests/replay/", "replay-memory.md"),
    ("tests/cognitive/", "replay-memory.md"),
    ("tests/config_layer/", "config-validation.md"),
]


def _load_linker():
    spec = importlib.util.spec_from_file_location(
        "link_infra", ROOT / ".grok" / "_link_infra_architecture.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def owner_for(rel: str) -> str:
    for prefix, owner in _OWNERS:
        if rel.startswith(prefix):
            return owner
    if rel.startswith("tests/"):
        return "INFRA.md (tests-floor)"
    if rel.startswith("scripts/"):
        return "INFRA.md (tooling)"
    if rel.startswith("src/"):
        return "INFRA.md (sidecar)"
    if rel.startswith("docs/"):
        return "INFRA.md (docs tooling)"
    if "/" not in rel:
        return "INFRA.md (root scripts)"
    return "INFRA.md (other)"


def main() -> None:
    link = _load_linker()
    cites = link.load_doc_citations()
    # Core only — remainder file is written by this script.
    core = set().union(
        cites.get("how_index", set()),
        cites.get("infra", set()),
        cites.get("topics", set()),
        cites.get("architecture", set()),
    )
    disk: list[str] = []
    for tree in (*link.GCMC_V1, *link.GCMC_V2, *link.GCMC_V3_DIRS):
        disk.extend(link.walk_py(tree))
    disk.extend(link.walk_py_root())
    remainder = sorted(p for p in disk if p not in core)

    grouped: dict[str, list[str]] = defaultdict(list)
    for rel in remainder:
        grouped[owner_for(rel)].append(rel)

    lines: list[str] = []
    A = lines.append
    A("# Infra file citations — remainder (sidecar, measurement, tests, lab)")
    A("")
    A(f"Generated {date.today().isoformat()} by `.grok/_cite_remainder.py`.")
    A("This file is the **existence inventory** for paths not already named in")
    A("How-index / INFRA / `docs/topics/` / `docs/architecture/`.")
    A("")
    A("**Not** a behavior claim. **Not** G001. **Not** CRT CLOSED. Source still wins.")
    A(f"**{MARKER}.**")
    A("")
    A(f"Remainder paths: **{len(remainder)}**. Disk declared trees: {len(disk)}.")
    A("The linker (`.grok/_link_infra_architecture.py`) counts every backtick path here")
    A("toward `Infra-doc referenced`.")
    A("")
    A("| Owning topic / INFRA bucket | Paths |")
    A("|---|---:|")
    for owner in sorted(grouped):
        A(f"| `{owner}` | {len(grouped[owner])} |")
    A("")
    for owner in sorted(grouped):
        files = grouped[owner]
        A(f"## {owner}")
        A("")
        A(f"{len(files)} paths. Existence only.")
        A("")
        for rel in files:
            A(f"- `{rel}`")
        A("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()} remainder={len(remainder)} owners={len(grouped)}")
    for owner in sorted(grouped):
        print(f"  {len(grouped[owner]):4} {owner}")


if __name__ == "__main__":
    main()
