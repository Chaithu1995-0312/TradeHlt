# Tradelatest Infrastructure Gap Analysis — Plan

## Context

The user asked for a market-intelligence-platform gap analysis of the Tradelatest repo, treating five
artifacts as authoritative: `Infrastructure Inventory.xlsx`, `src_business_functionality.xlsx`,
`docs/current-findings.md`, the CRT State Identity Ontology design doc, and the Semantic OS overview.
The ask is explicitly: reconstruct the current architecture, then — for missing infrastructure, control
planes, observability, automation, semantic connections, research capabilities, and production
capabilities — answer *why it's needed*, *what it connects*, *what it unlocks*, and *what evidence shows
it's missing*. No code review, no generic software-architecture advice, no new abstractions — this is a
capability inventory against the platform's own stated ambitions.

Three research passes are already complete and their findings are the direct input to this report:
- **Infrastructure Inventory.xlsx** (`docs/analysis/Infrastructure Inventory.xlsx`, generator
  `docs/analysis/_build_infrastructure_inventory.py`): 80 asset rows (INV-001..080) with
  Category/Status/Authority/Evidence/Architecture-Layer/Notes, 54 Relationship edges, and a
  Confidence rating (HIGH/MEDIUM/LOW) per asset judging how well-evidenced that row is.
- **src_business_functionality.xlsx** (`results/analysis/src_business_functionality.xlsx`): file-level
  census of ~564 `src/` modules, each tagged `ALIGNED`/`UNKNOWN` and `CURATED`(tier 1-2)/`DERIVED`(tier
  3) — the overwhelming majority (~550+) are Tier-3 `DERIVED`/`UNKNOWN`, i.e. machine-classified with no
  human-curated purpose statement.
- **Semantic OS overview** (`docs/governance/SEMANTIC_OS_CONTRACT.md` + `SEMANTIC_OS_V1_DESIGN.md` +
  `src/governance/semantic_grounding.py`): the L0-L6 meaning-grounding layer, its 5 verdict states
  (GROUNDED/UNKNOWN/AMBIGUOUS/UNANSWERABLE/REFUSED), and its own coverage dashboard showing
  journey_coverage 4.8% RED / attribution_coverage 0.0% RED.
- **CRT State Identity Ontology** (`docs/implementation_plan/crt-state-identity-ontology-2026-09.md`):
  a design-only doc (not implemented) diagnosing a 5-way split-brain over CRT state identity.
- **`docs/current-findings.md`** / CLAUDE.md Repository Truths Index: F-001..F-097, already loaded in
  full in context.

Plus direct reads of `docs/governance/layer-audit-manifest.json` (OHLCV layer audit BLOCKED) and the
user's persistent memory (untracked lineage, measurement-contract non-execution, etc.).

