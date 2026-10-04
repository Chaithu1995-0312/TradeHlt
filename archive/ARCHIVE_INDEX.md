# Archive index

Tracks migration batches that move/copy files into `archive/` instead of deleting.


## probes_extraction_phase1_2026-09-14
- When (UTC): 2026-09-14T10:24:11Z
- Purpose: Extract shared probe helpers into src/research/probes/; thin Phase-1 CLI; shim sep/p001
- Manifest: archive/probes_extraction_phase1_2026-09-14/MANIFEST.csv
- Deletes: none


## probes_extraction_all_states_economic_2026-09-14
- When (UTC): 2026-09-14T10:38:13Z
- Purpose: Migrate all_states_economic_probe off importlib; extract load_cost_model; audit Phase-1 batch
- Manifest: archive/probes_extraction_all_states_economic_2026-09-14/MANIFEST.csv
- Deletes: none

## probes_extraction_batch3_2026-09-14
- UTC: 2026-09-14T10:43:40Z
- Manifest: archive/probes_extraction_batch3_2026-09-14/MANIFEST.csv
- Deletes: none

## probes_extraction_sample_acquisition_2026-09-14
- When (UTC): 2026-09-14T10:46:08Z
- Purpose: Fix/migrate sample_acquisition off broken ev.sep.p001 onto research.probes
- Manifest: archive/probes_extraction_sample_acquisition_2026-09-14/MANIFEST.csv
- Deletes: none

## probes_extraction_replay_excursion_2026-09-14
- UTC: 2026-09-14T10:54:50Z
- Manifest: archive/probes_extraction_replay_excursion_2026-09-14/MANIFEST.csv
- Deletes: none
- `probes_extraction_clear18_2026-09-14/` — Batch 6b finish: scriptmod sys.modules + 8 remaining script loaders → `load_py` (2026-09-14T11:04:02Z)
- `probes_extraction_src_loaders_2026-09-14/` — route remaining src importlib loaders (semantic_query, ladder) through scriptmod.load_py (2026-09-14T11:06:27Z)

---

## Ledger rules (from 2026-09-14T12:40Z — research-framework consolidation, Phase 0)

- Verifier: `python scripts/maintenance/verify_archive_manifests.py` (logic `src/governance/archive_manifest.py`,
  floor `tests/governance/test_archive_manifests.py`). Every file under `archive/` must be named by an
  archive-copy row whose SHA-256 matches its bytes; no live original may disappear; every batch dir is named here.
- New rows use the canonical header `timestamp_utc,action,original_path,archive_path,sha256_before,reason,sha256_after`.
  Older manifests keep their own header (legacy A = no `sha256_after`; legacy B = `utc,action,source,dest,sha256,note`)
  and are appended to, never rewritten.
- Pre-convention folders (`dead_code/`, `inout_legacy/`, `scripts/`, `ui_legacy/`, `zips/`) are hashed in
  `archive/LEGACY_INVENTORY.csv` (action `inventory`).

## Backfill 2026-09-14T12:40:14Z (no files moved)
- 32 archived files inside the probes_extraction_* batches had NO manifest row; 25 pre-convention files had none either.
  `backfill_archive_copy` rows were appended to each batch's own MANIFEST.csv and `inventory` rows to
  `LEGACY_INVENTORY.csv`. Hashes are taken at backfill time; pre-archive provenance of those bytes is unknown.
- `probes_extraction_replay_excursion_2026-09-14/scripts/analysis/p001_excursion_probe.py.DAMAGED` is byte-identical
  (sha256 21dd419c…) to its sibling `p001_excursion_probe.py` in the same batch — the name is misleading, no content differs.
- Open warnings (edits the earlier batches did not record; surfaced by the verifier, not hidden):
  `scripts/analysis/p001_excursion_probe.py`, `src/research/probes/__init__.py`.
- Deletes: none

## research_framework_phase0_repair_2026-09-14
- When (UTC): 2026-09-14T12:36:23Z
- Purpose: Repair 9 `scripts/analysis/*.py` files left uncompilable (IndentationError) by the unrecorded part of
  `probes_extraction_clear18`: the `importlib` → `load_py` rewrite put `mod = load_py(...)` at column 0 inside a
  function. Fix = re-indent that single line (4 spaces). Broken bytes snapshotted first.
- Manifest: archive/research_framework_phase0_repair_2026-09-14/MANIFEST.csv (9 copied_before_edit + 9 edited_in_place)
- Parity: each diff is exactly 1 line; CRLF count unchanged; all 9 `py_compile` clean. The clear18 pre-edit originals
  (all compile) remain at archive/probes_extraction_clear18_2026-09-14/scripts/analysis/.
