# Canonical Feature Code Surface Closure Gate

_Date: 2026-07-11 · ACTIVE_VERSION=`v2_multi_2026_04`_

## Gate result

```text
CANONICAL_FEATURE_CODE_SURFACE_STATUS = CLOSED

38 CLOSED / 0 PARTIAL / 0 OPEN / 0 STALE_CENSUS
```

Evidence: [`feature_surface_closure_audit-2026-07-11.json`](feature_surface_closure_audit-2026-07-11.json)  
Driver: `scripts/analysis/feature_surface_closure_audit.py`

## Work that cleared the last two PARTIAL rows

| Residual | Class | Action | Equivalence? |
|---|---|---|---|
| `wick_size` | **Governance/ontology** | Exact alias → FM-002 `candle_range` (`aliases: [wick_size]`) | **Not** a second formula identity |
| `volatility_regime` | **Semantic correctness** | FC1-D: production → rolling causal ATR tercile N=200 | Material PIT/behavior change; global demoted to research column |

Plus mechanical: re-export [`feature_38_lineage_census-2026-07-11.json`](feature_38_lineage_census-2026-07-11.json) (also refreshed stable 2026-07-10 path).

## Separate state machine — artifact economic admissibility

**Still NOT closed** (do not conflate with the 38-row gate):

```text
BLOCKED FOR ECONOMIC USE OF EXISTING ARTIFACTS

1. RR PIT_UNCLEAN_CENTERED_SWINGS
2. Zone PIT_UNCLEAN_CENTERED_SWINGS
3. Causal dataset regeneration / revalidation before promotion
4. Existing model-specific lineage defects and §6.5 marginal-value requirements
```

Closing the feature code surface does **not** authorize RR/Zone reuse, model enablement, or economic claims.

## Explicit non-claims

- No ΔG001 / edge from FC1-A or FC1-D  
- No automatic model retrain  
- `volatility_regime` remains **local ATR-percentile context**, not latent Regime Detection (FC-0.5 adjudication)
