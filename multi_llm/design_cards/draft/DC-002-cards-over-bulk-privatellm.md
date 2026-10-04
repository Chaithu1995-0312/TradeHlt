# DC-002 — Design memory: cards over bulk PrivateLLM

| Field | Value |
|---|---|
| **ID** | DC-002 |
| **Status** | draft |
| **Domain** | memory |
| **Sources** | User 2026-09-18 pivot; Chaithu/PrivateLLM census |
| **Frozen** | no |

## Intention
Finalize designs across chats/drivers without standing up the full MODE-1/FAISS stack.

## Bridge
ChatGPT corpus / ProjectDiscussion packs ↔ small `design_cards` ↔ optional later PrivateLLM.

## Decision
**Prefer extract → finalize → tiny plug scripts.** PrivateLLM is optional backend later; not the gate for progress. Invalid/missing API keys must not block design finalization.

## Plug script (optional)
`scripts_design/new_card.py`, `scripts_design/list_cards.py`

## Out of scope
Replacing Tradelatest governance; AWS; IG posting.

## Open questions
Which 5 cards to finalize first from ProjectDiscussion shortlist.
