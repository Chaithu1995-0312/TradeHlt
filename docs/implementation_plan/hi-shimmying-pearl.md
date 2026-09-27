# Research-Framework Consolidation — Phase 4: shared script entrypoint + report/manifest writer

## Context
The user asked to "build a custom framework combining both" `src/research/` (the library) and
`scripts/research/` (the CLI layer), to cut down boilerplate duplicated across the ~163
argparse'd scripts in `scripts/research/` — config loading, cost-model wiring, output/report
writing.

Investigation shows this is **not** a new idea — it is an already-established, actively-numbered
initiative in this exact codebase: **"Research-framework consolidation"**, done in dated phases
on 2026-09-14 (docstrings + `archive/research_framework_phase*_2026-09-14/` are the record):

- **Phase 0** (`archive/research_framework_phase0_repair_2026-09-14/`) — repair pass.
- **Phase 1a–1e** — extracted `git_commit`/`sha256_file`/`utc_stamp_compact`/`utc_now_iso` into
  `src/research/provenance.py`, replacing ~59 byte-for-byte duplicated private helpers
  (`_git_commit` ×18, `_sha256`/`_sha256_file`/`_sha` ×33, `_utc`/`_utc_now` ×4+4) across
  `scripts/analysis/` and `scripts/research/`. Parity-pinned by
  `tests/research/test_provenance_helpers.py` against VERBATIM copies of every original.
- **Phase 2a–2b** — extracted `research.qualify_matrix.csv_map` / `winning_control`, removing
  byte-for-byte duplicated scope-loop code across 6–10 `qualify_*.py` drivers.
- **Phase 3a–3c** — built `research.mc_kit` (shared CSV-load/forward-walk/exit-classify/per-cell-
  stats primitives for the sealed-contract `MC-*` drivers: `mother_range.driver`, `sujan_crt.driver`,
  `evidence.mother_range_prior`, `evidence.magnitude_prior`). **Its own docstring records a
  directly relevant lesson** ("SCOPE HONESTY"): the original design imagined a full
  `TradeContractSpec` template so a new contract could be "just a population function + a spec" —
  reading every target driver in full showed that does **not** hold, because `_signal`
  construction and verdict/gate vocabulary differ **by design** per contract. Forcing them into
  one template would either silently drop a real distinction or require a risky Signal-
  construction DSL. The kit was scoped down to only the pieces *provably* identical by output
  comparison, not name similarity.

Measured with a live grep sweep before writing this plan:
- Only **5** scripts still hand-roll their own `git_commit`/`_sha256`/`_utc` instead of importing
  `research.provenance` (`build_bar_matrix.py`, `path_ambiguity_census.py`, `run_h_msip_002.py`,
  `xauusd_mt5_cost_calibration.py`, `zone_x_o4_gap_study.py`) — Phase 1 is ~87% adopted already.
- **36** scripts already import `research.provenance`.
- **88** argparse'd scripts import neither `research.provenance` nor an equivalent — some
  genuinely don't need it (read-only inspection scripts), some hand-roll an ad-hoc report+manifest
  write (e.g. `build_rare_zone_detection_eval.py` already writes a `jp`/`mp` two-file split by
  hand, mirroring `research.cli.cmd_run`'s own `edge_report.json` + `run_manifest.json` split —
  independently reinvented, not shared).

So the real, honest gap is narrower than "163 scripts need a framework": Phase 1–3 already solved
config loading (`ResearchConfig`), cost-model wiring (`CostModel`/`ComponentCostModel` bound once
in `HypothesisRunner.__init__`), and the qualify-family's scope loop. What's left and genuinely
undeduplicated is the **output/report-writing split** (deterministic artifact vs. wall-clock
manifest) that many scripts hand-roll differently, plus the 5 provenance stragglers.

**Applying the mc_kit lesson to this plan**: do not build a generic `ScriptRunner` base class that
scripts must subclass — that repeats the exact over-abstraction Phase 3 explicitly rejected.
Instead, add one small, optional, provably-reusable **function**, migrate the 5 real stragglers
onto Phase 1's existing primitives, and pilot the new function on a few representative scripts
with byte-identical-output parity proof — the same "read every target in full before generalizing"
discipline Phase 1–3 used, and the same incremental-and-proven approach CLAUDE.md §6.5 (Config-
First Doctrine) requires (`Evidence > Doctrine`; parity proof before generalizing).

## Approach — Phase 4

### Step 1: `research.provenance.write_report()` (the one new shared primitive)
Add one function to `src/research/provenance.py` (same module Phase 1 already extended, not a
new file/package):
```python
def write_report(out_dir: Path, payload: dict, *, run_id: str | None = None,
                  extra_manifest: dict | None = None) -> tuple[Path, Path]:
    """Write payload -> report.json (deterministic, no wall-clock) + a sibling
    run_manifest.json (run_id/generated_at/git_commit/environment). Mirrors the split
    research.cli.cmd_run already writes by hand. Returns (report_path, manifest_path)."""
```
Reuses `git_commit()`, `utc_now_iso()`, `utc_stamp_compact()` — already in this same module.
No new dependency, no new module, no subclassing required of callers.

