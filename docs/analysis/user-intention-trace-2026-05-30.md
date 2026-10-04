# User-Intention Trace — `assistant_project.md` + Agent Intent→Tool Layer

> **Point-in-time snapshot, not a living doc.** Captured 2026-05-30 from the SESSION LOG
> (`assistant_project.md`, 37 entries spanning 2026-04-10 → 2026-05-30) and the agent code under
> `src/agent/`. For current truth use the living docs: operating rules → `CLAUDE.md`; north-star
> → `docs/architecture/goal.md`; agent reference → `docs/reference/agent-reference.md`.
>
> **Why this exists:** to (1) reconstruct *what the user has been trying to build and why* from
> the append-only session log, and (2) trace the literal "user intention → tool" machinery in the
> AI agent — then show how the two are the same idea at different layers.

---

## Part 1 — The intention arc (traced from the session log)

The log reads newest-first, but the *intention* is clearest read oldest→newest. It moves through
five eras. Each era's underlying question is in italics.

### Era 1 · Foundation & legibility (2026-04-10 → 04-22)
Enhancement-plan Phases 0–5, "JSON-as-single-source-of-truth," the master-context docs suite
(architecture / conventions / schemas / config-reference / governance), the architecture diagram,
and the first AI-agent design docs.
*Intent: make the system governable and legible before growing it — no magic numbers, one config
of record, a documented promotion gate.*

### Era 2 · Stabilisation & correctness (2026-04-25 → 04-30)
pytest restored to **0 failures** (427 passed), a wave of stale-API agent-test fixes
(intent_router / tool_registry / plan_compiler / executor), dead-code archive pass, the **RR
data-integrity audit** (`rr=2.0` contamination), canonical naming (`UltronRiskGate` /
`RegimeGovernor`), root-causing the **all-zero feature columns** bug, and `signal-flow.md`.
*Intent: trust the numbers before extending — fix data integrity and the test net first.*

### Era 3 · Multi-strategy expansion (2026-04-30 → 05-01)
Sprints 1–7: 10 strategies (CRT wrapper, Trap, Pattern, MeanRev, Breakout, StatArb, Grid,
Scalping, News, ML ensemble), `StrategyOrchestrator`, `FusionEngine.fuse_strategy_results()`,
`MonteCarloEngine`, `KillSwitch`, UAT runner, live-hook integration (Telegram / MT5), Docker,
health checker, production governance.
*Intent: scale from a CRT-only spine to a governed multi-strategy portfolio engine.*

### Era 4 · Empirical, telemetry-driven tuning (2026-05-12 → 05-30)
Two-layer architecture (Pipeline A runtime / Pipeline B research), direction-mirroring fix,
calibrated scorers — then the **BNBUSDT Phase 0→6b** measure-first loop:
- **Phase 0** telemetry found the *real* bottleneck was DISPLACEMENT→EXPANSION, **not** the
  hypothesised retest depth.
- **Phase 1** SHADOW_PENDING displacement protection (SHADOW_LEAK=0).
- **Phase 2b** score-inversion shown to be N=5 noise; expansion max-dwell = 20,115 candles.
- **Phase 3b** expansion **TTL guard** (495 candles); promotion gate closed via
  `expired_counterfactual_rr`.
- **Phase 4b** shadow age-decay experiment → verdict **advisory-only** (decay was just threshold
  shifting; normal-only baseline cut drawdown 77%).
- **Phase 5a** decision-selectivity threshold sweep plan.
- **Phase 6 / 6b** ROI surfaced as additive telemetry; funnel diagnosis pinned the binding
  constraint to **RETEST→EXECUTION** — 64 valid retests discarded by the **session filter**, not
  the score threshold.
*Intent: let measured data, not hypotheses, drive every change.* Repeatedly the data **invalidated
the leading hypothesis** (retest-depth, score-inversion, age-decay) — the user's discipline is to
measure first and accept the verdict.

