# Grok validation infra — design

This is the **city plan** for the Grok session layer.
It does **not** replace `docs/architecture/goal.md` (constitution) or `PLAN_REGISTRY` (in-repo agent).
It does **not** grant production, promotion, or live-order authority.

| Layer | Owns | Happy flow |
|---|---|---|
| Constitution | `docs/architecture/goal.md` | M15 candle → four scores → fusion → decision → planner → Ultron → order |
| Grok infra (this file) | trader-LLM session | User phrase → **intent** → fixed file/tool sequence → fail-closed answer |
| In-repo agent | `src/agent/plan_compiler.py` | Separate surface. Do not merge. |

**Meta-rule:** the LLM classifies the intent. It does **not** invent the next file or skip a gate.
Unknown intent → `ask_user`. Unknown meaning → do not assume.

Grok’s economic goal (**earn money**) sits **alongside** G001, never above replay correctness.
A profitable-looking path that breaks determinism is still a reject.

---

## 1. Pieces (already on disk)

```
user phrase
    │
    ▼
.grok/rules/GROK.md          boot + role + retrieve rules          (auto-loaded)
    │
    ├─ .grok/GOAL.md         What / Why / 5-gate
    ├─ .grok/PLAYGROUND.md   review contract
    ├─ .grok/PENDING.md      later items (retrieve on “pending”)
    ├─ .grok/HOW_INDEX.md    topics + Ins/Outs + Excel rollup
    ├─ .grok/INFRA.md        this file — intent → happy flow
    │
    ▼
docs/topics/<needed>.md      meaning + Ins/Outs
    │
    ▼
cited src/scripts/tests      current behavior (source wins)
    │
    ▼
functionality Excels         file inventory (1,247 tracked)
    │
    ▼
ACTIVE_VERSION + tests       runtime truth
    │
    ▼
answer: hypothesis | identified concept | economic candidate | USER AUTHORIZATION
```

Do not auto-load HOW_INDEX or INFRA (token). GROK.md tells Grok **when** to open them.

---

## 2. Session intents (Grok infra)

Closed set. Add a row here before inventing a new one.

| Intent | User says (examples) | Happy flow | Stop if |
|---|---|---|---|
| `boot` | new session / “orient” | GROK.md → GOAL.md → PLAYGROUND.md. State role, Sense A, P-GOAL-04 still later. | — |
| `pending` | pending / what’s left | Open PENDING.md. List every non-`DONE` row. | File missing |
| `defer` | later / leave it | Append a PENDING row same turn. | Vague item (ask what to write) |
| `claim.validate` | “this is a setup / this makes money / the engine does X” | §3 five-gate How | Gate 1–4 UNKNOWN |
| `structure.name` | what does the playground implement? | Sense A result (already DONE). Do not re-hunt. | User wants to reopen A |
| `edge.measure` | measure / does it make money / Sense B | **Blocked** until P-GOAL-04 authorized. Then measurement-contract topic → honest ledger. | No MC / contaminated labels |
| `concept.discover` | new strategy / Sense C | **Blocked** until authorized. Domain meaning first. No invented proprietary semantics. | Meaning not established |
| `review.semantic` | is this a bug / another model said X | SEMANTIC_REVIEW_PROTOCOL (10-class close). No production edit. | — |
| `spine.walk` | walk a candle / happy flow | §4 spine stages in order. One topic per stage. | Skip a stage |
| `closure.record` | record this / close that | Write GROK.md / PENDING / session log. Findings only if a conclusion flipped. | Downgrade needs user |
| `how.regenerate` | refresh How-index | `python .grok/_build_how_index.py` after Excels change. | — |
| `ask_user` | anything else | State UNKNOWN. Offer the table. Do not guess. | — |

---

## 3. Happy flow — `claim.validate` (the How)

This is the core infra path. Assume the claim is well-formed.

```
trader claim spoken
        │
        ▼
[1] MEANING     HOW_INDEX → pick exactly one NEEDED topic
                Read Ins/Outs. If no topic fits → USEFUL or UNKNOWN (not a strategy).
        │
        ▼
[2] EXISTENCE   Open cited files. Confirm current behavior from source + ACTIVE_VERSION.
                Confirm the .py is in the matching Excel (or on P-EXCEL leftovers).
        │
        ▼
[3] CONTRACT    MIAR owner. Structure ≠ policy ≠ geometry ≠ risk.
                If two layers share a word, do not unify them.
        │
        ▼
[4] HONESTY     Can this be measured without lookahead, wrong clock, F-022 labels?
                Measurement-contract topic. If no → stop, not an edge.
        │
        ▼
[5] MONEY       Only if P-GOAL-04 is authorized.
                G001 / goal-layer. Pass → economic candidate.
                Fail → successful validation (hallucination stopped).
        │
        ▼
hypothesis  or  identified concept  or  economic candidate  or  USER AUTHORIZATION
```

