# Plan initiation — `chatgpt` / `RC-002`

## How to use
1. Open `PROMPT_FOR_CHATGPT.md`
2. Attach or paste `CONTEXT_BUNDLE.md` (curated docs only)
3. Send to **chatgpt**
4. Replace `DECISION.md` with the model's filled DECISION
5. Optional: run critic model with a new `--model deepseek` package, or fill CRITIQUE template

## Files
- `CONTEXT_INDEX.md` — doc list (10 entries; missing=0, truncated=0)
- `CONTEXT_BUNDLE.md` — concatenated context
- `PROMPT_FOR_CHATGPT.md` — plan design prompt
- `DECISION.md` — model-separated DECISION package (fill)

## Commands
```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model chatgpt --cycle RC-002 --kind DECISION
```
