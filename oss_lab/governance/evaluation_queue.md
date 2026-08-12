# OSS Evaluation Queue (post monitor scan)

Updated: 2026-08-12  
Authority: RESEARCH_LAB_ONLY  

## Initiative status

| Field | Value |
|---|---|
| Architecture | **APPROVED** — see [`ARCHITECTURE_APPROVAL.md`](ARCHITECTURE_APPROVAL.md) |
| Implementation | **Safely staged** (registry, contracts, stubs, scenarios) |
| G1–G6 Codebase-Memory | **PASS** (2026-08-12) → lifecycle **`APPROVED_FOR_LAB`** |
| Pin | **v0.10.2** / `b377c62a…` SHA-256 verified |
| SLSA residual | **ATTEMPTED_TOOLS_ABSENT** — cosign bundle saved; gh/cosign not on PATH |
| First lab run | **`RI-RUN-20260812T214500Z`** — REPO-INTEL-QA-V1 **12/12 pass** (MEASURED, unsealed) |
| Index | 34,572 nodes · 120,458 edges · ~71s fast mode |
| Waiting on | Optional SLSA when tools available; ingestion-contract design only if we promote usefulness |
| Semantic OS writes | **Still forbidden** (not mutated this run) |
| Install | Binary extracted to `tools/oss_lab/codebase-memory/v0.10.2/` (CLI only; no agent config install) |

## Can we reuse the existing OSS lab?

**Yes — fully for governance and execution; with a thin extension for repo-intel.**

| Lab piece | Reuse for monitor candidates? |
|---|---|
| Registry + trust tiers + lifecycle | **Yes** — all candidates registered here |
| Intake pipeline (DISCOVER→…) | **Yes** |
| Forbidden surfaces / T4 ban | **Yes** |
| DatasetManifest + BenchmarkTradeRecord + CanonicalMetrics | **Yes for LEAN / Nautilus / VectorBT / Qlib** |
| Fill model + lookahead + repro | **Yes for execution track** |
| Comparison matrix pattern | **Yes** (separate matrices per track) |
| Semantic OS as meaning authority | **Yes — do not replace** |
| Trade-centric adapters only | **No** — need StructuralFactRecord track for Codebase-Memory / Infigraph |

### Two tracks (same lab root)

```text
oss_lab/
  TRACK A — EXECUTION / RESEARCH
    DatasetManifest → adapters → BenchmarkTradeRecord → CanonicalMetrics

  TRACK B — REPO INTELLIGENCE
    local repo tree → adapters → StructuralFactRecord → (future) Semantic OS ingestion
```

Do **not** invent a second lab package.

---

## Priority order (this cycle)

| Pri | oss_id | Tier | Decision | Action |
|---|---|---|---|---|
| **1** | OSS-CODEBASE-MEMORY | T1 | **APPROVED_FOR_LAB** | First run done: `RI-RUN-20260812T214500Z` 12/12; report under results + `oss_lab/reports/` |
| **2** | OSS-LEAN | T3 | DISCOVERED | Add to execution three-way with Nautilus + Tradelatest |
| **3** | OSS-RIG-METHOD | T0 | REFERENCE_ONLY | Use as methodology input for repo-intel scenario design |
| **4** | OSS-INFIGRAPH | T1 | DISCOVERED | Head-to-head vs Codebase-Memory only — no dual adopt |
| **5** | OSS-VECTORBT | T2 | DEFERRED | Legal review Commons Clause first |
| — | OSS-NAUTILUS | T3 | DISCOVERED | Remains on execution track (LGPL gate) |
| — | OSS-QLIB / OSS-FINRLX | T2 | DISCOVERED | Research track; not this-week critical path |

---

## Safe architectures (confirmed)

### Repo intelligence

```text
Codebase-Memory ──┐
Infigraph ────────┼─► StructuralFactRecord ─► Semantic OS ingestion ─► meaning
local pyan/dot ───┘                              (advisory)
```

**Not:**

```text
Codebase-Memory = Semantic OS   ✗
```

### Execution

```text
          SAME market reality (DatasetManifest)
                     │
      ┌──────────────┼──────────────┐
      ▼              ▼              ▼
 Tradelatest      Nautilus         LEAN
      │              │              │
      └──────────────┼──────────────┘
                     ▼
            BenchmarkTradeRecord
                     ▼
             CanonicalMetrics
```

**Not:** import LEAN strategy model into Tradelatest.

---

## Existing Tradelatest assets to reuse before installing anything

| Asset | Role vs monitor candidates |
|---|---|
| `graph.dot` / `scripts/analysis/gen_pyan.py` | Local structural baseline for repo-intel H2H |
| `src/governance/semantic_os.py` + YAML | Meaning layer (ingestion target, not competitor) |
| `src/control_plane/dot_graph_context.py` | Existing graph context for agents |
| `oss_lab/*` (already built) | Registry, contracts, metrics, lifecycle |
| Phase-1 XAUUSD pin | Execution track market reality |
| Runtime benchmark suite | Sibling runtime authority; do not conflate |

---

## What NOT to do this week

1. Do not `pip install` / download binaries into production venv.
2. Do not dual-deploy Codebase-Memory **and** Infigraph.
3. Do not treat arXiv RIG / Codebase-Memory published gains as Tradelatest evidence.
4. Do not depend on VectorBT until Commons Clause legal review.
5. Do not wire any of these into CRT / Fusion / Decision / Ultron / production config.
