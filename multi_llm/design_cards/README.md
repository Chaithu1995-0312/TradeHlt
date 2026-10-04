# design_cards — plug-in / plug-out design memory

Small finalized (or draft) design units. **Not** the PrivateLLM monolith.

| Folder | Meaning |
|---|---|
| `draft/` | Intention captured, not frozen |
| `final/` | User-frozen — safe to build from |
| `_templates/` | Card shape |

## Card rules
- One decision / bridge / service boundary per card
- Max ~1 screen of markdown
- Status: `draft` | `final` | `killed`
- Scripts under `../scripts_design/` may read cards; nothing here calls AWS

## Add a card
```bash
python multi_llm/scripts_design/new_card.py --id DC-001 --title "Local control plane vs AWS LCP"
```
