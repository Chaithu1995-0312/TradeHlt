# DC-007 — UnifiedTool vs dedicated trading plane

| Field | Value |
|---|---|
| **ID** | DC-007 |
| **Status** | draft |
| **Domain** | trading-infra |
| **Sources** | UnifiedTool CANONICAL; Trading/LCP packs |
| **Frozen** | no |

## Intention
Avoid a second “AI Trading Tool” inside a mega-dashboard fighting the fail-closed plane.

## Bridge
Product surface (Unified dashboard) ↔ Trading spine (DC-003).

## Decision (proposed)
**Trading authority lives in the trading spine (DC-003/004), not inside UnifiedTool.**  
UnifiedTool may later *display* or *link* — it must not own risk/gate/execution.

## Plug script (optional)
—

## Out of scope
Building Unified dashboard.

## Open questions
Keep UnifiedTool pack as satellite ($/content modules only)?
