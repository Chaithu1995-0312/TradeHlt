# Topic ↔ File Coverage Map (JSONL-reasoned)

## Context

The repo runs a **topic-coverage census**: partition every file in the codebase into exactly one
named topic, and drive that coverage to 100%. Sixteen topics have been walked by hand
(T1–T16, one per session). The lane has three problems that will not fix themselves:

1. **Coverage is 218 / 1,668 = 13.07%** after 16 sessions. At that rate, 100% is ~20+ more sessions.
2. **57 of the 218 owned files are counts-only.** T1–T5 (49) and T10 (8) recorded a *number* but
   never an itemized file list; `assistant_project.md:375` confirms the breakdown is
   UNRECOVERABLE. Ownership is evaporating as it is produced.
3. **The whole ledger is prose** in `assistant_project.md`. Nothing is machine-readable, so
   disjointness, union arithmetic, and the remainder are all recomputed by hand each session
   (and have slipped: the T12 35-vs-34 tally, the T10 union never closed).

`docs/CODEBASE_SEMANTIC_NAMES.jsonl` (untracked, 1,707 rows) changes what is possible. Every row
carries `path · semantic_name · business_role · content_summary · area` — a per-file intent
statement. That is enough signal to *propose* an owner for every unowned file in one pass instead
of sixteen more manual walks.

**Intended outcome:** a machine-readable topic↔file map covering the full 1,668-file denominator,
a coverage number that regenerates instead of being retallied, and a floor test that makes
disjointness mechanical.

### Measured facts this plan rests on (verified this session, not recalled)

| Fact | Value | How verified |
|---|---|---|
| Census denominator | **1,668** (1,582 `.py` + 86 config) | re-derived by glob today; matches `assistant_project.md:404` |
| JSONL rows | 1,707, zero dupes, all paths on disk | `json` load + `os.path.exists` |
| JSONL ∩ denominator | **1,666 / 1,668 (99.88%)** | set intersection |
| Denominator files missing from JSONL | 2 — `configs/research/measurement_result_log.jsonl`, `configs/research/provenance_ledger.jsonl` | set difference |
| JSONL extras beyond denominator | 41 — 25 `docs/*.md`, 8 root `*.md`, 8 configs outside the 4 declared dirs | set difference |
| Union owned today | 218 (95 at T10 + 97 at T11–T15 + 26 at T16) | `assistant_project.md:375,377-381,406` |
| Itemized vs counts-only | 161 itemized / **57 counts-only** | same |
| JSONL `area` buckets | test 543 · research 458 · analytics 174 · runtime 157 · governance 130 · config 126 · script 48 · tools 37 · docs 33 · other 1 | `collections.Counter` |

### Decisions taken (user, this session)

- **Vocabulary = merged registry.** The 28 `docs/topics/*.md` names are the base; the 9 census-only
  topics (Parquet, DuckDB, TV engine, MT5 terminal, RAG, TradeNet, Ingest/Admission,
  Feature-State Layers, Parent Feed) become first-class entries. Neither vocabulary is dropped.
- **Assignment = bulk proposal, then review.** One scoring pass over all unowned files, then a
  human verdict on the low-confidence and contested rows only.

---

## Artifacts produced

| Path | Kind | Contents |
|---|---|---|
| `docs/governance/topic_registry.jsonl` | PRIMARY (hand-seeded) | one row per topic: `topic_id`, `name`, `origin` (`docs_topic`\|`census`\|`new`), `doc_path`, `kind` (`NEEDED`\|`USEFUL`\|`CENSUS`), `status` |
| `docs/governance/topic_file_map.jsonl` | PRIMARY (seeded + reviewed) | one row per denominator path: `path`, `topic_id`, `basis` (`LOG_CONFIRMED`\|`REVIEWED`\|`PROPOSED`\|`UNASSIGNED`\|`CROSS_CUTTING`), `confidence`, `evidence`, `signals` |
| `docs/governance/topic_coverage.md` | GENERATED | per-topic OWNED n + %, union, remainder, the 57-file debt, denominator provenance |
| `scripts/governance/build_topic_coverage.py` | script | builds the proposal, regenerates the report, runs the invariants |
| `tests/test_topic_coverage.py` | floor | denominator, disjointness, total-accounting, no-silent-unassigned |

Registry and map are **PRIMARY** (hand-authored / review-gated); the report is **GENERATED** and
never hand-edited — the tier separation CLAUDE.md §2 already enforces elsewhere.

---

## Steps

### S1 — Freeze the denominator

Re-derive 1,668 from the declared globs (`src|tests|scripts|tools/**/*.py` minus `__pycache__`,
plus `configs/{formulas,production,research,market_reality}/**` files). Write the glob spec and the
count into `topic_coverage.md` header so the number is reproducible, not asserted. Record the 2
JSONL-missing files and the 41 JSONL extras explicitly — an extra is not silently included, a gap
is not silently dropped.

### S2 — Build the merged topic registry (~37 rows)

- 28 from `docs/topics/*.md` — title via `^# ` (already extracted; `_template.md`/`readme.md` are
  not topics). Reuse the `NEEDED`/`USEFUL` split already encoded in `.grok/_build_how_index.py`
  rather than re-deriving it.
- 9 census-only topics from `assistant_project.md` (T5–T15 entries at lines 131, 143, 167, 195,
  377–381).
