# Semantic OS context transfer · queue gaps · a reachability trigger

## Context

Three requests landed in one turn. They share a root cause.

1. **"Save this analysis for context transfer, attach to the Jira docs, move to in-progress."**
   This session produced two analyses that exist **only in chat and the SESSION LOG**: a full
   reconstruction of the Semantic OS v1 design (after you couldn't recall it), and a reachability
   census proving **zero** spine code imports the Semantic OS. Chat is not a record system. Unless
   this is written to a tracked artifact and linked from the story, the next session re-derives it
   — the exact loss §6.1 exists to prevent.

2. **"Any gaps that need to be addressed from build_queue.jsonl?"** — a health census of the
   585-row queue.

3. **"Design workflow commands for runtime reachability."** Reachability is *the* most repeated
   analysis class in this repo's history — F-005 unwired, F-006 orphaned, F-012 sidecar-only,
   F-013 orphaned, F-036 tunable-but-inert, F-070 vetoes 0/30, F-085 never ran, F-089
   reachable-but-neutral, F-102 dormant, F-103 disjoint rails. **Ten findings, one question,
   re-derived by hand every time.**

The root shared by all three: **this repo keeps paying twice for the same knowledge** — once to
derive it, again to re-derive it when the record didn't hold.

---

## What the research established (source-verified, not assumed)

### Context transfer — the native pattern exists; do not invent one

| Candidate | Verdict |
|---|---|
| `pack_story.py --story <id>` | Writes `context/packs/<ID>.md`, but **`context/` is untracked** — wouldn't survive a clone. It's an *exporter* reading the story's `files` list; no input channel for new prose. |
| `log_turn.py` → `turn_ledger.jsonl` | **Gitignored and never used** — the ledger doesn't exist. Local-only. |
| **`docs/implementation_plan/continuation-context-<slug>.md`** | **The durable, tracked precedent.** Linked from the story four ways at once: `continuation` key + `files` + `affected_files` + a `lifecycle` entry. `pack_story.py` then picks it up automatically because it reads `files`. |

### Story conventions (verified against all 585 rows)

- Status vocabulary: `pending` 524 · `done` 54 · **`in_progress` 6** · `testing` 1. **`in_progress`
  already exists — use it.** Nothing validates the field; no test constrains it.
- `lifecycle` is **append-only** in every worked row. Stages: `Discovered` 575 · `Done` 11 ·
  `Verified` 7 · `Implemented` 5 · `Diagnosed` 4 · `Testing` 2 · `InProgress` 2.
- `analysis` = `{architecture, current_state, risk, status}` (SCREAMING_CASE status);
  `evidence` = `{observed[], inferred[], assumed[], status}`. Observed = verified; inferred =
  mechanism. Never promote an inference.
- `assignee` + `continuation` are real keys on 2 Grok rows. §13.9's `Story_Detail` /
  `Verification_Status` / `Assignee` were **never materialized** — don't create them.
- Leave `story_points` `null` (null in **all 585**) and `definition_of_done` untouched
  (boilerplate in all 579, never once customized).
- File must stay **BOM-free** — a BOM breaks 5 tests via `build_context.py:64`.

**Target story — `STORY-31.22` "Tradelatest Semantic OS v2 — Build 1 (L1 + L5 + L6)"**, `pending`,
26 files, `analysis`/`evidence` empty, lifecycle at `Discovered`. Its literal scope is L1+L5+L6 and
the analysis measures exactly those three: L1 = 15 concepts, L5 = authority 56.7%, L6 = 1,118
objects. (Others: STORY-45.2/45.3/45.4 chain, STORY-33.3 — all stay `pending`.)

---

## Part A — execute now

### A1. New `docs/implementation_plan/continuation-context-semantic-os-<slug>.md`

Follows the ~101-line shape of `continuation-context-oss-lab-epic-50.md`: *What is claimed ·
Already read (do not treat as the census) · Exact next step · Non-goals · Where this session left
off.* Every claim carries its verification method, not just its conclusion:

- **Design:** L0–L6 foundation-model-first stack; six entities (CN/BD/JN/CT/FileIdentity/OBJ);
  rules — humans write meaning / machines derive, fail closed, disk is always the denominator,
  advisory-forever-unless-G001, append-only retirement.
- **Inventory:** 15 CN · 10 BD · 1 JN (7 steps) · 9 CT · 98 curated FileIdentities (+1,020 Tier-3
  slugs, *not* reviewed claims).
- **Shipped vs not — verified against disk, not the design doc's own table:** PR-1..5 shipped;
  PR-6 attribution overlays **not** (0.0% RED); PR-7 `semantic_impact.py` **not** (file absent);
  PR-8 **partial** (dimension reads 100% GREEN over a denominator of **7**; GREEN_FLOOR hooks
  unwired); JN-002..005 never authored.
- **Scoreboard** @ 2026-09-18T12:59:14Z, 1,118 objects: `NOT_YET`, semantic layer SKELETON.
- **Reachability census:** zero spine importers; only `truth_mode.py:113` and
  `claude_integration.py:69`, both lazy and fail-open, + 3 scripts, 11 tests, 1 lab runner. Four
  `src/` hits are docstrings/path-strings/regex. Reverse direction clean. Closed per §6.8 as
  **`INTENTIONAL SEMANTIC SEPARATION`** (design K7 + the "no gating production trades" non-goal) —
  **not** a defect.
- **Two traps to hand forward:** (a) semantic_coverage and boundary_coverage are the *same 95
  objects* — authoring more CNs moves neither, only BD glob expansion does; (b) Semantic OS
  coverage % must never be cited as a production-safety claim.

### A2. `multi_llm/build_queue.jsonl` — STORY-31.22 → `in_progress`

**Raw-text single-line replacement** — read all 585 lines as text, replace only this one, write the
rest back untouched. *(Not a parse-and-re-dump: 96.2% of rows carry mojibake and re-serializing
risks key reordering.)*

`status` → `in_progress` · `analysis` filled, status `IN_PROGRESS` · `evidence.observed` gets the
source-verified facts, `.inferred` the mechanism, status `IN_PROGRESS_VERIFIED` · **append**
`{stage: "InProgress", actor: "Claude", at: "2026-09-18", comment: …}` keeping `Discovered` ·
add `continuation` + the same path into `files`/`affected_files` · add `assignee: "Claude"` ·
`story_points` and `definition_of_done` untouched.

### A3. `HANDOFF.md` — extend `parallel_program` only

**Do not touch `current_story`.** It holds live **RC-003** state whose `next_prompt` names **two
open Principal decisions**, and the file header says *"The User owns this file."* The existing
`parallel_program` key is the established second-track slot — its current value literally ends
*"RC-003 state above untouched."* Extend that; change nothing else. The file is already valid, so
§13.7 is satisfied by leaving it valid plus emitting the §3 block in the response.

### A4. §3 handoff block + SESSION LOG

Emit `CURRENT_TASK · NEXT_10_STEPS · CONTEXT_DELTA · FOR_NEXT_MODEL · PROMPT_FOR_NEXT_MODEL ·
CONFIRMATION` in the response (§13.7), and append the `📝 SESSION LOG ENTRY` to
`assistant_project.md` (§6).

---

## Part B — queue gaps: report, do not repair

Dependency graph is **healthy**: 585 distinct ids, **0 dangling refs, 0 cycles**. The damage is
elsewhere.

| # | Gap | Scale |
|---|---|---|
| 1 | **Mojibake / double-encoding** | **563 of 585 rows (96.2%)**; 927 broken em-dashes. All round-trip losslessly via `.encode('cp1252').decode('utf-8')`, 0 failures — mechanically safe, but a 563-row rewrite deserving its own turn. |
| 2 | **The queue is not a backlog** | **572 of 585 (97.8%)** are auto-mined census artifacts. `story_points` null in **all 585**. Only **7 rows** have real acceptance criteria. "pending" mostly means *not yet audited*, not *not yet built* — which is how 4 stale items went undetected this session. |
| 3 | **Done-ness is unevidenced** | **38 `done` rows have `evidence.status: PENDING`**; 44 have zero evidence; **36 `done` + 2 `in_progress` never left stage `Discovered`**. |
| 4 | **Stale `affected_files`** | **58 paths don't exist on disk** across 25 stories — including a literal `path/to/file.py`. |
| 5 | **Schema drift** | 8 thin rows (11–14 keys vs 32); `dependencies` a bare string in 5; 3 epics with conflicting titles; 14 rows in 3 duplicate-title groups; 1 malformed `lifecycle`. |
| 6 | **Highest-leverage unblockers** | STORY-18.12 blocks **38** · STORY-25.12 blocks **32** · STORY-35.2 blocks **32**. 159 not-done stories are blocked; longest chain depth **44**. |

Gap 1 is the only mechanically safe repair and it's a 563-row rewrite. Gaps 2–5 are judgment calls
about what the queue is *for*. **Recommendation: report now, decide separately.**

---

## Part C — the reachability trigger (design; separate authorized turn to implement)

### The finding that shapes it

Three reachability planes already exist, **and nothing joins them**:

| Plane | Existing mechanism | Weakness |
|---|---|---|
| **DECLARED** | `active_models.yaml.reachability` (pointers); gate2b `RB()` profiles; `build_queue.runtime_reachable` | Pointers only, no computed verdict; **no test asserts a declared telemetry stream has rows** |
| **STATIC** | `ast_import_census()` at `semantic_objects.py:267` — already a pure, reusable library fn; `h4_rail_reachability.py` (F-103's proof); `config_reachability.py` | **No transitive "does A reach B" helper and no CLI.** h4 is depth-1, hardcoded, and unregistered |
| **RUNTIME** | `src/runtime/layer_trace.py` v5 `LayerProof` — per-(bar,layer) rows, `LAYER_PLANE` observation/decision/execution, already records `NOT_REACHED`; plus the F-037 counting-decorator idiom (`f048_decision_probe.py`) | Observation-only; nothing reads it back |

**Do not invent a vocabulary — two already exist.** `gate2b_adjudication.py:31` defines six
dimensions (`runtime_/decision_/research_/training_/artifact_reachable`, `test_only`) with values
`YES/NO/UNKNOWN/NOT_APPLICABLE` and the rule already in its source comment: **"YES/NO require
evidence — cited per row."** `config_reachability.py` defines the verdict ladder
`READ_AND_USED > TOOLING_ONLY > READ_BUT_INERT > SHADOW_ONLY > DOC_ONLY > DEAD`.

**A collision worth naming (§6.2):** `runtime_reachable` is a **homonym** — an evidence-backed
4-valued enum in gate2b, versus a bare boolean on 577 build_queue stories (**True 342 / False 235**)
that **nothing computes**. Same name, two meanings.

### The ladder the repo already uses but has never named

| Rung | Question | Plane | Precedent |
|---|---|---|---|
| 0 **DECLARED** | exists in config/registry? | declared | F-082 (4 keys declared in zero configs) |
| 1 **IMPORTED** | static graph reaches it? | static | F-103; this session's census |
| 2 **CONSTRUCTED** | object actually built? | static | F-038 (`RRFusionLayer` never constructed when `enabled:false`) |
| 3 **EXECUTED** | ran on a real corpus? | runtime | F-037 (`run()` called 0×), F-085 |
| 4 **PIVOTAL** | does removing it change the ledger? | runtime | F-036, F-070 (0/30), F-089 |

Mirrors §6.5's Authority Ladder in structure; the non-collapse invariant is already stated in
F-089: **`REACHABLE != PIVOTAL`**. Most reachability rework in this repo is a **rung confusion** —
answering rung 1 and claiming rung 4, or the reverse.

### Proposed commands

Two **Tier-2 read-only** triggers, added via the documented 3-place edit (§4 of
`trigger-vocabulary.md`: table row + §3 composition line + `CLAUDE.md` §12 gloss). Table format is
`| Trigger | Action | Loads (docs/prompts) | Exit condition |`. *(Note: no test enforces the
trigger list — only the convention.)*

- **`Reach <target>`** — rungs 0–2, cheap and static. Joins declared + static planes, emits the
  six-dim gate2b profile, **fail-closed to `UNKNOWN` without a citation** (§6.6: UNKNOWN beats
  invention). Composition: `Reach = Orient → ast_import_census BFS → declared-plane join → Log`.
- **`Pivot <target>`** — rungs 3–4, expensive. Requires a `layer_trace` query or an instrumented
  probe or a byte-identical ablation diff. **Never inferred from `Reach`** — must be run.

Both grant **no authority**, consistent with every other trigger. `Pivot` is what §6.5 requires
before any ΔG001 authority claim.

**The one genuinely missing primitive:** a transitive BFS + CLI over the existing
`ast_import_census()`. Everything else is a join of things that already exist. If a new script is
needed it must be SITS-registered the same turn (§3.1b).

---

## Risks / constraints

- **Concurrent sessions.** `build_queue.jsonl` already shows modified from another session
  (585-row schema vs 44 at `HEAD`). A large `git diff --stat` here is **inherited drift, not
  damage** — verified earlier via `git show HEAD:<path>`.
- **Pre-existing reds, out of scope** (§1.5 report-don't-fix): `test_doc_citations` drift at
  `entry-exit-map.md:44`; 17 findings past `Revalidate-by`; session-log count 171 vs cap 30 (the
  rotator is deliberately not run — it fuses bare-marker entries).
- **Change class:** `DOCUMENTATION_ONLY` — no `src/`, no `configs/`, no finding registered or
  reversed, no G001, no `ACTIVE_VERSION` change.

## Verification

```bash
venv/Scripts/python.exe -m pytest -q tests/test_handoff_state.py tests/test_context_compiler.py tests/test_context_pack.py tests/test_session_log.py tests/test_doc_citations.py tests/test_topic_docs.py
```

- Re-parse all 585 lines as JSON; confirm **exactly one row differs** and it is STORY-31.22.
- `pack_story.py --story STORY-31.22 --check` — confirm the continuation doc appears in the pack
  (proves the linkage works end-to-end).
- `git diff --stat` — touched set is exactly: the new continuation doc, `build_queue.jsonl`,
  `HANDOFF.md`, `assistant_project.md`. **No `src/` or `configs/` diff.** File has no BOM.

## Out of scope

- Not building PR-6/PR-7/PR-8 or JN-002..005. Moving a story to `in_progress` claims intent, not
  completion.
- Not closing STORY-45.2/45.3/45.4 or STORY-33.3.
- Not repairing queue gaps (Part B is a report).
- Not editing `CLAUDE.md` — Part C is a design for approval; adding a trigger touches a
  test-enforced file and deserves its own turn.
- STORY-18.10 (4th stale-ledger find, fully implemented but still `pending`) stays flagged.
