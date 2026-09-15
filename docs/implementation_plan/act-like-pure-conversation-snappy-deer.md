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
