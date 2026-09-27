# DC-001 — Local plane vs AWS LCP

| Field | Value |
|---|---|
| **ID** | DC-001 |
| **Status** | draft |
| **Domain** | trading-infra |
| **Sources** | GROK_BOT_INFRA_REUSE_PLAN; User: AWS not yet |
| **Frozen** | no |

## Intention
Run trading infra without blocking on AWS.

## Bridge
Laptop demo / Tradelatest `:8787` ↔ later AWS `lambda_control_plane`.

## Decision
**AWS deferred.** Local control plane + design memory first. Do not duplicate LCP as a second Lambda stack inside Tradelatest.

## Plug script (optional)
—

## Out of scope
Live orders, terraform apply.

## Open questions
When to revisit AWS (User gate).
