# MODE_LOCK.md — local prep policy (P3)

> **Board:** `design_cards/boards/infra-design-04-mode-lock.png`  
> **Date:** 2026-09-18  
> **Owner:** Grok Bot (policy/docs). Claude implements code hooks if needed.  
> **Hard:** fail-closed default = **DENY**

## Allowed (now)

| Mode / surface | Meaning |
|---|---|
| **DryRun** | Simulate fills / path — **no broker** |
| **Shadow** | Observe / compare — **no live orders** |
| Local control plane `127.0.0.1:8787` | Dashboard / API only |
| LCP (`D:\Chaithu\lambda_control_plane`) | **Read-only doctrine** — schemas, spine, journals |

## Forbidden until User gate

- Hot / live orders  
- `terraform apply` / AWS deploy of LCP  
- ECS broker launch  
- Claiming trading **edge** from infra standing up alone  
- Silent upgrade DryRun → Hot

## Runbook rules

1. Any script or ticket that can place orders must default mode to `DryRun` or `Shadow`.  
2. `Hot` requires an explicit User message naming Hot **and** a separate approval — never inferred.  
3. Boot of `:8787` is **not** authorization to trade.  
4. If mode is missing / unknown → treat as DENY (fail-closed).

## Code hook (not done yet)

No dedicated `execution_mode` gate found in a quick `src/execution` / `src/live` scan this turn.  
**Next (P4 / Claude ticket after DC freeze):** add a single mode enum + refuse Hot in local prep profiles. Grok Bot will draft the ticket; Claude implements.

## Evidence

- Boards 01–04 under `design_cards/boards/`  
- P2 boot-check: `boards/bootcheck-8787-RESULT.md` (HTTP 200, then stopped)
