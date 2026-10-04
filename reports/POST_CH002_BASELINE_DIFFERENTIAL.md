# POST-CH-002 BASELINE DIFFERENTIAL

**Status:** **PASS** — trading behavior identical to frozen pre-remediation baseline  
**Date (UTC):** 2026-07-09  
**Branch:** `feature/truth-registry-v2`  
**HEAD:** `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (CH-002 F-050 emission rename)  
**Purpose:** Empirical proof that CH-002 was semantic-only (no trading delta).

---

## Verdict

```text
POST_CH002_BASELINE_DIFFERENTIAL = PASS
BEHAVIOR_CHANGE = NO
CRT_FREEZE_AUTHORIZED = YES
```

CH-002 declared an emission-key rename (FM-027/FM-028). Gate-ON BNBUSDT full-corpus backtest post-remediation reproduces the frozen pre-remediation economics and journal trade identity **exactly**.

---

## 1. Pins (ORIENT_RUNTIME)

| Pin | Pre-freeze (`PRE_REMEDIATION_BASELINE`) | Post-CH-002 run | Match |
|---|---|---|---|
| ACTIVE_VERSION | `v2_multi_2026_04` | `v2_multi_2026_04` | YES |
| Config SHA-256 | `8f45c66c…e778ae` | `8f45c66c…e778ae` | YES |
| Corpus | `data/BNBUSDT_M15.csv` | same | YES |
| Corpus SHA-256 | `083f2bdf…bcddce` | `083f2bdf…bcddce` | YES |
| EngineRunner gate | `BACKTEST_ENGINE_GATE=1` | forced ON (log: gate wired) | YES |
| Zone registry | `models/zone_registry.json` | 8 zones loaded | YES |

---

## 2. Command (production-fidelity)

```powershell
cd D:\Tradelatest
$env:PYTHONPATH = "D:\Tradelatest\src"
$env:BACKTEST_ENGINE_GATE = "1"
venv\Scripts\python.exe src\runtime\backtest_v2.py `
  --csv data\BNBUSDT_M15.csv `
  --instrument BNBUSDT `
  --output results\baseline_post_ch002
```

Log confirmation: `EngineRunner gate wired into backtest path (BACKTEST_ENGINE_GATE=1)`.

---

## 3. Artifacts compared

| Role | Path |
|---|---|
| Frozen pre (authority) | `results/baseline/run1/` |
| Post-CH-002 run | `results/baseline_post_ch002/run_20260709_161820_BNBUSDT/` |
| Pre durable report | `reports/PRE_REMEDIATION_BASELINE.md` |

---

## 4. Economic / funnel parity

| Metric | Pre (run1) | Post | Result |
|---|---:|---:|---|
| total_setups (CRT candidates) | 13 | 13 | **PASS** |
| approved_trades | 11 | 11 | **PASS** |
| rejected_trades | 2 | 2 | **PASS** |
| rejection_reasons | `invalid_session:0.0` ×2 | same | **PASS** |
| win_rate | 0.2727 (27.3%) | 0.2727 | **PASS** |
| avg_rr_net (E) | −0.3865 R | −0.3865 R | **PASS** |
| total_pnl_rr_net | −4.251 R | −4.251 R | **PASS** |
| total_pnl_rr_raw | −2.633 R | −2.633 R | **PASS** |
| max_drawdown_pct | 5.63% | 5.63% | **PASS** |
| max_drawdown_rr | 5.7318 R | 5.7318 R | **PASS** |
| final_capital | 95,758.16 | 95,758.16 | **PASS** |
| Profit factor (from trade pnl) | 0.509 | 0.509 | **PASS** |
| `BNBUSDT_summary.json` SHA-256 | `d32c75e2…d3bd1` | `d32c75e2…d3bd1` | **BYTE-IDENTICAL** |

