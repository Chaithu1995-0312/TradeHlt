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
| [`docs/reference/architecture.md`](docs/reference/architecture.md)       | Tech stack with versions, full directory tree, end-to-end data flow, design patterns, external integrations (llama.cpp / Groq / BitNet GGUF), production-config section index, CLI entry points. |
| [`docs/reference/conventions.md`](docs/reference/conventions.md)         | Naming rules (files / classes / constants / configs / JSONL), folder-placement table, the three error-handling modes (fail-fast / optional-import / fail-open), logging, import order, explicit anti-patterns. |
| [`docs/reference/schemas.md`](docs/reference/schemas.md)                 | Every dataclass (`Candle`, `Trade`, `BacktestConfig`, `RunRecord`, `CommandSpec`, `ToolStep`, `Plan`), enums (`CRTState`, `Direction`, `RejectReason`), the 38-dim `CANONICAL_FEATURES` schema, `ValidationReport` / `GateResult` / `ExecutionPlan` shapes, production-config top-level keys, JSONL line schemas, cross-object relationships. |
| [`docs/reference/example-service.py`](docs/reference/example-service.py) | Golden reference template demonstrating fail-fast config load, `_require` strict accessor, `from_prod_config` factory, named flow logger, optional-import guard, circuit-breaker, structured APPROVE/REJECT return shape, CLI wrapper, and module-registration checklist. Copy this when adding new engines / gates / validators. |
| [`docs/reference/config-reference.md`](docs/reference/config-reference.md) | Section-by-section reference for every key in `configs/production/v1_multi_2026_03.json`: `params`, `engine_runner`, `fusion_engine`, `decision_engine`, `execution_planner`, `ultron_risk_gate`, `crt_engine`, `gaussian_scorer`, `rr_model`, `llama_gate`, `config_validator`, `governance`, `validation_summary`, `backtest`, `feature_monitor`, `tuner`, `training`, `portfolio`, `agent`, `inout`. Includes editing + rehashing rules. |
| [`docs/reference/testing.md`](docs/reference/testing.md) | pytest layout (51 files across 10 domains), how to run (whole / by domain / single), `pyproject.toml` test config, `conftest.py` role, coverage expectations per module, representative test patterns (assertion / invariant / parametrise / registry-exhaustiveness), conventions enforced by tests, guide for writing new tests, pre-promotion regression command. |
| [`docs/reference/agent-reference.md`](docs/reference/agent-reference.md) | Complete agent reference: 14 intents (pipeline / copilot / governance / cross-mode), 20 tools with args/write flags, deterministic `PLAN_REGISTRY` tables, `IntentRouter` regex+LLM classification flow, `PlanCompiler` API, `Executor` confirm-gate + path-guard, `AgentState`, audit log formats (`logs/agent_audit.jsonl`, `logs/agent_intent_log.jsonl`), agent config, REPL CLI, add-a-new-tool procedure. |
| [`docs/reference/governance.md`](docs/reference/governance.md) | End-to-end promotion workflow, `PromotionManager` API (`promote_from_report` / `promote_from_tuner_checkpoint` / `promote_direct` / `list_versions` / `load_version`), registry layout + archive naming, `configs/promotion_log.jsonl` line schemas (PROMOTED / PROMOTION_FAILED), `ShadowPromotionGate` two-gate flow, `MetaGovernorExecutor`, `PortfolioValidation`, rollback procedure, pre-promotion checklist, write-authority matrix. |
| [`docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md`](docs/governance/DOCUMENTATION_DRIFT_PROTOCOL.md) | Long-form of the §6.2 thin rule: the invariant (every code/config/runtime-truth change triggers a documentation-truth decision), the 5-step process (classify → impact → gate → synchronize → audit), the user-approval gate calibration, the audit-trail format, the completion criterion, and the F-038 worked example. |
| [`docs/architecture/signal-flow.md`](docs/architecture/signal-flow.md) | End-to-end candle→order linear walk for the CRT spine (Steps 1–7) with module / entry-point / config / failure-mode per step, the four async kitchen feeders (Governance, Training, AI Agent, INOUT) and where each joins the spine, cross-reference matrix, Mermaid swim-lane diagram. |
| [`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md) | LLM trigger-word vocabulary for owning the codebase: `Continue` / `Next step` / `Next plan` / `Validate` / `Implement` (Tier 1) + `Orient`/`Status` / `Map` / `Audit` / `Plan` / `Log` (Tier 2). Per trigger: action · docs loaded · exit condition. See §12. |
| [`docs/architecture/goal.md`](docs/architecture/goal.md) | North-star goal document (plain language): purpose, the happy flow (candle→order), the 7 invariants + five governance questions, the deviation policy (throughput-improving deviations OK if invariants hold), migration target. The "what good looks like" baseline. |
| [`docs/architecture/intelligence-compounding.md`](docs/architecture/intelligence-compounding.md) | Long-form of CLAUDE.md §6.1: the repository as a self-compounding **intelligence substrate** (zero intelligence loss). Repository utility function, entropy principle, the goal-first chain, modules-as-frozen-thoughts, the three permanent checklists (User/Claude/System), 7-level intelligence ladder, strengthened Memory Rule, and the Stage 1→7 evolution path (with the "no premature framework" guardrail). |
| [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md) | Auto-generated command catalog (from `control_plane/registry.py`): every CLI invocation, artifacts, suggested next step. Authoritative for "how do I run X." |
| [`assistant_project.md`](assistant_project.md) | Persistent session log — every LLM response since April 2026 is timestamped and archived here. Contains the architecture migration doctrine, all past decisions, the five governance questions, and a complete audit trail. Always check before re-opening a resolved thread (§3.4 item 7). Governed by CLAUDE.md §6 (Persistent Logging Mandate). |
| | [`active_models.yaml`](active_models.yaml) | **Loaded first in every Claude session.** Machine-readable model registry: CRT engine (10 states, 81 thresholds, exact detection logic), Gaussian model (v4_mirrored metadata, 38-feature schema, governance rules), BitNet config, zone gate, RR model, strategy modules, engine runner orchestration. Source-verified against `crt_engine_v2.py`, `feature_schema.py`, `model_registry.py`. |


---

## 3. How to Work With This Codebase

### 3.1 Adding a new feature (canonical pattern)

1. **Place the module.** Pick the right subpackage from `CONVENTIONS.md §2`. Scoring engine → `src/engines/`; decision/risk logic → `src/core/`; validator → `src/config_layer/`; governance gate → `src/governance/`; live-mode code → `src/inout/`. Never put production logic in `scripts/`.
2. **Copy `docs/reference/example-service.py`** into the chosen folder, rename, and keep its structure: `_load_*_cfg()`, `_require()`, dataclass with `from_prod_config`, named flow logger, public `PascalCase` class with typed methods, private `_snake_case` helpers.
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
- **JSONL event line** → self-contained `dict` with `timestamp` + `kind`; append only. Document the shape in `docs/reference/schemas.md §9`.
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
- **`CRTState` transitions are not a free graph.** The legal map is **9 states** (golden path `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`, plus the `SHADOW_PENDING` branch `RANGE ↔ SHADOW_PENDING → SWEEP` (Phase 1) and the `EXPIRED` TTL branch `EXPANSION → EXPIRED → RANGE` (Phase 3b soft-archive)). Authoritative: `VALID_TRANSITIONS` (`crt_engine_v2.py:1025`) / `event-taxonomy.md §3`.
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
| F-004 | ARCH | BitNet is a LIVE hard-reject gate (score < 0.55) and the score IS persisted; only the *adaptive* threshold is dormant | Certain |
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
| F-041 | GOV | ZoneGate runtime scores through `models/zone_registry.json` (8 zones, HARD gate) per active config (`engine_runner.zone_registry_path`, `zone_mode=hard`) — NOT the `zone_gate_registry.json` version manifest, whose `active:true` points to a *different* file (sha256 `aade29c4`≠`e73e0893` → TruthConflict §6.2, surfaced not auto-reconciled). Stored zone labels are ~98% SL-hit / 6-of-8 negative mean_RR (consistent w/ F-038/F-025) — OBSERVATION; whether label-quality is the dominant ZoneGate defect is the explicit Phase-5 Go/No-Go gate, NOT yet asserted. E-001 self-correction: earlier "manifest empty → silent fail-open" was a parse artifact. Authority: governance-hygiene/research only | Certain |
| F-040 | ECON | The volatility/range-EXPANSION + compression→expansion TRANSITION channel (F-030's untested Program-4b successor) is INFORMATIVE but NOT economically consumable in the spot directional architecture. Two-stage pre-registered gate on the M15∧H1∧H4 candle-state conjunction (M15 base, H1/H4 derived; no M5 on disk): Stage-1 4b-vol/4b-range/4d-transition all permutation-significant (crypto+FX p≈0.0005), UNIVERSAL, persistent (half-life 8, 2024→2025 retention 0.67–0.99); 4c-persistence NOT informative (p≈0.97). Stage-2 directional consumer (compression_breakout, unchanged M4 gate, intrabar_fixed+12bps) 0 PROMOTE, well-powered REJECT (crypto E −0.25…−0.60R WR≈0.33; FX cost-dominated PF 0.02–0.08). Stage-1-PASS/Stage-2-FAIL: information priced efficiently, binding constraint = EXECUTION MODEL not predictability (extends F-030). SCOPE: MTF-conjunction's incremental info beyond single-TF vol NOT isolated (consistent w/ vol memory, no novelty claim); FAIL = directional construction under fixed standard, not "no instrument could monetize." Program 4 CLOSED. Authority: research/docs only | Likely |
| F-042 | ECON | The weekly liquidity-sweep ontology (ICT/CRT Mon+Tue accumulation → Wed-Fri sweep → reversal) does NOT clear the M4 gate on FX majors — Program 8 CLOSED. Pre-registered new geometry (`src/research/weekly_sweep/`, calendar-locked weekly range + boundary-cross-then-close-back-inside sweep, reimplementing crt_engine_v2's local-sweep geometry against a WEEKLY range) through the unchanged M4 gate (intrabar_fixed+12bps), same 5 FX majors as F-035. 0 PROMOTE across all 6 scopes (per-instrument REJECT at the absolute-expectancy gate, POOLED n=512 E=−0.634R PF=0.457); all 6 DO beat their winning control (p=0.0005) but that relative edge is moot since absolute expectancy stays negative. Direction×Vol 3×3 diagnostic (CandleStateEncoder direction × RegimeLabeler macro-vol, tercile_window=2000): 8/9 cells negative, one small-N positive (DOJI/EXPANSION) — information only, no authority. Extends F-019…F-041 to a genuinely NEW weekly-CALENDAR ontology (distinct from Program 1/2's local-structural frame). Authority: research only | Likely |
| F-043 | ECON | A forward Markov P^H regime-transition forecast is REDUNDANT with the current vol level and persistence — Program 4b CLOSED. New `MarkovRegimeForecaster` (`src/interpreters/regime_observer.py`, trailing transition matrix, w_markov=480, h=8, reuses `RegimeLabeler`'s S_t verbatim) feeds the unchanged `regime_conditioning.evaluate_scope` cross-matrix, extended additively with a within-tercile-shuffle 5th control (default-None param reproduces Program 4's F-030 artifact byte-identical, re-verified). Hard calibration gate passed (BNBUSDT H_atr=0.885027). 0 REGIME_EXPLOITABLE across all 15 scopes: all 10 toy consumer×scope combos (expansion_breakout/mean_reversion) resolve REGIME_REDUNDANT — well-powered (n=3,645–35,525), statistically real (p≤0.045) but fully explained by BOTH a stale-regime lag AND the current vol level (S_within_tercile ≥ S_real); spine REGIME_INSUFFICIENT (no claim). Corrects a stale Funding Ledger entry that conflated this literal Markov construction with F-040's different MTF-conjunction "4b/4c/4d" closure; the pre-registration's reserved "F-031" was superseded, this is F-043. Authority: research only | Likely |

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
