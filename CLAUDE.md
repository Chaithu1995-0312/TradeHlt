# CLAUDE.md — Master Context File

> **This is the file Claude reads first in every session.**
> It links the architecture + conventions + schemas + example service into one
> operating manual, and preserves the existing CodeBase Navigator ritual.

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
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)       | Tech stack with versions, full directory tree, end-to-end data flow, design patterns, external integrations (llama.cpp / Groq / BitNet GGUF), production-config section index, CLI entry points. |
| [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md)         | Naming rules (files / classes / constants / configs / JSONL), folder-placement table, the three error-handling modes (fail-fast / optional-import / fail-open), logging, import order, explicit anti-patterns. |
| [`docs/SCHEMAS.md`](docs/SCHEMAS.md)                 | Every dataclass (`Candle`, `Trade`, `BacktestConfig`, `RunRecord`, `CommandSpec`, `ToolStep`, `Plan`), enums (`CRTState`, `Direction`, `RejectReason`), the 35-dim `CANONICAL_FEATURES` schema, `ValidationReport` / `GateResult` / `ExecutionPlan` shapes, production-config top-level keys, JSONL line schemas, cross-object relationships. |
| [`docs/EXAMPLE_SERVICE.py`](docs/EXAMPLE_SERVICE.py) | Golden reference template demonstrating fail-fast config load, `_require` strict accessor, `from_prod_config` factory, named flow logger, optional-import guard, circuit-breaker, structured APPROVE/REJECT return shape, CLI wrapper, and module-registration checklist. Copy this when adding new engines / gates / validators. |
| [`docs/CONFIG_REFERENCE.md`](docs/CONFIG_REFERENCE.md) | Section-by-section reference for every key in `configs/production/v1_multi_2026_03.json`: `params`, `engine_runner`, `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`, `crt_engine`, `gaussian_scorer`, `rr_model`, `llama_gate`, `config_validator`, `governance`, `validation_summary`, `backtest`, `feature_monitor`, `tuner`, `training`, `portfolio`, `agent`, `inout`. Includes editing + rehashing rules. |
| [`docs/TESTING.md`](docs/TESTING.md) | pytest layout (51 files across 10 domains), how to run (whole / by domain / single), `pyproject.toml` test config, `conftest.py` role, coverage expectations per module, representative test patterns (assertion / invariant / parametrise / registry-exhaustiveness), conventions enforced by tests, guide for writing new tests, pre-promotion regression command. |
| [`docs/AGENT_REFERENCE.md`](docs/AGENT_REFERENCE.md) | Complete agent reference: 14 intents (pipeline / copilot / governance / cross-mode), 20 tools with args/write flags, deterministic `PLAN_REGISTRY` tables, `IntentRouter` regex+LLM classification flow, `PlanCompiler` API, `Executor` confirm-gate + path-guard, `AgentState`, audit log formats (`logs/agent_audit.jsonl`, `logs/agent_intent_log.jsonl`), agent config, REPL CLI, add-a-new-tool procedure. |
| [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) | End-to-end promotion workflow, `PromotionManager` API (`promote_from_report` / `promote_from_tuner_checkpoint` / `promote_direct` / `list_versions` / `load_version`), registry layout + archive naming, `configs/promotion_log.jsonl` line schemas (PROMOTED / PROMOTION_FAILED), `ShadowPromotionGate` two-gate flow, `MetaGovernorExecutor`, `PortfolioValidation`, rollback procedure, pre-promotion checklist, write-authority matrix. |
| [`docs/SIGNAL_FLOW.md`](docs/SIGNAL_FLOW.md) | End-to-end candle→order linear walk for the CRT spine (Steps 1–7) with module / entry-point / config / failure-mode per step, the four async kitchen feeders (Governance, Training, AI Agent, INOUT) and where each joins the spine, cross-reference matrix, Mermaid swim-lane diagram. |
| [`docs/architecture/TRIGGER_VOCABULARY.md`](docs/architecture/TRIGGER_VOCABULARY.md) | LLM trigger-word vocabulary for owning the codebase: `Continue` / `Next step` / `Next plan` / `Validate` / `Implement` (Tier 1) + `Orient`/`Status` / `Map` / `Audit` / `Plan` / `Log` (Tier 2). Per trigger: action · docs loaded · exit condition. See §12. |
| [`docs/architecture/GOAL.md`](docs/architecture/GOAL.md) | North-star goal document (plain language): purpose, the happy flow (candle→order), the 7 invariants + five governance questions, the deviation policy (throughput-improving deviations OK if invariants hold), migration target. The "what good looks like" baseline. |
| [`docs/CLI_MATRIX.md`](docs/CLI_MATRIX.md) | Auto-generated command catalog (from `control_plane/registry.py`): every CLI invocation, artifacts, suggested next step. Authoritative for "how do I run X." |

