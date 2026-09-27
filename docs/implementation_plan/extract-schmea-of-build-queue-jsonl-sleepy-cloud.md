# Build an HTML viewer for `multi_llm/build_queue.jsonl`

## Context

The 585-story backlog in `multi_llm/build_queue.jsonl` carries **35 top-level fields** (schema
extracted this session — see below), but nothing in the repo can read it:

- `multi_llm/console.html` has a queue panel, but it renders only **6 of 35 fields**
  (`renderQueue`, `console.html:395-421`) and expects the whole 2.3 MB file pasted into a
  single-line `<input>` (`console.html:177`) — not usable.
- The deep fields where models actually record their work — `analysis`, `evidence`, `lifecycle`,
  `linkage`, `risks`, `acceptance_criteria` — are invisible in every existing surface.

Outcome: a single self-contained HTML file you open by double-click, drop the `.jsonl` onto, and
browse — a sortable/filterable table with a click-through panel showing **every** field on a record.

## Decisions taken (from Q&A)

- **Local file, drag-drop.** `multi_llm/build_queue_viewer.html`, no embedded data. The queue is
  never duplicated into a second tracked file, the view is never stale, nothing leaves the machine.
- **Table + detail panel.** No kanban, no dependency graph, no schema-inspector tab.

## The schema the viewer must render

585 records · ids `STORY-<epic>.<n>` (unique, epics 1–82) · no header/meta line.

**Universal (585/585):** `id, epic, epic_title, title, description, status, creator, files, lifecycle`

**Near-universal:** `kind` (583) · `depends_on` (580) · `acceptance_criteria`, `definition_of_done`,
`analysis`, `evidence` (579) · `layer` (578)

**Enrichment block — exactly 577/585, always co-present:** `affected_files`, `assumptions`,
`business_objective`, `confidence`, `constraints`, `dependencies`, `linkage`, `module_count`,
`out_of_scope`, `risks`, `rollback_strategy`, `runtime_reachable`, `scope`, `story_points`,
`technical_objective`, `test_strategy`

**Rare:** `assignee` (2) · `continuation` (2)

**Nested:**
```
lifecycle : [ {stage, comment, actor?, at?} ]   stage ∈ Discovered|Done|Verified|Implemented|Diagnosed|Testing|InProgress
analysis  : {status, architecture|null, current_state|null, risk|null}
evidence  : {status, observed[], inferred[], assumed[]}
linkage   : {upstream_layers[], downstream_layers[], imports_n, imported_by_n}
risks     : [ {analysis, impact} ]
```

**Enums:** `status` pending 524 / done 54 / in_progress 6 / testing 1 · `kind` implementation 569 /
coordination 14 · `creator` Claude 462 / DeepSeek 109 / Grok Bot 14 · `layer` 11 values
(sidecar, governance, operator, config_layer, research, core, features, runtime, multi_llm,
data_ingestion, engines)

## Anomalies the viewer must survive (measured, not assumed)

These are real rows in the file. A naive renderer crashes or lies on each:

1. `lifecycle` is a **bare dict** on `STORY-82.1`, a list on the other 584 → normalize to list on read.
2. `dependencies` is a **bare str** on `STORY-81.4/.5/.6/.7/.8`, a list on the other 572 → normalize.
3. `story_points` is `null` on all 585 → render as "—", not "null".
4. `files` == `affected_files` on 574 and == `scope` on 572, but `depends_on` != `dependencies`
   on 392 → show all four, never collapse them.
5. **569/585 records carry mojibake** (`â€"` = an em-dash written UTF-8, read cp1252) → a
   display-only repair toggle, default ON. It never writes to disk.
6. 7/585 lines have unsorted keys (hand-appended) → irrelevant to rendering, but the parser must
   not assume key order.

Unknown keys (anything beyond the 35) must render generically in the detail panel rather than be
dropped — the queue is hand-enriched and will grow fields.

## Implementation

**One new file: `multi_llm/build_queue_viewer.html`** (~40 KB, zero dependencies, zero network).

