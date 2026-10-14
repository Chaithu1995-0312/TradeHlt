# Research SSOT Framework — MVP v0.1

A read-only-first orchestration framework for turning one research intent into a dependency tree and one evidence-backed final output.

## What this MVP does

- Treats `manifest.json` as the canonical registry for approved intents and reusable analysis nodes.
- Scans a repository's Python scripts without executing them.
- Extracts declared docstrings, imports, function/class names, likely file reads/writes, and SHA-256 code identity.
- Builds a deterministic dependency tree for a requested intent.
- Validates missing dependencies and duplicate node IDs.
- Emits one Markdown final report and one JSON run record.
- Explicitly labels inferred intent as a candidate, not verified fact.

## What it deliberately does not do yet

- It does not execute arbitrary repository scripts or shell commands.
- It does not infer economic truth or promote trading rules.
- It does not merge/delete scripts automatically.
- It does not treat a script name/docstring as proof of runtime behavior.
- It does not reuse an artifact unless its identity/contract matches. Artifact cache integration is a later phase.

## Quick start

Requires Python 3.11+ and standard library only.

```bash
python -m research_ssot.cli inventory --root /path/to/repo --out results/script_inventory.json
python -m research_ssot.cli plan --manifest examples/manifest.json --intent crt_expiry_diagnosis --out results/plan.json
python -m research_ssot.cli report --plan results/plan.json --inventory results/script_inventory.json --out results/final_report.md
```

Set `PYTHONPATH=src` when running from the project root, or install the package in editable mode with `pip install -e .`.

## Contract

Each node has a stable `node_id`, declared purpose, operation type, input/output contracts, dependencies, and an execution policy. The intent tree is a plan, not permission to execute. Execution adapters must be explicitly registered and allowlisted in a later phase.

## Intended progression

1. **v0.1 inventory + planning** (this MVP)
2. Add approved script contracts for existing `scripts/analysis/` scripts
3. Add output/artifact identity and compatibility checks
4. Add allowlisted adapters for safe, reproducible execution
5. Add evidence assembly, falsification checks, and terminal epistemic status

## Safety and research governance

- `UNKNOWN` is not silently converted to success.
- Missing required inputs/contracts block a node.
- Existing artifacts are not assumed valid merely because they exist.
- Observations, inferred intent, measurements, and findings remain distinct.
- Production configuration, execution policy, and deployment are outside this framework's authority.
