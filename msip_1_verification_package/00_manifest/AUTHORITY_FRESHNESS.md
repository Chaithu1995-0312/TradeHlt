# Authority & Freshness Rules (MSIP-1 package)

**Generated:** 2026-07-14T07:08:43Z

Independent verifiers **must** apply these rules. Historical evidence remains in the package
for lineage, but must not override fresher authorities.

## Precedence (high → low) within this package

1. **Executable production code** in `02_feature_authority/` and `04_crt_runtime/`
2. **Active config / WHO registry:** `ACTIVE_VERSION`, `v2_multi_2026_04.json`, `active_models.yaml`
3. **Closure authorities:** `closure_authority_index.json` → named authoritative artifacts
4. **Dated governance evidence 2026-07-11+** (lineage census body, feature-code closure, surface audit, FC1-A)
5. **Certification ledger / DAG layers / M15 census** (descriptive; grants no production authority)
6. **Historical 2026-07-10 fc05 / phase1 / feature_contract_v1** — useful history; **superseded where noted**
7. **feature_surface_query.py** — join/aggregation only
8. **MSIP design docs** — proposed; not repository truth until verified + implemented

## Explicit supersessions

| Topic | Stale risk | Current authority in package |
|---|---|---|
| Swing / structure PIT | fc05 dependency graph may say LEAKING / inherited lookahead for double_sweep family | FC1-A contract + `causal_structure.py` + `feature_pipeline.py` causal publication + `test_fc1a_swing_causal.py` |
| CRT emission names retest/disp | pre-CH-002 cache keys `retest_depth`/`disp_strength` confusion | `crt_closure_report.md` CH-002 + crt_engine_v2 emission of `displacement_retrace` / `displacement_atr_ratio` |
| Feature contract v1 | may predate later separations | Use identity registry + ontology + pipeline; contract is HISTORICAL |
| Consumer manifest 2026-07-10 | may lag M9–M15 certifications | Prefer later certification notes / M15 census for known encoding debts |
| LATEST pointers | always resolve to dated body + verify sha256 | `feature_38_lineage_census-2026-07-11.json`, `feature_dag_layers-2026-07-14.json` |

## Non-transitive closure (mandatory)

From `closure_authority_index.json`:

- CRT CLOSED does **not** close Gaussian/ZoneGate/RR/BitNet/TradeNet or Feature Query Surface.
- CANONICAL_FEATURE_CODE_SURFACE CLOSED does **not** authorize model enablement or economic claims.
- Feature Query Surface AUTHORITY_ACTIVE does **not** close producers/consumers/models.

MSIP must not be declared CLOSED by inheritance from any of the above.

## Economic evidence ban

Backtest PnL, expectancy, and strategy performance are **out of scope** for MSIP-1 verification.
