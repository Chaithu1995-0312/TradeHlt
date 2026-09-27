# Phase 3: corpus-read migration — ratchet-lint now, manual adjudication of the real 212

## Context

The user instructed "proceed with Phase 3." Before executing, I re-ran the census (it was
stale — concurrent sessions had been touching the repo throughout) and found the true count
had moved: `UNKNOWN` 208 → **212**, `CORPUS` unchanged at 6, files scanned 1,608 → 1,614.
Small drift, but confirms re-verification was warranted (CLAUDE.md §1.1).

I also found the 212 count is partly a tool-precision artifact — my census's taint tracer
never visits `ast.With`, so `src/runtime/backtest_v2.py:782` (`CandleLoader.stream()`'s own
`csv.reader(f)`, where `f` comes from `with open(self.filepath, ...) as f:` and
`self.filepath` is unambiguously gated) is misclassified `UNKNOWN`. ~60 of 212 share that
exact shape. I recommended fixing the tool before adjudicating by hand.

**Both recommendations were considered and explicitly overridden:**

| Decision | I recommended | User chose |
|---|---|---|
| Lint timing | Wait for the real backlog to hit zero, keep the original "empty allowlist, no ratchet" decision | **Ratchet now**, pinned to today's corrected count — this *reverses* that earlier decision, not a fresh one; recorded here rather than silently overwritten (§6.2 rule 4) |
| Tool fix vs. manual work | Fix the with-statement/argparse gaps first (cheap, resolves ~60+ sites for free) | **Skip the tool fix — adjudicate all 212 by hand**, including the ones a fix would resolve automatically |

Proceeding on both as instructed. One clarification, not a re-litigation: "skip the tool fix"
means I won't spend time automating the classifier — it does not mean discarding what I
already know by having read the code. `backtest_v2.py:782` gets adjudicated correctly
(already gated, no migration needed) using the manual judgment "adjudicate individually" was
always going to require anyway; I'm just not pretending I don't already know the answer.

**Honest scope note:** 212 individual manual judgments is not a single-turn task. This plan
sequences it into directory-sized batches with `src/` first (53 sites, highest production
value) as this wave's concrete deliverable, not a promise to clear all 212 in one pass.

---

## Wave 1

### 1. Build and wire `corpus_read_lint.py` — shrink-only ratchet, pinned to today

Same pattern as the existing `feature_math_lint.py` ratchet (this repo's own precedent, not
a new invention): a tracked allowlist snapshot, lint fails on anything outside it, shrinking
the allowlist is always fine, growing it never is.

- `docs/governance/corpus_read_allowlist.json` — every current `CORPUS` (6) and `UNKNOWN`
  (212) finding as a `{file, line, call}` triple, generated from today's manifest. `GATED`
  and `DERIVED` sites are never listed — they're always permitted, ratchet or not.
