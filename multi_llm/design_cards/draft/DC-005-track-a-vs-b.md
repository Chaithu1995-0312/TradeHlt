# DC-005 — Track A (institutional) vs Track B (opportunistic)

| Field | Value |
|---|---|
| **ID** | DC-005 |
| **Status** | draft |
| **Domain** | trading-infra |
| **Sources** | ProjectDiscussion/Trading CANONICAL (dual-track) |
| **Frozen** | no |

## Intention
Preserve capital-first path without deleting exploratory path.

## Bridge
Same ingest/features → split governance strictness → possibly different execution modes.

## Decision (proposed)
Keep **two tracks** in design language:
- **A — Institutional / capital preservation:** full Ultron+Jarvis, fail-closed.  
- **B — Opportunistic:** soft-gated; cannot silently promote to A without User freeze + measurement.

Edge work may *research* on B; **money authority** only via A after evidence.

## Plug script (optional)
—

## Out of scope
Sizing formulas.

## Open questions
Is Track B allowed to reach Shadow execution, or research-only?
