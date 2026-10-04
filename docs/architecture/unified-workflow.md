# unified-workflow.md — The One Cycle (P0–P8)

> **This is the operating core of the repo. Every task, mode, and agent is a front door into
> this same cycle — there are no parallel workflows.** Pairs with
> [`Claude-deepseek.md`](../../Claude-deepseek.md) §4 and `CLAUDE.md`. The RAG machinery that
> powers P3 is specified in [`docs/architecture/retrieval-layer.md`](retrieval-layer.md).

---

## 1. Master diagram — one cycle, two rings, five perpendiculars

```
                    ┌─────────────────────────────────────────────┐
                    │   OUTER RING — STRATEGY LIFECYCLE (TSA §0.4) │
                    │   weeks / months · one stage at a time       │
                    └─────────────────────────────────────────────┘

   [1] Semantics ──► [2] Features ──► [3] Strategy pkg ──► [4] Research
        ▲                                                        │
        │                                                        ▼
   [9] Improve ◄── [8] Ledger ◄── [7] Production ◄── [6] Promote ◄── [5] Qualify
        │
        │   every stage is realized by many iterations of the
        ▼   inner ring below

┌──────────────────────────────────────────────────────────────────────────┐
│   INNER RING — CHANGE LOOP (TSA §0.4.1)                                  │
│   one session · one task · ~100–130K tokens                             │
│                                                                          │
│     P0 Boot ──► P1 Orient ──► P2 Frame ──► P3 Retrieve ──► P4 Plan        │
│     P5 Execute ──► P6 Verify ──► P7 Record ──► P8 Activate                │
│                                                                          │
│   W4 Multi-LLM  → N agents run P2–P6 in parallel, merge at P7            │
│   W5 Agent      → triggers P2 · confirms P5                              │
│   W6 RAG        → the machinery inside P3                                │
│   W7 Compliance → the rule inside P6                                     │
│   W8 Session    → the artifact of P7                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The inner ring — input · output · rule per phase

| Phase | Input | Output | Hard rule |
|---|---|---|---|
| P0 Boot | repo | identity context (`goal.md`, `ACTIVE_VERSION`, `active_models.yaml`) | fixed boot; never grows |
| P1 Orient | task hint | shape map (`module-roles.generated.md` + `code-map.generated.md`) | Tier 1 only for architecture tasks; else Tier 1.5 |
| P2 Frame | intent | task class + change surface | no execution before intent is named |
| P3 Retrieve | frame | 10–20 verbatim spans + source paths | never blend CURRENT / INTENDED / RECORDED; never boot all files |
| P4 Plan | retrieved evidence | change proposal + verification plan | every claim has a `path:line` citation |
| P5 Execute | plan | diff | writes require confirmation (W5) |
| P6 Verify | diff | green floor + drift classification | green floor passes; drift classified, not resolved silently |
| P7 Record | verified change | findings + session log + regenerated maps | every change lands a finding or an update |
| P8 Activate | recorded change | `ACTIVE_VERSION` bump OR research result | only PromotionManager writes `ACTIVE_VERSION` |

---

## 3. Agent modes as P2 entry points

```
python -m src.agent.cli <mode>

pipeline_mode   ──► enters at P2, scope = production
copilot_mode    ──► enters at P2, scope = live signal review
governance_mode ──► enters at P2, scope = promotion decision
findings_mode   ──► enters at P2, scope = research synthesis
log_query_mode  ──► enters at P2, scope = observability
ops_mode        ──► enters at P2, scope = incident review
truth_mode      ──► enters at P2, scope = semantic grounding

                       all share P3–P8
```

Every mode is a front door into the same cycle. None is a separate workflow.

---

## 4. Scope variants — same cycle, different P8

| Scope | P8 = | Gate |
|---|---|---|
| Production | PromotionManager → `ACTIVE_VERSION` bump | ConfigValidator APPROVE + green floor + SESSION LOG |
| Research (W3) | measurement result → findings | same P3–P6; **no promotion import allowed** (`tests/test_runtime_boundary.py`) |
| Compliance (W7) | drift classification (ALIGNED / DOC_DRIFT / CODE_DRIFT / AMBIGUOUS) + audit-trail entry | no truth tier blended; both sides cited |
| Multi-LLM (W4) | N agents run P2–P6 in parallel · P7 merges via `HANDOFF.md` | each agent's P4 is the handoff artifact |

---

## 5. Budget — how P0 + P1 spend the window

- **~100–130K tokens** per inner iteration.
- **Boot ≤ 200K window**: Tier 1 (`~53K`) only for architecture tasks; narrow tasks use Tier 1.5 (`~10K`).
- Tier 0 identity is always loaded and never grows.