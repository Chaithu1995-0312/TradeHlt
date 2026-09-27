# DESIGN_DRIVE.md — Grok Bot drives; User freezes

## How we work
1. **I drive** — scan packs, draft cards, name conflicts, propose freeze order.
2. **You freeze** — reply `final DC-00x` / `kill DC-00x` / `edit: …`.
3. **Scripts last** — only after `final/`, a tiny plug-in script if useful.
4. **No bulk PrivateLLM / no AWS** until you reopen those gates.

## Lanes (from ProjectDiscussion + Chaithu)
| Lane | Packs | Intent |
|---|---|---|
| **T — Trading spine** | Trading, LambdaTradingCore, TradingECSShadow, Chaithu/lambda_control_plane | Fail-closed pipeline, edge path |
| **A — Agents** | Jarvis, CodingAgent, AIAgent* | Orchestration / gates / tools |
| **M — Memory** | PrivateLLM, chatgptextractor, design_cards | Don’t lose intention |
| **U — Surfaces** | TradingFrontEnd, TradingMobile, Jarvis UI | Human bridge |
| **$ — Income** | earntool, Freelancetool, IG Reel sketch | Monetize without fake edge |
| **X — Satellite** | Video*, Web*, PPTX, Cloud site | Park unless bridges T/A/M |

## Wave 1 (active) — Trading + Memory spine
See `draft/` cards DC-001…DC-007. Freeze targets this week: **DC-003, DC-004, DC-005** (trading doctrine).

## TruthConflicts to resolve with User
- **TC-1:** Jarvis UI = read-only / no buttons vs TradingFrontEnd = Accept/Reject trades.
- **TC-2:** UnifiedTool “AI Trading module inside dashboard” vs dedicated fail-closed LCP — one authority?

## Next after Wave 1 freeze
Wave 2 agents (Jarvis gate vs UI). Wave 3 income Reel. Wave 4 satellites only on ask.

## Boards
Image-first infra boards: [boards/](boards/) — local map, spine, modes. Prep doc: ../GROK_BOT_LOCAL_INFRA_PREP.md.

## Freeze log
- **2026-09-18:** User `Final` → DC-003 + DC-004 moved to `final/`. P4 DryRun plug next. AWS/Hot still deferred.
