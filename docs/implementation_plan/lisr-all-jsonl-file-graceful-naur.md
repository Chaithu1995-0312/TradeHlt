# End-to-End Proof of the Parquet Projection on the Real XAUUSD Corpus

## Context

The Tier-1 projection layer is built and unit-tested (`src/utils/parquet_store.py`,
`scripts/maintenance/jsonl_to_parquet.py`, 15/15 tests green), but **every measurement so far
ran on scratchpad copies**. Nothing in the repository has been converted, and no reader has
ever actually taken the Parquet fast path on real data. That is the gap this plan closes.

A backtest was then run on the XAUUSD corpus (`run_20260822_162108_XAUUSD`), producing fresh
artifacts and a useful — but easily over-read — signal.

**What the run does prove:** it is **byte-identical** to `run_20260819_004755_XAUUSD` on the
same config across all four artifacts (`XAUUSD_events.jsonl`, `XAUUSD_crt_telemetry.jsonl`,
`XAUUSD_trades.csv`, `XAUUSD_summary.json`). The spine is deterministic.

**What it does NOT prove (stated so it is not silently assumed):** it is *not* evidence the
Parquet changes are safe. None of the three migrated modules — `replay_memory_engine`,
`timing_reconstructor`, `structural_event_source` — are imported anywhere on the backtest
path (grep-verified against `backtest_v2.py`, `engine_runner.py`, `crt_engine_v2.py`), and no
projections exist in the repo, so **none of the changed code ran**. The missing evidence has
to be built directly, which is step 3 below.

**Also measured, incidentally:** that single backtest appended **+1.32 MB** to
`crt_transitions.jsonl` and +8.7 KB to `integrity_events.jsonl`. The six unrotated monoliths
now total **13.12 GB**; the tree is at 30.45 GB. Out of scope here, but it is the standing
Tier-0 lever and it grows every run.

---

## Scope

Convert four real XAUUSD corpora **in place** (sidecars beside each source; sources never
modified) and prove a real reader is unaffected. Chosen to cover both the fresh run and the
two families with a genuine consumer and the largest measured query win:

| Target | Size | Family handling | Why this one |
|---|---:|---|---|
| `results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/XAUUSD_events.jsonl` | 1.8 MB | partition by `event` | The fresh run |
| `…/run_20260822_162108_XAUUSD/XAUUSD_crt_telemetry.jsonl` | 1.6 MB | partition by `kind` | The fresh run; sparse-union case |
| `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl` | 121.2 MB | skip `run_header` row | **Has a real migrated reader** (`replay_memory_engine`); 18.3x measured |
| `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl` | 285.1 MB | flatten `features`, `feature_vector` as `list<double>` | The 27.1x case; 35 columns |

All four verified stable with no concurrent writers at plan time.

**Honest caveat on the two fresh-run files:** their consumers do not read them.
`spine_signal_source.py:202` reads `XAUUSD_trades.csv`, not the JSONL, and
`structural_event_source` globs events files produced by a *different* runner
(`execution_planner_replay._run_backtest`). Converting them is a demonstration on genuinely
fresh output, not an operational speedup. The operational case rests on the other two.

---

## Steps

### 1. Convert, with the round-trip gate on

```bash
venv/Scripts/python.exe scripts/maintenance/jsonl_to_parquet.py \
  "results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/XAUUSD_events.jsonl" \
  "results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/XAUUSD_crt_telemetry.jsonl" \
  "logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl" \
  "results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl" \
  --verify
```

`--verify` reconstructs every record and compares it to the source. Any `MISMATCH` stops the
plan — that is the gate that already caught the absent-key-vs-explicit-null bug.

### 2. Confirm the sources were not touched

Capture `sha256` + size of all four sources **before** step 1 and re-check after. The
projection is additive by construction; this proves it rather than asserting it.

### 3. Real-reader parity — the evidence the backtest could not give

Exercise `ReplayMemoryEngine._parse_jsonl` against the real 121 MB
`opportunities.jsonl` twice: once with the projection FRESH (takes the Parquet fast path
added in `_parse_jsonl`) and once with the sidecar temporarily renamed (falls back to the
raw line-numbered path). Compare `ReplayRecord`s field-by-field.

Two traps to design around, both of which would produce a green-but-meaningless result:

- **Vacuity.** Record timestamps in this corpus are `2024-05-…`, roughly 2.3 years old, and
  `_parse_jsonl` drops anything older than `2 × staleness_threshold_days` (default 90 ⇒ 180
  days). A naive run compares `[] == []` and passes. Construct the engine with a large
  `staleness_threshold_days` (e.g. 5000) and **assert a non-vacuity floor** (record count > 0
  and equal on both paths) before comparing.
- **Identity comparison.** `ReplayRecord` uses `__slots__` with no `__eq__`, so `==` is
  identity. Compare via `{f: getattr(r, f) for f in ReplayRecord.__slots__}`.

Do the same seam check for the fresh events file using the exact column set
`structural_event_source` requests — `["event", "state_to", "timestamp"]` — against a plain
JSONL parse applying that module's own `event == "STATE_TRANSITION"` filter. `harvest()`
itself runs a backtest internally, so the seam is what is testable without a second run.

### 4. Measure on real data and record it

Per family: `bytes_in` / `bytes_out`, and a column-pruned read timed against the JSONL
baseline. Compare each against **gzip on the same file** — gzip is the alternative Parquet
has to beat, and on `crt_telemetry` it previously won (0.88x). Record what is measured, not
what was expected.

### 5. Close out

Append the §6 SESSION LOG entry to `assistant_project.md`, and update
`project_jsonl_parquet_projection.md` to replace "nothing in the repo has actually been
converted" with the real result.

---

## Files

No new modules. Existing, already-tested code does the work:
`src/utils/parquet_store.py` (`compact_jsonl`, `iter_records`, `verify_projection`),
`scripts/maintenance/jsonl_to_parquet.py`.

Additions are limited to two parity tests appended to `tests/test_parquet_store.py`
(marked to skip when the real corpora are absent, so the floor stays green on a clean clone),
plus the log/memory updates in step 5.

New untracked sidecars: four `*.parquet` (file or dataset dir) + four
`*.parquet.manifest.json`, beside their sources under gitignored `results/` and `logs/`.

---

## Verification

1. Step 1 reports `VERIFIED  mismatches=0` for **all four** files.
2. Step 2 shows all four source hashes unchanged.
3. Step 3 passes **with the non-vacuity floor asserted** — a passing test on zero records is
   treated as a failure of the test, not a success of the code.
4. `venv/Scripts/python.exe -m pytest tests/test_parquet_store.py tests/replay/ -q` — expect
   17 passed in the new file and `tests/replay/` unchanged at 52 passed with the same **5
   pre-existing failures** (`test_assign_cluster` ×4, `test_cluster_stats_built`), which were
   confirmed failing on HEAD before any of this work.
5. Rollback is `rm` on the eight sidecar paths; every reader returns to the JSONL source
   automatically, since `projection_status` reports `ABSENT` and `iter_records` falls back.

## Risks

- **Concurrency** (`MEMORY.md`: ~15 sessions share this repo). Sidecars are additive and
  sources are untouched, so a concurrent run cannot be corrupted. Never `git add -A`.
- **A future backtest overwrites the run dir** ⇒ its projection goes `STALE` ⇒ readers
  silently fall back to JSONL. Correct behaviour, but invisible; no `--refresh-if-stale`
  sweep exists yet. Worth noting in the log rather than building now.