### Era 5 · LLM-context-economy migration (2026-05-28 → 05-30)
The **M0–M5 migration doctrine** (event-driven, "an LLM loads only the *one* service it needs"),
the M0 architecture docs + M1 telemetry-envelope + M2 event extraction, the **Trigger Vocabulary**
(single-word LLM ownership commands), `goal.md` north-star, the collaboration-workflow agreement,
the code-map import-graph generator, and the semantic docs reorg (kebab-case).
*Intent: make the codebase **ownable by an LLM** that loads minimal, curated context — microservice
boundaries as context boundaries.*

---

## Part 2 — The throughline (the deep intention)

Across all five eras, one meta-goal is consistent. The user is building a trading system that is:

1. **Deterministic / replayable** — no lookahead, fixed seeds, comparable telemetry across runs.
2. **Governed** — no config reaches production without an `APPROVE`d `ValidationReport`, SHA-256
   hashing, and an append-only audit trail.
3. **Empirically validated, not guessed** — Era 4 is the lived proof; hypotheses die on contact
   with telemetry.
4. **LLM-ownable** — Era 5's explicit north star; the whole migration exists so a future LLM (or a
   future session of *this* assistant) can operate the system from curated context instead of the
   whole repo.

The unifying frame is the **five governance questions** (replay deterministic? telemetry
comparable? auditable? LLM-reasonable? execution authority isolated?) declared at the top of
`assistant_project.md`. Every era is an answer to one of them.

---

## Part 3 — The agent intent→tool layer (the literal "user intention of tool")

The AI Automation Agent under `src/agent/` is the codebase's own implementation of "turn a user's
intention into tool execution." The pipeline:

```
User NL input
  → IntentRouter.classify()            intent_router.py:72  (regex fast-path → LLM fallback)
  → PlanCompiler.build(intent_key)     plan_compiler.py:126 (deterministic PLAN_REGISTRY lookup)
  → ArgFiller.fill(plan, context)      (resolve {placeholders} from state + prior outputs)
  → Executor.run(plan)                 executor.py:45       (confirm-gate on writes + path-guard)
  → AuditLogger                        (logs/agent_audit.jsonl + logs/agent_intent_log.jsonl)
```

### 3.1 Classification — how intention is recognised (`intent_router.py`)
1. **Regex fast path** (`_regex_classify`, line 92) — on match returns confidence **0.85**
   (`intent_router.py:99`), patterns loaded from `src/agent/prompts/intent_patterns.json`.
2. **LLM fallback** — only if regex misses; accepted when confidence ≥ **`confidence_floor=0.6`**
   (`intent_router.py:57,61`).
3. **Degenerate fallback** — `{intent_key: "ask_user", confidence: 0.0}` when nothing matches.

The LLM **classifies intent only**; it never selects tools or their order.

### 3.2 Planning — intention → ordered tools (`plan_compiler.py:43` `PLAN_REGISTRY`)
`PLAN_REGISTRY` is a pure `Dict[str, List[ToolStep]]` — the single source of truth for what each
intent runs.

| Mode | Intent | Tool sequence |
|---|---|---|
| pipeline | `tune_only` | `tuner.run_multi` |
| pipeline | `tune_and_validate` | `tuner.run_multi` → `validator.validate` |
| pipeline | `tune_and_promote` | `tuner.run_multi` → `validator.validate` → `promotion.promote_from_checkpoint` |
| pipeline | `validate_only` | `validator.validate` |
| pipeline | `promote_only` | `promotion.promote_from_checkpoint` |
| pipeline | `backtest_only` | `backtest.run_v2` |
| pipeline | `full_pipeline` | `tuner.run_multi` → `validator.validate` → `promotion.promote_from_checkpoint` → `backtest.run_v2` → `live_hook.dry_run` |
| copilot | `advise_signal` | `engine.run` → `fusion.explain` → `planner.plan` → `risk.check` → `advise.veto` |
| copilot | `veto_query` | `engine.run` → `fusion.explain` → `advise.veto` |
| copilot | `resize_query` | `engine.run` → `fusion.explain` → `advise.resize` |
| governance | `governance_inspect` | `reflection.load_merge` → `meta_governor.dry_run` |
| governance | `governance_propose` | `reflection.load_merge` → `reflection.generate_prompt` → `meta_governor.dry_run` → `shadow.stage_candidate` |
| governance | `governance_run` | `reflection.load_merge` → `meta_governor.dry_run` → `governance.run_loop` |
| cross-mode | `audit_inspect` | `audit.tail` |
| cross-mode | `findings_synthesize` | `findings.synthesize` |
| cross-mode | `findings_recent` | `findings.list_recent` (n=10) |
| cross-mode | `findings_explain` | `findings.explain` |

