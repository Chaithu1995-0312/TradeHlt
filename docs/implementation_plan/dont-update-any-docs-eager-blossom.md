# Integrated Claude Operating Workflow — design plan (rev 2)

**Status:** design only. Nothing in the repository is modified by this turn.
**Deliverable constraint (user):** plan file only — no repo doc writes, and **no `assistant_project.md`
SESSION LOG append this turn** (CLAUDE.md §6 deliberately waived by the user's "Plan file only" answer).
**Scope locked:** reconcile-and-supersede the prior design · plan file only · spec **plus** PR plan.
**Rev 2:** second sweep for missed layers. **Ten layers were missed** across both analyses — two of
them (run-provenance and enforcement) are load-bearing for this exact problem. They are folded in below
and marked **[MISSED-BY-BOTH]**.

---

## Context

The lab has ~40 distinct machine-readable capability surfaces. A session LLM arriving cold does **not**
systematically use them: it re-derives routing, reaches for `grep` and the session log, and occasionally
upgrades an artifact into a conclusion. The repository has already paid for that — F-067 (an external bug
trace repeated backwards), F-068 (a code comment cited that did not exist), the 2026-08-18 attribution
entry (working-tree changes credited to the wrong agent).

The missing piece is **typed routing over surfaces that already exist** — not another engine.

**Intended outcome:** a cold session can name the owner of any phrase, pick the right capability, keep
artifact/evidence/concept/capability/conclusion distinct, attach provenance to any claim about a run,
and fail closed — without a fourth intent registry and without new authority.

### Prior art this supersedes

A Grok session logged **"Design — Integrated Claude Operating Workflow"** at 2026-08-18 18:18
(`%TEMP%\grok-Hi\grok-design-doc-b578c7a8.md`, 1,078 lines; **not in the repo**). Its type system and
three-owner composition hold and are adopted, keeping its name. Corrections and additions are itemised
in Part 4.

### Coverage honesty

Read in full: `assistant_project.md` doctrine header + newest ~15 entries + all ~80 entry topics;
`.grok/INFRA.md`; the prior design's type system, key decisions, interface map, gaps, dispatch table.
**Sampled, not fully read:** June–July log mid-history; the prior design's §joins/§rollout tail; the
bodies of most census scripts. Every row below was verified on disk this turn or is marked UNVERIFIED.

---

## Part 1 — Epistemic type system (adopted from prior design, unchanged)

Every row, retrieval, and sentence is **exactly one** type. Collapsing types is a protocol violation.

| Type | Is | May | May not |
|---|---|---|---|
| **Artifact** | a file/JSONL line/report/screenshot on disk | be opened, hashed, cited as "this file says" | become a conclusion; override source or `ACTIVE_VERSION` |
| **Evidence** | an observation from a **named procedure** | support/weaken a claim at its declared class | auto-register a finding; grant G001 |
| **Concept** | a named meaning owned by ontology / Semantic OS / MIAR | constrain language | invent a formula, `CRTState`, or FM/SEM id |
| **Capability** | a runnable interface (CLI, `@register_tool`, script, floor) | be invoked with documented inputs | acquire authority its handler lacks |
| **Conclusion** | a **registered** finding / closure status / promotion decision | bind future sessions | be inferred from RAG, session log, or Excel |

Promotion is one-directional and fail-closed:
`artifact --search--> artifact` · `artifact --named procedure--> evidence` ·
`evidence --findings mandate + E-001 ritual--> conclusion` ·
`concept --ground--> GROUNDED|UNKNOWN|AMBIGUOUS|UNANSWERABLE` ·
`capability --invoke--> artifact|evidence` (never a conclusion).

**Reuse the existing enums** — `feature_surface_query.py:11-15` emits `PROVEN|HEURISTIC|TEXT_REFERENCE`;
`semantic_grounding.py` emits `GROUNDED|UNKNOWN|AMBIGUOUS|UNANSWERABLE`. Do not mint a sixth vocabulary.

**Rev-2 addition — the evidence→conclusion edge has a mechanical gate already built.** See family F.
An economic/market claim is not merely "typed as evidence"; a **run manifest is required for it to be
constructible at all** (`require_manifest` raises). That edge is enforced code, not doctrine.

**Forbidden promotions:** session-log sentence → conclusion · RAG chunk → finding · Excel row → runtime
behavior · TV mark → `TRADE_OPENED` · encyclopedia row → runtime behavior · capability exists →
capability has authority · `MC-*` file on disk → measurement layer CLOSED.

---

## Part 2 — Capability census (verified this turn)

### A. Agent kitchen — `src/agent/`
| Capability | Entry | Verified | Authority it lacks |
|---|---|---|---|
| `PLAN_REGISTRY` deterministic intent→tool order | [plan_compiler.py:42](src/agent/plan_compiler.py:42) | **22 keys** (imported) | LLM never picks tools |
| Tool registry | [tool_registry.py](src/agent/tool_registry.py) | **35 tools** (imported) | write tools need `confirmed=True` + path-guard |
| 7 modes | `src/agent/modes/` | copilot, findings, governance, log_query, **ops**, pipeline, **truth** | — |
| NL classification | [intent_router.py:30](src/agent/intent_router.py:30) | **21 of 22** classifiable | `semantic_ground` NL-unreachable |
| `truth.*` janitor | `modes/truth_mode.py` | ground_claim, construction_check, feature_math_lint, script_census, citation_floor, hygiene_pack | advisory |
| Audit stream | `logs/agent_{audit,intent_log,findings}.jsonl` | present | `findings.synthesize` writes JSONL, **not** `docs/current-findings.md` |

### B. Semantic OS / grounding
`scripts/governance/query_semantic_os.py --validate|--summary|--ask|--ground` over
`docs/governance/semantic_os/{concepts,boundaries,contracts,journeys,file_identities}.yaml`.
**Ran `--summary`:** 15 concepts · 10 boundaries · 9 contracts · 1 journey (7 steps) · 854 objects
(projection) · 98 file identities · 11/11 spine files claimed · 80 findings + 18 hypotheses loaded ·
`authority: advisory` · 0 warnings. Agent twin: `truth.ground_claim`.

### C. Ontology / registries (meaning + conclusions)
`configs/formulas/market_ontology.yaml` (authority #1, §6.6) · `market_crt_states.yaml` ·
`src/features/registry/` behind `formula_registry` · `active_models.yaml` v2.1 ·
`miar_registry.json` · `closure_authority_index.json` · **GENERATED** `data/*.jsonl`: findings **81**,
script_registry **393**, framework_registry **41**, hypothesis_registry **18**. Query CLIs:
`query_registry.py`, `query_scripts.py`, `query_hypotheses.py`, `feature_surface_query.py`,
`export_findings.py`.

### D. AST / census / floors (instrument layer)
`behavior_census.py` · `feature_math_lint.py` · `feature_dag_layers.py` ·
`feature_certification_state.py` / `feature_dag_certify.py` · `config_reachability.py` ·
`script_census.py` · `module_census.py` · `graph_query.py` over `graph.dot` (92 KB, 2026-08-08) ·
`gen_citation_map.py` · `construction_protocol.py {validate-impact, validate-completion, check}`.
Volume: **372 scripts** — `research/` 138, `analysis/` 119, `governance/` 36, `data/` 22, `training/` 13.

### E. Telemetry / evidence stores
`logs/` per-instrument + `crt_transitions.jsonl`, `feature_snapshots.jsonl`,
`llm_episodes.enveloped.jsonl`, `integrity_events.jsonl`, `logs/index/{run,trade,instrument}_index.jsonl` ·
`results/` per-instrument + `results/research/` · `src/agent/log_query.py` · `src/events/event_fabric.py`
(has `EventType.LLM_TURN` — no new bus needed) · `src/journal/trade_identity_v1_0.py`.

### F. **[MISSED-BY-BOTH] Run-provenance / anti-hallucination spine** — the most important omission
| Piece | Path | What it does |
|---|---|---|
| Manifest builder | [src/utils/run_manifest.py](src/utils/run_manifest.py) | `build_manifest` is **FAIL-CLOSED**: a missing required field raises, so *"a claim without provenance cannot be constructed."* Writes `results/test_runs/<run_id>/{run_manifest.json, assertions.json, RUN_SHA256.txt}` |
| Required fields | same, `REQUIRED_FIELDS` | `run_id, timestamp_utc, command, argv, cwd, git_sha, branch, ACTIVE_VERSION, config_hash, validation_lens, exit_model, cost_model_bps, label_source, instruments, timeframe, data_source, network, dry_run, intended_work_item_id, validation_flow_review` |
| H1/H2/H3 guards | [src/utils/validation_contract.py](src/utils/validation_contract.py) | **H1** `require_manifest` — economic claim without manifest raises · **H2** `assert_summary_matches_manifest` — a prose summary cannot silently disagree with the manifest · **H3** `validate_manifest_against_intent` — lens/label/cost/instrument/network must match the work-item intent |
| Floors | `tests/harness/test_anti_hallucination.py` (AH-01..05), `test_run_manifest.py`, `test_validation_path.py` | *"a failed/empty run can never be reported as success"* |
| Adoption (measured) | — | 38 dirs under `results/test_runs/`, **48** `run_manifest.json` on disk, newest **2026-08-15**; **10** producers repo-wide; **7 of 138** `scripts/research/` |

This is the mechanical enforcement of the exact boundary this workflow exists to protect, it is live and
CI-floored, and **neither analysis named it.** It belongs in the turn state machine, not in a footnote.

### G. **[MISSED-BY-BOTH] Validation Access ladder — a purpose-built LLM surface**
`src/validation_access/{ladder,surfaces}.py` + `scripts/governance/validation_access_cli.py`.
Design `VA-XAUUSD-M15`, sequential gating **S → I → F → E**, dual surfaces by explicit design:
**Surface A** = human CLI narrative; **Surface B** = *"LLM evidence pack"* under
`results/validation_access/xauusd_m15/<run_id>/`. Docstring: *"Separated by design — never merge pack
JSON into CLI narrative or vice versa."* Authority: access/packaging only, no promotion.
A ready-made typed-evidence consumption surface for an LLM — unreferenced by either design.

### H. **[MISSED-BY-BOTH] Enforcement layer — CI + git hooks**
`.github/workflows/governance.yml` → on **push and pull_request**, runs
`python scripts/maintenance/check_governance_invariants.py --all` (GREEN_FLOOR, curated green set;
deliberately not whole-suite — ~66 known reds). `.github/workflows/erp-test-harness.yml`.
Local hooks: `hooks/{pre-commit,commit-msg}` with `git config core.hooksPath = D:\Tradelatest\hooks`
(verified active). F-071 recorded that this whole layer once existed only on disk. **A design that
proposes floors must know what already runs automatically** — otherwise it proposes redundant gates.

### I. **[MISSED-BY-BOTH] Navigation / inventory layer**
- `docs/book/` — **24 chapters + A1/A2 appendices**, the repository as a sequential narrative.
- `docs/book/encyclopedia/` — E1–E6 + **`encyclopedia_rows.jsonl` (813 rows**, generated 2026-08-07,
  fields `path, purpose, group, phase, relevance, book_status, package, classes`). A machine-readable
  **file→purpose map**. This is the natural seed for both a dispatch index and a RAG include list.
- `docs/topics/` — **29** concept docs (§6.4 Topic Sync Mandate).
- Excel: `DOC_TRACKING_INDEX.xlsx`, `scripts_business_functionality.xlsx`,
  `docs/analysis/{tests_functionality_inventory, claude_test_intent, grok_test_intent}.xlsx`.
  Inventory only — never runtime.

### J. **[MISSED-BY-BOTH] Episode-semantic + OSS lab (the newest committed work)**
HEAD commit 84fff51 shipped `src/research/episodes/` (`builder, events, flat, policy, projectors,
protocol, query, schema, store, tensors`) + `docs/governance/EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`
+ `oss_lab/` (`contracts/{dataset_manifest, fill_model, metric_cell, presence, run_manifest,
structural_fact, trade_record}`, `registry/oss_capabilities.jsonl` 9 rows, `evidence/repo_intel`,
`scenarios`, `runners`, `reproducibility`). **Name-collision to respect:**
`oss_lab/contracts/run_manifest.py` is a *benchmark reproducibility envelope*, a different object from
`src/utils/run_manifest.py` (family F). Intentional separation — do not unify, do not conflate.

### K. **[MISSED-BY-BOTH] Model artifacts + provenance sidecars**
`models/` — per-instrument dirs + `rr_model.json` with `.meta.json` / `.provenance.json` siblings,
`zone_registry.json` (+ `.provenance.json`, `.bak_*`), `gaussian_registry.json`, `rr_registry.json`,
`tradenet_registry.json`, `zone_gate_registry.json`, `bitnet/`, `replay/`. Conclusions already bind
here (F-041 runtime/manifest parity, F-076 all six families stale on ≤39-dim schemas). Gitignored class
— evidence citing `models/` paths does not resolve from a clean checkout (F-071 residue).

### L. **[MISSED-BY-BOTH] Concurrency layer — worktrees**
`git worktree list` shows **15**: the main tree, **11** `.claude/worktrees/claude-*`, two certification
trees (`D:/Tradelatest-{pre,post}-p1-cert`), one prunable scratchpad tree. Both a hazard (shared index,
`assistant_project.md` append-shared, `core.autocrlf=true` inflating `modified` counts) and a
**capability** (isolated experiments without touching the main tree).

### M. Data corpora / visual evidence
`data/mt5/` 192 MB (M5/M15/H1/H4 across FX + XAUUSD) · Binance corpora · `tools/tv_forensic/`
(`capture_tv`, `annotate`, `engine_data`, `htf_bars`, `tv_bridge`, `measure_corpus_clock`, `shots/`,
`shots_disp_exp/`; control-plane ids `tv_forensic.capture`/`.annotate`) · `mt5_analytics/` +
`exec_telemetry/` · `docs/governance/clock_evidence/`. Registered conclusions: F-080, F-081.

### N. Multi-LLM / context / control plane
`multi_llm/` (protocol, roles, `build_queue.jsonl`, `turn_ledger.jsonl`, `research_lane`) · `HANDOFF.md` ·
`scripts/context/{build_context,discussion,log_turn,pack_story}.py` → `context/01..06_*.md` (derived
Portable Mind; regenerate via `Compile`, never hand-edit) · `.grok/` overlay · `ChatGpt  workflow/`
(GATHER/ENHANCE/IMPLEMENT prompt framework + `index.html`) · `tests/Grok/` A–I and `tests/Claude/` J–M ·
`src/control_plane/registry.py` **44 `CommandSpec`s** (counted), localhost-only, no auth.

### O. RAG (sidecar; **not** grounding)
`src/retrieval/` + `scripts/rag_index.py {--rebuild,--incremental,query,metrics,verify,discover}`;
Chroma at `data/chroma_db/` (633 MB). Measured directly — see G-2.

---

## Part 3 — Interface map

```
                    ┌─ trigger vocabulary (CLAUDE.md §12) ──► session ritual
user phrase ──► DISPATCH ─┼─ PLAN_REGISTRY (src/agent) ──────► kitchen tool order
                    └─ .grok/INFRA.md ────────────────────► trader intents (+ code.* when CLAC lands)

authority:   ACTIVE_VERSION ──► get_prod_config ──► CRTConfig / ConfigBuilder
             market_ontology.yaml ──► formula_registry ──► derived_math
             SemanticGrounder ──► findings + hypotheses + closure index + ACTIVE_VERSION
             construction_protocol ──► GREEN_FLOOR ──► hooks/pre-commit + .github/workflows/governance.yml

provenance:  build_manifest ──► results/test_runs/<id>/ ──► require_manifest / assert_summary_matches_manifest
             validation_access ladder S→I→F→E ──► Surface B LLM evidence pack
             measurement contracts MC-* ──► (charter OPEN)

retrieval:   feature_surface_query · query_{semantic_os,registry,scripts,hypotheses}
             log_query · graph_query · encyclopedia_rows.jsonl · build_context → context/*.md
             RetrievalPipeline (artifact search ONLY)
```

**Non-edges — intentional separation, do not "fix":** INFRA ↛ `PLAN_REGISTRY` (`INFRA.md:11,165`) ·
RAG ↛ `PLAN_REGISTRY`/control plane · `findings.synthesize` ↛ `docs/current-findings.md` ·
`EnterpriseGate.verify` (chunk-count "grounded", [claude_integration.py:115](src/retrieval/claude_integration.py:115))
↛ `SemanticGrounder.ground` · `oss_lab` RunManifest ↛ `utils.run_manifest` · Portable Mind ↛ Tier 0 ·
encyclopedia/Excel ↛ runtime · TV mark ↛ `TRADE_OPENED`.

---

## Part 4 — Reconciliation with the prior Grok design

### Confirmed against source (adopt)
Five-type system; fail-closed promotion ladder; reuse existing enums; "playbook, not a fourth runtime";
compose three owners, never merge. Plus these drift claims, all verified:
`agent-reference.md:4` "14 intents, 20 registered tools" vs source **22 / 35** · `:101` phantom tool
`audit.inspect` (not in `REGISTRY`; `PLAN_REGISTRY["audit_inspect"]` correctly steps `audit.tail`) ·
`plan_compiler.py:41` comment "All 14 intents" · `semantic_ground` NL-unreachable (21 of 22) ·
`full_pipeline` step 5 `live_hook.dry_run` cannot construct (F-073) · `agent-memory.md` modes omit
`ops`/`truth` · generated `cli-matrix.md` pins `v2_multi_2026_04` while `ACTIVE_VERSION` =
**`v2_htfcrt_2026_08`**.

### Corrected
1. **RAG gap is measured, largest, and its proposed fix is insufficient** — see G-2.
2. **RAG freshness is not absent; it is structurally inert.** [monitor.py:53](src/retrieval/monitor.py:53)
   sets `_indexed_commit` from HEAD in `__init__` and never reloads, so `snapshot()` computes
   `HEAD..HEAD` = 0 in every fresh process. F-006/F-060 pattern. The true indexed commit is already
   persisted in `data/rag_metrics.jsonl`.
3. **Do not hard-depend on CLAC PR-1.** Verified: `.grok/CLAC.md` and `scripts/governance/build_clac.py`
   **do not exist** — CLAC PR-1 has not landed. Sequencing behind another agent's unlanded PR, in a tree
   15 worktrees share, is a stall. Degrade gracefully instead.

### Added in rev 1
4. **The dispatch table must be GENERATED, not hand-written** — a hand-maintained owner table is exactly
   the artifact class that just drifted (14/20 vs 22/35). The repo owns the counter-pattern
   (`generate_cli_matrix.py`, `generate_script_matrix.py`, `gen_citation_map.py`). §6.5 corollary:
   *correcting the instrument creates more value than optimizing the system.*
5. **Multi-agent attribution belongs in BOOT** (family L).
6. **Load economics are a constraint** — `CLAUDE.md` is **123,038 bytes** and auto-loaded. A playbook
   not reachable from an auto-loaded surface does not bind; one pasted in full taxes every session.
7. **`TruthConflict` to surface, not resolve:** `cli-matrix.md` argv vs `ACTIVE_VERSION`. Source is
   `registry.py` `CommandSpec` templates — a control-plane owner's call.

### Added in rev 2 (the missed layers)
8. **Run-provenance is the real evidence→conclusion gate** (family F) — and it is under-adopted, not
   absent. Route to it; do not rebuild it.
9. **Enforcement already exists** (family H) — CI on push/PR + active local hooks. Propose no gate that
   duplicates GREEN_FLOOR.
10. **`encyclopedia_rows.jsonl` (813 rows) is the ready-made file→purpose map** — the correct seed for
    both the dispatch index and the RAG include list. Neither design used it; both proposed hand-listing.
11. **Surface B of the validation-access ladder is already "the LLM evidence pack"** (family G) — the
    playbook should consume it rather than define a new pack shape.
12. **Two provenance regimes are in play and neither binds recent research** — see G-1.
13. **A doctrine-header claim is stale:** the M0 migration index in `assistant_project.md` (lines ~40-46)
    references `services/` — **no `services/` directory exists**. DOC_DRIFT in the doctrine header both
    analyses treated as a standing-rule artifact.

**Name:** keep **"Claude Operating Playbook."** A second name for one procedure is the fragmentation
this exercise exists to prevent.

---

## Part 5 — Gaps (verified, ranked)

| ID | Gap | Evidence | Blocks | Extend (do not rebuild) |
|---|---|---|---|---|
| **G-1** | **Two provenance regimes; neither binds the newest research.** `utils.run_manifest` (H1/H2/H3, CI-floored) is used by **7 of 138** `scripts/research/` producers. The parallel regime is measurement contracts — **5 `MC-*` instance files exist on disk** (`configs/research/measurement_contracts/instances/`) while the Closure & Authority Index states *0 sealed instances* and the charter is `OPEN`. Yesterday's `scripts/research/p_struct_01_displacement_evidence.py` (2026-08-18) matches **neither** (0 hits for `build_manifest`, 0 for `MC-`). | a session cannot tell which envelope makes its claim admissible, and the newest evidence table has none | a routing rule + `require_manifest`; **P-GOV-MC-01 owns the MC side** |
| **G-2** | **RAG corpus omits every authority surface and is dominated by one generated census.** Measured read-only from `data/chroma_db/chroma.sqlite3`: 149,853 chunks in `tradelatest_rag`. Domains: governance **127,481 (85%)**, config 7,752, source_code 6,410, tests 5,296, analysis 1,757, architecture 677, research 344, intent 69, operations 67. Largest single file = `docs/governance/behavioral_constant_authority_trace-2026-07-11.json` at **39,997 chunks (27% of the index)**. Path probes (separator-agnostic): `CLAUDE.md` **0** · `docs/current-findings.md` **0** · `docs/topics/` **0** · `docs/reference/` **0** · `docs/memory/` **0** · `docs/book/` **0** · `scripts/**` **0** · `docs/governance/semantic_os/*.yaml` **0** · `active_models.yaml` **0**. (Present: `configs/production/` 6,088 · `market_ontology.yaml` 30 · `src/core/` 534 · `src/features/` 451 · `src/agent/` 162.) | search cannot see the bootloader, the conclusions record, the concept index, the Semantic OS, the model registry, the book, or any of 372 scripts | `domain_patterns` **plus** a cap/exclusion for generated census JSON ([config.py:66-97](src/retrieval/config.py:66)); seed the include list from `encyclopedia_rows.jsonl` |
| **G-3** | **No session dispatcher naming which of the three owners owns a phrase** | three owners exist; no table joins them | cold session re-derives routing or invents a fourth registry | generated dispatch index (Part 6) |
| **G-4** | **No typed-retrieval rule in any auto-loaded surface** | §6.7 mandates grounding but gives no retrieval order; nothing says "RAG is search, not grounding" | type promotion — or over-grounding that stalls Orient | ≤12-line CLAUDE.md §14 pointer |
| **G-5** | **RAG staleness gate structurally inert** | [monitor.py:53](src/retrieval/monitor.py:53); `HEAD..HEAD` = 0; real commit already in `data/rag_metrics.jsonl` | a hit's currency is unknowable | read the last index event's `commit_hash` |
| **G-6** | **Operator docs disagree with source** | `agent-reference.md:4` and `:101`; `plan_compiler.py:41`; `agent-memory.md` modes | wrong counts; hunting a tool that does not exist | header/comment hygiene only |
| **G-7** | **No attribution discipline for a 15-worktree shared tree** | `git worktree list` = 15; 2026-08-18 attribution entry needed transcript fingerprinting | a session edits or reports another agent's WIP | BOOT step + `.grok/PENDING.md` |
| **G-8** | **No authority-preserving join recipe** (visual ↔ CRT ↔ finding ↔ test) | F-081 exists because marks were nearly counted as trades | silent type collapse | join card (Part 6) |
| **G-9** | Doctrine-header drift: M0 index cites `services/`, which does not exist | `ls services` → absent | cold session hunts a non-existent tree | one-line correction |

### Non-gaps — do not build
A Claude-specific `PLAN_REGISTRY` · wrapping every CLI as an agent tool · putting RAG in
`PLAN_REGISTRY`/control plane · a third `RunManifest` · a new evidence-pack format (Surface B exists) ·
new CI gates duplicating GREEN_FLOOR · rebuilding Semantic OS as a graph DB · a free-tool-choice
meta-agent (`grok_agentic.py` Mode D forbidden) · Portable Mind as the workflow · indexing
`assistant_project.md` as truth · fixing F-073 here · enabling BitNet/rr_fusion because the code exists.

---

## Part 6 — Proposed design: the Claude Operating Playbook

A **procedure plus one generated index**. No daemon, no package, no new authority, no new KPI.

### 6.1 Session vs turn

**Once per session** (re-run only if `ACTIVE_VERSION` or the lane could have changed):
1. **BOOT** — load only the §0 memory doc matching the task domain. Never open `.env`.
2. **ORIENT_RUNTIME** (§4.0) — read `ACTIVE_VERSION`; load via `get_prod_config()`; verify keys against
   `CRTConfig`/`ConfigBuilder`; record `ACTIVE_VERSION=<v>`.
3. **NAME_LANE** (G-7) — state the lane; check `git status` shape, `git worktree list`,
   `.grok/PENDING.md` open rows. Unfamiliar untracked paths = another session's WIP; leave alone.

**Every turn:**
`DISPATCH → (GROUND) → RETRIEVE_TYPED → ACT → (PROVENANCE) → (VALIDATE_FLOOR) → CLOSE`,
with `ASK_USER` reachable from DISPATCH (unknown/collision) and from GROUND (UNKNOWN on a token the user
asked to use as if it existed).

### 6.2 DISPATCH — one owner, fail closed

| Phrase class | Owner | Next step | Stop if |
|---|---|---|---|
| `Orient` `Status` `Continue` `Next step` `Map` `Audit` `Sync` `Plan` `Log` `Compile` `Validate` (as §12 trigger words) | trigger vocabulary | that trigger's documented load list | the trigger would grant new authority |
| tune / validate-checkpoint / promote / backtest / advise / veto / resize / ops diagnose / truth janitor | `PLAN_REGISTRY` via `python -m src.agent.cli` | `IntentRouter → PlanCompiler → Executor` | `ask_user`; unconfirmed write; path-guard |
| "is this a setup" / "does it make money" / walk a candle / pending / semantic review | `.grok/INFRA.md` | that intent's happy flow | gates 1–4 UNKNOWN; P-GOAL-04 off for money |
| coding: orient-this-change / classify / implement / validate the floor | INFRA `code.*` **once CLAC PR-1 lands** | that `code.*` flow | **`PENDING_CLAC`** → fall back to trigger `Implement` + construction protocol |
| "ground this noun" / "does CN-001 exist" | Semantic OS CLI | `--ground` / `--ask` | status ≠ `GROUNDED` on a new claim |
| "what does this feature join to" | `feature_surface_query.py` | `--feature` / `--search` | `AmbiguousAliasError` |
| "what is this file for" / "where does X live" | `encyclopedia_rows.jsonl` (813 rows) + `graph_query.py` | row lookup → source | row is inventory, never runtime behavior |
| "show me the validated evidence for XAUUSD" | validation-access **Surface B** pack | `validation_access_cli.py` | ladder rung not reached (S→I→F→E gating) |
| "search the repo" | RAG **as search** | `rag_index.py query`, then re-ground any noun you assert | treating a hit as `GROUNDED`; **G-2 blind spots apply** |
| anything else | `ask_user` | state UNKNOWN, offer the table | guessing |

**Meta-rule:** exactly one owner. Two owners after the collision matrix → `ask_user`. Never a fourth table.
Collisions to encode: bare `orient` · `Validate` (trigger vs kitchen `validate_only` vs `code.validate`) ·
`Compile` vs `code.regenerate` vs `how.regenerate` · `record this` (trigger `Log` vs `closure.record`) ·
`implement` (trigger vs `code.implement` vs the `/implement` skill) · **`run manifest`
(`utils.run_manifest` vs `oss_lab/contracts/run_manifest`)**.

### 6.3 RETRIEVE_TYPED — ordered ladder
1. Ground the token → Semantic OS. 2. Concept? → ontology / `formula_registry` / MIAR.
3. Conclusion? → `docs/current-findings.md` + `closure_authority_index.json`.
4. Evidence? → the named procedure's artifact **and its run manifest**.
5. Artifact search? → encyclopedia rows / RAG / grep / `graph_query`.

Skipping to (5) is legal **only** when the user asked for a search. **Grounding carve-out:** citing a
token already bound on a loaded authority page (Repository Truths Index, closure index, `ACTIVE_VERSION`)
needs no subprocess per id. Ground when asserting a **join**, an **implementation fact not on the loaded
page**, or a **token the user just invented**.

### 6.4 PROVENANCE — the rev-2 state (G-1)
If the turn produces or repeats an **economic or market claim** about a run:
- claim derives from a run **this turn produced** → the producer writes `build_manifest` + `write_run`;
- claim derives from an **existing** run → `require_manifest(run_dir)` before repeating it, and
  `assert_summary_matches_manifest` before writing the prose summary;
- **no manifest resolvable** → the claim is reported as **`PROVENANCE_ABSENT`** and may not be typed as
  evidence, promoted to a finding, or given a number in a summary.
Measurement contracts (`MC-*`) are a **separate** admissibility question owned by P-GOV-MC-01; the two
are not substitutes and neither implies the other.

### 6.5 Join card (G-8)
`claim` · `left` (type + artifact + procedure) · `right` (type + artifact + procedure) · `join key`
(what makes them the same object — timestamp? trade id? FM id?) · `evidence_class`
(`PROVEN|HEURISTIC|TEXT_REFERENCE`) · `what this does NOT establish`.
Missing join key → the claim is not made. A TV mark joined to a bar timestamp is a *bar* join, never a
*trade* join.

### 6.6 CLOSE
Read-only turn → answer + typed sources. State-changing turn → `construction_protocol.py check`
(the hooks/CI will re-run GREEN_FLOOR — do not add a parallel gate) **then** the §7.4 SESSION LOG entry.
Conflicts → `TruthConflict` shape (§6.2 rule 3), never a silent pick.

### 6.7 Never
Edit `ACTIVE_VERSION` as a side effect · add `PLAN_REGISTRY` keys · merge the three owners · promote a
type · emit a numeric economic claim without a resolvable manifest · call `live_hook.dry_run` · enable
BitNet/rr_fusion · hand-edit a GENERATED artifact · treat RAG as grounding · claim measurement-layer
closure · act on another session's untracked WIP.

---

## Part 7 — Implementation PR plan

Classified against `docs/governance/change_contracts.json` (13 classes verified). No PR touches `src/`
decision paths, `configs/production/`, or `ACTIVE_VERSION`. Each ends with
`python scripts/governance/construction_protocol.py check`.

### PR-1 — Generated dispatch index `[DOCUMENTATION_ONLY + SCRIPT_LIFECYCLE_CHANGE]`
**The core ship. Do not hand-write the table.**
- **New:** `scripts/governance/build_dispatch_index.py`, modelled on `generate_script_matrix.py`.
  Reads at build time: `PLAN_REGISTRY` keys + each step's tool + `REGISTRY` write flags (import, not
  parse); `_MODE_INTENTS`; the §12 trigger list; `.grok/INFRA.md` rows; `core_command_specs()`; and
  **`docs/book/encyclopedia/encyclopedia_rows.jsonl`** for the file→purpose column (rev-2 addition 10).
- **Graceful CLAC degradation:** `.grok/CLAC.md` absent → emit `code.*` rows as `PENDING_CLAC` with the
  named fallback owner. A rerun fills them when CLAC lands. **No hard dependency.**
- **New (generated):** `docs/architecture/dispatch-index.generated.md` — owner table + collision matrix +
  retrieval ladder + the provenance rule. Header carries `generated_at`, generator path, never-hand-edit banner.
- **New floor:** `tests/test_dispatch_index_sync.py` — regenerate in-memory, assert byte-equality with the
  committed file, and assert every `PLAN_REGISTRY` key and every `REGISTRY` tool appears exactly once.
  This makes the 14/20-vs-22/35 drift class *impossible*, not merely corrected.
- **SITS same turn:** `script_census.py --write-stubs` → `seed_script_registry.py` →
  `generate_script_matrix.py` (unregistered paths fail GREEN_FLOOR).

### PR-2 — Provenance routing rule `[DOCUMENTATION_ONLY]` (G-1) — highest value per line
No new code. Add §6.4 as a short section in the generated index and one line in the CLAUDE.md pointer:
economic/market claim → `build_manifest` (producing) or `require_manifest` (repeating) or label
`PROVENANCE_ABSENT`. Name the `MC-*` question as separately owned. Optionally add a
`test_dispatch_index_sync` assertion that the rule text is present. **Reuses family F entirely.**

### PR-3 — Bind from the auto-loaded surface `[DOCUMENTATION_ONLY]`
≤12 lines added to `CLAUDE.md` as **§14 Session Dispatch**: five types one line each, the retrieval
ladder, the one-owner meta-rule, the provenance rule, and a pointer to the generated index. Plus one line
in `docs/architecture/trigger-vocabulary.md`'s cold-start recipe. **No prose duplication** — the generated
index is the body. Nothing else may grow `CLAUDE.md` in this train.

### PR-4 — Doc hygiene `[DOCUMENTATION_ONLY]` (G-6, G-9)
Auto-fixable drift only, changing no registered conclusion: `agent-reference.md:4` → 22 intents /
21 classifiable / 35 tools; delete the phantom `audit.inspect` row at `:101`; `plan_compiler.py:41`
comment → 22; `agent-memory.md` modes → add `ops`, `truth`; `assistant_project.md` M0 index → drop or
mark the non-existent `services/` (G-9). **Not** in scope: hand-editing generated `cli-matrix.md`.
**Surface, do not resolve:** the `cli-matrix` argv vs `ACTIVE_VERSION` `TruthConflict`.

### PR-5 — RAG corpus + staleness `[SCRIPT_LIFECYCLE_CHANGE]` — **user-gated** (G-2, G-5)
- **5a (cheap, first):** read the last `{"event":"index"}` `commit_hash` from `data/rag_metrics.jsonl`
  into `Monitor._indexed_commit` instead of `_get_current_commit()`
  ([monitor.py:53](src/retrieval/monitor.py:53)); print a staleness banner on `query`. ~10 lines, no reindex.
- **5b:** extend `domain_patterns` to `CLAUDE.md`, `docs/current-findings.md`, `docs/topics/**`,
  `docs/reference/**`, `docs/memory/**`, `docs/book/**`, `docs/governance/**/*.yaml` (**recursive** — the
  current pattern is non-recursive and misses all of `semantic_os/`), `active_models.yaml`, `scripts/**/*.py`.
  Derive the include list from `encyclopedia_rows.jsonl` rather than hand-listing.
- **5c (required with 5b):** cap or exclude generated census JSON under `docs/governance/*-2026-*.json`.
  Without it, one artifact keeps 27% of the index and the new authorities are drowned. Rebuild cost is
  real: 633 MB, 149,853 chunks.
- Floor: extend `tests/test_retrieval_pipeline.py` with a corpus-**coverage** assertion (never a relevance claim).

### PR-6 — `semantic_ground` NL reachability `[SCRIPT_LIFECYCLE_CHANGE]`
Add the key to `_MODE_INTENTS` + `intent_patterns.json` → 22/22 classifiable. Headers stay
"21 classifiable" until this lands. Sequence after PR-4 so counts change once.

### Owned elsewhere — do not clone
CLAC PR-1 (`.grok/CLAC.md`, INFRA `code.*`, `build_clac.py`) · P-GOV-MC-01 (MC-id resolution; the
5-files-vs-0-sealed conflict) · F-073 live rail · control-plane `CommandSpec` argv templates ·
CRT re-certification · episode-semantic Phase 3 · `oss_lab` roadmap.

---

## Verification

1. **PR-1:** `python scripts/governance/build_dispatch_index.py` → empty diff on rerun;
   `pytest tests/test_dispatch_index_sync.py -q` green; **mutate one `PLAN_REGISTRY` key and confirm the
   floor goes red** (a floor that cannot fail enforces nothing — E-001F);
   `python scripts/governance/query_scripts.py --validate` green.
2. **PR-2:** take the three most recent economic claims in the session log and confirm each resolves to
   a manifest, an `MC-*`, or `PROVENANCE_ABSENT` — `p_struct_01` is the known `PROVENANCE_ABSENT` case.
3. **PR-3:** §14 is ≤12 lines and `CLAUDE.md` grows <1 KB; every phrase class in 6.2 resolves to exactly
   one owner on a cold read.
4. **PR-4:** `pytest tests/test_doc_citations.py -q` green; grep shows no live `audit.inspect`;
   `len(PLAN_REGISTRY)` / `len(REGISTRY)` match the doc headers.
5. **PR-5a:** `python scripts/rag_index.py metrics` reports non-zero `embedding_staleness_commits`
   against an index built at an older commit (currently always 0 — that is the red-before-green proof).
   **PR-5b/c:** re-run the G-2 sqlite probe; assert `CLAUDE.md`, `docs/current-findings.md`,
   `docs/topics/`, `docs/governance/semantic_os/` all > 0 and no single file exceeds ~5% of chunks.
6. **PR-6:** `python -m src.agent.cli` with a natural-language grounding phrase classifies to
   `semantic_ground`, not `ask_user`.
7. **Every PR:** `python scripts/governance/construction_protocol.py check` green;
   `python scripts/maintenance/check_governance_invariants.py --all` green — this is what
   `hooks/pre-commit` and `.github/workflows/governance.yml` already run, so no new gate is added.
8. **Whole-design acceptance:** run the 6.2 table against 10 real phrases from recent session-log entries;
   every one lands on exactly one owner or `ask_user`, with zero type promotions in the answers.

## Authority statement

Grants **no** production, promotion, activation, or live-order authority (§6.5). Routing and hygiene only.
No F-id. No G001 claim. No ontology node. No `ACTIVE_VERSION` change.
