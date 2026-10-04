# Backwards-Dependency Refactor — Review of Haiku's Work + Completion Plan

## Context
A prior Haiku session ran the ownership audit (Pyan `graph.dot`) and implemented two of the three
HIGH backwards-dependency fixes:
- **HIGH #1** — extract `state_identity.py` to break `crt_engine_v2 ↔ state_contract_loader/state_topology`.
- **HIGH #3** — move `make_neural_fn_v2()` from `trainer.py` → `trade_net_v2.py`.
- **HIGH #2** (`llm_inference_client`) — intentionally PARKED.

This turn reviewed that work, found and repaired defects it introduced, and got the core + doc-citation
tests green. Plan mode then re-activated, so the remaining governance close-out items are captured here
for approval before execution.

---

## Review Findings

### What Haiku did correctly
- Created `src/config_layer/state_identity.py` holding `CRTState`/`Direction`/`RejectReason`/`VALID_TRANSITIONS`/`CRTConfig` (data-only, zero cyclic imports).
- Removed those definitions from `crt_engine_v2.py`; added a re-export line (`crt_engine_v2.py:36`) so old imports still resolve.
- Repointed `state_contract_loader.py` + `state_topology.py` to import from `state_identity`.
- Moved the `make_neural_fn_v2()` factory to `trade_net_v2.py`; removed it from `trainer.py`.
- Source-level dependency direction is now clean (verified this turn).

### Defects Haiku introduced (now FIXED this turn)
1. **16 broken imports** from the blanket `sed`. Lines that imported a *moved* symbol AND a *stayed*
   symbol (e.g. `from config_layer.crt_engine_v2 import CRTConfig, EngineState, StateMachine, Range, Direction, Candle`)
   were wholesale rewritten to `state_identity`, which does not contain `Candle/StateMachine/EngineState/Range/...`.
   → Repaired by pointing those mixed lines back to `crt_engine_v2` (which re-exports the moved symbols).
   Files: `interpreters/{contract,point_and_figure,reference}.py` + 13 test files.
2. **Doc-citation drift** (`tests/test_doc_citations.py` went RED): `docs/topics/crt-spine.md:20`
   cited `crt_engine_v2.py:1143 · VALID_TRANSITIONS` (now at `state_identity.py:69`).
   → Fixed crt-spine.md (test green), plus living-doc citations in `CLAUDE.md:73/148` and
   `docs/architecture/event-taxonomy.md:72`.

### Defects Haiku introduced — STILL OPEN (need execution approval)
3. **SESSION LOG never persisted** (§6, non-optional). Haiku printed the log block in chat but did
   not append it to `assistant_project.md`. No entry for the refactor OR this review exists there.
4. **`docs/architecture/citation-map.generated.md`** not regenerated — a GENERATED artifact that may
   still carry stale `crt_engine_v2` line/symbol citations for the 5 moved symbols.
5. **Graph not regenerated** — `graph.dot` still shows the 3 pre-fix backwards edges. `gen_pyan.py`
   fails on Windows (`WinError 206`, command line too long). Backwards-dep removal was instead proven
   at the source level this turn (HIGH #1 + #3 both RESOLVED).
6. **No memory file** written for the durable belief (Intelligence-Compounding mandate §6.1).
7. Optional hygiene: `crt_engine_v2.py` may have a now-unused `Enum`/`auto` import (1 residual match).

---

## Verified state after this turn's repairs
- `python -m pytest tests/ --collect-only` → **3348 tests collected, 0 import errors**.
- Targeted suites green: CRT/config/state (134p/10s), interpreters+ontology (46p), state
  contract+topology (39p), training (70p), doc-citations+topic-docs (5p).
- Source-level verifier: HIGH #1 and HIGH #3 backwards edges both **RESOLVED**; dependency
  direction is one-way (`crt_engine_v2 → {loader,topology} → state_identity`; `trade_net_v2 → trainer`).

---

## Remaining Work (execute on approval)

1. **Regenerate the citation map** (GENERATED artifact — never hand-edit):
   `python scripts/analysis/gen_citation_map.py` → rewrites `docs/architecture/citation-map.generated.md`.
   Then re-run `tests/test_doc_citations.py` + `tests/test_topic_docs.py` to confirm green.

2. **Full regression sweep** (the plan's original success criterion — only targeted subsets ran so far):
   `python -m pytest tests/ -q` from repo root (ACTIVE_VERSION = `v2_multi_2026_04` resolves at root).
   Investigate any red that isn't pre-existing (baseline the repo already had unrelated M-state).

3. **Optional hygiene**: remove the now-unused `Enum`/`auto` import from `crt_engine_v2.py` if
   confirmed dead (grep for remaining uses first; skip if still referenced).

4. **Graph regeneration** (best-effort): `gen_pyan.py` hits `WinError 206` on Windows. Either
   (a) run it in a chunked/`@argfile` mode if supported, or (b) record that the graph is refreshed on
   the next Linux/CI run and rely on the source-level proof. Do NOT block completion on this.

5. **SESSION LOG (§6, non-optional)** — append ONE `📝 SESSION LOG ENTRY` block to
   `assistant_project.md` covering both the refactor and this review/repair, including the
   `Belief Update / ROI / Goal` line. (Backfill Haiku's missing entry as part of the same block.)

6. **Memory file (§6.1)** — write a `project`-type memory (e.g. `project_backwards_dep_refactor.md`)
   capturing: the ownership-via-dependency-direction method, the `sed`-mixed-import gotcha, the
   re-export back-compat pattern, and that HIGH #2 remains parked; add a one-line pointer to `MEMORY.md`.

7. **Archive the audit** (post-implementation housekeeping): move the scratchpad
   `BACKWARDS_DEPENDENCY_AUDIT.md` + `ownership_audit.py` into `docs/governance/ownership-audit-2026-07-18.md`
   (living record of the method + the 3 findings), so the method is reusable for future "shared service" hunts.

8. **HIGH #2 remains PARKED** — no action; noted as the next cycle's candidate (`llm_transport` extraction).

---

## Verification (end-to-end)
- `python -m pytest tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py -q` → green (governance floors).
- `python -m pytest tests/ -q` → no new reds vs baseline.
- Source-level dep check re-run → HIGH #1 + #3 both RESOLVED (already passing).
- `assistant_project.md` tail shows the new SESSION LOG block; `MEMORY.md` shows the new pointer.
- `git status` review before any commit (commit only on explicit user request; branch first if on main).
