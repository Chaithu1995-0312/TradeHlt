# research_framework_phase3a_mc_kit_2026-09-14

- Plan: research-framework consolidation, Phase 3 (sealed-contract kit)
- Policy: **no deletes** — new files recorded `created`; the one edited file (`costs.py`) copied byte-exact first

## Change

New package `src/research/mc_kit/`:

| File | Provides | Absorbs |
|---|---|---|
| `bars.py` | `load_bars(path, bar_cls, *, parse_ts, volume)`, `parse_ts_iso19` | `mother_range.driver`/`evidence.mother_range_prior`/`sujan_crt.driver` load_bars + _parse_ts |
| `trade.py` | `walk_horizon(sig, bars, *, horizon_bars, adverse)`, `exit_kind(outcome)` | `mother_range.driver`/`sujan_crt.driver` `_walk`; the repeated exit-kind ternary |
| `stats.py` | `trade_stats(rows)`, `arm_cells(rows, y_key)`, `sign(x)` | `mother_range.driver`/`sujan_crt.driver` `_stats`; `mother_range_prior`/`magnitude_prior` `_arm_cells`; `asymmetry_contract`/`magnitude_prior`/`mother_range_prior` `sign`/`_sign` |

`src/research/costs.py` (edited, additive): `xau_measured_cost_model()` returns the F-082 `ComponentCostModel`
literal that was byte-identical in `mother_range/driver.py` and `sujan_crt/driver.py`.

## Scope correction (recorded, not hidden)

The plan's original design included a `spec.py` (`TradeContractSpec` + `run_trade_contract`) meant to let a new
contract be "just a population function + a spec". Reading every target driver in full (not just grepping
names) showed this doesn't hold: `_signal` construction differs per contract (different source dataclass,
different zero-risk handling — `mother_range` raises, `sujan_crt` guards to `1.0`), and `verdict`/gate logic
differs per contract by design (different required checks, different vocabulary). Building a template over
that would either erase a real difference or need a construction DSL — new behavior-risk this task must not
take. `spec.py` was **not built**. See the plan file's ROI section for the corrected estimate.

## Parity evidence

- `tests/research/test_mc_kit.py` (22 tests): every kit function pinned against a VERBATIM copy of every
  driver body it replaces, run on the same inputs. Two `_arm_cells` variants (mother_range_prior vs
  magnitude_prior) compute the same result via different statement order — proven equal by output comparison
  (the test asserts the two originals themselves agree, then checks the kit against both).
- `xau_measured_cost_model()` field values asserted against the literal in both original drivers.

## Correction (2026-09-14, same session, self-caught)

The `costs.py` `copied_before_edit`/`edited_in_place` pair recorded above was captured in the wrong order:
`dedup_batch.py snapshot` ran AFTER the `Edit` tool had already applied `xau_measured_cost_model()`, so the
archived "pre-edit" copy is byte-identical to the post-edit live file (343→362 lines was NOT what got
archived as "before" — a 362-line copy was, wrongly). Caught while computing the Step-5 ROI line-count table
(before=362/after=362 for a file that should have grown by ~19 lines was the tell). No data was ever actually
lost — nothing is committed this session, so `git show HEAD:src/research/costs.py` still held the true
pre-edit state — but the archive copy meant to preserve it independently of git did not, until this fix.

Fixed at the source, not just noted here: `MANIFEST.csv` gained a `correction` row explaining the mistake and
a new `copied_before_edit` row (archive path `CORRECTED_pre_edit/src/research/costs.py`, sha256
`3931983...66b6e9a4`) holding the true 343-line original recovered from git HEAD. The original wrong row is
left in place — its own claim ("these archived bytes hash to X") is still true, it just doesn't represent the
real pre-edit state — per append-only discipline (never silently delete or rewrite a manifest row).
`scripts/maintenance/verify_archive_manifests.py` is green after the fix (0 violations).

**Lesson recorded in memory:** always run `archive_manifest.snapshot()` (or the batch tool's `snapshot`
command) BEFORE calling Edit/Write on a file — never after, even when the edit already happened moments
earlier in the same turn.
