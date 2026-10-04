# REM-COST-04 — L5 cost vocabulary extension proposal (governance)

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Status** | PROPOSAL ONLY — do not edit `src/identity/tokens.py` until authorized |
| **Authority** | RESEARCH / governance |
| **Parents** | CANONICAL_LAYER_IDENTITY_CONTRACT L5 · cost-model-identity-stamping.md · CH-cost-model-identity-stamp · live_alert_v1 |

## Problem

Production backtest stamps `cost_model_id=backtest_g1g2_v2` (measured on fresh emit `run_20260916_225925_XAUUSD`, hash `8239f7adde53080c`).

L5 closed set in `src/identity/tokens.py` is still:

```
{flat_12bps, sem015_component_xauusd, none_gross}
```

So ledger outcomes cannot be certified as L5 objects under the cost surface they actually used. Same L4 geometry + different cost must be different L5 (contract).

## Proposed vocabulary (additive)

| id | Role | Generate? |
|---|---|---|
| `backtest_g1g2_v2` | Production G1+G2 knobs (spread % + ATR slip + seed) | **Yes** — already derived in `backtest_v2` |
| `backtest_zero_cost` | Reserve-only (never generated today) | Declare only |
| `flat_12bps` | Research falsification | Existing |
| `sem015_component_xauusd` | Measured XAU component model | Existing |
| `none_gross` | Explicit gross / Ultron admission today | Existing |

### Alias table (do not silently merge)

| Production / stamp | Research L5 | Notes |
|---|---|---|
| `backtest_g1g2_v2` | — | New closed member |
| `metals_mt5_v1` (plan reserved) | `sem015_component_xauusd` | Alias doc only until wiring; different names must not collapse without explicit SAFE_ALIAS |

## Acceptance (when authorized)

1. Add ids to `COST_MODEL_IDS` with tests that closed-set rejects unknowns.
2. Fresh stamp emit still byte-identical on `pnl_rr_*`.
3. Impact manifest + dual-world note: research path (`cost_model_bps`) vs production (`cost_model_id`) remain distinct until a later reconcile.

## Non-goals this proposal

- Wiring SEM-015 into `backtest_v2` charge path
- Activating Ultron pip tax
- Rewriting historical CSVs (sidecar stamp already covers Sept 16 morning run)

## Decision required

Authorize a governance PR that only extends the frozenset + tests + docs — no PnL math.
