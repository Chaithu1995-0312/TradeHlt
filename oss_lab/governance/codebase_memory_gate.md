# Gate: Codebase-Memory → APPROVED_FOR_LAB

| Field | Value |
|---|---|
| oss_id | `OSS-CODEBASE-MEMORY` |
| Current lifecycle | **`APPROVED_FOR_LAB`** (G1–G6 complete 2026-08-12) |
| Target lifecycle | `APPROVED_FOR_LAB` ✓ |
| After lab approval | isolated install + REPO-INTEL-QA-V1 only — **still no Semantic OS mutation** |
| Production integration | **Not in scope** |
| Pin | **v0.10.2** @ `b377c62a4e8b7ad64ccd295e4aa88abc8d275180` |
| Evidence | `G1_G3_gate_evidence.json` · `G4_G6_gate_evidence.json` |

---

## Gate criteria

### G1 — License — **PASS**

| Check | Status | Evidence |
|---|---|---|
| License file is MIT | **PASS** | LICENSE at pin `b377c62a…`; local copy under evidence pack |
| Obligations recorded | **PASS** | retain copyright + include license |

### G2 — Version pin — **PASS**

| Check | Status | Evidence |
|---|---|---|
| Exact tag or commit chosen | **PASS** | `v0.10.2` → `b377c62a4e8b7ad64ccd295e4aa88abc8d275180` |
| Registry updated | **PASS** | `oss_capabilities.jsonl` |
| Reproducible download URL | **PASS** | GitHub release asset URLs |

### G3 — Security / install surface — **PASS_WITH_RESIDUALS**

| Check | Status | Evidence |
|---|---|---|
| Source audit | **PASS** | README + SECURITY.md |
| SHA-256 of Windows zip | **PASS** | `8f08e5c5b480e625adf9d4560765a860d493a690df6ded5b94127283ec5b660a` |
| SLSA / Sigstore local verify | **RESIDUAL** | tools absent; cosign **bundle downloaded** for future verify |
| Install isolation path | **PASS** | `INSTALL_ISOLATION.md` + dirs created |
| Network posture | **PASS_WITH_RESIDUAL** | update-check after MCP initialize documented |
| Secrets / `.env` | **PASS_WITH_CONTROLS** | `lab.cbmignore` template |

### G4 — Architectural boundary — **PASS**

| Check | Status | Evidence |
|---|---|---|
| Allowed surfaces only lab/evidence/results (+ tools install tree) | **PASS** | registry + INSTALL_ISOLATION + `G4_G6_gate_evidence.json` |
| Forbidden semantic_os / production / CRT / core | **PASS** | registry `forbidden_surfaces` re-verified |
| Output contract = `StructuralFactRecord` only | **PASS** | `oss_lab/contracts/structural_fact.py` + registry `output_contract` |
| Non-goal: replace Semantic OS | **PASS** | ARCHITECTURE_APPROVAL + semantic_os_mapping |

### G5 — Benchmark readiness — **PASS**

| Check | Status | Evidence |
|---|---|---|
| Fixed Q&A corpus frozen | **PASS** | `REPO-INTEL-QA-V1` (12 items) |
| Local baselines named | **PASS** | pyan · `graph.dot` · `dot_graph_context` |
| Evidence output directory | **PASS** | `results/oss_lab/repo_intel/runs/` created |
| RunManifest fields planned | **PASS** | `REPO_INTEL_RUN_MANIFEST_PLAN.json` |
| Secrets ignore template | **PASS** | `lab.cbmignore` |

### G6 — Lifecycle transition — **PASS**

| Check | Status | Evidence |
|---|---|---|
| All G1–G5 PASS | **PASS** | this document |
| Registry `decision` → `APPROVED_FOR_LAB` | **PASS** | `oss_capabilities.jsonl` |
| Session log + evaluation queue | **PASS** | this turn |

---

## What APPROVED_FOR_LAB authorizes

```text
✓ Isolated extract/install under tools/oss_lab/codebase-memory/v0.10.2/
✓ CBM_CACHE_DIR under results/oss_lab/repo_intel/cbm_cache/
✓ Index Tradelatest with lab.cbmignore + CBM_ALLOWED_ROOT
✓ Run REPO-INTEL-QA-V1 → StructuralFactRecord / report under results/oss_lab/repo_intel/runs/
```

## What it does **not** authorize

```text
✗ Semantic OS live YAML mutation
✗ Production agent default MCP wiring (use --skip-config)
✗ T4 production authority
✗ Findings promotion without measurement discipline
✗ Dual Infigraph adoption without H2H
```

---

## Optional SLSA residual — **ATTEMPTED_TOOLS_ABSENT**

| Item | Status |
|---|---|
| `gh` CLI | not installed |
| `cosign` | not installed |
| Windows zip SHA-256 | **PASS** (load-bearing integrity today) |
| Cosign bundle local | **downloaded** `…/codebase-memory-mcp-windows-amd64.zip.bundle` (10559 bytes) |

When tools are available:

```text
gh attestation verify results/oss_lab/repo_intel/codebase_memory_v0.10.2/codebase-memory-mcp-windows-amd64.zip ^
  --repo DeusData/codebase-memory-mcp ^
  --signer-workflow DeusData/codebase-memory-mcp/.github/workflows/_build.yml

cosign verify-blob --bundle results/oss_lab/repo_intel/codebase_memory_v0.10.2/codebase-memory-mcp-windows-amd64.zip.bundle ^
  results/oss_lab/repo_intel/codebase_memory_v0.10.2/codebase-memory-mcp-windows-amd64.zip
```

**Policy:** first **execute** should still run these if tools exist. SHA-256 pin remains the verified integrity proof for APPROVED_FOR_LAB.

---

## Fail-closed rules (still)

- Do not install into production `venv/`
- Prefer `--skip-config`
- No `docs/governance/semantic_os/*.yaml` edits
- Do not treat arXiv gains as Tradelatest evidence

---

## Operator checklist

```text
[x] G1 license confirmed at pin
[x] G2 version/commit pinned in registry
[x] G3 security notes + SHA-256 artifacts
[x] G3 install path isolated
[x] G3 residual documented (SLSA tools absent; bundle saved)
[x] G4 architectural boundary certified
[x] G5 Q&A corpus + run dirs + RunManifest plan
[x] G6 lifecycle APPROVED_FOR_LAB
[x] Explicit: NO semantic_os/*.yaml edits
[ ] Next: isolated extract/install + REPO-INTEL-QA-V1 run
```

---

## Pin quick reference

| Item | Value |
|---|---|
| Version | v0.10.2 |
| Commit | b377c62a4e8b7ad64ccd295e4aa88abc8d275180 |
| Windows SHA-256 | 8f08e5c5b480e625adf9d4560765a860d493a690df6ded5b94127283ec5b660a |
| Archive | `results/oss_lab/repo_intel/codebase_memory_v0.10.2/` |
| Isolation | `oss_lab/adapters/codebase_memory/INSTALL_ISOLATION.md` |
| G4–G6 evidence | `oss_lab/evidence/repo_intel/codebase_memory_v0.10.2/G4_G6_gate_evidence.json` |
