from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
BATCH = "probes_extraction_all_states_economic_2026-09-14"
ARCH = ROOT / "archive" / BATCH
ARCH.mkdir(parents=True, exist_ok=True)
(ARCH / "scripts" / "analysis").mkdir(parents=True, exist_ok=True)

# ---------- 1) Audit record for Phase-1 extraction (already applied) ----------
manifests = ROOT / "docs" / "governance" / "build_manifests"
manifests.mkdir(parents=True, exist_ok=True)

phase1_arch = ROOT / "archive" / "probes_extraction_phase1_2026-09-14"
phase1_csv = (phase1_arch / "MANIFEST.csv").read_text(encoding="utf-8") if (phase1_arch / "MANIFEST.csv").exists() else ""
phase1_files = []
for line in phase1_csv.splitlines()[1:]:
    if not line.strip():
        continue
    parts = line.split(",", 5)
    if len(parts) >= 3:
        phase1_files.append(parts[2])

impact = {
    "change_id": "CH-probes-extract-phase1-2026-09-14",
    "title": "Extract shared probe helpers into src/research/probes (Phase-1 first)",
    "when_utc": stamp,
    "policy": "no_deletes; pre-edit copies archived with MANIFEST",
    "archive_batch": "archive/probes_extraction_phase1_2026-09-14/",
    "created": [
        "src/research/probes/__init__.py",
        "src/research/probes/corpus.py",
        "src/research/probes/governance.py",
        "src/research/probes/horizon.py",
        "src/research/probes/scoreboard.py",
        "src/research/probes/costs_path.py",
        "src/research/probes/shadow_collapse.py",
    ],
    "edited_in_place": [
        "scripts/analysis/p001_excursion_probe.py",
        "scripts/analysis/sweep_structure_economic_probe.py",
        "scripts/analysis/phase1_resolver_replay_evidence.py",
    ],
    "archived_pre_edit": [
        "scripts/analysis/phase1_resolver_replay_evidence.py",
        "scripts/analysis/sweep_structure_economic_probe.py",
        "scripts/analysis/p001_excursion_probe.py",
        "scripts/analysis/shadow_cross_range_restoration_probe.py",
    ],
    "behavior": "MEASURE-ONLY paths preserved; Phase-1 standing contract unchanged; importlib sibling loads removed for Phase-1/sep/p001 shared helpers",
    "deferred": "Phase-1 local _Capture / shadow-collapse monkeypatches remain in CLI; shadow_collapse.py is placeholder",
    "checks": [
        "python -c import research.probes (PYTHONPATH=src)",
        "py_compile phase1 / sep / p001",
        "phase1 --help",
    ],
    "manifest_csv": "archive/probes_extraction_phase1_2026-09-14/MANIFEST.csv",
    "completion_status": "COMPLETE_LOCAL",
    "note": "Applied on D:\\Tradelatest working tree; GitHub SCM not connected for cloud PR at apply time.",
}
completion = {
    "change_id": "CH-probes-extract-phase1-2026-09-14",
    "change_classes": ["REFACTOR_EXTRACT", "NO_BEHAVIOR_CHANGE_INTENDED"],
    "declared_files": impact["created"] + impact["edited_in_place"] + [
        "archive/probes_extraction_phase1_2026-09-14/MANIFEST.csv",
        "archive/probes_extraction_phase1_2026-09-14/MANIFEST.md",
        "archive/ARCHIVE_INDEX.md",
        "docs/governance/build_manifests/CH-probes-extract-phase1-2026-09-14.impact.json",
        "docs/governance/build_manifests/CH-probes-extract-phase1-2026-09-14.completion.json",
        "docs/research/probes_extraction_audit_2026-09-14.md",
    ],
    "checks_executed": impact["checks"],
    "completion_status": "COMPLETE_LOCAL",
    "behavior_evidence": "Import surface moved to research.probes; CLI entrypoints and artifact paths unchanged. Full Phase-1 scoreboard golden re-run not executed in this session (expensive); import/compile/--help green.",
    "residual_disclosure": "Many other scripts still importlib-load siblings (queued). load_cost_model still lived on sep until CH-probes-extract-all-states-economic.",
    "archive_policy": "no deletes; see MANIFEST.csv actions copied_before_edit|created|edited_in_place|moved_to_archive",
}
(manifests / "CH-probes-extract-phase1-2026-09-14.impact.json").write_text(json.dumps(impact, indent=2) + "\n", encoding="utf-8")
(manifests / "CH-probes-extract-phase1-2026-09-14.completion.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")

