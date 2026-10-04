# research_framework_phase3c_mc_kit_migrate_priors_2026-09-14

- Plan: research-framework consolidation, Phase 3 (sealed-contract kit), prior-contract migration
- Policy: **no deletes** — edited file copied byte-exact first

## Change

`src/research/evidence/mother_range_prior.py`: `load_bars` -> `research.mc_kit.bars.load_bars`; `_arm_cells`
-> `research.mc_kit.stats.arm_cells`. Dropped the now-dead `import csv` and the now-unused `_mean` import
from `research.evidence.queries`. `unit_rows`/`split_rows`/`verdict`/`fingerprint`/`measure`/`run` untouched.

## A real bug, caught and fixed (not hidden)

First re-run after the edit showed a last-bit float divergence vs the Step-0 baseline
(`holdout_s_contrast` `...2931` vs `...2927`). Cause: `_arm_cells` calls `_mean`, which in the ORIGINAL file
is `research.evidence.queries._mean` — `statistics.mean` (exact `Fraction`-based summation), not naive
`sum(xs)/len(xs)`. `mc_kit.stats._mean` had been written naive; small synthetic unit tests could not tell
the two apart, the real ~300-row corpus could. Fixed `mc_kit/stats.py` to use `statistics.mean`; added a
regression test with a planted, verified-divergent input so the bug class fails a unit test next time.

## Parity evidence

- Re-run after the fix: `metrics.json`, `population_fingerprint.json`, `split_manifest.json` all
  diff_lines=0 against the Step-0 baseline (captured before Phase 3 touched anything). Verdicts unchanged
  (`arm_s=INSUFFICIENT arm_t=INSUFFICIENT n_entries=320`), matching `docs/current-findings.md` F-094.
- `tests/research/test_mc_kit.py` (23 tests, incl. the new naive-vs-exact-mean regression) green.