- `scripts/analysis/corpus_read_lint.py` — re-runs the same AST classification
  `corpus_read_census.py` already implements (reuse its functions, don't fork them) and
  fails if any `CORPUS`/`UNKNOWN` finding exists that isn't in the pinned allowlist. A
  removed entry (migrated or reclassified) shrinks the allowlist in the same commit — the
  lint doesn't require a separate "update the pin" step, it just re-snapshots to whatever's
  left after real migrations land.
- Wire into `scripts/maintenance/check_governance_invariants.py` (`GREEN_FLOOR`) and the
  pre-commit hook path, per CLAUDE.md §1.5's existing hook==CI-by-construction pattern.
- SITS-register the new script (§3.1 item 1b, same chain as `corpus_read_census.py` earlier
  this session: `script_census.py --write-stubs` → `seed_script_registry.py` overlay →
  `generate_script_matrix.py` → grandfather-pin resync).

### 2. Migrate the 6 confirmed `CORPUS` sites

`feature_38_lineage_census.py:668`, `feature_pipeline_fc05_closure.py:1093`,
`bnbusdt_enrich_trades.py:33`, `momentum_continuation_bnbusdt.py:969`,
`test_chart_series.py:284`, `test_shape_hypothesis_pit.py:81`. Each: read the surrounding
code to see what it actually does with the rows, swap the read for `corpus_store.read()`
(building the cache first if the instrument/timeframe pair doesn't have one yet), and verify
at a depth matching what the script does — a census script needs a row-count/column check,
a script computing real statistics needs a value comparison. No blanket "byte-identical,
unverified" claim.

### 3. Remove `--xlsx`/`--csv` from `xauusd_excel_feature_state_trace.py`

As originally planned — independent of the census-count question, low-risk, in scope.

### 4. Begin manual adjudication: `src/` first (53 sites today)

Per-file, per-line: read the surrounding code, determine `GATED` (already safe, tool just
couldn't see it — e.g. the with-statement class), `DERIVED` (not actually a corpus read —
e.g. a trained-model artifact, a trace JSONL, a manifest), or genuine `CORPUS` (migrate to
`corpus_store.read()`). Every reclassification shrinks `corpus_read_allowlist.json` in the
same commit. Known already from this session's own reading:
- `backtest_v2.py:782` → `GATED` (self.filepath, established above).
- `data_ingestion/clock_detector.py:110,117` → stays an **annotated exception**, not
  migrated — it inspects raw bytes to *establish* clock provenance, so it structurally
  cannot depend on the gate that requires clock provenance to already exist.
- `data_ingestion/corpus_store.py:330` → the builder/reader itself, annotated exception.
- `data_ingestion/dataset_integrity.py:536` → almost certainly `GATED` internally (it's
  `_stream_candles`, the function `admit_corpus`/`validate_dataset` already call) — verify,
  don't assume.

The remaining ~48 `src/` sites (governance, research, runtime, analytics, bitnet, inout,
llm_research, identity, replay) get the same per-file treatment in this wave.

**Explicitly sequenced, not started this wave:** `scripts/` (128 today), `tests/` (23),
`tools/` (2), 5 root-level scripts. Each becomes its own follow-up wave once `src/` is done,
same per-file discipline, same allowlist-shrink-per-migration pattern.

---

## Verification

- `corpus_read_lint.py` must fail on a deliberately reintroduced ungated read of a corpus
  path outside the allowlist, and pass on everything currently pinned — prove the shrink-only
  property by removing one allowlist entry and confirming the lint now fails if that site's
  code is reverted to an ungated read.
- Each of the 6 `CORPUS` migrations gets its own stated verification depth (see step 2) —
  reported per-file, not asserted in bulk.
- `src/` adjudication: for every site reclassified `GATED`, show the specific taint chain
  (which admission call, which attribute) that makes it safe — not just "looks fine."
- Re-run `tests/test_corpus_store.py` + the 37-test targeted suite after every batch of
  changes touching `runner.py`/`corpus_store.py`/`cli.py`.
- End-of-wave: re-run the census, report the new true count and the shrunk allowlist size.

## Deferred write

Plan mode blocks the §6 SESSION LOG append; the entry is drafted in-conversation and
persisted as the first action after approval.


---

## Wave 2 — 2026-09-18 (scanner correctness + full adjudication of the residual set)

### What moved

`corpus_read_lint.py` was **failing** (exit 1) on 36 findings outside the pinned allowlist.
After this wave it fails on 26, every one of which is now adjudicated below with evidence.

**1. Scanner-correctness fix — `corpus_read_census.scan_file` now reads `utf-8-sig`.**
CPython's own tokenizer accepts a leading BOM, so a BOM'd file is valid Python. Reading it
as plain `utf-8` made `ast.parse` raise on the U+FEFF, and the file surfaced as a
`<syntax-error>` UNKNOWN — i.e. as *an unresolved corpus read* — when the scanner had never
looked inside it. **58 tracked files carry a BOM** (PowerShell's `Out-File`/`>` default in
this environment), so the false-positive class was large.

Measured effect: findings 36 → 26 (**10 false positives removed**), pinned sites newly
parseable 4 → 9, and **4 genuine reads that had been hidden behind a parse failure were
revealed** (`jse003…:513`, `l003h…:57`, `ultron_sem_r_shadow.py:22`,
`_fresh_stamp_backtest.py:61`).

This is **not** the taint-precision fix (with-statement / argparse resolution) that this
plan deliberately declined in its decision table. That one re-classifies *real* reads; this
one stops the scanner inventing findings for files it never parsed. A genuine `SyntaxError`
still reports.

**2. Two BOM regressions fixed** (`src/identity/tokens.py`, `multi_llm/build_queue.jsonl`).
`git show HEAD:<path>` proves both were BOM-free when committed, so these are uncommitted
regressions, not part of the 56 files of pre-existing committed BOM debt (left untouched —
a separate decision). Exactly 3 bytes removed from each; no content touched. This also
cleared 5 unrelated reds in `tests/test_context_compiler.py`, which reads the queue as plain
`utf-8` (8 passed).

### Adjudication of all 26 residual findings

**CORPUS — genuine corpus reads, migration required (13).** Each resolves to
`data/mt5/XAUUSD_M15.csv`; most via a `Path` join (`_ROOT / "data" / "mt5" / …`) rather than
a single string literal, which is why the literal classifier could not resolve them.

| Site | Evidence |
|---|---|
| `_build_run_story.py:34,35` | module constant `CSV = 'data/mt5/XAUUSD_M15.csv'`, then `open()` + `csv.reader()` |
| `scripts/analysis/layer_trace/h5_feature_alignment.py:66` | `--csv` default is `REPO_ROOT / "data" / "mt5" / "XAUUSD_M15.csv"` |
| `scripts/analysis/phase1_shadow_create_economic_census.py:201` | `_csv_index_by_timestamp` is called at `:255` with `_CSV` = the corpus |
| `scripts/analysis/trade_intent_ownership_shadow.py:120` | `csv_path` is the corpus; same value feeds `load_from_csv(csv_path)` at `:153` |
| `scripts/research/ab_rr_slot_xauusd.py:107` | `CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"` (`:40`) |
| `scripts/research/l003h_trail_exit_transition_replay.py:57` | function is `load_candles(csv_path)` |
| `scripts/research/link001_choch_measurement.py:136,151` | `DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"` (`:61`) |
| `scripts/research/retest_divergence_probe.py:148,156` | `DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"` (`:88`) |
| `src/research/probes/corpus.py:13` | `load_corpus` parses `timestamp/open/high/low/close` |

**DEFERRED, with reason — `src/research/mc_kit/bars.py:46` (1).** Genuinely a corpus read,
and the single highest-value target: the 3 sites that shrank out of the allowlist this wave
(`mother_range/driver.py`, `sujan_crt/driver.py`, `evidence/mother_range_prior.py`) did not
become gated — they **relocated their read into this shared loader**, which is precisely the
ratchet catching a relocation. It is **not** migrated here because those drivers are the
sealed measurement contracts behind **F-090** (SEM-026 mother-range) and **F-095**
(SEM-031 Sujan), so changing how their population loads demands a value-parity proof, not a
swap. This plan's own verification rule forbids a blanket "byte-identical, unverified" claim.
Migration belongs in its own authorised turn.

**DERIVED — not corpus reads, no migration (11).**

| Site | Evidence |
|---|---|
| `scripts/analysis/phase1_resolver_replay_evidence.py:717,722` | `atlas_dir / "transition_decision.parquet"` / `"envelope_bar.parquet"` — atlas artifacts |
| `scripts/research/jse003_engine_context_history_path_geometry.py:513` | `anatomy_path` — trade-anatomy artifact |
| `scripts/research/ultron_sem_r_shadow.py:22` | `read_csv(trades)` — a trades ledger |
| `src/governance/archive_manifest.py:175,307` | reads an archive **manifest** (`ManifestRow`, `_header_kind`, `ACTIONS` validation) |
| `src/research/probes/phase1_replay.py:126` | `read_table(bar_matrix_path, columns=["timestamp","trend_bias","atr_abs"])` — the derived bar-matrix parquet |
| `tests/test_report_writer_run_id_stamp.py:80,94,131` | reads the trades CSV the writer under test just wrote |
| `tools/_fresh_stamp_backtest.py:61` | `read_csv(trades[-1])` — a backtest trades output |

**TEST ORACLE — deliberate exception, never migrate (2).**
`tests/research/test_mc_kit.py:52,65` (`_orig_load_bars_required` / `_orig_load_bars_zero_default`)
are *verbatim copies* of the pre-consolidation `load_bars`, kept as independent parity
oracles proving `mc_kit.bars` is byte-identical to the originals it replaced. Migrating them
would destroy the oracle. These warrant a per-entry `note` on the allowlist (the field
`--regenerate` already carries forward) rather than a migration.

### Allowlist deliberately NOT regenerated

`--regenerate` re-snapshots to the live set. Today that is 217 − 9 shrunk + 26 new ≈ **234, a
growth of 17**, and the ratchet's own rule is that growing the list is never legitimate.
Regenerating now would launder 13 unmigrated corpus reads into the baseline. The allowlist is
left at 217 and the lint is left **failing on purpose** — that is the ratchet working, not a
defect to paper over. It shrinks when the 13 migrations land.

### Residual / next wave

- 13 CORPUS migrations (12 routine + `mc_kit/bars.py` needing a value-parity proof).
- 11 DERIVED + 2 test-oracle sites need no code change; they are unresolvable only because
  the path arrives as a function parameter. Closing them mechanically requires the
  interprocedural taint work this plan declined, so they stay adjudicated-on-paper until
  that decision is revisited.
- **56 files of committed BOM debt** remain. Out of scope here; they no longer cause false
  findings now that the scanner reads `utf-8-sig`, but the write path that produces them
  (PowerShell defaults) is unaddressed and will keep reintroducing them.
