# Architecture doc sync audit (2026-09-14)

> Status: **AUDIT ONLY** — no silent edits applied to canonical architecture docs.
> Live tree: `D:\Tradelatest`. Compared docs ↔ code after probes extraction Batch 6b/6c and UI kit reality.

## Canonical doc map (what exists)

| Role | Path | Notes |
|------|------|-------|
| Technical architecture (CLAUDE-linked) | `docs/reference/architecture.md` | Tech stack, tree, data flow |
| Memory index | `docs/memory/architecture-memory.md` | Cross-cutting index |
| Memory policy | `docs/memory/ARCHITECTURE_MEMORY_POLICY.md` | Hierarchy: CLAUDE → memory → deep docs → **code wins** |
| Deep maps | `docs/architecture/*` | signal-flow, goal, target-strategy, etc. |
| LLM stitch dump | `MASTER_ARCHITECTURE_REFERENCE.md` | Assembly for LLM handoff, not a rewrite |
| UI archaeology (stale date) | `docs/analysis/UI_ARCHAEOLOGY.md` (2026-06-12) | 4 UI systems; predates Knowledge tab |
| UI live gap | `docs/UI_DESIGN_GAP_FROM_LIVE.md` (2026-09-09) | TopBar vs sidebar vs dual kits |
| UI↔code nav | `docs/UI_LLM_NAVIGATION.md` + `.jsonl` | Unified-shell framing over two kits |

## Drift findings (doc vs live code)

### D1 — `src/research/probes/` missing from architecture tree
- **Code:** package present (`atlas_io`, `corpus`, `costs_path`, `excursion`, `governance`, `horizon`, `persistence`, `phase1_replay`, `scoreboard`, `scriptmod`, `shadow_collapse`).
- **Docs:** `docs/reference/architecture.md` and `MASTER_ARCHITECTURE_REFERENCE.md` mention **0** hits for `research/probes` / `scriptmod` / `load_py`.
- **Dir tree in architecture.md** still describes `llm_research/` but not the probes extraction lane.
- **Recommended edit:** Add under `src/research/` in §2 Directory Structure + a short § on “Research probes (shared helpers; thin CLIs under `scripts/research|analysis`)” pointing at `scriptmod.load_py` as the sole `importlib` choke-point under `src/`+`scripts/`.

### D2 — UI surface under-documented in architecture.md
- **Code:** Active UIs are `ui_kits/control_plane/` + `ui_kits/crt_dashboard/` served by `src/control_plane/server.py` on `:8787`. `src/ui/` is empty package only.
- **Docs:** architecture.md has **0** hits for `ui_kits` / `crt_dashboard` / `run_id`. Control plane is mentioned as HTTP server; React kits not named as product UI.
- **Recommended edit:** Replace/extend control-plane UI paragraph with dual-kit map + pointer to `docs/UI_LLM_NAVIGATION.md`. Explicitly mark `src/ui/` as dead/empty.

### D3 — RAG / retrieval lane almost absent from architecture.md
- **Code:** live RAG is truth-tier lexical under `src/retrieval/` (BM25 + DuckDB/Parquet) — prior read of tree; Knowledge page exists (`page9_knowledge.jsx`).
- **Docs:** architecture.md “rag” string hits are mostly substrings inside other words (e.g. coverage); no real DuckDB/Parquet/retrieval section. MASTER also 0 for RAG/retrieval.
- **Recommended edit:** Add a “Knowledge / retrieval” subsection: lexical RAG, CLIs, `/api/knowledge/*` if still accurate — **verify endpoints against `server.py` before writing**; do not invent routes.

### D4 — UI archaeology stale vs live dashboard
- Archaeology (Jun): 8 dashboard pages not listed with Knowledge; embedded vs React dual systems.
- Live (Sep gap + code): TopBar includes Knowledge; Research exists in app but not always TopBar; sidebar IA richer than TopBar; System/Intelligence/Replay still scaffold/synthetic per gap doc.
- **Recommended edit:** Refresh `UI_ARCHAEOLOGY.md` status table OR add a dated “supersedes” note pointing at `UI_DESIGN_GAP_FROM_LIVE.md` + this plan — **ask whether to rewrite archaeology or leave as historical**.

### D5 — run_id already first-class in control plane, invisible in architecture.md
- **Code:** `RunRecord.run_id` = `uuid.uuid4().hex`; persistence `results/{instrument}/{instrument}_{run_id[:8]}.json`; legacy `logs/control_plane/runs/{run_id}.json`; APIs `/runs`, `/runs/{run_id}`, logs/artifacts/monitors/report.
- **Dashboard:** `app.jsx` already threads `run_id` on some model/list mappers.
- **Docs:** architecture.md 0 `run_id`; route map in `UI_ROUTE_MAP.md` is the better current source.
- **Recommended edit:** Cross-link architecture.md → UI_ROUTE_MAP run APIs; state that **control-plane run_id is the closure key** for launched jobs.

### D6 — Multiple “architecture” authorities
- CLAUDE hierarchy says code wins; deep companions under `docs/architecture/` + `docs/reference/architecture.md` + MASTER stitch.
- Risk: updating only one leaves LLM/human confusion.
- **ASK USER (do not silent-pick):** which file(s) are in-scope for sync edits this pass.

## Proposed sync patch set (NOT APPLIED)

1. `docs/reference/architecture.md` — probes + ui_kits + retrieval + run_id pointers (minimal surgical).
2. `docs/memory/architecture-memory.md` — add index entries for probes lane + UI kits + run_id closure.
3. Optional: short “Current as of 2026-09-14” banner on MASTER pointing to reference/architecture + UI_LLM_NAVIGATION (avoid regenerating MASTER).
4. Optional: archaeology supersession note.

## Ambiguities requiring user choice

See chat widget / companion questions:
A. Canonical update targets
B. Archaeology: rewrite vs historical leave + pointer
C. Whether MASTER gets more than a banner