---

## 3. How to Work With This Codebase

### 3.1 Adding a new feature (canonical pattern)

1. **Place the module.** Pick the right subpackage from `CONVENTIONS.md §2`. Scoring engine → `src/engines/`; decision/risk logic → `src/core/`; validator → `src/config_layer/`; governance gate → `src/governance/`; live-mode code → `src/inout/`. Never put production logic in `scripts/`.
2. **Copy `docs/EXAMPLE_SERVICE.py`** into the chosen folder, rename, and keep its structure: `_load_*_cfg()`, `_require()`, dataclass with `from_prod_config`, named flow logger, public `PascalCase` class with typed methods, private `_snake_case` helpers.
3. **Add a new section to `configs/production/v1_multi_2026_03.json`** containing every tunable. No magic numbers in Python.
4. **Re-hash the config:** `python scripts/maintenance/_compute_hash.py`.
5. **Wire the module into its orchestrator.** Engine → add key to `core/engine_runner.EXPECTED_ENGINES`; validator → call from `PromotionManager` or `live_engine_hook`; risk check → extend `UltronRiskGate.evaluate()`.
6. **Write pytest tests** in `tests/`. Cover the APPROVE path, every hard-failure branch, the circuit-breaker open path (if external I/O), and the optional-dep absent path.
7. **Promote** with `python src/governance/promotion_manager.py promote --checkpoint results/tuner/checkpoint_multi.json --version v2_<label>_<YYYY_MM> --data-dir data/`. Promotion fails unless `ValidationReport.decision == "APPROVE"`.

### 3.2 Adding a new "DB model" (really: dataclass / config section)

This codebase has no ORM. "Models" are one of:

- **Value object** → `@dataclass` in the owning subpackage. Provide `from_prod_config(cls, cfg: dict) -> "Self"` if any field is config-driven.
- **Enum** → `class X(Enum):` with `SCREAMING_SNAKE_CASE` members. See `CRTState`, `Direction`, `RejectReason` in `src/config_layer/crt_engine_v2.py`.
- **Config section** → new top-level key in `configs/production/v1_multi_2026_03.json`, consumed via `get_prod_section("<name>")`. Register the required keys in a `_require` helper at module load (fail-fast).
- **JSONL event line** → self-contained `dict` with `timestamp` + `kind`; append only. Document the shape in `docs/SCHEMAS.md §9`.

### 3.3 Adding a new "API endpoint"

There is **no REST API**. The three surfaces that accept external input are:

| Surface                    | How to add                                                                         |
| -------------------------- | ---------------------------------------------------------------------------------- |
| **CLI entry point**        | New script in `scripts/<category>/` that imports from `src/` and uses `argparse`. Never define business logic in the script — it must be a thin wrapper. |
| **Control-plane command**  | Register a `CommandSpec` in `src/control_plane/registry.py` (name / category / argv template / params). The HTTP UI at `localhost:8787` picks it up automatically via `ControlPlaneAPI.commands_payload()`. |
| **Agent tool**             | Add to `src/agent/tool_registry.py` (name, args schema, handler). Add the intent → tool sequence to `PLAN_REGISTRY` in `src/agent/plan_compiler.py`. Deterministic by design — do not route planning through the LLM. |

### 3.4 Key files to always check before making changes

Before touching any code, read these in order:

1. `CLAUDE.md` (this file)
2. `configs/production/v1_multi_2026_03.json` — the single source of truth for every tunable
3. `docs/ARCHITECTURE.md` §3 (data flow) — know which layer you are modifying
4. `src/core/engine_runner.py` — the orchestrator that every decision path passes through
5. `src/config_layer/config_validator.py` — defines what "valid" means for a config
6. `src/governance/promotion_manager.py` — the only path to production
7. `assistant_project.md` — check recent session-log entries before re-opening resolved threads
8. If available at `graph.dot` / pyan output — the live dependency graph (`scripts/analysis/gen_pyan.py`). Cite nodes when discussing flow: `ModuleA → FunctionB → ClassC` (per dependency graph).

---

## 4. Current Known Constraints & Limitations

