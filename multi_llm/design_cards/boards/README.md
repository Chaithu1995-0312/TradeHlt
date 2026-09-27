# Design boards (image-first)

> Reusable architecture boards for local infra prep.  
> **Policy:** AWS deferred · no live / Hot orders · DryRun + Shadow only.  
> **Saved:** 2026-09-18

| File | Board | Meaning |
|---|---|---|
| `infra-design-01-local-map.png` | System map | Design memory → Grok Bot → local `:8787`; AWS+Hot deferred |
| `infra-design-02-fail-closed-spine.png` | Spine (DC-003/004) | Ultron → Sherlock/Saul → Jarvis → ALLOW/DENY; decision ≠ execution |
| `infra-design-03-modes.png` | Modes | DryRun + Shadow yes; Hot/live AWS not yet |
| `infra-design-04-mode-lock.png` | Mode lock | Fail-closed DENY; Hot/AWS/edge-claim forbidden until User gate |

**Mirrors:** `C:\Users\Hi\Documents\grok_bot_design_boards\` · Grok Bot `/workspace/design_boards/`

## Reuse
Open these for infra prep, demos, or card freezes. Regenerate only if doctrine changes.
