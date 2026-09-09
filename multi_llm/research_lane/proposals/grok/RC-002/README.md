# Plan initiation — `grok` / `RC-002`

## How to use
1. Open `PROMPT_FOR_GROK.md`
2. Attach or paste `CONTEXT_BUNDLE.md` (curated docs only)
3. Send to **grok**
4. Replace `PROPOSAL.md` with the model's filled PROPOSAL
5. Optional: run critic model with a new `--model deepseek` package, or fill CRITIQUE template

## Files
- `CONTEXT_INDEX.md` — doc list (8 entries; missing=0, truncated=0)
- `CONTEXT_BUNDLE.md` — concatenated context
- `PROMPT_FOR_GROK.md` — plan design prompt
- `PROPOSAL.md` — model-separated PROPOSAL package (fill)

## Commands
```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok --cycle RC-002 --kind PROPOSAL
```
