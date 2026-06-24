# Topic Visibility & Docs↔Code Sync — Foundation

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: M (new doc-governance layer, foundation phase)

## Context (why we're doing this)

The repo already has a **Context Report** button in the control plane — click 🧠 on a finished run and it runs `extract_code_context()` (pure-stdlib AST extraction of executed symbols from the script path + traceback lines, [`code_context_extractor.py`](src/control_plane/code_context_extractor.py)) → `ContextReportAPI.context_analysis()` ([`context_report.py`](src/control_plane/context_report.py)) → Claude Haiku → structured JSON (`root_cause` / `architecture_notes` / `artifact_analysis` / `recommendations`). It gives operational visibility into **one run**.

The user wants the same *shape of visibility* but keyed on a **topic / concept** instead of a run: for a topic, narrate in human language **what code it covers, its tests, its ins/outs, and its validations traced through application entry points** — and keep that narration **in sync with the code on every working response**, so docs never drift. The doc references in `CLAUDE.md` should become a navigable **tree path** (today the §2 table is flat — the "soft waterfall"), and each topic should carry a standing **discussion block** (risks / challenges / blockers / ambiguities / enhancements / need-more-info) filled during sessions.

This phase builds the **docs + sync foundation only** — no new UI button, server route, or LLM code. The LLM-powered "Topic Report" button (the technical mirror of Context Report) is the explicit **next phase**, unlocked once the structure and topic set exist. This is doc-only, fully reversible, no `src/` or runtime change.

**Why it helps Claude (the durable payoff):** today every session re-derives "what is the CRT spine / where does governance live / what tests cover fusion" by re-reading source. A maintained `docs/topics/` layer gives a session **one grounded, human-language file per concept** — code covered (with `file:line` citations), entry points, tests, validations, and known risks/blockers — so orientation is a single read instead of a fan-out, ambiguities are tracked across sessions instead of rediscovered, and the per-response sync mandate keeps that file true as code changes. Less token spend, faster `Orient`, no stale context. This is the same logic as the §6 SESSION LOG mandate, extended from "what I did" to "what each topic *is*."

## What already exists (reuse, do not reinvent)

| Concern | Existing asset |
|---|---|
| AST code extraction (for later report phase) | [`code_context_extractor.py`](src/control_plane/code_context_extractor.py) `extract_code_context()` |
| LLM structured-JSON pattern (for later report phase) | [`context_report.py`](src/control_plane/context_report.py) `ContextReportAPI` (4-key JSON, Haiku, optional-import guard, `.env` key load) |
| Human-language narration format | [`docs/human-language-analysis/`](docs/human-language-analysis/) — 20 package-grouped files (purpose / runtime role / invocation / I-O / failure modes / determinism / trust) |
| Per-module structured analysis | [`docs/analysis/codebase-analysis.md`](docs/analysis/codebase-analysis.md) — ✅Overview 📊Architecture 🚧Gates 🔗Integration ⚠️Constraints 🎯Operation per module |
| Entry-point catalog | [`src/control_plane/registry.py`](src/control_plane/registry.py) `CommandSpec` list → [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md) (auto-generated) |
| Session threads / open questions | [`assistant_project.md`](assistant_project.md) SESSION LOG blocks |
| Dependency/code mapping | [`scripts/analysis/gen_code_map.py`](scripts/analysis/gen_code_map.py), `graph.dot`, [`code-map.generated.md`](docs/architecture/code-map.generated.md) |
| Per-response mandate precedent | `CLAUDE.md` §6 SESSION LOG (mandatory append every response) |
| Doc-alignment test pattern | [`tests/test_control_plane_doc_alignment.py`](tests/test_control_plane_doc_alignment.py) |
| Tree/index doc precedent | [`README.md`](README.md) docs map · [`docs/governance/user-progress-registry.md`](docs/governance/user-progress-registry.md) |

## Recommended approach

### 1. New `docs/topics/` layer (the topic-visibility home)

- **`docs/topics/readme.md`** — the **topic index** and tree root. A single-screen table:
  `Topic | Domain | Source files | Entry points | Tests | Status | Doc`.
  Seeded by mining the existing assets (not invented): each [`human-language-analysis/`](docs/human-language-analysis/) grouping → candidate topic rows; cross-reference [`assistant_project.md`](assistant_project.md) threads (e.g. Phase 0–6 BNBUSDT funnel work) for live concepts; map `Entry points` to `registry.py` `CommandSpec` ids / `cli-matrix.md`; map `Source files`/coverage to [`codebase-analysis.md`](docs/analysis/codebase-analysis.md) modules.
- **`docs/topics/_template.md`** — the per-topic template (mirrors `docs/architecture/services/_template.md` placement convention). Sections:
  1. **Header** — `> Created · Updated · Status` (dated like §6 / plans).
  2. **In plain language** — what this topic *is* and why it exists (human narration, lifted style from `human-language-analysis/`).
  3. **Code covered** — modules/classes/functions with `file:line` citations (cross-ref `codebase-analysis.md`).
  4. **Ins / Outs** — inputs consumed, outputs produced, config sections, JSONL lines.
  5. **Entry points & validations** — how it's reached (CLI / control-plane command / agent tool, cited to `registry.py`) and what validates it end-to-end.
  6. **Tests** — covering `tests/` files (the coverage view).
  7. **Fits in architecture** — where it sits in `signal-flow.md` / `code-map`; links up the tree.
  8. **Discussion (filled in-session)** — `Risks · Challenges · Blockers · Ambiguities · Enhancements · Need-more-info`, each entry dated. This is the standing parallel-discussion surface; template, no API calls this phase.