- **Python `>=3.10` only.** `pyproject.toml` pins it; CI will not cover earlier versions.
- **Single production config version is active at a time.** Archived versions are preserved as `{version}_archived_{ts}.json` but are not hot-swappable — rollback requires restoring and re-loading.
- **Four engines are mandatory.** `EXPECTED_ENGINES = {"crt", "gaussian", "zone_gate", "rr"}`. Removing one without updating the completeness check will produce silent partial fusion.
- **No lookahead is allowed in backtests.** `BacktestRunner` streams candle-by-candle; feature builders that peek ahead will break determinism and must be rejected in review.
- **LLM is a tie-breaker, not a hot-path dependency.** `llm_inference_client` returns neutral `1.0` after `fail_count_disable` failures. Any code path that cannot tolerate that fallback is broken by design.
- **Windows console encoding.** Non-ASCII output must go through `src/utils/console_safe.py` (cp1252 fallback). Direct `print` of arbitrary strings in CLI entry points risks `UnicodeEncodeError`.
- **Control plane is localhost-only.** No auth layer, no TLS — do not expose `localhost:8787` externally.
- **Schema hash is load-bearing.** Any change to `CANONICAL_FEATURES` or `FEATURE_SCHEMA` invalidates the baseline and requires `python src/runtime/baseline_capture.py --label <new>` before training.
- **`CRTState` transitions are not a free graph.** The legal map is **9 states** (golden path `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`, plus the `SHADOW_PENDING` branch `RANGE ↔ SHADOW_PENDING → SWEEP` (Phase 1) and the `EXPIRED` TTL branch `EXPANSION → EXPIRED → RANGE` (Phase 3b soft-archive)). Authoritative: `VALID_TRANSITIONS` (`crt_engine_v2.py:981`) / `EVENT_TAXONOMY.md §3`.
- **No database.** Any request to "add a table" or "use the ORM" is a convention break — consult `docs/SCHEMAS.md §1` before proposing alternatives.

---

## 5. Preferred Response Style (when helping with this codebase)

- **Follow existing patterns, never introduce new ones.** If a pattern is not already in `docs/CONVENTIONS.md` or in `docs/EXAMPLE_SERVICE.py`, do not invent — ask.
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
Open Questions: {any unresolved items}
Next Step: {what should happen next}
---
```

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
[`docs/architecture/TRIGGER_VOCABULARY.md`](docs/architecture/TRIGGER_VOCABULARY.md).

**Cold start:** a fresh session runs `Orient` first — see the Cold-start recipe at the top
of [`TRIGGER_VOCABULARY.md`](docs/architecture/TRIGGER_VOCABULARY.md).

**Tier 1 — execution:**
- **Continue** — resume the active work from where it left off (reads latest `docs/implementation_plan/*.md` + SESSION LOG + `MEMORY.md`).
- **Next step** — do the next discrete step *within* the current milestone.
- **Next plan** — `Validate` the current milestone, then enter the next M0–M5 milestone (or draft a new plan).
- **Validate** — run the verification gate (`pytest` per `docs/TESTING.md` + determinism/replay check + Five Questions). **Read-only.**
- **Implement** — turn the approved plan into surgical additive code per §3, then auto-`Validate`.

**Tier 2 — ownership / navigation:**
- **Orient** / **Status** — one-screen state report (plan + SESSION LOG + `MEMORY.md`). **Read-only.**
- **Map** — load architecture context to locate where a change lands (`docs/architecture/CODEBASE_STATE_MAP.md`, `SERVICE_BOUNDARY_MAP.md`, `EVENT_TAXONOMY.md`, `docs/SIGNAL_FLOW.md`). **Read-only.**
- **Audit** — re-verify each architecture doc's `file:line` citations vs code; additive doc-only fixes.
- **Plan** — enter plan mode → Explore → design → write `docs/implementation_plan/` → `ExitPlanMode`.
- **Log** — append the `📝 SESSION LOG ENTRY` block (the §6 mandate, named explicitly).

**Doctrine (all four enforced):** triggers are advisory orchestration and grant **no new
authority** (never bypass write-authority / path-guard / `y/N` confirm / `APPROVE`
promotion gate); every trigger ends with the §6 SESSION LOG; every state-changing trigger
is scored against the Five Governance Questions; triggers compose (`Continue` = `Orient →
Map → Next step → Validate → Log`). The governance superset (`Promote` / `Baseline` /
`Rehash` / `Rollback`) is referenced, not redefined — see `docs/GOVERNANCE.md`.
