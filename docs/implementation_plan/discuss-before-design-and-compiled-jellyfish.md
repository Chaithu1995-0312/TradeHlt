# System-first narrowing: SYSTEM_FLOW (discussion before design)

## Context
User direction (2026-09-27): stop building governance. First finish and stabilize the **system**
(OHLC → … → trade → outcome), user starts/commits it, and only then lay governance on top.
User's question: **has Claude actually traced the whole system end to end?** Answer from
evidence, then narrow layer by layer: findings → discussion → design per layer. No implementation
drift. Save the direction to memory.

## Finding 0 — Has the end-to-end check been done? **No.** (verified 2026-09-27)

| Artifact (existing) | What it proves | What it does NOT prove |
|---|---|---|
| `graph.dot` + `docs/architecture/code-map.generated.md` (2026-09-16, `gen_code_map.py`) | Static **import** graph, 625 `src/` modules, 1,477 edges | Which code actually **runs**, from which entry point, to which output |
| `pyan_call_flow.dot` (68k lines) | Call graph | **Stale** — last change 2026-05-15, predates most of the current code |
| `multi_llm/layer_dependency_graph.jsonl` | — | **Zero information**: every layer depends on every other layer (fully connected). Its layers (operator/sidecar/…) are package buckets, not flow stages |
| `multi_llm/file_linkage.jsonl` (untracked) | A reachability label per file | Of the `src/` `.py` files: 322 `Unreachable` + 188 `Orphan`; only 11 `Reachable`. Which entry points it counted from is **UNVERIFIED** (no generator found in `scripts/` or `src/`) |
| `REPOSITORY_COVERAGE_DASHBOARD.md` (2026-09-18) | Its own verdict is "Is the whole codebase covered? `NOT_YET`" | journey coverage **3.7%** (41/1,118), attribution **0%** |
| `src/runtime/layer_trace.py` + `results/layer_trace*/` | A per-bar **runtime** trace L0–L9 with a fixed vocabulary (`PASS/REJECT/NOT_REACHED/EXCEPTION`) | Backtest rail only, XAUUSD only. No L2, no L9 rows, and the live rail writes no trace |
| `scripts/analysis/layer_trace/h4_rail_reachability.py` (F-103) | Backtest and live are **two rails** that reach different layers | Nothing about the ~470 other entry points |
| `docs/architecture/signal-flow.md` (2026-07-03) | Describes one spine, Steps 1–7 | Predates F-103/F-108/F-109, so it is **stale** |
| `data/script_registry.jsonl` | 492 scripts, each with a category (29 CANONICAL_CLI · 176 RESEARCH_RUNNER · 155 DIAGNOSTIC · 43 GOVERNANCE · 23 ORPHAN …) | What each script reaches or produces |

Entry points on disk: **422** `scripts/` files and **49** `src/` files contain `__main__`.

**What this means.** The repo already knows its *parts* (the import graph is complete) and has
traced *one path* at runtime (backtest, XAUUSD). It does not know *which entry points drive which
layers, or which files each one writes*. So SYSTEM_FLOW has to be built by joining existing
artifacts, not by writing new tracers.

## Design decisions to confirm in discussion (my recommendations)
1. **Reuse the layer vocabulary the code already emits** (`layer_trace.py` L0–L9). Don't adopt
   ChatGPT's L0–L7 as a third vocabulary. Mapping:
   L0 corpus/OHLCV · L1 features · L2 feature states (gap: never emitted) · L3 CRT state ·
   L4 Parent CRT / HTF · L5 engine scoring · L6 fusion + decision · L7 plan + risk
   (ExecutionPlanner/Ultron) · L8 trade birth / ledger · L9 outcome / measurement.
   ChatGPT's "Opportunity" = L6→L8, "Evidence/Dataset" = derived from L9, and "Automation" is a
   **rail**, not a layer.
2. **SYSTEM_FLOW is a rails × layers matrix.** Rails: Backtest · Live (paper) · Research-oracle
   (e.g. the F-086 every-bar labeler, the resolver) · Out-of-system (governance, docs, agent,
   multi_llm tooling). Each cell says REACHED / NOT_REACHED / DIFFERENT_PRODUCER, with evidence.
3. **Coverage header at the top** (the user's requirement). Denominator = entry points in the
   system rails only. Out-of-system tooling is counted separately so it can't make the number
   look better or worse. Fields: entry points found · classified by rail · fully traced (static
   and runtime) · static only · untraced · modules reached by no entry point · producers per layer
   (more than one producer = a multi-authority layer).
4. **Evidence grade per cell:** `RUNTIME` (a layer_trace row or run artifact) > `STATIC` (import
   closure) > `DOC` (docs claim only) > `UNKNOWN`. No cell is marked covered on `DOC` alone.

## Narrowing sequence (one layer per discussion turn; nothing gets frozen without the user's OK)
- **Step 0 — Coverage census (read-only).** Join `script_registry.jsonl` categories, `__main__`
  entry points, the `graph.dot` import closure, and the `layer_trace.py` layer→module map from
  `backtest_v2.py` (the `layer=` emit sites around lines 3138–3888). The result is the rail
  classification and the coverage header numbers. Any helper code goes in the scratchpad, not the
  repo. Deliverable: the header draft, shown in chat for discussion.
- **Steps 1–10 — one layer each, L0 → L9.** Per layer, in chat:
  (a) **Findings:** producers, consumers, output object, which rails reach it, the F-ids that
  touch it (e.g. L0 F-066/F-098; L1 F-061/F-107; L3 F-069/F-074; L5–L6 F-036/F-060/F-102;
  L7 F-108/F-109; L8 F-088/F-101; L9 F-022/F-088).
  (b) **Questions for the user:** the one or two decisions that layer needs (which producer is
  canonical, what the output is, research-only or execution).
  (c) **Row design:** Input → Transformation → Output → Consumer, plus immutable/derived and
  research/execution. It is only written after the user confirms.
- **Step 11 — Assemble `docs/architecture/SYSTEM_FLOW.md`.** Existing-doc-first applies (§6.2
  rule 1): it supersedes `signal-flow.md` rather than sitting beside it. Proposed handling: mark
  `signal-flow.md` SUPERSEDED with a pointer, never delete it. That is decided at this step.
- **Out of scope until the system is frozen:** manifests, parity, promotion, authority registers,
  and new governance floors. Gaps found along the way are **recorded** in SYSTEM_FLOW's gap list,
  not fixed (for example the missing L2 emitter, the live-rail trace, the three run_ids from F-101,
  the fail-open gate from F-102).

## How the user uses it once built
- Top of the file: "how much of the system is traced", with a number.
- For any question like "where is a trade born on live vs backtest?", read one row of the
  matrix: layer × rail → producer module, output, evidence.
- Any new work gets placed on a layer and a rail first. Governance later attaches to these
  frozen rows.

## After plan approval (first actions)
1. Save memory `project_system_flow_first.md` (the direction, Finding 0, the layer vocabulary
   decision) and add it to the `MEMORY.md` index.
2. Run Step 0 read-only and present the coverage header for discussion. Stop there.

## Verification
- Every number in the header is reproduced by a command that is shown alongside it (§1.1).
  Anything that can't be reproduced is marked `UNVERIFIED`.
- Every layer row cites file:line or a run artifact. `DOC` grade alone never counts as covered.