Follow the existing convention of `multi_llm/console.html`: single file, no build step, no CDN,
and reuse its exact CSS custom-property palette (`console.html:8-22` — `--bg #0d1117`,
`--accent #58a6ff`, `--green #3fb950`, `--mono`) so the two surfaces look like one tool.

Structure:

- **Load:** full-window drop zone + `<input type="file">` fallback, via `FileReader` (no `fetch`,
  so `file://` works with no CORS problem). Parse line-by-line in a `try/catch` per line, mirroring
  `console.html:388-392`; report `N records, M bad lines` in the header instead of failing silently.
- **Filter bar:** free-text search across `id`/`title`/`description`; multi-select chips for
  `status`, `layer`, `creator`, `kind`; epic dropdown; a "has analysis/evidence" toggle so the
  ~9 records with real written-up work are findable among 576 `PENDING` stubs.
- **Table:** sortable columns — id, epic, status, layer, creator, kind, confidence, title.
  Status-coloured rows reusing the done/blocked/ready logic already in `console.html:403-406`
  (blocked = any `depends_on` entry not in the done set).
- **Detail panel:** renders the full record in field groups — Identity · Narrative (`description`,
  `business_objective`, `technical_objective`, `rollback_strategy`, `test_strategy`) · Lists
  (`acceptance_criteria`, `definition_of_done`, `scope`, `out_of_scope`, `assumptions`,
  `constraints`, `files`, `affected_files`, `depends_on`, `dependencies`) · `analysis` ·
  `evidence` (observed/inferred/assumed) · `linkage` · `risks` · `lifecycle` as a timeline ·
  then an "Other fields" group catching anything unrecognised.
- **Deep link:** `#STORY-41.3` in the URL selects that record after a file is loaded.
- **Test hook:** expose `window.__loadJSONL(text)` so the parse/render path is drivable without a
  real drag gesture (also what I use to verify it).

Nothing else is touched. No Python, so no SITS registration is required (§3.1b covers `scripts/**`
and repo-root `*.py`); precedent is `console.html` / `codebase_explorer.html`.

## Explicitly out of scope

- **Not fixing the mojibake at the source.** 569 records would need rewriting — that is a separate
  authorized change to a governed artifact, not a side effect of building a viewer.
- **Not fixing the two type anomalies** in the data. The viewer tolerates them and flags them.
- **Not touching `seed_build_queue.py`.** Recorded, per your call, as documentation only: the
  seeder emits 9 keys, its docstring (`:16-17`) still declares that 9-key line as the schema, and
  `:126` does a full `write_text` overwrite — **running it today destroys 26 fields on all 585
  records.** I will state this in the session log; no guard is added.

## Verification

1. Open the file in the browser pane (`preview_start` with the local path).
2. Drive `window.__loadJSONL(...)` with the **real** 2.3 MB `build_queue.jsonl` content and confirm:
   `585 records, 0 bad lines`.
3. Assert the anomaly handling on named rows, not in the abstract:
   - `STORY-82.1` renders its dict `lifecycle` as a one-entry timeline (no crash, no `"stage"` text).
   - `STORY-81.4` renders its str `dependencies` as a single chip.
   - A record with `analysis.status == "VERIFIED"` shows the full prose block.
   - Mojibake toggle flips `â€"` to `—` in a `description` and back.
4. Exercise filters (status=done → 54 rows; creator=Grok Bot → 14; layer=engines → 3) — counts must
   match the profile above.
5. Screenshot the table + an open detail panel.

## Session close (CLAUDE.md mandates)

- §6: append the `SESSION LOG ENTRY` to **`assistant_project.md`** (building the `multi_llm/` layer
  is code, per the §6 routing tie-breaker), including the seeder-drift note.
- §13.7: this session touches `multi_llm/`, so the response carries the protocol §3 handoff block.
  `HANDOFF.md` stays valid as-is (its `current_story` is free text, not a STORY id, which
  `tests/test_handoff_state.py:62-68` permits) — no edit needed.