- New topics **only** where a real bucket has no home in either vocabulary. `research` (458 files
  by area, 441 by the T10 path sweep) is the known case and will need at least one — name it during
  the pass, do not pre-invent it here.

### S3 — Seed the map from the existing ledger (authority: session log, not the scorer)

Write the **161 itemized** owned files as `basis: LOG_CONFIRMED` with the session-log line as
`evidence`. These are settled; the bulk pass in S4 must not be able to overwrite them.

Record the **57 counts-only** files as a single explicit debt row per topic
(`topic_id`, `owed_count`, `basis: COUNT_ONLY_UNRECOVERABLE`). **Do not fabricate paths to close
the gap** — the union stays 218 with 57 unlocatable, stated as such.

### S4 — Bulk proposal pass over the ~1,450 unowned files

Score each file against each registry topic. Signals, strongest first:

1. **`content_summary` imports** — structural, and the strongest available. A file importing
   `features.registry` is feature-topic evidence. This is exactly the import-verified method that
   corrected the T12 walk after token-grep produced 18 false positives.
2. **`business_role`** — the module's own intent sentence, matched against the topic's
   *In plain language* / *Code covered* sections in `docs/topics/<name>.md`.
3. **`semantic_name`** — CamelCase token overlap with the topic name
   (`ResearchThreeAtlasesBarDirectionOutcome` → research/evidence tokens).
4. **`area`** — a 10-way prior that *narrows candidates*, never decides alone.
5. **path prefix** — tiebreak only.

Emit `topic_id` + `confidence`:
- `HIGH` — imports **and** business_role agree on one topic, no runner-up within margin.
- `MEDIUM` — two signals agree, or one strong signal with a close runner-up.
- `LOW` — area/path only, or two topics tie.

Everything lands as `basis: PROPOSED`. Nothing is owned yet.

**Traps this pass must structurally avoid** (each cost a real correction in the lane):
- No bare-token matching — the T8 `mt5` trap swallowed every `data/mt5` CSV citation.
- No filename-token test matching — the T16 walk found `test_fusion_engine.py` does not exist;
  central modules are covered only through integration suites, so tests are assigned by
  **import target**.
- Shared config files (`configs/production/v2_htfcrt_2026_08.json`) are `CROSS_CUTTING`, never
  owned — multiple topics hold *sections*, and sections are not files (`assistant_project.md:411`).
- OWNED and FOOT are different numbers. Coverage counts **OWNED only**.

### S5 — Review gate

Surface `MEDIUM` + `LOW` + any file whose top two topics are within margin, grouped by topic and
sorted by cluster size so one verdict settles many files. Reviewed rows flip to
`basis: REVIEWED`. `HIGH` rows stay `PROPOSED` and are counted, but stay visibly distinguishable
from `LOG_CONFIRMED`/`REVIEWED` in the report — a proposal is not a verdict.

### S6 — Generate the coverage report + floor test

`topic_coverage.md`: per-topic OWNED n and % of 1,668, union owned + %, unassigned remainder, the
57-file debt, and a basis breakdown (log-confirmed / reviewed / proposed) so the headline number
can never be read as more settled than it is.

---

## Verification

Run all of these; each is a hard gate in `tests/test_topic_coverage.py`:

1. **Denominator reproduces** — the glob spec re-derives to exactly 1,668.
2. **Total accounting** — every denominator path appears exactly once in `topic_file_map.jsonl`.
   No path is silently absent; unassigned is an explicit `UNASSIGNED` row, not a missing one.
3. **Disjointness is programmatic** — pairwise intersection of every topic's owned set is empty,
   asserted in code, not prose (the T7∩T8 precedent, and the check that caught the T12 slip).
4. **Union arithmetic** — `sum(per-topic OWNED) == union`, and `union / 1668` matches the reported %.
5. **Seed immutability** — the 161 `LOG_CONFIRMED` rows are byte-identical before and after a
   rebuild; the bulk pass cannot overwrite a log-confirmed owner.
6. **Registry closure** — every `topic_id` in the map exists in `topic_registry.jsonl`.
7. **Spot-check** — read the module docstring at source for 15 random `HIGH` rows and confirm the
   assignment. Any miss downgrades the confidence banding before the report is published.

Command shape (in-repo venv per CLAUDE.md §1.5):

```bash
venv/Scripts/python.exe scripts/governance/build_topic_coverage.py --verify
```

---

## Scope and authority

- **READ-ONLY** on `src/`, `configs/`, `tests/`, `scripts/`, `tools/`. No engine, config, or
  behavior change; `params` untouched, so no rehash.
- `DESCRIPTIVE_ONLY`. **No G001, grants no authority** (§6.5) — a coverage map is navigation, not
  evidence, and does not promote anything.
- The 28-vs-16 vocabulary split is **preserved, not resolved**: the merged registry records both
  origins per topic rather than picking a winner (§6.2 rule 4).
- Closes with a `📝 SESSION LOG ENTRY` in `assistant_project.md` (§6), including the coverage
  number and its basis breakdown.

## Open, deliberately not decided here

- The name and boundary of the `research` topic(s) covering ~450 files — decided during S4 with the
  files in hand, not pre-invented.
- Whether `docs/CODEBASE_SEMANTIC_NAMES.jsonl` (currently untracked) should be committed as a
  tracked input. The map cites it as evidence; an untracked evidence source is the same class of
  problem CLAUDE.md's Findings Mandate names for evidence paths.
