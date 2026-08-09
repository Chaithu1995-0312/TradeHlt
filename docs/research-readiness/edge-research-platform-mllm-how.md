# Multi-LLM Architecture — HOW Layer Design + Initiation

> **Status:** HOW design **initiated** (thin dual-lane) · 2026-07-14  
> **Program:** `EDGE_RESEARCH_PLATFORM` · Phase **P0/P6.A**  
> **Authority:** orchestration only — grants **no** production, promotion, or capital authority  
> **Runtime lane:** file packages under [`multi_llm/research_lane/`](../../multi_llm/research_lane/README.md)

---

## 1. Is multi-LLM architecture required?

| Question | Answer |
|---|---|
| Required for P1 harness code? | **No** — Claude + You can implement P1 |
| Required for anti-echo + promise-track research? | **Yes (thin)** — asymmetric roles + 4 artifact kinds |
| Full auto multi-agent mesh? | **No** — premature (D-bridge: You still bridge) |
| Rewrite existing `multi_llm/` impl pipeline? | **No** — **dual-lane** (AMB-01 default B) |

**Decision (HOW):** **Initiate Research Lane now** (packages + ledger + roles).  
Keep **Implementation Lane** (`MULTI_LLM_PROTOCOL.md` as today) unchanged until AMB-01 supersede.

---

## 2. HOW vs WHAT vs WHO vs CODE (this architecture)

| Layer | Owns |
|---|---|
| **WHAT** | Market math / features / outcomes (unchanged by multi-LLM) |
| **WHO** | CRT topology / contracts (unchanged) |
| **HOW** | *This doc + research_lane configs*: roles, cycle steps, package schema, stop rules, promise rung speech, scorecard knobs |
| **CODE** | Claude-only execution; optional later ledger validators |

Changing who reviews whom or package fields = **HOW** (edit protocol/schema).  
Changing CRT score formula = **WHAT**.  
Changing bar story synth = **CODE** (D-23).

---

## 3. Dual-lane HOW map

```text
                    YOU (HOW: capital + grants + bridge)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   LANE R — RESEARCH                    LANE I — IMPLEMENT
   multi_llm/research_lane/             multi_llm/ (existing)
   ERP P0–P7 · Promise Ladder           code epics · build_queue
              │                               │
   PROPOSAL → CRITIQUE → freeze               DeepSeek plan → …
   → Claude EXECUTION_EVIDENCE                → Claude EXECUTOR
   → DECISION (PL rung / next phase)          → tests + SESSION LOG
              │                               │
              └─────────── REPO TRUTH ─────────┘
                 findings · manifests · code
```

| Knob (HOW) | Default |
|---|---|
| `lane_default` | Dual-lane |
| `research_artifact_kinds` | PROPOSAL, CRITIQUE, EXECUTION_EVIDENCE, DECISION |
| `impl_handoff_block` | Existing §3 block in MULTI_LLM_PROTOCOL |
| `no_voting` | true |
| `claude_only_code` | true |
| `promise_rung_current` | PL-0 |
| `pl_upgrade_requires` | DECISION + You for PL-5; evidence for PL-3/4 |

---

## 4. Research-lane roles (HOW assignment)

| Role | Default model | Never does |
|---|---|---|
| **Principal** | You | Let LLM set capital |
| **Architect** | ChatGPT (or You) | Execute code; sole-sign PL-5 |
| **Hypothesis diversity** | Grok | Approve own ideas; write prod code |
| **Technical critic** | DeepSeek | Execute unfrozen experiments |
| **Executor** | Claude | Raise PL alone; skip factory for H_market |
| **Impl navigator** (Lane I only) | Gemini | Own research DECISION |

Gemini stays **Lane I** unless a research cycle explicitly invites quant critique as CRITIQUE.

---

## 5. Cycle HOW (8 steps — operational)

