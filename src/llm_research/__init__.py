"""
LLM Research Pipeline — offline pattern extraction → policy generation → forward validation.

Architecture:
  historical_data.csv
    → PatternExtractor (LLM, offline) → policy.json
    → PolicyBuilder (converts rules to deterministic code)
    → ForwardTester (runs 3 modes: baseline / LLM policy / hybrid)
    → Evaluator (generalization, overfitting, contribution analysis)

Key principle: LLM is used ONLY in pattern extraction (offline, frozen).
Policy rules are converted to deterministic code before forward testing.
LLM is NEVER used during forward test execution.
"""