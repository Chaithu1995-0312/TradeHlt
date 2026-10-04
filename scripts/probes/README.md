# scripts/probes/

Preferred home for **one-shot / ephemeral investigation scripts** (LLM or human).

- Category default: `PROBE` · lifecycle `EPHEMERAL`
- Do **not** put new probes at repo root as `_*.py` (grandfathered only)
- Register via SITS after create:

```text
python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
python scripts/governance/seed_script_registry.py
python scripts/analysis/generate_script_matrix.py
```

Production logic still belongs in `src/` — probes should stay temporary or graduate via extract (PR-6).