| Step | Actor | Writes kind | HOW stop |
|---|---|---|---|
| 1 | Architect | PROPOSAL | Unbound H rejected |
| 2 | Diversity (opt) | PROPOSAL counters | — |
| 3 | Critic | CRITIQUE | Blocking defects → no freeze |
| 4 | Architect + You | DECISION freeze | No RUN without freeze |
| 5 | Claude | EXECUTION_EVIDENCE | Must include run_manifest path when tools ran |
| 6 | Critic or Architect ≠ executor | CRITIQUE/DECISION review | H2 quote-check |
| 7 | Architect | DECISION branch | RETIRE/REPAIR/REPLICATE/EXPAND/PL |
| 8 | You | DECISION grant | P1…P7 / capital |

---

## 6. Package schema (HOW contract)

Machine schema: [`multi_llm/research_lane/package_schema.json`](../../multi_llm/research_lane/package_schema.json)

Minimum fields every package:

```text
package_id, kind, cycle_id, created_at, author_role, author_model,
claim_type (H_tool|H_market|process),
summary,
binds (entrypoint, lens, ACTIVE_VERSION, instruments) when applicable,
falsifier,
promise_rung_max_claim (≤ current unless DECISION upgrades),
artifact_paths[],
status (PROPOSED|ACCEPTED|REJECTED|SUPERSEDED)
```

Ledger: append-only [`research_cycle_ledger.jsonl`](../../multi_llm/research_lane/research_cycle_ledger.jsonl)

---

## 7. Initiation status (done this turn)

| Item | Status |
|---|---|
| HOW design doc (this file) | **INITIATED** |
| `multi_llm/research_lane/` tree | **INITIATED** |
| package_schema.json | **INITIATED** |
| research_cycle_ledger.jsonl seed (cycle RC-000) | **INITIATED** |
| Operator README + templates | **INITIATED** |
| Scorecard template | **INITIATED** |
| Lane I protocol rewrite | **NOT** done (by design) |
| Auto agent orchestration | **NOT** done |
| P1 harness code | **NOT** done (needs Implement P1 grant) |

---

## 8. How to run one research cycle (operator HOW)

### 8.1 Initiate plan command (model-separated)

```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok --cycle RC-001 --focus "..."
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model deepseek --cycle RC-001
# shortcuts: scripts/multi_llm/{grok,deepseek,gemini,claude,chatgpt}.ps1
# control plane: research.initiate_plan
```

Writes under `proposals/<model>/<cycle>/`:

| File | Purpose |
|---|---|
| `CONTEXT_BUNDLE.md` | Curated ERP docs only (`context_manifest.json`) |
| `PROMPT_FOR_<MODEL>.md` | Plan design prompt for that model |
| `PROPOSAL.md` | **Model-separated** proposal stub → paste model reply here |

**No full-repo scan. No LLM API.** You paste PROMPT+BUNDLE into the model.

### 8.2 After models return plans

```text
1. Overwrite each model's PROPOSAL.md with filled content
2. Optional DeepSeek CRITIQUE (template or critic initiate)
3. You: freeze DECISION
4. Claude: execute only if granted → EXECUTION_EVIDENCE
5. Ledger append (initiate_plan already logs INIT PROPOSED)
```

First cycle **RC-000** is process-only (architecture initiation). **RC-001** smoke packages may exist from initiate_plan.

---

## 9. Relation to Promise Ladder

| Package claim | Max PL speech without DECISION upgrade |
|---|---|
| H_tool integrity | PL-0 … PL-1 |
| H_market Stage-1 | PL-2 |
| Economic candidate | PL-3 only after DECISION |
| Capital | PL-5 only You |

---

## 10. Next HOW knobs (not initiated)

- Validator script `scripts/context/validate_research_ledger.py`  
- Nightly scorecard rollup  
- AMB-01 role-card merge into `roles/ROLE_*.md`  
- Wire packages to `docs/current-findings.md` gate  

---

*HOW owns the multi-LLM process. Reality owns truth. You own capital.*