- **Seed 1–2 example topic docs** to prove the format end-to-end — e.g. `context-report.md` (the feature we just studied; self-documenting) and `crt-spine.md` (the candle→order spine, the system's core concept). The rest are listed as rows in `readme.md` with `Status: stub`.

### 2. Restructure `CLAUDE.md` doc references into a tree path

- Add a **`§2.0 Doc Reference Tree`** block above the existing flat §2 table — an indented tree showing the navigation hierarchy (root → tier → leaf), e.g.:
  ```
  CLAUDE.md  (operating manual, root)
  ├─ README.md  (front door + docs map)
  ├─ docs/architecture/   (why / where / flow)
  │   ├─ goal.md · signal-flow.md · event-taxonomy.md · code-map.md …
  ├─ docs/reference/      (what — stack, schemas, conventions, configs, tests)
  ├─ docs/topics/         (TOPIC VISIBILITY — concept↔code↔tests↔validations)   ← NEW
  │   ├─ readme.md  (topic index = tree of topics)
  │   └─ <topic>.md
  ├─ docs/governance/ · docs/architecture/idea-governance-framework.md
  └─ docs/analysis/       (historical, non-living)
  ```
  Keep the existing §2 task→doc table (it stays authoritative for "which doc covers X"); the tree is the *navigation* view the user asked for. Add one `docs/topics/readme.md` row to the §2 table and a §3.4 "Key files" bullet so it's discoverable in the soft waterfall.

### 3. Per-response docs↔code sync mandate (the "automatic on every response" ask)

- Add **`§6.1 Topic Sync Mandate`** to `CLAUDE.md`, modeled on the §6 SESSION LOG rule:
  > On every response that changes code or the understanding of a topic, update that topic's `docs/topics/<topic>.md` in the same turn — **only the affected topic file(s)** (token-aware; never rewrite unrelated docs), bump its `Updated:` date, and note the change. Purely conversational responses touch only the SESSION LOG.
- This makes docs↔code sync **automatic per response** (the user's explicit request) without a generator or CI gate, reusing the proven §6 discipline. Token control is honored by the "only touched files" rule (§8).
- Add a **`Sync`** trigger to [`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) Tier-2 (action: reconcile a topic doc against current code; read-then-surgical-edit; ends with SESSION LOG) and reference it from `CLAUDE.md` §12.

### 4. Discoverability + light enforcement

- `README.md` docs map: add `docs/topics/` under Tier 3.
- Extend [`tests/test_control_plane_doc_alignment.py`](tests/test_control_plane_doc_alignment.py) (or sibling `tests/test_topic_docs.py`) with a read-and-assert test: every `docs/topics/*.md` (except `readme.md`/`_template.md`) has a `Created:`/`Updated:` date header and the required section headings — the enforceable analogue of the §6 / plan-timestamp pattern. Mechanical only; does **not** verify code-sync content.

## Files to create / modify

- **Create:** `docs/topics/readme.md`, `docs/topics/_template.md`, `docs/topics/context-report.md`, `docs/topics/crt-spine.md`
- **Modify:** `CLAUDE.md` (§2.0 tree block, §2 table row, §3.4 bullet, §6.1 sync mandate, §12 `Sync` trigger)
- **Modify:** `README.md` (docs-map Tier-3 entry)
- **Modify:** `docs/architecture/trigger-vocabulary.md` (`Sync` Tier-2 trigger)
- **Create/Modify:** `tests/test_topic_docs.py` (or extend `test_control_plane_doc_alignment.py`) — header/section assertion

## Next phase (explicitly out of scope here)

The **LLM-powered "Topic Report" button** — control-plane button → topic resolver (registry + dependency graph) → AST topic extractor (generalize `extract_code_context()` from run→topic) → Claude structured JSON (risks/challenges/blockers/enhancements, the parallel-discussion lenses) → auto-written `docs/topics/<topic>.md`. Foundation here makes that a thin wrapper later. **No UI/server/LLM code this phase.**

## Verification (end-to-end)

1. **Read test:** open `docs/topics/readme.md` — is the topic index a scannable one-screen table with the tree visible? Open `docs/topics/context-report.md` — does it narrate the feature in plain language with `file:line` citations, ins/outs, entry points, tests, and a dated Discussion block?
2. **Tree path:** `CLAUDE.md` §2.0 renders the doc references as an indented tree including `docs/topics/`.
3. **Sync mandate:** `CLAUDE.md` §6.1 + the `Sync` trigger in `trigger-vocabulary.md` are present and consistent with the §6 pattern.
4. **Discoverability:** `docs/topics/readme.md` is linked from `CLAUDE.md` §2/§3.4 and `README.md`.
5. **Tests:** `python -m pytest tests/test_topic_docs.py -q` (or the extended alignment test) → pass.
6. **Sync dry-run:** make a trivial edit to one cited symbol, confirm the mandate's loop (update only that topic's doc, bump `Updated:`) is followable in one turn without touching unrelated docs.

## Out of scope

- No `src/`, engine, runtime, control-plane, or UI change.
- No LLM API calls / new automation beyond the one doc-alignment test.
- Not regenerating `human-language-analysis/` or `codebase-analysis.md` — they are *sources* to mine, left intact.
- Not building the Topic Report button (next phase).
