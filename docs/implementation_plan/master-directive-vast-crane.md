# Master Directive — Phase 1: Land Existing WIP, Investigate Clutter, Scaffold the Coverage Audit

## Context

The user's master directive asks for autonomous, full architecture understanding/validation/
closure of the entire repository. That is not a one-session task on a codebase this size (476+
`src/` modules, 70+ tracked findings, an 11-surface closure index, a Semantic OS, an 813-row
Encyclopedia). Before any of that could responsibly start, exploration surfaced that the working
tree already carries **~1,872 uncommitted lines of complete, tested research-shadow work**
(Phase 2a/2b/2c episode-semantic integration + an OSS-lab benchmark scaffold) sitting alongside
some unrelated hardening diffs and unclassified workspace clutter (root-level zip files, a
duplicate `oss_lab` tree, stray log dumps). Starting a repo-wide audit against that moving,
partially-uncommitted baseline would produce a coverage report that's wrong the moment it's
written.

The user confirmed the priority: **land the existing WIP first** (validate + commit only the
coherent, intended work — not a blind `git add -A`), **investigate the clutter's actual contents**
before deciding its disposition, then move to the formal coverage audit on a clean, frozen
baseline. This plan covers the first two steps concretely and scaffolds the third; full
architecture reconstruction and closure (the master directive's later sections) is out of scope
for this session and is handed off as a dependency-ordered roadmap.

## What's already known (from exploration, not re-derived)

- **5 build manifests, all self-report `COMPLETE`** under `docs/governance/build_manifests/`:
  `CH-phase2a-magnitude-states`, `CH-phase2b-episode-propositions`, `CH-phase2c-episode-agreement`,
  `CH-l4-l7-context-testimony`, `CH-oss-lab-scaffold` (this last one `COMPLETE_LAB_SCAFFOLD`,
  `authority_statement: RESEARCH_LAB_ONLY`).
- **Tests actually pass**, independently re-run (not just manifest-trusted): 116 passed across
  [magnitude_states](../../src/features/magnitude_states.py) /
  [episode_agreement](../../src/research/episode_agreement.py) /
  [episode_propositions](../../src/research/episode_propositions.py) / `market_context.py` /
  `model_evidence.py` / `feature_states.py`; 24 passed for `test_oss_lab.py`. A pre-existing,
  disclosed residual (`test_geometry_census.py` + `test_gate2b_closure.py`, 4 failed) predates this
  WIP and is explicitly called out in the phase2a manifest as not introduced by it.
- **Nothing new is wired into the spine** — `magnitude_states.py` / `episode_propositions.py` /
  `episode_agreement.py` have zero import references from `fusion_engine.py`, `decision_engine.py`,
  or any engine; only `scripts/research/xauusd_episode_*` and their own test suites use them. This
  matches every manifest's `PRODUCTION_BEHAVIOR_CHANGED=NO` / `research_shadow` claim.
- **One genuinely unbuilt, blocked item** lives alongside the complete work:
  [docs/implementation_plan/no-goverznnce-no-docs-graceful-crescent.md](../../docs/implementation_plan/no-goverznnce-no-docs-graceful-crescent.md)
  is a fully-specified but **not-yet-implemented** fix for a PnL unit bug in
  `oss_lab/adapters/tradelatest/adapter.py` (line 128-133: `net_pnl` currently aliases a
  dimensionless R-multiple instead of money). Its own closing line flags an explicit open question:
  a prior instruction told it to skip CLAUDE.md's §6 SESSION LOG mandate ("no governance, no
  docs"), and it defers that call to the user. **This plan does not implement that fix** — it's
  new code, out of scope for "land what's already done" — but the governance question needs a
  default for when it *is* built.
- **Unrelated diffs riding in the same tree**: `src/bitnet/bitnet_registry.py` and
  `src/engines/live_engine.py` only remove silent `try/except` fallback wrappers around
  `ModelPaths` imports — plausibly tied to `docs/governance/model_paths_literal_debt.json` (also
  modified) rather than to the episode-semantic work. Need confirming against each manifest's
  `impact.json` declared-surfaces list before deciding whether they ride with this commit or are
  held out.
- **Unclassified clutter, in no manifest**: `docs (2).zip`, `docs (3).zip`, `scripts (2).zip` at
  repo root, a second `tools/oss_lab/` directory alongside the real `oss_lab/`, `terminals/1.txt`,
  raw dumps under `agent-tools/` and `bundles/who_how_what_bundle.zip`.

## Phase 1 — Land the existing WIP

1. **Verify, don't trust.** For each of the 5 `CH-*` manifests, run
   `python scripts/governance/construction_protocol.py validate-completion <manifest>` (per
   CLAUDE.md §3.3b — this executes the declared checks rather than log-trusting the `COMPLETE`
   self-report). Re-run the already-passing test files as a second confirmation
   (`pytest tests/test_magnitude_states.py tests/test_episode_propositions.py
   tests/test_episode_agreement.py tests/test_market_context.py tests/test_model_evidence.py
   tests/test_feature_states.py tests/test_oss_lab.py -q`).
2. **Resolve file scope.** Read each manifest's paired `impact.json` for its declared changed-file
   list; cross-check `bitnet_registry.py`, `live_engine.py`, and `model_paths_literal_debt.json`
   against those lists. If declared → commit with the matching CH's files. If undeclared → hold out
   and surface to the user as a separate, unrelated change needing its own review.
3. **SESSION LOG compliance (default: follow CLAUDE.md, not the "no governance, no docs"
   exception).** Confirm `assistant_project.md` carries entries covering this WIP per the §6
   mandate; append any missing entries for the 5 landed changes before committing. The
   "no-governance-no-docs" exception in the adapter-fix plan doc applies only to that *unbuilt*
   future work, not to what's being landed now — flag this default explicitly to the user rather
   than silently deciding it covers everything.
4. **Stage and commit only the coherent WIP** — the 5 CH-manifested source/test/doc files, their
   supporting docs (`EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`, `STATE_SEMANTIC_CENSUS_39.md`,
   `OSS_INTEGRATION_ARCHITECTURE.md`, the two new `docs/implementation_plan/*.md` files — the
   adapter-fix plan doc is safe to commit as a plan artifact even though its code isn't built), the
   real `oss_lab/` tree, and the two `scripts/research/xauusd_episode_*.py` files. Explicitly
   exclude the 3 root zips, `tools/oss_lab/`, `terminals/`, `agent-tools/`, `bundles/` (Phase 2
   territory), and anything from step 2 that turned out undeclared. Show `git status`/diff and the
   proposed commit message(s) before running `git commit` — no `git add -A`.

## Phase 2 — Investigate the clutter (read-only, no deletion)

Open and read (not just list) each unclassified item, then report a disposition recommendation
per item — duplicate / stale / historical-evidence / load-bearing / genuinely-orphaned — without
deleting or moving anything:

- `docs (2).zip`, `docs (3).zip`, `scripts (2).zip` (repo root)
- `tools/oss_lab/` vs the real `oss_lab/` — diff their contents to see if one is a stale copy
- `terminals/1.txt` and the rest of `terminals/`
- `agent-tools/*.txt` (looked like a raw hypothesis-framework JSON dump)
- `bundles/who_how_what_bundle.zip`

## Phase 3 — Freeze the baseline (this session if time remains, else handoff)

- Regenerate `graph.dot` via `scripts/analysis/gen_pyan.py` — it's currently stale (Aug 8 mtime vs
  today's Aug 12 commits).
- Run the GREEN_FLOOR check (`scripts/maintenance/check_governance_invariants.py` /
  `construction_protocol.py check`) post-commit to confirm no new breakage; the 4 pre-existing red
  tests (`test_geometry_census.py`, `test_gate2b_closure.py`) stay tracked as a known, disclosed
  residual — not a new blocker.

## Phase 4 — Scaffold the formal coverage audit (handoff roadmap, not executed this session)

Per the master directive's own "LLM Analysis Coverage Audit" methodology: reuse existing
denominators rather than inventing one — `scripts/analysis/script_census.py` (script universe),
`scripts/analysis/feature_dag_layers.py` (feature universe), and the Semantic OS's
`docs/governance/semantic_os/file_identities.yaml` (2,901-line FileIdentity registry, already
covering much of the repo but self-declaring ~1.3% *semantic* coverage vs its own ~92.5%
*documentation* coverage — the exact File-Discovery-vs-Source-Inspection distinction the directive
asks for). A first pass should target the architecturally-critical spine modules first
(`engine_runner.py`, `fusion_engine.py`, `decision_engine.py`, `execution_planner.py`,
`ultron_risk_gate.py`, `config_validator.py`, `promotion_manager.py`) rather than attempting all
476 modules at once — this becomes the next session's plan.

## Verification

- `pytest` targeted runs listed in Phase 1 step 1, plus `construction_protocol.py
  validate-completion` per manifest — all must pass before commit.
- `git status` clean (only intended files staged) and `git log -1` showing the new commit(s) after
  Phase 1.
- `git status` unchanged for clutter paths after Phase 2 (read-only confirmed).
- `graph.dot` mtime newer than HEAD's commit time after Phase 3.
