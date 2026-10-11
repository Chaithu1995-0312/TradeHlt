# Contract and loader gate: evidence index

- Baseline (unchanged): `results/consumer_graph/` and `results/parity_audit/` at commit fb80a997eb (hashes in `baseline_hashes.txt`); baseline test failures in `baseline_failures.txt`.
- After: `results/consumer_graph_after/` (regenerated with `python scripts/analysis/consumer_graph.py --out results/consumer_graph_after`).
- Matrix: `BEFORE_AFTER.md`, `branch_status_matrix.csv` (`python scripts/analysis/branch_status_diff.py results/consumer_graph/consumer_registry.json results/consumer_graph_after/consumer_registry.json results/contract_gate`).
- Contract snapshot: `feature_contract.json`. Full-suite failures after the change: `after_failures.txt` (identical to the baseline list).
- Scope kept narrow: no change to the live hook, pipeline, CRT engine, production config, registry contents or models; ML inference not activated.
