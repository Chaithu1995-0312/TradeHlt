# Research Lane — Role HOW Map

> Dual-lane default (AMB-01 B). Does **not** replace `multi_llm/roles/ROLE_*.md` for Implementation Lane.

| Role | Default model | Lane | Writes | Never |
|---|---|---|---|---|
| **Principal** | You | Both | DECISION (capital, phase grants) | Delegate capital to LLM |
| **Architect** | ChatGPT | Research | PROPOSAL, DECISION (freeze/branch drafts) | Sole-sign PL-5; write prod code |
| **Hypothesis diversity** | Grok | Research | PROPOSAL (counters, new families) | Approve own H; execute |
| **Technical critic** | DeepSeek | Research | CRITIQUE | Execute unfrozen RUN |
| **Executor** | Claude | Both | EXECUTION_EVIDENCE; code/tests | Raise PL alone; invent metrics |
| **Impl planner** | DeepSeek | Implementation | plan handoffs | Own ERP DECISION |
| **Impl navigator** | Gemini | Implementation | gaps/next | Own ERP DECISION |
| **Impl interpreter** | ChatGPT | Implementation | explain/expand | Execute code |

## Handoff rule

```text
Same problem → different roles → different package kinds
Never: four models answer same prompt and vote
```

## Speech rule

| Role output | Max wealth language |
|---|---|
| Any PROPOSAL/CRITIQUE | PL-0 wording unless package binds higher *after* DECISION |
| DECISION upgrading PL | Must cite EXECUTION_EVIDENCE package_ids |
