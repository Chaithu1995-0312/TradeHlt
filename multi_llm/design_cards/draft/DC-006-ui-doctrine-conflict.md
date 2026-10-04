# DC-006 — TruthConflict: Jarvis read-only UI vs TradingFrontEnd Accept/Reject

| Field | Value |
|---|---|
| **ID** | DC-006 |
| **Status** | draft |
| **Domain** | surfaces |
| **Sources** | ProjectDiscussion/Jarvis vs TradingFrontEnd CANONICAL |
| **Frozen** | no |

## Intention
One clear human-surface doctrine so we don’t build two contradictory UIs.

## Bridge
Operator ↔ system state / decisions.

## Decision (options — User must pick)
| Option | Meaning |
|---|---|
| **J** | Jarvis doctrine wins: read-only intel; no accept/reject in UI; execution only via gated plane |
| **F** | FrontEnd doctrine wins: human Accept/Reject is part of the loop |
| **Split** | Jarvis = mobile intel; FrontEnd = research desk only — **not** live gate |

## Plug script (optional)
—

## Out of scope
Building either UI now.

## Open questions
Which option? Default recommendation while AWS deferred: **Split** (intel ≠ order button).