- Deletes: none
- `architecture_ui_closure_2026-09-14/` — architecture doc sync + CP Closure Inspector / ?run= (2026-09-14T12:56:00Z)

## research_framework_phase1a_provenance_2026-09-14
- When (UTC): 2026-09-14 (see MANIFEST.csv timestamps)
- Purpose: Phase 1a dedup. Added shared `git_commit` / `sha256_file` / `utc_stamp_compact` / `utc_now_iso` to
  `src/research/provenance.py` (additive), then replaced the private `_git_commit` copy (normalized-body variant
  9b89feee8d) in 13 `scripts/research/` drivers + `src/research/cli.py` with
  `from research.provenance import git_commit as _git_commit` at the same spot. Call sites unchanged.
- Manifest: archive/research_framework_phase1a_provenance_2026-09-14/MANIFEST.csv (15 files: copied_before_edit + edited_in_place each)
- Parity: tool refuses any def whose AST body is not the approved variant; `--help` stdout sha + exit code identical
  before/after for all 14 CLIs; every module's `_git_commit is research.provenance.git_commit`; floor
  `tests/research/test_provenance_helpers.py` pins the shared helpers against verbatim copies of every replaced variant;
  `tests/research/test_carry.py` + `test_harvest.py` green.
- Deletes: none

## research_framework_phase1b_provenance_2026-09-14
- Purpose: Phase 1b dedup — `_git_commit` (9b89feee8d) in 5 program drivers (`m5_mtf_information`, `phase_b/d/e/s_*`) →
  `research.provenance.git_commit`; `_utc_now` (8a3c0b1dff) in 4 `rr_*` drivers → `research.provenance.utc_now_iso`.
- Manifest: archive/research_framework_phase1b_provenance_2026-09-14/MANIFEST.csv (9 files)
- Parity: approved-variant gate; `--help` identical 9/9; identity 9/9. Deletes: none

## research_framework_phase1c_provenance_2026-09-14
- Purpose: Phase 1c dedup — streaming SHA-256 `_sha256` / `_sha256_file` (58ea5a0042) in 15 scripts →
  `research.provenance.sha256_file`.
- Manifest: archive/research_framework_phase1c_provenance_2026-09-14/MANIFEST.csv (15 files)
- Parity: approved-variant gate; `--help` identical 12/12 (3 without argparse not executed); identity 15/15. Deletes: none

## research_framework_phase1d_provenance_2026-09-14
- Purpose: Phase 1d dedup — `_sha256_file` (58ea5a0042 / 88dc0288cd / 5b64ee474a) in 14 scripts →
  `research.provenance.sha256_file`; `_utc` (c87b462e43) in 4 XAUUSD Gaussian/metals drivers →
  `research.provenance.utc_stamp_compact`.
- Manifest: archive/research_framework_phase1d_provenance_2026-09-14/MANIFEST.csv (14 files, 18 helper defs)
- Parity: approved-variant gate; `--help` identical 10/10 (4 without argparse not executed); identity 18/18. Deletes: none

## research_framework_phase1e_provenance_2026-09-14
- Purpose: Phase 1e dedup — `_sha` (6ac2da0004) in 4 feature-certification scripts → `research.provenance.sha256_file`.
- Manifest: archive/research_framework_phase1e_provenance_2026-09-14/MANIFEST.csv (4 files)
- Parity: approved-variant gate; none use argparse (not executed); identity 4/4. Deletes: none

### Phase 1 total
- 55 files, 59 private helper defs replaced by same-named imports of 4 shared functions in `src/research/provenance.py`.
- Left local on purpose (AST body differs from the shared function), per the Phase-1 inventory:
  `_git_commit` 643a936874 ×3 (`cwd=_ROOT` + timeout) + 2 single variants; `_git` 4 single variants;
  `_git_provenance` 040857cd36 ×2 + 3 single variants; `_sha256` f933f6e1fe ×2 + 2 single variants;
  `_sha256_file` 1 single variant; `_sha` 2 single variants; `_utc_now` 1 single variant.

