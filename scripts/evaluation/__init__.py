"""
scripts/evaluation/ — RAG benchmark evaluation suite.

Provides:
  - benchmark_100.json : Gold standard dataset of 100 questions
  - run_benchmark.py   : Automated evaluation runner
  - report.py          : Markdown/JSON report generator

Usage:
    python scripts/evaluation/run_benchmark.py
    python scripts/evaluation/report.py results/evaluation/latest_run.json
"""