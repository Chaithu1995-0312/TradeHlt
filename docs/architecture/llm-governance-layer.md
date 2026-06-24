# llm-governance-layer.md

> **Purpose:** Intentionally design the advisory-LLM layer — the part the historical
> architecture did **not** design for. Core doctrine: **LLMs are an advisory governance
> layer, never an execution authority.** This doc shows where that boundary is enforced
> today (with evidence), where LLM output may legitimately enter, where it is forbidden,
> and how to harden the boundary.
>
> Anchored to `v2_multi_2026_04`. Citations `file:line`.

---

## 1. Doctrine (the five-question lens, LLM edition)

| Question | LLM-layer answer |
|---|---|
| Replay deterministic? | **Yes** — no LLM call on the replay hot path. |
| Telemetry comparable? | Yes — advisory calls should emit enveloped events (target). |
| Auditable later? | Yes — agent writes `agent_audit.jsonl`; advisory calls logged. |
| Can an LLM reason about the event? | Yes — that is the LLM's *only* role: reason, advise. |
| **Execution authority isolated?** | **Yes — and this is the invariant the whole layer exists to protect.** |

---

## 2. Isolation evidence (current state — already good)

1. **Fusion LLM is a tie-breaker only.** `core/fusion_engine.py:9` ("uncertainty
   arbiter, fires ONLY when Gaussian score [is in the uncertainty band]"), `:18-19`
   ("LLM is NOT a replacement for Gaussian — it is a tie-breaker"), `:610` (Layer 3),
   with an explicit `llm_fired` flag (`:189`). Clear signals never touch the LLM.
2. **Fail-open neutral.** `config_layer/llm_scorer.py` circuit breaker: after
   `_FAIL_COUNT_DISABLE` failures it sets `CIRCUIT_OPEN = True` (`:294`) and returns
   **0.5 neutral abstention** for all subsequent calls (`:280-303`). Any path that
   cannot tolerate a neutral fallback is broken by design (CLAUDE.md §4).
3. **No LLM on the replay path.** The backtest candle loop calls no LLM; gates are
   Gaussian / drift / engine-based. See [`replay-governance.md`](replay-governance.md) §4.
4. **Agent write-authority is fenced.** `agent/executor.py:27` defines `_WRITE_ROOTS`
   (`configs/production/`, `logs/`, `results/`); `:35` rejects any write outside them
   (`:85` error). Write tools additionally require a `y/N` human confirm-gate.
5. **Promotion requires a human-grade gate.** `governance/promotion_manager.py:140`
   refuses any report whose `decision != "APPROVE"`; a fresh re-validation must *also*
   be APPROVE (`:161-164`). The LLM cannot auto-promote a config.

---

## 3. Where LLM output may enter (and where it must not)

| Surface | Allowed? | Constraint |
|---|---|---|
| Fusion uncertainty band | ✅ advisory | tie-breaker weight only; fail-open to neutral |
| Config-validation commentary | ✅ advisory | informs a human reviewer; does not set `decision` |
| Narrative / insight generation | ✅ advisory | prose only, no control flow |
| Agent (copilot/governance modes) | ✅ gated | path-guard + `y/N` confirm; deterministic `PLAN_REGISTRY` |
| Trade entry / exit | ⛔ forbidden | risk gate + engines decide; never an LLM |
| Config auto-promotion | ⛔ forbidden | requires APPROVE ValidationReport |
| Replay hot path | ⛔ forbidden | breaks determinism |

---

## 4. Hardening recommendations (Trd-M5)

1. **`GOVERNANCE_MODE` flag** *(Trd-M5 — not yet implemented in codebase)* — a
   process-level switch that disables *all* LLM inference outside the agent/validation
   contexts, so a misconfigured deployment can never accidentally call a model on a
   decision path.
2. **Decision-path assertions** — add explicit asserts/comments in `DecisionEngine`
   and the live path documenting "LLM is never consulted here," to fail fast if a
   future edit wires one in.
3. **`CIRCUIT_OPEN` is monitoring-only** — document that handlers must treat a circuit
   `0.5` as *abstention*, not a genuine score (`llm_scorer.py:282-283` already warns).
   Replace the module-level `FAIL_COUNT`/`CIRCUIT_OPEN` globals with injected state
   (Tier-2 coupling fix) so multiple contexts don't share a breaker.
4. **Advisory-call event contract** — every advisory LLM call emits an enveloped event
   (proposed `EventType` for advisory I/O) capturing prompt hash, model, latency, and
   the returned score/text. This makes the LLM's *own* reasoning replayable, comparable
   across runs, and auditable — satisfying questions 2–4 for the LLM itself.

---

## 5. The LLM advisory event contract (target shape)

```
envelope(
  event_type = "LLM_ADVISORY",        # additive EventType (Trd-M5)
  source     = "<fusion|validator|agent|narrative>",
  payload    = {
    "purpose":      "tie_break | validation_comment | narrative | agent_plan",
    "prompt_hash":  "<sha256[:8] of prompt>",   # not raw prompt (size/PII)
    "model":        "<llama.cpp|groq:model>",
    "result":       <score or text-hash>,
    "fired":        true/false,                 # entered uncertainty band?
    "circuit_open": false,                      # was fallback returned?
    "latency_ms":   <int>
  }
)
```

Because advisory calls are non-deterministic, their events carry `circuit_open` and
`fired` so replay-comparison tooling can **exclude** them from determinism diffs while
still auditing them. The advisory event never appears as an input to a gate.