Plus the degenerate `ask_user` → empty plan (`_ASK_PLAN`, `plan_compiler.py:123`).

> **Doc-drift finding (accurate-to-code 2026-05-30):** `PLAN_REGISTRY` defines **17** mapped
> intents (+ `ask_user`). `docs/reference/agent-reference.md` §4.2 still lists **14** — it
> predates the `findings_*` trio (`findings_synthesize` / `findings_recent` / `findings_explain`).
> The reference should be refreshed (out of scope for this snapshot).

### 3.3 Execution — guarded dispatch (`executor.py`, `tool_registry.py`)
`Executor.run()` dispatches each `ToolStep` via `tool_registry.get_tool(name)`. **Write** tools
(`ToolSpec.write=True`) trigger a per-call confirmation gate plus a path-guard; copilot tools are
all read-only. Every step and a session summary are appended to the agent audit JSONL.

---

## Part 4 — Where the two meet

The agent's *design* is the project's *intention* compiled into code:

| Project intention (Part 2) | Agent mechanism (Part 3) |
|---|---|
| Deterministic / replayable | `PLAN_REGISTRY` is a pure lookup — the LLM never picks tools (no nondeterministic planning) |
| Governed writes | `Executor` confirm-gate + path-guard; `write_tools_enabled` allowlist |
| LLMs advisory, never execution authority | copilot mode is read-only; `UltronRiskGate` stays the sole execution authority; LLM only *classifies* |
| Auditable | every step + summary → `logs/agent_audit.jsonl` / `agent_intent_log.jsonl` |
| LLM-ownable codebase (Era 5) | the **Trigger Vocabulary** (`Continue` / `Validate` / `Implement` …) is the human-facing twin of intent routing — single words classified into a deterministic action |

So "user intention of tool" has two faithful readings and they converge: the **user's intention for
the tool** (a deterministic, governed, empirically-tuned, LLM-ownable trading system) is exactly
what the **agent's intention-routing tool** enforces in miniature — deterministic plans, guarded
writes, advisory-only LLM, full audit.

---

## Part 5 — Open intentions (latest unresolved `Next Step` fields)

- **M3** — orchestration de-coupling (kill `live_engine_hook` singletons → injection).
- **Phase 5a** — `tier_2_threshold` selectivity sweep `[0.44..0.60]`.
- **ROI session-window sweep** — backtest with `asia` added to `allowed_sessions` (the funnel
  diagnosis named the session filter as the #1 ROI lever).
- **Pending user decision** — ROI as a *governance gate* vs *optimisation target* (the latter
  needs a documented deviation flag).

---

## Sources

- `assistant_project.md` (SESSION LOG, 37 entries, 2026-04-10 → 2026-05-30).
- `src/agent/intent_router.py` (`:51,57,72,92,99`), `src/agent/plan_compiler.py` (`:43,123,126`),
  `src/agent/executor.py` (`:45`), `src/agent/tool_registry.py`.
- `docs/reference/agent-reference.md` §1–§5 (note the 14-vs-17 intent drift above).
- Corroborating memory: `project_phase{0,1,2b,3b,4b,5a,6,6b}_findings`.
