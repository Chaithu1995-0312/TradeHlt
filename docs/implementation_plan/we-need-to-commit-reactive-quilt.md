# Plan: Commit all pending work, clean working tree (commits only, no code edits)

## Context
`git status` currently shows 13 modified tracked files and ~450 untracked
paths on `feature/truth-registry-v2` (a mix of real work-in-progress: new
`src/`/`tests/` modules, research packages, reports, docs, the `multi_llm/`
coordination layer, plus some scratch/junk that accumulated alongside it).
The user wants the tree brought to a clean state (`git status` empty) purely
through `git add`/`git commit` — no file content should be rewritten, no
refactors, no SITS registration workflow. This continues the same restoration
pattern already visible in recent history (`9b1b5ed`…`8696844`, "B2"–"B5 of
tree-restoration").

Two exceptions were explicitly approved by the user (not "code," but small,
necessary deviations to avoid an unsafe commit):
1. Delete 2 corrupted, unreadable-named files left over from a broken
   terminal command (0 bytes / 1.7KB, not real content).
2. Fix a one-line `.gitignore` typo (`models\` → `models/`) so the existing
   ignore intent for the 459MB `models/` artifact tree actually works —
   without committing `models/` itself.

## Excluded from any commit (left untracked, per user decision)
- `models/` (459MB trained-model binaries/checkpoints) — gitignore fixed so
  it's ignored going forward.
- `docs (2).zip`, `docs (3).zip`, `scripts (2).zip`,
  `bundles/who_how_what_bundle.zip` (duplicate/regenerable exports, ~6.5MB).
- `terminals/`, `agent-tools/` (session/tool-call scratch logs).
- **Proposed, flagging for review:** `xauusd_backtest_run/` (9MB generated
  backtest run output — JSONL/CSV/txt) is the same category as `models/`
  (regenerable artifact tree, not source). Recommend excluding it too,
  leaving it untracked, unless you want it committed — will confirm during
  execution if you'd rather include it.

## Pre-flight (safety, read-only)
- `.env` already confirmed properly gitignored (`git check-ignore -v .env`
  → matched `.gitignore:9`). No secret files appear in the untracked list.
- Before staging, grep the untracked set for obvious secret patterns
  (`api_key`, `BEGIN PRIVATE KEY`, `AKIA`, `sk-`, `ghp_`, `xox[bp]-`) as a
  final check — per repo's git-safety convention of reviewing anything
  suspicious before it's committed.

## Commit sequence
All commits keep file **content** byte-identical to what's on disk today —
each is `git add <paths>` + `git commit` only. Grouped thematically,
extending the existing "N of tree-restoration" commit-message convention:

1. **`chore: remove corrupted debug artifacts from a broken terminal command`**
   — `rm` the 2 garbled-name files, commit the deletion.
2. **`fix(gitignore): correct models/ ignore pattern (models\ -> models/)`**
   — the one approved config edit.
3. **`chore(tree): commit modified tracked files (B6 of tree-restoration)`**
   — the 13 `M` files (`assistant_project.md`, `configs/formulas/market_ontology.yaml`,
   `docs/book/encyclopedia/E1b-features-registry.md`, two
   `docs/governance/SEMANTIC_OS_*` files, `docs/governance/model_paths_literal_debt.json`,
   two `scripts/research/xauusd_episode_*` files, `src/bitnet/bitnet_registry.py`,
   `src/engines/live_engine.py`, `src/features/feature_states.py`,
   `src/features/market_context.py`, `tests/test_feature_states.py`).
4. **`feat(tree): commit new src/tests modules (B7 of tree-restoration)`**
   — `src/features/magnitude_states.py`, `src/research/episode_agreement.py`,
   `src/research/episode_propositions.py`, `ui_kits/control_plane/ExplorerPanel.jsx`,
   `mt5_analytics/evaluate_bar_features_outcome.py`, and their matching
   `tests/test_*.py`.
5. **`chore(tree): commit root-level analysis scripts + census outputs (B8 of tree-restoration)`**
   — root `_*.py` probes, `audit.py`, `count_audit_tmp.py`, the census
   `*.csv`/`*.jsonl`/`*.json` files, `codebase-atlas-explorer.html`,
   `codebase_explorer.html`, `flow_context/telemetry.json`, `flow_graphs/telemetry.dot`.
6. **`docs(tree): commit root-level and governance docs (B9 of tree-restoration)`**
   — root planning/analysis `*.md`/`*.txt` (`AMBIGUITY_REPORT.md`,
   `HANDOFF.md`, `MASTER_ARCHITECTURE_REFERENCE.md`, the `ZONE-X-*.md` set,
   `YAML_CONSUMER_AUDIT_*.md`, etc.), `docs/governance/EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`
   + `docs/governance/build_manifests/*`.
7. **`docs(tree): commit research reports (B10 of tree-restoration)`**
   — the full `reports/` tree (incl. `reports/parity_experiment/`, `reports/research/`, `reports/analysis/`).
8. **`chore(tree): commit research packages (B11 of tree-restoration)`**
   — `research/H-G001-001*`, `H-SECONDLOW-002_Complete_Package/`,
   `msip_1_verification_package/`.
9. **`chore(tree): commit multi-LLM coordination layer (B12 of tree-restoration)`**
   — `multi_llm/` (README, protocol, roles, research_lane, build_queue.jsonl,
   console.html), `llm_project_assistant.md`.
10. **`chore(tree): commit ChatGpt workflow library + grok exports (B13 of tree-restoration)`**
    — `ChatGpt  workflow/` (docx/html prompt library), `grok/` (PDFs, xlsx,
    scripts), plus root reference binaries `CRTClaude.pdf`, `Claude20day.pdf`,
    `DOC_TRACKING_INDEX.xlsx`, `scripts_business_functionality.xlsx`,
    `SujanTraderCRTExp.txt`, `DesignPlan1.txt`, `GrokCRTStatesAnalysis.md`.
11. **`chore(tree): commit scratch run logs (B14 of tree-restoration)`**
    — `pytest_full_run.log`, `pytest_output.txt`, `xauusd_backtest_console.txt`,
    `logs_phase1_run1_tmp.txt`, `fallback_sweep_after_b1.txt`,
    `fallback_sweep_before.txt`, `.fallback_after_b1_failures.txt`,
    `.fallback_before_failures.txt`, `knowledge_graph.json`.
12. **`docs: append SESSION LOG entry for tree-cleanup commits`** — per
    CLAUDE.md §6 (non-optional persistent logging mandate), append one
    `📝 SESSION LOG ENTRY` block to `assistant_project.md` summarizing this
    cleanup (this is a log append, not a code change).

After each commit, verify with `git status --short` that the expected paths
moved from `??`/`M` to committed. Final check: `git status` should be empty
except for the intentionally-excluded paths above (`models/`, the zips,
`terminals/`, `agent-tools/`, and `xauusd_backtest_run/` if still excluded).

## Verification
- `git log --oneline -15` shows the new commits in order.
- `git status --porcelain -uall` at the end shows only the deliberately
  excluded paths (or is fully empty if you'd rather include
  `xauusd_backtest_run/` too — flag during execution).
- `git show --stat` on commit 2 confirms only `.gitignore` changed, one line.
- No file's content differs from its pre-commit working-tree state (this
  plan performs zero rewrites other than the one approved `.gitignore` line
  and the two approved deletions).
