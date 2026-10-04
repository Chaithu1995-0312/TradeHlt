# Tradelatest

Tradelatest is a file-backed quantitative trading system. It reads M15 price candles, scores
each candle through four independent engines (CRT, Gaussian, Zone Gate, RR), combines those
scores into one decision, plans the trade (entry / stop / target), and lets a risk gate
approve or reject it. Nothing reaches production without passing governance (validation,
SHA-256 hashing, an append-only audit trail). No database, no message broker, no cloud
dependency. The system is being migrated toward an event-driven, replay-governed,
explainable, advisory-AI architecture — see [`docs/architecture/goal.md`](docs/architecture/goal.md).

> **Priorities (profit is *not* the top goal):**
> replay correctness > explainability > telemetry continuity > advisory-AI > (structure validity ≠ execution validity).

---

## Quick Start

**Prerequisites:** Python ≥ 3.10.

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 2. Install the package (exposes the src/ packages on the path)
pip install -e .
```

> ⚠️ `pyproject.toml` pins only Python ≥ 3.10 and does **not** declare third-party
> dependencies. The runtime needs `numpy`, `scipy`, `scikit-learn`, and `pandas` available
> in the environment — install them if they aren't already present.

**Run your first backtest** (small sample instrument, ~2k candles, finishes in seconds):

```bash
python src/runtime/backtest_v2.py --csv data/AUDUSD_M15.csv --output results
```

Output lands in `results/run_<timestamp>_<instrument>/` (summary JSON, events JSONL, report)
and telemetry streams in `logs/`.

**Run the tests:**

```bash
pytest                            # full suite (testpaths = tests/)
pytest -k engine_runner           # one area
```

**The full command catalog** (data prep → tuning → validation → promotion → backtest → live
→ training) is auto-generated in [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md).

---

## Working in this repo (start here)

- **If you're an LLM / agent:** the authoritative operating manual is
  [`CLAUDE.md`](CLAUDE.md). Begin with the **cold-start recipe** in
  [`docs/architecture/trigger-vocabulary.md`](docs/architecture/trigger-vocabulary.md), then
  use the trigger vocabulary (`Orient`, `Map`, `Continue`, …).
- **If you're a human:** read the one-paragraph goal above, run the Quick Start, then use the
  docs map below to find what you need.

---

## Docs map

Docs live in four tiers. **Each doc owns one thing** — when two sources seem to disagree, the
*authoritative source* wins (last column).

### Tier 1 — Operating rules (root)
| Doc | Owns |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **The authoritative operating manual** — conventions, how to add features, response ritual, constraints. Read first. |
| `README.md` (this file) | The front door — Quick Start + docs map. |
| [`assistant_project.md`](assistant_project.md) | Migration doctrine header + the append-only SESSION LOG. |
| [`AGENTS.md`](AGENTS.md) | Pointer to `CLAUDE.md` (kept only for tools that look for `AGENTS.md`). |

### Tier 2 — Reference (`docs/`)
| Doc | Owns |
|---|---|
| [`docs/reference/architecture.md`](docs/reference/architecture.md) | Tech stack, directory tree, data flow, CLI entry points. |
| [`docs/reference/conventions.md`](docs/reference/conventions.md) | Naming, folder placement, error-handling modes, anti-patterns. |
| [`docs/reference/schemas.md`](docs/reference/schemas.md) | Dataclasses, enums, the canonical feature schema, JSONL line schemas. |
| [`docs/reference/config-reference.md`](docs/reference/config-reference.md) | Every key in the production config + rehash rules. |
| [`docs/reference/testing.md`](docs/reference/testing.md) | pytest layout, how to run, coverage expectations. |
| [`docs/reference/governance.md`](docs/reference/governance.md) | Promotion workflow, the APPROVE gate, rollback. |
| [`docs/architecture/signal-flow.md`](docs/architecture/signal-flow.md) | **Authoritative** candle→order step-by-step flow. |
| [`docs/reference/agent-reference.md`](docs/reference/agent-reference.md) | The AI automation agent (intents, tools, plan registry). |
| [`docs/reference/cli-matrix.md`](docs/reference/cli-matrix.md) | **Authoritative** generated command catalog. |

### Tier 3 — Architecture / migration (`docs/architecture/`)
| Doc | Owns |
|---|---|
| [`GOAL.md`](docs/architecture/goal.md) | **Authoritative north-star** — purpose, happy flow, invariants, deviation policy. |
| [`intelligence-compounding.md`](docs/architecture/intelligence-compounding.md) | **Doctrine** (CLAUDE.md §6.1 long-form) — repository as intelligence substrate: utility function, entropy principle, goal-first ROI chain, checklists, evolution path. |
| [`event-taxonomy.md`](docs/architecture/event-taxonomy.md) | **Authoritative** event catalogue + CRT state graph (9 states). |
| [`CODEBASE_STATE_MAP.md`](docs/architecture/codebase-state-map.md) | Module map + hidden-coupling inventory. |
| [`service-boundary-map.md`](docs/architecture/service-boundary-map.md) | Candidate services (ins → flow → outs). |
| [`REPLAY_GOVERNANCE.md`](docs/architecture/replay-governance.md) | Determinism / replay-comparability contract. |
| [`LLM_GOVERNANCE_LAYER.md`](docs/architecture/llm-governance-layer.md) | LLM-is-advisory isolation evidence + hardening. |
| [`TRIGGER_VOCABULARY.md`](docs/architecture/trigger-vocabulary.md) | LLM ownership commands + cold-start recipe. |
| `docs/architecture/services/` · `docs/implementation_plan/` | Per-service docs · session plans. |

### Tier 4 — Historical analyses (`docs/analysis/`)
Point-in-time snapshots and audits — **not living docs**. See
[`docs/analysis/README.md`](docs/analysis/README.md) for the dated catalog.

---

**Authoritative-source quick rule:** config truth = `configs/production/*.json` · flow =
`SIGNAL_FLOW.md` · events + CRT states = `event-taxonomy.md` · goal/invariants = `GOAL.md` ·
operating rules = `CLAUDE.md` · commands = `CLI_MATRIX.md`.
