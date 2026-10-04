> Created: 2026-06-05 · Updated: 2026-06-05 · Milestone: Gov (docs-alignment / cold-start visibility)

# CLAUDE.md Preparation — Doc↔Code Alignment + Durable Mapping + Chronological Reference

## Context

**Why this is being done.** CLAUDE.md is the file every session reads first; the user's goal is that
reading CLAUDE.md + its referenced docs alone gives **full repository visibility**, that any
doc↔code drift is surfaced and fixed, and that a session can **reference every change/implementation
from the start, differentiated by time** (via `assistant_project.md` + `docs/plans/`).

A three-agent audit (2026-06-05) found the doc graph is structurally sound — **all ~43 paths
referenced in CLAUDE.md exist** and already use the new kebab-case names from the in-flight doc
reorg — but surfaced concrete drift and visibility gaps:

1. **Stale code citations** (lines drift on every edit — already drifted twice):
   - `CLAUDE.md:177` — `VALID_TRANSITIONS (crt_engine_v2.py:1021)` → actual **`src/config_layer/crt_engine_v2.py:1074`**
   - `CLAUDE.md:29` (F-004) + `docs/current-findings.md:94` — BitNet gate `crt_engine_v2.py:1752` → actual reject gate **`:1805`** (1752 is the comment block; `bitnet_main_threshold=0.55` at `:363`)
   - `CLAUDE.md:93` + `docs/reference/agent-reference.md:4` — **"22 tools"**; registry scan counts **25**. Doc's own breakdown (6+7+5+4) sums to 22 → 3 tools exist in code but not in the doc breakdown. **Recount authoritatively before flipping the number.**
2. **`CLAUDE.md` §2.0 doc tree omits real files** that exist on disk: `docs/architecture/llm-governance-layer.md`, `docs/architecture/replay-governance.md`, `docs/architecture/architecture-diagram.html`, `docs/architecture/services/`, and `docs/reference/control-plane.md`.
3. **Chronological reference is fragmented & partly unnavigable.** `docs/plans/` has **64 files** with opaque random-suffix names (`goofy-prism.md`, `velvety-gosling.md`…) and **no index** — you cannot tell what/when a plan is without opening it. ~16 lack the mandated `> Created · Updated · Milestone` header. There is no single "what happened when" view tying SESSION LOG (37 dated entries) + plans + findings + git.

**User decisions (2026-06-05):** Full hardening · citations carry **both symbol AND line** · build **plans index + unified timeline** · and — most important — a **durable mechanism so future code edits update the mapped docs in the same turn** (docs-mapping is first-class, not a one-off cleanup).

## Goals

- **G1 — Visibility:** CLAUDE.md + referenced docs = complete, accurate map of the repo (tree gaps closed).
- **G2 — Alignment + durability:** fix current drift AND install a self-enforcing map so drift is caught automatically and corrected at edit time.
- **G3 — Chronological reference:** any session can answer "what changed, when, why" from one entry point.

---

## Work Items

### A. Alignment fixes (close current drift) — serves G1/G2

Adopt the dual citation format **`path:line · Symbol`** everywhere a code location is cited (symbol = durable anchor that survives refactors; line = precision the user wants kept current).

- `CLAUDE.md:177` → `VALID_TRANSITIONS` (`src/config_layer/crt_engine_v2.py:1074 · VALID_TRANSITIONS`).
- `CLAUDE.md:29` (F-004 row) + `docs/current-findings.md:94` → BitNet reject gate `src/config_layer/crt_engine_v2.py:1805 · bitnet_main_score<0.55` (threshold `:363 · bitnet_main_threshold`).
- **Recount agent tools authoritatively** (enumerate `src/agent/tool_registry.py` + mode files / `PLAN_REGISTRY`), then reconcile the number in `CLAUDE.md:93`, `docs/current-findings.md` (if cited), and `docs/reference/agent-reference.md:4` **and** its §3.2–3.5 per-mode breakdown so the parts sum to the stated total. If true count is 25, document the 3 missing tools in the right mode section.
- **§2.0 doc tree completion** in `CLAUDE.md`: add `llm-governance-layer.md`, `replay-governance.md`, `architecture-diagram.html`, `services/` under `docs/architecture/`, and surface `docs/reference/control-plane.md` in the reference tier (and the §2 table). One-line role each.

### B. Citation convention + durable doc-mapping mechanism — serves G2 (the user's core ask)

1. **Codify the citation convention** in `docs/reference/conventions.md` (and a short pointer in `CLAUDE.md §10`): code locations in docs are written `path:line · Symbol`; the **symbol is authoritative**, the line is a maintained hint.
2. **New self-enforcing test `tests/test_doc_citations.py`** — mirrors the existing `tests/test_current_findings.py` / `tests/test_topic_docs.py` "read-a-doc-and-assert" pattern (regex-parse, no new deps). For each `path:line · Symbol` citation in the mapped docs (CLAUDE.md, current-findings.md, and the architecture/reference set): assert (a) file exists, (b) the symbol token appears in the file, (c) the cited line is within file length and the symbol is on or within a small window of that line (drift detector). Failure = the mechanical "code moved, docs didn't" red flag. This is what makes the mapping durable instead of a snapshot.
3. **New `CLAUDE.md §6.3 — Citation Sync Mandate`** (extends the §6.1 Topic Sync discipline from topics to code-citations): when a response edits a file that owns doc citations, update the co-located `path:line · Symbol` in the **same turn**. Add a one-line note to the `docs/architecture/trigger-vocabulary.md` `Sync`/`Validate` triggers.
4. **Reverse map (the "docs mapping"): generated `docs/architecture/citation-map.generated.md`** via new `scripts/analysis/gen_citation_map.py` (mirrors `scripts/analysis/gen_code_map.py`). It scans the mapped docs and emits a **symbol → docs-that-cite-it** index, so when code at symbol X changes a session instantly sees which docs to update. Regen step documented next to `gen_code_map.py` in CLAUDE.md §3.4 / code-map.md.