Never jump to [5] from a feeling. Never edit production on this path.

---

## 4. Happy flow — spine stages (`spine.walk`)

This is the **constitution** candle walk, assumed to succeed at each stage.
Grok uses it to check a claim against the **right** topic. Source wins if a topic drifts.

| Stage | Intent of the stage | NEEDED topic | In (happy) | Out (happy) | Must not become |
|---|---|---|---|---|---|
| 0 | Represent the bar | `feature-schema.md` | Honest M15 OHLCV | 38-dim vector, PIT | A signal |
| 1a | Name structure | `crt-spine.md` | Candle + `crt_engine` config | Legal CRT state / direction | A strategy |
| 1b | Score structure / conformity / zone / commitment | `scoring-engines.md` | Features + direction | `{crt, gaussian, zone_gate, rr}` | p(win) |
| 2 | Approve the **decision** | `fusion-decision.md` | Four scores, all present | ACCEPT / REJECT | An order |
| 3 | Place geometry | `execution-planning.md` | Accepted decision + features | Entry / intent / TTL | A fill |
| 4 | Permit risk | `ultron-risk-gate.md` | Plan + portfolio | APPROVE + size **or** REJECT | Optional |
| 5 | Optional veto | `bitnet-gate.md` | Feature subset | REJECT if enabled+low; **inert** on active | Fusion voter |
| 6 | Live send | `live-execution.md` | Approved sized plan | **No rail today (F-073)** | “We are live” |
| M | Measure | `research-measurement-contract.md` + `goal-layer.md` | Ledger + declared MC | Goal report / ΔG001 | Promotion |
| G | Promote | `config-validation.md` → `promotion-governance.md` | `ValidationReport.APPROVE` | New `ACTIVE_VERSION` | Silent default |
| Q | Who owns the question | `model-intent-and-feature-ownership.md` | Concept name | One MIAR owner | Two owners |

**Spine happy path (one sentence):**  
an honest M15 bar is encoded, CRT names a legal structure, four engines each answer their own question, fusion approves a decision, the planner draws geometry, Ultron sizes or kills it, nothing is live until a rail exists, money is judged only under a measurement contract.

**CRT golden path (structure only):**  
`RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`  
(plus `SHADOW_PENDING`, `EXPIRED`). Illegal jump → reject. F-074: displacement is **away from** the swept side.

---

## 5. Happy flow — other session intents

### `pending`
Open `.grok/PENDING.md` → emit every `OPEN`/`LATER` row → stop. No extra research.

### `defer`
Write one new row (id, LATER, date, item, source) → confirm the id to the user.

### `structure.name`
Return the Sense A close: CRT = structure, S1–S10 dormant consensus, not one named strategy.

### `edge.measure`
If P-GOAL-04 is not authorized → stop and say so.  
If authorized: measurement-contract Ins/Outs → `forward_walk` / backtest ledger → goal-layer compare to G001 → report Δ, never “so promote.”

### `review.semantic`
Reproduce → trace → owner → domain → compare → one of 10 classes → no silent edit.

### `closure.record`
Update the owning file (GROK.md / PENDING / findings if a conclusion flipped) + session log.

---

## 6. What we will not build (yet)

- A second `PLAN_REGISTRY` inside `src/agent/` for these intents.
- Auto-injecting HOW_INDEX (too large).
- Copying 1,247 Excel rows into GROK.md.
- A live order path (F-073; USER AUTHORIZATION).
- Treating S1–S10 as the strategy (`weight_strategy_consensus` default 0).

If a router is wanted later: a thin table in this file is the spec. Implementation is a separate authorized turn.

---

## 7. Failure is part of the infra

| Break | Infra response |
|---|---|
| No NEEDED topic matches | USEFUL sidecar or UNKNOWN — not a strategy |
| File not in Excel | Check P-EXCEL leftovers; else inventory gap, not an edge |
| Two owners for one word | Ownership table; do not unify |
| Honesty fails | Stop before money |
| P-GOAL-04 off | Money claim stays hypothesis |
| Live claimed | F-073 — not happy, not a bug in the session layer |

---

## 8. Codebase map — GCMC × stack rooms × LLM allowance (2026-09-03)

This is the **link layer** between the functionality Excels and the LLM-ready stack
from the session doctrine: the model sits in Lab / Adapter / After-the-yes.
It does **not** sit in data, structure, trade-object, measurement, or
decision/risk/execution.