Gate-ON fidelity confirmed: 2 ER rejects (not gate-OFF's 0 rejects / 13 journal trades).

---

## 5. Journal trade identity

All 11 admitted trades match pre ledger on `trade_id` + `pnl_rr_net` (and all other economic columns):

| trade_id | pnl_rr_net | Identity |
|---|---:|---|
| CRT-0002 | +0.7436 | PASS |
| CRT-0003 | −0.9732 | PASS |
| CRT-0004 | −1.0684 | PASS |
| CRT-0005 | −1.0811 | PASS |
| CRT-0006 | −0.9558 | PASS |
| CRT-0007 | +1.8189 | PASS |
| CRT-0008 | −1.2892 | PASS |
| CRT-0009 | −1.0789 | PASS |
| CRT-0010 | −1.1041 | PASS |
| CRT-0012 | +1.8440 | PASS |
| CRT-0013 | −1.1068 | PASS |

Not journaled (OI-ER-001 residual, unchanged): CRT-0001, CRT-0011.

---

## 6. Candidate timestamps (13 TRADE_OPENED)

All 13 event timestamps match pre `BNBUSDT_events.jsonl`:

```text
2024-05-24T07:45:00
2024-10-28T13:45:00
2024-11-07T14:00:00
2025-01-13T15:15:00
2025-01-19T09:15:00
2025-02-17T13:45:00
2025-03-15T08:15:00
2025-06-15T09:15:00
2025-08-02T09:00:00
2025-10-04T09:45:00
2025-12-09T07:30:00
2026-02-12T14:00:00
2026-03-18T13:45:00
```

---

## 7. Telemetry-only observation (non-stop)

Full-column trade CSV compare: **9/11 trades byte-identical across all columns**.

| trade_id | Field | Pre | Post | Cause |
|---|---|---:|---:|---|
| CRT-0002 | `cached_retest_depth` | 1.052632 | 1.0 | FM-027 clip `[0,1]` via `derived_math.displacement_retrace` |
| CRT-0008 | `cached_retest_depth` | 1.009709 | 1.0 | same |

- `cached_disp_strength` identical on all trades.
- Pipeline `retest_depth` / `disp_strength` (FM-021/FM-020) identical.
- **No trade outcome, PnL, or admission change** from the clip.
- Pre-rename path could emit retrace slightly >1.0; CH-001 registered math clips to `[0,1]` (documented in `derived_math.py:106-120`). Journal alias `cached_retest_depth` now carries the clipped FM-027 value.

**Classification:** telemetry/journal field normalization — **not a trading-behavior delta**. Does not reverse PASS.

Trades CSV SHA differs solely due to these two alias cells (expected).

---

## 8. Stop-condition check

| Stop condition | Observed | Action |
|---|---|---|
| Candidate count delta | none | continue |
| Admitted trade delta | none | continue |
| Timestamp / trade_id delta | none | continue |
| PnL / E / PF / WR / MaxDD delta | none | continue |
| Accidental gate-OFF (13 journal / 0 ER) | no (11 / 2) | continue |

---

## 9. Implications

1. **CRT rediscovery stays closed.** Empirical parity completes CH-002's semantic-only claim.
2. **Do not retrain models because of the rename.** Live trading path is unchanged.
3. **Next work:** model/training lineage audits (Gaussian → ZoneGate → RR → BitNet → TradeNet), not CRT re-audit, not mass rebuild.
4. Residual non-blockers (OI-ER-001, F-048, historical JSONL keys, BitNet inert) remain **downstream** — see `docs/governance/crt_closure_report.md`.

---

## 10. Files

| Path | Role |
|---|---|
| `reports/POST_CH002_BASELINE_DIFFERENTIAL.md` | This report |
| `results/baseline_post_ch002/run_20260709_161820_BNBUSDT/*` | Post-run artifacts |
| `results/baseline/run1/*` | Frozen pre authority |
| `reports/PRE_REMEDIATION_BASELINE.md` | Pre freeze documentation |

**Production code / configs / models:** not modified by this differential.

---

## COMPLETION_STATUS

**COMPLETE — PASS.** Gate-ON BNBUSDT post-CH-002 baseline is behaviorally identical to the frozen pre-remediation baseline. CRT freeze authorized. Proceed to Gaussian lineage audit.
