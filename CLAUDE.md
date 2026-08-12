# CLAUDE.md — Master Context File

> **This is the file Claude reads first in every session.**
> It is the project **bootloader** (navigation + operating rules), **not** the complete documentation.
> It links conventions, schemas, findings, and companion docs into one operating manual.

---

## 0. Architecture Memory Policy (bootloader rule)

> **Full policy:** [`docs/memory/ARCHITECTURE_MEMORY_POLICY.md`](docs/memory/ARCHITECTURE_MEMORY_POLICY.md)  
> **Index:** [`docs/memory/README.md`](docs/memory/README.md)

**Hierarchy:** `CLAUDE.md` → companion memory under `docs/memory/` → deep companions (`docs/architecture/`, `docs/reference/`, …) → **source code (always wins)**.

**On every task:** (1) identify the subsystem, (2) load **only** the matching memory doc, (3) follow its Reading order into source, (4) do not assume all knowledge is already loaded.

| Task domain | Load first |
|---|---|
| Agent / modes / tools | [`docs/memory/agent-memory.md`](docs/memory/agent-memory.md) |
| Runtime / backtest / live | [`docs/memory/runtime-memory.md`](docs/memory/runtime-memory.md) |
| Features / schema / pipeline | [`docs/memory/feature-memory.md`](docs/memory/feature-memory.md) |
| Engines / scoring | [`docs/memory/engine-memory.md`](docs/memory/engine-memory.md) |
| Governance / promotion | [`docs/memory/governance-memory.md`](docs/memory/governance-memory.md) |
| Cross-cutting architecture | [`docs/memory/architecture-memory.md`](docs/memory/architecture-memory.md) |

**Do not** paste large architectural dumps into this file. Update the **affected** memory doc when architecture changes; change this section only if the memory hierarchy itself changes.

---

## 1. Project Summary

**Tradelatest** is a Python >=3.10 quantitative trading system that ingests M15 OHLCV candles, scores each bar through four independent engines (CRT, Gaussian, Zone Gate, RR), fuses the scores under a weighted-completeness gate, plans entry/SL/TP via `ExecutionPlannerV1_2`, and approves the final position through `UltronRiskGate`. Governance sits on top: no config reaches production without an approved `ValidationReport` from `ConfigValidator.validate()`, SHA-256 hashing, and an append-only `promotion_log.jsonl` audit trail. An AI automation agent (REPL, BitNet 3B, deterministic `PLAN_REGISTRY`), an expansion engine for bounded parameter search, and a stdlib HTTP control plane complete the system. Everything is file-backed — **no database, no message broker, no cloud deps**.

---

## 2. Companion Documentation (read these when the task touches their domain)

> **Front door:** [`README.md`](README.md) is the repo entry point — Quick Start + the full
> 4-tier docs map + authoritative-source rules. Historical/point-in-time analyses live in
> [`docs/analysis/`](docs/analysis/README.md) (not living docs). The table below is the
> task→doc lookup.

| File                              | Covers                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------ |
| [`docs/book/README.md`](docs/book/README.md) | The canonical knowledge book — the repository reconstructed as a sequential, cross-referenced narrative (26 chapters, Parts I–VIII: Foundations → Market Understanding → Market Semantics → Decision Making → Execution → Governance → Research → Agent Intelligence). Read start-to-finish for onboarding, or jump to a chapter for one concept's canonical explanation. A map into the code, not a replacement for it — code always wins on conflict. |
| [`docs/reference/architecture.md`](docs/reference/architecture.md)       | Tech stack with versions, full directory tree, end-to-end data flow, design patterns, external integrations (llama.cpp / Groq / BitNet GGUF), production-config section index, CLI entry points. |
| [`docs/reference/conventions.md`](docs/reference/conventions.md)         | Naming rules (files / classes / constants / configs / JSONL), folder-placement table, the three error-handling modes (fail-fast / optional-import / fail-open), logging, import order, explicit anti-patterns. |
| [`docs/reference/schemas.md`](docs/reference/schemas.md)                 | Every dataclass (`Candle`, `Trade`, `BacktestConfig`, `RunRecord`, `CommandSpec`, `ToolStep`, `Plan`), enums (`CRTState`, `Direction`, `RejectReason`), the 38-dim `CANONICAL_FEATURES` schema, `ValidationReport` / `GateResult` / `ExecutionPlan` shapes, production-config top-level keys, JSONL line schemas, cross-object relationships. |
| [`docs/reference/example-service.py`](docs/reference/example-service.py) | Golden reference template demonstrating fail-fast config load, `_require` strict accessor, `from_prod_config` factory, named flow logger, optional-import guard, circuit-breaker, structured APPROVE/REJECT return shape, CLI wrapper, and module-registration checklist. Copy this when adding new engines / gates / validators. |
| [`docs/reference/config-reference.md`](docs/reference/config-reference.md) | Section-by-section reference for every key in `configs/production/v1_multi_2026_03.json`: `params`, `engine_runner`, `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`, `crt_engine`, `gaussian_scorer`, `rr_model`, `llama_gate`, `config_validator`, `governance`, `validation_summary`, `backtest`, `feature_monitor`, `tuner`, `training`, `portfolio`, `agent`, `inout`. Includes editing + rehashing rules. |
| [`docs/reference/testing.md`](docs/reference/testing.md) | pytest layout (51 files across 10 domains), how to run (whole / by domain / single), `pyproject.toml` test config, `conftest.py` role, coverage expectations per module, representative test patterns (assertion / invariant / parametrise / registry-exhaustiveness), conventions enforced by tests, guide for writing new tests, pre-promotion regression command. |
| [`docs/reference/agent-reference.md`](docs/reference/agent-reference.md) | Complete agent reference: 14 intents (pipeline / copilot / governance / cross-mode), 20 tools with args/write flags, deterministic `PLAN_REGISTRY` tables, `IntentRouter` regex+LLM classification flow, `PlanCompiler` API, `Executor` confirm-gate + path-guard, `AgentState`, audit log formats (`logs/agent_audit.jsonl`, `logs/agent_intent_log.jsonl`), agent config, REPL CLI, add-a-new-tool procedure. |
| [`docs/reference/governance.md`](docs/reference/governance.md) | End-to-end promotion workflow, `PromotionManager` API (`promote_from_report` / `promote_from_tuner_checkpoint` / `promote_direct` / `list_versions` / `load_version`), registry layout + archive naming, `configs/promotion_log.jsonl` line schemas (PROMOTED / PROMOTION_FAILED), `ShadowPromotionGate` two-gate flow, `MetaGovernorExecutor`, `PortfolioValidation`, rollback procedure, pre-promotion checklist, write-authority matrix. |
| [`docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md`](docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md) | Long-form of the §6.2 thin rule: the invariant (every code/config/runtime-truth change triggers a documentation-truth decision), the 5-step process (classify → impact → gate → synchronize → audit), the user-approval gate calibration, the audit-trail format, the completion criterion, and the F-038 worked example. |
| [`docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`](docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md) | **ACTIVE:** Behavior-preservation is **task-class based** (`OBSERVATION_ONLY` / `BEHAVIOR_CHANGE_AUTHORIZED` / `EXPLORATORY_RESEARCH`). Historical baseline transition/event/trade hashes are comparison evidence, **not** permanent golden acceptance criteria (general hash-parity requirement SUPERSEDED 2026-07-14). |
| [`docs/architecture/signal-flow.md`](docs/architecture/signal-flow.md) | End-to-end candle→order linear walk for the CRT spine (Steps 1–7) with module / entry-point / config / failure-mode per step, the four async kitchen feeders (Governance, Training, AI Agent, INOUT) and where each joins the spine, cross-reference matrix, Mermaid swim-lane diagram. |
| [`docs/memory/`](docs/memory/README.md) | **Subsystem memory (navigation only):** policy + `*-memory.md` indexes (purpose, contracts, entry/exit, reading order, coverage). Load by task domain (§0). Deep reverse-engineered map (optional): [`docs/architecture/architecture-memory.md`](docs/architecture/architecture-memory.md). |