**Do not copy Excel rows here.** The join workbook is the row-level truth.

| Artifact | Role |
|---|---|
| `.grok/infra_architecture_link.xlsx` | one row per disk `.py` + Gaps + Stack_rooms + Unreferenced_spine |
| `.grok/infra_architecture_link_coverage.json` | the coverage numbers for this sweep |
| `.grok/_link_infra_architecture.py` | regenerates the join + appends link columns on the four inventories |
| `results/analysis/src_business_functionality.xlsx` | src inventory (GCMC v1 numerator) |
| `scripts_business_functionality.xlsx` | scripts inventory |
| `docs/analysis/tests_functionality_inventory.xlsx` (`By File`) | tests inventory |
| `.grok/gcmc_v2_inventory.xlsx` | mt5_analytics / oss_lab / tools |
| [`docs/architecture/llm-governance-layer.md`](../docs/architecture/llm-governance-layer.md) | doctrine: LLM is advisory, never execution authority |
| [`docs/architecture/goal.md`](../docs/architecture/goal.md) | constitution candle walk |
| [`.grok/HOW_INDEX.md`](HOW_INDEX.md) | topic × cited files (regenerated 2026-09-03 with Excel 592/408/531) |
| [`docs/architecture/three-layer-codebase-atlas.md`](../docs/architecture/three-layer-codebase-atlas.md) | static/runtime/authority atlas — **DOC_DRIFT** (351 modules vs 592 `src/` files today) |

### Code sweep (name census, 2026-09-03)

Kind: **path listing + Excel join + citation extract.** Not a read-every-source pass.
Proof of sweep: this section + the join workbook + `This analysis referenced = YES`
on every inventory row processed.

| Tree | Disk `.py` | Excel listed ∩ disk | Excel leftover (on disk, no row) |
|---|---:|---:|---:|
| `src/` | 592 | 592 | 0 |
| `scripts/` | 408 | 408 | 0 |
| `tests/` | 531 | 531 | 0 |
| **GCMC v1** | **1,531** | **1,531 (100%)** | **0** |
| `mt5_analytics/` + `oss_lab/` + `tools/` | 99 | 99 | 0 |
| **GCMC v2** | **99** | **99 (100%)** | **0** |
| **Declared trees total** | **1,630** | | |

P-EXCEL-07 restored GCMC v1 to 100% on 2026-09-03 (regenerate three Excels).
2026-08-15 1,281/1,281 and the midday 1,460/1,531 reading are history.
KPI ledger: [`.grok/CLOSURE_KPI.md`](CLOSURE_KPI.md).

This analysis **referenced 1,630 / 1,630** declared-tree `.py` paths.
Infra-**doc** citation (How-Index ∪ topics ∪ architecture ∪ INFRA ∪ remainder
inventory) hits **1,531 / 1,531** GCMC v1 and **1,630 / 1,630** declared trees.
`Unreferenced_spine` remaining: **0**. Remainder (sidecar / measurement / tests /
lab) named in [`.grok/infra_file_citations.md`](infra_file_citations.md) (944
paths, existence only).

| Citation source | Distinct `.py` paths extracted |
|---|---:|
| `docs/architecture/**` | 481 |
| `docs/topics/**` | 300 |
| `.grok/HOW_INDEX.md` | 239 |
| `.grok/INFRA.md` | 32 |
| `.grok/infra_file_citations.md` (remainder) | 944 |
| Union (on-disk hit) | 1,531 of 1,531 v1 · 1,630 of 1,630 declared |

### Stack rooms (where each file fits)

Assigned by path prefix in `_link_infra_architecture.py`. Source still wins if a
file’s *behavior* disagrees with the prefix.

| Room | Disk files (v1+v2) | LLM allowance | Must not become |
|---|---:|---|---|
| `data_clock_identity` | 104 | `FORBIDDEN_HOT_PATH` | a signal |
| `structure` | 33 | `FORBIDDEN_HOT_PATH` | a strategy |
| `trade_object_costs` | 11 | `FORBIDDEN_HOT_PATH` / `MEASUREMENT_ONLY` | a live fill |
| `measurement` | 505 | `MEASUREMENT_ONLY` | promotion |
| `decision_risk_execution` | 94 | `FORBIDDEN_HOT_PATH` | an LLM trigger |
| `llm_sideline` | 49 | see three seats below | the book |
| `governance` | 117 | `GOVERNANCE_GATED` | silent default |
| `sidecar_orphan` | 59 | `FORBIDDEN_HOT_PATH` | spine by import |
| `lab` | 99 | `LAB_ONLY` | production control |
| `tests` | 531 | `N/A_TEST_FLOOR` | a claim by existing |
| `tooling_scripts` | 28 | `ALLOWED_SIDELINE` | a strategy |