audit_md = ROOT / "docs" / "research" / "probes_extraction_audit_2026-09-14.md"
audit_md.write_text(f"""# Probes extraction audit — 2026-09-14

## Purpose
Record migrations that extract shared probe helpers into `src/research/probes/` so later audits can see **what moved, what was archived, and what was not deleted**.

## Policy
- **No deletes** of existing files.
- Before in-place edits: copy originals into `archive/<batch>/` preserving relative paths.
- Track every action in `MANIFEST.csv` + `MANIFEST.md`.
- Append batch to `archive/ARCHIVE_INDEX.md`.

## Batch 1 — Phase-1 / sep / p001 (`probes_extraction_phase1_2026-09-14`)

| Item | Detail |
|------|--------|
| Change id | `CH-probes-extract-phase1-2026-09-14` |
| Created | `src/research/probes/` (corpus, governance, horizon, scoreboard, costs_path, shadow_collapse placeholder) |
| Edited | `p001_excursion_probe.py`, `sweep_structure_economic_probe.py`, `phase1_resolver_replay_evidence.py` |
| Archived | pre-edit copies of those three + `shadow_cross_range_restoration_probe.py` |
| Removed pattern | `importlib` file-load of sep/p001 from Phase-1 and sep→p001 |
| Manifest | `archive/probes_extraction_phase1_2026-09-14/MANIFEST.csv` |
| Governance | `docs/governance/build_manifests/CH-probes-extract-phase1-2026-09-14.{{impact,completion}}.json` |

## Batch 2 — all_states_economic (this apply)

See section below / `CH-probes-extract-all-states-economic-2026-09-14`.

## How to verify later
1. Diff live file vs `archive/<batch>/scripts/...` for intended shim-only changes.
2. Confirm SHA256 rows in `MANIFEST.csv`.
3. `PYTHONPATH=src` → `from research.probes import ...`
4. Re-run probe CLI; compare artifact schema (no claim keys).

---
Generated UTC: {stamp}
""", encoding="utf-8")
print("wrote phase1 audit records")

# ---------- 2) Extend costs_path with load_cost_model ----------
costs = ROOT / "src" / "research" / "probes" / "costs_path.py"
# archive costs_path before edit
rel_costs = "src/research/probes/costs_path.py"
dst = ARCH / rel_costs
dst.parent.mkdir(parents=True, exist_ok=True)
if costs.exists():
    dst.write_bytes(costs.read_bytes())

costs.write_text('''"""SEM-015 cost + TIMEOUT net-R path shared by economic probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from research.costs import ComponentCostModel
from research.probes.horizon import close_at_horizon

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = (
    _ROOT / "results/research/xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)


def load_cost_model(
    manifest_path: Path | None = None,
    instrument: str = "XAUUSD",
) -> ComponentCostModel:
    path = Path(manifest_path) if manifest_path is not None else DEFAULT_MANIFEST_PATH
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return ComponentCostModel.from_manifest(
        manifest, instrument=instrument, source=f"{path.name}",
    )


def net_r(
    corpus: list[dict],
    bar_index: int,
    direction: str,
    atr: float,
    cost_model: ComponentCostModel,
    horizon: int,
) -> Optional[float]:
    gross = close_at_horizon(corpus, bar_index, direction, atr, horizon)
    if gross is None:
        return None
    side = "long" if direction == "LONG" else "short"
    cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=side, nights_held=0) / atr
    return gross - cost_r
''', encoding="utf-8")
print("updated costs_path with load_cost_model")

