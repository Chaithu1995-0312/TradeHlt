"""
Expansion Engine — controlled trade frequency scaling.
Architecture:
  LLM Pattern Extractor (offline, one-shot)
    → expansion_plan.json
  ExpansionEngine (deterministic loop)
    → ConfigMutator: tweak ONE param per step
    → BacktestRunner: evaluate
    → Evaluator: score(pnl, drawdown, trades)
    → stop if guardrails breached
  Output: SAFE / BALANCED / AGGRESSIVE config variants
"""