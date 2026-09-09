# Topic Atlas v2 — dual metrics + T4 Dataset Integrity Layer

## Context

Two requests, both tracking-only — **no code changes, no repo writes**. The artifact at
`https://claude.ai/code/artifact/1f31e362-2193-4300-8049-098ddd388f7a` is republished from the
same scratchpad file, keeping its URL.

1. **Track both metrics, not one.** T3's 255 files (15.3%) is reference *footprint* — every file
   mentioning `crt_engine_v2` / `CRTEngine`, i.e. 59 src importers plus every test and research
   script touching CRT. That is blast radius, not ownership; by ownership T3 is ~11 files. The
   register needs both columns side by side so neither number is mistaken for the other.
2. **Add T4 — Dataset Integrity Layer.**

## Dual-metric definitions (to be stated on the page)

- **Ownership** — files that *are* the topic: its home modules, its dedicated configs, and tests
  or scripts named for it. Sums toward 100% and is the basis for primary-topic assignment.
- **Footprint** — any file defining *or referencing* the topic's symbols. Overlaps freely across
  topics, will exceed 100% in aggregate, and answers "what breaks if this changes."

Measured (read-only, this turn): ownership T1 **12** · T2 **18** · T3 **11**
(6 `config_layer` modules + 5 dedicated tests) · T4 **~9** — exact count at execution.
Footprint stays 54 / 90 / 255 / 48.

## T4 — Dataset Integrity Layer

**Home modules**
```
src/data_ingestion/ohlcv_schema.py        L1 — single-ROW correctness
src/data_ingestion/dataset_integrity.py   L2 — whole-SEQUENCE integrity + validate_universe
src/data_ingestion/corpus_gate.py         admission wrapper (admit_corpus -> validate_dataset)
src/data_ingestion/dataset_registry.py    R3 dataset identity / admission API
src/utils/integrity_events.py             integrity-event telemetry spine
```
**Dedicated tests**
```
tests/test_dataset_integrity.py · tests/test_dataset_registry.py
tests/data_ingestion/test_strict_fetch_gate.py · tests/data_ingestion/test_session_autoderive.py
tests/Grok/test_H_ingestion.py · tests/test_resample_completeness.py
```
**Consumer footprint** — 21 files call `validate_dataset(`, plus `backtest_v2`'s own
`_preflight_dataset` / `validate_universe` route.

## New Cross-Layer Log entries

**1. "Dataset" is a homonym (verified).** `dataset_integrity.py` is L2 **OHLCV corpus sequence**
integrity; `src/features/dataset_validator.py` validates **fusion trade logs before model
training**; `dataset_builder.py` / `stage1_dataset_builder.py` / `rr_dataset_builder.py` build
**ML feature datasets**. Only the first belongs to T4. Also `src/governance/config_integrity.py`
is *config* integrity (F-006, orphaned), not dataset — excluded. Same trap as "population" and
"policy"; that makes three confirmed homonym families.

**2. F-039's second clause is stale (verified, with an E-001 correction recorded).**
F-039 (2026-06-26) states L3 runs at "ONLY two call sites, both in `backtest_v2`" and that "the
whole `src/research/` pipeline … streams with only the inline L1/L2 backstop (no L3)". Measured
now: **21 files** call `validate_dataset`, including 7 under `src/research/evidence/` and 5
research drivers — the exact population F-039 said had none, mostly reaching it through the newer
`corpus_gate.admit_corpus` wrapper.

*The correction to record alongside it:* a raw `grep -c "validate_dataset(" backtest_v2.py`
returns **0**, which reads as "backtest_v2 lost its gate". That is wrong — it still imports
`validate_universe` from `dataset_integrity` (`:61-64`), still defines `_preflight_dataset`
(`:3287`), and imports `admit_corpus` (`:60`). The file reaches the layer through different entry
points than the symbol I grepped. The honest claim is **coverage expanded**, not "the gate moved".
F-039 self-describes as "a dated observation, not a future guarantee", so this is drift the
finding anticipated — status `open`, not a reversal.

## Changes to the artifact

`scratchpad/artifact_topic_atlas.html`, republished to the same URL.

- Coverage table gains **Ownership** and **Footprint** columns; the share bar tracks ownership.
- Header readout carries both headline numbers so the page cannot be skimmed into the wrong one.
- Sheet-1 flag rewritten: the blast-radius caveat becomes the column definition rather than a
  warning bolted on afterwards.
- T4 row added; backlog table drops the now-mapped `data_ingestion` share.
- Cross-Layer Log gains the two entries above (log count 5 → 7).
- Tab label counts updated (4 topics / 7 entries).

## Explicitly not done

- No repo file touched, nothing committed, no `src/` change — tracking only.
- **F-039 is not edited.** Marking a governed finding stale is a §6.2 Findings-Mandate action
  requiring its own turn and a same-turn decision; the artifact records the observation, and
  `docs/current-findings.md` stays untouched.
- No re-run of the BG measurements; no new topics beyond T4.
- Ownership numbers are a *proposed* assignment rule, not yet applied as an exclusive
  partition — until every file has exactly one owning topic, "100%" stays undefined.

## Verification

1. Recompute ownership/footprint per topic with grep only; confirm T4's exact ownership count and
   that footprint totals still match (54 / 90 / 255).
2. Confirm the union and denominator are unchanged (308 / 1,665) — T4's files were already inside
   the denominator, so only the *mapped* union moves.
3. Republish to the same file path; confirm the URL is unchanged and both sheets still switch.
4. Update the memory register with the dual-metric definitions and the two new cross-layer entries.
