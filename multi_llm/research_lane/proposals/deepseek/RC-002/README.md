# Plan initiation — `deepseek` / `RC-002`

## How to use
1. Open `PROMPT_FOR_DEEPSEEK.md`
2. Attach or paste `CONTEXT_BUNDLE.md` (curated docs only)
3. Send to **deepseek**
4. Replace `CRITIQUE.md` with the model's filled CRITIQUE
5. Optional: run critic model with a new `--model deepseek` package, or fill CRITIQUE template

## Files
- `CONTEXT_INDEX.md` — doc list (8 entries; missing=0, truncated=0)
- `CONTEXT_BUNDLE.md` — concatenated context
- `PROMPT_FOR_DEEPSEEK.md` — plan design prompt
- `CRITIQUE.md` — model-separated CRITIQUE package (fill)

## Commands
```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model deepseek --cycle RC-002 --kind CRITIQUE
```