## research_framework_phase2a_qualify_matrix_2026-09-14
- When (UTC): 2026-09-14 (see MANIFEST.csv timestamps)
- Purpose: Phase 2 (QUALIFY-family scope loop). New `src/research/qualify_matrix.py` — `csv_map(cfg, instruments)`
  and `winning_control(per_by_hyp, control_names, scope_instruments, agg, cost)`, copied verbatim from the AST-identical
  `_csv_map` (variants b83c62316c / 08e71a58eb — two spellings of the SAME computation, one assigns `Path(cfg.data_dir)`
  to a local first, the other inlines it) and `_winning_control` (variant 7c421cd3a9) copies found across
  `scripts/research/qualify_*.py`. Adds no statistics — only calls `research.qualification._net_rrs` +
  `EdgeAggregator.aggregate`, exactly as every replaced copy did. This batch: `_csv_map` in 5 `csv_map`-only drivers
  (`qualify_carry`, `qualify_cross_sectional`, `qualify_harvest`, `qualify_regime_conditioning`,
  `qualify_regime_transition`) → same-named import.
- Manifest: archive/research_framework_phase2a_qualify_matrix_2026-09-14/MANIFEST.csv (1 `created` row for the new
  module + 5 files × copied_before_edit/edited_in_place)
- Deletes: none

## research_framework_phase2b_qualify_matrix_2026-09-14
- Purpose: Phase 2 continued — `_csv_map` + `_winning_control` in the 6 drivers that use both
  (`qualify_fx_metals`, `qualify_htf` [`_winning_control` only — its own `_csv_map` takes a `tf` arg, NOT a duplicate,
  left local], `qualify_m5_straddle`, `qualify_majors`, `qualify_transitions`, `qualify_weekly_sweep`) → same-named
  imports of `research.qualify_matrix.csv_map` / `.winning_control`.
- Manifest: archive/research_framework_phase2b_qualify_matrix_2026-09-14/MANIFEST.csv (6 files, 11 helper defs)
- Deletes: none

### Phase 2 parity evidence (both batches)
- Edit tool's AST-normalized-body fingerprint gate (same mechanism as Phase 1) refused any def not byte-identical
  in structure to the approved variant — this IS the primary correctness proof: the two functions are not merely
  "similar", their AST dumps (modulo the docstring) are equal, i.e. the exact same sequence of operations.
- `--help` stdout SHA-256 + exit code identical before/after for all 11 CLIs.
- Identity: in every edited module the private name `is` the shared `research.qualify_matrix` function (17/17).
- New floor `tests/research/test_qualify_matrix.py` (6 tests) pins both shared functions against VERBATIM copies of
  every replaced variant on realistic inputs (matching/excluding/no-match/empty instruments; single-scope and
  empty-controls `winning_control`, real `Outcome`/`Signal`/`CostModel`/`EdgeAggregator` objects — not mocks).