**Deliverable** (per user's answers): a published Artifact (interactive HTML report), comprehensive scope
(~20-25 distinct gaps across all 7 categories, each with Why/Connects/Unlocks/Evidence).

## Architecture reconstruction (feeds the report's opening section)

A single-instrument, file-backed spine, no DB/broker/cloud:

```
OHLCV CSV (data/, gitignored)
  -> Feature Pipeline (src/features/, 48-dim v5.0 canonical vector, F-076)
  -> 4 mandatory scoring engines (CRT/Gaussian/ZoneGate/RR, src/engines/ + config_layer/crt_engine_v2.py)
  -> FusionEngine -> DecisionEngine (src/core/)
  -> ExecutionPlanner (src/config_layer/execution_planner.py)
  -> UltronRiskGate (src/core/ultron_risk_gate.py) -- sole capital authority
  -> [Live Bridges: MT5/Telegram -- NO PRODUCTION CALLER, F-073]
```

Four async "kitchen" feeders sit alongside: Governance/Promotion (the only path to production config),
Training, the Agent (LLM-assisted operator automation, never in the hot path), and INOUT (now reduced to
candle fetchers + an unwired paper-only live-rail; the old strategy/state-machine code is archived, not
live — contradicting `docs/architecture/signal-flow.md`'s description of it as a live parallel rail).

Orphaned/sidecar subsystems that exist on disk but do not reach a live decision: TradeNet v2 fusion slot
(F-005), scan->rank->allocate->ExecutionLoop + PortfolioAllocator (F-013), ReplayMemory/CognitiveBus/
ClusterEngine/HMF (F-012, write-only telemetry), BitNet (inert, `use_bitnet:false`, F-004), the entire
Research platform (`src/research/`, ~175 files, deliberately isolated from promotion).

The report opens with a compact version of this diagram plus the "authoritative artifacts disagree with
each other and with live state" catches already found (architecture.md's stale `v1_multi_2026_03`
pointer vs actual `ACTIVE_VERSION=v2_htfcrt_2026_08`; signal-flow.md describing archived INOUT code as
live) — these are gap-analysis-relevant findings in their own right (missing doc-truth automation), not
just scene-setting.

## Report structure

Single HTML artifact, `artifact-design` skill loaded first (mandatory pre-read before writing). Sections:

1. **Header / how to read this** — states the 5 authoritative sources, the CLOSURE non-transitivity rule
   (a CLOSED subsystem doesn't imply its neighbors are), and that findings are evidence-graded, not
   speculative "best practice" suggestions.
2. **Architecture snapshot** — the diagram above + the 3 pre-existing doc-drift catches, framed as "here
   is what actually runs today" (not a review of code quality).
3. **Seven gap sections**, each gap as a card: **Gap name** / **Why needed** / **Connects** (named
   existing components, using their real file paths and INV-IDs) / **Unlocks** (concrete capability) /
   **Evidence** (file:line or F-id or INV-id citations). Gaps below are the confirmed candidate list —
   final report may merge 1-2 that overlap once written, but should not silently drop any without noting
   why.

### Category 1 — Missing infrastructure
- No logical->physical OHLCV corpus resolver (layer-audit-manifest BC-1: 9 logical corpora resolve to
  different bytes across mt5/binance/yfinance families; audit BLOCKED, no R3 admission gate)
- No production live execution rail (F-073; INV-014 live_rail is paper-only, `ACTIVE_VERSION` has no
  `live_rail` key; F-085 Feature Store fix has no live loop to prove itself on)
- No git-tracked data/model/result/telemetry lineage (INV-050..053 all gitignored/mixed; memory note:
  the full OHLC->Feature->CRTState->Outcome chain is untracked, so nothing here survives a clone)
- TradeNet v2 fusion neural slot permanently empty (F-005, INV-004) — a complete trained model with no
  socket wired to receive it

### Category 2 — Missing control planes
- ExecutionLoop (scan->rank->regime->allocate->gate->alert->override) built, zero callers (F-013,
  INV-016) — the only documented human-in-loop override surface for live trading is unreachable
- Scanner/SignalPool + PortfolioAllocator designed to sit before Ultron, never invoked; live runs a
  single-candle spine instead (INV-017/018) — no cross-symbol or cross-position control plane exists
- `live.inout_runner` control-plane command is registered but points at archived code (INV-003 note,
  entry-exit-map DRIFT-DOC) — a control surface that silently no-ops
- Health Checker (port 8788, Docker/K8s-probe shaped) has no confirmed production binder and the repo
  has a Dockerfile but no k8s manifests (INV-045) — deployment control plane half-built

### Category 3 — Missing observability
- `logs/crt_transitions.jsonl` (2.59GB) drops every RESET event — folding it gives a *wrong* state
  series; only run-scoped `events.jsonl` is fold-complete (memory: semantic lineage census) — the
  platform's largest CRT telemetry stream is not safe to aggregate
- Exec-telemetry has two unreconciled trees (`exec_telemetry/` vs `runtime/exec_telemetry/`, INV-046)
- ReplayMemory/CognitiveBus/HMF telemetry is write-only and never read back into any decision (F-012) —
  "institutional memory" exists but nothing observes whether it would have helped
- Event Fabric envelope backbone is incomplete — not every trade writer is enveloped (service-boundary
  S7 note, Trd-M1)
- No admissibility/coverage dashboard ties telemetry streams to what they're allowed to prove — the
  `jsonl_claim_catalog.yaml` exists but is enforced only inside Semantic OS grounding calls, not as a
  standing dashboard

### Category 4 — Missing automation
- No automated OHLCV admission gate — layer-audit R0-R2 landed, R3 (the actual gate) was never built
  (layer-audit-manifest.json)
- Measurement Contract probes: schema + 27 adversarial seeds frozen since 2026-07-10, **0/27
  implemented** even though 10 `MC-*` instances now exist on disk (INV-023) — sealed contracts exist
  with no automated way to check they pass their own gate
- GREEN_FLOOR has 9 pre-existing failures and 1,077 untracked paths never triaged post F-071 restore —
  no automated backlog-burn-down for its own reconstructed integrity gate
- AI Feedback -> ExpansionEngine loop is intentionally human-gated (by design) but there is no automated
  loop closing suggestion -> measured outcome -> promoted/rejected verdict; suggestions can silently pile
  up unactioned

### Category 5 — Missing semantic connections
- CRT State Identity: 5 authorities claim ownership simultaneously (`active_models.yaml`,
  `market_ontology.yaml`, `market_crt_states.yaml`/resolver, `crt_engine_v2.py`, stale
  `file_identities.yaml` claim) — a full design for the fix exists but is **not implemented**
  (`docs/implementation_plan/crt-state-identity-ontology-2026-09.md`)
- CRTStateResolver vs live engine: only 88.16% parity, and the residual is *structurally* config-
  unreachable (F-069) — two interpreters of "the same" state graph that can never be reconciled by
  tuning
- Semantic OS coverage: journey_coverage 4.8% (RED), attribution_coverage 0.0% (RED) — the meaning layer
  covers a small fraction of the ~564-module codebase it exists to explain
- `semantic_impact.py` (L6 blast-radius engine) is explicitly flagged "Missing file" in its own design
  doc — no way to ask "what does changing X semantically touch"
- The Semantic OS's own JSONL-claim doc (`JSONL_CLAIM_SURFACE.md`) says "not implemented, design only"
  while the code (`semantic_grounding.py` lines 966-1499) is live and CLAUDE.md documents it as shipped
  — a documentation-truth gap inside the subsystem whose job is truth-grounding
- ~550+ of ~564 `src/` modules are Tier-3 `DERIVED`/`UNKNOWN` in the business-functionality census — no
  human-curated purpose statement for the large majority of the codebase's semantic identity

### Category 6 — Missing research capabilities
- Measurement Contract admissibility layer stays `OPEN` — every finding F-090 through F-097 that cites a
  sealed `MC-*` instance still carries `economic_claims_allowed:false` because mt00/mt01 never ran
- No production live rail means no research measurement can ever be checked against real fills/slippage
  — every cost/exit-model finding (F-082, F-087, F-088) is calibrated from historical/paper data only
- OSS Lab (comparative benchmark laboratory vs qlib/nautilus/finrlx/lean/vectorbt) is architecture-
  approved but blocked on a Codebase-Memory pin/security gate before its first real benchmark (INV-058)
- Retrieval/RAG (`src/retrieval/`) wiring completeness is UNKNOWN — unclear whether it actually improves
  agent-assisted research today or is dormant infrastructure

### Category 7 — Missing production capabilities
- Zero live P&L has ever been generated — F-010 stays OPEN; the entire economic case rests on backtest
  ceilings, not verified live execution
- Kill-switch state path is hardcoded (`logs/kill_switch_state.json`, service-boundary-map S4 blocker),
  not config-governed — a safety mechanism that is fragile exactly where it would matter (live)
- UAT package (`src/uat/`, Monte Carlo + kill switch + runner) is LOW-confidence in the inventory —
  internals unread/unverified, so there's no confirmed acceptance gate before any live cutover
- No cross-position capital governance is active live — Ultron gates single trades only; the
  Portfolio/Correlation/Capital-Policy stack that would provide it is orphaned (Category 2)
- Deployment automation is half-built: a Dockerfile exists, a health-check endpoint is designed for
  Docker/K8s probes, but no k8s manifests or deployment pipeline were found

4. **Closing synthesis** — one short paragraph naming the two or three structural gaps that most other
   gaps trace back to (candidates: no live execution rail; no git-tracked telemetry lineage; CRT identity
   split-brain), since the user asked to prefer discovering missing *system capabilities* over proposing
   abstractions — the synthesis should point at root capability gaps, not re-list everything.

## Execution steps

1. Load the `artifact-design` skill (required before writing any artifact).
2. Write the HTML report to the scratchpad directory, following the section structure above, using the
   evidence already gathered (no new tool calls needed for content — all facts are sourced from the three
   completed research passes plus the direct reads already done this session).
3. Every gap card cites at least one concrete evidence anchor (F-id, INV-id, file:line, or named doc) —
   no unsourced claims.
4. Publish via the `Artifact` tool (title: a short distinctive name, e.g. "Tradelatest Capability Gaps";
   description = one-sentence subtitle; favicon appropriate to a technical/systems report).
5. Verification: re-read the published artifact's rendered text (via `Artifact` read or a quick visual
   check) to confirm every section renders, the theme (light/dark) tokens are correct, and no gap card is
   missing its four required fields (Why/Connects/Unlocks/Evidence).
6. Report the artifact link back to the user with a short summary (per response-style rules: 1-2
   sentences, not a re-narration of the whole report).

No source files are modified. No SESSION LOG entry is required (CLAUDE.md §6 governs codebase-affecting
turns; this is a read-only analysis producing an external artifact, not a code/config/finding change) —
if the user later wants this promoted into `docs/analysis/` as a citable repo doc, that's a separate,
explicitly-scoped follow-up per their own answer (they chose Artifact-only for now).
