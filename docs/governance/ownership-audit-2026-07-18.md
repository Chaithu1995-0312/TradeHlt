# Module Ownership Audit — Backwards-Dependency Census (2026-07-18)

> **Method record + findings.** Point-in-time analysis per §6.2 (not a living doc). Preserves the
> reusable "ownership-via-dependency-direction" technique for finding alleged *shared services* in
> the codebase, and records the three HIGH backwards-dependencies it surfaced + their disposition.

## The method (reusable)

A module that *looks* like a shared service (high in-degree — many importers) is only a **true
service** if the dependency direction is one-way: consumers import *from* it, and it does **not**
import *from* its consumers. When a high-in-degree module imports from its own importers, that is a
**backwards dependency** (import cycle / mixed ownership) — the module is both a service and a
consumer of its consumers.

Procedure (`scripts/analysis/gen_pyan.py` → `graph.dot`):
1. Parse `graph.dot` edges (`A -> B` = *A imports B*).
2. Compute in-degree per node; candidates = in-degree ≥ 5.
3. For each candidate, flag any node that is BOTH an importer of it AND imported by it → backwards dep.
4. Classify: clean shared service (one-way, high in-degree) vs orchestrator/interface vs backwards-dep.

Census result: **217 nodes, 696 edges, 33 candidates (in-degree ≥ 5), 3 backwards dependencies.**
Cleanliness ratio ≈ 90.9%. The clean shared services (no back-edge) included
`config_layer.production_config` (54), `utils.logging_config` (36), `features.feature_schema` (35).

## The three HIGH findings

| # | Module (in-deg) | Backwards edge (imported its own consumer) | Root cause | Disposition |
|---|---|---|---|---|
| **HIGH #1** | `config_layer.crt_engine_v2` (16) | imported `state_contract_loader` + `state_topology`, which imported `crt_engine_v2` back | CRT state identity (enums + `VALID_TRANSITIONS` + `CRTConfig`) lived in the engine; the loader/topology had to import them to validate/build the graph | **RESOLVED** — extracted `config_layer/state_identity.py` (data-only, zero cyclic imports); loader/topology now import from `state_identity`; engine re-exports the five symbols for back-compat |
| **HIGH #3** | `training.trainer` (5) | imported `training.trade_net_v2`, its own consumer | the `make_neural_fn_v2()` factory (which constructs `TradeNetV2`) sat in `trainer.py` instead of where the owned type lives | **RESOLVED** — moved `make_neural_fn_v2()` to `trade_net_v2.py`; `trainer` no longer imports its consumer |
| **HIGH #2** | `config_layer.llm_inference_client` (9) | lazy `__getattr__` re-export cycle with `llm_scorer` / `llm_narrative` | scorer/narrative need HTTP transport; client re-exports their fns for back-compat → deferred-import cycle | **PARKED** — future cycle: extract `config_layer/llm_transport.py` (pure transport) so all three import from it |

## Verification (2026-07-18)

- Source-level dependency direction re-checked: HIGH #1 + HIGH #3 both **one-way** now
  (`crt_engine_v2 → {loader,topology} → state_identity`; `trade_net_v2 → trainer`). No back-edge.
- `pytest --collect-only` → 3348 tests, 0 import errors. Targeted CRT/state/training/interpreter
  suites green. Doc-citation + topic-doc floors green after citation-map regen.
- `graph.dot` regeneration on Windows hits `WinError 206` (command line too long); the backwards-dep
  removal was proven at the source level instead. Graph refreshes on the next Linux/CI `gen_pyan` run.

## Gotcha (for the next audit)

Do **not** blanket-`sed` import lines when extracting symbols to a new module. Lines that import a
*moved* symbol AND a *stayed* symbol on the same line (e.g.
`from config_layer.crt_engine_v2 import CRTConfig, StateMachine, Candle`) get wholesale-rewritten to
the new module, which lacks the stayed symbols → broken imports (16 occurred here). The safe pattern:
keep a **re-export** in the origin module so mixed-symbol lines can point back to it unchanged.
