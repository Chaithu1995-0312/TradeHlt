# OSS Lab — Isolated Open-Source Integration & Comparative Benchmark Laboratory

| Field | Value |
|---|---|
| Status | **LAB ONLY** — architecture **APPROVED**, implementation staged; blocked on Codebase-Memory pin/security gate before first real benchmark |
| Approval | [`governance/ARCHITECTURE_APPROVAL.md`](governance/ARCHITECTURE_APPROVAL.md) |
| Authority | Research / evidence generation only (§6.5 Authority Ladder) |
| Design | [`docs/governance/OSS_INTEGRATION_ARCHITECTURE.md`](../docs/governance/OSS_INTEGRATION_ARCHITECTURE.md) |
| Plan | [`docs/implementation_plan/oss-integration-benchmark-lab.md`](../docs/implementation_plan/oss-integration-benchmark-lab.md) |
| Default trust ceiling | **T3** (runtime/execution adapter). **T4 production authority is forbidden** without independent architecture decision + certification. |

## Purpose

Accelerate **generic** capabilities (research infra, event-driven replay, ML/RL experimentation)
by borrowing mature open source, while **preserving** Tradelatest's unique semantic, market,
CRT, fusion, decision, Ultron capital, and governance authorities.

```text
TRADLATEST UNIQUE SEMANTICS
    ↓
TRADLATEST AUTHORITY
    ↓
OSS CAPABILITY ADAPTER  (this package)
    ↓
COMMON EVIDENCE / MEASUREMENT CONTRACT
```

Open-source projects are **capability providers**, not authorities.

## Layout

| Path | Role |
|---|---|
| `registry/` | Machine-readable OSS capability registry (candidates + decisions) |
| `contracts/` | Canonical schemas (TradeRecord, DatasetManifest, RunManifest, MetricCell) |
| `adapters/` | Thin per-engine adapters (`tradelatest`, `qlib`, `nautilus`, `finrlx`) |
| `datasets/` | Dataset pins / manifests (bind existing corpus authority; no silent re-download) |
| `scenarios/` | Benchmark scenario definitions |
| `runners/` | Isolated lab runners (never import into production spine) |
| `metrics/` | Independent metric calculators over normalized evidence |
| `evidence/` | Run artifacts (gitignored runtime; manifests committed) |
| `reports/` | Comparison matrices |
| `reproducibility/` | Fingerprints, triple-run proofs |
| `governance/` | Lifecycle states, risk/UNKNOWN registers |

## Hard rules

1. **Never** `pip install` + import throughout the repository.
2. All external OSS stays **behind an adapter** in this tree.
3. Production spine (`src/core`, CRT, Fusion, Decision, Ultron, ontology) **must not** import from `oss_lab/`.
4. `oss_lab` may import from `src/` for **reuse** (corpus guards, cost models, forward-walk, provenance) — adapters map **out**, never redefine authority **in**.
5. Missing fields = `UNKNOWN` / `NOT_AVAILABLE` / `NOT_APPLICABLE` with provenance — never invent.
6. Research result ≠ production finding ≠ production authority.

## Phases (status)

| Phase | Status |
|---|---|
| 0 Discovery | DONE (architecture doc) |
| 1 OSS registry + contracts | SHIPPED (this tree) |
| 2 Canonical benchmark schema | SHIPPED |
| 3 Tradelatest baseline adapter | SCAFFOLD |
| 4 Independent metrics layer | SCAFFOLD |
| 5–7 Qlib / Nautilus / FinRL-X | PLANNED (stubs only; no deps installed) |
| 5b Monitor scan 2026-08-12 | REGISTERED: Codebase-Memory, LEAN, Infigraph, VectorBT, RIG |
| 8 Lookahead / cost / fill certs | DESIGNED |
| 9 Semantic OS integration | DESIGNED (mapping stub) |
| 10 Governance promotion path | DESIGNED |

### Tracks

| Track | Input | Output | Engines |
|---|---|---|---|
| **EXECUTION** | DatasetManifest (XAUUSD pin) | BenchmarkTradeRecord | Tradelatest, Nautilus, LEAN, Qlib, FinRL, VectorBT (deferred) |
| **REPO_INTELLIGENCE** | Local repository tree | StructuralFactRecord | Codebase-Memory, Infigraph, local pyan/graph |

See [`governance/evaluation_queue.md`](governance/evaluation_queue.md).

## Quick smoke

```bash
python -m pytest tests/test_oss_lab.py -q
python -c "from oss_lab.registry.loader import load_registry; print(load_registry().summary())"
```