- **End-to-end corpus A/B** (executes the ARCHIVED byte-exact original and the LIVE edited file, each loaded at the
  live path so relative imports/`__file__` match, same argv): `qualify_carry.py --out {tmp}` and
  `qualify_majors.py --out {tmp}` both original and live runs exit 1 at the IDENTICAL line — a pre-existing,
  unrelated repo precondition (`data/BNBUSDT_M15.csv` has no human-reviewed clock provenance,
  `data_ingestion.clock_registry.require_reviewed_clock`, F-066) — with byte-identical (empty) output trees. This
  confirms `csv_map` runs identically inside the real driver up to that gate for both AST variants; only
  `data/mt5/XAUUSD_M15.csv` is clock-reviewed in this repo and no touched driver's dedup'd function uses it
  (`qualify_xauusd.py`'s loader is the differently-named, untouched `_guarded_csv_map`), so a full successful run of
  a dedup'd driver was not obtainable without a separate, out-of-scope governance action (reviewing a corpus clock)
  — recorded honestly rather than forced. `winning_control` is not reached by this A/B (the crash precedes it); its
  parity rests on the AST-identity proof + the dedicated unit tests above.
- `tests/research/test_carry.py` + `test_harvest.py` + `test_qualify_matrix.py` + `test_provenance_helpers.py`: 29/29 green.

### Phase 2 total
- 11 files, 17 private helper defs (`_csv_map` ×10, `_winning_control` ×6 — `qualify_fx_metals`/`qualify_m5_straddle`/
  `qualify_majors`/`qualify_transitions`/`qualify_weekly_sweep` carry both) replaced by same-named imports of 2 shared
  functions in `src/research/qualify_matrix.py`.
- Left local on purpose (different signature/behavior, confirmed by fingerprinting — NOT folded in):
  `_csv_map` unique in `qualify_htf.py` (extra `tf` arg, resamples `{TF}` in the pattern) and `qualify_shape_xauusd.py`
  (no args, hardcoded XAUUSD); `_winning_control` unique in `qualify_interpreter.py`, `qualify_shape_xauusd.py`,
  `qualify_xauusd.py`, `qualify_zone_topk.py` (each a different signature/reduction). `_print_table` / `_run_family`
  fingerprinted too (per-driver inventory) — every variant across all 15 `qualify_*.py` files is UNIQUE (each driver's
  report shape/config differs genuinely), so nothing was extracted there; left local.

## research_framework_phase3a_mc_kit_2026-09-14
- When (UTC): 2026-09-14 (see MANIFEST.csv timestamps)
- Purpose: Phase 3 (sealed-contract kit, user-approved design pivot after Phase 2 reached the QUALIFY-family
  dedup ceiling). New package `src/research/mc_kit/` — `bars.py` (`load_bars`, `parse_ts_iso19`), `trade.py`
  (`walk_horizon`, `exit_kind`), `stats.py` (`trade_stats`, `arm_cells`, `sign`) — built ONLY from logic proven
  identical by reading every target driver in full (not assumed from name similarity; the plan's original
  `TradeContractSpec` template was dropped after reading showed `_signal` construction and `verdict`/gate logic
  differ per contract for real reasons, not copy-paste). `src/research/costs.py` extended (additive) with
  `xau_measured_cost_model()`, replacing the byte-identical `_XAU_COST` `ComponentCostModel` literal duplicated in
  `mother_range/driver.py` and `sujan_crt/driver.py`.
- Manifest: archive/research_framework_phase3a_mc_kit_2026-09-14/MANIFEST.csv (4 `created` rows for the new
  package + 1 `costs.py` copied_before_edit/edited_in_place pair)
- Parity: `tests/research/test_mc_kit.py` (22 tests) pins every kit function against a VERBATIM copy of every
  driver body it replaces, including the two `_arm_cells` variants that compute the SAME result via a DIFFERENT
  statement sequence (mother_range_prior inlines `ea`/`ed`/list-comps in the return; magnitude_prior precomputes
  `contrast`/`pos_a`/`pos_d` as locals first) — proven equal by output comparison, not AST identity.
- Deletes: none

## research_framework_phase3b_mc_kit_migrate_2026-09-14
- Purpose: Migrate the two trade-contract drivers to `research.mc_kit` + `research.costs.xau_measured_cost_model`:
  `mother_range/driver.py` (`load_bars`/`_parse_ts`/`_walk`/nested `_stats`/`_XAU_COST` -> kit imports; dropped the
  now-dead `import csv`) and `sujan_crt/driver.py` (same, plus `_sha256` -> `research.provenance.sha256_file`
  (Phase 1's shared helper — this file was outside Phase 1's `scripts/` scan scope but carries the identical
  duplicate body), plus 3 inline `exit_kind = "SL_HIT" if ... else (...)` ternaries at net-R call sites ->
  `_exit_kind(out.outcome)`). `_signal`, split scheme, controls, and gate/verdict logic in both files are
  UNTOUCHED — genuinely per-contract, not extracted.
- Manifest: archive/research_framework_phase3b_mc_kit_migrate_2026-09-14/MANIFEST.csv (2 files)
- Parity — the real gate for this batch (hand-edited code, not a mechanical AST swap): **every artifact each
  driver writes, re-run after the edit, byte-identical to that same driver's own pre-edit run** (captured
  separately as a Step-0 baseline before any kit code existed): `mother_range` — `metrics.json`, `ledger.jsonl`
  (299 rows), `split_manifest.json`, `report.md` all diff_lines=0. `sujan_crt` — `metrics.json`, `ledger.jsonl`
  (6,221 rows), `population_fingerprint.json`, `split_manifest.json`, `report.md` all diff_lines=0 (full 2m20s
  run incl. the 100-seed random-entry control). Verdicts unchanged (`DIAGNOSTIC_PASS_NOT_ECONOMIC` holdout_n=59;
  `REJECT` holdout_n=80 detected=6256) and match the values `docs/current-findings.md` F-090/F-095 already
  record. Both drivers' own committed baseline (`docs/research-readiness/sujan_crt/...`,
  `docs/research-readiness/mother_range_...`) was independently byte-verified against the SAME Step-0 run before
  any edit (sujan_crt: exact; mother_range: numbers exact, JSON *shape* differs — that committed file predates
  fields the current, unedited driver already adds (`corpus`, `corpus_sha256`, `ledger_n`) — a pre-existing
  schema-drift artifact, unrelated to and unchanged by this migration, reported not fixed).
  `tests/research/test_mother_range_prior.py` + `test_visual_crt_prior.py` (isolation floors covering
  `mother_range.driver`) green.
- Deletes: none

## research_framework_phase3c_mc_kit_migrate_priors_2026-09-14
- Purpose: migrate `mother_range_prior.py` to `research.mc_kit` (`load_bars`, `arm_cells`); dropped the
  now-dead `import csv` and the now-unused `_mean` import from `research.evidence.queries`.
