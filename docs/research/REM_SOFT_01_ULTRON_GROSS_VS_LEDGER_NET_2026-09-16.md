# REM-SOFT-01 — Ultron gross RR vs ledger net (design note)

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Status** | DESIGN NOTE — tax stays dormant (`spread_pips=0`, `slippage_pips=0`) |
| **Authority** | RESEARCH_ONLY |
| **Parents** | ultron_risk_gate config comments · cost audit · live_alert_v1 BLOCKER_OPEN |

## Measured split

| Layer | Cost surface | RR meaning |
|---|---|---|
| **UltronRiskGate** admission | Effective `none_gross` while pip tax = 0 | `min_rr_ratio` on **raw** CRT RR |
| **Backtest ledger** | `backtest_g1g2_v2` | `pnl_rr_net` after G1+G2 fills |
| **Research SEM-015** | `sem015_component_xauusd` | Exit-aware USD/oz → R (shadow only) |

Config already declares this dormancy (2026-08-19 comment): activating non-zero Ultron tax is a **separate authorized decision**. `pip_size=0.0001` is FX-major and wrong for XAU (true pip ≈ 0.01) — inert while tax is zero.

## Remediation design (not activated)

### Option A — Document-only (current)

Stamp admission as `cost_model_id=none_gross` in any live preflight report. Ledger remains G1+G2. Alerts already raise BLOCKER_OPEN.

### Option B — SEM→R tax mapping (future authorize)

Map SEM-015 components to an R haircut at gate:

```
cost_R ≈ ComponentCostModel.cost_r(entry, risk_distance, exit_kind=SL_HIT|TP)
gate_rr_net = raw_rr - cost_R
```

Use instrument price units (USD/oz), **not** FX `pip_size`. Reject wiring SEM dollars into `spread_pips` without converting via correct XAU pip/R denom.

### Option C — Mirror G1+G2 at gate (discouraged)

Would couple live admission to backtest RNG slip — breaks broker-truth intent of SEM-015.

## Recommended next

1. Keep Option A until REM-COST-04 lands (so ledger L5 is nameable).
2. If activating a tax, prefer Option B with explicit config keys (not silent defaults) + XAU pip table.
3. Never claim live↔backtest RR equivalence while gate is gross and ledger is net.

## Non-goals

- Changing `configs/production/v2_htfcrt_2026_08.json` Ultron zeros in this note
- Economic claims from shadowed SEM nets

## Measured shadow (2026-09-16) — stamped run `run_20260916_225925_XAUUSD`

Script: `scripts/research/ultron_sem_r_shadow.py`  
Artifacts: `results/run_20260916_225925_XAUUSD/cost_audit/ultron_sem_r_shadow.{csv,json}`

Gate assumption: `min_rr_ratio=1.5`, SEM cost_R under **SL_HIT** (conservative admission haircut).

| Trade | planned TP1 R (raw) | admit gross | gate R SEM-shadow | admit SEM-shadow | flip |
|---|---:|---|---:|---|---|
| CRT-0001 | 1.00 | no | 0.92 | no | no |
| CRT-0002 | 1.50 | **yes** | 1.12 | **no** | **yes** |
| CRT-0003 | 1.50 | **yes** | 1.20 | **no** | **yes** |

**n_flip = 2 / 3.** Tight-stop / exact-1.5R plans fail SEM shadow while passing dormant Ultron gross gate. Reinforces: do not claim live↔ledger RR equivalence; activating SEM→R would change admission on this sample.

Ultron config zeros **unchanged**.
