# Codebase commit — batch plan (semanticos_impl)

## Context
User asked for a "codebase commit". Working tree on `semanticos_impl` holds ~276 modified + ~150 untracked
paths from several lanes (F-117 feature fixes v7, F-118 candle patterns v8, F-119 corpus SSOT, F-120 clock
contract, timeframe SSOT v1/v2, card identities v9, semantic equivalence / authority mapping, research
scripts, user investigations). User chose: **commit everything, including scratch and large untracked dirs.**
Shared src files (feature_pipeline.py, feature_schema.py, backtest_v2.py …) span lanes, so batching is
by area, not by lane. HEAD is not switched; explicit paths only (never `git add -A`).

Preconditions already verified: `core.hooksPath=hooks` (hooks active); `assistant_project.md` has
2026-10-14 SESSION LOG entries (commit-msg hook satisfied); 14 files already staged.

## Steps
1. **Baseline**: `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` — record
   failed/passed before staging.
2. **Secret / size scan** on untracked paths: grep for key patterns (`gsk_`, `sk-`, `api_key`, `token=`,
   `password`) and list any file >5 MB. Stop and report on any hit. Confirm no `data/ logs/ results/ models/`
   paths are staged.
3. **Re-check `git status`** immediately before each batch (concurrent sessions); only stage paths seen in
   this plan's snapshot.
4. Commit batches in order (each `git add -- <explicit paths>` then `git commit`):
   - **B1 Data/clock + corpus SSOT (F-119/F-120)**: `src/data_ingestion/**`, `configs/data_provenance/**`,
     `docs/governance/CORPUS_CLOCK_CONTRACT.md`, `docs/governance/dataset_identity.schema.json`,
     `docs/governance/datasets/*`, `scripts/governance/review_ohlcv_clocks.py`, `tests/test_corpus_*`,
     `tests/test_ohlcv_clock_provenance.py`, `tests/test_dataset_registry.py`, `src/research/**` + research
     scripts that were migrated to `corpus_store.load`.
   - **B2 Features / schema v7–v8 (F-117/F-118, timeframe SSOT, semantic equivalence)**: `src/features/**`,
     `configs/formulas/**`, `configs/production/*.json`, `configs/research/*`, `src/config_layer/**`,
     `src/runtime/**`, `src/core/**`, `src/strategies/**`, `src/engines/**`, `src/training/**`,
     `src/identity/**`, `src/governance/**`, `src/semantics/**`, `src/charts/**`, `src/inout/**`,
     `src/analytics/**`, and all modified/new `tests/**`.
   - **B3 Governance & docs**: `CLAUDE.md`, `active_models.yaml`, `docs/current-findings.md`,
     `docs/governance/**` (manifests, registries, census, feature_semantic_*), `docs/reference/**`,
     `docs/memory/**`, `docs/topics/**` (incl. deletion of `feature-schema.md`), `docs/research-readiness/**`,
     `docs/research/**`, `docs/implementation_plan/*.md`.
   - **B4 Scripts & tools**: `scripts/analysis/**`, `scripts/research/**` (incl. new xau_1009_* /
     sujan_trade_decode), `scripts/governance/seed_script_registry.py`, `scripts/maintenance/**`,
     `scripts/backtest/**`, `scripts/data/**`, `scripts/training/**`, `tools/**`, `_build_run_story.py`,
     `multi_llm/bridge_layer/_tmp_replay_run1_paths.py`.
   - **B5 Investigations & artifacts**: `userinvestigation/**`, `docs/artifacts/`, `researcharctitecuredocs/`,
     `researchtasks/`, `HtmlArtifacts/`, `docs/reference/candle_theory/`, `docs/reference/capital-lot-sizing-reference.html`.
   - **B6 Scratch + session logs**: `results_xau_*.log`, `scratch_run_logs/`, `.playwright-mcp/`,
     `day1-initial.png`, `_probe.txt`, `report.json`, `write_html.py`, `docs/**/.grok-write-*.tmp`,
     `assistant_project.md`, `llm_project_assistant.md`.
   Pre-commit hook runs the green floor on governed batches. If a batch is blocked **only** by reds that
   match the step-1 baseline, report and ask before using `--no-verify`; never fix unrelated code.
   Each message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
5. New scripts under `scripts/**` are SITS-governed; if the coverage floor flags them unregistered, report
   it (registration = separate step, not done silently).
6. Append a SESSION LOG entry for this commit turn to `assistant_project.md` before B6.

## Verification
- `git status --porcelain` shows none of the snapshot paths left (other sessions' new files may appear).
- Re-run the governance floor; report failed/passed delta vs step 1.
- `git log --oneline -7` to show the batches. No push unless asked.