### C. Chronological reference layer — serves G3

1. **`docs/plans/readme.md`** — dated, milestone-tagged, newest-first index of all 64 plans (mirrors `docs/analysis/readme.md`). Columns: `Date · Milestone · Title (human) · File · Status`. Title is read from each plan's `#` heading; date/milestone from its header. Becomes the navigable face over the opaque filenames. Link it from `CLAUDE.md §2.0` tree + §2 table.
2. **`docs/timeline.md`** — single unified "what happened when": one row per dated work unit tying **date → milestone/phase → SESSION LOG entry → plan(s) → findings touched → key git commit(s)**. Sourced from `assistant_project.md` (37 entries), `docs/plans/`, `docs/current-findings.md`, `git log`. Link from CLAUDE.md §2/§2.0 and from `collaboration-workflow.md` (the "track + replay" doc).

### D. Full-hardening: plan-header retrofit — serves G3

- Retrofit the mandated `> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Milestone: <M>` header onto the ~16 non-compliant plans (e.g. `based-on-your-screenshot-precious-scott.md`, `study-the-code-base-linear-alpaca.md`). Created date = best available (header/body/git first-commit of file); Milestone = `n/a` when exploratory. Optionally extend `tests/test_topic_docs.py` style check (or the new citation test) with a plan-header floor so future plans can't omit it.
- Git milestone tags were considered but are **deferred** (mutate git history/refs; revisit only if the user wants `git log @M..` queryability — the timeline.md gives the same answer doc-side without touching git).

---

## Critical files

| File | Change |
|---|---|
| `CLAUDE.md` | §2.0 tree completion; §2 table rows; fix `:177` + `:29` citations; reconcile tool count `:93`; new §6.3 Citation Sync Mandate; §10 citation-format note; §3.4 regen pointer |
| `docs/current-findings.md` | F-004 evidence line `:1752`→`:1805` (+ symbol) |
| `docs/reference/agent-reference.md` | tool count `:4` + §3.2–3.5 breakdown reconciled to true count |
| `docs/reference/conventions.md` | codify `path:line · Symbol` citation convention |
| `docs/architecture/trigger-vocabulary.md` | note citation-sync on `Sync`/`Validate` |
| `tests/test_doc_citations.py` | **new** — self-enforcing citation/drift check (pattern from `tests/test_current_findings.py`) |
| `scripts/analysis/gen_citation_map.py` | **new** — emits reverse symbol→docs map (pattern from `scripts/analysis/gen_code_map.py`) |
| `docs/architecture/citation-map.generated.md` | **new (generated)** |
| `docs/plans/readme.md` | **new** — dated/milestone index of 64 plans (pattern from `docs/analysis/readme.md`) |
| `docs/timeline.md` | **new** — unified date→milestone→session→plan→finding→commit view |
| `docs/plans/*.md` (~16) | retrofit dated header |

**Reuse, don't reinvent:** `docs/analysis/readme.md` (index pattern), `tests/test_current_findings.py` + `tests/test_topic_docs.py` (doc-assert test pattern), `scripts/analysis/gen_code_map.py` (generator pattern), the existing §6/§6.1/§6.2 mandate structure (for §6.3). All edits are **additive/surgical, doc+test only — no production code, no config rehash, no promotion.**

---

## Verification

1. **Citation accuracy:** open each fixed citation, confirm symbol is at the cited line in `src/config_layer/crt_engine_v2.py` (`VALID_TRANSITIONS` @1074; reject gate @1805; threshold @363).
2. **New test:** `python -m pytest tests/test_doc_citations.py -v` passes; then temporarily perturb one cited line number and confirm it **fails** (proves the drift detector works), revert.
3. **Existing tests still green:** `python -m pytest tests/test_current_findings.py tests/test_topic_docs.py -v` (index↔doc consistency unbroken by edits).
4. **Generator:** `python scripts/analysis/gen_citation_map.py` runs clean and produces a non-empty `citation-map.generated.md` whose symbols resolve.
5. **Link integrity:** every new/edited markdown link in CLAUDE.md resolves on disk (re-run the audit's path-existence sweep).
6. **Visibility smoke test:** from CLAUDE.md alone, confirm you can reach plans-index → timeline → a specific dated change → its finding/evidence (the G3 cold-start path).
7. **§6 mandate:** append the SESSION LOG entry to `assistant_project.md`; update touched `docs/topics/*` per §6.1.

## Open items / risks

- **Tool count must be recounted, not assumed** — 22 (doc breakdown) vs 25 (scan) is unresolved; resolve at implementation by enumerating the registry, then make doc total = sum of parts.
- **Citation-test scope:** start with the high-value mapped set (CLAUDE.md + current-findings.md + architecture/reference docs), not every analysis snapshot, to keep the test fast and the floor meaningful. Expandable later.
- **Plan "Created" dates** for headerless plans may be approximate (git/body-derived) — acceptable; mark inferred dates as such.
