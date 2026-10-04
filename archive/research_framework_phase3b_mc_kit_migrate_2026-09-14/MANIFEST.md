# research_framework_phase3b_mc_kit_migrate_2026-09-14

- Plan: research-framework consolidation, Phase 3 (sealed-contract kit), driver migration
- Policy: **no deletes** — both edited files copied byte-exact first

## Change

| File | Replaced with `research.mc_kit` / `research.costs` / `research.provenance` |
|---|---|
| `src/research/mother_range/driver.py` | `load_bars`, `_parse_ts` (kit `bars`), `_walk` (kit `trade.walk_horizon`), nested `_stats` (kit `stats.trade_stats`), `_XAU_COST` (`costs.xau_measured_cost_model()`); dropped the now-dead `import csv` |
| `src/research/sujan_crt/driver.py` | same, plus `_sha256` -> `research.provenance.sha256_file` (Phase 1's shared helper; this file was outside Phase 1's `scripts/`-only scan but carries the identical duplicate body), plus 3 inline exit-kind ternaries -> `_exit_kind(out.outcome)` |

`_signal`, split scheme, controls, and gate/verdict logic in both files are **untouched**.

## Parity evidence (the real gate — this is hand-edited code, not a mechanical swap)

Step 0 (before any edit in this batch) captured a baseline by running both drivers as they stood, into a
scratch directory, and byte-comparing every written artifact against the git-committed baseline:

| Contract | Artifacts | vs committed baseline |
|---|---|---|
| `mother_range` | `metrics.json`, `ledger.jsonl`, `split_manifest.json`, `report.md` | numbers exact; committed `docs/research-readiness/mother_range_..._metrics.json` predates fields the driver already adds (`corpus`, `corpus_sha256`, `ledger_n`) — pre-existing schema drift, unrelated to this migration |
| `sujan_crt` | `metrics.json`, `ledger.jsonl`, `population_fingerprint.json`, `split_manifest.json` | byte-identical |

After the edit, each driver was re-run and every artifact byte-compared against **its own Step-0 output**:

| Contract | Result | Wall time |
|---|---|---|
| `mother_range` | `metrics.json`/`ledger.jsonl`/`split_manifest.json`/`report.md` all diff_lines=0; verdict `DIAGNOSTIC_PASS_NOT_ECONOMIC` holdout_n=59 unchanged | 4.9s |
| `sujan_crt` | `metrics.json`/`ledger.jsonl` (6,221 rows)/`population_fingerprint.json`/`split_manifest.json`/`report.md` all diff_lines=0; verdict `REJECT` holdout_n=80 detected=6256 unchanged | 2m20s (100-seed random-entry control) |

Both verdicts match the values already recorded in `docs/current-findings.md` (F-090, F-095).

Also green: `tests/research/test_mother_range_prior.py` (the `mother_range.driver` isolation-boundary AST scan)
and `tests/research/test_visual_crt_prior.py`.