### Step 2: fix the 5 genuine provenance stragglers
For each of `build_bar_matrix.py`, `path_ambiguity_census.py`, `run_h_msip_002.py`,
`xauusd_mt5_cost_calibration.py`, `zone_x_o4_gap_study.py`:
1. Read its local `_git_commit`/`_sha256`/`_utc*` implementation in full.
2. Add it to `tests/research/test_provenance_helpers.py` as a VERBATIM-copied `_orig_*` variant
   (the exact method already used for the other ~60 replaced copies) and assert it matches
   `research.provenance`'s shared function on the same inputs.
3. Replace the local def with the shared import. Byte-identical behavior, mechanical diff.

### Step 3: pilot `write_report()` on 3 representative scripts (not all 163)
One from each genuinely different family, so the pilot actually tests generality rather than
one easy case:
- `scripts/research/build_rare_zone_detection_eval.py` (a `build_*_eval.py` probe with its own
  hand-rolled `jp`/`mp` two-file write)
- `scripts/research/run_h_msip_002.py` (already touched in Step 2, and a `run_h_*` harness)
- one `qualify_*.py` script's non-M4 output write, if one hand-rolls it outside `research.cli`
  (else substitute another standalone diagnostic, e.g. `scripts/research/gaussian_rr_scatter.py`)

For each: capture its current output byte-for-byte on a small fixed input BEFORE the change,
migrate to `write_report()`, re-run, diff — must be byte-identical (same discipline as Phase 1–3's
own parity tests). If a script's shape genuinely can't fit `write_report()` without dropping a
real field, that is itself the finding (mc_kit's own lesson) — leave it un-migrated and say why,
rather than force it.

### Step 4: document the lineage, do not promise full migration
Add a one-paragraph "Phase 4" entry to `src/research/provenance.py`'s module docstring (matching
how Phase 1/2/3 already self-document their own history there) recording what Phase 4 covers and,
explicitly, that migrating the remaining ~125 scripts is **future, optional, mechanical, one-script-
at-a-time cleanup** — not committed work in this pass. This avoids the config-entropy-explosion /
optimization-theater trap CLAUDE.md §6.5 warns about.

### Step 5: Jira bookkeeping (continuing this session's coverage work)
File one story under epic 41 (where this session already placed STORY-41.63, the Phase 2/
qualify_matrix owner) for Phase 4 itself, e.g. `STORY-41.69`, citing `src/research/provenance.py`,
`tests/research/test_provenance_helpers.py`, and the 3 piloted scripts. Not a new epic — Phase
2/3's ownership is already scattered across existing stories with no dedicated consolidation epic,
so this follows the same placement precedent rather than inventing a new umbrella.

## Files touched
- `src/research/provenance.py` — add `write_report()`; extend the module-docstring lineage note.
- `tests/research/test_provenance_helpers.py` — add the 5 stragglers' VERBATIM originals +
  parity assertions; add a parity test for `write_report()` against the pilot scripts' prior output.
- `scripts/research/build_bar_matrix.py`, `path_ambiguity_census.py`, `run_h_msip_002.py`,
  `xauusd_mt5_cost_calibration.py`, `zone_x_o4_gap_study.py` — replace local helpers with the
  shared import (mechanical).
- `scripts/research/build_rare_zone_detection_eval.py` + 2 more pilot scripts — migrate their
  output-writing call to `write_report()`.
- `multi_llm/build_queue.jsonl` — one new story (Step 5).

## Explicitly out of scope this pass
- No generic `ScriptRunner`/base-class abstraction (rejected per the mc_kit precedent).
- No migration of the other ~125 scripts — left as documented future one-off cleanup.
- No change to `research.qualify_matrix`, `research.mc_kit`, `HypothesisRunner`, `ResearchConfig`,
  or `CostModel` — those are Phase 2/3's already-proven abstractions, untouched here.

## Verification
- `tests/research/test_provenance_helpers.py` — full file green, including the 5 new parity pins
  and the `write_report()` pin (byte-identical `report.json`/`run_manifest.json` shape vs. each
  pilot script's pre-migration output on the same fixed input).
- Re-run each of the 5 migrated stragglers + 3 pilot scripts on their existing small/fixture
  inputs (not the full 2-year corpus) and diff stdout/output files against a pre-change capture.
- `python scripts/maintenance/check_governance_invariants.py --all` — record before/after failed
  count, confirm no new red (per CLAUDE.md §1.5 baseline discipline).
- No `src/` production/spine files touched — this is entirely inside `src/research/` (research-
  only, `Authority: research only` per CLAUDE.md §6.5's Authority Ladder) and `scripts/research/`.
