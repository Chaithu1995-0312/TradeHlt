# Repository Memory Index

> **Policy:** [`ARCHITECTURE_MEMORY_POLICY.md`](ARCHITECTURE_MEMORY_POLICY.md)  
> **Hierarchy:** `CLAUDE.md` → these memory docs → deep companions → **source code (wins)**  
> **Last generation:** 2026-08-07

## Task → memory map

| Task domain | Memory document | Primary `src/` trees |
|---|---|---|
| Agent, modes, tools, REPL | [`agent-memory.md`](agent-memory.md) | `src/agent/` |
| Backtest, live hook, harnesses | [`runtime-memory.md`](runtime-memory.md) | `src/runtime/` |
| Feature schema, pipeline, formulas | [`feature-memory.md`](feature-memory.md) | `src/features/` |
| CRT / Gaussian / Zone / RR engines | [`engine-memory.md`](engine-memory.md) | `src/engines/` |
| Promotion, validators, registries | [`governance-memory.md`](governance-memory.md) | `src/governance/`, `src/config_layer/config_validator.py` |
| Full spine, layers, cross-subsystem | [`architecture-memory.md`](architecture-memory.md) | multi-package |

## Load rules

1. Load **one** subsystem memory for a focused task (two only if the task clearly spans both).  
2. Follow **Reading order** inside that file.  
3. Do **not** paste memory bodies into `CLAUDE.md`.  
4. Inventory Excels (file name + one-line summary) are **not** memory docs; open only when inventory completeness is required:
   - `results/analysis/src_business_functionality.xlsx`
   - `scripts_business_functionality.xlsx`
   - `docs/analysis/tests_functionality_inventory.xlsx`

## Deep detail (not always-loaded)

Full reverse-engineered map (file contracts, diagrams, glossary):  
[`docs/architecture/architecture-memory.md`](../architecture/architecture-memory.md)  
Load via architecture-memory **Related documents** when a full map is needed — not on every turn.
