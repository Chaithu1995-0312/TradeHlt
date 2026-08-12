# Initiate plan commands (model-separated)

> **No full-repo scan.** Context = curated list in `context_manifest.json` (ERP docs already gathered).  
> **No LLM API call** — prepares PROMPT + CONTEXT_BUNDLE + empty PROPOSAL for you to paste into each model.

## Python (canonical)

```bash
# one model
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model deepseek --cycle RC-001 --focus "P1 harness"
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model claude --focus "Implement P1"
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model gemini
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model chatgpt

# all models, same cycle id
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model all --cycle RC-001
```

## PowerShell shortcuts

```powershell
.\scripts\multi_llm\grok.ps1
.\scripts\multi_llm\deepseek.ps1 -Cycle RC-001 -Focus "attack P1 design"
.\scripts\multi_llm\claude.ps1 -Focus "P1 implement plan"
.\scripts\multi_llm\gemini.ps1
.\scripts\multi_llm\chatgpt.ps1 -Focus "architect next cycle"
```

## Output layout (per model)

```text
multi_llm/research_lane/proposals/<model>/<cycle_id>/
  README.md
  CONTEXT_INDEX.md      # list of curated docs
  CONTEXT_BUNDLE.md     # concatenated context (paste with prompt)
  PROMPT_FOR_<MODEL>.md # plan design prompt
  PROPOSAL.md           # model-separated proposal stub → fill from model reply
```

## Operator flow

```text
1. Run initiate for model(s)
2. Open PROMPT_FOR_*.md + CONTEXT_BUNDLE.md
3. Paste into that LLM chat
4. Paste model reply into that model's PROPOSAL.md (overwrite stub)
5. Optional: deepseek initiate for critic plan / use templates/CRITIQUE.md
6. You DECISION freeze → Claude execute (code) only if granted
```

## Edit what context is passed

Edit `multi_llm/research_lane/context_manifest.json` — add/remove paths under `docs/`.  
Do **not** point at whole `src/` (defeats the design).

## Master prompt template

`multi_llm/research_lane/prompts/PLAN_DESIGN_PROMPT.md`