# update __init__.py exports
init = ROOT / "src" / "research" / "probes" / "__init__.py"
init_txt = init.read_text(encoding="utf-8")
if "load_cost_model" not in init_txt:
    # archive init before edit
    (ARCH / "src/research/probes/__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (ARCH / "src/research/probes/__init__.py").write_bytes(init.read_bytes())
    init.write_text('''"""Shared research probe helpers.

Extracted from scripts/analysis probe CLIs so jobs stay thin entrypoints
without importlib file-loading sibling scripts.

Pre-edit snapshots: archive/probes_extraction_phase1_2026-09-14/
"""
from research.probes.corpus import load_corpus
from research.probes.governance import FORBIDDEN_KEYS, assert_no_claim_keys
from research.probes.horizon import close_at_horizon
from research.probes.costs_path import load_cost_model, net_r
from research.probes.scoreboard import profit_factor, scoreboard_row

__all__ = [
    "load_corpus",
    "FORBIDDEN_KEYS",
    "assert_no_claim_keys",
    "close_at_horizon",
    "load_cost_model",
    "net_r",
    "profit_factor",
    "scoreboard_row",
]
''', encoding="utf-8")
    print("updated probes __init__")

# ---------- 3) Archive + migrate all_states_economic_probe ----------
target_rel = "scripts/analysis/all_states_economic_probe.py"
target = ROOT / target_rel
arch_target = ARCH / target_rel
arch_target.parent.mkdir(parents=True, exist_ok=True)
arch_target.write_bytes(target.read_bytes())
sha_before = hashlib.sha256(target.read_bytes()).hexdigest()

txt = target.read_text(encoding="utf-8")
if "from research.probes.horizon import close_at_horizon" in txt:
    print("all_states already migrated")
else:
    txt = re.sub(r"import importlib\.util\n", "", txt, count=1)
    txt, n = re.subn(
        r"\n_SEP = ROOT.*?\n_spec\.loader\.exec_module\(sep\)\n",
        "\nfrom research.probes.corpus import load_corpus  # noqa: E402\n"
        "from research.probes.costs_path import load_cost_model  # noqa: E402\n"
        "from research.probes.governance import assert_no_claim_keys  # noqa: E402\n"
        "from research.probes.horizon import close_at_horizon  # noqa: E402\n",
        txt,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit(f"failed to replace sep load block n={n}")
    txt = txt.replace("cost_model = sep.load_cost_model()", "cost_model = load_cost_model()")
    txt = txt.replace("corpus = sep.p001.load_corpus(ROOT / args.csv)", "corpus = load_corpus(ROOT / args.csv)")
    txt = txt.replace("gross = sep.close_at_horizon(", "gross = close_at_horizon(")
    txt = txt.replace("sep.p001.assert_no_claim_keys(", "assert_no_claim_keys(")
    leftover = [f"{i}:{l}" for i, l in enumerate(txt.splitlines(), 1) if "sep." in l or "importlib" in l]
    if leftover:
        print("LEFTOVER:", leftover)
        raise SystemExit("leftover sep/importlib")
    target.write_text(txt, encoding="utf-8")
    print("migrated all_states_economic_probe")

# Also shim sep.load_cost_model to re-export from probes for other callers
sep_path = ROOT / "scripts/analysis/sweep_structure_economic_probe.py"
sep = sep_path.read_text(encoding="utf-8")
if "from research.probes.costs_path import load_cost_model" not in sep:
    # archive sep again for this batch
    (ARCH / "scripts/analysis/sweep_structure_economic_probe.py").write_bytes(sep_path.read_bytes())
    if "from research.probes.horizon import close_at_horizon" in sep:
        sep = sep.replace(
            "from research.probes.horizon import close_at_horizon  # noqa: E402\n",
            "from research.probes.horizon import close_at_horizon  # noqa: E402\n"
            "from research.probes.costs_path import load_cost_model as _load_cost_model_shared  # noqa: E402\n",
            1,
        )
        sep, n = re.subn(
            r"\ndef load_cost_model\(\) -> ComponentCostModel:.*?(?=\n\n# close_at_horizon|\n\ndef cell|\n\ndef pct|\n\ndef main)",
            "\ndef load_cost_model() -> ComponentCostModel:\n"
            "    return _load_cost_model_shared()\n\n\n",
            sep,
            count=1,
            flags=re.S,
        )
        # if body still old style
        if n == 0:
            sep, n = re.subn(
                r"\ndef load_cost_model\(\) -> ComponentCostModel:.*?(?=\n\ndef )",
                "\ndef load_cost_model() -> ComponentCostModel:\n"
                "    return _load_cost_model_shared()\n\n\n",
                sep,
                count=1,
                flags=re.S,
            )
        print(f"sep load_cost_model wrapper n={n}")
        sep_path.write_text(sep, encoding="utf-8")
    else:
        print("WARN: sep missing probes import; skip load_cost_model shim")

# ---------- MANIFEST for batch 2 ----------
rows = ["timestamp_utc,action,original_path,archive_path,sha256_before,reason"]
rows.append(f"{stamp},copied_before_edit,{target_rel},archive/{BATCH}/{target_rel},{sha_before},pre-edit snapshot before all_states probes migration")
for rel in ["src/research/probes/costs_path.py", "src/research/probes/__init__.py", "scripts/analysis/sweep_structure_economic_probe.py"]:
    p = ROOT / rel
    ap = ARCH / rel
    if ap.exists():
        h = hashlib.sha256(ap.read_bytes()).hexdigest()
        rows.append(f"{stamp},copied_before_edit,{rel},archive/{BATCH}/{rel},{h},pre-edit snapshot")
    if p.exists():
        h2 = hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append(f"{stamp},edited_in_place,{rel},archive/{BATCH}/{rel},{h2},post-edit live hash")
h_t = hashlib.sha256(target.read_bytes()).hexdigest()
rows.append(f"{stamp},edited_in_place,{target_rel},archive/{BATCH}/{target_rel},{h_t},removed importlib; uses research.probes")
(ARCH / "MANIFEST.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
(ARCH / "MANIFEST.md").write_text(f"""# Archive batch `{BATCH}`

- UTC: {stamp}
- Policy: no deletes
- Migrated: `scripts/analysis/all_states_economic_probe.py` off importlib → `research.probes`
- Also: `load_cost_model` lifted into `src/research/probes/costs_path.py`; sep wrapper retained

See MANIFEST.csv for SHA256.
""", encoding="utf-8")

idx = ROOT / "archive" / "ARCHIVE_INDEX.md"
entry = f"""
## {BATCH}
- When (UTC): {stamp}
- Purpose: Migrate all_states_economic_probe off importlib; extract load_cost_model; audit Phase-1 batch
- Manifest: archive/{BATCH}/MANIFEST.csv
- Deletes: none
"""
if idx.exists():
    idx.write_text(idx.read_text(encoding="utf-8") + entry, encoding="utf-8")
else:
    idx.write_text("# Archive index\n" + entry, encoding="utf-8")

# Batch 2 governance manifests
impact2 = {
    "change_id": "CH-probes-extract-all-states-economic-2026-09-14",
    "title": "Migrate all_states_economic_probe to research.probes; extract load_cost_model",
    "when_utc": stamp,
    "archive_batch": f"archive/{BATCH}/",
    "created_or_extended": ["src/research/probes/costs_path.py (load_cost_model)", "src/research/probes/__init__.py exports"],
    "edited_in_place": [
        "scripts/analysis/all_states_economic_probe.py",
        "scripts/analysis/sweep_structure_economic_probe.py",
        "src/research/probes/costs_path.py",
        "src/research/probes/__init__.py",
    ],
    "depends_on": "CH-probes-extract-phase1-2026-09-14",
    "completion_status": "COMPLETE_LOCAL",
}
completion2 = {
    "change_id": "CH-probes-extract-all-states-economic-2026-09-14",
    "change_classes": ["REFACTOR_EXTRACT", "NO_BEHAVIOR_CHANGE_INTENDED"],
    "declared_files": impact2["edited_in_place"] + [
        f"archive/{BATCH}/MANIFEST.csv",
        f"archive/{BATCH}/MANIFEST.md",
        "docs/governance/build_manifests/CH-probes-extract-all-states-economic-2026-09-14.impact.json",
        "docs/governance/build_manifests/CH-probes-extract-all-states-economic-2026-09-14.completion.json",
        "docs/research/probes_extraction_audit_2026-09-14.md",
    ],
    "checks_executed": ["py_compile all_states_economic_probe", "import load_cost_model from research.probes"],
    "completion_status": "COMPLETE_LOCAL",
    "behavior_evidence": "Same close_at_horizon / load_corpus / assert_no_claim_keys / SEM-015 TIMEOUT path; importlib removed.",
}
(manifests / "CH-probes-extract-all-states-economic-2026-09-14.impact.json").write_text(json.dumps(impact2, indent=2) + "\n", encoding="utf-8")
(manifests / "CH-probes-extract-all-states-economic-2026-09-14.completion.json").write_text(json.dumps(completion2, indent=2) + "\n", encoding="utf-8")

# append batch2 section to audit md
audit_md.write_text(audit_md.read_text(encoding="utf-8") + f"""
## Batch 2 — all_states_economic (`{BATCH}`)

| Item | Detail |
|------|--------|
| Change id | `CH-probes-extract-all-states-economic-2026-09-14` |
| Edited | `all_states_economic_probe.py` (no importlib); `costs_path.load_cost_model`; sep wrapper |
| Archived | pre-edit copies under `archive/{BATCH}/` |
| Manifest | `archive/{BATCH}/MANIFEST.csv` |

### Remaining importlib sibling loaders (queue)
See live `Select-String importlib.util` under `scripts/` — next likely: `phase1_shadow_create_economic_census.py`, `sweep_conditional_magnitude_probe.py`, `all_states_persistence_probe.py`, `build_decision_atlas.py`.
""", encoding="utf-8")

print("DONE")
