# Research Scripts Intent Tracker

Inventory of research-script intents for TradeHlt / TradeLatest.

## Deliverables

- `RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx` - sheet `research_scripts` (frozen header + filters)
- `RESEARCH_SCRIPTS_INTENT_TRACKER.csv` - twin for easy git diff
- This README

## Scope

- **Primary:** all `scripts/research/**/*.py` (165 files)
- **Also:** research-oriented analysis scripts under `scripts/analysis/` that are clearly Phase / CRT / resolver / shadow / probe work (64 files)
- `folder` column distinguishes `research` vs `analysis`

## Columns

| Column | Meaning |
|--------|---------|
| script_path | Repo-relative path (forward slashes) |
| script_name | Basename |
| folder | `research` or `analysis` |
| intent | 1-3 sentences grounded in module docstring / top comment / argparse description |
| status_hints | MEASURE-ONLY / READ-ONLY / frozen / probe / etc. when stated |
| claim_class_or_authority | DESCRIPTIVE_ONLY, economic_claims_allowed=false, etc. when stated |
| primary_inputs | Short corpus/config/path hints from the file |
| primary_outputs | Artifact/path hints from the file |
| related_episode_or_id | L-003, JSE, SHADOW, SEM-015, Phase-1, CRT, etc. when mentioned |
| last_mtime | ISO local mtime at inventory time |
| notes | Gaps such as `INTENT_UNSTATED - inferred from name/CLI only` |

## Stats (this build)

- Explicit module docstring: **228**
- Intent unstated / inferred: **1**
- Total rows: **229**

## How to maintain

1. Prefer completeness for `scripts/research/` first.
2. When adding a script, put a real module docstring (1-3 sentences of intent) plus argparse `description=` if CLI.
3. State status/claim authority explicitly in the docstring when applicable, e.g. `MEASURE-ONLY`, `DESCRIPTIVE_ONLY`, `economic_claims_allowed=false`.
4. Re-run the builder:

```powershell
$env:PYTHONPATH = "D:\Tradelatest"
& .\.venv\Scripts\python.exe docs\research\_build_research_scripts_intent_tracker.py
```

5. Diff the CSV twin in PRs; treat Excel as the human-facing workbook.
6. Do **not** invent intents. If the docstring is empty, mark `INTENT_UNSTATED` and keep name/CLI inference minimal.
7. Do not commit unless asked. This tracker is documentation only - no freeze/resolver economic work.

## Rebuild script

The generator lives at `docs/research/_build_research_scripts_intent_tracker.py`.
It strips UTF-8 BOM (`utf-8-sig`), uses `ast.get_docstring` with regex fallback, and scrapes argparse `description=` / leading comments for gaps.
