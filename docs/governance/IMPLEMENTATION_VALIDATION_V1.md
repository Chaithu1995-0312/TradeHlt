# IMPLEMENTATION_VALIDATION_V1

**Milestone freeze — post-P0/P1 implementation governance baseline**

| Field | Value |
|---|---|
| **ID** | `IMPLEMENTATION_VALIDATION_V1` |
| **Frozen run** | `20260722T165028Z` |
| **ACTIVE_VERSION** | `v2_multi_2026_04` |
| **Corpus** | Phase-1 frozen XAUUSD M15 `data/mt5/XAUUSD_M15.csv` (pin match) |
| **Schema** | v4.0 / 39-dim |
| **Bars** | 47,197 feature rows |
| **Artifact** | [`results/implementation_validation/IMPLEMENTATION_VALIDATION_V1.json`](../../results/implementation_validation/IMPLEMENTATION_VALIDATION_V1.json) |
| **SHA-256** | see `IMPLEMENTATION_VALIDATION_V1.sha256` |
| **Harness** | `scripts/analysis/implementation_model_validation_xauusd.py` |

> Scope: **implementation correctness only**. No profitability. No promotion. No retrain.

---

## Acceptance criteria

| Criterion | Result |
|---|---|
| No FAIL_OPEN execution paths | **PASS** (count = 0) |
| Name-based schema contracts | **PASS** (Gaussian NB name-anchored; ZoneGate feature_order subset) |
| Production artifact resolution validated | **PASS** (ZoneGate v4 via ModelResolver; BitNet catalog) |
| Active registries governed | **PASS** (zone / gaussian / bitnet / rr selection rules) |
| Runtime guards fail closed | **PASS** (RR Fusion dim refuse; BitNet enable-without-selection refuse) |
| Validation harness exercises production paths | **PASS** |
| Remaining issues are intentional architecture | **PASS** (see P2 below) |

---

## Execution matrix (authoritative)

| Model | Loaded | Executed | Features OK | Outputs Healthy | Failure Mode | Raw Status |
|---|---|---|---|---|---|---|
| CRT | True | True | True | True | **PASS** | OK |
| RR polarity | True | True | True | True | **PASS** | OK |
| ZoneGate | True | True | True | True | **PASS** | OK |
| Gaussian heuristic (live) | True | True | True | True | **DEGRADED** | OK |
| Gaussian trained NB | True | True | True | True | **ORPHAN** | EXECUTED_ORPHAN |
| RR Fusion | False | False | False | False | **FAIL_CLOSED** | LOAD_FAIL |
| TradeNet | True | True | False | True | **ORPHAN** | EXECUTED_ORPHAN |
| BitNet | True | True | True | True | **DISABLED** | EXECUTED_DISABLED_ON_SPINE |

**FAIL_OPEN count: 0**

---

## What this milestone means

The repository has moved from *implementation uncertainty* to *implementation governed*:

```
Artifact Exists → Catalogued → Selected → Enabled → Serving
```

Silent schema corruption paths (RR Fusion index truncate, Gaussian ambient truncate) are closed.  
Production ZoneGate resolves the remapped v4 artifact.  
BitNet is catalogued with dual-schema fork explicit; enablement requires selection.

---

## Bugs retained in the freeze (non–FAIL_OPEN)

| Severity | Code | Model | Interpretation |
|---|---|---|---|
| Critical | `GAUSSIAN_DEFAULT_MU_SIGMA` | heuristic | Live kernel unparameterized (F-060) — **DEGRADED truth**, not silent mis-score |
| Critical | `RR_FUSION_DIM_LOAD_REFUSED` | RR Fusion | **Protective** refuse under v4 — FAIL_CLOSED |
| High | `GAUSSIAN_NEAR_CONSTANT` | heuristic | Information-poor live channel |
| High | `GAUSSIAN_NO_XAUUSD_REGISTRY` | heuristic | No XAUUSD active pointer; miss cached (P1) |
| High | `RR_NAME_SEMANTIC_MISMATCH` | RR polarity | CPI vs DecisionEngine threshold — consumer semantics (F-048) |
| High | `TRADENET_*` | TradeNet | No torch / dim — research orphan |
| Medium | `RR_REGISTRY_PATH_DRIFT` | RR Fusion | Technical debt |
| Low | `BITNET_DUAL_SCHEMA` | BitNet | **Intentional** fork |
| Low | `GAUSSIAN_NAME_ANCHORED_OK` | Gaussian NB | Contract success note |

---

## P2 — intentional (do not “fix” without intent)

1. **RR registry path drift** — technical debt; unify via ModelResolver later.  
2. **TradeNet / PyTorch** — environment qualification: support torch **or** keep research-only.  
3. **Dual BitNet schemas** — leave split until one serve contract is chosen.

---

## How to re-validate

```bash
python scripts/analysis/implementation_model_validation_xauusd.py
# compare failure_mode_summary + FAIL_OPEN count against this freeze
```

Optional local tag (not created automatically):

```bash
git tag -a IMPLEMENTATION_VALIDATION_V1 -m "Post-P0/P1 implementation governance freeze"
```

---

## Session lineage (what landed before this freeze)

| Work | Outcome |
|---|---|
| RR Fusion P0 | No silent 39→38 truncate; load refuse on dim mismatch |
| ZoneGate | v4 ALIGNMENT_REMAP production path re-validated PASS |
| Gaussian NB P0 | Name-anchored load/score; no ambient truncate |
| Gaussian retry cache P1 | Miss cached; one warning per epoch |
| BitNet registry P1 | Catalog + Exists≠Selected≠Enabled + enable guard |

**Authority:** implementation / governance only. No economic promote. No retrain implied.