- Manifest: archive/research_framework_phase3c_mc_kit_migrate_priors_2026-09-14/MANIFEST.csv (2 files)
- **A real bug was caught here, not just a formatting drift.** The end-to-end byte-identity re-run (against the
  Step-0 baseline captured earlier) showed `holdout_s_contrast=-0.8093092929292931` vs the baseline's
  `...2927` — a last-bit float divergence in `metrics.json`. Root cause: `mother_range_prior._arm_cells` (and
  `magnitude_prior._arm_cells`) call `_mean`, which is `research.evidence.queries._mean` — a wrapper around
  `statistics.mean` (exact `Fraction`-based summation) — NOT a naive mean. `mc_kit.stats._mean` had been
  written as naive `sum(xs)/len(xs)`, which the small synthetic unit tests in `test_mc_kit.py` could not
  distinguish from `statistics.mean` (both give the same answer on those inputs) but which silently diverged
  on the real ~300-row corpus. Fixed `mc_kit/stats.py` to use `statistics.mean`; added
  `test_arm_cells_mean_matches_statistics_mean_not_naive_sum` (a planted, verified-divergent 50-value input,
  `random.Random(0)` seeded) so this class of bug fails a UNIT test the next time, not only an end-to-end run.
  Re-ran `mother_range_prior`: `metrics.json`/`population_fingerprint.json`/`split_manifest.json` now all
  diff_lines=0 against Step-0.
- **Ledger note on this fix itself**: `stats.py` was `created` (no archive copy needed — nothing to preserve)
  then edited twice in the same turn (add `arm_cells` use here, then fix the naive-sum bug) without an
  intermediate snapshot before the bug fix. Recorded as `edited_in_place` with `sha256_before` left blank and
  a reason explaining why: unlike the `costs.py` incident below, the buggy intermediate was never consumed by
  any artifact, commit, or downstream file — it existed only within this same edit sequence before the gate
  caught it — so there is no prior *state* to lose, only a hash to skip recording (honestly noted, not hidden).
- Deletes: none

## Correction: research_framework_phase3a_mc_kit_2026-09-14 — costs.py snapshot-ordering bug
- **Self-caught, 2026-09-14, while computing Step-5 ROI line counts.** The `costs.py` `copied_before_edit` row
  in `phase3a`'s own manifest was captured by running the snapshot tool AFTER the `Edit` tool had already
  applied `xau_measured_cost_model()` — so the archived "pre-edit" copy is byte-identical to the post-edit
  live file (both 362 lines; a ROI table showing `before=362/after=362` for a file that should have grown
  ~19 lines was the tell). Unlike the stats.py case above, this one DID have a real prior state worth
  preserving (`costs.py` existed before this session and is git-tracked). Recovered via
  `git show HEAD:src/research/costs.py` (nothing committed this session, so HEAD still held the truth;
  `git diff --stat HEAD -- src/research/costs.py` confirmed exactly the intended 19-line addition and nothing
  else). Fixed at the source: `phase3a`'s `MANIFEST.csv` gained a `correction` row explaining the mistake and
  a new `copied_before_edit` row (archive path `CORRECTED_pre_edit/src/research/costs.py`) holding the true
  343-line original. The original wrong row is left in place (its own claim — "these bytes hash to X" — is
  still true; append-only discipline, never rewrite). Verifier green after the fix (0 violations). Full
  account: `archive/research_framework_phase3a_mc_kit_2026-09-14/MANIFEST.md`.
- **Lesson applied for the rest of Phase 3** (and recorded in memory): snapshot BEFORE Edit/Write, never
  after — `phase3c`'s `mother_range_prior.py` snapshot was correctly taken first.

### Phase 3 total (so far)
- New package `src/research/mc_kit/` (4 files, 244 lines) + 1 `research/costs.py` extension (+19 lines); 2
  trade-contract drivers migrated (`mother_range` −53, `sujan_crt` −65) + 1 prior-contract driver
  (`mother_range_prior`, small), all byte-identical pre/post on every written artifact after the arm_cells fix
  above. Net line count is currently **positive** (the kit costs more than 3 migrations save) — amortizes only
  as more drivers migrate; see the plan file's ROI note. Remaining prior-contract drivers (`magnitude_prior`,
  `rnet_overlay`, `asymmetry_contract`) were read in full and found to share less than the plan assumed
  (`rnet_overlay` already imports `split_rows` from `magnitude_prior`; `verdict`/`overlay` differ by field
  name and required checks per contract) — migrating them is deferred, corrected scope recorded in the plan.