| [`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) | LLM trigger-word vocabulary for owning the codebase: `Continue` / `Next step` / `Next plan` / `Validate` / `Implement` (Tier 1) + `Orient`/`Status` / `Map` / `Audit` / `Plan` / `Log` (Tier 2). Per trigger: action · docs loaded · exit condition. See §12. |
| [`docs/architecture/goal.md`](docs/architecture/goal.md) | North-star goal document (plain language): purpose, the happy flow (candle→order), the 7 invariants + five governance questions, the deviation policy (throughput-improving deviations OK if invariants hold), migration target. The "what good looks like" baseline. |
| [`docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md`](docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md) | **MIAR** — model *intent* authority (below ontology + feature pipeline, above implementations). Why each engine exists, non-goals, ownership matrix, alignment 🟢🟡🔴⚫. Machine twin: `docs/governance/miar_registry.json` · floor `tests/test_miar_registry.py`. |
| [`docs/architecture/intelligence-compounding.md`](docs/architecture/intelligence-compounding.md) | Long-form of CLAUDE.md §6.1: the repository as a self-compounding **intelligence substrate** (zero intelligence loss). Repository utility function, entropy principle, the goal-first chain, modules-as-frozen-thoughts, the three permanent checklists (User/Claude/System), 7-level intelligence ladder, strengthened Memory Rule, and the Stage 1→7 evolution path (with the "no premature framework" guardrail). |
| [`docs/governance/MEASUREMENT_CONTRACT.md`](docs/governance/MEASUREMENT_CONTRACT.md) | **Research Measurement Contract** — why research results weren't comparable (no recorded measurement basis: label derivation, cost model, gate mode, clock basis all lived as ambient `.env`/script state) + the fix. Frozen per-experiment schema (`measurement_contract.schema.json`, `MC-*` instances) + 27-seed adversarial mutation matrix (E-MT-00/E-MT-01, §1–§8, FROZEN v1.0.0 2026-07-10) subordinates 3 reusable per-asset-class **profiles** (`configs/research/measurement_contracts/*.v1.json`, `MP-*` namespace, §9) and the **L0 sufficiency criterion** bounding hygiene spend (§10). Claims bind via `docs/governance/research_family_registry.json` — the object(16)×layer(L0–L5) atlas of what's been researched about what, seeded from history, currently `Contract:UNKNOWN` on every finding. Current state: `MEASUREMENT_LAYER_STATUS=OPEN`, 0 sealed `MC-*` instances, 0/27 probes built — see the Closure & Authority Index below. Human-language picture: `docs/topics/research-measurement-contract.md`. |
| [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md) | Auto-generated command catalog (from `control_plane/registry.py`): every CLI invocation, artifacts, suggested next step. Authoritative for "how do I run X." |
| [`assistant_project.md`](assistant_project.md) | Persistent session log — every LLM response since April 2026 is timestamped and archived here. Contains the architecture migration doctrine, all past decisions, the five governance questions, and a complete audit trail. Always check before re-opening a resolved thread (§3.4 item 7). Governed by CLAUDE.md §6 (Persistent Logging Mandate). |
| [`active_models.yaml`](active_models.yaml) | **Loaded first in every Claude session.** Machine-readable model registry (schema v2.1, four truth layers `intent`/`runtime`/`evidence`/`status`): CRT engine (9 states, exact detection logic), Gaussian (live 3-feature heuristic; v4_mirrored 38-dim NB is experimental/unwired), BitNet config, zone gate, RR model, strategy modules, engine-runner orchestration. Each model also carries v2.1 `reachability` (telemetry/tests/topics/framework-ids) + descriptive-only `optimization` + `evidence.conflicts`/`hypotheses`. Source-verified against `crt_engine_v2.py`, `feature_schema.py`, `model_registry.py`. |

**Machine-readable truth sources** (reachable from `active_models.yaml` `meta.machine_readable_sources`; artifacts are GENERATED/seeded — edit the source/seed, never the artifact under gitignored `data/`):

| Artifact | Source of truth | Regenerate | Guard |
|---|---|---|---|
| `data/findings.jsonl` | [`docs/current-findings.md`](docs/current-findings.md) | `python scripts/governance/export_findings.py` | `tests/test_findings_export.py` |
| `data/hypothesis_registry.jsonl` | `scripts/governance/seed_hypothesis_registry.py` | run the seed | `tests/test_hypothesis_registry.py` |
| `data/framework_registry.jsonl` | `scripts/governance/seed_framework_registry.py` | run the seed | `tests/test_framework_registry.py` |
| `data/script_registry.jsonl` | stubs `docs/governance/script_registry_stubs.jsonl` + overlays in `scripts/governance/seed_script_registry.py` | `python scripts/analysis/script_census.py --write-stubs …` then `seed_script_registry.py` (+ `generate_script_matrix.py`) | `tests/test_script_registry.py` + `tests/test_script_matrix_sync.py` |
| `active_models.yaml` (v2.1) | hand-maintained, source-verified | — | `tests/test_active_models_registry.py` + `tests/test_crt_state_invariants.py` |
| `context/*.md` (Portable Mind) | canonical docs (the `Compile` trigger) | `python scripts/context/build_context.py` | `tests/test_context_compiler.py` |

Schemas: [`docs/reference/schemas.md §9.4–9.8`](docs/reference/schemas.md). Tier separation: PRIMARY (findings doc, seed scripts, stubs/overlays, `active_models.yaml`) → GENERATED (`data/*.jsonl`) → RUNTIME (`logs/*.jsonl` event streams). Never hand-edit a GENERATED artifact.

---

## 3. How to Work With This Codebase

### 3.1 Adding a new feature (canonical pattern)

1. **Place the module.** Pick the right subpackage from `CONVENTIONS.md §2`. Scoring engine → `src/engines/`; decision/risk logic → `src/core/`; validator → `src/config_layer/`; governance gate → `src/governance/`; live-mode code → `src/inout/`. Never put production logic in `scripts/`.
1b. **If you add a runnable script** under `scripts/**` or repo-root `*.py`, register it the same turn (SITS): `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py` (see `docs/reference/conventions.md` §2.1). Unregistered paths fail the GREEN_FLOOR coverage test.
2. **Copy `docs/reference/example-service.py`** into the chosen folder, rename, and keep its structure: `_load_*_cfg()`, `_require()`, dataclass with `from_prod_config`, named flow logger, public `PascalCase` class with typed methods, private `_snake_case` helpers.
3. **Add a new section to `configs/production/v1_multi_2026_03.json`** containing every tunable. No magic numbers in Python.
4. **Re-hash the config:** `python scripts/maintenance/_compute_hash.py`.
5. **Wire the module into its orchestrator.** Engine → add key to `core/engine_runner.EXPECTED_ENGINES`; validator → call from `PromotionManager` or `live_engine_hook`; risk check → extend `UltronRiskGate.evaluate()`.
6. **Write pytest tests** in `tests/`. Cover the APPROVE path, every hard-failure branch, the circuit-breaker open path (if external I/O), and the optional-dep absent path.
7. **Promote** with `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_multi.json --version v2_<label>_<YYYY_MM> --data-dir data/`. Promotion fails unless `ValidationReport.decision == "APPROVE"`.

### 3.2 Adding a new "DB model" (really: dataclass / config section)

This codebase has no ORM. "Models" are one of:

- **Value object** → `@dataclass` in the owning subpackage. Provide `from_prod_config(cls, cfg: dict) -> "Self"` if any field is config-driven.
- **Enum** → `class X(Enum):` with `SCREAMING_SNAKE_CASE` members. See `CRTState`, `Direction`, `RejectReason` in `src/config_layer/state_identity.py` (re-exported by `crt_engine_v2`).
- **Config section** → new top-level key in `configs/production/v1_multi_2026_03.json`, consumed via `get_prod_section("<name>")`. Register the required keys in a `_require` helper at module load (fail-fast).
- **JSONL event line** → self-contained `dict` with `timestamp` + `kind`; append only. Document the shape in `docs/reference/schemas.md §9`.
### 3.3 Adding a new "API endpoint"

There is **no REST API**. The three surfaces that accept external input are:

| Surface                    | How to add                                                                         |
| -------------------------- | ---------------------------------------------------------------------------------- |
| **CLI entry point**        | New script in `scripts/<category>/` that imports from `src/` and uses `argparse`. Never define business logic in the script — it must be a thin wrapper. |
| **Control-plane command**  | Register a `CommandSpec` in `src/control_plane/registry.py` (name / category / argv template / params). The HTTP UI at `localhost:8787` picks it up automatically via `ControlPlaneAPI.commands_payload()`. |
| **Agent tool**             | Add to `src/agent/tool_registry.py` (name, args schema, handler). Add the intent → tool sequence to `PLAN_REGISTRY` in `src/agent/plan_compiler.py`. Deterministic by design — do not route planning through the LLM. |

### 3.3b Construction Protocol (non-optional — Gate 6, 2026-07-08)

Every repository modification follows the **Repository Construction Contract**:
[`docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md`](docs/governance/REPOSITORY_CONSTRUCTION_PROTOCOL.md).
Classify the change against [`docs/governance/change_contracts.json`](docs/governance/change_contracts.json)
→ BUILD_IMPACT_MANIFEST (blocking UNKNOWN = STOP) → implement through the canonical authorities
(ontology → registry → implementations; **never local formula math** — new quantities are registered
first) → `python scripts/governance/construction_protocol.py validate-completion <manifest>`.
One-command floor: `construction_protocol.py check`. Enforcement is mechanical (census FRESHNESS floor
+ extended GREEN_FLOOR in CI): a completion claim with ungoverned feature math, undeclared changed
surfaces, or failing/stale checks is DENIED by the validator regardless of prose.

### 3.4 Key files to always check before making changes

Before touching any code, read these in order:

1. `CLAUDE.md` (this file)
2. `configs/production/v1_multi_2026_03.json` — the single source of truth for every tunable
3. `docs/reference/architecture.md` §3 (data flow) — know which layer you are modifying
4. `src/core/engine_runner.py` — the orchestrator that every decision path passes through
5. `src/config_layer/config_validator.py` — defines what "valid" means for a config
6. `src/governance/promotion_manager.py` — the only path to production
7. `assistant_project.md` — check recent session-log entries before re-opening resolved threads
8. If available at `graph.dot` / pyan output — the live dependency graph (`scripts/analysis/gen_pyan.py`). Cite nodes when discussing flow: `ModuleA → FunctionB → ClassC` (per dependency graph).

---

## 4. Current Known Constraints & Limitations

> ### 4.0 Active Version Resolution (Mandatory) — `ORIENT_RUNTIME`
> Version truth is **file-driven and branch-scoped**, never inferred from memory or history.
> Before any planning, backtest, promotion, forensic, or config reasoning, run `ORIENT_RUNTIME`:
> **(A)** read `configs/production/ACTIVE_VERSION`; **(B)** load that config via `get_prod_config()`;
> **(C)** verify its keys exist in the in-code schema (`CRTConfig` / `ConfigBuilder`);
> **(D)** record `ACTIVE_VERSION=<version>`; **(E)** only then plan or execute.
>
> **Runtime Truth Precedence** (a lower tier may *describe* history but **never overrides** a higher tier):
>
> | Tier | Source | Authority |
> |---|---|---|
> | **0** | `configs/production/ACTIVE_VERSION` | the only runtime truth |
> | **1** | schema physically present in code (`CRTConfig`, `ConfigBuilder`) | what can actually load |
> | **2** | `configs/promotion_log.jsonl` | promotion history |
> | **3** | `assistant_project.md` · historical findings · old audit reports | past states only |
> | **4** | LLM / session memory | weakest; advisory |
>
> The runtime already enforces Tier 0 — `get_active_version()` fail-fasts with `RuntimeError`
> (`src/config_layer/production_config.py`). The split-brain risk is at the **reasoning layer**: an
> agent reading a stale finding can *infer* the wrong version. If a config carries keys absent from
> `CRTConfig`, `ConfigBuilder._validate_override_keys` raises `ValueError: unknown override key(s)`
> (`src/config_layer/config_builder.py`) — conclude **"schema/version mismatch," do NOT migrate or
> execute**, and surface it per §6.2. Active on `patch` = `v2_multi_2026_04` (F-016); v4 loads only
> on the post-TP3 code line.

- **Python `>=3.10` only.** `pyproject.toml` pins it; CI will not cover earlier versions.
- **Single production config version is active at a time.** Archived versions are preserved as `{version}_archived_{ts}.json` but are not hot-swappable — rollback requires restoring and re-loading.
- **Four engines are mandatory.** `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}`. Removing one without updating the completeness check will produce silent partial fusion.
- **No lookahead is allowed in backtests.** `BacktestRunner` streams candle-by-candle; feature builders that peek ahead will break determinism and must be rejected in review.
- **LLM is a tie-breaker, not a hot-path dependency.** `llm_inference_client` returns neutral `1.0` after `fail_count_disable` failures. Any code path that cannot tolerate that fallback is broken by design.
- **Windows console encoding.** Non-ASCII output must go through `src/utils/console_safe.py` (cp1252 fallback). Direct `print` of arbitrary strings in CLI entry points risks `UnicodeEncodeError`.
- **Control plane is localhost-only.** No auth layer, no TLS — do not expose `localhost:8787` externally.
- **Schema hash is load-bearing.** Any change to `CANONICAL_FEATURES` or `FEATURE_SCHEMA` invalidates the baseline and requires `python src/runtime/baseline_capture.py --label <new>` before training.
- **`CRTState` transitions are not a free graph.** The legal map is **9 states** (golden path `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`, plus the `SHADOW_PENDING` branch `RANGE ↔ SHADOW_PENDING → SWEEP` (Phase 1) and the `EXPIRED` TTL branch `EXPANSION → EXPIRED → RANGE` (Phase 3b soft-archive)). Authoritative: `VALID_TRANSITIONS` (`state_identity.py:69` seed — extracted from `crt_engine_v2` 2026-07-18 to break the state-loader import cycle, re-exported for back-compat; immutable view `state_topology.py:109`) / `event-taxonomy.md §3`.
- **No database.** Any request to "add a table" or "use the ORM" is a convention break — consult `docs/reference/schemas.md §1` before proposing alternatives.
- **Never read `.env` (secrets).** `.env` contains live secrets (API keys, tokens). Do NOT open, read, print, cat, grep, or echo it, and never copy its contents into responses, logs, commits, docs, or memory files. If a key name is needed, reference the variable name only — never its value. Read config from `configs/production/*` instead.

---

## 5. Preferred Response Style (when helping with this codebase)

- **Follow existing patterns, never introduce new ones.** If a pattern is not already in `docs/reference/conventions.md` or in `docs/reference/example-service.py`, do not invent — ask.
- **Show minimal diffs.** Surgical edits keyed by file path and line number. No full-file rewrites. Preserve surrounding whitespace and comment style.
- **Flag conflicts explicitly.** If the request breaks an existing convention (magic numbers, skipped gates, partial fusion, lookahead, stringly-typed enums, API-wrapper around stdlib HTTP), call it out before producing code and propose the compliant alternative.
- **Be concrete.** Reference actual file paths, class names, and function signatures from the codebase — never generic placeholders like `your_module`.
- **Compress explanation.** Short prose on the *why*, code on the *what*. If a topic was covered in a prior `assistant_project.md` entry, reference the entry instead of repeating.
- **No preamble, no padding.** Start with `ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT` per §7 below.

---

## 6. Persistent Logging Mandate (non-optional)

- On EVERY assistant response, append the exact `📝 SESSION LOG ENTRY` block to `assistant_project.md` at repo root.
- If `assistant_project.md` does not exist, create it immediately and then append.
- A response is incomplete unless both are done:
  - the log block is shown in the response, and
  - the same block is persisted to `assistant_project.md`.
- Never defer this write. Do not skip for short replies.

### Two logs — route by dimension (non-optional)
There are **two** SESSION LOG files, same `📝 SESSION LOG ENTRY` format, routed by what the response did:
- **`assistant_project.md` — the CODEBASE log.** Engineering/research on the trading system: code,
  config, findings, backtests, and tooling builds (incl. building the `multi_llm/` layer — that is
  code). The test (`test_session_log.py`), rotation, and commit-hook target THIS file.
- **`llm_project_assistant.md` — the WORKFLOW log.** The *operation* of the multi-LLM workflow:
  handoff cycles (who did what), cross-model coordination decisions, protocol/role/queue evolution,
  discussion-level meta. Human-readable companion to `multi_llm/turn_ledger.jsonl`
  (`test_llm_project_assistant_log.py`).
- **Tie-breaker:** a change to governed code/config/findings → codebase log (the commit-hook needs it
  there); workflow-only → workflow log; genuinely both → log the primary dimension + a one-line
  cross-link (never duplicate full entries — §6.2). Both are bounded by the same rotator
  (`rotate_session_log.py [--file llm_project_assistant.md]`).

---

## 6.1 Intelligence Compounding Doctrine (non-optional)

> Complements §6. The repository's purpose is **zero intelligence loss + continuous
> compounding**, not file preservation. Full long-form (utility function, entropy principle,
> 3 checklists, evolution path): [`docs/architecture/intelligence-compounding.md`](docs/architecture/intelligence-compounding.md).

**North star (the one frozen sentence):** *The repository exists to preserve and compound
meaning, not information. Every tool output must ultimately be interpreted in terms of the
user's economic objectives, because **intelligence is an ROI-weighted belief change that
increases the probability of achieving the user's long-term objectives — not accumulated
data.***

**Intelligence ≠ information.** Data, logs, artifacts, and tool outputs are **not**
intelligence until their meaning + goal-anchored ROI + belief-impact are captured. ROI without
a goal is undefined — so every interpretation starts from the user's objective.

**The chain (goal-first, never belief-in-the-abstract):**
`User Goal → Economic Objective → Tool → Output → ROI Evaluation → Belief Update → Memory →
Future Decisions → Goal Probability`.

**Meaning over data.** Never treat a tool output as an isolated fact. Raw `Tool output →
Memory` is forbidden; the path is `Tool → Output → Purpose → User Intent → Economic Objective
→ ROI → Belief Update → Memory`.

**Modules are frozen thoughts.** Understanding *what* code does is insufficient. *Modules are
not assets; they are manifestations of user intent.* Continuously reverse-engineer
`Module → Purpose → User Thought → Economic Meaning → Long-Term Wealth Contribution`. Losing
this chain — the economic *why* — is the true intelligence loss; the code itself is
recoverable. **Artifacts are recoverable. Meaning is not.** (immutable doctrine) Artifacts
without meaning are noise.

**Per-result ROI check.** After a consequential tool result, ask: (1) which goal/economic
objective did this serve? (2) did it move that goal's probability? (3) what belief changed?
(4) what should stop being explored? (5) what next? A null/negative financial result with a
clear conclusion (e.g. "EMA gate non-binding → stop optimizing it, redirect to the session
bottleneck") is **high knowledge-ROI** — preserve it.

**Operational hook:** every response's SESSION LOG carries a `Belief Update / ROI / Goal` line
(§7.4). Durable belief changes (confirmed/invalidated hypotheses, dead ends, economic meaning,
confidence shifts) are saved as a **memory file** (`feedback`/`project` type) per the Memory
mandate — not left only in the session log. The enemy is fragmented meaning, not missing data.

---

## 6.2 Repository Truth Maintenance Doctrine (non-optional)

> Complements §6/§6.1. Purpose: **zero silent truth divergence.** Most "bugs" in this repo's
> history (the F-007/F-016 version split-brain, feature-dim drift, config illusions, stale
> analyses) are *documentation entropy* — uncontrolled truth duplication — not code errors. The
> repository must grow **more compressed and self-consistent** over time, not more fragmented.

**Record systems (authority on conflict):** runtime/config = `configs/production/*` + the §4.0
precedence · flow/schema = [`docs/architecture/signal-flow.md`](docs/architecture/signal-flow.md) / [`docs/reference/schemas.md`](docs/reference/schemas.md) ·
**conclusions** = [`docs/current-findings.md`](docs/current-findings.md) (living) · **history** =
[`docs/analysis/`](docs/analysis/readme.md) (point-in-time, *not* living) · how they connect =
[`docs/knowledge-map.md`](docs/knowledge-map.md) · when = [`docs/timeline.md`](docs/timeline.md).

**The seven rules:**
1. **Existing-doc-first.** Before creating any new doc, find the doc that already owns the topic and update it. A new standalone file is the last resort.
2. **Detect drift, classify it.** For any claim, compare code vs docs vs findings vs tests: `ALIGNED` (no-op) · `DOC_DRIFT` (code wins → fix the doc) · `CODE_DRIFT` (doc wins → fix the code) · `AMBIGUOUS` (→ rule 3).
3. **Never silently resolve a conflict.** When authorities disagree and the winner is unclear, do NOT edit either side or invent a third answer — surface a `TruthConflict` (source A, source B, evidence, impact, recommendation) and ask the user.
4. **Preserve history; never delete truth.** Mark superseded items `SUPERSEDED` / `INVALIDATED_BY` / `BRANCH_SPECIFIC` and keep the row (append-discipline). History is kept for replay; truth evolves on top of it.
5. **Minimize doc count.** Prefer one evolving topic/findings doc over many `finding_N.md`. Move point-in-time studies to `docs/analysis/`; keep `docs/topics/` curated.
6. **Synchronize, never in isolation.** Code change → check docs / tests / findings / topics. Doc change → check code / tests. Finding change → check indexes / citations.
7. **Branch-scoped truth.** State version/runtime truth per-branch (see §4.0), never globally.

### Documentation Drift Protocol (non-optional)
**The invariant:** *every code / config / runtime-truth change triggers a documentation-truth
decision.* Reporting a discrepancy is necessary but **not sufficient** — a turn that finds drift is
**incomplete** until the doc decision is made and recorded. Run the 5 steps: **classify** (rule 2) →
**present impact** (believed vs true, artifacts affected, whether a conclusion downgrades — rule 3
`TruthConflict` shape) → **gate** → **synchronize** all affected artifacts (rule 6 + §6.3 + §6.4 +
Findings Mandate) → **audit-trail entry** (rule 4 + E-001 "fix the SOURCE, not just chat").
**Gate calibration:** *auto-fix* unambiguous `DOC_DRIFT`/`CODE_DRIFT` that changes no registered
conclusion (stale path, scope sentence); **require user approval** only for `AMBIGUOUS`/split-brain,
for any change that **downgrades/reverses a finding**, or for edits to an active config /
`ACTIVE_VERSION`. **Completion criterion:** a task touching governed code/config/runtime is not done
until doc-impact is assessed + gated updates approved + an audit entry recorded (extends the §7.4
SESSION LOG close). Full process + audit-trail format + the F-038 worked example:
[`docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md`](docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md).
Grants no new authority.

### Findings Mandate (the `§6.2` cited by `docs/current-findings.md`)
When a session **validates or overturns** a conclusion, add or flip a finding in
[`docs/current-findings.md`](docs/current-findings.md) the **same turn**: set
`Validated` / `Revalidate-by`, cite non-empty `Evidence`, fill `Reversal` when it overturns a prior
belief. **Never delete** — mark `SUPERSEDED` / `RETIRED` and keep the row. `Confidence` ∈
`Certain · Likely · Possible`. Never silently revive a `KILLED` / `FROZEN` Funding-Ledger
initiative (meet its Reopen Conditions **and** file a SESSION LOG entry). Enforced by
`tests/test_current_findings.py`.

### Epistemic Integrity Pre-Registration Ritual (Program E-001)
Before registering any finding, run the following 6-question check (from
[`docs/governance/EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md)):

1. **What artifact supports this?** (file:line required)
2. **Could INSUFFICIENT explain the observation?**
3. **Am I upgrading sign noise into meaning?**
4. **Is this statistical or economic?** (Authority-Ladder check: Level 1 ≠ Level 2)
5. **Is the parent stronger than the children?** (E-001E invariant)
6. **Would I phrase this differently after seeing raw counts?**

If any answer exposes uncertainty, confidence must be downgraded or status set to HYPOTHESIS.
Mandatory phrase when an E-001 failure class is discovered:
> **"Caught me overclaiming; I owe you a correction."**
A pre-registration correction is evidence governance succeeded — not failure.

**Correction = fix the SOURCE, not just the chat (non-optional).** A retraction is incomplete if it
lives only in the reply — the false claim stays recorded and **re-propagates to future sessions**.
So the *same turn* you retract, also **fix every recorded instance** of the false claim — the memory
file, the finding's `Reversal:`, the doc — marking it `CORRECTED: <old> -> <new>` (never
silent-delete; preserve history per §6.2 rule 4). Then state how the *true* fact was verified
(command/file:line), not just that you were wrong. (Worked example: "docs/ is gitignored" was a
mis-diagnosis of *untracked* as *ignored* — `.gitignore` has no `docs` rule; the memory entries
carrying it were `CORRECTED` 2026-06-24, not just corrected in chat.)

Full charter: [`docs/governance/EPISTEMIC_INTEGRITY.md`](docs/governance/EPISTEMIC_INTEGRITY.md).
Enforced by `tests/governance/test_epistemic_invariants.py`.

### Repository Truths Index (thin, always-loaded)
Active conclusions — full record + evidence in [`docs/current-findings.md`](docs/current-findings.md),
which is **authoritative on conflict**. This table is enforced ↔ the living doc by
`tests/test_current_findings.py` (every non-terminal finding must appear here and vice-versa):

| F-id | Type | Conclusion | Conf |
|---|---|---|---|
| F-001 | ECON | Intelligence is NOT the binding constraint — governance / throughput / consumption are | Certain |
| F-002 | ECON | The edge is in the decision PROCESS (selection ≫ SL/TP), not a static feature→outcome map | Likely |
| F-004 | ARCH | BitNet is a hard-reject gate (score < 0.55) WHEN `use_bitnet` is enabled (score persisted; only the *adaptive* threshold is dormant) — but `use_bitnet:false` on active `v2_multi_2026_04`, so INERT on the active patch | Certain |
| F-005 | ARCH | TradeNet v2 is BUILT but unwired — the fusion neural slot is a permanent stub | Certain |
| F-006 | GOV | `config_integrity` is a REAL check but ORPHANED — it gates nothing at runtime | Certain |
| F-008 | RISK | Concept drift is DETECTED but NOT acted on (no block / size-down) | Certain |
| F-009 | GOV | Per-instrument doctrine validated; global / multi configs underperform | Likely |
| F-010 | RISK | Headline ROI is BACKTEST-only; live PnL (ExecutionPlanner + UltronRiskGate) UNVERIFIED *(OPEN)* | Likely |
| F-011 | ECON | OOS persistence is real but small; persistence ≠ discrimination *(DURABLE)* | Likely |
| F-012 | ARCH | ReplayMemory / CognitiveBus / Cluster / HMF are sidecar-only (zero spine consumption) | Certain |
| F-013 | ARCH | scan→allocate→ExecutionLoop + PortfolioAllocator BUILT but ORPHANED; live runs the single-candle spine | Certain |
| F-014 | ECON | Time-to-first-move is a real, feature-orthogonal POST-ENTRY discriminator; FROZEN pending throughput | Likely |
| F-015 | ECON | Detection-gate relaxation is NOT quality-preserving; cheap throughput is exhausted on BNB/SOL | Likely |
| F-016 | GOV | On `patch`, active config is `v2_multi_2026_04` (pre-TP3); v4 applies only to the TP3 code line — supersedes F-007 | Certain |
| F-017 | ECON | Session policy is NOT a promotable BNBUSDT lever under realistic exits + OOS — supersedes F-003's "proven lever" | Likely |
| F-018 | GOV | Active config (patch) lags HEAD code: required sections absent + knobs hardcoded → data-gate runs on defaults; concrete symptom of F-016 | Certain |
| F-019 | ECON | No existing hypothesis qualifies (M4) across crypto majors under intrabar+12bps; toy entries ≈ random, spine throughput-starved | Likely |
| F-020 | ECON | No candle-conditional directional pocket on crypto majors (session×vol×momentum, h≤20); entropy "significance" saturates at large N, economics finds 0 pockets — extends F-019 to the conditional level | Likely |
| F-021 | ECON | Spine RETEST selection = the (incumbent, F-017-null) SESSION filter; no score/zone skill under intrabar+12bps (ZONE 0 rejects, SCORE noise) — F-002 stale, selection-beyond-session falsified | Likely |
| F-022 | GOV | `opportunities.jsonl` is a DETECTION STREAM, not a trade ledger — outcome/rr only 36.8% self-consistent (SL_HIT on paths that never touch the stop); derive realized truth via governing exit. Frequency illusion: 139,942 detections ≠ trades (spine=13) | Certain |
| F-023 | ECON | Feature morphology separates SHAPE, not expectancy — KMeans k=4 distinct anatomy, all win≈0.34 / mean_R≈0; kills the "just cluster harder" class | Likely |
| F-024 | ECON | Timing asymmetry (de-censored): losers resolve ~immediately (within-trade peak median 1 bar), winners mature over ~90 min (median 6 / p90 18 bars) — NOT 5.5 h; exit-agnostic path peak is random-walk/uninformative. Descriptive, partly mechanical | Likely |
| F-025 | ECON | Exit/cost is a risk/cost lever, NOT expectancy: on powered universe (n=53k) no SL/TP cell clears E>0 OOS (max recoverable +0.30R = cost recovery, still negative); bottleneck is entry information (reality_gap +4.16R, 90.55% plain_stop_loss). 4th falsification (entry/conditional/selection/exit all null) | Likely |
| F-026 | ECON | Program 2/E1: completed sweep→displacement→retest adds NO forward asymmetry beyond sweep (BNBUSDT) — point estimate NEGATIVE, loses to all 4 controls; INSUFFICIENT_POWER (n=47, ~1% funnel completion); calibration passed (instrument valid). Program 2 not advancing to E2 | Likely |
| F-027 | ECON | Program 3A: coarser timeframes (H1/H4) do NOT rescue the directional edge — toy pool 0 PROMOTE at H1/H4 (H4 expansion_breakout only reaches cost-recovery gross≈0), spine non-decisive; extends the M15 four-falsification sweep to the HTF horizon | Likely |
| F-028 | ECON | First real interpreter (P&F PNF-v1, double-top/bottom) carries NO standalone edge on crypto majors — shadow-measured REJECT on BNBUSDT, worse than random controls (Δexpectancy −0.039); FROZEN, reopen only via a NEW ontology not a sweep; extends F-019→F-027 | Likely |
| F-029 | OPER | Feature-pipeline `center=True` swing lookahead AND `volatility_regime` global-rank are both benign for trade generation — byte-identical across CRYPTO MAJORS (BNB/BTC/ETH/SOL, A/B/C/S sweep; extends+graduates trust-layer F1) — the adversarial "FATAL leakage / kill-the-model" verdict is DOC_DRIFT, the alleged training-contamination path doesn't exist, and the "execution successor" (TradeNet v2) is already built; FX/metals NOT INFORMATIVE (0 trades on active config) so cross-asset-class stays OPEN | Likely |
| F-030 | ECON | Contemporaneous volatility-regime LEVEL conditioning is economically non-consumable in spot directional architectures — vol memory confirmed (H_atr=0.885) but 0 exploitable cells; powered toys statistically informative (best regime beats nulls p≈0.0025) yet expectancy never crosses 0 (Authority-Ladder L1 not L2), 2 cells REDUNDANT (persistence not skill); spine arm INSUFFICIENT (underpowered, no claim). First non-directional falsification (Program 4 LEVEL channel KILLED); binding constraint = execution model, not predictability. TRANSITION channel (Markov P^H) untested → Program 4b | Likely |
| F-031 | GOV | Governance caught an overclaim before repository contamination — Program-4's v1.1 rollup emitted REGIME_HARMFUL for all-underpowered spine cells (all gate-INSUFFICIENT, n<30); a human review caught the semantic inflation and the rollup was corrected (v1.1→v1.2, all_insufficient guard) BEFORE registration. A pre-registration correction is evidence the governance system succeeded — formalized as the E-001E invariant + mandatory-phrase + pre-registration ritual (Program E-001) | Certain |
| F-032 | ECON | Cross-sectional dispersion (relative-value, market-neutral) on crypto majors is NOT monetizable net of costs — Program 5: 0 PROMOTE, all 5 interpreters REJECT (well-powered n=722–8,758); cross-sectional momentum loses (PF 0.335), the lone positive cell (reversal) is a long-leg/beta artifact (loses to long_only control) and insignificant (p=0.57). FIRST falsification on the PANEL (cross-sectional) axis — extends F-019…F-031 beyond the per-instrument directional frame; earns research authority only (§6.5), no CrossSectional style built on a single null | Likely |
| F-033 | ECON | Carry/basis is NOT an informative signal for cross-sectional spot dispersion on crypto majors — Program 6 (first axis tested on the newly-acquired perp corpus): 0 PROMOTE, all 8 carry/basis interpreters REJECT (well-powered n=722–4,373); both signs net-negative (E∈[−0.0032,−0.0016], PF 0.55–0.82, p 0.76–1.0), each loses to the market/long_only control → below even Authority-Level-1 information. Reuses the Program-5 kernel verbatim (Program 5 stays byte-identical). Scope: the signal-on-dispersion payoff only — NOT the funding-PnL carry-HARVEST payoff (Program 6b) or OI (Program 7); data corpus stays a permanent asset. Research authority only (§6.5) | Likely |
| F-034 | ECON | Carry HARVEST does not clear costs on crypto majors — Program 6b (the cashflow payoff, distinct from F-033's signal): 0 PROMOTE, all 4 tradeable harvest_full REJECT (n=104–729). Funding income is real but economically negligible: pre-cost +1…+6 bps/rebalance < ~24 bps round-trip turnover ⇒ all 4 funding-only twins DIAGNOSTIC_NEGATIVE (cashflow doesn't cover its own cost); price/basis drag makes the full trade worse; lowest-turnover H=672 still REJECTs. Authority separation held (funding-only = diagnostic-only, never promotable). NOT a claim that funding is worthless — a low-turnover/netting cash-and-carry is a separate untested construction needing a fresh thesis (not an H/cost tweak). STOP after F-034. Research authority only (§6.5) | Likely |
| F-035 | ECON | Entry-information null GENERALIZES from crypto to FX majors — first non-crypto asset-class test. Existing toy pool + spine through the VERBATIM M4 gate (intrabar_fixed, 12bps, 2000 perm), re-scoped to 5 FX majors (2yr M15 fetched via MT5): 0 PROMOTE. Toys WELL-POWERED + decisively negative (expansion_breakout/mean_reversion ALL REJECT, n=7.7k–17k, PF 0.02–0.10, E −1.5…−2.8R); spine INSUFFICIENT per-inst (2–8 trades, corroborates F-029), POOLED n=30 REJECT. COST CAVEAT: 12bps = 1.8–2.5× the median FX M15 bar so magnitude is cost-dominated (extends F-025), but PF≪1 makes the direction null robust to cost (0bps wouldn't cross). XAUUSD excluded (holiday gap REJECTs FX gap gate). Research authority only (§6.5) | Likely |
| F-036 | ECON | `engine_runner.zone_gate` knobs (top_k/cluster_min_n/cluster_spread_max) are config-TUNABLE but INERT — ΔG001≡0 (byte-identical entries ∀ top_k×BNB/ETH/BTC/SOL). MECHANISM CORRECTED (E-001): the earlier "zone fusion-weight 0.2 flips 0 decisions" was an OVERCLAIM measured with the FUSION GATE OFF in backtest (`.env` BACKTEST_ENGINE_GATE=0, F-037). RE-MEASURED gate-ON (live-equivalent fusion spine BNB11/ETH4/BTC5/SOL6): zone is non-pivotal for real — weight{0,0.2,0.4,0.6}×threshold{0,0.25,0.5} all byte-identical; audit shows zone NOT weak (mean 0.608, +0.358 above thresh, passes 85%) and NOT under-weighted → redundant/decision-dominated, fusion vetoes are zone-independent. Tunability-NOT-authority; default top_k=3. Confidence restored→Likely. Extends F-021/F-019 | Likely |
| F-037 | ARCH | The research "spine" is CRT-only by design — the EngineRunner 4-engine FUSION gate (CRT/Gaussian/ZoneGate/RR→Fusion→Decision veto) is OFF in backtests (`.env` sets BACKTEST_ENGINE_GATE=0, honored only by backtest_v2; live path always runs it). Probe: EngineRunner.run() called 0× in spine-adapter backtest. So F-019/F-036/qualify_majors measure CRT-state-machine entries, NOT the full fusion stack the spine_signal_source docstring claimed (now fixed). Gate-ON impact modest+real: BNB 13→11, SOL 7→6 (gate-OFF reproduces corpus exactly). USER-CLASSIFIED INTENDED (CRT isolation) → doc-side fix. Scope-correction NOT conclusion-reversal (gate-ON = smaller-N → null unaffected) | Certain |
| F-038 | ARCH | **[FIX SHIPPED 2026-06-26]** the "RR" engine was a GAUSSIAN DUPLICATE in gate-ON fusion — rr_fusion's confidence gate almost always bypasses to gaussian (Mahalanobis conf≈1e-88…5e-5 ≪0.3 threshold even with Fix A's full feature vector), discarding the base RREngine. Remediated by disabling `engine_runner.rr_fusion.enabled` in the active config (`v2_multi_2026_04.json`) per the §6.5 Authority Ladder (rr_fusion never demonstrated ΔG001 improvement) — code-verified the disable path is structural (RRFusionLayer never constructed when `enabled=false`, base `RREngine.compute()` flows through unmutated, no `rr_fusion` metadata key, hash-neutral, grep-confirmed no downstream consumer breaks). Regression test added (`test_rr_fusion_disabled_is_base_rr_identity`, full-object identity). Fusion now runs CRT+Gaussian+ZoneGate+base-RR honestly (no double-weighted gaussian). Retrain/recalibration of the underlying model remains a separate, non-blocking research track (Funding Ledger) — model is OOD even when fed correctly, root cause unresolved | Certain |
| F-039 | ARCH | Repo-wide census 2026-06-26 (dated observation, not a future guarantee): the L3 dataset-integrity pre-flight (`dataset_integrity.validate_dataset`) runs at ONLY two call sites, both in `backtest_v2` (`_preflight_dataset`/`validate_universe`); every other `CandleLoader.stream()` consumer — the whole `src/research/` pipeline + analytics/governance/replay/config_validator AND the entire `scripts/` training/research/analysis fleet + tests — streams with only the always-on inline L1/L2 backstop (no L3). `dataset_integrity.py:24` "every backtest entry point" overclaim CORRECTED (DOC_DRIFT). SCOPE GUARD: L3 adds confidence, not validity — does NOT invalidate F-019…F-035 (the inline backstop DID enforce schema+chronology); flags a single-layer fragility (permissive `stream()` = sole net removed). No-lookahead = conjunction of L1/L2/L3+generator. Authority: doc/research only | Certain |
| F-041 | GOV | ZoneGate runtime scores through `models/zone_registry.json` (8 zones, HARD gate) per active config (`engine_runner.zone_registry_path`, `zone_mode=hard`) — NOT the `zone_gate_registry.json` version manifest, whose `active:true` pointed to a *different* file (sha256 `aade29c4`≠`e73e0893` → TruthConflict §6.2) — **F-041A RECONCILED 2026-07-05 (B1)**: registered+promoted `v2_gaussian_runtime_2026_07` so manifest active == config-loaded `models/zone_registry.json` (`e73e0893`); permanent invariant `tests/test_zone_manifest_runtime_parity.py` enforces it. **Phase-5/F-041B RESOLVED 2026-07-05**: the stored ~98% SL-hit / 6-of-8 negative mean_RR labels are an **F-022 labeling ARTIFACT** — re-deriving all 139,942 source opportunities through `forward_walk(intrabar_fixed)` over the VERIFIED-identical KMeans membership gives honest SL≈0.66 (Δ≈−0.33 ∀zone, + sign-flips) → CONTAMINATED; AND 0/8 zones clear honest E>0 (bootstrap CI all <0) → underlying HONEST_NO_EDGE, so label-quality is NOT the rescuable ZoneGate defect (binding constraint = entry-info null F-019…F-040/F-025; consistent w/ F-036 NON_PIVOTAL, honest win≈0.34 re-confirms F-023). Runtime↔label assignment parity only 0.414. Gate is geometric → no live risk. E-001 self-correction: earlier "manifest empty → silent fail-open" was a parse artifact. Authority: governance-hygiene/research only | Certain |
| F-040 | ECON | The volatility/range-EXPANSION + compression→expansion TRANSITION channel (F-030's untested Program-4b successor) is INFORMATIVE but NOT economically consumable in the spot directional architecture. Two-stage pre-registered gate on the M15∧H1∧H4 candle-state conjunction (M15 base, H1/H4 derived; no M5 on disk): Stage-1 4b-vol/4b-range/4d-transition all permutation-significant (crypto+FX p≈0.0005), UNIVERSAL, persistent (half-life 8, 2024→2025 retention 0.67–0.99); 4c-persistence NOT informative (p≈0.97). Stage-2 directional consumer (compression_breakout, unchanged M4 gate, intrabar_fixed+12bps) 0 PROMOTE, well-powered REJECT (crypto E −0.25…−0.60R WR≈0.33; FX cost-dominated PF 0.02–0.08). Stage-1-PASS/Stage-2-FAIL: information priced efficiently, binding constraint = EXECUTION MODEL not predictability (extends F-030). SCOPE: MTF-conjunction's incremental info beyond single-TF vol NOT isolated (consistent w/ vol memory, no novelty claim); FAIL = directional construction under fixed standard, not "no instrument could monetize." Program 4 CLOSED. Authority: research/docs only | Likely |
| F-042 | ECON | The weekly liquidity-sweep ontology (ICT/CRT Mon+Tue accumulation → Wed-Fri sweep → reversal) does NOT clear the M4 gate on FX majors — Program 8 CLOSED. Pre-registered new geometry (`src/research/weekly_sweep/`, calendar-locked weekly range + boundary-cross-then-close-back-inside sweep, reimplementing crt_engine_v2's local-sweep geometry against a WEEKLY range) through the unchanged M4 gate (intrabar_fixed+12bps), same 5 FX majors as F-035. 0 PROMOTE across all 6 scopes (per-instrument REJECT at the absolute-expectancy gate, POOLED n=512 E=−0.634R PF=0.457); all 6 DO beat their winning control (p=0.0005) but that relative edge is moot since absolute expectancy stays negative. Direction×Vol 3×3 diagnostic (CandleStateEncoder direction × RegimeLabeler macro-vol, tercile_window=2000): 8/9 cells negative, one small-N positive (DOJI/EXPANSION) — information only, no authority. Extends F-019…F-041 to a genuinely NEW weekly-CALENDAR ontology (distinct from Program 1/2's local-structural frame). Authority: research only | Likely |
| F-043 | ECON | A forward Markov P^H regime-transition forecast is REDUNDANT with the current vol level and persistence — Program 4b CLOSED. New `MarkovRegimeForecaster` (`src/interpreters/regime_observer.py`, trailing transition matrix, w_markov=480, h=8, reuses `RegimeLabeler`'s S_t verbatim) feeds the unchanged `regime_conditioning.evaluate_scope` cross-matrix, extended additively with a within-tercile-shuffle 5th control (default-None param reproduces Program 4's F-030 artifact byte-identical, re-verified). Hard calibration gate passed (BNBUSDT H_atr=0.885027). 0 REGIME_EXPLOITABLE across all 15 scopes: all 10 toy consumer×scope combos (expansion_breakout/mean_reversion) resolve REGIME_REDUNDANT — well-powered (n=3,645–35,525), statistically real (p≤0.045) but fully explained by BOTH a stale-regime lag AND the current vol level (S_within_tercile ≥ S_real); spine REGIME_INSUFFICIENT (no claim). Corrects a stale Funding Ledger entry that conflated this literal Markov construction with F-040's different MTF-conjunction "4b/4c/4d" closure; the pre-registration's reserved "F-031" was superseded, this is F-043. Authority: research only | Likely |
| F-044 | ARCH | The RR-fusion confidence gate is MIS-SPECIFIED for its dimensionality — refines F-038's mechanism from "model OOD" to "gate mis-scaled." In-sample probe (`scripts/analysis/rr_confidence_probe.py`, READ-ONLY) runs all 49,000 training rows of `models/rr_model.json` back through `NanoInferenceEngine`: **100% in-sample bypass**; min in-sample `d_sq`=4.30 > the `d_sq<2.408` needed to clear `confidence_bypass_threshold=0.3` (`rr_pattern_miner.py:339-342`) → not one training point passes. Cause: `confidence=exp(-0.5·d_sq)` over a **rank-27** Mahalanobis form (38 dims − 11 `zero_indices`; static-validated) has in-dist `E[d_sq]=27` (measured mean 26.7, median 21.5 ≈ χ²(27)) → in-dist confidence ≈ exp(-13.5) ≈ 1.4e-6 ≪ 0.3. Decisive: a model can't be OOD on its own training data ⇒ the defect is the GATE, and retrain alone can't fix it (any well-fit model reproduces the `exp(-0.5·dof)` floor). Fix = dof-aware gate (χ²-tail or `d_sq/dof`), additive + config-behind + parity-proved (default `legacy_scalar` byte-identical); grants NO authority to re-enable rr_fusion (stays `enabled:false`, §6.5). Authority: architecture/governance only | Certain |
| F-045 | GOV | The RR-model economic kill-test is INDETERMINATE (not a clean RETIRE) — its labels are F-022-contaminated. 5-fold CV shadow test (`scripts/research/rr_shadow_value.py`, READ-ONLY, n=49k, model raw outputs computed BYPASSING the F-044 gate) shows APPARENT OOS discrimination (AUC 0.605 vs shuffle 0.505; rr_corr 0.074; top-decile y_rr +0.042 vs random −0.078) — surprising vs the F-001/F-002 prior. BUT y_win/y_rr derive from the trade `outcome`/`rr_achieved` field (`rr_dataset_builder.py:125-206`) = the F-022 stream (36.8% self-consistent), and y_rr is near-degenerate (win==+1.0 → y_rr≈y_win); F-041B precedent = this contamination flips on `forward_walk` re-derive. So the discrimination is not credible economic evidence → no Keep/Retire verdict. REQUIRED: re-derive y via forward_walk(intrabar_fixed) + re-run. Two E-001 pre-registration corrections caught before registering a false RETIRE (Tier-3 logic bug; missing label-validity gate). NO authority; rr_fusion stays `enabled:false`. Authority: research/governance only | Certain |
| F-059 | ARCH | Clean-label RR kill-test KEEP_CANDIDATE research-only (rr_corr 0.167, top-decile beats random but mean R still −0.44); no rr_fusion authority — completes F-045 re-test | Likely |
| F-046 | ARCH | `wick_size`/`body_ratio` had a divergent (DEAD) definition, not three: the CRT engine `Candle` property ≡ the batch pipeline (`body/candle_range`, bounded [0,1] — the only def the `body_ratio>=0.70` gate is coherent against); the lone outlier `crt_feature_builder` (`body/total_wick`) has ZERO call sites. Canonical = body/range; unified all paths behind immutable `src/features/candle_math.py` (+ WHAT-layer `configs/formulas/market_ontology.yaml` / `formula_registry.py`, parity-tested). ZERO runtime impact (byte-identical, 210 golden tests green). Authority: architecture/governance only | Certain |
| F-050 | ARCH | **[REMEDIATED CH-002 2026-07-09]** CRT `cached_features` now emit FM-027 `displacement_retrace` + FM-028 `displacement_atr_ratio` via `derived_math` (no longer under colliding pipeline names `retest_depth`/`disp_strength`). Pipeline FM-021/FM-020 unchanged. BitNet call-site maps FM→legacy model input keys only if `use_bitnet` (still false, F-004). Residual: historical training JSONL pre-CH-002 keys until rebuild. CH-001 registered math; CH-002 renamed emission. Authority: architecture/governance only | Certain |
| F-051 | ARCH | Centered-swing production binding is non-PIT: leaks future bars, contaminates 10/38 canonical dims (~63% bars differ), exposes CRT/ZoneGate/model inputs, live default-absent path is live-zero; final-ledger structural importance INCONCLUSIVE (PC-2 failed — null ledger ≠ structure-insensitive); F-029 gate-OFF trade-generation refined not reversed; RR/Zone artifacts PIT_UNCLEAN_CENTERED_SWINGS (no promote/re-enable without causal revalidation; no immediate retrain). FC1-A contract frozen. Authority: architecture/governance only | Likely |
| F-052 | GOV | PLAN-002 closure — the 2nd engines-path CODE authority (the (0.35,0.25,0.20,0.20) fallback in `engines.crt_engine.compute`) removed: missing `score_component_weights` now FAIL-CLOSED (returns `{score:0.0, reason}` via the broad except, NOT a silent CODE literal and NOT a propagated exception); all real callers (EngineRunner, S01CRTWrapper, both probes) inject the HOW key; `conf_weights` + `risk_score_weights` untouched; the two weight identities stay distinct. IC-007 closed at implementation + focused-regression (38/38). Authority: governance/hygiene only | Certain |
| F-048 | ARCH | **[RESOLVED 2026-07-24]** The DecisionEngine RR gate consumed candle polarity ∈[0.5,1] against `rr_threshold=1.5` → `low_rr` every candle → `run()` executed 0/70,002. RESOLVED as an OWNERSHIP decision (not intent-adjudication): the gate was REMOVED — DecisionEngine is now semantic-approval only (score/p_win/zone/weak-component), and economic reward:risk is owned SOLELY by UltronRiskGate (cost-taxed `min_rr_ratio`, after ExecutionPlanner SL/TP; contract D). `decision_engine.rr_threshold` retained-but-RETIRED (hash-neutral). Parity: no real path fed economic RR to DecisionEngine (only test injectors) ⇒ removal byte-identical; XAUUSD gate-ON ledger unchanged. Unblocks GD-001/002 body_ratio remediation. Authority: architecture/governance only | Certain |
| F-047 | ARCH | The market ontology is now the AUTHORITATIVE source for feature mathematics (geometry + deterministic derived metrics: disp_strength/retest_depth/ema_spread/momentum_score/volatility_ratio parity_verified + liquidity_* registered), with stable IDs (`FM-0NN`)/per-feature version/lifecycle/`depends_on` DAG. Registry-authoritative (`src/features/registry/` package behind the `formula_registry` facade + scalar `derived_math.py`; never `eval`'d). Enforced by parity (pipeline↔scalar), an OWNERSHIP-lint (`scripts/analysis/feature_math_lint.py`, semantics-not-syntax; fails on NEW re-derivation) + a feature-lineage exhaustiveness invariant. Census pinned 10 pre-existing divergences → adjudicated 2026-07-07 into a durable GD-001…GD-010 ledger (`durable_key` AST-fingerprint + append-only retirement manifest + monotonic ratchet; Matrix v1 = `docs/analysis/feature-math-divergence-adjudication.md`). Load-bearing `live_engine_hook.py:361` NON-CANONICAL `body_ratio` (body/total_wick) is decision-reachable IN CODE (chain: pipeline_mode→LiveEngineHook→EngineRunner.run:570→crt_compute:654→compute_scores:40→fusion) but execution CONDITIONAL (live-hook only; backtests use canonical pipeline; F-010/F-037 → NO production-loss claim). Gate-2 7c decision-flip RETRACTED 2026-07-08; V1-V10 validation → POSITIVE_CONTROL_NOT_CONSTRUCTIBLE: `run()` structurally never executes (rr gate = RREngine polarity∈[0,1] vs threshold 1.5 → low_rr always; 0/70,002 executes) & is a veto whose pass-path (zone bypass) is body_ratio-independent ⇒ decision-inert at run() BY STRUCTURE (source-confirmed). observed_decision_flips=not_measured (empirically); correct instrument = backtest-ledger diff (predicted 0). GD-001/002 decision-reachable, urgency UNDETERMINED. disp_strength sites = rename (distinct quantities); `crt_engine_v2:2539` already routed canonical. Enforcement-only; remediation deferred to per-GD Phase-B findings. Hash-neutral. Authority: architecture/governance only | Certain |
| F-055 | ARCH | Enabling the EXISTING (F-050-skewed) BitNet gate does NOT improve the CRT spine — shadow A/B (gate-ON clone `v2_multi_bitnet_shadow_2026_07` vs active OFF, same `model.json`, BNB/ETH/BTC/SOL) pooled book ΔE=−0.13R (E 0.156→0.023, PF 1.29→1.04), 0/4 instruments improve (BNB neutral, ETH/BTC inert, SOL harmful −0.35R), underpowered n<30. The gate is a state-machine-perturbing VETO not a filter (a `LOW_SCORE` reject resets the CRT state machine → divergent trajectory, removed≠added; BNB 50 rejects yet 11→11 trades). `atr` fed raw/unnormalized (not scale-invariant). No ΔG001 ⇒ no authority (§6.5); `use_bitnet` stays false on active; shadow config not promoted. Extends F-004/F-050 | Likely |
| F-054 | ARCH | Bottom-up feature-DAG certification (Milestone 1, L0→L2): built the missing spine — topological DAG + L0–L6 layering (`feature_dag_layers.py`, 38/38, 2 fc05 bugfixes), append-only certification ledger + resolver (`feature_certification_state.py`), transitive-invalidation engine with `formula_hash`/`dependency_contract_hash` + ordering gate + STALE cascade (`feature_dag_certify.py`), series-parity+PIT rolling cert (7/7). Executed frontier = 28 PROMOTED_PRODUCTION: L1 ATR/RSI/EMA/true_range/swings promoted to first-class `rolling_indicators` FM-040..046 (lifted B3 freeze, ontology v1.3 + `validate_registry` windowed exemption, `validate_registry()==[]`, byte-identical); FM-030/031 re-certified vs PROMOTED ATR + PROMOTED as production-intended identity, legacy FM-022/023 SUPERSEDED. Reverses B2B-first: correct upstream in topological order, consumers migrate after (a dependent can't certify until every dep is certified+promoted). Milestone reaches promoted-IDENTITY not ACTIVATION — no live math swap/retrain/recalibrate, 38-dim intact, `PRODUCTION_BEHAVIOR_CHANGED=NO`; STALE cascade over rr_model/gaussian/dual_engine/backtests/F-053 evidence records. Decision impact UNKNOWN · Economic value UNKNOWN · Activation authority NONE; L3+/L6 deferred. 54 new floors + registry/lineage/lint/pipeline (84) green. Authority: research/governance only | Certain |
| F-053 | ARCH | B2A candidate-formula CERTIFICATION: FM-030 `ema_spread_atr` / FM-031 `momentum_score_atr` are mathematically + temporally sound — both PROMOTE across synthetic+BNB/BTC/ETH/SOL on THREE-path reconstruction (independent raw-OHLC float64 `TR_abs→SMA14=ATR_abs` ≡ linked `atr_relative*close` ≡ emitted `legacy/close`; float32 `ema_fast−ema_slow` cancellation attributed, not a formula error), scale-invariance (err ~1e-14 vs legacy ~100× defect), NaN/Inf discipline, deterministic recompute, scalar↔vector parity, PIT/prefix invariance. Observe-only probe `scripts/analysis/b2a_feature_candidate_certification.py` + floor `tests/test_b2a_feature_candidate_certification.py` + immutable artifact (`b2a_feature_candidate_certification.LATEST.json`). All behavioral/decision/economic metrics quarantined under `NON_AUTHORITATIVE_DOWNSTREAM_DIAGNOSTICS` (never gate). PROMOTE = B2B-eligible ONLY; Decision impact UNKNOWN · Economic value UNKNOWN · Activation authority NONE; ontology FM-030/031 stay inactive; vector stays 38-dim; PRODUCTION_BEHAVIOR_CHANGED=NO. Extends B0/B1. Authority: research/governance only | Certain |
| F-056 | ARCH | `backtest_v2` had 3 trade-affecting constants declared in NO config — `partial_tp_fraction` was strict-read then DISCARDED (config illusion; hardcoded 0.5/0.5 blend at 3 sites incl. a `:2426` one missed by audit), `sl_atr_buffer` duplicated as a `0.2` literal not read, `p_win<0.35` bare literal. REMEDIATED (all declared+strictly read; BNBUSDT byte-identical, params hash unchanged; floor `tests/test_backtest_declared_constants.py`). Lesson: presence+strict-read ≠ governed until the value reaches behavior; byte-identity only covers exercised paths. Authority: architecture/governance only | Certain |
| F-057 | ARCH | **[RESOLVED 2026-08-09]** CRTConfig resolution split-brain on the programmatic `crt_config is None` path is fixed — `backtest_v2.py:1739-1748` now routes through `load_prod_config_from_registry` (the same governed per-instrument loader the CLI uses) with a fail-closed provenance gate (`:1750-1759`) rejecting router-derived config by default; `market_router.py`'s hardcoded profiles are gone (now config-driven). Regression test `test_f057_f058_config_authority.py`. Residual: `MultiInstrumentRunner.run_all` still reuses one instrument's resolved config across a batch run (`backtest_v2.py:2932-2945`), masked today, not yet fixed. Authority: architecture/governance only | Certain |
| F-060 | ARCH | The live Gaussian channel is an UNPARAMETERIZED kernel that degenerates to a near-CONSTANT ≈0.8825 — (1) all 11 `gaussian_registry.json` entries lack `mu`/`sigma` so the `_normalize_registry_entry` defaults (0/1) fire even on a SUCCESSFUL load ⇒ score = `exp(-x²/2)`, byte-identical to no-registry (refines "TRAINED_ARTIFACT = INERT" to "no learned parameter reaches the score at all"); (2) `tanh(momentum_score)` saturates on 93.4–99.9% of 280,008 bars because the ontology's already-registered `FORMULA_CORRECTION_DEFERRED` defect (absolute Δprice ÷ relative atr, corrected identity FM-031) yields magnitudes ~10³, and `mu=0` discards the sign ⇒ std 3e-3…1e-2 — **first case of a deferred formula correction carrying a DECISION-surface cost, not just a representational one**; (3) the audited trainer (`train_pipeline`) built none of the on-disk artifacts — the builder of record is `phase5_calibration.py`, training on raw `rr_achieved` from the F-022 stream ⇒ contamination CONFIRMED, not "possible". Ablation (F-036 method, gate-ON): `GAUSSIAN_INFORMATION_INERT` — all 3 cells (live / pinned-at-saturation / pinned-0.5) byte-identical ∀ BNB/ETH/BTC/SOL, so the channel is non-pivotal on BOTH information and level axes (n=26<30 ⇒ proof of non-pivotality, no economic claim). Descriptive, not economic; grants NO authority | Certain |
| F-061 | ARCH | The FM-022/023 dimensional mix is a DECISION-surface defect on crypto, not a representational one — legacy ≡ corrected × `close` (closed form, verified 9.9e-08), so against the active `dual_engine` thresholds (0.15/0.3) FOUR consumers degenerate: `detect_regime` returns `"trend"` on 98.86% (BNB) / 99.94% (BTC) of bars, `breakout_engine` score is pinned at 1.0 on ~100%, `tanh(momentum_score)` saturates 98.8/99.9% (= F-060's mechanism, one instance of the pattern), `gate_intelligence` REVERSAL collapses to 0.0. Corrected identity discriminates and is instrument-invariant (52.7/52.8/50.1% trend across BNB/BTC/EURUSD) ⇒ the thresholds are tunable but INERT on crypto, binding only where close≈1 (FX). Three sign-only consumers unaffected. REMEDIATED to config-gated: FM-030/031 promoted to registered identities behind strict `feature_pipeline.normalization_basis`, default `atr_relative` byte-identical (XAUUSD freeze-pin vector SHA unchanged); corrected arm reachable only via a non-promoted shadow config. Generalizes F-060; DESCRIPTIVE only, grants NO activation authority | Certain |
| F-058 | GOV | **[RESOLVED 2026-07-23]** `backtest.engine_gate_enabled` is now a strictly-required config key (`_require_bt_cfg`, `backtest_v2.py:2050`) — `true` on the active config and all others carrying `backtest`; `.env`/env-var is now an explicit override that WARNs on disagreement (`:2054-2063`), closing the silent-default class. Epoch change: gate-OFF corpus behind F-019/F-036/F-037 valid only for its pre-2026-07-23 epoch. Residue: resolved gate mode is WARNed, not written to run artifacts (tracked via `MEASUREMENT_CONTRACT.md` §9/§10); gate-ON re-measurement of the corpus queued (M-GATE-01, `RF-CRT-STRUCTURE.L5`). Authority: governance only | Certain |
| F-062 | GOV | **[FIX SHIPPED 2026-07-31]** The feature-DAG spine (`scripts/analysis/feature_dag_layers.py`) was stale against schema v4.0 (still declared v3.0 names `wick_size`/`macd_hist`), so `feature_surface_query --summary` reported `surface_status: CLOSED` while 3/39 canonical slots (`candle_range`/`macd_hist_raw`/`macd_hist_z`) had no certification-ledger row. Renamed the three `_NODES` entries to the v4.0 names; all three now `PROMOTED_PRODUCTION`, `closure: {'CLOSED': 39}`, no `None` rows. Byte-identical (XAUUSD vector SHA/SCHEMA_HASH/FEATURE_ORDER_HASH unchanged). Authority: governance/hygiene only | Certain |
| F-063 | ARCH | **[FIX SHIPPED 2026-07-31]** `trend_strength`/`candles_since_retest` were the ONLY 2 of 39 canonical slots with no ontology identity — registering either name tripped `feature_math_lint` red on an unrelated same-named execution-code local (`engine_runner.py:151` local `trend_strength`=abs(ema_spread)) or a genuine two-producer collision (`crt_engine_v2.py`'s live bars-since-RETEST-CANDLE vs the pipeline's bars-since-SWEEP FM-065). Renamed the `engine_runner.py` local to `ema_spread_abs`; registered FM-064 `trend_strength` + FM-065 `candles_since_retest` (pipeline quantity) + NEW FM-070 `candles_since_retest_state` (CRT engine's distinct quantity, `derived_math.py`), with a legacy-name alias added ONLY at the BitNet call boundary (CH-002 pattern). `_UNREGISTERED_VECTOR_SLOTS` ratchet now empty. Byte-identical. Authority: architecture/governance only | Certain |
| F-064 | ARCH | F-061's FM-022/023 dimensional-mix decision-surface defect GENERALIZES to XAUUSD (4th instrument, non-crypto): `|tanh(momentum_score)|>0.999` on 99.70% of 19,922 bars, `|ema_spread|>0.15` on 99.99%, exact 100.000× scale ratio under a synthetic 100× price shift (vs 1.000× for every other ATR-normalized dim) — confirms `legacy == corrected * close` off crypto. Measured, not activated: `normalization_basis` stays `atr_relative` by explicit decision; a one-time startup log warning added (log-only, zero emitted-value change). DESCRIPTIVE only, grants NO activation authority (§6.5) | Certain |
| F-065 | ARCH | The participation (volume) channel is declared twice on the live decision path and consumed by neither: (H7) `gate_intelligence._liquidity_score`'s documented 50%-weight `vol_score` is a structural constant 0.0 — its sole input `volume_ma20` is never emitted by either production feature builder (`live_engine_hook.py`/`backtest_v2.py`, grep-confirmed), only by a non-canonical pipeline intermediate + a hardcoded test fixture; (H8) `market_crt_states.yaml` declares `volume_spike: [NoSpike, VolumeSpike]` in `feature_states:` but no CRT state's `when:` block references it. Declaration only (ontology `SEM-004` + inline pointer comments) — fixing H7 changes live decision scores on every bar, out of scope for a hash-neutral pass; needs a separately authorized behavior-change program. OPEN | Certain |
| F-066 | ARCH | MT5-sourced `session`/`hour_of_day` (FM-052) derive from broker-server time labeled UTC (`mt5_candle_fetcher.py:186`) — 53.36% of XAUUSD bars carry the wrong session label. TWO independent tests confirm (BTCUSDT cross-correlation: exact on-the-hour shift, −3h summer/−2h winter; NFP-release alignment: season-invariant 15:30 server, not the 12:30/13:30 UTC split true stamps would show), plus the server tracks **US** DST not EU (boundary holds through US/EU mismatch weeks). Scope-bounded: Binance corpora (F-017/F-021's BNBUSDT base) are UNAFFECTED. Two surfaces treated differently — the FEATURE is a mislabel (fixed); the FILTER (`crt_engine.session_windows`, live trading gate) was empirically tuned on broker time and is deliberately left untouched (relabeling it is a separate economic decision, not a bug fix). Shipped config-gated (`feature_pipeline.session_timestamp_basis`, mirrors F-061's `normalization_basis` pattern): `broker_local` DEFAULT/byte-identical, `utc_corrected` opt-in via new `features/broker_clock.py` (NY-DST-aware, not Europe/Athens). Hash-neutral (`feature_pipeline` is non-`params`). Activating on the ACTIVE config is a separate gated decision (freeze-pin re-certification required). Authority: architecture/governance only | Certain |
| F-067 | ARCH | Soft-confirmation `EngineState.update_emas` fires twice on the same candle close during the RETEST window (`crt_engine_v2.py:2629` unconditional + `:2998` inside `elif evaluating_soft_conf` — no `RETEST` state branch exists, so every confirmation candle falls through to the second call). A received bug-trace called this `EMA(EMA(close))` making momentum "overly sensitive"; source-verified BACKWARDS — double-application = effective α=2α−α² (span 1.25 not 2 for `ema_fast=2`), which COMPRESSES the trend spread and makes `f_mom` UNDER-state momentum, making approval HARDER. OBSERVATION_ONLY probe (`scripts/analysis/soft_conf_ema_double_update_probe.py`, no `src/` edit) on full XAUUSD corpus: n=17 evaluations, trend ratio 0.4673 (matches closed-form ~0.46–0.47, CONFIRMED), chop ratio 0.9698 (the toy alternating-series ~1.34x inflation did NOT replicate on real chop — reported as observed), 0/17 tier flips (ledger-neutral on this evidence), self-consistency 0.0 (bit-exact reimplementation). No fix applied — remediation is a separate gated turn. Authority: research/architecture only | Certain |
| F-068 | ARCH | Shadow-memory TTL off-by-one: `reset_to_range`'s `[DEADLOCK FIX]` fall-through (`crt_engine_v2.py:2655`) means a shadow created via HTF-reset reaches the RANGE branch's TTL countdown on the SAME candle — pre-fix, that branch unconditionally decremented, so a configured TTL of N yielded only N−1 usable bars. Fixed via new `EngineState.pending_displacement_created_idx` (set on creation, guards the decrement at `:2700-2701`, cleared on all 4 existing teardown paths). `tests/test_shadow_ttl_lifecycle.py` verified to FAIL against the pre-fix guard (reverted, ran, confirmed `[2,1,0,0]` not `[3,2,1,0]`, restored). A separate bug-trace claimed this was "documented in the code with the comment 'same bar burns 1'" — that comment does NOT exist in source (only in a prior session log); CORRECTED, comment now added for real. XAUUSD before/after: `SHADOW_PENDING` 43→51 (+8), `SWEEP` 6995→6987 (−8), all else byte-identical, `total_setups` unchanged at 1 (no economic claim derivable at that N). Authority: architecture/governance only | Certain |
| F-069 | ARCH | CRT Semantic Parity (CRTStateResolver vs BacktestRunner, config-only): baseline 88.16% (41,607/47,197 XAUUSD M15, `injection=none`); RANGE/SWEEP/DISPLACEMENT already 96–98% recall, EXPANSION only 10.77%. Exhaustive 33-candidate coordinate-descent sweep (6 param groups, every resolver threshold with an engine counterpart) found the best anti-Simpson-safe candidate at only 88.46% (+0.30pp) — several higher-raw-agreement candidates (up to 89.77%) were correctly REJECTED for zeroing EXPANSION recall to 0.00% (Simpson's-paradox trade). Mechanism (source-verified): with `continuous_disp_to_expansion:false`, the resolver skips its ATR-extension EXPANSION-entry gate entirely, reaching EXPANSION only via a declarative predicate/sticky-dwell — a different construction from the engine's `try_displacement_to_expansion()` state machine, not a mistuned threshold. Volume-weighted mismatch classification: Category C (divergent construction) = 96.1% of residual bars, Category B (3 structurally unreachable states) = 0.1%, Category D (uninvestigated, ≤50 bars/cell) = 3.8%. **Determination: structurally config-unreachable** — closing it needs a resolver code change, out of this program's freeze. Also corrects a stale in-session estimate: the historical instrument ran with unconditional engine-oracle injection, producing 64–99% figures that never measured "configuration alone." Report: `reports/crt_semantic_parity_report.md`. Authority: architecture/governance only | Certain |
| F-070 | ARCH | M-GATE-01: on the ACTIVE config epoch, the 4-engine fusion gate vetoes 0/30 CRT-committed entries across all 4 crypto majors (BNB 13, ETH 5, BTC 5, SOL 7 — full historical window, gate-ON == gate-OFF byte-identical, non-vacuity guard passed). F-037's recorded 2026-06-25 gate-ON reduction (BNB 13→11, SOL 7→6) does NOT reproduce today. Confirmed via the run's own native artifact (`rejected_trades:0`), not just adapter parsing. Does not reverse F-037 (history preserved, §6.2 rule 4) — the ACTIVE-config object has changed since. Plausible driver (Likely, not proven — E-001 discipline): F-038 (rr_fusion disabled 2026-06-26, one day after F-037) and/or F-048 (DecisionEngine RR gate removed 2026-07-24), both independently VALIDATED; not isolated in this run. Script: `scripts/research/gate_measurement_m_gate_01.py` (SITS-registered). Grants NO authority — does not re-enable rr_fusion, does not claim general inertness. Authority: architecture/research only | Likely |
| F-071 | GOV | **[RESOLVED same-session 2026-08-09]** The committed repository was not the running system: 239/476 (50.2%) `src/` modules, the entire Semantic OS (`docs/governance/semantic_os/*.yaml` + 4 modules, despite PR-2..5 marked "SHIPPED 2026-08-08" with no commit behind it), all CI (`.github/`), and the pre-commit hook (`hooks/`, activated only via a local, unversioned `core.hooksPath`) existed solely on-disk. HEAD's own last commit (F-069) shipped a file importing a module that commit didn't include. Restored via 5 dependency-ordered, secret-scanned, additive-only commits (1,838 files, ~468k lines), verified from a fresh `git worktree`: 0 unresolvable imports (was 16), Semantic OS VALID, spine modules import cleanly. Clean-checkout gate run surfaced a second-order residue: evidence citing `models/`/`results/` paths still can't resolve (those trees correctly stay out of scope — gitignored or unvetted). 9 pre-existing GREEN_FLOOR failures + 1,077 untracked paths remain, unrelated/out of scope, not yet triaged. Authority: governance only | Certain |
| F-072 | ARCH | **[PARTIALLY RESOLVED 2026-08-09]** Canonical `atr` is close-relative (FM-041) but `compute_crt_levels` (`gate_intelligence.py:24-84`) requires price-unit ATR. Root cause was a missing ontology node (absolute ATR had no first-class id, computed twice under 3 local names) — registered **FM-074 `atr_absolute`**, re-pointed FM-028/FM-050 at it, fixed the 2 live sites (`execution_planner.py`, `model_runners/adapters/execution_plan.py`) to derive `atr*close`; new `feature_math_lint.py` guard watch-lists `compute_crt_levels(atr=...)` against recurrence. `live_engine_hook.py:916` deliberately left unfixed (pinned `DM-001`) — dead code, scoped with the parked F-073 live-rail decision, not fixed mechanically. Freeze-pin waived (byte-identical XAUUSD vector); 46/46+55/55 planner tests incl. a new magnitude regression assertion. Authority: architecture/governance only | Certain |
| F-073 | ARCH | There is no live execution rail: `HookedLiveEngine` (`live_engine_hook.py:688`) is never instantiated anywhere in the repo; its one would-be caller (`agent/modes/pipeline_mode.py:160`) imports a class name (`LiveEngineHook`) that does not exist, and the `ImportError` is swallowed. `src/execution/loop.py`'s `ExecutionLoop` is a third, unrelated, test-only skeleton (already logged as orphaned, F-013). "Live vs backtest equivalence" is not currently a measurable question — only backtest is runnable. OPEN — resolving is a fork (repair the entry point + F-072's ATR fix, vs. formally retire the live rail) needing explicit authorization. Authority: architecture only | Certain |

### Closure & Authority Index (thin, always-loaded)

> **Machine-readable registry (authoritative for index shape + status tokens):**
> [`docs/governance/closure_authority_index.json`](docs/governance/closure_authority_index.json)
> — enforced by `tests/test_closure_authority_index.py`. Detailed proof stays in each surface's
> authoritative artifact; this index is navigation only.

**Invariant:** `CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE.`

A CLOSED upstream subsystem does **not** make a downstream join, query surface, model, artifact,
or decision path CLOSED. Only the named authoritative closure artifact establishes closure for
the declared boundary.

**Distinctions (non-optional):**
`AUDITED != CLOSED` · `LINEAGE CLOSED != ECONOMICALLY VALIDATED` · `UPSTREAM CLOSED != DOWNSTREAM CLOSED`

**Reopen policy (CLOSED surfaces only):** reopen only when (1) governed code/config/artifact
dependencies inside the declared boundary change; (2) a closure invariant or mechanical check
fails; (3) new contradictory evidence invalidates the closure claim; or (4) the authoritative
closure artifact defines an explicit revalidation condition that fires. Residual non-blockers
listed in an artifact do **not** reopen closure.

| Surface | Status | Scope (boundary) | Authoritative artifact | Frozen? | Reopen |
|---|---|---|---|---|---|
| CRT | **CLOSED** | OHLCV → CRT `TRADE_OPENED` only | [`docs/governance/crt_closure_report.md`](docs/governance/crt_closure_report.md) | yes | default closed policy |
| Geometry static lineage (Gate 5) | **COMPLETE** | Static geometry derivation-site lineage packaging (≠ domain CLOSED) | [`docs/governance/geometry_static_lineage_report.md`](docs/governance/geometry_static_lineage_report.md) | no | not CLOSED — advancement |
| Canonical Feature Code Surface | **CLOSED** | 38-dim code surface (formula/PIT/write-sites); **not** economic artifact admissibility | [`docs/governance/canonical_feature_code_surface_closure-2026-07-11.md`](docs/governance/canonical_feature_code_surface_closure-2026-07-11.md) | yes | default closed policy |
| Feature layer mutation freeze | **COMPLETE** | Mutation freeze + vector regression pin after 2026-07-18/19 queue; **not** L6 / not `FEATURE_PROGRAM_CLOSED` | [`docs/governance/feature-layer-mutation-freeze-2026-07-20.md`](docs/governance/feature-layer-mutation-freeze-2026-07-20.md) | yes | accepted future programs only |
| Feature Query Surface | **AUTHORITY_ACTIVE** | Read-only join API over existing artifacts (`feature_surface_query.py`) | [`scripts/governance/feature_surface_query.py`](scripts/governance/feature_surface_query.py) | no | not CLOSED — tooling |
| Gaussian lineage | **AUDITED** | Dual-track heuristic/ML observational audit; NO retrain/promote authority | [`docs/governance/gaussian_lineage_audit.md`](docs/governance/gaussian_lineage_audit.md) | no | AUDITED ≠ CLOSED |
| ZoneGate lineage | **AUDITED** | Active geometric HARD gate + no marginal value (F-036/F-041B); PIT_UNCLEAN economic | [`docs/governance/zonegate_lineage_audit.md`](docs/governance/zonegate_lineage_audit.md) | no | AUDITED ≠ CLOSED |
| RR lineage | **AUDITED** | Three contracts (polarity / rr_fusion inert / F-048 mismatch **RESOLVED 2026-07-24** — gate removed, economics owned by UltronRiskGate); not remediated re: rr_fusion | [`docs/governance/rr_lineage_audit.md`](docs/governance/rr_lineage_audit.md) | no | AUDITED ≠ CLOSED |
| BitNet lineage | **AUDITED** | INERT + conditional skew; `use_bitnet=false` on active patch | [`docs/governance/bitnet_lineage_audit.md`](docs/governance/bitnet_lineage_audit.md) | no | AUDITED ≠ CLOSED |
| TradeNet lineage | **AUDITED** | INERT / UNWIRED fusion neural slot (F-005); wire-up only via `TN_QUAL_V1` | [`docs/governance/tradenet_lineage_audit.md`](docs/governance/tradenet_lineage_audit.md) · [`tradenet_qualification_protocol.md`](docs/governance/tradenet_qualification_protocol.md) | no | AUDITED ≠ CLOSED |
| Research Measurement Contract | **OPEN** | Whether any research claim carries measurement-contract admissibility; schema+registry+3 profiles exist, 0 sealed `MC-*` instances, 0/27 probes implemented, all profiles `DRAFT` | [`docs/governance/MEASUREMENT_CONTRACT.md`](docs/governance/MEASUREMENT_CONTRACT.md) | no | advances only on a real E-MT-00+E-MT-01 pass |

Related (not in this index's minimum set; see its own program): OHLCV layer audit is
**BLOCKED** in [`docs/governance/layer-audit-manifest.json`](docs/governance/layer-audit-manifest.json)
— a separate layer program, not implied by CRT/feature CLOSED.

---

## 6.3 Citation Sync Mandate (non-optional)

When you move or rename code that a doc cites with a `path:line · Symbol` reference, update the
citation in the **same turn**. Find affected citations via
[`docs/architecture/citation-map.generated.md`](docs/architecture/citation-map.generated.md). Drift
is enforced by `tests/test_doc_citations.py` (±30-line window). This is the enforcement contract
behind the `Audit` / `Sync` triggers (§12).

---

## 6.4 Topic Sync Mandate (non-optional)

[`docs/topics/`](docs/topics/readme.md) is the concept↔code↔tests↔validations index — one
human-language file per concept. When you change code a topic covers, update **only that one**
topic doc the same response: surgical edit, bump `Updated:`, append a dated entry to its
Discussion block. Promote a stub from [`docs/topics/_template.md`](docs/topics/_template.md).
Enforced by `tests/test_topic_docs.py`. This is the home of the `Sync` Tier-2 trigger (§12).

---

## 6.5 Config-First Doctrine (non-optional)

> Complements §6.2. Target end-state: **Frozen Engine + Mutable Behavior + Governed Evolution** —
> code changes rare, config changes routine, goal-seeking by *generating configs*, not rewriting
> engines. Long-form + per-migration evidence log:
> [`docs/research-readiness/config-first-doctrine.md`](docs/research-readiness/config-first-doctrine.md).

**Evidence outranks doctrine (the meta-rule that produced this section).** Freeze a doctrine only
*after* implementation → parity proof → census verification → determinism proof. **Never** reverse
the order (no Doctrine → Hope → Reality). This §6.5 was frozen only once Batch A (4 live-spine
migrations) was proven byte-identical and the census gate was green — not before.

**Precedence hierarchy (why this effort worked):**
`Evidence > Doctrine > Preference > Convenience > Elegance`. Three corollaries:
**Evidence quality outranks migration quantity** (a sharper instrument beats more migrations);
**never optimize using a measurement instrument known to be biased** (fix the census blind spot
before ranking on its output); and **correcting the instrument often creates more value than
optimizing the system** — repairing the census (Phase 3) shrank the backlog 45→7 and reframed
"Batch C" from 30-knob surgery to a hash-neutral 12-field config-completeness pass, more than any
single migration did.

**Classify every constant before touching it:**

| Class | Examples | Action |
|---|---|---|
| **STRUCTURAL** | interfaces, dataclass fields, enum members, `VALID_TRANSITIONS`, execution order, array/vector dims, ATR/EMA *kernel* periods | **Frozen** — leave in code; changing it is expensive. |
| **BEHAVIORAL** | thresholds, percentiles, clamps, penalties, weights, multipliers, accept-rate bands, tier boundaries, quotas | **Externalize** to a config section. |
| **GOAL-SEEKING** | candidate-config generation, sweeps, optimization, promotion | Behavior is *generated as config*; the engine is untouched. |

> **EXCEPTION (2026-07-18, feature-pipeline indicator periods).** RSI/ATR/MA/Bollinger/MACD/EMA
> rolling-window and EMA-span PERIOD NUMBERS in `src/features/feature_pipeline.py`
> (`compute_indicators`, `compute_trend_features`, `compute_canonical_ema_features`) are
> reclassified BEHAVIORAL — config-driven via `configs/production/*.json` → `feature_pipeline`
> (`rsi_period`, `atr_period`, `ma_periods`, `bb_period`/`bb_std`, `macd_fast`/`macd_slow`/
> `macd_signal`, `trend_strength_window`, `ema_fast_span`, `ema_slow_span`), strict `_require()`,
> no silent defaults. Rationale: (a) closed a live silent-drift risk — `crt_engine.ema_fast`/
> `ema_slow` (2/5, soft-confirmation EMA) and this pipeline's `ema_fast`/`ema_slow` (9/21, the
> BitNet 38-dim feature-vector EMA) shared bare names across unrelated modules with no
> registered single source; (b) enables period sweeps as a research capability. **Scope is
> strictly limited to rolling-window/span period numbers.** It does **not** extend to the
> geometric primitives (`body_size`/`wick_size`/`body_ratio`/`candle_body`/`upper_wick`/
> `lower_wick`) — those remain STRUCTURAL/immutable per `candle_math.py`'s own doctrine (fixed
> identities like `area = pi*r*r`; there is no period to tune). Parity-proven: config values
> equal the prior hardcoded literals byte-for-byte; migration verified to produce an identical
> 38-dim vector on the XAUUSD corpus before/after. `market_ontology.yaml` `rolling_indicators`
> entries for `rsi_14`/`atr`/`ema_fast`/`ema_slow` (FM-042/041/043/044) now carry a `config_key`
> field naming the live source.

**Maturity ladder (the direction of travel for every BEHAVIORAL knob):**
`HARD_CODED → CONFIG_WIRED → CONFIG_DRIVEN`. Goal-seeking is **orthogonal**, layered on top
(`CONFIG_DRIVEN → GOAL_SEEKING`) — a knob *may* graduate to automated search, but **not every
module must become a tuner** (avoid optimization theater / config-entropy explosion).

**Hard rule — NO silent config defaults (the A1 lesson; closes the F-018 split-brain class):**
- New behavioral knobs are introduced through strict `_require()` / `from_prod_config()`
  boundaries. **A missing key/section is an error** (raise) — never `get_prod_section(...).get(key,
  literal)`. The soft-default form is **deprecated for new migrations**.
- **Parity proof = JSON value == prior literal · + · strict read · + · byte-identical ledger**
  (BNBUSDT + SOLUSDT). A migration that changes the ledger means a wrong JSON default, caught by
  the determinism gate.
- `params`-block edits change the config hash → require `python scripts/maintenance/_compute_hash.py`;
  new top-level sections are hash-neutral.

**Six questions before writing engine code:** can this be (1) configuration, (2) data, (3) a
plugin, (4) an interpreter, (5) a strategy module, (6) a policy? If YES → expose it through config;
do **not** branch the engine.

**Enforcement contract:** `scripts/analysis/behavior_census.py` (AST classifier + per-module
maturity) ↔ `tests/test_behavior_census.py` (pins the migrated modules' maturity so behavior cannot
silently drift back into code). Sibling of `config_reachability.py`. Known-remaining work: the
**CRTConfig `params` split-brain** (~30 knobs) — the next batch, gated on a rehash; perform it
*under* this doctrine.

**Authority Ladder (anti-self-deception).** Generalizes beyond config — ties to §6.1
(intelligence-compounding) and the G001 / Interpreter-Contract program (Goal Layer). **Permanent
invariant: evidence has no authority; only demonstrated G001 improvement grants authority.** Four
*distinct* states (a ladder, not synonyms):

| Level | Meaning |
|---|---|
| Information exists | phenomenon detected |
| Economic usefulness exists | measurable ΔG001 benefit |
| Authority earned | allowed to influence production |
| Architecture justified | allowed to increase complexity |

Corollaries: **Information ≠ value** (statistically detectable may be economically worthless) ·
**Value ≠ authority** (a useful signal does not auto-earn fusion / production weight) ·
**Authority ≠ architecture** (even a successful consumer does not auto-justify more complexity).
Enforcement: a `REGIME_EXPLOITABLE`-type finding = *information* → may justify docs / research /
shadow measurement; may **not** justify sizing / fusion / production authority. Only a
`CONSUMER_CANDIDATE` *with measured ΔG001* may justify fusion / authority / production weight — and
even then not new architecture. **Config-first tie-in:** a knob becoming `CONFIG_DRIVEN` grants
*tunability*, never *authority* (authority is earned only by demonstrated G001 improvement). This is
the F-019…F-028 falsification discipline in one rule.

---

## 6.6 Canonical Market Ontology Evolution Contract (non-optional)

> Adopted 2026-07-25. Full charter: [`docs/governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`](docs/governance/MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md).
> Machine-readable authority: `configs/formulas/market_ontology.yaml` `spec_schema.semantic_registry`.
> Enforced by `tests/test_semantic_registry.py` (`features.registry.validate_semantic_registry`).

The market ontology is the **permanent semantic authority** — authority **#1**, first-mover (user
decision: *literal supersession*; runtime/models and the historical §4.0/§6.5 precedence derive
from it for MEANING). Every market concept (feature/formula/state/transition/pattern/regime/
context/zone/geometry/liquidity·volatility·execution·risk behaviour/model I/O/validation rule/
invariant) must exist as a canonical node with full lineage. Discovered-but-undefined behaviour
becomes an explicit `UNKNOWN_*` node the same turn — **never a TODO or a comment** — with `evidence`
+ `origin` filled and a contamination caveat when the source is a single run / shadow path.

**Two mechanical constraints (physical, not overridable — keep supremacy coherent):** (1) frozen
runtime keys (`primitives`/`feature_compositions`/`derived_metrics`, read by `crt_engine_v2` at
import) stay FLAT + additive; new node types live in non-frozen sibling sections. (2) An ontology
change that alters PRODUCTION behaviour still cascades through parity-proof + the promotion gate —
"ontology first" governs the ORIGIN/REQUIREMENT of a change, not automatic unvalidated runtime
mutation (preserves §4.0 anti-split-brain + §6.5 earned-authority).

**Refinement ladder** (knowledge axis, distinct from execution `lifecycle`): `UNKNOWN → OBSERVED →
CHARACTERIZED → MATHEMATICALLY_DEFINED → FORMULA_DERIVED → VALIDATED → PRODUCTION_CERTIFIED →
STABLE`. Nodes refine IN PLACE (identity fixed, no duplicates). `PRODUCTION_CERTIFIED` is earned
only by measured G001 (§6.5) — evidence never auto-grants authority. **Epistemic discipline
(mandatory for UNKNOWN, encouraged for OBSERVED/CHARACTERIZED):** a research-stage node keeps
epistemic levels DISTINCT in an `epistemic` block — `known_invariants` (validated facts) /
`unknown_mechanism` (the one open question) / `candidate_hypotheses` (untested, never truth) /
`resolution_metric` (how it's answered) / `falsification_conditions` (what would disprove it);
`observation`=`observed_behaviour`. Never let a hypothesis become a fact by repetition; state
ruled-out invariants factually ("current evidence indicates X is not explained by the previously
identified defect Y", not "X is not an artifact"). **Automatic Semantic
Discovery ritual:** every investigation searches for undefined/duplicate/hidden semantics + missing
formulas/transitions/consumers/producers/invariants → each becomes a canonical node. Never force a
new behaviour into an existing node; if evidence is insufficient, create a new (or UNKNOWN) node and
refine. **Never fabricate** a value the evidence does not support.

---

## 7. Response Ritual — On Every "continue" or User Message

### 7.1 ORIENT (token-efficient)
Briefly state what you understand is in scope. One sentence. No fluff.

### 7.2 PROBE (proactive discussion)
Ask 1–2 sharp clarifying questions BEFORE proceeding if ambiguity exists:
- What's the impact radius of this change? (check `.dot` graph)
- Which callers/dependents are affected?
- Is this a new abstraction or extending existing?

### 7.3 IMPLEMENT / DISCUSS
Provide your response. Be concrete. Reference actual node names from the `.dot` file when discussing flow.

### 7.4 SELF-DOCUMENT (append to session log)
End EVERY response with this block:

```
---
📝 SESSION LOG ENTRY
Date: {timestamp}
Topic: {1-line summary}
Decision/Output: {key content or code produced}
Belief Update / ROI / Goal: {Goal: …  Belief: …  Knowledge ROI: …  Action: …}  # "none" if pure mechanics
Open Questions: {any unresolved items}
Next Step: {what should happen next}
---
```

The `Belief Update / ROI / Goal` field operationalizes §6.1 — it is where intelligence
compounds. It forces every turn through Goal → Belief → ROI → next Action. Example:

```
Belief Update / ROI / Goal:
  Goal: increase probability of finding profitable BNB improvements.
  Belief: EMA gate is non-binding.
  Knowledge ROI: high.
  Action: stop exploring EMA; redirect to the session bottleneck.
```

*Optional:* you may append a `**Metrics**` self-report block to an entry — see
[`docs/architecture/intelligence-compounding.md`](docs/architecture/intelligence-compounding.md)
("Metrics Block"). It is self-report only, carries **no authority**, and is **not** required.

---

## 8. Token Control Rules

- No re-explaining context already in the session log.
- No padding, no preamble ("Great question!").
- Compress code with comments over verbose prose.
- If a concept was covered in a prior log entry → reference it by entry, don't repeat.
- Max prose per turn: explain the WHY briefly, let code carry the WHAT.

## 9. LLM Capabilities Preserved

- Full reasoning chains allowed.
- Creative architectural suggestions encouraged.
- Contradicting the user is allowed if the `.dot` graph (or `docs/*.md`) shows a conflict.
- Hypothetical / tradeoff analysis fully permitted.

## 10. Codebase Flow Reference

When referencing code flow, cite nodes from the `.dot` file like:

> `EngineRunner → FusionEngine.evaluate → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate.evaluate` (per dependency graph)

This keeps discussion grounded and skips re-explaining structure.

---

## 11. Completed Enhancements (ENHANCEMENT_IMPLEMENTATION_PLAN.md — 2026-04-12)

### Phase 0 — Baseline & Safety Net
- `results/baseline/` directory created.
- `src/runtime/baseline_capture.py` captures schema hash, model registry state, production config SHA-256 and validation metrics into a timestamped manifest.
- **Run:** `python src/runtime/baseline_capture.py --label phase0`

### Phase 1 — Runtime Correctness
- **`config_validator.py`** fully implemented (`ConfigValidator` class).
  - `validate(params, csv_paths, config_id)` runs per-instrument backtest via `BacktestRunner`, computes fitness score, applies hard+soft quality gates, returns structured `ValidationReport`.
  - Hard gates: min trade count (10), max drawdown (35%), min fitness score (0.15).
  - Soft gates: win rate < 35%, expectancy < -0.5R, high cross-instrument variance.
  - **CLI:** `python config_validator.py validate-prod --data-dir data/`
- `promotion_manager.py` already wired to `ConfigValidator.validate()` — unblocked.
- `live_engine_hook.py` already implements `EngineRunner` API contract with correct session normalization, drift detection, and `UltronRiskGate` integration.

### Phase 2 — Integration Hardening
- **`FeatureMonitor` wired into `BacktestRunner`** (`runtime/backtest_v2.py`):
  - Initialized in `__init__` (window=500).
  - Updated on every `TRADE_OPENED` event using `retest_depth`, `body_ratio`, `disp_strength`.
  - HARD drift (Z>3.0) → `WARNING` log; soft drift (Z>2.5) → `DEBUG` log.
  - Drift stats attached to `BacktestMetrics.distribution["feature_drift"]` in final output.
- `FusionEngine.evaluate()` path already behind `fusion_use_evaluate` feature flag in production config.
- `llm_inference_client.py` already implements timeout/fallback controls (`fail_count_disable=10`, `request_timeout=2.0s`, returns 1.0 on failure).

### Phase 3 — Data & Model Quality
- `rr_dataset_builder.py` implements canonical RR label extraction with 3-level priority (rr_achieved → pnl_rr_net → computed).
- `model_registry.py` enforces GOV-3 atomic promotion + `PROMOTION_MARGIN=2%` quality gate.
- `train_pipeline.py` implements Phase-5 calibration gate before registration.
- `dataset_validator.py` enforces hard min-sample thresholds, label entropy, class balance.

### Phase 4 — Decision Surface & Actionability
- `execution_planner.py` (`ExecutionPlannerV1_2`) derives entry/SL/TP/RR/TTL from accepted signals.
- Intent-specific TP multipliers and TTLs are configurable via `configs/production/*.json`.
- Conservative/standard/aggressive profiles expressible via `min_rr_ratio`, `default_sl_atr_mult`, `risk_percent`.
- `EngineRunner` remains scoring/filter authority; planner only consumes decision outputs.

### Phase 5 — Governance & Rollout
- `promotion_manager.py` enforces: approved `ValidationReport` required, SHA-256 config hash, score_std_dev tracked, immutable changelog via `promotion_log.jsonl`.
- `ConfigValidator.validate()` is the mandatory pre-promotion gate (hard + soft quality gates).
- Rollback: restore archived `configs/production/{version}_archived_{ts}.json` and update `PROD_VERSION`.
- **Promote:** `python promotion_manager.py promote --checkpoint results/tuner/checkpoint_multi.json --version v2_... --data-dir data/`

---

## 12. Trigger Vocabulary (LLM ownership commands)

Single-word commands that let a session **own** this codebase — self-navigate, advance
the migration, validate, and implement — without re-deriving context each turn. Full
spec (action · docs loaded · exit condition · compositions) in
[`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md).

**Cold start:** a fresh session runs `Orient` first — see the Cold-start recipe at the top
of [`TRIGGER_VOCABULARY.md`](docs/architecture/trigger-vocabulary.md).

**Tier 1 — execution:**
- **Continue** — resume the active work from where it left off (reads latest `docs/implementation_plan/*.md` + SESSION LOG + `MEMORY.md`).
- **Next step** — do the next discrete step *within* the current milestone.
- **Next plan** — `Validate` the current milestone, then enter the next M0–M5 milestone (or draft a new plan).
- **Validate** — run the verification gate (`pytest` per `docs/reference/testing.md` + determinism/replay check + Five Questions). **Read-only.**
- **Implement** — turn the approved plan into surgical additive code per §3, then auto-`Validate`.

**Tier 2 — ownership / navigation:**
- **Orient** / **Status** — one-screen state report (plan + SESSION LOG + `MEMORY.md`). **Read-only.**
- **Map** — load architecture context to locate where a change lands (`docs/architecture/codebase-state-map.md`, `service-boundary-map.md`, `event-taxonomy.md`, `docs/architecture/signal-flow.md`). **Read-only.**
- **Audit** — re-verify each architecture doc's `file:line` citations vs code; additive doc-only fixes.
- **Plan** — enter plan mode → Explore → design → write `docs/implementation_plan/` → `ExitPlanMode`.
- **Log** — append the `📝 SESSION LOG ENTRY` block (the §6 mandate, named explicitly).
- **Compile** — regenerate the multi-LLM Portable Mind (`python scripts/context/build_context.py` → `context/*.md`). Derived views only; **read-only** re: the repo. See §13.

**Doctrine (all four enforced):** triggers are advisory orchestration and grant **no new
authority** (never bypass write-authority / path-guard / `y/N` confirm / `APPROVE`
promotion gate); every trigger ends with the §6 SESSION LOG; every state-changing trigger
is scored against the Five Governance Questions; triggers compose (`Continue` = `Orient →
Map → Next step → Validate → Log`). The governance superset (`Promote` / `Baseline` /
`Rehash` / `Rollback`) is referenced, not redefined — see `docs/reference/governance.md`.

---

## 13. Multi-LLM Coordination Layer (`multi_llm/` + `ChatGpt workflow/`)

> Thin pointer — full spec lives in [`multi_llm/README.md`](multi_llm/README.md) and
> [`multi_llm/MULTI_LLM_PROTOCOL.md`](multi_llm/MULTI_LLM_PROTOCOL.md). Extended protocol details,
> agent role cards, and the GATHER/ENHANCE/IMPLEMENT phase framework live in
> [`ChatGpt workflow/`](ChatGpt%20workflow/) (the Jarvis prompt framework, adapted below).
> Visualizer: [`ChatGpt workflow/index.html`](ChatGpt%20workflow/index.html).
>
> Six hand-operated models (DeepSeek=Planner · Gemini Think=Quant Analyst · Gemini Pro=Optimizer ·
> ChatGPT=Interpreter/Architect · Claude=Executor · Grok-2=Synthesizer), coordinated by the
> **User=Bridge/Decider** ([`multi_llm/roles/ROLE_USER.md`](multi_llm/roles/ROLE_USER.md)
> — the principal who sets the goal, moves context, and approves), share one reality instead of
> drifting into six. **Grants no new authority**
> (extends §6.5 Authority Ladder + §4.0 precedence; never bypasses the §6 SESSION LOG,
> write-authority, path-guard, `y/N`, or `APPROVE` gates).

### 13.1 The Pipeline (merged from CLAUDE.md §13 + ChatGpt workflow docs)

```
👤 User (Bridge & Principal Decider)
  │  goal + context/*.md + story pack (copy-paste)
  ▼
🔴 DeepSeek — Planner (first)
  │  decomposes story → plan + §3 prompt for next model
  ▼
🔵 Gemini Think — Quant Analyst
  │  mathematical reasoning, statistical tests, CRT validation
  │  "Never optimises code"
  ▼
🟢 Gemini Pro — Optimizer
  │  converts analysis into efficient algorithms/code
  │  "Never re-derives mathematics"
  ▼
🧠 ChatGPT — Interpreter / Architect
  │  explains, creates JSON task plan, expands parameters
  │  "Never executes tasks"
  ▼
🟣 Claude — Executor
  │  writes code, runs Validate, SESSION LOG
  │  "Never adds unsolicited explanations"
  ▼
🟡 Reality — Tests + Findings
  │  VALIDATED / REFUTED / INCONCLUSIVE
  ▼
𐃘 Grok-2 (xAI) — Synthesizer
  │  combines all outputs + findings into final answer
  │  separate chat tab, new addition
  ▼
👤 User decides — approve, reject, or loop
```

Each arrow represents the **User copy-pasting** the §3 handoff block (`PROMPT_FOR_NEXT_MODEL`) from one model's chat window into the next. No model calls another directly.

### 13.2 Agent Role Cards (system prompts + boundaries)

| Agent | Model | Role | Never Does | Input | Output |
|-------|-------|------|------------|-------|--------|
| 🔴 DeepSeek | DeepSeek | Planner | Writes new features | User goal + context/*.md | Plan + §3 handoff block |
| 🔵 Gemini Think | Gemini 2.0 | Quant Analyst | Optimises code | Analytical request from plan | Formulas, stats, edge-case flags |
| 🟢 Gemini Pro | Gemini Pro | Optimizer | Re-derives maths | Gemini Think's analysis | Optimised code/algorithms |
| 🧠 ChatGPT | GPT-4o | Interpreter/Architect | Executes tasks | Plan + context | JSON task plan + expanded params |
| 🟣 Claude | Claude Sonnet | Executor | Adds unsolicited explanations | Spec + context | Code diff + pytest tests + SESSION LOG |
| 𐃘 Grok-2 | xAI Grok-2 | Synthesizer | Ignores findings | All outputs + Reality | Synthesised final answer |

Full system prompts for each agent are available in [`ChatGpt workflow/index.html`](ChatGpt%20workflow/index.html) (click any agent card → "Copy System Prompt") and in [`ChatGpt workflow/OrchestartedPrompts/AGENT_ROLES.md`](ChatGpt%20workflow/OrchestartedPrompts/AGENT_ROLES.md).

### 13.3 GATHER / ENHANCE / IMPLEMENT Phase Framework

Every cycle follows this three-phase structure (from `ChatGpt workflow/Jarvis_Prompt_Framework.docx`):

**GATHER** (before touching code):
- **G-1 Clarifier** — map affected files, existing patterns, constraints. Output: JSON state object.
- **G-2 Pyan Analysis** — generate `.dot` call graph for large refactors.
- **G-3 Micro-Service Boundary Audit** — PASS/FAIL checklist for service boundaries.

**ENHANCE** (sharpen every prompt before sending):
- **E-1 Context Layer** — prepend architecture summary + conventions + constraints.
- **E-2 Output Format** — specify exact files, format, and what NOT to output.
- **E-3 Uncertainty Guard** — "If unsure, write `# UNKNOWN:` — never invent."
- **E-4 Role + Constraint Pairing** — open with agent identity + primary constraint.
- **E-5 Step-by-Step Trigger** — for complex logic, show reasoning before output.

**IMPLEMENT** (code generation chain):
- **I-1 SpecWriter** (ChatGPT) → **I-2 DiffGen** (Claude) ‖ **I-3 TestGen** (Claude, parallel with I-2)
- **I-4 Auditor** (DeepSeek) → **I-5 Line-by-Line Explanations** (Claude, optional)
- Post-implementation: CommitWriter → PRWriter → ChangelogWriter

### 13.4 Chain Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| PENDING | Task planned, no agent started | — |
| IN_PROGRESS | Agent working on this task | Wait for output |
| BLOCKED | Output contains `BLOCKED:` tags | Resolve before continuing |
| UNKNOWN | Output contains `UNKNOWN:` tags | Verify file/API before running |
| DONE | Auditor signed off | Ready to commit |
| NEEDS REVISION | Audit returned issues | Fix specific items, re-run affected steps |

### 13.5 State Object (per-cycle)

Every cycle maintains a state object (adapted from `Jarvis_Prompt_Framework.docx §5.1`):

```json
{
  "task": "current story description",
  "issue_id": "STORY-x.y",
  "existing_architecture_summary": {},
  "spec": "",              // from I-1 SpecWriter
  "diff": "",              // from I-2 DiffGen
  "tests": "",             // from I-3 TestGen
  "audit": {},             // from I-4 Auditor
  "chain_status": "pending | in_progress | blocked | done"
}
```

The authoritative state is stored in `multi_llm/turn_ledger.jsonl` + `HANDOFF.md`. The state JSON above is a working-memory convenience, not a source of truth.

### 13.6 Infrastructure & Tooling (unchanged)

- **Truth stays in the repo.** `context/*.md` (the *Portable Mind*) are **generated, gitignored
  derived views** — regenerate with the `Compile` trigger; never hand-edit. Edit the source
  (CLAUDE.md, `docs/current-findings.md`, the queue), then re-Compile.
- **One queue.** `multi_llm/build_queue.jsonl` is the single backlog feeding `NEXT_10_STEPS`.
- **Memory & transfer (no loss).** Every model turn is captured verbatim + indexed by
  `scripts/context/log_turn.py` → `multi_llm/turn_ledger.jsonl`. Rewind with
  `scripts/context/discussion.py --full|--rewind <turn>|--digest`. Transfer bounded context with
  `scripts/context/pack_story.py --story <id>`.
- **Two logs.** `assistant_project.md` = codebase log; `llm_project_assistant.md` = workflow log (§6).
- **Enforced by** `tests/test_context_compiler.py` + `tests/test_handoff_state.py`.

### 13.7 Claude-Side Handoff Mandate (non-optional)
In any session that **touches `multi_llm/` or advances `build_queue.jsonl`**, Claude's turn is
**incomplete** unless it (a) emits the protocol §3 handoff block (`CURRENT_TASK`, `NEXT_10_STEPS`,
`CONTEXT_DELTA`, `FOR_NEXT_MODEL`, `PROMPT_FOR_NEXT_MODEL`, `CONFIRMATION`) in its response, **and**
(b) leaves `HANDOFF.md` valid + consistent. The §3 block is the universal handoff unit across all
six models. Enforced floor: `tests/test_handoff_state.py`.

### 13.8 Code & Execution Authority (non-optional)
**Implementation is Claude's alone; advice is everyone's.** Claude is the sole actor that
writes/edits code and runs execution in this codebase — DeepSeek/Gemini/ChatGPT/Grok-2 may *propose*
code, diffs, or commands, but those are **inputs to Claude**, never applied directly.
**Advice, by contrast, is shared and bidirectional:** every model contributes **recommendations**
(non-binding). **No model's advice — including Claude's own — is authority**; it is a recommendation
the User weighs and the evidence settles.
This **grants Claude no new authority**: every change Claude makes still passes the §6 SESSION LOG,
write-authority/path-guard, the `y/N` confirm, the `APPROVE` promotion gate, and **User approval**
for irreversible / outward-facing actions. Reality / Tests / Findings still decide (§6.5 Authority Ladder).
