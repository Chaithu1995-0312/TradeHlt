# DC-004 — Decision plane ≠ execution plane

| Field | Value |
|---|---|
| **ID** | DC-004 |
| **Status** | final |
| **Domain** | trading-infra |
| **Sources** | LambdaTradingCore; TradingECSShadow; DC-001 |
| **Frozen** | yes (User Final 2026-09-18) |

## Intention
Governance decisions must not place orders in-process.

## Bridge
Control plane (Lambda / local :8787 later) ↔ Execution adapters (DryRun / Shadow / Hot / ECS).

## Decision (proposed)
- **Decision plane:** risk + gates + audit log only.  
- **Execution plane:** separate process/task; modes DryRun | Shadow | Hot.  
- Hot stays **User-gated**; AWS path deferred (DC-001). Local/dev uses DryRun/Shadow first.

## Plug script (optional)
—

## Out of scope
Broker API details.

## Open questions
Does local Tradelatest :8787 count as decision plane only? (Recommend: yes.)

---

## Grounding C (2026-09-18) — pack + chat + code

### Design pack
- LambdaTradingCore / Trading: Lambda decides; ECS Fargate executes; DryRun/Shadow/Hot in TradingECSShadow pack.

### ChatGPT export
- Phase 9 / Jarvis updates: feature freeze → backtest; ECS mentioned as execution container; fail-closed blocks trades on error.
- Separation theme: Ultron computes risk; Jarvis enforces; not the same process as “place order” narrative.

### Implemented code
- `lambda_function.py`: ECS task launch after gates; not in-process broker calls in Jarvis module.
- `jarvis_execution.py`: outputs permission verdicts only.
- Execution modes appear in shadow/hot adapters under trading packs / LCP (Hot User-gated per prior doctrine).

### Verdict
**DC-004 (decision ≠ execution) SUPPORTED.** Local `:8787` as decision-plane-only remains consistent with DC-001 (AWS deferred).

### Residual
- Confirm Hot path never enabled without User gate (ops policy, not missing code comment hunt).

---:
**Frozen by User** Final on 2026-09-18. Doctrine locked; edits need re-freeze.