Constitution walk (INFRA §4) maps onto rooms:

| Spine stage | Room | Canonical files (not exhaustive) |
|---|---|---|
| 0 bar | `data_clock_identity` | `src/features/feature_schema.py`, `src/features/feature_pipeline.py`, `src/data_ingestion/dataset_registry.py`, `src/identity/` |
| 1a structure | `structure` | `src/config_layer/crt_engine_v2.py`, `src/config_layer/state_identity.py`, `src/config_layer/parent_crt.py`, `src/structure/` |
| 1b scores | `decision_risk_execution` | `src/engines/heuristic_gaussian_engine.py`, `src/engines/zone_gate_engine.py`, `src/engines/rr_engine.py` |
| 2 decision | `decision_risk_execution` | `src/core/engine_runner.py`, `src/core/fusion_engine.py`, `src/core/decision_engine.py` |
| 3 geometry | `decision_risk_execution` | `src/config_layer/execution_planner.py` |
| 4 risk | `decision_risk_execution` | `src/core/ultron_risk_gate.py` |
| 5 optional veto | `decision_risk_execution` (inert on active) | `src/bitnet/bitnet_inference.py` |
| 6 live | `decision_risk_execution` — **no rail (F-073)** | `src/runtime/live_engine_hook.py`, `src/live/` |
| M measure | `measurement` | `src/research/`, `scripts/research/` |
| G promote | `governance` | `src/governance/promotion_manager.py`, `src/config_layer/config_validator.py` |
| Q owner | `governance` | MIAR / `docs/topics/model-intent-and-feature-ownership.md` |

### LLM — three seats only

Matches `llm-governance-layer.md` and the session rule (think next to the book).

| Seat | Allowance token | Files | If the model is wrong |
|---|---|---|---|
| Lab | `ALLOWED_SIDELINE` | `src/llm_research/*`, `src/multi_llm/*`, `src/expansion/llm_pattern_extractor.py`, `src/control_plane/context_report.py`, `src/control_plane/code_context_extractor.py`, `scripts/context/*` | wasted time |
| Adapter / operator agent | `GOVERNANCE_GATED` | `src/agent/*` (`intent_router.py`, `plan_compiler.py`, `executor.py` — path-guard + `y/N`; LLM never picks tools) | confirm-gate / UNKNOWN |
| After-the-yes tie-break | `TIEBREAK_NEUTRAL_FALLBACK` | `src/config_layer/llm_scorer.py`, `src/config_layer/llm_inference_client.py` (fusion uncertainty band only; circuit → 0.5 / 1.0) | book unchanged |

**Forbidden:** candle → model → buy/sell. `src/core/engine_runner.py` and
`src/core/ultron_risk_gate.py` stay `FORBIDDEN_HOT_PATH`. A path that cannot
tolerate the LLM returning neutral is broken by design.

### What is still unlinked (do not pretend done)

- **P-EXCEL-07 DONE.** GCMC v1 1,531/1,531. Gaps sheet empty for declared trees.
- **Unreferenced_spine DONE (0 remaining).** 108 paths named in owning topics (existence only) + 8 utils in this file.
- **Remainder (sidecar / measurement / tests / lab) DONE 2026-09-04.** Paths live in [`.grok/infra_file_citations.md`](infra_file_citations.md) (generated; existence only). Linker counts them toward `Infra-doc referenced` / `Cited in remainder inventory`. Not a behavior claim.
- Atlas “351 modules / 696 imports” is a dated Layer-1 snapshot, not today’s census (592 `src/` files).

### Spine inventory (2026-09-03 citation pass)

The 108 Unreferenced_spine rows after GCMC restore were named in owning
`docs/topics/*.md` Code covered blocks (existence only). Utils with no NEEDED
topic are named here so the join column `Cited in INFRA` is YES:

| File | Room |
|---|---|
| `src/utils/console_safe.py` | `data_clock_identity` support |
| `src/utils/jsonl_writer.py` | `data_clock_identity` support |
| `src/utils/log_identity.py` | `data_clock_identity` support |
| `src/utils/log_index_writer.py` | `data_clock_identity` support |
| `src/utils/logging_config.py` | `data_clock_identity` support |
| `src/utils/parquet_store.py` | `data_clock_identity` support |
| `src/utils/pattern_hasher.py` | `data_clock_identity` support |
| `src/utils/zone_schema_migrator.py` | `data_clock_identity` support |

